// Several walk-through shots of one flat in one go (see look.mjs for one): each view is a plan
// point to stand at and one to look at, at eye height, optionally pitched (radians, + up).
//   node tools/ab/looks.mjs APT_ID OUTDIR "SX,SY,TX,TY[,PITCH]" ...   → OUTDIR/APT_ID_<n>.png
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const [id, outDir, ...views] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 1200, height: 800 } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1500);
await page.evaluate(async (id) => {
  const app = window.__app;
  const a = app.apartments.find((x) => x.id === id);
  app.selectApt(a);
  app.enterWalk(a);
  await new Promise((r) => setTimeout(r, 1800));
}, id);
let n = 0;
for (const v of views) {
  const [sx, sy, tx, ty, pitch] = v.split(',').map(Number);
  await page.evaluate(([sx, sy, tx, ty, pitch]) => {
    const app = window.__app, it = app.interior;
    const s = it.frame.toScene(sx, sy), t = it.frame.toScene(tx, ty);
    app.walk.target = null;
    app.walk.pos.set(s.x, s.z);
    app.walk.yaw = Math.atan2(-(t.x - s.x), -(t.z - s.z));
    app.walk.pitch = pitch || 0;
  }, [sx, sy, tx, ty, pitch]);
  await page.waitForTimeout(700);
  const out = `${outDir}/${id}_${n++}.png`;
  await page.screenshot({ path: out });
  console.log('wrote', out, v);
}
await browser.close();
