// Furniture against furniture and against the walls, in every layout as the walk-through builds
// it: pieces that overlap one another (more than a few centimetres), pieces standing in a wall or
// a column, open door leaves standing in a piece. Rugs are left out (they lie under the others).
//   node tools/ab/check_pieces.mjs [APT_ID ...]
import { chromium } from 'playwright-core';

const ids = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 800, height: 500 } });
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const out = await page.evaluate(async (ids) => {
  const { buildFloor } = await import('/src/floor.js');
  const { aptsOnFloor, apartments } = await import('/src/data.js');
  const { inside } = await import('/src/geometry.js');
  const { PLANS } = await import('/src/config.js');
  let list = ids.length ? ids.map((id) => apartments.find((a) => a.id === id)) : [];
  if (!ids.length) {
    const seen = new Set();
    for (const a of apartments) {
      const k = `${a.plan}:${a.data.outline[0].join(',')}`;
      if (!seen.has(k)) seen.add(k), list.push(a);
    }
  }
  // overlap depth of two convex polygons (the smallest projection overlap over their edge normals)
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
  const res = [];
  for (const a of list) {
    const it = buildFloor(a.tower, a.floor, aptsOnFloor(a.tower, a.floor), a);
    const plan = PLANS[a.plan];
    const solids = [...plan.walls, ...plan.struct];
    const pieces = it.obstacles.filter((o) => o.poly.length >= 3 && o.what && !/rug/.test(o.what));
    const leaves = it.obstacles.filter((o) => o.what === 'door');
    const issues = [];
    // (a piece and its own parts - a bed and its nightstands, a table and its chairs - come as one)
    for (let i = 0; i < pieces.length; i++) {
      for (let j = i + 1; j < pieces.length; j++) {
        const d = depth(pieces[i].poly, pieces[j].poly);
        if (d > 0.04) issues.push(`overlap ${pieces[i].what} / ${pieces[j].what} ${d.toFixed(2)} m`);
      }
      // in a wall or a column: grid points of the piece, 3 cm in from its edges
      const p = pieces[i].poly;
      if (p.length !== 4) continue;
      const [A, B, , D] = p;
      // (3 cm in from its edges: a piece touching a wall, or a sofa's back a centimetre into it, is
      // no fault)
      const lu = Math.hypot(B[0] - A[0], B[1] - A[1]), lv = Math.hypot(D[0] - A[0], D[1] - A[1]);
      if (lu < 0.08 || lv < 0.08) continue;
      let hit = 0, n = 0;
      for (let u = 0; u <= 6; u++) {
        for (let v = 0; v <= 6; v++) {
          const fu = (0.03 + ((lu - 0.06) * u) / 6) / lu, fv = (0.03 + ((lv - 0.06) * v) / 6) / lv;
          const x = A[0] + (B[0] - A[0]) * fu + (D[0] - A[0]) * fv, y = A[1] + (B[1] - A[1]) * fu + (D[1] - A[1]) * fv;
          n++;
          if (solids.some((w) => inside(w, x, y))) hit++;
        }
      }
      if (hit > 0) issues.push(`in a wall: ${pieces[i].what} (${hit}/${n} points)`);
    }
    // open leaves through pieces: points along the leaf
    for (const l of leaves) {
      const [h, t] = l.poly;
      for (const pc of pieces) {
        if (pc.poly.length < 3) continue;
        let k = 0;
        for (let s = 0.1; s <= 0.95; s += 0.05) if (inside(pc.poly, h[0] + (t[0] - h[0]) * s, h[1] + (t[1] - h[1]) * s)) k++;
        if (k) issues.push(`door leaf through ${pc.what}`);
      }
    }
    // doors left shut (no way to open them): which rooms of this flat they are on
    const shut = it.obstacles.filter((o) => o.what === 'door shut' && a.data.rooms.some((r) => o.poly.some((p) => Math.min(...r.poly.map((q) => Math.hypot(q[0] - p[0], q[1] - p[1]))) < 3 && inside(r.poly, (o.poly[0][0] + o.poly[1][0]) / 2 + 0.2, (o.poly[0][1] + o.poly[1][1]) / 2) || inside(r.poly, (o.poly[0][0] + o.poly[1][0]) / 2 - 0.2, (o.poly[0][1] + o.poly[1][1]) / 2) || inside(r.poly, (o.poly[0][0] + o.poly[1][0]) / 2, (o.poly[0][1] + o.poly[1][1]) / 2 + 0.2) || inside(r.poly, (o.poly[0][0] + o.poly[1][0]) / 2, (o.poly[0][1] + o.poly[1][1]) / 2 - 0.2))));
    res.push({ id: a.id, number: a.number, issues, shut: shut.length, front: it.obstacles.filter((o) => o.what === 'front door').length });
    it.dispose();
  }
  return res;
}, ids);
let bad = 0;
for (const r of out) {
  if (r.issues.length) bad++;
  console.log(`${r.issues.length ? 'FAIL' : 'ok  '} ${r.id.padEnd(7)} № ${String(r.number).padEnd(4)} front doors on the floor ${r.front}, shut doors in the flat ${r.shut}${r.issues.length ? '  ' + [...new Set(r.issues)].join('; ') : ''}`);
}
console.log(`${out.length} layouts, ${bad} with problems`);
await browser.close();
process.exit(bad ? 1 : 0);
