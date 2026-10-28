// Bedrooms, living rooms and kitchens that end up with no furniture at all, in every layout as the
// walk-through builds it (drawn pieces or the viewer's own): none should be listed.
//   node tools/ab/empty_rooms.mjs [APT_ID ...]
import { chromium } from 'playwright-core';

const ids = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 500 } });
await page.goto('http://localhost:5197/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const out = await page.evaluate(async (ids) => {
  const { buildFloor } = await import('/src/floor.js');
  const { aptsOnFloor, apartments } = await import('/src/data.js');
  const { inside } = await import('/src/geometry.js');
  let list = ids.length ? ids.map((id) => apartments.find((a) => a.id === id)) : [];
  if (!ids.length) {
    const seen = new Set();
    for (const a of apartments) {
      const k = `${a.plan}:${a.data.outline[0].join(',')}`;
      if (!seen.has(k)) seen.add(k), list.push(a);
    }
  }
  const res = { layouts: list.length, rooms: 0, empty: [] };
  for (const a of list) {
    // (the cut-away view: every piece keeps its collision outline, which the walk may give up)
    const it = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor), null);
    for (const r of a.data.rooms) {
      if (!['bedroom', 'living', 'kitchen'].includes(r.kind)) continue;
      res.rooms++;
      const n = it.obstacles.filter((o) => o.what && !/door/.test(o.what) && o.poly.length >= 3 &&
        inside(r.poly, o.poly.reduce((s, p) => s + p[0], 0) / o.poly.length, o.poly.reduce((s, p) => s + p[1], 0) / o.poly.length)).length;
      if (!n) res.empty.push(`${a.id} ${a.plan} ${r.kind} ${r.area} m²`);
    }
    it.dispose();
  }
  return res;
}, ids);
for (const e of out.empty) console.log('EMPTY', e);
console.log(`${out.layouts} layouts, ${out.rooms} bedrooms, living rooms and kitchens, ${out.empty.length} empty`);
await browser.close();
process.exit(out.empty.length ? 1 : 0);
