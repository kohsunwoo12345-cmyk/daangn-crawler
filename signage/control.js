'use strict';

// 제어판 로직: 재생목록 구성 + 모드/모니터 설정 + 재생 제어

const state = {
  mode: 'mirror',          // mirror | wall | separate
  screenCount: 3,
  displays: [],
  assignments: [null, null, null],
  lists: [[], [], []],     // 화면별 재생목록 (mirror/wall 은 lists[0] 공용 사용)
  playing: false,
};

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

// ───────── 토스트 ─────────
let toastT = null;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastT);
  toastT = setTimeout(() => t.classList.remove('show'), 2400);
}

// ───────── 모니터 감지 ─────────
async function loadDisplays() {
  state.displays = await window.api.getDisplays();
  // 기본 배정: 화면1->모니터1, 2->2, 3->3 (없으면 마지막 것)
  for (let i = 0; i < 3; i++) {
    const d = state.displays[i] || state.displays[state.displays.length - 1];
    state.assignments[i] = d ? d.id : null;
  }
  renderAssigns();
}

function renderAssigns() {
  const wrap = $('#assigns');
  wrap.innerHTML = '';
  for (let i = 0; i < state.screenCount; i++) {
    const row = document.createElement('div');
    row.className = 'assign-row';
    const opts = state.displays
      .map((d) => `<option value="${d.id}" ${state.assignments[i] === d.id ? 'selected' : ''}>${d.label}</option>`)
      .join('');
    row.innerHTML = `<span class="n">화면 ${i + 1}</span>
      <select data-screen="${i}">${opts || '<option>모니터 없음</option>'}</select>`;
    wrap.appendChild(row);
  }
  wrap.querySelectorAll('select').forEach((sel) => {
    sel.addEventListener('change', (e) => {
      state.assignments[+e.target.dataset.screen] = Number(e.target.value);
    });
  });
  if (state.displays.length < state.screenCount) {
    const warn = document.createElement('div');
    warn.style.cssText = 'font-size:11px;color:#e6a23a;margin-top:4px';
    warn.textContent = `⚠ 현재 ${state.displays.length}개 모니터만 감지됨. 테스트(창모드)로 미리볼 수 있어요.`;
    wrap.appendChild(warn);
  }
}

// ───────── 모드 ─────────
function setMode(mode) {
  state.mode = mode;
  $$('#modes .mode').forEach((m) => m.classList.toggle('active', m.dataset.mode === mode));
  renderLists();
}

// ───────── 재생목록 렌더 ─────────
function fileIcon(it) {
  return it.type === 'video' ? '🎬' : '🖼️';
}

function renderItem(it, listIdx, itemIdx) {
  const el = document.createElement('div');
  el.className = 'item';
  const durBlock = it.type === 'image'
    ? `<span class="dur">⏱ <input type="number" min="1" max="600" value="${it.duration || ''}" placeholder="기본" data-list="${listIdx}" data-idx="${itemIdx}" class="dur-in" />초</span>`
    : `<span class="dur">🎬 영상 전체 재생</span>`;
  el.innerHTML = `
    <div class="thumb">${it.type === 'image' ? `<img src="file://${encodeURI(it.path)}" style="width:100%;height:100%;object-fit:cover;border-radius:6px" onerror="this.replaceWith(document.createTextNode('🖼️'))"/>` : '🎬'}</div>
    <div class="meta">
      <div class="nm" title="${it.path}">${it.name}</div>
      <div class="sub">${fileIcon(it)} ${it.type === 'video' ? '영상' : '사진'} · ${durBlock}</div>
    </div>
    <div class="ops">
      <button data-op="up" title="위로">▲</button>
      <button data-op="down" title="아래로">▼</button>
      <button data-op="del" title="삭제">✕</button>
    </div>`;
  el.querySelector('[data-op=up]').onclick = () => moveItem(listIdx, itemIdx, -1);
  el.querySelector('[data-op=down]').onclick = () => moveItem(listIdx, itemIdx, 1);
  el.querySelector('[data-op=del]').onclick = () => { state.lists[listIdx].splice(itemIdx, 1); renderLists(); };
  const durIn = el.querySelector('.dur-in');
  if (durIn) durIn.onchange = (e) => {
    const v = parseInt(e.target.value, 10);
    state.lists[listIdx][itemIdx].duration = v > 0 ? v : undefined;
  };
  return el;
}

function renderOneList(listIdx, title) {
  const list = document.createElement('div');
  list.className = 'list';
  const items = state.lists[listIdx];
  list.innerHTML = `<div class="list-h"><span class="ttl">${title}</span>
    <span class="cnt">${items.length}개</span>
    <button class="add-s" data-target="${listIdx}">＋ 추가</button></div>`;
  const box = document.createElement('div');
  box.className = 'items';
  if (!items.length) {
    box.innerHTML = `<div class="empty">아직 비어있어요.<br/>＋ 버튼으로 사진·영상을 추가하세요.</div>`;
  } else {
    items.forEach((it, i) => box.appendChild(renderItem(it, listIdx, i)));
  }
  list.appendChild(box);
  list.querySelector('.add-s').onclick = () => addFiles(listIdx);
  return list;
}

function renderLists() {
  const wrap = $('#lists');
  wrap.innerHTML = '';
  // 각각 모드는 컬럼별 추가 버튼을 사용하므로 상단 버튼 숨김
  $('#addBtn').style.display = state.mode === 'separate' ? 'none' : 'block';
  if (state.mode === 'separate') {
    wrap.className = 'lists cols-3';
    $('#listTitle').textContent = '화면별 재생목록 (각각)';
    for (let i = 0; i < state.screenCount; i++) {
      wrap.appendChild(renderOneList(i, `화면 ${i + 1}`));
    }
  } else {
    wrap.className = 'lists cols-1';
    $('#listTitle').textContent = state.mode === 'wall' ? '재생목록 (3화면에 걸쳐 표시)' : '재생목록 (3화면 동시)';
    wrap.appendChild(renderOneList(0, '공용 재생목록'));
  }
}

function moveItem(listIdx, i, dir) {
  const arr = state.lists[listIdx];
  const j = i + dir;
  if (j < 0 || j >= arr.length) return;
  [arr[i], arr[j]] = [arr[j], arr[i]];
  renderLists();
}

async function addFiles(targetList) {
  const files = await window.api.pickFiles();
  if (!files.length) return;
  state.lists[targetList].push(...files);
  renderLists();
  toast(`${files.length}개 추가됨`);
}

// ───────── 재생 ─────────
function buildConfig() {
  const defaults = {
    imageDuration: parseInt($('#imgDur').value, 10) || 8,
    fit: $('#fit').value,
    muted: $('#muted').checked,
    transition: 'fade',
  };
  const cfg = {
    mode: state.mode,
    windowed: $('#windowed').checked,
    screenCount: state.screenCount,
    assignments: state.assignments.slice(0, state.screenCount),
    defaults,
  };
  if (state.mode === 'separate') {
    cfg.playlists = state.lists.slice(0, state.screenCount);
  } else {
    cfg.playlist = state.lists[0];
  }
  return cfg;
}

async function start() {
  const cfg = buildConfig();
  const hasMedia = state.mode === 'separate'
    ? cfg.playlists.some((l) => l.length)
    : cfg.playlist.length;
  if (!hasMedia) { toast('재생할 사진·영상을 먼저 추가하세요'); return; }

  await window.api.start(cfg);
  state.playing = true;
  $('#status').textContent = '재생 중';
  $('#status').className = 'status on';
  $('#startBtn').disabled = true;
  $('#stopBtn').disabled = false;
  toast(cfg.windowed ? '창모드로 미리보기 시작' : '재생 시작');
}

async function stop() {
  await window.api.stop();
  state.playing = false;
  $('#status').textContent = '정지됨';
  $('#status').className = 'status off';
  $('#startBtn').disabled = false;
  $('#stopBtn').disabled = true;
}

// ───────── 이벤트 바인딩 ─────────
$$('#modes .mode').forEach((m) => m.addEventListener('click', () => setMode(m.dataset.mode)));

$('#screenCount').addEventListener('change', (e) => {
  state.screenCount = parseInt(e.target.value, 10);
  renderAssigns();
  renderLists();
});

$('#refreshDisp').addEventListener('click', async () => { await loadDisplays(); toast('모니터 다시 감지함'); });
$('#addBtn').addEventListener('click', () => addFiles(state.mode === 'separate' ? 0 : 0));
$('#startBtn').addEventListener('click', start);
$('#stopBtn').addEventListener('click', stop);

$$('.playctl .minibtn').forEach((b) => b.addEventListener('click', () => {
  if (!state.playing) { toast('먼저 재생을 시작하세요'); return; }
  window.api.sendControl({ action: b.dataset.act });
}));

// ───────── 초기화 ─────────
(async function init() {
  await loadDisplays();
  setMode('mirror');
  renderLists();
})();
