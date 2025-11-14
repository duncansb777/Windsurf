const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const fs = require('fs');

function resolveAppHtml() {
  // In production, the HTML is copied to resources/app/ by electron-builder (extraFiles)
  const resPath = process.resourcesPath || '';
  const candidates = [
    path.join(resPath, 'app', 'agentic-control-demo.html'),
    path.join(resPath, 'agentic-control-demo.html')
  ];
  // In dev, load from the project root ../agentic-control-demo.html
  const devPath = path.resolve(__dirname, '..', 'agentic-control-demo.html');
  for (const p of candidates) {
    if (fs.existsSync(p)) return { path: p, source: 'prod' };
  }
  return { path: devPath, source: 'dev' };
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true
    }
  });

  const target = resolveAppHtml();
  const loadFallback = (reason) => {
    const msg = `Failed to load app UI (${reason}).\nTried: ${target.path}`;
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>App Load Error</title></head>
      <body style="font-family: -apple-system, system-ui, sans-serif; padding: 24px;">
      <h2>Agentic Control Console</h2>
      <div style="padding:12px; border:1px solid #ddd; border-radius:8px; background:#fff;">
        <p><strong>Could not find or load the demo HTML.</strong></p>
        <p>Path tried: <code>${target.path}</code></p>
        <p>If this is a packaged build, ensure the file is bundled under <code>Contents/Resources/app/agentic-control-demo.html</code>.<br/>
        In development, ensure <code>agentic-control-demo.html</code> exists one directory above <code>desktop-console</code>.</p>
      </div>
      </body></html>`;
    win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html));
    win.webContents.openDevTools({ mode: 'detach' });
  };

  if (!fs.existsSync(target.path)) {
    loadFallback('missing file');
  } else {
    win.loadFile(target.path).catch(err => {
      loadFallback(err && err.message ? err.message : 'unknown error');
    });
  }

  // Open external links in the default browser
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  // If navigation fails later (e.g., file permissions), show fallback
  win.webContents.on('did-fail-load', (_e, code, desc) => {
    const reason = `${code} ${desc}`;
    const targetInfo = resolveAppHtml();
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>App Load Error</title></head>
      <body style="font-family: -apple-system, system-ui, sans-serif; padding: 24px;">
      <h2>Agentic Control Console</h2>
      <div style="padding:12px; border:1px solid #ddd; border-radius:8px; background:#fff;">
        <p><strong>Failed to load UI:</strong> ${reason}</p>
        <p>Tried: <code>${targetInfo.path}</code></p>
      </div>
      </body></html>`;
    win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html));
    win.webContents.openDevTools({ mode: 'detach' });
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
