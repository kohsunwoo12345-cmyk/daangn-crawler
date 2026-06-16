'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  // 제어판용
  getDisplays: () => ipcRenderer.invoke('get-displays'),
  pickFiles: () => ipcRenderer.invoke('pick-files'),
  start: (config) => ipcRenderer.invoke('start', config),
  stop: () => ipcRenderer.invoke('stop'),
  sendControl: (msg) => ipcRenderer.send('control', msg),

  // 디스플레이 창용
  onInit: (cb) => ipcRenderer.on('init', (_e, data) => cb(data)),
  onControl: (cb) => ipcRenderer.on('control', (_e, data) => cb(data)),
});
