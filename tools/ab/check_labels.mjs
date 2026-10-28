// Room names and areas on the apartment card: for every flat (Russian and Tajik), lays out the
// labels on a canvas the size of the card and reports overlaps, labels off the plan and rooms
// left without a label.
//   node tools/ab/check_labels.mjs [--shots DIR]   (DIR: a picture of every unique layout)
import { chromium } from 'playwright-core';
import fs from 'node:fs';
const args = process.argv.slice(2);
const shots = args.includes('--shots') ? args[args.indexOf('--shots') + 1] : null;
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
let bad = 0;
for (const lang of ['ru', 'tj']) {
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`http://localhost:5191/?still&lang=${lang}`);
  await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
  const res = await page.evaluate(async () => {
    const { drawPlan } = await import('/src/plan.js');
    const out = [];
    const seen = new Set();
    for (const a of window.__app.apartments) {
      const c = document.createElement('canvas');
      c.style.cssText = 'width:304px;height:210px;position:fixed;left:0;top:0';
      document.body.appendChild(c);
      const T = drawPlan(c, a);
      const p = T.labels.placed;
      const overlaps = [];
      for (let i = 0; i < p.length; i++) {
        for (let j = i + 1; j < p.length; j++) {
          const [q, r] = [p[i], p[j]];
          if (q.x0 < r.x1 && q.x1 > r.x0 && q.y0 < r.y1 && q.y1 > r.y0) overlaps.push(`${q.room}/${r.room}`);
        }
      }
      const off = p.filter((q) => q.x0 < 0 || q.y0 < 0 || q.x1 > 304 || q.y1 > 210).map((q) => q.room);
      const key = `${a.plan}:${a.data.rooms.map((r) => r.area).join(',')}`;
      const first = !seen.has(key);
      seen.add(key);
      out.push({
        id: a.id, number: a.number, key, first, overlaps, off, skipped: T.labels.skipped,
        small: p.filter((q) => q.small).length, noArea: p.filter((q) => !q.area).map((q) => q.room), rot: p.filter((q) => q.rot).length,
        png: first ? c.toDataURL('image/png') : null,
      });
      c.remove();
    }
    return out;
  });
  const uniq = res.filter((r) => r.first);
  const sum = (f) => uniq.reduce((s, r) => s + f(r), 0);
  console.log(`[${lang}] layouts ${uniq.length} (flats ${res.length}): overlaps ${sum((r) => r.overlaps.length)}, off the plan ${sum((r) => r.off.length)}, unlabelled ${sum((r) => r.skipped.length)}, no area line ${sum((r) => r.noArea.length)}, 8 px ${sum((r) => r.small)}, turned ${sum((r) => r.rot)}`);
  for (const r of uniq) {
    if (r.overlaps.length || r.off.length) {
      bad++;
      console.log('  BAD', r.id, '№', r.number, r.overlaps.join(' '), r.off.length ? 'off: ' + r.off.join(' ') : '');
    }
    if (r.skipped.length || r.noArea.length) console.log('  note', r.id, '№', r.number, r.skipped.length ? 'unlabelled: ' + r.skipped.join(' ') : '', r.noArea.length ? 'no area: ' + r.noArea.join(' ') : '');
  }
  if (shots) {
    fs.mkdirSync(shots, { recursive: true });
    for (const r of uniq) fs.writeFileSync(`${shots}/${lang}_${r.id}.png`, Buffer.from(r.png.split(',')[1], 'base64'));
  }
  if (errors.length) console.log('page errors:', errors.join(' | '));
  await page.close();
}
await browser.close();
console.log(bad ? `${bad} layouts with problems` : 'all labels clear');
process.exit(bad ? 1 : 0);
