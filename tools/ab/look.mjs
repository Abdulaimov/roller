// A walk-through shot of a flat from a plan point towards another (plan metres), at eye height.
//   node tools/ab/look.mjs APT_ID OUT.png SX SY TX TY [PITCH] [--num 214 --tower B]
// With --num the flat is found by its number (as shown on the site) in that block.
import { chromium } from 'playwright-core';

const args = process.argv.slice(2);
const opt = (k) => (args.includes(k) ? args[args.indexOf(k) + 1] : null);
const [id, out, sx, sy, tx, ty, pitch] = args;
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1500);
const res = await page.evaluate(async ([id, num, tower, sx, sy, tx, ty, pitch]) => {
  const app = window.__app;
  const a = num ? app.apartments.find((x) => x.number === +num && x.tower === tower) : app.apartments.find((x) => x.id === id);
  app.selectApt(a);
  app.enterWalk(a);
  await new Promise((r) => setTimeout(r, 1500));
  const it = app.interior;
  if (sx !== 'auto') {
    const s = it.frame.toScene(+sx, +sy), t = it.frame.toScene(+tx, +ty);
    app.walk.target = null;
    app.walk.pos.set(s.x, s.z);
    app.walk.yaw = Math.atan2(-(t.x - s.x), -(t.z - s.z));
    app.walk.pitch = +(pitch ?? 0);
  }
  await new Promise((r) => setTimeout(r, 900));
  return { id: a.id, rooms: a.data.rooms.map((r) => `${r.kind} ${r.area}`) };
}, [id, opt('--num'), opt('--tower'), sx, sy, tx, ty, pitch]);
await page.screenshot({ path: out });
console.log(JSON.stringify(res));
await browser.close();
