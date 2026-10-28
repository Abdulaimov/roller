// What the walk-through builds in a flat, in plan metres: collision lines, door leaves, furniture
// outlines, doorways (for tools/rp/compare.py, which draws them over the sheet).
//   node tools/ab/dump_walk.mjs OUT.json APT_ID [APT_ID ...]
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const [out, ...ids] = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 500 } });
await page.goto('http://localhost:5197/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const res = await page.evaluate(async (ids) => {
  const { buildFloor } = await import('/src/floor.js');
  const { aptsOnFloor, apartments } = await import('/src/data.js');
  const res = {};
  for (const id of ids) {
    const a = apartments.find((x) => x.id === id);
    const it = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor), a);
    res[id] = { plan: a.plan, index: a.data.index ?? null, rooms: a.data.rooms.map((r) => ({ kind: r.kind, area: r.area, poly: r.poly })),
      obstacles: it.obstacles, segments: it.segments, doorways: it.doorways.filter((d) => d.apt === a.id || d.apt === undefined), gaps: it.gaps.filter((g) => g.apt === a.id), notes: it.notes, reach: it.reach };
    it.dispose();
  }
  return res;
}, ids);
fs.writeFileSync(out, JSON.stringify(res));
console.log('written', Object.keys(res).join(' '));
await browser.close();
