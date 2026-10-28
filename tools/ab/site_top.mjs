// The site straight from above in the viewer (no panels), for laying over the genplan.
//   node tools/ab/site_top.mjs OUT.png [--cx 0 --cy 0 --span 360]   (site metres: centre and width)
import { chromium } from 'playwright-core';
const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? +args[args.indexOf(k) + 1] : d);
const out = args[0];
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1500);
await page.evaluate(async ([cx, cy, span]) => {
  const app = window.__app;
  for (const id of ['ext-ui', 'labels', 'places', 'tooltip', 'quality', 'hint']) {
    const el = document.getElementById(id);
    if (el) el.style.visibility = 'hidden';
  }
  app.state.mode = 'walk'; // (no view offset for the panels)
  const cam = app.camera;
  cam.clearViewOffset();
  cam.fov = 20;
  cam.updateProjectionMatrix();
  const h = span / 2 / Math.tan((cam.fov * Math.PI) / 360) / (innerWidth / innerHeight);
  const cfg = await import('/src/config.js');
  const c = cfg.toScene(cx, cy);
  // (a hair to the south of straight above: north is up in the picture)
  app.setView([c.x, h, c.z + h * 0.002], [c.x, 0, c.z]);
  app.state.mode = 'overview';
  await new Promise((r) => setTimeout(r, 2500));
}, [opt('--cx', 0), opt('--cy', 0), opt('--span', 360)]);
await page.screenshot({ path: out });
console.log('wrote', out);
await browser.close();
