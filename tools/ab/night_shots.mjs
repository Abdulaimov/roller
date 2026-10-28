// The time of day tried: the complex at several hours (start view), the ground walk and a flat at
// night, the floor opened at night, and the eye (every panel away and back). Reports page errors.
//   node tools/ab/night_shots.mjs OUTDIR [--hours 15,18.5,20,22.5] [--w 1280 --h 800]
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const out = args[0];
const hours = opt('--hours', '15,18.5,20,22.5').split(',').map(Number);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: +opt('--w', 1280), height: +opt('--h', 800) } });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building && window.__app.daytime, null, { timeout: 180000 });
await page.waitForTimeout(1500);
const at = async (h, name) => {
  await page.evaluate((h) => window.__app.setHours(h), h);
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${out}/${name}.png` });
};
for (const h of hours) await at(h, `home_${String(h).replace('.', '_')}`);
// the eye: panels away, then back
await page.click('#eye');
await page.waitForTimeout(400);
const hidden = await page.evaluate(() => ['#ext-ui', '#daytime', '#labels', '#places'].map((s) => getComputedStyle(document.querySelector(s)).display));
await page.screenshot({ path: `${out}/clean.png` });
await page.click('#eye');
await page.waitForTimeout(400);
const shown = await page.evaluate(() => ['#ext-ui', '#daytime'].map((s) => getComputedStyle(document.querySelector(s)).display));
// a floor opened at night
await page.evaluate(() => window.__app.selectFloor && window.__app.selectBlock('B'));
await page.waitForTimeout(2500);
await page.evaluate(() => window.__app.selectFloor('B', 10));
await page.waitForTimeout(3500);
await page.screenshot({ path: `${out}/floor_night.png` });
// a flat at night
await page.evaluate(() => {
  const a = window.__app.apartments.find((x) => x.id === 'B10-4') ?? window.__app.apartments[0];
  window.__app.selectApt(a);
  window.__app.enterWalk(a);
});
await page.waitForTimeout(3000);
await page.screenshot({ path: `${out}/flat_night.png` });
await page.evaluate(() => { window.__app.walk.yaw += Math.PI; });
await page.waitForTimeout(600);
await page.screenshot({ path: `${out}/flat_night2.png` });
await page.evaluate(() => window.__app.exitWalk());
await page.waitForTimeout(1500);
await page.evaluate(() => window.__app.goOverview());
await page.waitForTimeout(1500);
// the ground at night
await page.evaluate(() => window.__app.enterSiteWalk(null));
await page.waitForFunction(() => window.__app.interior?.outdoor, null, { timeout: 30000 });
await page.waitForTimeout(2500);
await page.screenshot({ path: `${out}/site_night.png` });
await page.evaluate(() => { window.__app.walk.yaw += Math.PI * 0.75; window.__app.walk.pitch = 0.25; });
await page.waitForTimeout(800);
await page.screenshot({ path: `${out}/site_night2.png` });
await page.evaluate(() => window.__app.setHours(19.25));
await page.waitForTimeout(800);
await page.screenshot({ path: `${out}/site_dusk.png` });
await page.evaluate(() => window.__app.exitWalk());
await page.waitForTimeout(1500);
const st = await page.evaluate(() => ({ mode: window.__app.state.mode, hours: window.__app.daytime.hours, clock: document.querySelector('#daytime-clock').textContent }));
console.log(JSON.stringify({ hidden, shown, st, errors }));
await browser.close();
