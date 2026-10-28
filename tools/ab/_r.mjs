import { chromium } from 'playwright-core';
const browser = await chromium.launch({ executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`, headless: true, args: ['--use-angle=metal'] });
const page = await browser.newPage();
await page.goto('http://localhost:5197/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const out = await page.evaluate(async () => {
  const { buildFloor, reachableRooms } = await import('/src/floor.js');
  const { aptsOnFloor, apartments } = await import('/src/data.js');
  const a = apartments.find((x) => x.id === 'B14-4');
  const it = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor), a);
  const res = [];
  for (const d of it.doorways.filter((d) => d.apt === 'B14-4')) {
    const m = [(d.a[0] + d.b[0]) / 2, (d.a[1] + d.b[1]) / 2];
    // points through the doorway along its normal
    const pts = [-0.4, -0.2, 0, 0.2, 0.4].map((s) => [m[0] + d.n[0] * s, m[1] + d.n[1] * s]);
    const near = it.segments.filter(([ax, ay, bx, by]) => pts.some(([x, y]) => {
      const vx = bx - ax, vy = by - ay, L = vx * vx + vy * vy || 1e-9;
      const t = Math.max(0, Math.min(1, ((x - ax) * vx + (y - ay) * vy) / L));
      return Math.hypot(ax + vx * t - x, ay + vy * t - y) < 0.23;
    }));
    res.push({ room: d.room, across: d.across, len: d.len, m: m.map((v) => +v.toFixed(2)), n: d.n, near: near.map((s) => s.map((v) => +v.toFixed(2))).slice(0, 6) });
  }
  return res;
});
for (const r of out) console.log(JSON.stringify(r));
await browser.close();
