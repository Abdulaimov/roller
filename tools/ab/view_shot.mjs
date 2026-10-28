import { chromium } from 'playwright-core';
const [out, px, py, pz, tx, ty, tz] = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 860 } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1500);
await page.evaluate(async (v) => {
  const app = window.__app;
  for (const id of ['ext-ui', 'labels', 'places', 'tooltip', 'quality', 'hint']) { const el = document.getElementById(id); if (el) el.style.visibility = 'hidden'; }
  const cfg = await import('/src/config.js');
  const a = cfg.toScene(v[0], v[1]), b = cfg.toScene(v[3], v[4]);
  app.camera.clearViewOffset();
  app.setView([a.x, v[2], a.z], [b.x, v[5], b.z]);
  await new Promise((r) => setTimeout(r, 2500));
}, [px, py, pz, tx, ty, tz].map(Number));
await page.screenshot({ path: out });
console.log('wrote', out);
await browser.close();
