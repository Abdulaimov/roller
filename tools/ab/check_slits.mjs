// Slits in the flats' shells, seen from inside (23.10.2026: "a door not joined to its wall, gaps"):
// every flat of one floor of every plan (all positions, the mirrored ones too) built for the
// walk-through, the furniture hidden, the shell drawn as its distance from the eye. From a few points
// in each room, at two heights, in eight directions, the rows and columns of the picture are
// searched for a slit: a narrow band (a few millimetres to 7 cm wide where it is) much further away
// than both its sides - a gap beside a door frame, between a frame and its wall, between two walls,
// over a door, under a wall. Hits are grouped by where they are in the plan.
//   node tools/ab/check_slits.mjs [APT_ID ...] [--json OUT.json]
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const args = process.argv.slice(2);
const jsonOut = args.includes('--json') ? args[args.indexOf('--json') + 1] : null;
const ids = args.filter((a, i) => !a.startsWith('--') && args[i - 1] !== '--json');
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 500 } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const res = await page.evaluate(async ({ ids }) => {
  const { buildFloor } = await import('/src/floor.js');
  const { aptsOnFloor, apartments } = await import('/src/data.js');
  const { inside, interiorPoint, bounds } = await import('/src/geometry.js');
  const { interiorMaterials } = await import('/src/interior/materials.js');
  const { THREE, renderer } = window.__app;
  const M = interiorMaterials();
  // (the open leaves of the inner doors left out: the gap behind an open door, between it and the
  // wall it stands by, is how a door stands, not a slit)
  const SHELL = new Set(['floor', 'tileFloor', 'floorUnder', 'tileWall', 'wall', 'struct', 'ceiling', 'skirting', 'corridor', 'balcony', 'entrance', 'frame', 'sill', 'glass', 'frosted'].map((k) => M[k]).filter(Boolean));
  // every flat of the lowest floor of each plan
  let list;
  if (ids.length) list = ids.map((id) => apartments.find((a) => a.id === id));
  else {
    const first = new Map();
    for (const a of apartments) {
      const k = `${a.tower}:${a.plan}`;
      if (!first.has(k) || a.floor < first.get(k)) first.set(k, a.floor);
    }
    list = apartments.filter((a) => first.get(`${a.tower}:${a.plan}`) === a.floor);
  }
  const S = 384, f = S / 2; // 90 degrees: focal length in pixels
  const rt = new THREE.WebGLRenderTarget(S, S, { type: THREE.FloatType });
  const cam = new THREE.PerspectiveCamera(90, 1, 0.02, 100);
  const depthMat = new THREE.ShaderMaterial({
    side: THREE.DoubleSide,
    vertexShader: `varying float vD;
      void main() {
        vec4 p = vec4(position, 1.0);
        #ifdef USE_INSTANCING
          p = instanceMatrix * p;
        #endif
        vec4 mv = modelViewMatrix * p;
        vD = -mv.z;
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: 'varying float vD; void main() { gl_FragColor = vec4(vD, 0.0, 0.0, 1.0); }',
  });
  const buf = new Float32Array(S * S * 4);
  const hits = [];
  for (const a of list) {
    const it = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor), a);
    const scene = new THREE.Scene();
    scene.add(it.group);
    it.group.traverse((o) => {
      if (o.isMesh || o.isInstancedMesh) {
        const mats = [o.material].flat();
        o.visible = mats.some((m) => SHELL.has(m));
      } else if (o.isLight || o.isPoints || o.isLine || o.isSprite) o.visible = false;
    });
    scene.overrideMaterial = depthMat;
    it.group.updateMatrixWorld(true);
    for (const r of a.data.rooms) {
      const b = bounds(r.poly);
      const pts = [interiorPoint(r.poly)];
      for (const [fx, fy] of [[0.25, 0.5], [0.75, 0.5], [0.5, 0.25], [0.5, 0.75]]) {
        const p = [b.x0 + (b.x1 - b.x0) * fx, b.y0 + (b.y1 - b.y0) * fy];
        if (!inside(r.poly, ...p) || pts.some((q) => Math.hypot(q[0] - p[0], q[1] - p[1]) < 0.8)) continue;
        let d = Infinity;
        for (let i = 0, j = r.poly.length - 1; i < r.poly.length; j = i++) {
          const [ax, ay] = r.poly[j], [bx, by] = r.poly[i];
          const L = (bx - ax) ** 2 + (by - ay) ** 2;
          const t = L ? Math.max(0, Math.min(1, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / L)) : 0;
          d = Math.min(d, Math.hypot(p[0] - ax - t * (bx - ax), p[1] - ay - t * (by - ay)));
        }
        if (d > 0.4) pts.push(p);
      }
      for (const p of pts) {
        for (const z of [1.1, 2.15]) {
          const w = it.frame.toScene(p[0], p[1]);
          cam.position.set(w.x, it.baseY + z, w.z);
          for (let k = 0; k < 8; k++) {
            const ang = (k * Math.PI) / 4;
            cam.up.set(0, 1, 0);
            cam.lookAt(cam.position.x + Math.sin(ang), cam.position.y, cam.position.z - Math.cos(ang));
            cam.updateMatrixWorld();
            renderer.setRenderTarget(rt);
            renderer.setClearColor(0x000000, 0);
            renderer.clear();
            renderer.render(scene, cam);
            renderer.readRenderTargetPixels(rt, 0, 0, S, S, buf);
            const D = (x, y) => {
              const v = buf[(y * S + x) * 4];
              return v > 0 ? v : 1000; // nothing there: the open air
            };
            // a narrow band further than both sides: [start, end) along a line
            const scan = (len, get, emit) => {
              let x = 1;
              while (x < len - 1) {
                const l = get(x - 1), c = get(x);
                if (c - l < Math.max(0.08, 0.04 * l)) { x++; continue; }
                let e = x;
                while (e < len - 1 && get(e) - l >= Math.max(0.08, 0.04 * l)) e++;
                if (e >= len - 1) break;
                const rr = get(e), near = Math.max(l, rr), wpx = e - x;
                const width = (wpx * near) / f;
                if (get(x) - rr >= Math.max(0.08, 0.04 * rr) && width <= 0.07 && width >= 0.003 && near < 8) emit(x, e, near, width);
                x = e;
              }
            };
            const found = [];
            for (let y = 4; y < S - 4; y += 3) scan(S, (x) => D(x, y), (x0, x1, near, width) => found.push({ px: (x0 + x1) / 2, py: y, near, width, dir: 'v' }));
            for (let x = 4; x < S - 4; x += 3) scan(S, (y) => D(x, y), (y0, y1, near, width) => found.push({ px: x, py: (y0 + y1) / 2, near, width, dir: 'h' }));
            // a slit is a line: keep the finds with another one of the same kind 3 px away along it
            const keep = found.filter((h) => found.some((o) => o !== h && o.dir === h.dir && (h.dir === 'v' ? Math.abs(o.py - h.py) === 3 && Math.abs(o.px - h.px) <= 2 : Math.abs(o.px - h.px) === 3 && Math.abs(o.py - h.py) <= 2)));
            for (const h of keep) {
              // where it is: the near edge's point in the scene, then on the plan
              const ndc = new THREE.Vector3((h.px + 0.5) / S * 2 - 1, (h.py + 0.5) / S * 2 - 1, 0.5).unproject(cam);
              const dir = ndc.sub(cam.position).normalize();
              const fwd = new THREE.Vector3();
              cam.getWorldDirection(fwd);
              const q = cam.position.clone().addScaledVector(dir, h.near / dir.dot(fwd));
              const pl = it.frame.toPlan(q.x, q.z);
              hits.push({ id: a.id, number: a.number, room: `${r.kind} ${r.area}`, from: p.map((v) => +v.toFixed(2)), z, at: [+pl.x.toFixed(2), +pl.y.toFixed(2)], h: +(q.y - it.baseY).toFixed(2), width: +(h.width * 100).toFixed(1), kind: h.dir === 'v' ? 'vertical' : 'horizontal' });
            }
          }
        }
      }
    }
    renderer.setRenderTarget(null);
    it.dispose?.();
  }
  return { flats: list.length, ids: list.map((a) => a.id), hits };
}, { ids });

// group by flat and place (25 cm), the kind of slit
const groups = new Map();
for (const h of res.hits) {
  const k = `${h.id}|${Math.round(h.at[0] * 4) / 4},${Math.round(h.at[1] * 4) / 4}|${h.kind}`;
  const g = groups.get(k) ?? { ...h, n: 0, hs: [], widths: [], rooms: new Set() };
  g.n++;
  g.hs.push(h.h);
  g.widths.push(h.width);
  g.rooms.add(h.room);
  groups.set(k, g);
}
const list = [...groups.values()].filter((g) => g.n >= 3).sort((p, q) => p.id.localeCompare(q.id, 'en', { numeric: true }) || q.n - p.n);
console.log(`flats ${res.flats}; slits (seen 3+ times): ${list.length}`);
for (const g of list) {
  const hs = g.hs.sort((p, q) => p - q);
  console.log(`  ${g.id} № ${g.number} ${[...g.rooms].join(', ')}: ${g.kind} at ${g.at} h ${hs[0]}–${hs[hs.length - 1]} m, ${Math.min(...g.widths)}–${Math.max(...g.widths)} cm, seen ${g.n}x (from ${g.from} @${g.z})`);
}
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify(list.map((g) => ({ ...g, rooms: [...g.rooms] })), null, 1));
await browser.close();
