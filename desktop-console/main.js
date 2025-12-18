const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

// Simple process handle for the internal backend (Ownership Trigger + MCP shims)
let backendProc = null;

function startBackend() {
  if (backendProc) return; // already running

  // Resolve project root from the desktop-console folder
  const projectRoot = path.resolve(__dirname, '..');

  // Prefer the repo-local virtualenv Python if present, so uvicorn and
  // dependencies are loaded from the same environment the app uses.
  const venvDir = path.join(projectRoot, '.venv');
  const venvPython = process.platform === 'win32'
    ? path.join(venvDir, 'Scripts', 'python.exe')
    : path.join(venvDir, 'bin', 'python');

  const pythonCmd = fs.existsSync(venvPython)
    ? venvPython
    : (process.env.HEALTH_PYTHON || 'python3');
  const args = [
    '-m',
    'uvicorn',
    'services.ownership_trigger.app.main:app',
    '--port',
    process.env.HEALTH_BACKEND_PORT || '8002',
  ];

  backendProc = spawn(pythonCmd, args, {
    cwd: projectRoot,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      // Ensure CSV-based CoO demo data is available to the mock MCP if overridden.
      // Default path is already wired in the Python code; this lets advanced users override it.
      COO_DATA_DIR: process.env.COO_DATA_DIR || process.env.HEALTH_COO_DATA_DIR || '',
    },
  });

  backendProc.on('exit', (code, signal) => {
    backendProc = null;
    // In dev we may want to see failures in the console; avoid UI popups here.
    console.log('[backend] exited', { code, signal });
  });

  backendProc.stdout.on('data', (data) => {
    console.log('[backend]', data.toString().trim());
  });

  backendProc.stderr.on('data', (data) => {
    console.error('[backend:err]', data.toString().trim());
  });
}

function stopBackend() {
  if (!backendProc) return;
  try {
    backendProc.kill();
  } catch (e) {
    // ignore
  }
  backendProc = null;
}

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

  // If the TOP-LEVEL navigation fails (e.g., file permissions), show fallback.
  // Ignore failures from subframes/iframes such as external map embeds.
  win.webContents.on('did-fail-load', (_e, code, desc, _url, isMainFrame) => {
    if (isMainFrame === false) return;
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
  // Start internal backend so the HTML UI can call HEALTH_API/CoO endpoints
  startBackend();

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  // Ensure the internal backend is stopped when the app exits
  stopBackend();
});
