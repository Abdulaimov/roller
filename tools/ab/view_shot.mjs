import { chromium } from 'playwright-core';
import CHROME from './chrome.mjs';
// node tools/ab/view_shot.mjs OUT px py pz tx ty tz [hour] - camera at site (px, py), height pz, looking at (tx, ty, tz)
const [out, px, py, pz, tx, ty, tz, hour] = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 860 } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('http://localhost:5197/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1500);
await page.evaluate(async (v) => {
  const app = window.__app;
  for (const id of ['ext-ui', 'labels', 'places', 'tooltip', 'quality', 'hint']) { const el = document.getElementById(id); if (el) el.style.visibility = 'hidden'; }
  const cfg = await import('/src/config.js');
  const a = cfg.toScene(v[0], v[1]), b = cfg.toScene(v[3], v[4]);
  app.camera.clearViewOffset();
  app.setView([a.x, v[2], a.z], [b.x, v[5], b.z]);
  if (v[6]) app.setHours(v[6]);
  await new Promise((r) => setTimeout(r, 2500));
}, [px, py, pz, tx, ty, tz, hour ?? 0].map(Number));
await page.screenshot({ path: out });
console.log('wrote', out);
await browser.close();
