// Where the shop signs can go, read off the built model (the dev server on :5191 must be running):
//   - every white stone portal of blocks Б, В, Г, Д (the top of its head at 10.2 m, blender/ab/podium.py
//     shop_front), street and yard faces alike (model/complex.json `shops` has the street ones only)
//   - the outer edge of block A podium's upper white band (glass_front: 11.1-12.45 m)
//   node tools/ab/shopfronts.mjs build/shopfronts.json      (then tools/ab/py tools/ab/place_signs.py)
import { chromium } from 'playwright-core';
import fs from 'fs';

const out = process.argv[2] ?? 'build/shopfronts.json';
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 600 } });
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const res = await page.evaluate(() => {
  const portals = {}, band = [];
  const V = (o, p, i) => new __app.THREE.Vector3().fromBufferAttribute(p, i).applyMatrix4(o.matrixWorld);
  __app.scene.traverse((o) => {
    if (!o.isMesh) return;
    const m = /^([ABVGD])_shops_\d+$/.exec(o.name);
    if (!m) return;
    o.updateMatrixWorld(true);
    const p = o.geometry.attributes.position, idx = o.geometry.index;
    if (m[1] !== 'A' && o.material.name === 'Stone white') {
      // the faces lying flat at 10.2 m: portal heads and jamb tops (scene x, z)
      for (let t = 0; t < idx.count; t += 3) {
        const v = [0, 1, 2].map((k) => V(o, p, idx.getX(t + k)));
        if (v.every((q) => Math.abs(q.y - 10.2) < 0.01)) (portals[m[1]] ??= []).push(v.map((q) => [+q.x.toFixed(3), +q.z.toFixed(3)]));
      }
    }
    if (m[1] === 'A' && o.material.name === 'White band') {
      const seen = new Set();
      for (let i = 0; i < p.count; i++) {
        const q = V(o, p, i);
        const k = `${q.x.toFixed(2)},${q.z.toFixed(2)}`;
        if (Math.abs(q.y - 12.45) < 0.02 && !seen.has(k)) seen.add(k), band.push([+q.x.toFixed(3), +q.z.toFixed(3)]);
      }
    }
  });
  return { portals, band };
});
fs.writeFileSync(out, JSON.stringify(res));
console.log(out, Object.fromEntries(Object.entries(res.portals).map(([k, v]) => [k, v.length / 6])), 'band points', res.band.length);
await browser.close();
