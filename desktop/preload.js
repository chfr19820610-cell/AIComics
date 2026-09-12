/**
 * AIComics Desktop — preload script.
 * Exposes a safe API to the renderer process.
 */
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("aicomic", {
  version: "4.0.0",
  platform: process.platform,
  isDesktop: true,
});
