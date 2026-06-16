'use strict';

const { app, BrowserWindow, ipcMain, dialog, screen } = require('electron');
const path = require('path');
const url = require('url');

// 동영상 자동재생(소리 포함) 허용 - 사이니지 특성상 사용자 제스처 없이 재생되어야 함
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

/** @type {BrowserWindow|null} */
let controlWin = null;
/** 화면(0,1,2)별 디스플레이 창 */
let displayWins = [];

const IMAGE_EXT = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'];
const VIDEO_EXT = ['mp4', 'webm', 'ogv', 'ogg', 'mov', 'm4v', 'avi', 'mkv'];

function mediaType(p) {
  const ext = path.extname(p).slice(1).toLowerCase();
  if (IMAGE_EXT.includes(ext)) return 'image';
  if (VIDEO_EXT.includes(ext)) return 'video';
  return null;
}

function createControlWindow() {
  controlWin = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 900,
    minHeight: 640,
    title: 'Daangn Signage - 제어판',
    backgroundColor: '#1c1c1e',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  controlWin.removeMenu();
  controlWin.loadFile('control.html');
  controlWin.on('closed', () => {
    controlWin = null;
    closeDisplays();
  });
}

/** 현재 연결된 모든 디스플레이 정보 */
function listDisplays() {
  const primaryId = screen.getPrimaryDisplay().id;
  return screen.getAllDisplays().map((d, i) => ({
    id: d.id,
    index: i,
    primary: d.id === primaryId,
    bounds: d.bounds,
    width: d.bounds.width,
    height: d.bounds.height,
    scaleFactor: d.scaleFactor,
    label: `모니터 ${i + 1} (${d.bounds.width}×${d.bounds.height})${d.id === primaryId ? ' · 주화면' : ''}`,
  }));
}

function findDisplay(id) {
  return screen.getAllDisplays().find((d) => d.id === id) || null;
}

function closeDisplays() {
  for (const w of displayWins) {
    if (w && !w.isDestroyed()) w.close();
  }
  displayWins = [];
}

/**
 * 미디어 항목 경로 -> 표시용 객체로 변환 (file:// URL 부여)
 */
function decorateItem(item) {
  return {
    type: item.type || mediaType(item.path) || 'image',
    name: path.basename(item.path),
    path: item.path,
    src: url.pathToFileURL(item.path).href,
    duration: item.duration, // 이미지 표시 시간(초). 없으면 display에서 기본값 사용
  };
}

/**
 * 재생 시작
 * config = {
 *   mode: 'mirror' | 'wall' | 'separate',
 *   windowed: boolean,            // 테스트용 창모드
 *   defaults: { imageDuration, fit, muted, transition },
 *   assignments: [displayId, displayId, displayId],   // 화면 0,1,2 -> 모니터
 *   screenCount: 1..3,
 *   playlist: [items],            // mirror / wall 공용
 *   playlists: [[items],[items],[items]]  // separate
 * }
 */
function startPlayback(config) {
  closeDisplays();

  const count = Math.max(1, Math.min(3, config.screenCount || 3));
  const windowed = !!config.windowed;

  for (let i = 0; i < count; i++) {
    const dispId = config.assignments && config.assignments[i];
    const disp = findDisplay(dispId) || screen.getPrimaryDisplay();
    const b = disp.bounds;

    let winOpts;
    if (windowed) {
      // 테스트(창모드): 작은 창들을 좌상단에 나란히 배치
      const w = 480, h = 270;
      winOpts = { x: 40 + i * (w + 20), y: 80, width: w, height: h, frame: true };
    } else {
      winOpts = { x: b.x, y: b.y, width: b.width, height: b.height, frame: false };
    }

    const win = new BrowserWindow({
      ...winOpts,
      title: `화면 ${i + 1}`,
      backgroundColor: '#000000',
      autoHideMenuBar: true,
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        webSecurity: false, // 로컬 파일(file://) 미디어 로드 허용
      },
    });
    win.removeMenu();
    if (!windowed) win.setFullScreen(true);

    // 화면별 재생목록 구성
    let items;
    if (config.mode === 'separate') {
      items = (config.playlists && config.playlists[i]) || [];
    } else {
      items = config.playlist || [];
    }
    const decorated = items.map(decorateItem);

    const payload = {
      screenIndex: i,
      screenCount: count,
      mode: config.mode,
      defaults: config.defaults || {},
      items: decorated,
      wall: config.mode === 'wall' ? { index: i, total: count } : null,
    };

    win.webContents.once('did-finish-load', () => {
      win.webContents.send('init', payload);
    });
    win.loadFile('display.html');

    win.on('closed', () => {
      displayWins[i] = null;
    });

    displayWins[i] = win;
  }

  return { ok: true, count };
}

function broadcastControl(msg) {
  for (const w of displayWins) {
    if (w && !w.isDestroyed()) w.webContents.send('control', msg);
  }
}

// ───────────────────────── IPC ─────────────────────────

ipcMain.handle('get-displays', () => listDisplays());

ipcMain.handle('pick-files', async () => {
  const res = await dialog.showOpenDialog(controlWin, {
    title: '사진 / 영상 추가',
    properties: ['openFile', 'multiSelections'],
    filters: [
      { name: '사진/영상', extensions: [...IMAGE_EXT, ...VIDEO_EXT] },
      { name: '사진', extensions: IMAGE_EXT },
      { name: '영상', extensions: VIDEO_EXT },
      { name: '모든 파일', extensions: ['*'] },
    ],
  });
  if (res.canceled) return [];
  return res.filePaths.map((p) => ({
    type: mediaType(p) || 'image',
    name: path.basename(p),
    path: p,
  }));
});

ipcMain.handle('start', (e, config) => startPlayback(config));

ipcMain.handle('stop', () => {
  closeDisplays();
  return { ok: true };
});

ipcMain.on('control', (e, msg) => broadcastControl(msg));

// ───────────────────────── 앱 수명주기 ─────────────────────────

app.whenReady().then(() => {
  createControlWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createControlWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
