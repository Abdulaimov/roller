// The apartment card (plan and details) of one flat, as the buyer sees it.
//   node tools/ab/card_shot.mjs APT_ID OUT.png [--lang tj]
import { chromium } from 'playwright-core';
import CHROME from './chrome.mjs';
const args = process.argv.slice(2);
const [id, out] = args;
const lang = args.includes('--lang') ? args[args.indexOf('--lang') + 1] : 'ru';
const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
await page.goto(`http://localhost:5197/?still&lang=${lang}`);
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
