// A walk round every room of a flat: from points in each room, views in eight directions at eye
// height, put together into contact sheets (one per flat, 4 views a row) for a visual check.
//   node tools/ab/tour.mjs OUTDIR APT_ID [APT_ID ...] [--pts 2] [--dirs 8] [--w 560 --h 380]
// OUTDIR/<id>_<n>.png (the sheets), OUTDIR/<id>.json (what each cell shows: room, point, direction)
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? +args[args.indexOf(k) + 1] : d);
const [outDir, ...rest] = args;
const ids = rest.filter((a, i) => !a.startsWith('--') && !(rest[i - 1] ?? '').startsWith('--'));
const W = opt('--w', 560), H = opt('--h', 380), DIRS = opt('--dirs', 8), PTS = opt('--pts', 2);
fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1200);
for (const id of ids) {
  const views = await page.evaluate(async ([id, PTS, DIRS]) => {
    const app = window.__app;
    const { inside, distToPolygon, interiorPoint, bounds } = await import('/src/geometry.js');
    const a = app.apartments.find((x) => x.id === id);
    app.selectApt(a);
    app.enterWalk(a);
    await new Promise((r) => setTimeout(r, 1800));
    for (const el of ['walk-help', 'minimap']) document.getElementById(el).style.visibility = 'hidden';
    const edge = (p, x, y) => {
      let d = Infinity;
      for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
        const [ax, ay] = p[j], [bx, by] = p[i], dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy;
        const t = L ? Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / L)) : 0;
        d = Math.min(d, Math.hypot(x - ax - t * dx, y - ay - t * dy));
      }
      return d;
    };
    const out = [];
    const rooms = [...a.data.rooms, ...a.data.balconies];
    rooms.forEach((r, ri) => {
      const b = bounds(r.poly);
      const pts = [interiorPoint(r.poly)];
      // more points along the room's long axis, 0.45 m clear of its edges
      const long = b.x1 - b.x0 > b.y1 - b.y0;
      for (const f of [0.2, 0.8, 0.35, 0.65]) {
        const p = long ? [b.x0 + (b.x1 - b.x0) * f, pts[0][1]] : [pts[0][0], b.y0 + (b.y1 - b.y0) * f];
        if (pts.length < PTS && inside(r.poly, ...p) && edge(r.poly, ...p) > 0.45 && pts.every((q) => Math.hypot(q[0] - p[0], q[1] - p[1]) > 1.2)) pts.push(p);
      }
      pts.forEach((p, pi) => {
        for (let k = 0; k < DIRS; k++) {
          const ang = (2 * Math.PI * k) / DIRS;
          out.push({ room: `${r.name} ${r.area}`, ri, pi, p: p.map((v) => +v.toFixed(2)), ang: +ang.toFixed(3) });
        }
      });
    });
    return out;
  }, [id, PTS, DIRS]);
  const shots = [];
  for (const v of views) {
    await page.evaluate(([p, ang]) => {
      const app = window.__app, it = app.interior;
      const s = it.frame.toScene(p[0], p[1]), t = it.frame.toScene(p[0] + Math.cos(ang), p[1] + Math.sin(ang));
      app.walk.target = null;
      app.walk.pos.set(s.x, s.z);
      app.walk.yaw = Math.atan2(-(t.x - s.x), -(t.z - s.z));
      app.walk.pitch = -0.12;
    }, [v.p, v.ang]);
    await page.waitForTimeout(260);
    shots.push(await page.screenshot({ type: 'jpeg', quality: 82 }));
  }
  fs.writeFileSync(`${outDir}/${id}.json`, JSON.stringify(views));
  // sheets of 12 (4 x 3), each cell labelled with its index
  const per = 16;
  for (let s = 0; s * per < shots.length; s++) {
    const cells = shots.slice(s * per, (s + 1) * per).map((b) => `data:image/jpeg;base64,${b.toString('base64')}`);
    const labels = views.slice(s * per, (s + 1) * per).map((v, i) => `${s * per + i}: ${v.room} · ${Math.round((v.ang * 180) / Math.PI)}°`);
    const sheet = await page.evaluate(async ([cells, labels, W, H]) => {
      const cw = W / 2, ch = H / 2, c = document.createElement('canvas');
      c.width = cw * 4;
      c.height = (ch + 16) * Math.ceil(cells.length / 4);
      const g = c.getContext('2d');
      g.fillStyle = '#222';
      g.fillRect(0, 0, c.width, c.height);
      for (let i = 0; i < cells.length; i++) {
        const im = new Image();
        im.src = cells[i];
        await im.decode();
        const x = (i % 4) * cw, y = Math.floor(i / 4) * (ch + 16);
        g.drawImage(im, x, y + 16, cw, ch);
        g.fillStyle = '#fff';
        g.font = '11px sans-serif';
        g.fillText(labels[i], x + 4, y + 12);
      }
      return c.toDataURL('image/jpeg', 0.85);
    }, [cells, labels, W, H]);
    fs.writeFileSync(`${outDir}/${id}_${s}.jpg`, Buffer.from(sheet.split(',')[1], 'base64'));
  }
  console.log(id, views.length, 'views ->', Math.ceil(shots.length / per), 'sheets');
  await page.evaluate(() => window.__app.exitWalk());
  await page.waitForTimeout(1500);
}
await browser.close();
