// The apartment card (plan and details) of one flat, as the buyer sees it.
//   node tools/ab/card_shot.mjs APT_ID OUT.png [--lang tj]
import { chromium } from 'playwright-core';
const args = process.argv.slice(2);
const [id, out] = args;
const lang = args.includes('--lang') ? args[args.indexOf('--lang') + 1] : 'ru';
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
await page.goto(`http://localhost:5191/?still&lang=${lang}`);
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1000);
await page.evaluate(async (id) => {
  const app = window.__app;
  const a = app.apartments.find((x) => x.id === id);
  app.selectApt(a);
  await new Promise((r) => setTimeout(r, 2200));
}, id);
const side = await page.$('#side');
await (side ?? page).screenshot({ path: out });
console.log('wrote', out, errors.length ? 'ERRORS ' + errors.join(' | ') : '');
await browser.close();
