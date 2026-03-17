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

## Optional: Chrome New Tab Extension

On desktop Chrome, you can make every new tab open your Raindrop dashboard (or Raindrop.io directly) using a tiny unpacked extension that requires no permissions and no Developer account.

See [optional-chrome-extension/README.md](optional-chrome-extension/README.md) for setup instructions.
