// Screenshot of the floor view with the pointer over one flat (the hover highlight).
//   node tools/hover_shot.mjs TOWER FLOOR UNIT OUT.png [overview]
import { chromium } from 'playwright-core';
const [tower, floor, unit, out, mode] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`, headless: true, args: ['--use-angle=metal'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:5191/');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(2500);
const id = `${tower}${floor}-${unit}`;
if (mode === 'overview') await page.evaluate((t) => window.__app.selectBlock(t), tower);
else await page.evaluate(([t, f]) => window.__app.selectFloor(t, +f), [tower, floor]);
await page.waitForTimeout(3500);
const p = await page.evaluate((id) => {
  const u = window.__app.building.units.get(id);
  const v = u.center.clone();
  v.y += 1.2;
  v.project(window.__app.camera);
  return [((v.x + 1) / 2) * innerWidth, ((1 - v.y) / 2) * innerHeight];
}, id);
await page.mouse.move(p[0] - 30, p[1] - 30);
await page.mouse.move(p[0], p[1], { steps: 5 });
await page.waitForTimeout(1200);
await page.screenshot({ path: out });
console.log(id, p, await page.evaluate(() => window.__app.state.hoverApt?.id));
await browser.close();
