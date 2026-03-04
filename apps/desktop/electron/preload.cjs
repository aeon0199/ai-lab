const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("aiLabDesktop", {
  startStack: () => ipcRenderer.invoke("stack:start"),
  stopStack: () => ipcRenderer.invoke("stack:stop"),
  stackStatus: () => ipcRenderer.invoke("stack:status"),
});
