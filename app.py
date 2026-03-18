import hmac
import json
import logging
import os
import secrets
import time
import threading
from datetime import timedelta
from functools import wraps
import requests
from flask import Flask, render_template, jsonify, request, redirect, session, url_for

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

_secret_key = os.environ.get("SECRET_KEY", "")
if not _secret_key:
    _secret_key = secrets.token_hex(32)
    logger.warning("SECRET_KEY not set — sessions will not survive container restarts")
app.secret_key = _secret_key
app.permanent_session_lifetime = timedelta(days=3650)

RAINDROP_TOKEN = os.environ.get("RAINDROP_TOKEN", "")
CACHE_TTL = int(os.environ.get("CACHE_TTL", 3600))  # seconds, default 1 hour
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
READONLY_PASSWORD = os.environ.get("READONLY_PASSWORD", "")
API_BASE = "https://api.raindrop.io/rest/v1"
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CACHE_KEY = "raindrop_data"
CACHE_TS_KEY = "raindrop_data_ts"

# --- Redis client (optional — falls back to in-memory if unavailable) ---
_redis = None
_redis_error = None
try:
    import redis as _redis_lib
    _redis = _redis_lib.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
    _redis.ping()
    logger.info("Redis connected: %s", REDIS_URL)
except Exception as e:
    _redis_error = str(e)
    _redis = None
    logger.warning("Redis unavailable (%s) — using in-memory cache", _redis_error)

# --- Startup validation ---
if not RAINDROP_TOKEN:
    logger.error("RAINDROP_TOKEN is not set — bookmarks will not load")
else:
    logger.info("RAINDROP_TOKEN configured (len=%d)", len(RAINDROP_TOKEN))
logger.info("CACHE_TTL=%ds", CACHE_TTL)
if DASHBOARD_PASSWORD:
    logger.info("Dashboard password protection: enabled")
    if READONLY_PASSWORD:
        logger.info("Read-only password: enabled")
else:
    logger.info("Dashboard password protection: disabled (DASHBOARD_PASSWORD not set)")

# In-memory fallback
_mem_cache = {"data": None, "ts": 0}

# Prevent concurrent background revalidations
_revalidating = False
_revalidate_lock = threading.Lock()


def _cache_get_with_age():
    """Return (data, age_seconds) from cache. data=None if nothing cached."""
    if _redis:
        try:
            raw = _redis.get(CACHE_KEY)
            ts_raw = _redis.get(CACHE_TS_KEY)
            if raw:
                age = time.time() - float(ts_raw) if ts_raw else CACHE_TTL + 1
                return json.loads(raw), age
        except Exception:
            pass
    if _mem_cache["data"]:
        return _mem_cache["data"], time.time() - _mem_cache["ts"]
    return None, None


def _cache_get():
    data, age = _cache_get_with_age()
    if data is not None and age is not None and age < CACHE_TTL:
        return data
    return None


def _cache_set(data):
    now = time.time()
    if _redis:
        try:
            # Store data with 2× TTL so stale data survives for SWR
            _redis.setex(CACHE_KEY, CACHE_TTL * 2, json.dumps(data))
            _redis.setex(CACHE_TS_KEY, CACHE_TTL * 2, str(now))
        except Exception:
            pass
    _mem_cache["data"] = data
    _mem_cache["ts"] = now


def _cache_bust():
    if _redis:
        try:
            _redis.delete(CACHE_KEY)
            _redis.delete(CACHE_TS_KEY)
        except Exception:
            pass
    _mem_cache["data"] = None
    _mem_cache["ts"] = 0


def _do_revalidate():
    """Background worker: fetch fresh data and update cache."""
    global _revalidating
    try:
        data = _fetch_from_api()
        _cache_set(data)
    except Exception:
        pass
    finally:
        with _revalidate_lock:
            _revalidating = False


def headers():
    return {"Authorization": f"Bearer {RAINDROP_TOKEN}"}


def fetch_collections():
    """Fetch all root and child collections, deduplicating by ID."""
    seen = set()
    colls = []
    for endpoint in ["/collections", "/collections/childrens"]:
        r = requests.get(f"{API_BASE}{endpoint}", headers=headers(), timeout=15)
        r.raise_for_status()
        for c in r.json().get("items", []):
            if c["_id"] not in seen:
                seen.add(c["_id"])
                colls.append(c)
    colls.sort(key=lambda c: c.get("title", "").lower())
    return colls


def fetch_raindrops(collection_id, page=0, per_page=50):
    """Fetch raindrops for a single collection (paginated)."""
    all_items = []
    while True:
        r = requests.get(
            f"{API_BASE}/raindrops/{collection_id}",
            headers=headers(),
            params={"page": page, "perpage": per_page, "sort": "sort"},
            timeout=15,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        all_items.extend(items)
        if len(items) < per_page:
            break
        page += 1
    return all_items


def fetch_all():
    """Return cached data immediately (stale-while-revalidate).
    If cache is stale, serve old data and kick off a background refresh.
    If cache is empty (cold start), block synchronously."""
    global _revalidating
    data, age = _cache_get_with_age()

    if data is not None:
        if age is not None and age >= CACHE_TTL:
            # Stale — serve immediately and revalidate in background
            with _revalidate_lock:
                if not _revalidating:
                    _revalidating = True
                    t = threading.Thread(target=_do_revalidate, daemon=True)
                    t.start()
        return data

    # Cold start — no cached data at all, must block
    fresh = _fetch_from_api()
    _cache_set(fresh)
    return fresh


def _fetch_from_api():
    """Fetch all collections and bookmarks fresh from the Raindrop API."""
    collections = fetch_collections()
    grouped = []
    for coll in collections:
        cid = coll["_id"]
        raindrops = fetch_raindrops(cid)
        if not raindrops:
            continue
        grouped.append(
            {
                "id": cid,
                "title": coll.get("title", "Untitled"),
                "parent_id": coll.get("parent", {}).get("$id") if isinstance(coll.get("parent"), dict) else None,
                "count": coll.get("count", len(raindrops)),
                "color": coll.get("color", None),
                "bookmarks": [
                    {
                        "id": rd.get("_id"),
                        "title": rd.get("title", "Untitled"),
                        "link": rd.get("link", "#"),
                        "excerpt": rd.get("excerpt", ""),
                        "domain": rd.get("domain", ""),
                        "cover": rd.get("cover", ""),
                        "tags": rd.get("tags", []),
                        "created": rd.get("created", ""),
                        "type": rd.get("type", "link"),
                        "important": rd.get("important", False),
                        "note": rd.get("note", ""),
                        "highlights": [
                            h.get("color", "yellow")
                            for h in rd.get("highlights", [])
                        ],
                    }
                    for rd in raindrops
                ],
            }
        )

    # Also fetch Unsorted (collection id -1)
    unsorted = fetch_raindrops(-1)
    if unsorted:
        grouped.append(
            {
                "id": -1,
                "title": "Unsorted",
                "count": len(unsorted),
                "color": None,
                "bookmarks": [
                    {
                        "id": rd.get("_id"),
                        "title": rd.get("title", "Untitled"),
                        "link": rd.get("link", "#"),
                        "excerpt": rd.get("excerpt", ""),
                        "domain": rd.get("domain", ""),
                        "cover": rd.get("cover", ""),
                        "tags": rd.get("tags", []),
                        "created": rd.get("created", ""),
                        "type": rd.get("type", "link"),
                        "important": rd.get("important", False),
                        "note": rd.get("note", ""),
                        "highlights": [
                            h.get("color", "yellow")
                            for h in rd.get("highlights", [])
                        ],
                    }
                    for rd in unsorted
                ],
            }
        )

    return grouped


@app.before_request
def check_auth():
    if not DASHBOARD_PASSWORD:
        return  # auth not configured — open access
    if request.endpoint in ("login", "logout", "api_status", "static"):
        return  # always allow
    if not session.get("authenticated"):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return redirect(url_for("login"))


def _is_admin():
    """Return True if the current session has admin (full-access) role."""
    # When auth is disabled everyone is implicitly admin
    if not DASHBOARD_PASSWORD:
        return True
    return session.get("role") == "admin"


def _require_admin():
    """Return a 403 JSON response if the caller is not an admin, else None."""
    if not _is_admin():
        return jsonify({"ok": False, "error": "forbidden — read-only account"}), 403
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if not DASHBOARD_PASSWORD:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        pw = request.form.get("password", "")
        if hmac.compare_digest(pw.encode(), DASHBOARD_PASSWORD.encode()):
            session.permanent = True
            session["authenticated"] = True
            session["role"] = "admin"
            logger.info("Admin login from %s", request.remote_addr)
            return redirect(url_for("index"))
        if READONLY_PASSWORD and hmac.compare_digest(pw.encode(), READONLY_PASSWORD.encode()):
            session.permanent = True
            session["authenticated"] = True
            session["role"] = "readonly"
            logger.info("Read-only login from %s", request.remote_addr)
            return redirect(url_for("index"))
        error = "Incorrect password"
        logger.warning("Failed login attempt from %s", request.remote_addr)
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    role = session.get("role", "admin")  # admin when auth is disabled
    return render_template("index.html", auth_enabled=bool(DASHBOARD_PASSWORD), role=role)


@app.route("/api/status")
def api_status():
    """Return configuration health for frontend validation."""
    data, age = _cache_get_with_age()
    return jsonify({
        "ok": True,
        "token_set": bool(RAINDROP_TOKEN),
        "redis_connected": _redis is not None,
        "redis_error": _redis_error,
        "cache_ttl": CACHE_TTL,
        "cache_age": round(age) if age is not None else None,
        "cache_populated": data is not None,
    })


@app.route("/api/bookmarks")
def api_bookmarks():
    try:
        data = fetch_all()
        logger.info("Served %d collections", len(data))
        return jsonify({"ok": True, "collections": data})
    except Exception as e:
        logger.error("api_bookmarks failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Force cache invalidation."""
    guard = _require_admin()
    if guard:
        return guard
    _cache_bust()
    try:
        data = fetch_all()
        logger.info("Cache refreshed — %d collections", len(data))
        return jsonify({"ok": True, "collections": data})
    except Exception as e:
        logger.error("api_refresh failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/add", methods=["POST"])
def api_add():
    """Create a new raindrop via the Raindrop.io API."""
    guard = _require_admin()
    if guard:
        return guard
    body = request.get_json(silent=True) or {}
    link = (body.get("link") or "").strip()
    if not link:
        return jsonify({"ok": False, "error": "link is required"}), 400
    if not link.startswith(("http://", "https://")):
        link = "https://" + link

    payload = {"link": link}
    title = (body.get("title") or "").strip()
    if title:
        payload["title"] = title
    tags = [t.strip() for t in (body.get("tags") or "").split(",") if t.strip()]
    if tags:
        payload["tags"] = tags
    collection_id = body.get("collection_id")
    if collection_id is not None:
        try:
            payload["collection"] = {"$id": int(collection_id)}
        except (ValueError, TypeError):
            pass
    if "important" in body:
        payload["important"] = bool(body["important"])
    excerpt = (body.get("excerpt") or "").strip()
    if excerpt:
        payload["excerpt"] = excerpt

    r = requests.post(
        f"{API_BASE}/raindrop",
        headers={**headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    result = r.json()
    if not result.get("result"):
        return jsonify({"ok": False, "error": result.get("errorMessage", "Unknown error")}), 400

    # Bust cache so the new bookmark appears on next load
    _cache_bust()
    return jsonify({"ok": True})


@app.route("/api/remove/<int:raindrop_id>", methods=["DELETE"])
def api_remove(raindrop_id):
    """Permanently delete a raindrop."""
    guard = _require_admin()
    if guard:
        return guard
    r = requests.delete(
        f"{API_BASE}/raindrop/{raindrop_id}",
        headers=headers(),
        timeout=15,
    )
    r.raise_for_status()
    result = r.json()
    if not result.get("result"):
        return jsonify({"ok": False, "error": result.get("errorMessage", "Unknown error")}), 400
    _cache_bust()
    return jsonify({"ok": True})


@app.route("/api/edit/<int:raindrop_id>", methods=["PUT"])
def api_edit(raindrop_id):
    """Update an existing raindrop."""
    guard = _require_admin()
    if guard:
        return guard
    body = request.get_json(silent=True) or {}
    payload = {}
    title = (body.get("title") or "").strip()
    if title:
        payload["title"] = title
    link = (body.get("link") or "").strip()
    if link:
        if not link.startswith(("http://", "https://")):
            link = "https://" + link
        payload["link"] = link
    if "tags" in body:
        payload["tags"] = [t.strip() for t in (body["tags"] or "").split(",") if t.strip()]
    if "collection_id" in body:
        cid = body["collection_id"]
        try:
            payload["collection"] = {"$id": int(cid) if cid else -1}
        except (ValueError, TypeError):
            payload["collection"] = {"$id": -1}
    if "note" in body:
        payload["note"] = body["note"]
    if "excerpt" in body:
        payload["excerpt"] = (body["excerpt"] or "").strip()
    if "important" in body:
        payload["important"] = bool(body["important"])
    if not payload:
        return jsonify({"ok": False, "error": "nothing to update"}), 400
    r = requests.put(
        f"{API_BASE}/raindrop/{raindrop_id}",
        headers={**headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    result = r.json()
    if not result.get("result"):
        return jsonify({"ok": False, "error": result.get("errorMessage", "Unknown error")}), 400
    _cache_bust()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
