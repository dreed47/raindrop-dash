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
- Add new bookmarks directly from the dashboard (URL, title, collection, tags)
- Delete bookmarks with a single click — removes instantly without a page reload
- Manual refresh button to bust the cache on demand
- Remembers last selected collection across page loads
- Keyboard shortcut: `/` to focus search
- Responsive layout — single-column cards on mobile, grid on desktop

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
| `DASHBOARD_PASSWORD` | *(unset)* | Password to protect the dashboard. Leave unset to disable auth |
| `SECRET_KEY` | *(auto-generated)* | Signs session cookies. **Must be set** if using `DASHBOARD_PASSWORD`, otherwise sessions break on restart |

### Authentication

If `DASHBOARD_PASSWORD` is set, the dashboard shows a login page before granting access. Authentication is entirely optional — leave `DASHBOARD_PASSWORD` unset and the dashboard is open to anyone who can reach it (fine for a private home network; not recommended if exposed to the internet).

**Session behaviour:** once you log in, the session cookie is permanent with no expiry. You will not be prompted again on that device/browser, even after closing and reopening the browser.

**To enable:**

1. Generate a secret key:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Add both variables to your `.env`:
   ```
   DASHBOARD_PASSWORD=your_chosen_password
   SECRET_KEY=<output from step 1>
   ```
3. Rebuild and restart:
   ```bash
   docker compose up -d --build
   ```

**To log out:** click the **Log out** link at the bottom of the sidebar, or navigate to `/logout` directly.

> **Note:** `SECRET_KEY` must be a stable value. If it is not set, a random key is generated on each container start, which invalidates all active sessions every time the container restarts.

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
