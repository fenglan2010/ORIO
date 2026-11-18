const { app, BrowserWindow, shell } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");

const API_PORT = process.env.OIRO_API_PORT || "8765";
let apiProcess = null;

function userDataRoot() {
  return path.join(app.getPath("userData"), "oiro");
}

function ensureBackendEnv() {
  const dataDir = path.join(userDataRoot(), "data");
  fs.mkdirSync(dataDir, { recursive: true });
  process.env.OIRO_DATA_DIR = dataDir;
  process.env.OIRO_DISTRIBUTION = process.env.OIRO_DISTRIBUTION || "packaged";
  process.env.DATABASE_URL = `sqlite:///${path.join(dataDir, "oiro.db")}`;
  const renderer = path.join(__dirname, "renderer");
  if (fs.existsSync(renderer)) {
    process.env.OIRO_STATIC_ROOT = renderer;
  }
}

function backendCmd() {
  const root = path.resolve(__dirname, "..");
  const venvPython =
    process.platform === "win32"
      ? path.join(root, ".venv", "Scripts", "python.exe")
      : path.join(root, ".venv", "bin", "python");
  const python = fs.existsSync(venvPython) ? venvPython : "python3";
  return {
    cmd: python,
    args: [
      "-m",
      "uvicorn",
      "app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      API_PORT,
    ],
    cwd: path.join(root, "backend"),
  };
}

function startBackend() {
  const spec = backendCmd();
  apiProcess = spawn(spec.cmd, spec.args, {
    cwd: spec.cwd,
    env: { ...process.env },
    stdio: "inherit",
  });
  apiProcess.on("exit", (code) => {
    console.log(`OIRO API exited with code ${code}`);
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
    },
  });
  const devUrl = process.env.OIRO_DEV_URL;
  if (devUrl) {
    win.loadURL(devUrl);
  } else {
    win.loadURL(`http://127.0.0.1:${API_PORT}/`);
  }
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

app.whenReady().then(() => {
  ensureBackendEnv();
  startBackend();
  createWindow();
});

app.on("window-all-closed", () => {
  if (apiProcess) apiProcess.kill();
  if (process.platform !== "darwin") app.quit();
});