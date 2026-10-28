// Views of the shop signs for checking (the dev server on :5191 must be running):
//   node tools/ab/sign_shots.mjs <out dir> [name ...]
// Cameras in site metres (x east, y north, z up): [from x, y, z, to x, y, z, hours].
import { chromium } from 'playwright-core';
import fs from 'fs';

const VIEWS = {
  b_street: [-25, -98, 4, -30, -52, 10, 15],
  v_street: [58, -100, 4, 56, -58, 10, 15],
  g_street: [5, 48, 4, 32, 62, 10, 15],
  d_street: [121, 6, 4, 111, 25, 10, 15],
  a_north: [-112, 42, 5, -112, 7, 11, 15],
  a_south: [-72, -72, 5, -92, -44, 11, 15],
  b_yard: [-50, 4, 4, -38, -20, 9, 15],
  g_yard: [86, 70, 4, 64, 56, 9, 15],
  far_south: [-40, -240, 30, -10, -30, 25, 15],
  b_night: [-25, -98, 4, -30, -52, 10, 21.5],
  a_night: [-72, -72, 5, -92, -44, 11, 21.5],
};
const [out, ...names] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
page.on('console', (m) => m.type() === 'warning' && /sign/.test(m.text()) && console.log(m.text()));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building && window.__app.scene.getObjectByName('signs'), null, { timeout: 180000 });
await page.waitForTimeout(2000);
for (const name of names.length ? names : Object.keys(VIEWS)) {
  const v = VIEWS[name];
  await page.evaluate(async (v) => {
    const app = window.__app;
    for (const id of ['ext-ui', 'labels', 'places', 'tooltip', 'quality', 'hint', 'daytime', 'eye']) {
      const el = document.getElementById(id);
      if (el) el.style.visibility = 'hidden';
    }
    app.setHours?.(v[6]);
    const cfg = await import('/src/config.js');
    const a = cfg.toScene(v[0], v[1]), b = cfg.toScene(v[3], v[4]);
    app.camera.clearViewOffset();
    app.setView([a.x, v[2], a.z], [b.x, v[5], b.z]);
    await new Promise((r) => setTimeout(r, 2500));
  }, v);
  await page.screenshot({ path: `${out}/${name}.png` });
  console.log('wrote', `${out}/${name}.png`);
}
await browser.close();
