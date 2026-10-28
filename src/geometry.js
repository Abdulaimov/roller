// Small 2D polygon helpers for the floor plans (polygons are [[x, y], ...]).

export function polygonArea(p) {
  let a = 0;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) a += (p[j][0] + p[i][0]) * (p[j][1] - p[i][1]);
  return Math.abs(a / 2);
}

export function centroid(p) {
  let x = 0, y = 0, a = 0;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
    const f = p[j][0] * p[i][1] - p[i][0] * p[j][1];
    x += (p[j][0] + p[i][0]) * f;
    y += (p[j][1] + p[i][1]) * f;
    a += f;
  }
  if (Math.abs(a) < 1e-9) return [p[0][0], p[0][1]];
  return [x / (3 * a), y / (3 * a)];
}

export function bounds(p) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of p) {
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
  }
  return { x0, y0, x1, y1 };
}

export function inside(p, x, y) {
  let c = false;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
    const [xi, yi] = p[i], [xj, yj] = p[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}

export function distToSegment(x, y, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay;
  const L = dx * dx + dy * dy;
  let t = L ? ((x - ax) * dx + (y - ay) * dy) / L : 0;
  t = Math.max(0, Math.min(1, t));
  const px = ax + t * dx, py = ay + t * dy;
  return { d: Math.hypot(x - px, y - py), px, py };
}

export function distToPolygon(p, x, y) {
  if (inside(p, x, y)) return 0;
  let d = Infinity;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) d = Math.min(d, distToSegment(x, y, p[j][0], p[j][1], p[i][0], p[i][1]).d);
  return d;
}

// A point well inside a polygon (the grid point furthest from the edges).
export function interiorPoint(p) {
  const b = bounds(p);
  let best = null, bestD = -1;
  const n = 18;
  for (let i = 1; i < n; i++) {
    for (let j = 1; j < n; j++) {
      const x = b.x0 + ((b.x1 - b.x0) * i) / n, y = b.y0 + ((b.y1 - b.y0) * j) / n;
      if (!inside(p, x, y)) continue;
      let d = Infinity;
      for (let k = 0, m = p.length - 1; k < p.length; m = k++) d = Math.min(d, distToSegment(x, y, p[m][0], p[m][1], p[k][0], p[k][1]).d);
      if (d > bestD) { bestD = d; best = [x, y]; }
    }
  }
  return best ?? centroid(p);
}

// The largest axis-aligned rectangle that fits inside a polygon: grown from the interior point,
// or, where that growth stops in one leg of an L-shaped room, the largest rectangle on a 10 cm grid
export function innerRect(p, margin = 0.08) {
  const fits = (q) => {
    const steps = 6;
    for (let i = 0; i <= steps; i++) {
      const fx = q.x0 + ((q.x1 - q.x0) * i) / steps, fy = q.y0 + ((q.y1 - q.y0) * i) / steps;
      for (const [x, y] of [[fx, q.y0], [fx, q.y1], [q.x0, fy], [q.x1, fy]]) {
        if (distToPolygon(p, x, y) > 0 || edgeDist(p, x, y) < margin) return false;
      }
    }
    return true;
  };
  const grow = (r, step) => {
    let grew = true;
    while (grew) {
      grew = false;
      for (const k of ['x0', 'x1', 'y0', 'y1']) {
        const q = { ...r, [k]: r[k] + (k.endsWith('0') ? -step : step) };
        if (fits(q)) { r = q; grew = true; }
      }
    }
    return r;
  };
  const [cx, cy] = interiorPoint(p);
  const r = grow({ x0: cx - 0.2, y0: cy - 0.2, x1: cx + 0.2, y1: cy + 0.2 }, 0.1);
  const area = (q) => (q.x1 - q.x0) * (q.y1 - q.y0);
  let g = gridRect(p, margin);
  if (!g) return r;
  for (let i = 0; i < 5 && !fits(g); i++) g = { x0: g.x0 + 0.02, y0: g.y0 + 0.02, x1: g.x1 - 0.02, y1: g.y1 - 0.02 };
  if (!fits(g)) return r;
  g = grow(grow(g, 0.1), 0.02);
  return area(g) > area(r) * 1.15 ? g : r;
}

// the largest rectangle of 10 cm cells whose corners all lie inside the polygon, `margin` from its
// edges (the maximal rectangle of a 0/1 grid, row by row over column heights)
function gridRect(p, margin) {
  const b = bounds(p), c = 0.1;
  const nx = Math.floor((b.x1 - b.x0) / c), ny = Math.floor((b.y1 - b.y0) / c);
  if (nx < 2 || ny < 2 || nx * ny > 40000) return null;
  const ok = [];
  for (let j = 0; j <= ny; j++) {
    const row = new Uint8Array(nx + 1);
    for (let i = 0; i <= nx; i++) {
      const x = b.x0 + i * c, y = b.y0 + j * c;
      row[i] = inside(p, x, y) && edgeDist(p, x, y) >= margin ? 1 : 0;
    }
    ok.push(row);
  }
  // cell (i, j): between grid points i..i+1 and j..j+1
  const h = new Int32Array(nx);
  let best = null, bestA = 0;
  for (let j = 0; j < ny; j++) {
    for (let i = 0; i < nx; i++) h[i] = ok[j][i] && ok[j][i + 1] && ok[j + 1][i] && ok[j + 1][i + 1] ? h[i] + 1 : 0;
    const stack = [];
    for (let i = 0; i <= nx; i++) {
      const hi = i < nx ? h[i] : 0;
      let start = i;
      while (stack.length && stack[stack.length - 1][1] >= hi) {
        const [s0, hs] = stack.pop();
        if (hs * (i - s0) > bestA) {
          bestA = hs * (i - s0);
          best = { x0: b.x0 + s0 * c, x1: b.x0 + i * c, y0: b.y0 + (j + 1 - hs) * c, y1: b.y0 + (j + 1) * c };
        }
        start = s0;
      }
      stack.push([start, hi]);
    }
  }
  return best;
}

function edgeDist(p, x, y) {
  let d = Infinity;
  for (let k = 0, m = p.length - 1; k < p.length; m = k++) d = Math.min(d, distToSegment(x, y, p[m][0], p[m][1], p[k][0], p[k][1]).d);
  return d;
}

// Resample a closed ring every `step` metres (keeps the corners).
export function resampleRing(p, step) {
  const out = [];
  for (let i = 0; i < p.length; i++) {
    const a = p[i], b = p[(i + 1) % p.length];
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const n = Math.max(1, Math.round(L / step));
    for (let k = 0; k < n; k++) out.push([a[0] + ((b[0] - a[0]) * k) / n, a[1] + ((b[1] - a[1]) * k) / n]);
  }
  return out;
}
