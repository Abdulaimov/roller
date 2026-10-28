// What the interior fitting left out, per flat (rooms left empty to keep the way through).
//   node tools/ab/notes.mjs [ids...]
import { chromium } from 'playwright-core';
const ids = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 500 } });
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const out = await page.evaluate(async (ids) => {
  const { buildFloor } = await import('/src/floor.js');
  const { aptsOnFloor, apartments } = await import('/src/data.js');
  const res = {};
  const list = ids.length ? ids : [...new Set(apartments.filter((a) => [5, 9, 10, 20].includes(a.floor)).map((a) => a.id))];
  for (const id of list) {
    const a = apartments.find((x) => x.id === id);
    if (!a) continue;
    const it = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor), a);
    if (it.notes.length) res[id] = it.notes;
    it.dispose();
  }
  return res;
}, ids);
console.log(JSON.stringify(out, null, 1));
await browser.close();
