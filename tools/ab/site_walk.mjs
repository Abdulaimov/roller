// The walk on the ground round the complex, tried as a visitor would: starts it (from the courtyard
// entrance or at a block), looks round, walks with the keys for a while in several directions and
// reports where the walker ended (never in a building, never off the ground), takes pictures.
//   node tools/ab/site_walk.mjs OUTDIR [--from B] [--w 1280 --h 800]
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const out = args[0];
const from = opt('--from', null);
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
await page.waitForFunction(() => window.__app?.building, null, { timeout: 180000 });
await page.waitForTimeout(1500);
await page.evaluate((from) => window.__app.enterSiteWalk(from), from);
await page.waitForFunction(() => window.__app.state.mode === 'walk' && window.__app.interior?.outdoor, null, { timeout: 30000 });
await page.waitForTimeout(2500);
const tag = from ?? 'entry';
await page.screenshot({ path: `${out}/${tag}_0_start.png` });
// look round: four quarter turns
for (let i = 1; i <= 3; i++) {
  await page.evaluate(() => { window.__app.walk.yaw += Math.PI / 2; });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${out}/${tag}_${i}_turn.png` });
}
await page.evaluate(() => { window.__app.walk.yaw += Math.PI / 2; });
// walk: hold W for a while, then turn and walk on (the walker slides along walls, never through)
const report = [];
for (const [turn, secs] of [[0, 6], [0.9, 5], [-1.8, 6], [1.2, 8]]) {
  await page.evaluate((t) => { window.__app.walk.yaw += t; }, turn);
  await page.keyboard.down('KeyW');
  await page.waitForTimeout(secs * 1000);
  await page.keyboard.up('KeyW');
  await page.waitForTimeout(400);
  const st = await page.evaluate(() => {
    const it = window.__app.interior, p = window.__app.walk.pos;
    const q = it.frame.toPlan(p.x, p.y);
    return { x: +q.x.toFixed(2), y: +q.y.toFixed(2), kind: it.kindAt(q.x, q.y), eye: +window.__app.camera.position.y.toFixed(2) };
  });
  report.push(st);
  await page.screenshot({ path: `${out}/${tag}_walk_${report.length}.png` });
}
// click on the ground ahead to walk there
const click = await page.evaluate(async () => {
  const app = window.__app;
  const before = app.walk.pos.clone();
  const r = app.renderer.domElement.getBoundingClientRect();
  const ev = (type, x, y) => app.renderer.domElement.dispatchEvent(new PointerEvent(type, { clientX: x, clientY: y, pointerId: 1, bubbles: true, pointerType: 'mouse' }));
  const x = r.left + r.width / 2, y = r.top + r.height * 0.72;
  ev('pointerdown', x, y);
  ev('pointerup', x, y);
  const target = app.walk.target ? { x: +app.walk.target.x.toFixed(2), z: +app.walk.target.y.toFixed(2) } : null;
  await new Promise((res) => setTimeout(res, 3500));
  return { target, moved: +before.distanceTo(app.walk.pos).toFixed(2) };
});
await page.screenshot({ path: `${out}/${tag}_click.png` });
// clicks all over the grounds: from a random spot to another, the way found and walked to the end
// (the walker steps as the site does, 30 times a second, sliding along whatever is in the way)
const trips = await page.evaluate(() => {
  const app = window.__app, it = app.interior, w = app.walk, m = it.map;
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const spot = () => {
    for (;;) {
      const x = m.x0 + rnd() * m.nx, y = m.y0 + rnd() * m.ny;
      if (it.canStand(x, -y)) return [x, -y];
    }
  };
  const res = [];
  for (let n = 0; n < 60; n++) {
    const [ax, az] = spot(), [bx, bz] = spot();
    w.pos.set(ax, az);
    const t0 = performance.now();
    const way = it.route(ax, az, bx, bz);
    const ms = performance.now() - t0;
    if (!way) {
      res.push({ a: [ax, -az].map(Math.round), b: [bx, -bz].map(Math.round), way: null, ms: Math.round(ms) });
      continue;
    }
    w.path = way;
    w.target = w.path.shift();
    w.stuck = 0;
    let steps = 0;
    while (w.target && steps < 30 * 400) (w.update(1 / 30), steps++);
    const left = Math.hypot(w.pos.x - bx, w.pos.y - bz);
    res.push({ a: [ax, -az].map(Math.round), b: [bx, -bz].map(Math.round), legs: way.length + 1, ms: Math.round(ms), secs: Math.round(steps / 30), left: +left.toFixed(2) });
  }
  return res;
});
const missed = trips.filter((t) => t.way === null || t.left > 2.5);
console.log('trips', trips.length, 'not reached', missed.length, 'slowest route ms', Math.max(...trips.map((t) => t.ms)));
for (const t of missed) console.log('  ', JSON.stringify(t));
console.log(JSON.stringify({ from: tag, report, click, errors }));
await page.evaluate(() => window.__app.exitWalk());
await page.waitForTimeout(1500);
const mode = await page.evaluate(() => window.__app.state.mode);
console.log('after exit:', mode);
await browser.close();
