// Walking on the ground round the complex, as inside a flat (src/walk.js does the walking).
// The map of the ground comes from the Blender build (public/models/site_walk.json, blender/ab/site.py
// walk_map): what is underfoot on a 1 m grid, the outlines one cannot walk through (buildings, play
// equipment, benches, cars), fences and hedges as lines, lamps, masts, trunks and people as posts.
// Site metres (x east, y north) -> scene (x, z = -y), the site centre at the origin (config.js).
import * as THREE from 'three';

const URL_MAP = `${import.meta.env.BASE_URL}models/site_walk.json`;
const R = 0.3; // the walker: half a shoulder width and a little room
const CELL = 4; // metres per cell of the obstacle index
// what is underfoot: kind -> ground level (m) and colour on the mini-map
export const KINDS = {
  0: { h: 0, c: '#2c2f33' }, // no way
  1: { h: 0.0, c: '#8c9095' }, // asphalt
  2: { h: 0.12, c: '#ddd3c4' }, // paving
  3: { h: 0.15, c: '#93b86c' }, // lawn
  4: { h: 0.13, c: '#e59b55' }, // play surface
  5: { h: 0.14, c: '#4f9a3c' }, // pitch
  6: { h: 0.05, c: '#9cc074' }, // school lawn
  7: { h: 0.1, c: '#e6dccb' }, // school paving
  8: { h: 0.08, c: '#b5573e' }, // track, courts
  9: { h: -0.04, c: '#c2b996' }, // bare ground
};

let cached = null;
export function loadSiteMap() {
  cached ??= fetch(URL_MAP).then((r) => {
    if (!r.ok) throw new Error(`site map: ${r.status}`);
    return r.json();
  });
  return cached;
}

// run lengths along the rows, alternately out and in, LEB128 (the build's walk map) -> a bit per cell
function decodeRuns(runs, n) {
  const bits = new Uint8Array(n), b = Uint8Array.from(atob(runs), (ch) => ch.charCodeAt(0));
  for (let p = 0, k = 0, inside = false; p < b.length; inside = !inside) {
    let v = 0;
    for (let sh = 0; ; sh += 7) {
      const c = b[p++];
      v += (c & 127) * 2 ** sh;
      if (c < 128) break;
    }
    if (inside) bits.fill(1, k, k + v);
    k += v;
  }
  return bits;
}

/** the lawns' fine mask (25 cm): (x, y) in site metres -> on the lawn itself, not on its kerb or the paving */
export function lawnTest(map) {
  const L = map.lawn;
  if (!L) return () => true;
  const bits = decodeRuns(L.runs, L.gx * L.gy);
  return (x, y) => {
    const i = Math.floor((x - map.x0) / L.step), j = Math.floor((y - map.y0) / L.step);
    return i >= 0 && j >= 0 && i < L.gx && j < L.gy && bits[j * L.gx + i] === 1;
  };
}

function inPoly(p, x, y) {
  let c = false;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
    const [xi, yi] = p[i], [xj, yj] = p[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}

/**
 * The walk on the site, in the shape walk.js expects of an interior: spawn, move(), the ground
 * height under a point, a pick of the ground under the pointer, and the frame for the mini-map.
 * @param map    the site map (loadSiteMap)
 * @param from   where to begin: null for the courtyard entrance, or a block key ('B', 'G'...)
 * @param picks  meshes that hide the ground behind them (the blocks' invisible prisms)
 */
export function siteWalk(map, from = null, picks = [], beds = []) {
  const ground = Uint8Array.from(atob(map.ground), (ch) => ch.charCodeAt(0));
  const { x0, y0, nx, ny } = map;
  const kindAt = (x, y) => {
    const i = Math.floor(x - x0), j = Math.floor(y - y0);
    return i < 0 || j < 0 || i >= nx || j >= ny ? 0 : ground[j * nx + i];
  };
  // ground level, bilinear over the grid (kerbs read as a few centimetres up or down)
  const level = (x, y) => {
    const fx = x - x0 - 0.5, fy = y - y0 - 0.5;
    const i = Math.floor(fx), j = Math.floor(fy), u = fx - i, v = fy - j;
    const h = (a, b) => KINDS[kindAt(x0 + a + 0.5, y0 + b + 0.5)]?.h ?? 0;
    return (h(i, j) * (1 - u) + h(i + 1, j) * u) * (1 - v) + (h(i, j + 1) * (1 - u) + h(i + 1, j + 1) * u) * v;
  };

  // obstacles, indexed by cell: segments [ax, ay, bx, by, half width] and posts [x, y, r]
  const cells = new Map();
  const key = (i, j) => i * 100003 + j;
  const addTo = (bx0, by0, bx1, by1, item, list) => {
    for (let i = Math.floor((bx0 - R) / CELL); i <= Math.floor((bx1 + R) / CELL); i++) {
      for (let j = Math.floor((by0 - R) / CELL); j <= Math.floor((by1 + R) / CELL); j++) {
        const k = key(i, j);
        if (!cells.has(k)) cells.set(k, { segs: [], posts: [], solids: [] });
        cells.get(k)[list].push(item);
      }
    }
  };
  const addSeg = (a, b, hw) => addTo(Math.min(a[0], b[0]) - hw, Math.min(a[1], b[1]) - hw, Math.max(a[0], b[0]) + hw, Math.max(a[1], b[1]) + hw, [a[0], a[1], b[0], b[1], hw], 'segs');
  for (const s of map.solids) {
    for (let i = 0, j = s.length - 1; i < s.length; j = i++) addSeg(s[j], s[i], 0);
    let bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity;
    for (const [x, y] of s) (bx0 = Math.min(bx0, x)), (by0 = Math.min(by0, y)), (bx1 = Math.max(bx1, x)), (by1 = Math.max(by1, y));
    addTo(bx0, by0, bx1, by1, s, 'solids');
  }
  for (const [w, pts] of map.lines) for (let i = 1; i < pts.length; i++) addSeg(pts[i - 1], pts[i], w / 2);
  // (the flower beds, src/flowers.js, are posts too: round, the walker keeps off them)
  for (const p of [...map.posts, ...beds.map((d) => [d.x, d.y, d.r + 0.15])]) addTo(p[0] - p[2], p[1] - p[2], p[0] + p[2], p[1] + p[2], p, 'posts');
  const near = (x, y) => cells.get(key(Math.floor(x / CELL), Math.floor(y / CELL)));
  const insideSolid = (x, y) => near(x, y)?.solids.some((s) => inPoly(s, x, y)) ?? false;
  const free = (x, y) => kindAt(x, y) !== 0 && !insideSolid(x, y);
  // room for the walker here: on the ground, out of buildings, a shoulder clear of every obstacle
  const roomy = (x, y) => {
    if (!free(x, y)) return false;
    const c = near(x, y);
    if (!c) return true;
    for (const [ax, ay, bx, by, hw] of c.segs) {
      const dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy;
      const t = L ? Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / L)) : 0;
      if (Math.hypot(x - ax - t * dx, y - ay - t * dy) < R + hw - 0.02) return false;
    }
    for (const [cx, cy, r] of c.posts) if (Math.hypot(x - cx, y - cy) < R + r - 0.02) return false;
    return true;
  };
  const sight = (ax, ay, bx, by) => {
    const n = Math.ceil(Math.hypot(bx - ax, by - ay) / 0.2);
    for (let i = 1; i <= n; i++) if (!roomy(ax + ((bx - ax) * i) / n, ay + ((by - ay) * i) / n)) return false;
    return true;
  };

  // the way to a clicked point round hedges, fences, benches and buildings: A* over the grid of
  // the places the walker can get to (the build's map.reach: run lengths along the rows,
  // alternately out of reach and in it, LEB128), then cut short wherever the walker can see further
  const { step: G, gx: GX, gy: GY } = map.reach;
  const open = decodeRuns(map.reach.runs, GX * GY);
  // the flower beds closed to the search (the walk goes round them)
  for (const d of beds) {
    const rr = d.r + 0.15 + R;
    for (let j = Math.floor((d.y - rr - y0) / G); j <= Math.floor((d.y + rr - y0) / G); j++) {
      for (let i = Math.floor((d.x - rr - x0) / G); i <= Math.floor((d.x + rr - x0) / G); i++) {
        if (i < 0 || j < 0 || i >= GX || j >= GY) continue;
        if (Math.hypot(x0 + (i + 0.5) * G - d.x, y0 + (j + 0.5) * G - d.y) < rr) open[j * GX + i] = 0;
      }
    }
  }
  // the search's arrays, kept between clicks: a cell's cost counts only when stamped this search
  const cost = new Float64Array(GX * GY), back = new Int32Array(GX * GY), stamp = new Uint32Array(GX * GY);
  let search = 0;
  const cellOpen = (i, j) => i >= 0 && j >= 0 && i < GX && j < GY && open[j * GX + i] === 1;
  const nearestOpen = (x, y, rmax) => {
    const ci = Math.floor((x - x0) / G), cj = Math.floor((y - y0) / G);
    let best = null, bd = Infinity;
    const n = Math.ceil(rmax / G);
    for (let dj = -n; dj <= n; dj++) {
      for (let di = -n; di <= n; di++) {
        const d = Math.hypot(di, dj);
        if (d < bd && d <= n && cellOpen(ci + di, cj + dj)) (bd = d), (best = [ci + di, cj + dj]);
      }
    }
    return best;
  };
  const route = (ax, ay, bx, by) => {
    const s = nearestOpen(ax, ay, 1.2), g = nearestOpen(bx, by, 2);
    if (!s || !g) return null;
    const S = s[1] * GX + s[0], T = g[1] * GX + g[0];
    search++;
    const costOf = (k) => (stamp[k] === search ? cost[k] : Infinity);
    const heap = [], hk = [];
    const push = (k, f) => {
      let i = heap.length;
      heap.push(k), hk.push(f);
      while (i > 0) {
        const p = (i - 1) >> 1;
        if (hk[p] <= f) break;
        (heap[i] = heap[p]), (hk[i] = hk[p]), (i = p);
      }
      (heap[i] = k), (hk[i] = f);
    };
    const pop = () => {
      const top = heap[0], k = heap.pop(), f = hk.pop();
      if (heap.length) {
        let i = 0;
        for (;;) {
          let c = 2 * i + 1;
          if (c >= heap.length) break;
          if (c + 1 < heap.length && hk[c + 1] < hk[c]) c++;
          if (hk[c] >= f) break;
          (heap[i] = heap[c]), (hk[i] = hk[c]), (i = c);
        }
        (heap[i] = k), (hk[i] = f);
      }
      return top;
    };
    const h = (k) => {
      const di = Math.abs((k % GX) - g[0]), dj = Math.abs(Math.floor(k / GX) - g[1]);
      return Math.max(di, dj) + (Math.SQRT2 - 1) * Math.min(di, dj);
    };
    (cost[S] = 0), (back[S] = -1), (stamp[S] = search);
    push(S, h(S));
    let found = false;
    for (let n = 0; heap.length && n < 2 * GX * GY; n++) {
      const f = hk[0], k = pop();
      if (f > cost[k] + h(k) + 1e-6) continue; // a stale entry: the cell was reached cheaper since
      if (k === T) {
        found = true;
        break;
      }
      const i = k % GX, j = Math.floor(k / GX);
      for (let dj = -1; dj <= 1; dj++) {
        for (let di = -1; di <= 1; di++) {
          if ((!di && !dj) || !cellOpen(i + di, j + dj)) continue;
          if (di && dj && (!cellOpen(i + di, j) || !cellOpen(i, j + dj))) continue; // no corner cutting
          const q = (j + dj) * GX + i + di, c = cost[k] + (di && dj ? Math.SQRT2 : 1);
          if (c < costOf(q) - 1e-9) {
            (cost[q] = c), (back[q] = k), (stamp[q] = search);
            push(q, c + h(q));
          }
        }
      }
    }
    if (!found) return null;
    const chain = [];
    for (let k = T; k !== -1; k = back[k]) chain.push([x0 + ((k % GX) + 0.5) * G, y0 + (Math.floor(k / GX) + 0.5) * G]);
    chain.reverse();
    chain[0] = [ax, ay];
    if (roomy(bx, by) && sight(...chain[chain.length - 1], bx, by)) chain.push([bx, by]);
    // string-pull: from each corner go as far along as can be seen
    const way = [];
    let a = chain[0], k = 0;
    while (k < chain.length - 1) {
      let m = k + 1;
      while (m + 1 < chain.length && sight(a[0], a[1], chain[m + 1][0], chain[m + 1][1])) m++;
      way.push(chain[m]);
      (a = chain[m]), (k = m);
    }
    return way.map(([x, y]) => new THREE.Vector2(x, -y));
  };

  const toScene = (x, y) => ({ x, z: -y });
  const toPlan = (X, Z) => ({ x: X, y: -Z });

  const start = (from && map.blocks[from]) || map.spawn;
  const yaw = Math.atan2(-start.look[0], start.look[1]); // scene: look = (lx, -ly) -> yaw with -sin, -cos
  const group = new THREE.Group();

  // the ground under the pointer: the plane at the ground's level, the hit kept only where one can
  // stand, not behind a block and not far off
  const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const hit = new THREE.Vector3();
  const pick = (ray) => {
    plane.constant = -0.12;
    if (!ray.ray.intersectPlane(plane, hit)) return null;
    const d = hit.distanceTo(ray.ray.origin);
    if (d > 90) return null;
    if (picks.length && ray.intersectObjects(picks, false).some((h) => h.distance < d)) return null;
    const p = toPlan(hit.x, hit.z);
    if (!free(p.x, p.y) || !nearestOpen(p.x, p.y, 0.8)) return null;
    return new THREE.Vector3(hit.x, level(p.x, p.y), hit.z);
  };

  return {
    outdoor: true,
    group,
    floorMeshes: [],
    spawn: { x: start.x, z: -start.y, yaw, pitch: start.pitch ?? 0 },
    baseY: 0,
    speed: 1.45, // the grounds are large: a brisk walk (Shift: faster still)
    frame: { toScene, toPlan },
    map,
    kindAt,
    groundAt: (X, Z) => level(X, -Z),
    pick,
    // scene points to walk through from (X, Z) to the clicked (TX, TZ), the last one the goal
    route: (X, Z, TX, TZ) => route(X, -Z, TX, -TZ),
    canStand: (X, Z) => roomy(X, -Z) && !!nearestOpen(X, -Z, 0.4),
    move(x, z, nx, nz) {
      let px = nx, py = -nz;
      for (let iter = 0; iter < 3; iter++) {
        const c = near(px, py);
        if (!c) break;
        for (const [ax, ay, bx, by, hw] of c.segs) {
          const rr = R + hw;
          if (Math.min(ax, bx) - rr > px || Math.max(ax, bx) + rr < px || Math.min(ay, by) - rr > py || Math.max(ay, by) + rr < py) continue;
          const dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy;
          const t = L ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / L)) : 0;
          const qx = ax + t * dx, qy = ay + t * dy, d = Math.hypot(px - qx, py - qy);
          if (d < rr && d > 1e-6) {
            px = qx + ((px - qx) / d) * rr;
            py = qy + ((py - qy) / d) * rr;
          }
        }
        for (const [cx, cy, r] of c.posts) {
          const rr = R + r, d = Math.hypot(px - cx, py - cy);
          if (d < rr && d > 1e-6) {
            px = cx + ((px - cx) / d) * rr;
            py = cy + ((py - cy) / d) * rr;
          }
        }
      }
      // never off the ground nor into a building (a long step at a corner)
      if (!free(px, py)) return { x, z };
      return { x: px, z: -py };
    },
    dispose() {},
  };
}
