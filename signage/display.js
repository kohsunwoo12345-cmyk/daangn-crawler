'use strict';

// 디스플레이(화면) 창의 재생 엔진.
// 제어판 -> main(IPC) -> 이 창 으로 전달된 재생목록을 무한 반복 재생한다.

const stage = document.getElementById('stage');
const idle = document.getElementById('idle');
const badge = document.getElementById('badge');

let state = {
  items: [],
  mode: 'mirror',
  defaults: { imageDuration: 8, fit: 'contain', muted: true, transition: 'fade' },
  wall: null,
  screenIndex: 0,
  screenCount: 3,
};

let idx = 0;
let timer = null;
let layers = []; // 두 개의 .layer
let activeLayer = 0;
let paused = false;

function clearTimer() {
  if (timer) { clearTimeout(timer); timer = null; }
}

function makeLayers() {
  stage.innerHTML = '';
  layers = [];
  for (let i = 0; i < 2; i++) {
    const el = document.createElement('div');
    el.className = 'layer';
    stage.appendChild(el);
    layers.push(el);
  }
  activeLayer = 0;
}

function fitClass() {
  const f = state.defaults.fit || 'contain';
  if (state.wall) return 'wall';
  return 'fit-' + f;
}

// 비디오월: 콘텐츠를 N개 화면에 걸쳐 보이도록 변형
function applyWall(mediaEl) {
  if (!state.wall) return;
  const { index, total } = state.wall;
  // 전체 콘텐츠가 (총 화면 너비)를 차지하도록 확대 후, 자기 구간만큼 이동
  mediaEl.style.width = total * 100 + 'vw';
  mediaEl.style.height = '100vh';
  mediaEl.style.objectFit = 'cover';
  mediaEl.style.transform = `translateX(${-index * 100}vw)`;
  // 레이어가 콘텐츠를 가운데 정렬하므로, 좌측 기준으로 재배치
  mediaEl.parentElement.style.justifyContent = 'flex-start';
  mediaEl.style.flex = '0 0 auto';
}

function showBadge(text) {
  badge.textContent = text;
  badge.classList.add('show');
  setTimeout(() => badge.classList.remove('show'), 2200);
}

function buildMedia(item) {
  let el;
  if (item.type === 'video') {
    el = document.createElement('video');
    el.src = item.src;
    el.muted = !!state.defaults.muted;
    el.autoplay = true;
    el.playsInline = true;
    el.loop = false;
  } else {
    el = document.createElement('img');
    el.src = item.src;
  }
  return el;
}

function playIndex(i) {
  if (!state.items.length) { showIdle(true); return; }
  showIdle(false);
  clearTimer();

  idx = ((i % state.items.length) + state.items.length) % state.items.length;
  const item = state.items[idx];

  const incoming = layers[1 - activeLayer];
  const outgoing = layers[activeLayer];
  incoming.className = 'layer ' + fitClass();
  incoming.innerHTML = '';

  const media = buildMedia(item);
  incoming.appendChild(media);
  applyWall(media);

  const advance = () => { if (!paused) next(); };

  if (item.type === 'video') {
    media.addEventListener('ended', advance, { once: true });
    media.addEventListener('error', () => {
      console.warn('영상 재생 실패:', item.path);
      timer = setTimeout(advance, 1500);
    }, { once: true });
    // 혹시 ended 이벤트가 안 올 경우 대비(스트림 길이 + 여유)
    media.play().catch(() => {});
  } else {
    const dur = (item.duration || state.defaults.imageDuration || 8) * 1000;
    media.addEventListener('error', () => {
      console.warn('이미지 로드 실패:', item.path);
      timer = setTimeout(advance, 1500);
    }, { once: true });
    timer = setTimeout(advance, dur);
  }

  // 크로스페이드
  requestAnimationFrame(() => {
    incoming.classList.add('show');
    outgoing.classList.remove('show');
  });
  // 이전 레이어 정리
  setTimeout(() => {
    if (layers[activeLayer] === outgoing) {
      // 이미 다음으로 넘어갔다면 건드리지 않음
    }
  }, 700);

  activeLayer = 1 - activeLayer;
}

function next() { playIndex(idx + 1); }
function prev() { playIndex(idx - 1); }

function showIdle(on) {
  idle.classList.toggle('hide', !on);
}

function restart(newState) {
  Object.assign(state, newState);
  paused = false;
  idx = 0;
  makeLayers();
  if (state.items.length) {
    showBadge(modeLabel());
    playIndex(0);
  } else {
    showIdle(true);
  }
}

function modeLabel() {
  const m = { mirror: '미러링', wall: '비디오월', separate: '각각' }[state.mode] || state.mode;
  return `화면 ${state.screenIndex + 1} · ${m}`;
}

// ───────── IPC ─────────
window.api.onInit((data) => restart(data));

window.api.onControl((msg) => {
  switch (msg.action) {
    case 'pause': paused = true; {
      const v = stage.querySelector('video'); if (v) v.pause();
      clearTimer();
    } break;
    case 'resume': paused = false; {
      const v = stage.querySelector('video');
      if (v) { v.play().catch(() => {}); }
      else next();
    } break;
    case 'next': next(); break;
    case 'prev': prev(); break;
    case 'mute': {
      const v = stage.querySelector('video'); if (v) v.muted = true;
      state.defaults.muted = true;
    } break;
    case 'unmute': {
      const v = stage.querySelector('video'); if (v) v.muted = false;
      state.defaults.muted = false;
    } break;
  }
});

// 미디어가 없을 때 클릭으로 음소거 해제 등(테스트 편의)
document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight') next();
  if (e.key === 'ArrowLeft') prev();
  if (e.key === 'Escape') window.close();
});
