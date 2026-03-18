# Raindrop Bookmark Dashboard

A self-hosted bookmark dashboard powered by your Raindrop.io account. Browse, search, and navigate your bookmarks from any browser — including mobile Chrome, where the Raindrop.io extension cannot be installed.

## Why this exists

The official Raindrop.io browser extension only works on desktop browsers. On **mobile Chrome** (Android) and other mobile browsers that don't support extensions, you lose quick access to your bookmarks unless you use the Raindrop mobile app.

This dashboard is a lightweight alternative to the Raindrop mobile app. Self-hosting it gives you:

- **No app install required** — works as a regular web page in any mobile or desktop browser
- **Add to home screen** — pin it as a shortcut that opens full-screen with no browser chrome (iOS Safari natively; Android Chrome via the included PWA manifest)
- **Your own server, your own data flow** — requests go from your server to Raindrop's API, not from the app to Raindrop's servers with your credentials embedded in a third-party app
- **Persistent collection selection** — remembers which collection you were browsing across sessions
- **No ads, no upsell, no account wall** — just your bookmarks
- **Customizable** — it's a single Python file and one HTML template; change anything you want

## Features

- Pulls live from the Raindrop.io API with configurable caching (default 1 hour)
- Collection hierarchy — parent/child collections displayed as an expandable tree
- Sidebar navigation on desktop; slide-in drawer on mobile
- Full-text search across titles, domains, excerpts, and tags
- Filter by tag — click any tag to show only bookmarks with that tag
- Sort per collection — cycle between Default, A→Z, Newest, and Oldest (saved across page loads)
- Add bookmarks directly from the dashboard (URL, title, collection, tags, description)
- Edit any bookmark in place — title, URL, tags, description
- Delete bookmarks with a single click — removes instantly without a page reload
- Click a bookmark's description to expand it inline
- Manual refresh button to bust the cache on demand
- Remembers last selected collection and per-collection sort order across page loads
- Keyboard shortcut: `/` to focus search
- Responsive layout — single-column cards on mobile, multi-column grid on desktop

## Setup

### 1. Get a Raindrop API token
1. Go to https://app.raindrop.io/settings/integrations
2. Click **Create new app**
3. Copy the **Test token**

### 2. Configure
```bash
cp .env.example .env
# Edit .env and paste your token
```

### 3. Deploy
```bash
docker compose up -d
```

Open `http://your-server:8080` in any browser.

To use it like a full-screen native app on mobile:

- **iOS (Safari)**: tap the Share icon → **Add to Home Screen**
- **Android (Chrome)**: tap the three-dot menu → **Add to Home Screen** (or Chrome may show an install prompt automatically)

Once added, the icon opens the dashboard full-screen with no browser address bar.

## Environment Variables
| Variable | Default | Description |
|---|---|---|
| `RAINDROP_TOKEN` | *(required)* | Raindrop.io API test token |
| `CACHE_TTL` | `3600` | Seconds to cache bookmarks before re-fetching (1 hour) |
| `PORT` | `8080` | Port the server listens on |
| `DASHBOARD_PASSWORD` | *(unset — auth disabled)* | Password to protect the dashboard. Leave unset to disable auth entirely |
| `READONLY_PASSWORD` | *(unset)* | Optional second password granting read-only access (browse/filter only — no add/edit/delete) |
| `SECRET_KEY` | *(no default — required when auth is enabled)* | Signs session cookies. Required when using `DASHBOARD_PASSWORD` — without it every container restart logs everyone out |

### Authentication

Authentication is **optional but recommended** if the dashboard is accessible outside your private home network. Without it, anyone who can reach the URL can view and modify your bookmarks.

Leave `DASHBOARD_PASSWORD` unset to disable auth entirely — no login page, no cookies.

**Session behaviour:** once you log in, the session cookie is permanent with no expiry. You will not be prompted again on that device/browser, even after closing and reopening the browser.

**To enable:**

1. Generate a secret key — you must do this yourself, it is not auto-generated:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Add the variables to your `.env`:
   ```
   DASHBOARD_PASSWORD=your_admin_password
   SECRET_KEY=<output from step 1>

   # Optional: second password for read-only access
   # READONLY_PASSWORD=your_readonly_password
   ```
3. Rebuild and restart:
   ```bash
   docker compose up -d --build
   ```

Users who log in with `READONLY_PASSWORD` can browse, search, and filter bookmarks but will not see the Add button and cannot edit or delete anything. Users who log in with `DASHBOARD_PASSWORD` have full access.

**To log out:** click the **Log out** link at the bottom of the sidebar, or navigate to `/logout` directly.

> **Warning:** if `SECRET_KEY` is not set, the app falls back to a randomly generated key on each startup. This means every container restart will invalidate all active sessions and log everyone out. Always set a stable `SECRET_KEY` when using authentication.

## HTTPS

The dashboard works fine over plain HTTP on a local network, but if you expose it to the internet (or want "Add to Home Screen" to behave like a proper PWA on some Android devices) you'll want HTTPS in front of it.

### Option A — Cloudflare Tunnel (easiest, no open ports)

1. Install `cloudflared` on the host machine ([docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/)).
2. Authenticate and create a tunnel:
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create raindrop-dash
   ```
3. Add a public hostname that points to `http://localhost:8080`.
4. Run the tunnel (or add it as a system service). Cloudflare terminates TLS — your container stays on HTTP internally.

### Option B — Caddy reverse proxy (automatic Let's Encrypt)

Add a `caddy` service to `docker-compose.yml`:

```yaml
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
    depends_on:
      - raindrop-dash

volumes:
  caddy_data:
```

Create a `Caddyfile` next to `docker-compose.yml`:

```
bookmarks.example.com {
    reverse_proxy raindrop-dash:8080
}
```

Caddy fetches and auto-renews a Let's Encrypt certificate. Make sure port 80 and 443 are reachable from the internet (DNS A record pointing to your server).

### Option C — nginx + Certbot

If you already run nginx, add a server block that proxies to port 8080 and run Certbot to obtain a certificate. Standard reverse-proxy setup — see the [Certbot docs](https://certbot.eff.org/) for your OS.

### Option D — Tailscale / VPN only

If you only need to reach the dashboard from your own devices, put the host in a [Tailscale](https://tailscale.com/) network and enable HTTPS via `tailscale cert`. No open firewall ports required.

---

## Optional: Chrome New Tab Extension

On desktop Chrome, you can make every new tab open your Raindrop dashboard (or Raindrop.io directly) using a tiny unpacked extension that requires no permissions and no Developer account.

See [optional-chrome-extension/README.md](optional-chrome-extension/README.md) for setup instructions.
