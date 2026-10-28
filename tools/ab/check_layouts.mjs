// Every layout (one flat of each kind on each plan) built for the walk-through: is every room that
// can be walked to without furniture still reachable from the start with it, does the walk start
// inside the flat at its entrance door, how many drawn pieces it has, and what was given up.
//   node tools/ab/check_layouts.mjs
import { chromium } from 'playwright-core';

const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 500 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const out = await page.evaluate(async () => {
  const { buildFloor } = await import('/src/floor.js');
  const { aptsOnFloor, apartments } = await import('/src/data.js');
  const { inside } = await import('/src/geometry.js');
  // one flat per layout: the plan's flat index, on the lowest floor that has that plan
  const seen = new Map();
  for (const a of apartments) {
    const k = `${a.plan}:${a.data.outline[0].join(',')}`;
    if (!seen.has(k)) seen.set(k, a);
  }
  const res = [];
  for (const a of seen.values()) {
    const it = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor), a);
    const r = it.reach;
    const lost = r.before.filter((i) => !r.after.includes(i)).map((i) => `${a.data.rooms[i].kind} ${a.data.rooms[i].area}`);
    const never = a.data.rooms.map((_, i) => i).filter((i) => !r.before.includes(i)).map((i) => `${a.data.rooms[i].kind} ${a.data.rooms[i].area}`);
    res.push({ id: a.id, plan: a.plan, pieces: (a.data.furniture ?? []).length, startIn: inside(a.data.outline, ...r.start), door: r.door, lost, never, notes: it.notes });
    it.dispose();
  }
  return res;
});
let bad = 0;
for (const r of out) {
  const ok = r.lost.length === 0 && r.startIn && r.door;
  if (!ok) bad++;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${r.id.padEnd(7)} ${r.plan.padEnd(6)} pieces ${String(r.pieces).padStart(2)}  start in flat ${r.startIn}, at the door ${r.door}` +
    (r.lost.length ? `  LOST: ${r.lost.join(', ')}` : '') + (r.never.length ? `  (no way in even empty: ${r.never.join(', ')})` : '') + (r.notes.length ? `  notes: ${r.notes.join('; ')}` : ''));
}
console.log(`${out.length} layouts, ${bad} failing`, errors.length ? `ERRORS: ${errors.join(' | ')}` : '');
await browser.close();
