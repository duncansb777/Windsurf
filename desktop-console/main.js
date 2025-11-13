const { app, BrowserWindow, shell } = require('electron');
const path = require('path');

function resolveAppHtml() {
  // In production, the HTML is copied to resources/app/ by electron-builder (extraFiles)
  const prodPath = path.join(process.resourcesPath || '', 'app', 'agentic-control-demo.html');
  // In dev, load from the project root ../agentic-control-demo.html
  const devPath = path.resolve(__dirname, '..', 'agentic-control-demo.html');
  return require('fs').existsSync(prodPath) ? prodPath : devPath;
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

  win.loadFile(resolveAppHtml());

  // Open external links in the default browser
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
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
