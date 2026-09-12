/**
 * AIComics Desktop — Electron main process.
 *
 * Wraps the AIComics web UI in a desktop window.
 * The app backend (FastAPI) runs as a child process;
 * the renderer loads http://localhost:8000.
 */

const { app, BrowserWindow, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

let mainWindow = null;
let backendProcess = null;

function startBackend() {
  const pythonPath = process.env.AICOMIC_PYTHON || "python";
  const projectRoot = path.resolve(__dirname, "..");
  backendProcess = spawn(pythonPath, ["-m", "aicomic", "serve", "--port", "8000"], {
    cwd: projectRoot,
    stdio: ["ignore", "pipe", "pipe"],
  });
  backendProcess.stdout.on("data", (data) => {
    console.log(`[backend] ${data}`);
  });
  backendProcess.stderr.on("data", (data) => {
    console.error(`[backend] ${data}`);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: "AIComics",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  // Load the AIComics web UI
  const url = process.env.AICOMIC_URL || "http://localhost:8000";
  mainWindow.loadURL(url);

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://localhost") || url.startsWith("file://")) {
      return { action: "allow" };
    }
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  startBackend();
  // Wait a moment for backend to start
  setTimeout(createWindow, 2000);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});
