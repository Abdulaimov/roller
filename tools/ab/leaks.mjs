// Holes in the flats' shells, seen from inside: for every room of every layout (or of one flat),
// renders the floor's interior alone on a magenta background, the glass made opaque, from a few
// points in the room at three heights in six directions. A magenta pixel is a place where the eye
// sees out between the pieces: a slit between walls, beside a window, under a wall or over a door.
//   node tools/ab/leaks.mjs [APT_ID ...] [--out DIR]   (no ids: one flat of every layout)
// The slab above and the open air over the parapets of loggias and terraces are stood in for by
// green pieces (the test sees only the floor's own interior).
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const args = process.argv.slice(2);
const outDir = args.includes('--out') ? args[args.indexOf('--out') + 1] : null;
const ids = args.filter((a, i) => !a.startsWith('--') && args[i - 1] !== '--out');
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 500 } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const res = await page.evaluate(async ({ ids, keep }) => {
  const { buildFloor } = await import('/src/floor.js');
  const { aptsOnFloor, apartments } = await import('/src/data.js');
  const { inside, distToPolygon, interiorPoint, bounds } = await import('/src/geometry.js');
  const { towerByKey, PLANS } = await import('/src/config.js');
  const { THREE, renderer } = window.__app;
  let list = ids.length ? ids.map((id) => apartments.find((a) => a.id === id)) : [];
  if (!ids.length) {
    // one flat of every layout: the first of each (plan, flat index)
    const seen = new Set();
    for (const a of apartments) {
      const key = `${a.plan}:${a.data.rooms.map((r) => r.area).join(',')}`;
      if (!seen.has(key)) seen.add(key), list.push(a);
    }
  }
  const S = 512;
  const rt = new THREE.WebGLRenderTarget(S, S);
  const cam = new THREE.PerspectiveCamera(90, 1, 0.01, 200);
  const buf = new Uint8Array(S * S * 4);
  const dirs = { E: [1, 0, 0], W: [-1, 0, 0], N: [0, 0, -1], S: [0, 0, 1], up: [0, 1, 0], down: [0, -1, 0] };
  const out = [];
  for (const a of list) {
    const it = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor), a);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(1, 0, 1);
    scene.add(it.group);
    it.group.traverse((o) => {
      if (!o.material) return;
      for (const m of [o.material].flat()) {
        m.transparent = false;
        m.opacity = 1;
        if ('transmission' in m) m.transmission = 0;
        m.alphaMap = null;
        m.alphaTest = 0;
        m.needsUpdate = true;
      }
    });
    // stand-ins for what is outside the floor's own pieces: the slab of the floor above (over the
    // open loggias and terraces too) and the open air over their parapets, in green
    const fl = towerByKey[a.tower].floors.find((f) => f.floor === a.floor);
    const H = fl.h - 0.5;
    const green = new THREE.MeshBasicMaterial({ color: 0x00ff00, side: THREE.DoubleSide });
    const eb = bounds(PLANS[a.plan].enclosure);
    const lid = new THREE.Mesh(new THREE.PlaneGeometry(eb.x1 - eb.x0 + 20, eb.y1 - eb.y0 + 20), green);
    lid.rotation.x = -Math.PI / 2;
    lid.position.set((eb.x0 + eb.x1) / 2, H + 0.01, -(eb.y0 + eb.y1) / 2);
    it.group.add(lid);
    for (const gp of it.gaps.filter((g) => g.done === 'parapet' || g.done === 'railing')) {
      const [[ax, ay], [bx, by]] = [gp.a, gp.b], z0 = 0.98, z1 = H + 0.02;
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute([ax, z0, -ay, bx, z0, -by, bx, z1, -by, ax, z0, -ay, bx, z1, -by, ax, z1, -ay], 3));
      it.group.add(new THREE.Mesh(geo, green));
    }
    // balconies and terraces outside the walls get their parapets from the building's own model:
    // their outer edges are stood in for too (the edges along the facade stay open to the test)
    const pl = PLANS[a.plan], onFloor = aptsOnFloor(a.tower, a.floor);
    const taken = [...pl.walls, ...pl.struct, ...pl.windows, ...pl.glazing, ...(pl.common ?? []), ...onFloor.flatMap((o) => o.data.rooms.map((r) => r.poly))];
    for (const o of onFloor) {
      for (const b of o.data.balconies) {
        const ccw = b.poly.reduce((s, p, i) => { const q = b.poly[(i + 1) % b.poly.length]; return s + p[0] * q[1] - q[0] * p[1]; }, 0) > 0;
        for (let i = 0, j = b.poly.length - 1; i < b.poly.length; j = i++) {
          const [[ax, ay], [bx, by]] = [b.poly[j], b.poly[i]];
          const L = Math.hypot(bx - ax, by - ay);
          if (L < 0.02) continue;
          // the outward side of the edge: beyond it, nothing of the floor (open air)
          const [nx, ny] = ccw ? [(by - ay) / L, -(bx - ax) / L] : [-(by - ay) / L, (bx - ax) / L];
          const q = [(ax + bx) / 2 + nx * 0.3, (ay + by) / 2 + ny * 0.3];
          if (taken.some((t) => inside(t, ...q))) continue;
          const z0 = 0, z1 = H + 0.02;
          const geo = new THREE.BufferGeometry();
          geo.setAttribute('position', new THREE.Float32BufferAttribute([ax, z0, -ay, bx, z0, -by, bx, z1, -by, ax, z0, -ay, bx, z1, -by, ax, z1, -ay], 3));
          it.group.add(new THREE.Mesh(geo, green));
        }
      }
    }
    it.group.updateMatrixWorld(true);
    // (balconies outside the flat are not walked on: seen from the rooms only)
    const rooms = a.data.rooms.map((r) => ({ r, kind: r.kind }));
    for (const { r, kind } of rooms) {
      // points: the middle of the room and the middles of its halves, 0.35 m clear of the walls
      const b = bounds(r.poly);
      const pts = [interiorPoint(r.poly)];
      for (const [fx, fy] of [[0.25, 0.5], [0.75, 0.5], [0.5, 0.25], [0.5, 0.75], [0.2, 0.2], [0.8, 0.8], [0.2, 0.8], [0.8, 0.2]]) {
        const p = [b.x0 + (b.x1 - b.x0) * fx, b.y0 + (b.y1 - b.y0) * fy];
        if (inside(r.poly, ...p) && -distToPolygon(r.poly, ...p) <= 0 && pts.every((q) => Math.hypot(q[0] - p[0], q[1] - p[1]) > 0.8)) {
          // (distToPolygon is 0 inside; check the clearance to the edges directly)
          let d = Infinity;
          for (let i = 0, j = r.poly.length - 1; i < r.poly.length; j = i++) {
            const [ax, ay] = r.poly[j], [bx, by] = r.poly[i];
            const L = (bx - ax) ** 2 + (by - ay) ** 2;
            const t = L ? Math.max(0, Math.min(1, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / L)) : 0;
            d = Math.min(d, Math.hypot(p[0] - ax - t * (bx - ax), p[1] - ay - t * (by - ay)));
          }
          if (d > 0.35) pts.push(p);
        }
      }
      for (const p of pts.slice(0, 5)) {
        for (const z of [0.12, 1.3, 2.62]) {
          const w = it.frame.toScene(p[0], p[1]);
          cam.position.set(w.x, it.baseY + z, w.z);
          for (const [dn, d] of Object.entries(dirs)) {
            if ((dn === 'down' && z > 1) || (dn === 'up' && z < 1)) continue;
            cam.up.set(...(dn === 'up' || dn === 'down' ? [0, 0, -1] : [0, 1, 0]));
            cam.lookAt(cam.position.x + d[0], cam.position.y + d[1], cam.position.z + d[2]);
            cam.updateMatrixWorld();
            renderer.setRenderTarget(rt);
            renderer.render(scene, cam);
            renderer.readRenderTargetPixels(rt, 0, 0, S, S, buf);
            // magenta pixels, except a hair's breadth beside a green stand-in (whose ends only
            // roughly meet the real corners)
            let n = 0;
            const green = (x, y) => x >= 0 && y >= 0 && x < S && y < S && buf[(y * S + x) * 4 + 1] > 200 && buf[(y * S + x) * 4] < 60;
            for (let i = 0; i < buf.length; i += 4) {
              if (!(buf[i] > 200 && buf[i + 1] < 60 && buf[i + 2] > 200)) continue;
              const x = (i / 4) % S, y = Math.floor(i / 4 / S);
              let near = false;
              for (let dy = -4; dy <= 4 && !near; dy++) for (let dx = -4; dx <= 4 && !near; dx++) near = green(x + dx, y + dy);
              if (!near) n++;
            }
            if (n > 2) {
              let png = null;
              if (keep) {
                const c = document.createElement('canvas');
                c.width = c.height = S;
                const g = c.getContext('2d'), img = g.createImageData(S, S);
                for (let y = 0; y < S; y++) img.data.set(buf.subarray((S - 1 - y) * S * 4, (S - y) * S * 4), y * S * 4);
                g.putImageData(img, 0, 0);
                png = c.toDataURL('image/png');
              }
              // (the plan point 2 m ahead, for tools/ab/look.mjs)
              const t = it.frame.toPlan(w.x + d[0] * 2, w.z + d[2] * 2);
              out.push({ id: a.id, number: a.number, room: `${r.name} ${r.area}`, kind, p: p.map((v) => +v.toFixed(2)), t: [+t.x.toFixed(2), +t.y.toFixed(2)], z, dir: dn, px: n, png });
            }
          }
        }
      }
    }
    renderer.setRenderTarget(null);
    it.dispose?.();
  }
  return { flats: list.length, hits: out };
}, { ids, keep: !!outDir });

const real = res.hits;
console.log(`flats ${res.flats}: views with a hole ${real.length}`);
const by = new Map();
for (const h of real) {
  const k = `${h.id} № ${h.number} · ${h.room}`;
  by.set(k, [...(by.get(k) ?? []), `${h.dir}@${h.z}(${h.px}px at ${h.p} → ${h.t})`]);
}
for (const [k, v] of by) console.log(' ', k, v.join(' '));
if (outDir) {
  fs.mkdirSync(outDir, { recursive: true });
  res.hits.forEach((h, i) => fs.writeFileSync(`${outDir}/${h.id}_${i}_${h.room.replace(/\W+/g, '_')}_${h.dir}_${h.z}.png`, Buffer.from(h.png.split(',')[1], 'base64')));
}
await browser.close();
process.exit(real.length ? 1 : 0);
