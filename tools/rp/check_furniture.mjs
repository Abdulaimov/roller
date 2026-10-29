// Every piece of furniture as the walk-through builds it, checked one by one (the parts of a group
// too: each chair of a dining set, each nightstand): from the kit's record of what was built
// (src/interior/kit.js, src/floor.js RECORD), not from the placement's own footprints. For every
// distinct layout of the three blocks:
//   overlap    two pieces in each other (their footprints and heights both overlap; a chair may be
//              pushed in under its table, a curtain hangs in front of what stands at the window)
//   duplicate  two pieces of one kind in the same place (drawn and furnished again, say)
//   wall       a piece standing in a wall or a column (3 cm in from its edges)
//   floating   a piece that stands on the floor lifted off it
//   door       an open door leaf through a piece
// and a log of what was covered: layouts, flats, rooms, pieces by kind.
//   node tools/rp/check_furniture.mjs [APT_ID ...] [--json OUT.json]
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import CHROME from '../ab/chrome.mjs';

const args = process.argv.slice(2);
const jsonOut = args.includes('--json') ? args[args.indexOf('--json') + 1] : null;
const ids = args.filter((a, i) => !a.startsWith('--') && args[i - 1] !== '--json');
const browser = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 800, height: 500 } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('http://localhost:5197/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 180000 });
const out = await page.evaluate(async (ids) => {
  const { buildFloor, RECORD } = await import('/src/floor.js');
  const { aptsOnFloor, apartments } = await import('/src/data.js');
  const { inside } = await import('/src/geometry.js');
  const { PLANS } = await import('/src/config.js');
  RECORD.pieces = true;
  let list = ids.length ? ids.map((id) => apartments.find((a) => a.id === id)) : [];
  if (!ids.length) {
    const seen = new Set();
    for (const a of apartments) {
      const k = `${a.plan}:${a.data.outline[0].join(',')}`;
      if (!seen.has(k)) seen.add(k), list.push(a);
    }
  }
  // overlap depth of two convex polygons: the smallest overlap of their projections (SAT)
  const depth = (p, q) => {
    let best = Infinity;
    for (const poly of [p, q]) {
      for (let i = 0; i < poly.length; i++) {
        const [x0, y0] = poly[i], [x1, y1] = poly[(i + 1) % poly.length];
        let nx = y0 - y1, ny = x1 - x0;
        const L = Math.hypot(nx, ny);
        if (L < 1e-9) continue;
        (nx /= L), (ny /= L);
        let a0 = Infinity, a1 = -Infinity, b0 = Infinity, b1 = -Infinity;
        for (const [x, y] of p) (a0 = Math.min(a0, nx * x + ny * y)), (a1 = Math.max(a1, nx * x + ny * y));
        for (const [x, y] of q) (b0 = Math.min(b0, nx * x + ny * y)), (b1 = Math.max(b1, nx * x + ny * y));
        best = Math.min(best, Math.min(a1, b1) - Math.max(a0, b0));
      }
    }
    return best;
  };
  const area = (p) => Math.abs(p.reduce((s, [x, y], i) => s + x * p[(i + 1) % p.length][1] - p[(i + 1) % p.length][0] * y, 0)) / 2;
  const centroid = (p) => [p.reduce((s, q) => s + q[0], 0) / p.length, p.reduce((s, q) => s + q[1], 0) / p.length];
  // sample points of a convex polygon, `inset` m in from its edges
  const samples = (p, inset, n = 7) => {
    const [cx, cy] = centroid(p), pts = [];
    for (const [x, y] of p) {
      for (let t = 1; t <= n; t++) {
        const f = t / (n + 1);
        const qx = cx + (x - cx) * f, qy = cy + (y - cy) * f;
        const d = Math.hypot(x - cx, y - cy) || 1;
        if (Math.hypot(qx - cx, qy - cy) <= d - inset) pts.push([qx, qy]);
      }
    }
    for (let i = 0; i < p.length; i++) {
      const [x0, y0] = p[i], [x1, y1] = p[(i + 1) % p.length];
      for (let t = 0.1; t < 1; t += 0.2) {
        const ex = x0 + (x1 - x0) * t, ey = y0 + (y1 - y0) * t;
        const d = Math.hypot(ex - cx, ey - cy) || 1;
        pts.push([cx + ((ex - cx) * (d - inset)) / d, cy + ((ey - cy) * (d - inset)) / d]);
      }
    }
    return pts;
  };
  // (the coat rack hangs on the wall, its coat from 0.9 m)
  const GROUND = new Set(['bed', 'sofa', 'sofaBoxes', 'armchair', 'coffeeTable', 'sideTable', 'mediaWall', 'floorLamp', 'plant', 'desk', 'nightstand', 'wardrobe', 'kitchen', 'chair', 'dining', 'diningTable', 'island', 'console_', 'shoeCabinet', 'shelving', 'bathtub', 'laundry', 'nestTable', 'shower', 'balconyTable']);
  const ON_WALL = new Set(['picture', 'roundMirror', 'towelRail', 'acUnit', 'curtain', 'kitchen', 'mediaWall', 'wardrobe', 'shelving', 'vanity', 'toilet', 'shower', 'bathtub', 'liftCar', 'liftPortal']);
  const SKIP = new Set(['rugAt', 'pendants', 'liftCar', 'liftPortal']);
  const allow = (a, b) => {
    const pair = [a, b].sort().join('+');
    // (a chair may stand with its seat under the table's top, as the sheets draw them; not its back:
    // the chair is 0.46 m deep, its back the last 5 cm of it)
    if (pair === 'chair+diningTable' || pair === 'chair+dining' || pair === 'chair+desk' || pair === 'balconyTable+chair') return 0.40;
    if (a === 'curtain' || b === 'curtain') return 0.16;
    return 0.03;
  };
  const res = [], cover = { layouts: 0, flats: 0, rooms: 0, pieces: 0, byKind: {} };
  for (const a of list) {
    const it = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor), a);
    const plan = PLANS[a.plan];
    const solids = [...plan.walls, ...plan.struct];
    const mine = (it.pieces ?? []).filter((p) => !SKIP.has(p.what) && p.hull.length >= 3 && a.data.rooms.concat(a.data.balconies).some((r) => inside(r.poly, ...centroid(p.hull))));
    const issues = [];
    cover.layouts++;
    cover.flats++;
    cover.rooms += a.data.rooms.length;
    cover.pieces += mine.length;
    for (const p of mine) cover.byKind[p.what] = (cover.byKind[p.what] ?? 0) + 1;
    const where = (p) => {
      const c = centroid(p.hull);
      const r = a.data.rooms.concat(a.data.balconies).find((q) => inside(q.poly, ...c));
      return r ? `${r.kind} ${r.area}` : '?';
    };
    for (let i = 0; i < mine.length; i++) {
      const p = mine[i];
      for (let j = i + 1; j < mine.length; j++) {
        const q = mine[j];
        const dy = Math.min(p.y1, q.y1) - Math.max(p.y0, q.y0);
        if (dy <= 0.03) continue;   // (a vase on a table, a lamp over a sofa: one above the other)
        const d = depth(p.hull, q.hull);
        if (p.what === q.what && d > 0.05) {
          const ov = Math.min(area(p.hull), area(q.hull));
          if (d > 0.3 && ov > 0.05) issues.push(`duplicate ${p.what} ×2 in ${where(p)} (${d.toFixed(2)} m)`);
          else if (d > allow(p.what, q.what)) issues.push(`overlap ${p.what} / ${q.what} ${d.toFixed(2)} m in ${where(p)}`);
        } else if (d > allow(p.what, q.what)) issues.push(`overlap ${p.what} / ${q.what} ${d.toFixed(2)} m in ${where(p)}`);
      }
      // in a wall or a column (things fixed to a wall may touch it)
      const inset = ON_WALL.has(p.what) ? 0.06 : 0.03;
      const pts = samples(p.hull, inset);
      const hit = pts.filter(([x, y]) => solids.some((w) => inside(w, x, y))).length;
      if (hit > 1 && p.y0 < 2.2) issues.push(`in a wall: ${p.what} in ${where(p)} (${hit}/${pts.length} points)`);
      if (GROUND.has(p.what) && p.y0 > 0.06) issues.push(`floating: ${p.what} ${p.y0.toFixed(2)} m off the floor in ${where(p)}`);
    }
    for (const l of it.obstacles.filter((o) => o.what === 'door')) {
      const [h, t] = l.poly;
      for (const pc of mine) {
        if (pc.y0 > 2.0) continue;
        let k = 0;
        for (let s = 0.1; s <= 0.95; s += 0.05) if (inside(pc.hull, h[0] + (t[0] - h[0]) * s, h[1] + (t[1] - h[1]) * s)) k++;
        if (k > 1) issues.push(`door leaf through ${pc.what} in ${where(pc)}`);
      }
    }
    res.push({ id: a.id, number: a.number, plan: a.plan, pieces: mine.length, issues: [...new Set(issues)],
      ...(ids.length ? { drawing: { pieces: mine.map(({ what, hull, y0, y1 }) => ({ what, hull, y0, y1 })), walls: solids, rooms: a.data.rooms.concat(a.data.balconies).map((r) => ({ kind: r.kind, area: r.area, poly: r.poly })), doors: it.obstacles.filter((o) => o.what === 'door').map((o) => o.poly) } } : {}) });
    it.dispose();
  }
  return { res, cover };
}, ids);
let bad = 0;
for (const r of out.res) {
  if (r.issues.length) bad++;
  console.log(`${r.issues.length ? 'FAIL' : 'ok  '} ${r.id.padEnd(7)} № ${String(r.number).padEnd(4)} ${String(r.pieces).padStart(3)} pieces${r.issues.length ? '  ' + r.issues.join('; ') : ''}`);
}
const c = out.cover;
console.log(`covered: ${c.layouts} layouts, ${c.rooms} rooms, ${c.pieces} pieces - ` + Object.entries(c.byKind).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${v}`).join(', '));
console.log(`${out.res.length} layouts, ${bad} with problems`);
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify(out, null, 1));
await browser.close();
process.exit(bad ? 1 : 0);
