# Optional Chrome Extension — Raindrop.io New Tab

Chrome does not provide a setting to change the new tab page to an arbitrary URL. This tiny unpacked extension works around that by overriding the new tab page with a local HTML file that immediately redirects to Raindrop.io.

## How it works

`manifest.json` uses the `chrome_url_overrides.newtab` key to replace Chrome's built-in new tab page with `index.html`. That page contains a single `<meta http-equiv="refresh">` tag that redirects instantly to your Raindrop.io collection URL. No JavaScript, no background scripts, no permissions required.

## Setup

### 1. Copy the folder to a permanent location

Chrome loads the extension directly from disk — if the folder is moved or deleted, the extension will break. Copy this folder somewhere it won't be accidentally moved, for example:

- `~/extensions/raindrop-new-tab/`
- `C:\Users\you\extensions\raindrop-new-tab\`

Keep it there permanently.

### 2. Edit the redirect URL

Open `index.html` and change the URL to the Raindrop page you want to land on when opening a new tab:

```html
<meta http-equiv="refresh" content="0;url=https://app.raindrop.io/my/YOUR_COLLECTION_ID" />
```

Replace `YOUR_COLLECTION_ID` with the numeric ID from your Raindrop URL, or use `https://app.raindrop.io` to open the default view. You can also point this at your self-hosted raindrop-dash instance (e.g. `http://your-server:8080`).

### 3. Load the extension into Chrome

1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select this `optional-chrome-extension` folder
5. The extension will appear in the list — no restart needed

### 4. Verify

Open a new tab. Chrome will briefly show a blank page then redirect to your chosen URL.

## Notes

- The extension only needs to be loaded once. It persists across Chrome restarts as long as Developer mode remains enabled.
- If Chrome shows a warning about developer-mode extensions on startup, click **Keep** to dismiss it. This is normal for any unpacked extension.
- To stop the redirect, go to `chrome://extensions` and disable or remove the extension.
- This extension requests **no permissions** and makes **no network requests** — it is purely a local HTML redirect.
