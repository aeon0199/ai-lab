const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("node:path");
const { spawn } = require("node:child_process");

const isDev = !app.isPackaged;
const repoRoot = path.resolve(__dirname, "../../..");
const composeFile = path.join(repoRoot, "infra/docker/docker-compose.yml");
const composeCommand = process.env.DOCKER_COMPOSE_CMD || "docker";
const composePrefix = composeCommand === "docker" ? ["compose"] : [];

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 980,
    minWidth: 1100,
    minHeight: 760,
    backgroundColor: "#0c1417",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  if (isDev) {
    mainWindow.loadURL("http://127.0.0.1:5173");
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

function runCompose(args) {
  return new Promise((resolve, reject) => {
    const cmd = spawn(composeCommand, [...composePrefix, "-f", composeFile, ...args], {
      cwd: repoRoot,
      shell: false,
    });

    let stdout = "";
    let stderr = "";

    cmd.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    cmd.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    cmd.on("close", (code) => {
      if (code === 0) {
        resolve({ ok: true, stdout, stderr });
      } else {
        reject(new Error(stderr || stdout || `docker compose exited ${code}`));
      }
    });
  });
}

ipcMain.handle("stack:start", async () => {
  return runCompose(["up", "-d", "--build"]);
});

ipcMain.handle("stack:stop", async () => {
  return runCompose(["down"]);
});

ipcMain.handle("stack:status", async () => {
  return runCompose(["ps"]);
});

app.whenReady().then(createWindow);
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
