import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { LAMPS, LETTER, PLACES, RESIDENTIAL, SHOPS, TOWERS, planFrame, toScene, towerByKey } from './config.js';
import { addSigns } from './signs.js';
import { bounds, interiorPoint } from './geometry.js';
import { apartments, aptsOnFloor, priceOf, summaryOf } from './data.js';
// prices in US dollars, thin spaces between thousands
const money = (v) => `${String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, '\u202f')} $`;
import { buildWorld } from './world.js';
import { OUTLINE, loadComplex } from './building.js';
import { buildFloor } from './floor.js';
import { KINDS, loadSiteMap, siteWalk } from './sitewalk.js';
import { DAY, FIRST, LAST, clock as hhmm, timeOfDay } from './night.js';
import { ROOM_LIGHT } from './interior/materials.js';
import { captureReflections } from './reflections.js';
import { addGrass } from './grass.js';
import { addFlowers, flowerBeds } from './flowers.js';
import { GROUND_AO } from './materials.js';
import { WalkControls } from './walk.js';
import { drawPlan, planTransform } from './plan.js';
import { Q, setQuality } from './quality.js';
import { createRenderer, createPipeline } from './render.js';
import { setupMaterial, water } from './materials.js';
import { WIND, driveCars, setDrivers, updateCars } from './props.js';
import { L, getLang, num, setLang } from './i18n.js';

const $ = (s) => document.querySelector(s);
const ACCENT = 0xc8955a;

let walkInterior = null; // the flat walked through, or the ground (sitewalk.js); declared up here: the wording reads it

// ---------- static wording ----------
function applyStatic() {
  document.querySelectorAll('[data-t]').forEach((el) => {
    const v = L()[el.dataset.t];
    if (typeof v === 'string') el.textContent = v;
  });
  document.querySelectorAll('.lang button').forEach((b) => b.classList.toggle('on', b.dataset.lang === getLang()));
  $('#walk-help').innerHTML = walkInterior?.outdoor ? L().walkHelpSite : L().walkHelp;
  $('#exit-walk').textContent = walkInterior?.outdoor ? L().exitSiteWalk : L().exitWalk;
  $('#daytime-range').setAttribute('aria-label', L().dayTime);
  $('#daytime').title = L().dayTime;
  const eye = $('#eye'), clean = document.body.classList.contains('clean');
  eye.title = clean ? L().showUi : L().hideUi;
  eye.setAttribute('aria-label', eye.title);
  const q = $('#quality');
  q.textContent = L().quality(Q.level === 'high');
  q.title = L().qualityTitle(Q.level === 'high');
  document.title = `${L().brand} — 3D`;
}
applyStatic();
document.querySelector('.lang').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-lang]');
  if (!b || b.dataset.lang === getLang()) return;
  setLang(b.dataset.lang);
  applyStatic();
  buildPlaces();
  buildLabels();
  refresh();
  if (state.mode === 'walk' && walkInterior) walkInterior.outdoor ? ($('#walk-title').innerHTML = L().siteWalkTitle) : setWalkTitle(walkInterior.apt);
});

// ---------- renderer / scene ----------
let renderer;
try {
  renderer = createRenderer();
} catch (err) {
  console.error(err);
  document.body.classList.add('no-webgl');
  $('#loading').hidden = true;
  $('#nogl').hidden = false;
  throw err;
}
$('#stage').appendChild(renderer.domElement);
const canvas = renderer.domElement;
canvas.addEventListener('webglcontextlost', (e) => {
  e.preventDefault();
  $('#nogl').hidden = false;
  $('#nogl .why').textContent = L().contextLost;
});

const scene = new THREE.Scene();
// the scene stands still: the sun's shadow map is redrawn only when something changes
renderer.shadowMap.autoUpdate = false;
let shadowFrames = 2;
const shadowsDirty = () => (shadowFrames = 2);
THREE.DefaultLoadingManager.onProgress = shadowsDirty;

const camera = new THREE.PerspectiveCamera(38, innerWidth / innerHeight, 1, 30000);
// Start view: the whole complex from the south-west, over the street, the mountains behind it.
const HOME_WIDE = { pos: new THREE.Vector3(165, 105, 140), target: new THREE.Vector3(-24, 30, 6) };
// portrait: the panel covers the lower half, so the camera aims below the complex (it shows higher up)
const HOME_TALL = { pos: new THREE.Vector3(250, 165, 215), target: new THREE.Vector3(-24, 22, 6) };
const home = () => (innerWidth < innerHeight ? HOME_TALL : HOME_WIDE);
camera.position.copy(home().pos);

const controls = new OrbitControls(camera, canvas);
controls.target.copy(home().target);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 12;
controls.maxDistance = 900;
controls.maxPolarAngle = Math.PI * 0.48;
controls.autoRotate = false;
controls.autoRotateSpeed = 0.3;

let building = null;
const loadingEl = $('#loading');
const modelLoad = loadComplex(apartments, renderer, (k) => (loadingEl.querySelector('b').textContent = `${Math.round(k * 100)}%`));
const world = buildWorld(scene, renderer, modelLoad.then(() => {}, () => {}));
const pipeline = createPipeline(renderer, scene, camera);
const walk = new WalkControls(camera, canvas);

// invisible prisms over every block, for hovering / clicking a whole block
const blockPicks = [];
for (const t of TOWERS) {
  const shape = new THREE.Shape(t.outline.map(([x, y]) => {
    const w = toScene(x, y);
    return new THREE.Vector2(w.x, -w.z);
  }));
  const g = new THREE.ExtrudeGeometry(shape, { depth: t.top + 4, bevelEnabled: false });
  g.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ visible: false }));
  m.userData.block = t.key;
  scene.add(m);
  blockPicks.push(m);
}

modelLoad
  .then((b) => {
    building = b;
    scene.add(b.group);
    setupMaterial(world.cityMat, renderer);
    addSigns(scene, SHOPS, toScene, new URLSearchParams(location.search).get('signs'))
      .then(() => (daytime?.refresh(), shadowsDirty()))
      .catch((e) => console.warn('signs', e));
    shadowsDirty();
    loadingEl.hidden = true;
    refresh();
  })
  .catch((err) => {
    console.error(err);
    loadingEl.textContent = L().loadFailed;
  });

$('#quality').onclick = () => setQuality(Q.level === 'high' ? 'low' : 'high');

// ---------- time of day (src/night.js) ----------
// the slider from early morning to late night; the site starts in the afternoon light it was made for
let daytime = null;
const dtRange = $('#daytime-range'), dtClock = $('#daytime-clock');
dtRange.min = FIRST;
dtRange.max = LAST;
dtRange.step = 0.25;
dtRange.value = DAY;
function showHours(h) {
  dtClock.textContent = hhmm(h);
  const s = daytime?.state;
  $('#daytime').dataset.phase = !s ? 'day' : s.night > 0.5 ? 'night' : s.lights > 0.05 || h > 17.5 ? 'dusk' : 'day';
  dtRange.style.setProperty('--k', `${((h - FIRST) / (LAST - FIRST)) * 100}%`);
}
function setHours(h) {
  if (!daytime) return;
  daytime.set(h);
  dtRange.value = daytime.hours;
  showHours(daytime.hours);
}
showHours(DAY);
Promise.all([modelLoad, world.ready])
  .then(() => {
    daytime = timeOfDay({
      scene, camera, renderer, world, lamps: LAMPS, shops: SHOPS, toScene, cityLights: world.cityLights,
      changed: (s) => {
        lightIndoors();
        pipeline.bloom(s.lights * 1.15);
        shadowsDirty();
      },
    });
    daytime.indoors(!!outdoor);
    $('#daytime').hidden = false;
    // the flower beds on the lawns (both levels: a few thousand small cards)
    loadSiteMap()
      .then((map) => {
        flowers = addFlowers(scene, map, toScene);
        shadowsDirty();
      })
      .catch((e) => console.warn('flowers', e))
      .finally(() => Q.level === 'high' && highQuality());
  })
  .catch((e) => console.warn('time of day', e));
dtRange.addEventListener('input', () => setHours(+dtRange.value));

let grass = null, flowers = null, hqDone = false;
// High quality (computers): the ground's baked sky occlusion and glass that reflects its surroundings
// (taken once, in daylight, when everything is in; the floor or flat open meanwhile is put back)
async function highQuality() {
  try {
    const base = `${import.meta.env.BASE_URL}models/`;
    const [box, tex] = await Promise.all([
      fetch(`${base}ground_ao.json`).then((r) => r.json()),
      new THREE.TextureLoader().loadAsync(`${base}ground_ao.webp`),
    ]);
    tex.colorSpace = THREE.NoColorSpace;
    tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
    tex.anisotropy = 4;
    GROUND_AO.map.value = tex;
    GROUND_AO.box.value.set(box.x0, box.z0, 1 / box.w, 1 / box.d);
    GROUND_AO.k.value = 0.7;
  } catch (e) {
    console.warn('ground occlusion', e);
  }
  // grass with blades on the lawns round the camera, the trees and the grass in a light breeze
  try {
    const map = await loadSiteMap();
    grass = addGrass(scene, map, WIND, flowerBeds(map));
    WIND.amp.value = 0.07;
  } catch (e) {
    console.warn('grass', e);
  }
  await new Promise((r) => setTimeout(r, 300));
  const hours = daytime.hours;
  if (hours !== DAY) daytime.set(DAY);
  captureReflections({ renderer, scene, building, towers: TOWERS, toScene });
  if (hours !== DAY) daytime.set(hours);
  if (state.mode === 'floor' && state.tower) building.showUpTo(state.tower, state.floor);
  else if (state.mode === 'walk' && walkInterior && !walkInterior.outdoor) building.showAll(state.tower, state.floor);
  shadowsDirty();
  hqDone = true;
}
// let go of the slider: the arrow keys walk again (a focused slider would take them)
dtRange.addEventListener('pointerup', () => dtRange.blur());

// ---------- the eye: hide every panel, only the view stays (and the eye, to bring them back) ----------
function setClean(on) {
  document.body.classList.toggle('clean', on);
  $('#eye').setAttribute('aria-pressed', String(on));
  tooltip.style.opacity = 0;
  applyStatic();
}
$('#eye').onclick = () => setClean(!document.body.classList.contains('clean'));

// ---------- state ----------
const state = {
  mode: 'overview', // overview | block | floor | walk
  tower: null,
  floor: null,
  apt: null,
  hoverApt: null,
  hoverFloor: null, // { tower, floor }
  filter: { rooms: 0 },
};
let dollhouse = [];
let lastInteraction = performance.now();

const isOpen = (a) => a.tower === state.tower && a.floor === state.floor;
const filterActive = () => state.filter.rooms > 0;
const matches = (a) => !state.filter.rooms || a.rooms === state.filter.rooms || (state.filter.rooms === 4 && a.rooms >= 4);
const towerApts = (k) => apartments.filter((a) => a.tower === k);
const sameFloor = (a, b) => !!a && !!b && a.tower === b.tower && a.floor === b.floor;

// ---------- camera flights ----------
let tween = null;
function flyTo(pos, target, dur = 1.2) {
  tween = { p0: camera.position.clone(), t0: controls.target.clone(), p1: pos.clone(), t1: target.clone(), t: 0, dur };
  controls.enabled = false;
}
function azimuth() {
  return Math.atan2(camera.position.x - controls.target.x, camera.position.z - controls.target.z);
}
function towerCentre(k) {
  const t = towerByKey[k];
  const w = toScene(t.centre[0], t.centre[1]);
  return new THREE.Vector3(w.x, 0, w.z);
}
function blockView(k) {
  const t = towerByKey[k];
  const c = towerCentre(k);
  const target = c.clone().setY(t.top * 0.45);
  // from the side of the camera now, far enough to see the whole block
  const az = Math.atan2(camera.position.x - c.x, camera.position.z - c.z);
  const d = t.top * 1.55 + 40;
  return { pos: target.clone().add(new THREE.Vector3(Math.sin(az) * d, t.top * 0.35, Math.cos(az) * d)), target };
}
function floorCentre(tower, floor) {
  const list = aptsOnFloor(tower, floor);
  const c = new THREE.Vector3();
  for (const a of list) c.add(building.units.get(a.id).center);
  return c.divideScalar(list.length);
}
function floorView(tower, floor) {
  // far enough for the whole floor to fit between the side panels (slab blocks 64 m, tower A 45 m)
  const target = floorCentre(tower, floor);
  let az = azimuth();
  if (tower !== 'A') {
    // a slab block from its long side (the side nearer the camera): the flats in two rows, side by
    // side across the screen, their tags in two rows too
    const fr = planFrame(towerByKey[tower]);
    const o = fr.toScene(0, 0), y1 = fr.toScene(0, 1);
    const side = Math.atan2(y1.x - o.x, y1.z - o.z);
    const off = (a) => Math.abs(Math.atan2(Math.sin(a - az), Math.cos(a - az)));
    az = off(side) <= off(side + Math.PI) ? side : side + Math.PI;
  }
  const size = tower === 'A' ? 46 : 66;
  const d = size * (innerWidth < innerHeight ? 2.6 : 1.75);
  // (slab blocks steeper from above: the two rows of flats and their tags well apart)
  const [hz, vt] = tower === 'A' ? [0.55, 0.85] : [0.42, 0.9];
  return { pos: target.clone().add(new THREE.Vector3(Math.sin(az) * d * hz, d * vt, Math.cos(az) * d * hz)), target };
}
function aptView(apt) {
  const c = building.units.get(apt.id).center;
  const target = new THREE.Vector3(c.x, c.y + 0.5, c.z);
  const tc = towerCentre(apt.tower);
  const dir = new THREE.Vector3(c.x - tc.x, 0, c.z - tc.z).normalize();
  // steeply from above the opened floor (the neighbouring block can stand 25 m away)
  const tall = innerWidth < innerHeight;
  const pos = target.clone().add(dir.multiplyScalar(tall ? 14 : 15)).add(new THREE.Vector3(0, tall ? 52 : 34, 0));
  // on a portrait screen the panel covers the lower half: aim below the flat so it shows higher up
  return { pos, target: tall ? target.clone().addScaledVector(dir.normalize(), 12) : target };
}

// ---------- overlays on the building ----------
function updateOverlays() {
  if (!building) return;
  for (const a of apartments) {
    const u = building.units.get(a.id);
    if (!u) continue;
    let show = false, color = 0xffffff, op = 0, edges = null;
    const hoverFloor = sameFloor(state.hoverFloor, a);
    if (state.mode === 'overview' || state.mode === 'block') {
      if (hoverFloor) {
        // the floor under the pointer: amber (it shows on the brick and on the white top floors
        // alike), with a white outline round every flat
        show = true; op = 0.62; edges = OUTLINE.floor; color = 0xffa42b;
      } else if (filterActive() && matches(a) && (state.mode === 'overview' || a.tower === state.tower)) {
        show = true; color = ACCENT; op = 0.55;
      }
    } else if (state.mode === 'floor') {
      if (isOpen(a)) {
        // the flats of the open floor: a light outline each; the one under the pointer (or chosen)
        // lit up in amber with a thick outline drawn over the walls and furniture
        const lit = a === state.apt || a === state.hoverApt;
        show = true; color = lit ? 0xffa42b : ACCENT;
        edges = a === state.apt ? OUTLINE.chosen : a === state.hoverApt ? OUTLINE.hover : OUTLINE.open;
        op = a === state.apt ? 0.48 : a === state.hoverApt ? 0.44 : 0.06;
        if (filterActive() && !matches(a)) [op, edges] = [0.0, null];
      } else if (hoverFloor) {
        show = true; op = 0.35;
      }
    }
    u.overlay.visible = show;
    u.overlay.material.color.setHex(color);
    u.overlay.material.opacity = op;
    // a floor seen from outside: the outline of every flat's volume; the open floor: each flat's
    // outline on the floor plan
    const line = state.mode === 'floor' ? u.ring : u.edges;
    (line === u.ring ? u.edges : u.ring).visible = false;
    line.visible = show && !!edges;
    if (edges) line.material = edges;
    line.renderOrder = edges === OUTLINE.hover || edges === OUTLINE.chosen ? 12 : 11;
  }
}

// ---------- tags over the apartments of the open floor ----------
const labelsEl = $('#labels');
let labels = [];
function sidesText(a) {
  return a.sides.map((s) => L().sides[s]).join(', ');
}
let liftLabels = [];
// the point a flat's tag points at: inside the flat (the point furthest from its walls), on top of
// the cut walls of the open floor
function tagAnchor(a) {
  const u = building.units.get(a.id);
  const [px, py] = interiorPoint(a.data.outline);
  const s = planFrame(towerByKey[a.tower]).toScene(px, py);
  return new THREE.Vector3(s.x, u.top + 0.15, s.z);
}
function buildLabels() {
  labelsEl.innerHTML = '';
  labels = [];
  liftLabels = [];
  if (state.mode !== 'floor') return;
  const add = (cls, html) => {
    const el = document.createElement('div');
    el.className = cls;
    el.innerHTML = html;
    const line = document.createElement('i');
    line.className = 'tag-line';
    const dot = document.createElement('i');
    dot.className = 'tag-dot';
    labelsEl.append(line, dot, el);
    return { el, line, dot };
  };
  // the lifts of the open floor, as on the drawings: how many, and their capacities
  for (const t of dollhouse[0]?.liftTags ?? []) {
    const tag = add('tag lift', `<b>${L().lifts(t.q.length)}</b><span>Q ${t.q.join(' / ')} ${L().kg}</span>`);
    liftLabels.push({ ...tag, pos: new THREE.Vector3(t.x, t.y, t.z) });
  }
  for (const a of aptsOnFloor(state.tower, state.floor)) {
    const tag = add('tag', `<b>№ ${a.number}</b><span>${num(a.area)} ${L().m2}</span>`);
    tag.el.title = `№ ${a.number} · ${L().roomsShort(a.rooms)} · ${num(a.area)} ${L().m2}`;
    tag.el.onclick = () => selectApt(a);
    tag.el.onpointerenter = () => setHover(a);
    tag.el.onpointerleave = () => setHover(null);
    labels.push({ ...tag, apt: a, pos: tagAnchor(a) });
  }
  for (const t of [...labels, ...liftLabels]) [t.w, t.h] = [t.el.offsetWidth, t.el.offsetHeight];
}
const tmp = new THREE.Vector3();
function project(v) {
  tmp.copy(v).project(camera);
  return { x: ((tmp.x + 1) / 2) * innerWidth, y: ((1 - tmp.y) / 2) * innerHeight, behind: tmp.z > 1 };
}
function updateLabels() {
  // each tag stands right over its flat, a dot and a thin line down to it; where tags would cover
  // one another, the farther one moves up (the nearer ones first, they are in front)
  const list = [];
  for (const t of [...labels, ...liftLabels]) {
    const p = project(t.pos);
    const hidden = p.behind || (t.apt && filterActive() && !matches(t.apt));
    for (const el of [t.el, t.line, t.dot]) el.style.display = hidden ? 'none' : '';
    if (!hidden) list.push({ t, p });
    if (t.apt) t.el.classList.toggle('hover', t.apt === state.hoverApt);
  }
  list.sort((p, q) => q.p.y - p.p.y);
  const placed = [];
  for (const { t, p } of list) {
    const w = t.w || 80, h = t.h || 34;
    const x0 = p.x - w / 2;
    let top = p.y - 14 - h;
    for (let i = 0; i < 8; i++) {
      const hit = placed.find((r) => x0 < r.x1 + 4 && x0 + w > r.x0 - 4 && top < r.y1 + 3 && top + h > r.y0 - 3);
      if (!hit) break;
      top = hit.y0 - 3 - h;
    }
    placed.push({ x0, x1: x0 + w, y0: top, y1: top + h });
    t.el.style.left = `${x0}px`;
    t.el.style.top = `${top}px`;
    t.dot.style.left = `${p.x}px`;
    t.dot.style.top = `${p.y}px`;
    t.line.style.left = `${p.x}px`;
    t.line.style.top = `${top + h}px`;
    t.line.style.height = `${Math.max(0, p.y - top - h)}px`;
  }
}

// ---------- block letters and the places around ----------
const placesEl = $('#places');
let places = [];
function buildPlaces() {
  placesEl.innerHTML = '';
  places = [];
  for (const p of PLACES) {
    const el = document.createElement('div');
    const w = toScene(p.x, p.y);
    const pos = new THREE.Vector3(w.x, p.z, w.z);
    if (p.kind === 'block') {
      const t = towerByKey[p.key];
      el.className = `block-tag ${t.sales ? 'sales' : 'neighbour'}`;
      el.innerHTML = `<b>${LETTER[p.key]}</b>`;
      el.title = L().block(LETTER[p.key]);
      el.onclick = () => (t.sales ? selectBlock(p.key) : toast(L().neighbourBlock));
    } else {
      el.className = `place-tag ${p.kind}`;
      el.innerHTML = `<i></i><span>${L().places[p.kind] ?? (getLang() === 'tj' ? p.tj : p.ru)}</span>`;
      el.onclick = () => flyToPlace(pos);
    }
    placesEl.appendChild(el);
    places.push({ el, pos, p });
  }
}
// a place behind a block (seen through it) is shown faint; checked a few times a second
const occRay = new THREE.Raycaster();
let occAt = 0;
function updatePlaces() {
  const show = state.mode === 'overview' || state.mode === 'block';
  placesEl.style.display = show ? '' : 'none';
  if (!show) return;
  const now = performance.now(), checkOcc = now - occAt > 200;
  if (checkOcc) occAt = now;
  for (const it of places) {
    const { el, pos, p } = it;
    const q = project(pos);
    const hideBlock = p.kind === 'block' && state.mode === 'block' && p.key === state.tower;
    el.style.display = q.behind || hideBlock ? 'none' : '';
    el.style.left = `${q.x}px`;
    el.style.top = `${q.y}px`;
    if (checkOcc && p.kind !== 'block') {
      const d = pos.clone().sub(camera.position), L = d.length();
      occRay.set(camera.position, d.normalize());
      occRay.far = L - 2;
      it.hidden = occRay.intersectObjects(blockPicks, false).length > 0;
      el.classList.toggle('behind', it.hidden);
    }
  }
}
function flyToPlace(pos) {
  const az = azimuth();
  const target = pos.clone().setY(8);
  flyTo(target.clone().add(new THREE.Vector3(Math.sin(az) * 110, 70, Math.cos(az) * 110)), target, 1.4);
}

// ---------- panels ----------
function renderFloors() {
  const T = L();
  let html = `<button class="overview-btn ${state.mode === 'overview' ? 'active' : ''}" data-act="overview">⌂ ${T.complex}</button>`;
  html += `<h3>${T.blocks}</h3><div class="block-tabs">`;
  for (const t of TOWERS) {
    const on = state.tower === t.key && state.mode !== 'overview';
    html += `<button class="block-tab ${on ? 'on' : ''} ${t.sales ? '' : 'off'}" data-block="${t.key}" title="${t.sales ? T.block(LETTER[t.key]) : T.neighbourBlock}">${LETTER[t.key]}</button>`;
  }
  html += '</div>';
  if (state.tower && state.mode !== 'overview') {
    const t = towerByKey[state.tower];
    html += `<h3>${T.floors}</h3>`;
    for (const { floor: f } of [...t.floors].reverse()) {
      const list = aptsOnFloor(t.key, f);
      const n = list.filter(matches).length;
      const active = state.mode === 'floor' && state.floor === f;
      const hover = state.hoverFloor && state.hoverFloor.tower === t.key && state.hoverFloor.floor === f;
      html += `<button class="floor-btn ${active ? 'active' : ''} ${hover ? 'hover' : ''} ${filterActive() && !n ? 'dim' : ''}" data-floor="${f}">
        <span class="num">${f}</span><span class="meta">${filterActive() ? `${n} / ` : ''}${T.flats(list.length)}</span></button>`;
    }
    html += `<button class="floor-btn lobby" disabled><span class="num">1–2</span><span class="meta">${T.shops}</span></button>`;
  } else {
    html += `<div class="block-list">`;
    for (const t of RESIDENTIAL) {
      const list = towerApts(t.key);
      html += `<button class="block-row" data-block="${t.key}"><b>${LETTER[t.key]}</b><span>${T.floorsN(t.levels)}<br>${T.flats(list.length)}</span></button>`;
    }
    html += `</div>`;
  }
  $('#floors').innerHTML = html;
}
$('#floors').addEventListener('click', (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  if (b.dataset.act === 'overview') goOverview();
  else if (b.dataset.block) {
    const t = towerByKey[b.dataset.block];
    if (t.sales) selectBlock(t.key);
    else toast(L().neighbourBlock);
  } else if (b.dataset.floor) selectFloor(state.tower, +b.dataset.floor);
});
$('#floors').addEventListener('pointerover', (e) => {
  const b = e.target.closest('[data-floor]');
  const hf = b ? { tower: state.tower, floor: +b.dataset.floor } : null;
  if (JSON.stringify(hf) !== JSON.stringify(state.hoverFloor)) {
    state.hoverFloor = hf;
    updateOverlays();
  }
});
$('#floors').addEventListener('pointerleave', () => {
  state.hoverFloor = null;
  updateOverlays();
});

function roomFilter(list) {
  const T = L();
  const rooms = [...new Set(list.map((a) => Math.min(a.rooms, 4)))].sort();
  return `<div class="label">${T.rooms}</div><div class="seg" data-filter="rooms">
    ${[0, ...rooms].map((r) => `<button data-v="${r}" class="${state.filter.rooms === r ? 'on' : ''}">${r ? T.roomsShort(r) : T.all}</button>`).join('')}
  </div>`;
}

function renderSide() {
  const side = $('#side');
  const T = L();
  if (state.mode === 'overview') {
    const areas = apartments.map((a) => a.area);
    side.innerHTML = `
      <h2>${T.chooseTitle}</h2>
      <div class="sub">${T.chooseSub}</div>
      <div class="stats">
        <div class="stat"><b>${apartments.length}</b><span>${T.stat1}</span></div>
        <div class="stat"><b>${num(Math.round(Math.min(...areas)))}–${num(Math.round(Math.max(...areas)))}</b><span>${T.stat2}</span></div>
        <div class="stat"><b>${Math.min(...RESIDENTIAL.map((t) => t.levels))}–${Math.max(...RESIDENTIAL.map((t) => t.levels))}</b><span>${T.stat3}</span></div>
      </div>
      <button class="btn site-walk" data-act="sitewalk">${T.siteWalk}</button>
      ${roomFilter(apartments)}
      <div class="note">${T.chooseNote}</div>
      <div class="label">${T.nearby}</div>
      <div class="near">
        ${PLACES.filter((p) => p.kind !== 'block').map((p, i) => `<button class="near-btn ${p.kind}" data-place="${i}"><i></i>${T.places[p.kind]}</button>`).join('')}
      </div>`;
  } else if (state.mode === 'block') {
    const t = towerByKey[state.tower];
    const list = towerApts(t.key);
    const areas = list.map((a) => a.area);
    side.innerHTML = `
      <button class="back" data-act="overview">${T.backTo(T.complex)}</button>
      <h2>${T.block(LETTER[t.key])}</h2>
      <div class="sub">${T.blockSub(T.floorsN(t.levels), T.flats(list.length))} · ${T.shopsFloors}</div>
      <div class="stats">
        <div class="stat"><b>${list.length}</b><span>${T.stat1}</span></div>
        <div class="stat"><b>${num(Math.round(Math.min(...areas)))}–${num(Math.round(Math.max(...areas)))}</b><span>${T.stat2}</span></div>
        <div class="stat"><b>${t.levels}</b><span>${T.stat3}</span></div>
      </div>
      <button class="btn site-walk" data-act="sitewalk" data-from="${t.key}">${T.siteWalkBlock(LETTER[t.key])}</button>
      ${roomFilter(list)}
      <div class="note">${T.blockNote}</div>`;
  } else if (state.mode === 'floor' && !state.apt) {
    const list = aptsOnFloor(state.tower, state.floor);
    side.innerHTML = `
      <button class="back" data-act="block">${T.backTo(T.block(LETTER[state.tower]))}</button>
      <h2>${T.block(LETTER[state.tower])} · ${T.floorN(state.floor)}</h2>
      <div class="sub">${T.flatsOnFloor(list.length)}</div>
      ${roomFilter(list)}
      <div class="apt-list">
        ${[...list].sort((a, b) => a.number - b.number).map((a) => `
          <button class="apt-row ${filterActive() && !matches(a) ? 'muted' : ''}" data-apt="${a.id}">
            <span class="t">№ ${a.number}</span><span class="p">${num(a.area)} ${T.m2}${priceOf(a.floor) ? ` · ${money(Math.round(priceOf(a.floor) * a.area / 100) * 100)}` : ''}</span>
            <span class="d">${T.roomsN(a.rooms)} · ${sidesText(a)}</span>
          </button>`).join('')}
      </div>
      <div class="note">${T.floorNote}</div>`;
  } else if (state.mode === 'floor' && state.apt) {
    const a = state.apt;
    side.innerHTML = `
      <button class="back" data-act="floor">${T.backTo(T.floorN(a.floor))}</button>
      <h2>${T.flat(a.number)}</h2>
      <div class="sub">${T.block(a.letter)} · ${T.roomsN(a.rooms)} · ${T.floorN(a.floor)}</div>
      <div class="plan-wrap"><canvas class="plan" title="${T.planZoom}"></canvas><button class="plan-zoom" data-act="zoom" title="${T.planZoom}" aria-label="${T.planZoom}">⤢</button></div>
      <div class="area-big">${num(a.area)} <small>${T.m2}</small></div>
      ${priceOf(a.floor) ? `<div class="price"><div><span>${T.pricePerM2}</span><b>${money(priceOf(a.floor))}</b></div><div><span>${T.priceTotal}</span><b>≈ ${money(Math.round(priceOf(a.floor) * a.area / 100) * 100)}</b></div></div>` : ''}
      <div class="specs">
        <div><span>${T.rooms}</span><b>${a.rooms}</b></div>
        <div><span>${T.floor}</span><b>${T.floorOf(a.floor, a.floors)}</b></div>
        <div><span>${T.ceiling}</span><b>${num(a.ceiling)} ${T.m}</b></div>
        <div><span>${T.windows}</span><b>${sidesText(a)}</b></div>
        <div style="grid-column: span 2"><span>${T.layout}</span><b>${summaryOf(a.data.rooms.concat(a.data.balconies))}</b></div>
      </div>
      <div class="actions">
        <button class="btn primary" data-act="walk">${T.walk}</button>
        <button class="btn" data-act="request">${T.contact}</button>
      </div>`;
    const cv = side.querySelector('.plan');
    cv.style.height = `${planHeight(a, cv.clientWidth)}px`;
    drawPlan(cv, a);
    cv.onclick = () => openPlan(a);
  }
}
// width / height of a flat's plan with its balconies
function planAspect(a) {
  const b = bounds([...a.data.outline, ...a.data.balconies.flatMap((q) => q.poly)]);
  return (b.x1 - b.x0) / (b.y1 - b.y0);
}
// The card's plan as tall as the flat's shape asks for (a long narrow flat gets a tall plan), as far
// as the screen leaves room for the rest of the card
function planHeight(a, w) {
  const want = (w - 28) / planAspect(a) + 28;
  const most = innerWidth <= 760 ? 210 : 210 + Math.max(0, Math.min(150, innerHeight - 730));
  return Math.round(Math.min(Math.max(want, 210), most));
}
// the plan full-screen, its rooms' names and areas in larger type
function openPlan(a) {
  const box = $('#plan-big');
  box.querySelector('b').textContent = `${L().flat(a.number)} · ${num(a.area)} ${L().m2}`;
  box.querySelector('button').textContent = `✕ ${L().close}`;
  box.hidden = false;
  const pad = 24, k = planAspect(a);
  let w = Math.min(innerWidth - 68, 1100), h = (w - 2 * pad) / k + 2 * pad;
  const most = innerHeight - 130;
  if (h > most) [h, w] = [most, Math.min(w, (most - 2 * pad) * k + 2 * pad)];
  const cv = box.querySelector('canvas');
  cv.style.width = `${Math.round(w)}px`;
  cv.style.height = `${Math.round(h)}px`;
  drawPlan(cv, a, { pad, text: innerWidth <= 760 ? 1.15 : 1.45 });
}
const closePlan = () => ($('#plan-big').hidden = true);
$('#plan-big').addEventListener('click', (e) => {
  if (e.target === e.currentTarget || e.target.closest('[data-act="close"]')) closePlan();
});
$('#side').addEventListener('click', (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  if (b.dataset.act === 'overview') goOverview();
  else if (b.dataset.act === 'block') selectBlock(state.tower);
  else if (b.dataset.act === 'floor') selectFloor(state.tower, state.floor);
  else if (b.dataset.act === 'walk') enterWalk(state.apt);
  else if (b.dataset.act === 'sitewalk') enterSiteWalk(b.dataset.from ?? null);
  else if (b.dataset.act === 'zoom') openPlan(state.apt);
  else if (b.dataset.act === 'request') toast(L().contactToast);
  else if (b.dataset.apt) selectApt(apartments.find((a) => a.id === b.dataset.apt));
  else if (b.dataset.place !== undefined) {
    const p = PLACES.filter((q) => q.kind !== 'block')[+b.dataset.place];
    const w = toScene(p.x, p.y);
    flyToPlace(new THREE.Vector3(w.x, p.z, w.z));
  } else if (b.dataset.v !== undefined) {
    state.filter.rooms = +b.dataset.v;
    refresh();
  }
});
$('#side').addEventListener('pointerover', (e) => {
  const row = e.target.closest('[data-apt]');
  setHover(row ? apartments.find((a) => a.id === row.dataset.apt) : null);
});
$('#side').addEventListener('pointerleave', () => setHover(null));

function refresh() {
  renderFloors();
  renderSide();
  if (!$('#plan-big').hidden) state.apt ? openPlan(state.apt) : closePlan();
  updateOverlays();
  const T = L();
  $('#hint').textContent = state.mode === 'overview' ? T.hintOverview : state.mode === 'block' ? T.hintBlock : T.hintFloor;
}

let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
}

function setHover(a) {
  if (state.hoverApt === a) return;
  state.hoverApt = a;
  updateOverlays();
  document.querySelectorAll('.apt-row').forEach((r) => r.classList.toggle('hover', a && r.dataset.apt === a.id));
}

// ---------- navigation ----------
function clearDollhouse() {
  dollhouse.forEach((d) => d.dispose());
  dollhouse = [];
}

function goOverview() {
  shadowsDirty();
  clearDollhouse();
  building?.showAll();
  Object.assign(state, { mode: 'overview', tower: null, floor: null, apt: null, hoverApt: null, hoverFloor: null });
  buildLabels();
  flyTo(home().pos, home().target, 1.4);
  refresh();
}

function selectBlock(k) {
  shadowsDirty();
  clearDollhouse();
  building?.showAll();
  Object.assign(state, { mode: 'block', tower: k, floor: null, apt: null, hoverApt: null, hoverFloor: null });
  const v = blockView(k);
  flyTo(v.pos, v.target, 1.3);
  buildLabels();
  refresh();
}

function selectFloor(tower, floor) {
  shadowsDirty();
  if (!building) return;
  if (state.tower !== tower || state.floor !== floor || state.mode !== 'floor') {
    clearDollhouse();
    building.showUpTo(tower, floor);
    const d = buildFloor(tower, floor, aptsOnFloor(tower, floor));
    scene.add(d.group);
    dollhouse.push(d);
  }
  Object.assign(state, { mode: 'floor', tower, floor, apt: null, hoverFloor: null });
  const v = floorView(tower, floor);
  flyTo(v.pos, v.target);
  buildLabels();
  refresh();
}

function selectApt(a) {
  if (state.mode !== 'floor' || !isOpen(a)) selectFloor(a.tower, a.floor);
  state.apt = a;
  const v = aptView(a);
  flyTo(v.pos, v.target);
  refresh();
}

function fade(fn) {
  const f = $('#fade');
  f.classList.add('on');
  setTimeout(() => {
    fn();
    requestAnimationFrame(() => requestAnimationFrame(() => f.classList.remove('on')));
  }, 380);
}

function setWalkTitle(a) {
  const T = L();
  $('#walk-title').innerHTML = `<b>№ ${a.number}</b> · ${T.block(a.letter)} · ${T.roomsShort(a.rooms)} · ${num(a.area)} ${T.m2} · ${T.floorN(a.floor)}`;
}

function enterWalk(a) {
  shadowsDirty();
  fade(() => {
    clearDollhouse();
    labelsEl.innerHTML = '';
    labels = [];
    liftLabels = [];
    building.showAll(a.tower, a.floor);
    walkInterior = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor), a);
    scene.add(walkInterior.group);
    shadowsDirty();
    state.mode = 'walk';
    state.hoverApt = null;
    updateOverlays();
    tween = null;
    controls.enabled = false;
    camera.fov = 72;
    camera.near = 0.05;
    frameCentre();
    pipeline.walk(true);
    lightInterior(walkInterior);
    camera.updateProjectionMatrix();
    walk.start(walkInterior, scene);
    $('#ext-ui').hidden = true;
    $('#walk-ui').hidden = false;
    document.body.classList.add('walking');
    setWalkTitle(a);
    prepareMinimap(a);
  });
}

// On the ground round the complex: the walk of src/sitewalk.js on the map of the ground the Blender
// build writes (what is underfoot, what one cannot walk through). Outdoors light as it is; the sun's
// shadow drawn finer round the walker, following them.
let sunSaved = null, sunAt = null;
async function enterSiteWalk(from = null) {
  if (!building || state.mode === 'walk') return;
  let map;
  try {
    const slow = setTimeout(() => toast(L().siteLoading), 250);
    map = await loadSiteMap();
    clearTimeout(slow);
  } catch (err) {
    console.error(err);
    toast(L().loadFailed);
    return;
  }
  shadowsDirty();
  fade(() => {
    clearDollhouse();
    building.showAll();
    labelsEl.innerHTML = '';
    labels = [];
    liftLabels = [];
    walkInterior = siteWalk(map, from, blockPicks, flowerBeds(map));
    placesEl.style.display = 'none';
    tooltip.style.opacity = 0;
    Object.assign(state, { mode: 'walk', apt: null, hoverApt: null, hoverFloor: null });
    updateOverlays();
    tween = null;
    controls.enabled = false;
    controls.autoRotate = false;
    camera.fov = 64;
    camera.near = 0.1;
    frameCentre();
    camera.updateProjectionMatrix();
    walk.start(walkInterior, scene);
    // the sun's shadow: 160 m round the walker instead of the whole complex
    const sun = world.sun, sc = sun.shadow.camera;
    sunSaved = { cam: [sc.left, sc.right, sc.top, sc.bottom], pos: sun.position.clone(), target: sun.target.position.clone() };
    [sc.left, sc.right, sc.top, sc.bottom] = [-80, 80, 80, -80];
    sc.updateProjectionMatrix();
    sunAt = null;
    followSun();
    $('#ext-ui').hidden = true;
    $('#walk-ui').hidden = false;
    document.body.classList.add('walking');
    $('#walk-title').innerHTML = L().siteWalkTitle;
    applyStatic();
    prepareSiteMinimap(map);
  });
}
// keep the sun's finer shadow round the walker (redrawn when they have gone 30 m)
function followSun() {
  if (!sunSaved || !walkInterior?.outdoor) return;
  const p = walk.pos;
  if (sunAt && Math.hypot(p.x - sunAt.x, p.y - sunAt.y) < 30) return;
  sunAt = p.clone();
  const sun = world.sun;
  const off = sun.position.clone().sub(sun.target.position);
  sun.target.position.set(p.x, 0, p.y);
  sun.position.copy(sun.target.position).add(off);
  sun.target.updateMatrixWorld();
  shadowsDirty();
}
function exitSiteWalk() {
  shadowsDirty();
  fade(() => {
    walk.stop();
    walkInterior = null;
    const sun = world.sun, sc = sun.shadow.camera;
    if (sunSaved) {
      [sc.left, sc.right, sc.top, sc.bottom] = sunSaved.cam;
      sc.updateProjectionMatrix();
      sunBack(sunSaved);
      sun.target.updateMatrixWorld();
      sunSaved = null;
    }
    camera.fov = 38;
    camera.near = 1;
    camera.updateProjectionMatrix();
    controls.enabled = true;
    $('#ext-ui').hidden = false;
    $('#walk-ui').hidden = true;
    document.body.classList.remove('walking');
    applyStatic();
    state.mode = 'overview';
    frameCentre();
    camera.updateProjectionMatrix();
    camera.position.copy(home().pos);
    controls.target.copy(home().target);
    goOverview();
  });
}

// the sun back over its saved spot, at its saved distance, from where it stands now (the hour may
// have been changed meanwhile)
function sunBack(saved) {
  const sun = world.sun;
  const dir = sun.position.clone().sub(sun.target.position).normalize();
  sun.target.position.copy(saved.target);
  sun.position.copy(saved.target).addScaledVector(dir, saved.pos.distanceTo(saved.target));
}

// Indoors at night: the light is the rooms' own (ROOM_LIGHT on the interior's materials), the
// studio light that fills the whole scene turned down, so the street seen from the window is dark
function lightIndoors() {
  if (!outdoor) return;
  const L = daytime?.state.lights ?? 0;
  scene.environmentIntensity = 0.32 * (1 - 0.75 * L);
  bounce.intensity = 0.9 * (1 - 0.85 * L);
}

// Indoors: a studio-like environment instead of the sky, the sun's shadow pulled in round the flat.
let roomEnv = null, outdoor = null, bounce = null;
function lightInterior(interior) {
  const sun = world.sun, sc = sun.shadow.camera;
  if (interior) {
    roomEnv ??= new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
    outdoor = {
      env: scene.environment, envI: scene.environmentIntensity,
      cam: [sc.left, sc.right, sc.top, sc.bottom, sc.near, sc.far], pos: sun.position.clone(), target: sun.target.position.clone(),
    };
    scene.environment = roomEnv;
    scene.environmentIntensity = 0.32;
    bounce ??= new THREE.HemisphereLight(0xfff3e4, 0xd9c3a5, 0.9);
    scene.add(bounce);
    const c = new THREE.Box3().setFromObject(interior.group).getCenter(new THREE.Vector3());
    const dir = sun.position.clone().sub(sun.target.position).normalize();
    sun.target.position.copy(c);
    sun.position.copy(c).addScaledVector(dir, 120);
    [sc.left, sc.right, sc.top, sc.bottom, sc.near, sc.far] = [-30, 30, 30, -30, 60, 200];
  } else if (outdoor) {
    bounce?.removeFromParent();
    scene.environment = outdoor.env;
    scene.environmentIntensity = daytime ? daytime.state.env : outdoor.envI;
    [sc.left, sc.right, sc.top, sc.bottom, sc.near, sc.far] = outdoor.cam;
    sunBack(outdoor);
    outdoor = null;
  }
  daytime?.indoors(!!interior);
  lightIndoors();
  sun.target.updateMatrixWorld();
  sc.updateProjectionMatrix();
  shadowsDirty();
}

function exitWalk() {
  if (walkInterior?.outdoor) return exitSiteWalk();
  shadowsDirty();
  const a = walkInterior.apt;
  fade(() => {
    walk.stop();
    walkInterior.dispose();
    walkInterior = null;
    camera.fov = 38;
    camera.near = 1;
    pipeline.walk(false);
    lightInterior(null);
    camera.updateProjectionMatrix();
    controls.enabled = true;
    $('#ext-ui').hidden = false;
    $('#walk-ui').hidden = true;
    document.body.classList.remove('walking');
    state.mode = 'block';
    frameCentre();
    camera.updateProjectionMatrix();
    selectFloor(a.tower, a.floor);
    selectApt(a);
    const v = aptView(a);
    camera.position.copy(v.pos);
    controls.target.copy(v.target);
    tween = null;
    controls.enabled = true;
  });
}
$('#exit-walk').onclick = exitWalk;
addEventListener('keydown', (e) => {
  if (e.code === 'Escape') {
    if (!$('#plan-big').hidden) closePlan();
    else if (state.mode === 'walk') exitWalk();
    else if (state.mode === 'floor' && state.apt) selectFloor(state.tower, state.floor);
    else if (state.mode === 'floor') selectBlock(state.tower);
    else if (state.mode === 'block') goOverview();
  }
});

// ---------- mini-map ----------
const mini = $('#minimap canvas');
let miniBg = null, miniT = null;
function prepareMinimap(a) {
  const off = document.createElement('canvas');
  off.width = mini.clientWidth;
  off.height = mini.clientHeight;
  drawPlan(off, a, { pad: 6, labels: false });
  miniBg = off;
  miniT = planTransform(a, mini.clientWidth, mini.clientHeight, 6);
}
// the site's mini-map: the ground under the walker (1 m grid), buildings and fences, north up,
// 70 x 45 m round the walker
let siteMini = null;
function prepareSiteMinimap(map) {
  const s = 3; // px per metre on the prepared map
  const c = document.createElement('canvas');
  c.width = map.nx * s;
  c.height = map.ny * s;
  const g = c.getContext('2d');
  const ground = Uint8Array.from(atob(map.ground), (ch) => ch.charCodeAt(0));
  const img = g.createImageData(map.nx, map.ny);
  const rgb = Object.fromEntries(Object.entries(KINDS).map(([k, v]) => [k, new THREE.Color(v.c)]));
  for (let j = 0; j < map.ny; j++) {
    for (let i = 0; i < map.nx; i++) {
      const col = rgb[ground[j * map.nx + i]] ?? rgb[0], o = ((map.ny - 1 - j) * map.nx + i) * 4;
      img.data[o] = col.r * 255;
      img.data[o + 1] = col.g * 255;
      img.data[o + 2] = col.b * 255;
      img.data[o + 3] = 255;
    }
  }
  const small = document.createElement('canvas');
  small.width = map.nx;
  small.height = map.ny;
  small.getContext('2d').putImageData(img, 0, 0);
  g.imageSmoothingEnabled = false;
  g.drawImage(small, 0, 0, c.width, c.height);
  const P = (x, y) => [(x - map.x0) * s, (map.y0 + map.ny - y) * s];
  g.fillStyle = '#6f6862';
  for (const poly of map.solids) {
    g.beginPath();
    poly.forEach(([x, y], i) => (i ? g.lineTo(...P(x, y)) : g.moveTo(...P(x, y))));
    g.closePath();
    g.fill();
  }
  g.strokeStyle = '#2e4b3a';
  g.lineWidth = 1.2;
  for (const [, pts] of map.lines) {
    g.beginPath();
    pts.forEach(([x, y], i) => (i ? g.lineTo(...P(x, y)) : g.moveTo(...P(x, y))));
    g.stroke();
  }
  siteMini = { c, s, map };
  miniBg = null;
}
function drawSiteMinimap() {
  const dpr = Math.min(devicePixelRatio || 1, 2);
  const w = mini.clientWidth, h = mini.clientHeight;
  if (mini.width !== Math.round(w * dpr)) {
    mini.width = Math.round(w * dpr);
    mini.height = Math.round(h * dpr);
  }
  const { c, s, map } = siteMini;
  const g = mini.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  const st = walk.localState();
  const k = 2.2 / s; // px per map px
  const cx = (st.x - map.x0) * s, cy = (map.y0 + map.ny - st.y) * s;
  g.save();
  g.beginPath();
  g.roundRect?.(0, 0, w, h, 8);
  g.clip();
  g.drawImage(c, cx - w / 2 / k, cy - h / 2 / k, w / k, h / k, 0, 0, w, h);
  g.restore();
  const ang = Math.atan2(-st.dy, st.dx);
  g.fillStyle = 'rgba(200, 149, 90, 0.35)';
  g.beginPath();
  g.moveTo(w / 2, h / 2);
  g.arc(w / 2, h / 2, 28, ang - 0.6, ang + 0.6);
  g.closePath();
  g.fill();
  g.fillStyle = '#9a6a3c';
  g.strokeStyle = '#fff';
  g.lineWidth = 2;
  g.beginPath();
  g.arc(w / 2, h / 2, 5, 0, Math.PI * 2);
  g.fill();
  g.stroke();
}
function drawMinimap() {
  if (walkInterior?.outdoor && siteMini && walk.enabled) return drawSiteMinimap();
  if (!miniBg || !walk.enabled) return;
  const dpr = Math.min(devicePixelRatio || 1, 2);
  const w = mini.clientWidth, h = mini.clientHeight;
  if (mini.width !== Math.round(w * dpr)) {
    mini.width = Math.round(w * dpr);
    mini.height = Math.round(h * dpr);
  }
  const g = mini.getContext('2d');
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.clearRect(0, 0, mini.width, mini.height);
  g.drawImage(miniBg, 0, 0);
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const s = walk.localState();
  const x = miniT.px(s.x), y = miniT.py(s.y);
  const ang = Math.atan2(-s.dy, s.dx);
  g.fillStyle = 'rgba(200, 149, 90, 0.3)';
  g.beginPath();
  g.moveTo(x, y);
  g.arc(x, y, 30, ang - 0.6, ang + 0.6);
  g.closePath();
  g.fill();
  g.fillStyle = '#9a6a3c';
  g.strokeStyle = '#fff';
  g.lineWidth = 2;
  g.beginPath();
  g.arc(x, y, 5, 0, Math.PI * 2);
  g.fill();
  g.stroke();
}

// ---------- joystick (touch screens) ----------
const joy = $('#joystick'), knob = joy.querySelector('.knob');
let joyId = null;
const joyMove = (e) => {
  const r = joy.getBoundingClientRect();
  let dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2);
  const max = r.width / 2 - 10, d = Math.hypot(dx, dy);
  if (d > max) { dx *= max / d; dy *= max / d; }
  knob.style.transform = `translate(${dx}px, ${dy}px)`;
  walk.setJoystick(dx / max, dy / max);
};
joy.addEventListener('pointerdown', (e) => { joyId = e.pointerId; joy.setPointerCapture(joyId); joyMove(e); });
joy.addEventListener('pointermove', (e) => e.pointerId === joyId && joyMove(e));
const joyEnd = () => { joyId = null; knob.style.transform = ''; walk.setJoystick(0, 0); };
joy.addEventListener('pointerup', joyEnd);
joy.addEventListener('pointercancel', joyEnd);
addEventListener('pointerdown', (e) => {
  lastInteraction = performance.now();
  if (e.pointerType === 'touch') document.body.classList.add('touch');
});
addEventListener('wheel', () => (lastInteraction = performance.now()), { passive: true });

// ---------- picking ----------
const ray = new THREE.Raycaster();
const ndc = new THREE.Vector2();
const tooltip = $('#tooltip');
// What is under the pointer: { apt } (a flat of a block for sale), { block } (a neighbour block), or null.
function pick(e) {
  if (!building) return null;
  ndc.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
  ray.setFromCamera(ndc, camera);
  const hidden = (o) => {
    const a = o.userData.apt;
    return state.mode === 'floor' && a && a.tower === state.tower && a.floor > state.floor;
  };
  const hits = ray.intersectObjects([...building.pickables.filter((o) => !hidden(o)), ...blockPicks], false);
  for (const h of hits) {
    const d = h.object.userData;
    if (d.apt) return d;
    if (d.block && !towerByKey[d.block].sales) return d;
  }
  return null;
}
let down = null;
canvas.addEventListener('pointerdown', (e) => (down = { x: e.clientX, y: e.clientY }));
canvas.addEventListener('pointermove', (e) => {
  if (state.mode === 'walk' || e.pointerType === 'touch') return;
  if (e.buttons) {
    tooltip.style.opacity = 0;
    return;
  }
  const hit = pick(e);
  const a = hit?.apt ?? null;
  const floorHover = a && (state.mode !== 'floor' || !isOpen(a)) ? { tower: a.tower, floor: a.floor } : null;
  const changed = JSON.stringify(floorHover) !== JSON.stringify(state.hoverFloor);
  state.hoverFloor = floorHover;
  if (changed) {
    renderFloors();
    updateOverlays();
  }
  setHover(a);
  canvas.style.cursor = a || hit?.block ? 'pointer' : '';
  const place = () => {
    tooltip.style.left = `${e.clientX + 16}px`;
    tooltip.style.top = `${e.clientY + 12}px`;
    tooltip.style.opacity = 1;
  };
  const T = L();
  if (a && (state.mode !== 'floor' || !isOpen(a))) {
    const list = aptsOnFloor(a.tower, a.floor);
    const n = filterActive() ? list.filter(matches).length : list.length;
    tooltip.innerHTML = T.tipFloor(a.letter, a.floor, T.flats(n));
    place();
  } else if (hit?.block) {
    tooltip.innerHTML = T.tipNeighbour(LETTER[hit.block]);
    place();
  } else tooltip.style.opacity = 0;
});
canvas.addEventListener('pointerleave', () => {
  tooltip.style.opacity = 0;
  if (state.mode !== 'walk') {
    setHover(null);
    state.hoverFloor = null;
    updateOverlays();
  }
});
canvas.addEventListener('pointerup', (e) => {
  if (state.mode === 'walk' || !down) return;
  const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y) > 6;
  down = null;
  if (moved) return;
  const hit = pick(e);
  if (!hit) return;
  tooltip.style.opacity = 0;
  if (hit.block) {
    toast(L().neighbourBlock);
    return;
  }
  const a = hit.apt;
  if (state.mode === 'floor' && isOpen(a)) selectApt(a);
  else selectFloor(a.tower, a.floor);
});

// The side panels cover the edges of a wide screen: the camera's centre moves into the free space
// between them, so what it looks at (a block, the open floor) shows in the middle of what is seen
// and the tags at its ends stay clear of the panels.
function frameCentre() {
  const W = innerWidth, H = innerHeight;
  let dx = 0;
  if (state.mode !== 'walk' && W > 760) {
    const l = $('#floors').getBoundingClientRect().right, r = $('#side').getBoundingClientRect().left;
    if (r - l > 240) dx = Math.round(W / 2 - (l + r) / 2);
  }
  if (dx) camera.setViewOffset(W, H, dx, 0, W, H);
  else camera.clearViewOffset();
}

// ---------- loop ----------
addEventListener('resize', () => {
  if (!$('#plan-big').hidden && state.apt) openPlan(state.apt);
  camera.aspect = innerWidth / innerHeight;
  frameCentre();
  camera.updateProjectionMatrix();
  pipeline.setSize(innerWidth, innerHeight);
});

const clock = new THREE.Clock();
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
renderer.info.autoReset = false;
renderer.setAnimationLoop(() => {
  renderer.info.reset();
  const dt = Math.min(clock.getDelta(), 0.05);
  if (tween) {
    tween.t += dt;
    const k = ease(Math.min(1, tween.t / tween.dur));
    camera.position.lerpVectors(tween.p0, tween.p1, k);
    controls.target.lerpVectors(tween.t0, tween.t1, k);
    if (k >= 1) {
      tween = null;
      controls.enabled = true;
    }
  }
  if (state.mode === 'walk') {
    walk.update(dt);
    followSun();
    drawMinimap();
  } else {
    controls.autoRotate = state.mode === 'overview' && performance.now() - lastInteraction > 25000;
    if (!tween) controls.update();
    else camera.lookAt(controls.target);
    if (building) updateLabels();
    updatePlaces();
  }
  for (const n of water) n.offset.x += dt * 0.006, n.offset.y += dt * 0.004;
  if (grass) {
    WIND.t.value += dt;
    grass.update(camera);
  }
  ROOM_LIGHT.value = !daytime ? 0 : state.mode !== 'walk' ? daytime.state.lights * 0.55 : walkInterior?.outdoor ? 0 : daytime.state.lights * 0.38;
  updateCars(camera);
  if (shadowFrames > 0) {
    renderer.shadowMap.needsUpdate = true;
    shadowFrames--;
  }
  pipeline.render(dt);
});

buildPlaces();
refresh();
frameCentre();
camera.updateProjectionMatrix();
const STILL = new URLSearchParams(location.search).has('still');
lastInteraction = STILL ? Infinity : performance.now();

// handles for the automated checks in tools/ (screenshots, picking and walk tests)
window.__app = {
  THREE, scene, camera, controls, renderer, state, walk, apartments, pipeline, world, quality: Q,
  get building() { return building; },
  get interior() { return walkInterior; },
  selectBlock, selectFloor, selectApt, enterWalk, exitWalk, goOverview, enterSiteWalk,
  get daytime() { return daytime; },
  get flowers() { return flowers; },
  get grass() { return grass; },
  get hqDone() { return hqDone; },
  film: { WIND, driveCars, setDrivers, updateCars, shadowsDirty: () => shadowsDirty() },
  setHours: (h) => setHours(h),
  setClean: (on) => setClean(on),
  setView(pos, target) {
    tween = null;
    camera.position.set(...pos);
    controls.target.set(...target);
    controls.update();
  },
};
