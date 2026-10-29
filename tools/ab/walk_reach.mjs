// Every layout walked through: the rooms of the flat the visitor cannot walk into from its front
// door (with the doors and the furniture as built). None should be listed but the small service
// loggias the sheets close off.
//   node tools/ab/walk_reach.mjs [APT_ID ...]
import { chromium } from 'playwright-core';
import CHROME from './chrome.mjs';

const ids = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 500 } });
await page.goto('http://localhost:5197/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const out = await page.evaluate(async (ids) => {
  const { buildFloor } = await import('/src/floor.js');
  const { aptsOnFloor, apartments } = await import('/src/data.js');
  let list = ids.length ? ids.map((id) => apartments.find((a) => a.id === id)) : [];
  if (!ids.length) {
    const seen = new Set();
    for (const a of apartments) {
      const k = `${a.plan}:${a.data.outline[0].join(',')}`;
      if (!seen.has(k)) seen.add(k), list.push(a);
    }
  }
  const res = [];
  for (const a of list) {
    const it = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor), a);
    const lost = a.data.rooms.map((r, i) => [r, i]).filter(([r, i]) => !it.reach.after.includes(i) && !(r.kind === 'loggia' && r.area <= 2.6))
      .map(([r]) => `${r.kind} ${r.area}`);
    res.push({ id: a.id, plan: a.plan, lost, front: it.reach.door });
    it.dispose();
  }
  return res;
}, ids);
let bad = 0;
for (const r of out) if (r.lost.length || !r.front) { bad++; console.log(`${r.id} ${r.plan}: ${r.front ? '' : 'NO FRONT DOOR; '}${r.lost.join(', ')}`); }
console.log(`${out.length} layouts, ${bad} with rooms the visitor cannot walk into`);
await browser.close();
process.exit(bad ? 1 : 0);
