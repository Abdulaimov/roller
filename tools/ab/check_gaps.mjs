// The openings in the rooms' outlines that are no doorway, in every layout: slits between walls,
// stretches with nothing across (a hole to the outside), openings into another flat or the
// corridor, and wide openings between rooms of one flat (open plan, or a missing wall).
//   node tools/ab/check_gaps.mjs [--all]     (--all: list the open-plan connections too)
import { chromium } from 'playwright-core';

const all = process.argv.includes('--all');
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 500 } });
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const out = await page.evaluate(async () => {
  const { buildFloor } = await import('/src/floor.js');
  const { aptsOnFloor, apartments } = await import('/src/data.js');
  // every floor plan once (all its flats are built in the floor view)
  const seen = new Set(), res = [];
  for (const a of apartments) {
    if (seen.has(a.plan)) continue;
    seen.add(a.plan);
    const it = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor));
    res.push({ plan: a.plan, tower: a.tower, floor: a.floor, gaps: it.gaps });
    it.dispose();
  }
  return res;
});
for (const p of out) {
  const by = {};
  for (const g of p.gaps) (by[g.done] ??= []).push(g);
  console.log(`\n${p.plan} (${p.tower}${p.floor}): ${p.gaps.length} openings that are no doorway`);
  for (const [done, list] of Object.entries(by)) {
    const big = list.filter((g) => g.len >= 0.2);
    console.log(`  ${done}: ${list.length} (${big.length} of 20 cm or more)`);
    if (done === 'walled' && !all) continue;
    for (const g of big.slice(0, 60)) console.log(`     ${g.apt} ${g.room}${g.other ? ' -> ' + g.other : ''} [${g.across}]  len ${g.len} depth ${g.depth}  ${g.a} .. ${g.b}`);
  }
}
await browser.close();
