# Agentic Control Console — Desktop App

A minimal Electron wrapper to run the demo console as a desktop application on macOS, Windows, and Linux.

## Prerequisites
- Node.js 18+ and npm
- Internet access for first-time dependency install

## Project layout
- Loads `../agentic-control-demo.html` in development.
- During packaging, the HTML is copied into the app bundle automatically.

## Setup
```bash
# From this folder
npm install
```

## Run (development)
```bash
npm start
```
This opens a desktop window running the console. External links open in your default browser.

## Build installers
Uses electron-builder to create platform-specific bundles.

```bash
# Build for your current platform
npm run dist

# Or create unpacked directories (no installer)
npm run package
```

- macOS: `.dmg` / `.pkg` or `.app` depending on host and signing
- Windows: `.exe` (NSIS)
- Linux: `.AppImage`

Artifacts appear in `dist/`.

## Configuration
- Update execution base URLs inside `agentic-control-demo.html` (AGENTS_EXEC) if your services are not on localhost.
- To change window size, edit `desktop-console/main.js`.

## Troubleshooting
- If the app window is blank in dev, ensure `agentic-control-demo.html` exists one directory above this folder.
- If packaging misses the HTML, confirm `build.extraFiles` in `package.json` includes `agentic-control-demo.html`.

## Alternative: wrap quickly with Nativefier
If you prefer a quick wrapper without a repo:
```bash
npm install -g nativefier
nativefier --name "Agentic Control Console" file://$PWD/../agentic-control-demo.html
```
This creates a runnable desktop app with sensible defaults.
