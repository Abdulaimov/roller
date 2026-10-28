// Top-down picture of a flat in the cut-away floor view, furnished as for the walk-through.
//   node tools/ab/flat_top.mjs OUT.png APT_ID [APT_ID...]
import { chromium } from 'playwright-core';
const [out, ...ids] = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 900, height: 900 } });
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1500);
let i = 0;
for (const id of ids) {
  await page.evaluate(async (id) => {
    const app = window.__app;
    for (const elId of ['ext-ui', 'labels', 'places', 'tooltip', 'quality']) document.getElementById(elId).style.visibility = 'hidden';
    const a = app.apartments.find((x) => x.id === id);
    app.selectFloor(a.tower, a.floor);
    await new Promise((r) => setTimeout(r, 1500));
    const c = app.building.units.get(a.id).center;
    app.setView([c.x + 0.01, c.y + 22, c.z + 0.01], [c.x, c.y, c.z]);
  }, id);
  await page.waitForTimeout(900);
  await page.screenshot({ path: out.replace('.png', `_${i++}.png`) });
}
await browser.close();
