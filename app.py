import os
import time
import requests
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

RAINDROP_TOKEN = os.environ.get("RAINDROP_TOKEN", "")
CACHE_TTL = int(os.environ.get("CACHE_TTL", 3600))  # seconds, default 1 hour
API_BASE = "https://api.raindrop.io/rest/v1"

_cache = {"data": None, "ts": 0}


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
    """Fetch everything, grouped by collection. Uses simple in-memory cache."""
    now = time.time()
    if _cache["data"] and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

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

    # Also fetch Unsorted (collection id 0)
    unsorted = fetch_raindrops(0)
    if unsorted:
        grouped.append(
            {
                "id": 0,
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

    _cache["data"] = grouped
    _cache["ts"] = now
    return grouped


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/bookmarks")
def api_bookmarks():
    try:
        data = fetch_all()
        return jsonify({"ok": True, "collections": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Force cache invalidation."""
    _cache["data"] = None
    _cache["ts"] = 0
    try:
        data = fetch_all()
        return jsonify({"ok": True, "collections": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/add", methods=["POST"])
def api_add():
    """Create a new raindrop via the Raindrop.io API."""
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
    _cache["data"] = None
    _cache["ts"] = 0
    return jsonify({"ok": True})


@app.route("/api/remove/<int:raindrop_id>", methods=["DELETE"])
def api_remove(raindrop_id):
    """Permanently delete a raindrop."""
    r = requests.delete(
        f"{API_BASE}/raindrop/{raindrop_id}",
        headers=headers(),
        timeout=15,
    )
    r.raise_for_status()
    result = r.json()
    if not result.get("result"):
        return jsonify({"ok": False, "error": result.get("errorMessage", "Unknown error")}), 400
    _cache["data"] = None
    _cache["ts"] = 0
    return jsonify({"ok": True})


@app.route("/api/edit/<int:raindrop_id>", methods=["PUT"])
def api_edit(raindrop_id):
    """Update an existing raindrop."""
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
    _cache["data"] = None
    _cache["ts"] = 0
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
