// The floor view as the site opens it (the site's own camera), with the panels and tags.
//   node tools/ab/floor_view.mjs TOWER FLOOR OUT.png [--w 1280 --h 720]
import { chromium } from 'playwright-core';
const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const [tower, floor, out] = args;
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: +opt('--w', 1280), height: +opt('--h', 720) } });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1000);
await page.evaluate(([t, f]) => window.__app.selectFloor(t, +f), [tower, floor]);
await page.waitForTimeout(2600);
await page.screenshot({ path: out });
console.log('wrote', out, errors.length ? 'ERRORS ' + errors.join(' | ') : '');
await browser.close();
