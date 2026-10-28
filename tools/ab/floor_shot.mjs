// The cut-away floor view of a block, the camera over a plan point (plan metres of that floor's
// plan), to look at furniture, fittings and lifts as they are built.
//   node tools/ab/floor_shot.mjs TOWER FLOOR OUT.png [--at X,Y] [--span 12] [--tilt 35] [--yaw 0] [--ui]
// --tilt: degrees from straight down; --yaw: where the camera looks from (plan degrees); --ui keeps
// the panels and tags.
import { chromium } from 'playwright-core';

const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const [tower, floor, out] = args;
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: +(opt('--w', 1400)), height: +(opt('--h', 900)) } });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1500);
const res = await page.evaluate(async ([tower, floor, at, span, tilt, yaw, ui]) => {
  const app = window.__app;
  app.selectFloor(tower, +floor);
  await new Promise((r) => setTimeout(r, 1500));
  if (!ui) for (const id of ['ext-ui', 'places', 'tooltip', 'quality']) {
    const el = document.getElementById(id);
    if (el) el.style.visibility = 'hidden';
  }
  const cfg = await import('/src/config.js');
  const t = cfg.towerByKey[tower];
  const fr = cfg.planFrame(t);
  const fl = t.floors.find((f) => f.floor === +floor);
  const plan = cfg.PLANS[fl.plan];
  let [px, py] = at ? at.split(',').map(Number) : [0, 0];
  if (!at) {
    const xs = plan.enclosure.map((p) => p[0]), ys = plan.enclosure.map((p) => p[1]);
    [px, py] = [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
  }
  const c = fr.toScene(px, py);
  const y = fl.z + t.slab;
  const d = (+span / 2) / Math.tan((app.camera.fov * Math.PI) / 360);
  const tl = (+tilt * Math.PI) / 180, yw = (+yaw * Math.PI) / 180;
  // the look-from direction in plan, turned into the scene
  const dx = Math.cos(yw) * Math.sin(tl), dy = Math.sin(yw) * Math.sin(tl);
  const e = fr.toScene(px + dx, py + dy);
  const ex = e.x - c.x, ez = e.z - c.z;
  app.setView([c.x + ex * d + 0.001, y + d * Math.cos(tl), c.z + ez * d + 0.001], [c.x, y, c.z]);
  await new Promise((r) => setTimeout(r, 1200));
  return { plan: fl.plan, lifts: plan.lifts?.length ?? 0, tags: document.querySelectorAll('.tag.lift').length };
}, [tower, floor, opt('--at', null), opt('--span', 14), opt('--tilt', 35), opt('--yaw', -90), args.includes('--ui')]);
await page.screenshot({ path: out });
console.log(JSON.stringify(res), errors.length ? 'ERRORS: ' + errors.join(' | ') : 'no errors');
await browser.close();
