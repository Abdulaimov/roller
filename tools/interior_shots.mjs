// Screenshots inside one flat: one from a corner of each furnished room, looking across it.
//
//   npx vite --port 5173 &
//   node tools/interior_shots.mjs build/interior [--apt V12-7] [--url http://localhost:5191/] [--size 1600x1000]
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';

const args = process.argv.slice(2);
const out = args.find((a) => !a.startsWith('--') && !args[args.indexOf(a) - 1]?.startsWith('--')) ?? 'build/interior';
const opt = (k, d) => (args.includes(`--${k}`) ? args[args.indexOf(`--${k}`) + 1] : d);
const url = opt('url', 'http://localhost:5191/');
const aptIds = opt('apt', 'V12-7').split(',');
const [W, H] = opt('size', '1600x1000').split('x').map(Number);
const query = opt('query', '');
const only = opt('rooms', '').split(',').filter(Boolean); // e.g. --rooms bath,kitchen

mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true,
  args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('console', (m) => m.type() === 'error' && console.log('console:', m.text()));
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto(`${url}?still${query ? `&${query}` : ''}`);
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(2000);

for (const aptId of aptIds) {
  const rooms = await page.evaluate(async (id) => {
    const app = window.__app;
    const a = app.apartments.find((x) => x.id === id);
    if (app.state.mode === 'walk') app.exitWalk(), await new Promise((r) => setTimeout(r, 900));
    app.selectApt(a);
    app.enterWalk(a);
    await new Promise((r) => setTimeout(r, 1200));
    return a.data.rooms.map((r, i) => ({ i, kind: r.kind, area: r.area, wet: !!r._wet }));
  }, aptId);
  for (const room of rooms) {
    if (room.area < 3 && room.kind !== 'bath') continue;
    if (only.length && !only.includes(room.kind) && !(only.includes('bath') && room.wet)) continue;
    for (const corner of [0, 1]) {
      const ok = await page.evaluate(({ i, corner }) => {
        const app = window.__app, it = app.interior, r = it.apt.data.rooms[i];
        // the room's bounding box; stand 0.45 m in from one corner, look at the opposite one
        let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
        for (const [x, y] of r.poly) (x0 = Math.min(x0, x)), (y0 = Math.min(y0, y)), (x1 = Math.max(x1, x)), (y1 = Math.max(y1, y));
        let pts = corner ? [[x1 - 0.45, y0 + 0.45], [x0, y1]] : [[x0 + 0.45, y1 - 0.45], [x1, y0]];
        if (r.area < 10) {
          // small rooms: from the middle, towards one far corner and then the other
          const c = [(x0 + x1) / 2, (y0 + y1) / 2];
          pts = corner ? [c, [x0, y0]] : [c, [x1, y1]];
          const dx = pts[1][0] - c[0], dy = pts[1][1] - c[1], L = Math.hypot(dx, dy);
          pts[0] = [c[0] - (dx / L) * 0.5, c[1] - (dy / L) * 0.5];
        }
        const [[sx, sy], [tx, ty]] = pts;
        const s = it.frame.toScene(sx, sy), t = it.frame.toScene(tx, ty);
        app.walk.target = null;
        app.walk.pos.set(s.x, s.z);
        app.walk.yaw = Math.atan2(-(t.x - s.x), -(t.z - s.z));
        app.walk.pitch = -0.12;
        return true;
      }, { i: room.i, corner });
      if (!ok) continue;
      await page.waitForTimeout(700);
      const file = `${out}/${aptId}_${room.i}_${room.kind}_${corner}.png`;
      await page.screenshot({ path: file });
      console.log('wrote', file);
    }
  }
}
await browser.close();
