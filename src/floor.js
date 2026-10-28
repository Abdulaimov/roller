// One residential floor built from the architect's plan: room floors, walls and columns,
// windows and glazing, balconies, the furniture and sanitary ware where the drawing has them, and
// the lifts. Used for the cut-away floor view and, with a ceiling and lights, for the walk-through.
//
// The drawing gives walls, windows, room outlines, door swings, furniture, fittings and lift cars
// (tools/ab/extract_plan.py, tools/ab/furniture.py). Every room edge is probed from inside to find
// what is behind it (wall, window, glazing or nothing); a gap of door width between two rooms gets
// a door, its frame and the wall above it. The drawn furniture stands where it is drawn, turned as
// drawn; rooms the drawing leaves empty (halls, wardrobes) get a few pieces against solid walls,
// away from door swings and windows (src/interior/ has the models, materials and textures).
import * as THREE from 'three';
import { PLANS, planFrame, towerByKey } from './config.js';
import { distToPolygon, distToSegment, inside, innerRect, interiorPoint } from './geometry.js';
import { interiorMaterials } from './interior/materials.js';
import { Kit } from './interior/kit.js';
import * as F from './interior/furniture.js';
import { Q } from './quality.js';

const SILL = 0.85;
const HEAD = 0.35;
const DOOR_H = 2.1;
const CEIL = 0.02; // the ceiling hangs this far under the walls' tops (see the walk-through's ceiling)
const HIGH = Q.level === 'high';

const shape = (poly) => new THREE.Shape(poly.map(([x, y]) => new THREE.Vector2(x, y)));
// plan polygon -> vertical prism in local (x, height, -y)
function prism(poly, y0, y1) {
  const g = new THREE.ExtrudeGeometry(shape(poly), { depth: y1 - y0, bevelEnabled: false, curveSegments: 1 });
  g.rotateX(-Math.PI / 2);
  g.translate(0, y0, 0);
  return g;
}
function flat(poly, y) {
  const g = new THREE.ShapeGeometry(shape(poly));
  g.rotateX(-Math.PI / 2);
  g.translate(0, y, 0);
  return g;
}

// ---------- what is where on the plan ----------

function bbox(p) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of p) (x0 = Math.min(x0, x)), (y0 = Math.min(y0, y)), (x1 = Math.max(x1, x)), (y1 = Math.max(y1, y));
  return { x0, y0, x1, y1 };
}

/** polygons with their bounds, for quick point lookups */
class PolyIndex {
  constructor() { this.items = []; }
  add(poly, kind, data) {
    this.items.push({ poly, kind, data, b: bbox(poly) });
    return this;
  }
  at(x, y) {
    for (const it of this.items) {
      const b = it.b;
      if (x < b.x0 || x > b.x1 || y < b.y0 || y > b.y1) continue;
      if (inside(it.poly, x, y)) return it;
    }
    return null;
  }
}

/**
 * Walk round a room's outline from inside and sort it into runs of what is behind it:
 * 'wall' (walls, columns), 'window', 'glass' (floor-to-ceiling glazing) or 'open'.
 * The outline is sampled every 5 cm along its length with a smoothed direction (the drawings'
 * outlines have many tiny, jagged edges); runs break where what is behind changes or at a corner.
 * Each run: { kind, a: [x, y], b: [x, y], u, n: [nx, ny] (into the room), len, face }
 */
function edgeRuns(room, solid) {
  const p = room.poly, ccw = polygonArea2(p) > 0;
  const segs = [];
  let total = 0;
  for (let i = 0; i < p.length; i++) {
    const a = p[i], b = p[(i + 1) % p.length], L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (L < 1e-6) continue;
    segs.push({ a, b, L, s0: total });
    total += L;
  }
  if (total < 0.2) return [];
  const at = (s) => {
    s = ((s % total) + total) % total;
    let lo = 0, hi = segs.length - 1;
    while (lo < hi) {
      const m = (lo + hi + 1) >> 1;
      if (segs[m].s0 <= s) lo = m;
      else hi = m - 1;
    }
    const g = segs[lo], t = (s - g.s0) / g.L;
    return [g.a[0] + (g.b[0] - g.a[0]) * t, g.a[1] + (g.b[1] - g.a[1]) * t];
  };
  const N = Math.max(8, Math.round(total / 0.05)), step = total / N;
  const samples = [];
  for (let k = 0; k < N; k++) {
    const sp = (k + 0.5) * step, P = at(sp), q0 = at(sp - 0.06), q1 = at(sp + 0.06);
    let tx = q1[0] - q0[0], ty = q1[1] - q0[1];
    const tl = Math.hypot(tx, ty) || 1;
    (tx /= tl), (ty /= tl);
    const nx = ccw ? -ty : ty, ny = ccw ? tx : -tx;
    let kind = 'open';
    for (const d of [0.03, 0.08]) {
      const hit = solid.at(P[0] - nx * d, P[1] - ny * d);
      if (hit) { kind = hit.kind; break; }
    }
    samples.push({ s: sp, kind, tx, ty });
  }
  // start at a break so no run wraps round the end of the list
  const breaks = (i, j) => samples[i].kind !== samples[j].kind || samples[i].tx * samples[j].tx + samples[i].ty * samples[j].ty < 0.87;
  let first = samples.findIndex((x, i) => i > 0 && breaks(i - 1, i));
  if (first < 0) first = 0;
  const runs = [];
  let cur = null;
  for (let k = 0; k < N; k++) {
    const i = (first + k) % N;
    if (cur && samples[i].kind === cur.kind && samples[i].tx * samples[cur.i0].tx + samples[i].ty * samples[cur.i0].ty >= 0.87) cur.s1 = samples[i].s + step / 2;
    else runs.push((cur = { kind: samples[i].kind, i0: i, s0: samples[i].s - step / 2, s1: samples[i].s + step / 2 }));
  }
  return runs.map((r) => {
    const a = at(r.s0), b = at(r.s1 < r.s0 ? r.s1 + total : r.s1);
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1e-6;
    const ux = (b[0] - a[0]) / len, uy = (b[1] - a[1]) / len;
    const nx = ccw ? -uy : uy, ny = ccw ? ux : -ux;
    // where the wall's face is: walls overlap the room outlines by a few centimetres
    let face = 0;
    if (r.kind !== 'open') {
      const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
      while (face < 0.1 && solid.at(mx + nx * (face + 0.002), my + ny * (face + 0.002))) face += 0.005;
    }
    return { kind: r.kind, a, b, u: [ux, uy], n: [nx, ny], len, face };
  });
}

function polygonArea2(p) {
  let a = 0;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) a += (p[j][0] - p[i][0]) * (p[j][1] + p[i][1]);
  return a / 2;
}

/** principal axis of a polygon's points: centre, direction u, extents along u and across */
function axisOf(poly) {
  let cx = 0, cy = 0;
  for (const [x, y] of poly) (cx += x), (cy += y);
  cx /= poly.length;
  cy /= poly.length;
  let sxx = 0, syy = 0, sxy = 0;
  for (const [x, y] of poly) (sxx += (x - cx) ** 2), (syy += (y - cy) ** 2), (sxy += (x - cx) * (y - cy));
  const ang = 0.5 * Math.atan2(2 * sxy, sxx - syy);
  const ux = Math.cos(ang), uy = Math.sin(ang);
  let t0 = Infinity, t1 = -Infinity, s0 = Infinity, s1 = -Infinity;
  for (const [x, y] of poly) {
    const t = (x - cx) * ux + (y - cy) * uy, s = -(x - cx) * uy + (y - cy) * ux;
    (t0 = Math.min(t0, t)), (t1 = Math.max(t1, t)), (s0 = Math.min(s0, s)), (s1 = Math.max(s1, s));
  }
  return { cx, cy, u: [ux, uy], v: [-uy, ux], t0, t1, s0, s1 };
}

// ---------- the floor ----------

/**
 * @param towerKey 'V' | 'B'
 * @param floor floor number
 * @param apts apartments of this floor (data.js)
 * @param walk the apartment to walk around in (adds ceiling and lights), or null
 */
export function buildFloor(towerKey, floor, apts, walk = null) {
  const M = interiorMaterials();
  const tower = towerByKey[towerKey];
  const fl = tower.floors.find((f) => f.floor === floor);
  const plan = PLANS[fl.plan];
  const frame = planFrame(tower);
  const baseY = fl.z + tower.slab;
  const H = fl.h - 0.5; // clear height
  const glassTower = fl.plan.startsWith('A'); // block A: glass all round

  const group = new THREE.Group();
  group.position.set(frame.position.x, baseY, frame.position.z);
  group.rotation.y = frame.rotY;
  const own = [];
  const floorMeshes = [];
  const k = new Kit();
  const lights = []; // { pos: [x, y, z] in plan / height, room, kind }

  const solid = new PolyIndex();
  for (const w of plan.walls) solid.add(w, 'wall');
  for (const w of plan.struct) solid.add(w, 'wall');
  for (const w of plan.windows) solid.add(w, 'window');
  for (const w of plan.glazing) solid.add(w, 'glass');
  const roomsAt = new PolyIndex();
  for (const apt of apts) for (const room of apt.data.rooms) roomsAt.add(room.poly, 'room', { apt, room });
  for (const c of plan.common ?? []) roomsAt.add(c, 'common', null);
  const terraceAt = new PolyIndex();
  for (const apt of apts) for (const b of apt.data.balconies) terraceAt.add(b.poly, 'terrace', { apt, room: b });

  // collision outlines (plan segments): walls, windows and glazing, then doors and furniture
  const segments = [];
  const obstacles = []; // furniture and door leaves (for the checks in tools/)
  const notes = [];
  const addOutline = (p, what) => {
    if (what) obstacles.push({ what, poly: p });
    for (let i = 0, j = p.length - 1; i < p.length; j = i++) segments.push([p[j][0], p[j][1], p[i][0], p[i][1]]);
  };
  for (const list of [plan.walls, plan.struct, plan.windows, plan.glazing]) for (const p of list) addOutline(p);

  // the flats to fit out: all of them in the cut-away view, the visited one when walking
  const fitted = walk ? apts.filter((a) => a === walk) : apts;

  // ---- room floors and the shell ----
  // wet rooms (bathrooms, WCs): tiles up the walls, frosted glass, bathroom fittings; loggias and
  // terraces only get a tiled floor and stay open to the view (clear glass, a table and chairs)
  const wet = (room, apt) => ['bath', 'wc'].includes(room.kind) || (!['loggia', 'terrace'].includes(room.kind) &&
    (apt.data.furniture ?? []).some((it) => (it.type === 'toilet' || it.type === 'bath') && inside(room.poly, ...it.c)));
  const outdoor = (room) => ['loggia', 'terrace'].includes(room.kind);
  for (const apt of apts) {
    for (const room of apt.data.rooms) {
      room._wet = wet(room, apt);
      const g = flat(room.poly, 0.006);
      own.push(g);
      const m = new THREE.Mesh(g, room._wet || outdoor(room) ? M.tileFloor : M.floor);
      m.receiveShadow = true;
      m.userData = { apt, room };
      group.add(m);
      floorMeshes.push(m);
    }
    // balconies and terraces: a floor of their own (one can walk out onto them), a table and chairs
    for (const b of apt.data.balconies) {
      const g = flat(b.poly, 0.012);
      own.push(g);
      const m = new THREE.Mesh(g, M.balcony);
      m.receiveShadow = true;
      m.userData = { apt, room: b };
      group.add(m);
      floorMeshes.push(m);
      const t = balconyFurniture(k, M, b.poly);
      if (t && walk === apt) addOutline([[t[0] - 0.36, t[1] - 0.36], [t[0] + 0.36, t[1] - 0.36], [t[0] + 0.36, t[1] + 0.36], [t[0] - 0.36, t[1] + 0.36]], 'table');
    }
  }
  for (const c of plan.common ?? []) k.world().add(M.corridor, flat(c, 0.004));

  for (const w of plan.walls) k.world().add(M.wall, prism(w, 0, H));
  for (const w of plan.struct) k.world().add(M.struct, prism(w, 0, H));
  const openings = new Map(plan.windows.map((w) => [w, windowOpening(w, solid)]));
  for (const w of plan.windows) {
    k.world().add(M.wall, prism(openings.get(w).poly, 0, SILL));
    k.world().add(M.wall, prism(openings.get(w).poly, H - HEAD, H));
  }

  // ---- windows: glass (frosted in bathrooms), frames, sills, curtains ----
  const roomOf = (x, y) => roomsAt.at(x, y)?.data ?? null;
  // what the drawn furniture covers: no radiator or curtain where a piece stands against the window
  const drawnFloor = fitted.flatMap((a) => (a.data.furniture ?? []).flatMap(drawnFootprints));
  const covered = (poly) => drawnFloor.some((q) => overlaps(poly, q));
  for (const w of plan.windows) {
    const ax = openings.get(w).ax;
    const thick = ax.s1 - ax.s0, mid = (ax.s0 + ax.s1) / 2;
    // which side is the room?
    let n = null, owner = null;
    for (const sgn of [1, -1]) {
      const d = sgn > 0 ? ax.s1 + 0.15 : ax.s0 - 0.15;
      const r = roomOf(ax.cx + ax.v[0] * d, ax.cy + ax.v[1] * d);
      if (r) { n = [ax.v[0] * sgn, ax.v[1] * sgn]; owner = r; break; }
    }
    const glass = owner?.room._wet ? M.frosted : M.glass;
    k.world().add(glass, prism(openings.get(w).poly, SILL, H - HEAD));
    if (!n) continue;
    const fitHere = fitted.includes(owner.apt);
    // segment along the window at the middle of the wall
    const P = (t, s) => [ax.cx + ax.u[0] * t + ax.v[0] * s, ax.cy + ax.u[1] * t + ax.v[1] * s];
    const a = P(ax.t0, mid), b = P(ax.t1, mid), len = ax.t1 - ax.t0;
    // (the frame runs 3 cm on into the walls at its ends: where the drawn opening stops short of
    // the wall, no slit of sky shows beside the frame)
    windowFrame(k, M, P(ax.t0 - 0.03, mid), P(ax.t1 + 0.03, mid), n, len + 0.06, SILL, H - HEAD);
    // sill board, flush with the inside face and a little proud of it
    const inner = n[0] * ax.v[0] + n[1] * ax.v[1] > 0 ? ax.s1 : ax.s0;
    const ia = P(ax.t0, inner), ib = P(ax.t1, inner);
    slab(k, M.sill, ia, ib, n, -thick / 2 + 0.04, thick / 2 - 0.04 + 0.05, SILL - 0.02, SILL + 0.005, 0.03);
    const along = (t0, t1, z0, z1) => {
      const at = (t, z) => [ia[0] + ((ib[0] - ia[0]) * t) / len + n[0] * z, ia[1] + ((ib[1] - ia[1]) * t) / len + n[1] * z];
      return [at(t0, z0), at(t1, z0), at(t1, z1), at(t0, z1)];
    };
    const cw = Math.min(0.55, len * 0.3);
    if (fitHere && ['living', 'bedroom'].includes(owner.room.kind) && !covered(along(-0.3, cw, 0.08, 0.2)) && !covered(along(len - cw, len + 0.3, 0.08, 0.2))) curtains(k, M, ia, ib, n, H, len);
    const rw = Math.min(len * 0.75, 1.6);
    // (none on the loggias: they are not heated)
    if (fitHere && !owner.room._wet && !['loggia', 'terrace'].includes(owner.room.kind) && len > 0.7 &&
      !covered(along((len - rw) / 2 - 0.08, (len + rw) / 2 + 0.08, 0.02, 0.16))) radiator(k, M, ia, ib, n, len);
  }
  // floor-to-ceiling glazing (tower A): along each room's own edge, one curtain wall in one rhythm -
  // a pane a few centimetres out, black rails at the floor and the ceiling, mullions at its ends and
  // every metre and a half. (Drawn as the plan's glazing blocks, which run on to the facade line,
  // the blocks' ends stood in the rooms as panes of glass and the frames came out on some panes
  // only.) Between a room and its loggia or terrace the pane is the room's; glazing no room
  // borders is drawn as before.
  const claimed = new Set();
  for (const apt of apts) {
    for (const room of apt.data.rooms) {
      const runs = edgeRuns(room, solid);
      runs.forEach((r, i) => {
        if (r.kind !== 'glass' || r.len < 0.12) return;
        const mid = [(r.a[0] + r.b[0]) / 2, (r.a[1] + r.b[1]) / 2];
        const g = solid.at(mid[0] - r.n[0] * 0.06, mid[1] - r.n[1] * 0.06);
        if (g) claimed.add(g.poly);
        let beyond = null;
        for (let d = 0.12; d < 0.9 && !beyond; d += 0.06) beyond = roomsAt.at(mid[0] - r.n[0] * d, mid[1] - r.n[1] * d);
        const outdoorHere = room.kind === 'loggia' || room.kind === 'terrace';
        if (outdoorHere && beyond?.kind === 'room' && !['loggia', 'terrace'].includes(beyond.data.room.kind)) return;
        curtainWall(k, M, r.a, r.b, r.n, H);
        // sheer curtains gathered where the glass meets a wall, in the living rooms and bedrooms
        if (fitted.includes(apt) && ['living', 'bedroom', 'kitchen'].includes(room.kind)) {
          for (const [end, nb, sgn] of [[r.a, runs[(i - 1 + runs.length) % runs.length], 1], [r.b, runs[(i + 1) % runs.length], -1]]) {
            if (nb.kind !== 'wall' || r.len < 1.2) continue;
            const c = [end[0] + r.u[0] * sgn * 0.32 + r.n[0] * 0.16, end[1] + r.u[1] * sgn * 0.32 + r.n[1] * 0.16];
            k.at(c[0], c[1], Math.atan2(r.n[1], r.n[0]));
            F.curtain(k, M.sheer, 0.55, H - 0.05, 0.015);
          }
        }
      });
    }
  }
  for (const w of plan.glazing) {
    if (claimed.has(w)) continue;
    k.world().add(M.glass, prism(w, 0, H));
    glazingFrame(k, M, w, H, roomOf, fitted, (x, y) => (solid.at(x, y)?.kind === 'glass' ? solid.at(x, y) : null));
  }

  // ---- the lifts: the cars in their shafts as drawn, the doors on the hall side ----
  const liftTags = [];
  const halls = [];
  for (const lf of plan.lifts ?? []) {
    const face = lift(k, M, lf, H, solid);
    // lifts side by side with their doors the same way share a hall: one tag for them
    const near = halls.find((g) => Math.abs(g.f - lf.f) < 0.1 && g.lifts.some((o) => dist(o.c, lf.c) < 3.2));
    if (near) near.lifts.push({ ...lf, face });
    else halls.push({ f: lf.f, lifts: [{ ...lf, face }] });
  }
  for (const g of halls) {
    const fs = g.lifts.map((l) => l.face ?? l.c);
    const at = [fs.reduce((a, p) => a + p[0], 0) / fs.length, fs.reduce((a, p) => a + p[1], 0) / fs.length];
    const sc = frame.toScene(at[0], at[1]);
    liftTags.push({ x: sc.x, y: baseY + H + 0.4, z: sc.z, q: g.lifts.map((l) => l.q) });
  }

  // ---- per room: what is behind each edge; doors; skirting and tiles ----
  // (keepout: plan polygons furniture must stay out of - door swings, the way through openings)
  const doors = [], leaves = []; // centres of the doorways fitted so far, and of those with a leaf
  const keepout = []; // plan polygons furniture must stay out of (door swings)
  // ways to walk (door zones, swings, the space in front of a piece) may overlap one another;
  // furniture may stand in none of them. Each belongs to its room: a swing's way round the leaf
  // that reaches through the wall does not keep the furniture of the next room away
  const way = (q, room) => Object.assign(q, { way: true, room });
  const roomInfo = new Map();
  // doors open into the rooms rather than into the hall, but out of the small rooms (bathrooms,
  // WCs, wardrobes, loggias), where an open leaf would stand in the way
  const order = (r) => (['bath', 'wc', 'storage', 'loggia'].includes(r.kind) ? 2 : r.kind === 'hall' ? 1 : 0);
  // ...unless the drawing says otherwise: the side each drawn door opens to ([x, y] of the doorway,
  // [x, y] half a metre into that side)
  const swingAt = (c) => {
    let best = null, bd = 0.75;
    for (const q of plan.swings ?? []) {
      const d = Math.hypot(q[0] - c[0], q[1] - c[1]);
      if (d < bd) [best, bd] = [q, d];
    }
    return best;
  };
  const later = []; // leaves the drawing puts in the room on the other side, hung after all rooms
  const leafPlans = []; // the leaves decided on (and their other hinge), built once all are in
  const entrances = []; // the doors into each flat: { apt, room, common, mid, n (into the room), s1 }
  const pending = []; // openings in a room's outline that made no doorway: { apt, room, r }
  const doorSpans = []; // the doorways made: { a, b, u, n, len } (the run of the room they were made from)
  // first pass: what is round each room, and a clear zone in front of every opening
  const zones = []; // { poly, mid }
  for (const apt of apts) {
    for (const room of apt.data.rooms) {
      const runs = edgeRuns(room, solid);
      roomInfo.set(room, runs);
      for (const r of runs) {
        if (r.kind !== 'open' || r.len < 0.45) continue;
        // a doorway keeps its whole width clear; a wide open-plan opening only a 1.1 m way through
        // its middle (furniture may stand along the rest of it, as in any open-plan room)
        const e = 0.15, d = 0.95;
        let a = [r.a[0] - r.u[0] * e, r.a[1] - r.u[1] * e], b = [r.b[0] + r.u[0] * e, r.b[1] + r.u[1] * e];
        if (r.len > 1.3) {
          const m = [(r.a[0] + r.b[0]) / 2, (r.a[1] + r.b[1]) / 2];
          a = [m[0] - r.u[0] * 0.55, m[1] - r.u[1] * 0.55];
          b = [m[0] + r.u[0] * 0.55, m[1] + r.u[1] * 0.55];
        }
        const poly = [a, b, [b[0] + r.n[0] * d, b[1] + r.n[1] * d], [a[0] + r.n[0] * d, a[1] + r.n[1] * d]];
        keepout.push(way(poly, room));
        zones.push({ poly, mid: [(r.a[0] + r.b[0]) / 2, (r.a[1] + r.b[1]) / 2] });
      }
    }
  }
  // doors: door-wide gaps in the walls. Returns the wall's band [s0, s1] (along n) when a
  // doorway was made. `band`: the band to use where the gap's ends find no wall
  const doorway = (apt, room, r, band = null) => {
    if (r.kind !== 'open' || r.len < 0.55 || r.len > 1.3) return null;
    const fit = fitted.includes(apt);
    // what is across the gap: a room of this flat, a loggia, the corridor, another flat
    const mx0 = (r.a[0] + r.b[0]) / 2, my0 = (r.a[1] + r.b[1]) / 2;
    let across = null, depth = null;
    for (let d = 0.04; d <= 0.8; d += 0.02) {
      const hit = roomsAt.at(mx0 - r.n[0] * d, my0 - r.n[1] * d) ?? terraceAt.at(mx0 - r.n[0] * d, my0 - r.n[1] * d);
      if (hit) {
        [across, depth] = [hit, d];
        break;
      }
    }
    if (!across) return null; // nothing across: a hole to the outside, closed later
    if (across.kind === 'room' && across.data.apt !== apt) return null; // into another flat: walled up later
    const glazed = across.kind === 'terrace' || (across.kind === 'room' && ['loggia', 'terrace'].includes(across.data.room.kind)) ||
      ['loggia', 'terrace'].includes(room.kind);
    // the slot through the wall: where the wall ends beside the gap, across its thickness
    // (s along n, 0 = this run; the outline may run along the wall face or inside the gap).
    // The wall beside it is looked for up to 20 cm on: door frames are drawn wider than the gap;
    // beside a balcony door the window counts as wall
    const solidKind = (q) => {
      const k = solid.at(q[0], q[1])?.kind;
      return k === 'wall' || (glazed && (k === 'window' || k === 'glass'));
    };
    const side = (p, sgn, s) => [0.05, 0.1, 0.15, 0.2].some((e) => solidKind([p[0] - r.u[0] * e * sgn + r.n[0] * s, p[1] - r.u[1] * e * sgn + r.n[1] * s]));
    const scan = (test) => {
      let s0 = null, s1 = null;
      for (let s = -0.7; s <= 0.3; s += 0.01) {
        if (test(s)) {
          if (s0 === null) s0 = s;
          s1 = s;
        } else if (s0 !== null && s1 > -0.02) break;
        else if (s0 !== null) s0 = s1 = null;
      }
      return s0 !== null && s1 - s0 >= 0.05 ? [s0, s1] : null;
    };
    // wall on both sides; else (a door in a corner) on one side; else the band given; else the
    // gap between this room and the one across
    let got = scan((s) => side(r.a, 1, s) && side(r.b, -1, s)) ?? scan((s) => side(r.a, 1, s) || side(r.b, -1, s)) ?? band;
    if (!got && depth > 0.06) got = [-depth + 0.02, 0];
    if (!got) return null;
    let [s0, s1] = got;
    s0 -= 0.005;
    s1 += 0.005;
    const mx = mx0, my = my0, sm = (s0 + s1) / 2;
    // the door's pieces (frame, casings, leaf, the wall over it) go where the walls end beside the
    // opening, in the middle of their thickness: the gap drawn in each room's outline can be a
    // centimetre or two off them, and differently on the two sides of one wall (23.10.2026: frames
    // and leaves stood off their walls). The doorway itself (what the outline is checked against)
    // stays the drawn gap.
    const r0 = r;
    {
      const jamb = (sgn) => {
        for (let t = 0; t <= r0.len / 2 + 0.04; t += 0.005) {
          if (solidKind([mx + r0.u[0] * sgn * t + r0.n[0] * sm, my + r0.u[1] * sgn * t + r0.n[1] * sm])) return t;
        }
        return null;
      };
      const ta = jamb(-1), tb = jamb(1);
      // (only the small misses of the drawing, up to 3.5 cm: a wider difference is a glazed door
      // beside a window or a door in a corner, left as drawn)
      const a = ta !== null && Math.abs(ta - r0.len / 2) < 0.035 ? [mx - r0.u[0] * ta, my - r0.u[1] * ta] : r0.a;
      const b = tb !== null && Math.abs(tb - r0.len / 2) < 0.035 ? [mx + r0.u[0] * tb, my + r0.u[1] * tb] : r0.b;
      r = { ...r0, a, b, len: dist(a, b) };
    }
    const behind = roomsAt.at(mx + r.n[0] * (s0 - 0.15), my + r.n[1] * (s0 - 0.15)) ?? across;
    const entrance = !behind || behind.kind === 'common' || (behind.kind === 'room' && behind.data.apt !== apt);
    // (a flat has one front door: a second way to the corridor is walled up)
    if (entrance && entrances.some((e) => e.apt === apt)) return null;
    const centre = [mx + r.n[0] * sm, my + r.n[1] * sm];
    if (entrance) entrances.push({ apt, room, common: !behind || behind.kind === 'common', mid: [mx, my], n: r.n, s1 });
    const shift = (p, s) => [p[0] + r.n[0] * s, p[1] + r.n[1] * s];
    const face = { ...r, a: shift(r.a, s1), b: shift(r.b, s1) };
    doorSpans.push({ a: r0.a, b: r0.b, u: r0.u, n: r0.n, len: r0.len, apt: apt.id, room: room.kind, across: across.kind === 'room' ? across.data.room.kind : across.kind, entrance, band: [s0, s1],
      rooms: [room, across.kind === 'room' ? across.data.room : null], aptObj: apt });
    // casing on this side of the wall
    casing(k, entrance ? M.entrance : glazed ? M.frame : M.skirting, face);
    // the same doorway seen from the room on its other side: the wall over it once, the leaf
    // in whichever room it fits first
    const seen = (list) => list.some((c) => dist(c, centre) < 0.45);
    if (!seen(doors)) {
      doors.push(centre);
      // (4 cm into the walls on either side: no hairline at its ends)
      slab(k, M.wall, shift(r.a, s0), shift(r.b, s0), r.n, 0, s1 - s0, DOOR_H, H, 0.04);
      // the door frame through the wall (23.10.2026: a slit showed beside the leaf and where the
      // drawn gap stops short of the wall's end): its sides 1.5 cm into the opening and 3 cm on into
      // the wall's end, its head under the wall over the door
      lining(k, entrance ? M.entrance : glazed ? M.frame : M.skirting, r, s0, s1);
    }
    if (seen(leaves)) return [s0, s1];
    if (entrance) {
      // the flat's front door: shut, in the middle of the wall, a walnut leaf with a frame on both
      // sides and a mat inside - from above and from inside it shows where the flat begins (an open
      // leaf did not, and where one did not fit there was only an empty frame)
      leaves.push(centre);
      if (fit || !walk) frontDoor(k, M, r, s0, s1);
      // (its collision on the wall's face in the flat: the visitor stops a step short of the leaf,
      // inside the flat, not on the threshold)
      const A = shift(r.a, s1), B = shift(r.b, s1);
      segments.push([A[0], A[1], B[0], B[1]]);
      obstacles.push({ what: 'front door', poly: [A, B] });
      // (it opens into the flat: its swing kept clear of furniture)
      keepout.push(way([shift(r.a, s1), shift(r.b, s1), shift(r.b, s1 + r.len), shift(r.a, s1 + r.len)], room));
      return [s0, s1];
    }
    // the leaf, open 90 degrees into this room, hinged at the end nearer a corner; the drawing
    // opens this door into the room on the other side: the leaf goes there (or back here, once
    // every room is done, if it does not fit there)
    const otherRoom = across.kind === 'room' ? across.data.room : null;
    const drawn = swingAt(centre);
    if (drawn && (drawn[2] - drawn[0]) * r.n[0] + (drawn[3] - drawn[1]) * r.n[1] < 0 && across.kind === 'room') {
      later.push({ centre, hang: () => hang(room, r, face, centre, entrance, s0, s1, fit, glazed, otherRoom) });
      return [s0, s1];
    }
    hang(room, r, face, centre, entrance, s0, s1, fit, glazed, otherRoom);
    return [s0, s1];
  };
  // one front door per flat: where a flat has two door-wide gaps to the corridor (a piece of wall
  // the drawing leaves unfilled next to the entrance), the one with the door drawn at it - else
  // the hall's - is the door, the other is walled up
  const notFront = new Set();
  for (const apt of apts) {
    const cands = [];
    for (const room of apt.data.rooms) {
      for (const r of roomInfo.get(room)) {
        if (r.kind !== 'open' || r.len < 0.55 || r.len > 1.3) continue;
        const m = [(r.a[0] + r.b[0]) / 2, (r.a[1] + r.b[1]) / 2];
        let hit = null;
        for (let d = 0.04; d <= 0.8 && !hit; d += 0.02) hit = roomsAt.at(m[0] - r.n[0] * d, m[1] - r.n[1] * d);
        if (hit?.kind === 'common') cands.push({ r, room, swing: !!swingAt(m), hall: room.kind === 'hall', fit: Math.abs(r.len - 1.0) });
      }
    }
    if (cands.length < 2) continue;
    cands.sort((p, q) => q.swing - p.swing || q.hall - p.hall || p.fit - q.fit);
    for (const c of cands.slice(1)) notFront.add(c.r);
  }
  for (const apt of apts) {
    const fit = fitted.includes(apt);
    for (const room of [...apt.data.rooms].sort((p, q) => order(p) - order(q))) {
      const runs = roomInfo.get(room);
      for (const r of runs) {
        if (r.kind === 'wall' || r.kind === 'window') {
          if (room._wet) slab(k, M.tileWall, r.a, r.b, r.n, r.face, 0.008, 0, r.kind === 'window' ? SILL : H);
          else slab(k, M.skirting, r.a, r.b, r.n, r.face, 0.014, 0, 0.08);
          if (room._wet && r.kind === 'window') slab(k, M.tileWall, r.a, r.b, r.n, r.face, 0.008, H - HEAD, H);
        }
      }
      for (const r of runs) {
        if (r.kind !== 'open') continue;
        if (r.len <= 1.3) {
          if (notFront.has(r) || !doorway(apt, room, r)) pending.push({ apt, room, r });
          continue;
        }
        // (wider: an open plan, or a doorway in a wall the drawing leaves unfilled: see below)
        pending.push({ apt, room, r });
      }
    }
  }

  // ---- the openings that are no doorway: closed the way the drawing means them ----
  // The sheets draw every room closed by walls, some of them as thin lines the extraction does not
  // read: a slit between walls, a stretch with nothing across (a hole to the outside), an opening
  // into another flat or the corridor, a wide opening between two rooms - walled up, with the
  // doors the drawing has in them (and a door wherever a room would else have no way in). A hole
  // to the outside of a room: glazed to the ceiling (the corner bays, French windows); towards a
  // loggia or terrace: glazed, with a glass door; the open edge of a loggia: a parapet.
  const OUTDOOR = new Set(['loggia', 'terrace']);
  const gaps = []; // for the checks: { apt, room, r, across, other, depth, done }
  const fillers = []; // plan polygons of what was put into the openings (each opening once)
  const along = (r, t) => [r.a[0] + r.u[0] * t, r.a[1] + r.u[1] * t];
  const out = (q, r, s) => [q[0] - r.n[0] * s, q[1] - r.n[1] * s];
  const filled = (r, t0, t1, thick) => fillers.some((f) => inside(f, ...out(along(r, (t0 + t1) / 2), r, thick / 2)));
  const piece = (r, t0, t1, thick) => {
    const A = along(r, t0 - 0.015), B = along(r, t1 + 0.015);
    return { A, B, poly: [A, B, out(B, r, thick), out(A, r, thick)] };
  };
  const wallUp = (room, r, t0, t1, thick) => {
    if (filled(r, t0, t1, thick)) return;
    const { A, B, poly } = piece(r, t0, t1, thick);
    fillers.push(poly);
    // (5 mm into the room: no hairline left where the wall meets the floor and the next wall)
    slab(k, M.wall, A, B, r.n, -thick, thick + 0.005, 0, H);
    if (room._wet) slab(k, M.tileWall, A, B, r.n, 0, 0.008, 0, H);
    else slab(k, M.skirting, A, B, r.n, 0, 0.014, 0, 0.08);
    addOutline(poly);
  };
  const glazeUp = (room, r, t0, t1, thick) => {
    if (filled(r, t0, t1, thick)) return;
    const { A, B, poly } = piece(r, t0, t1, thick);
    fillers.push(poly);
    const mid = -thick / 2;
    slab(k, M.glass, A, B, r.n, mid - 0.005, 0.01, 0, H);
    slab(k, M.frame, A, B, r.n, mid - 0.035, 0.07, 0, 0.09);
    slab(k, M.frame, A, B, r.n, mid - 0.035, 0.07, H - 0.07, H);
    const L = dist(A, B), u = r.u;
    const posts = Math.max(1, Math.round(L / 1.2));
    for (let i = 0; i <= posts; i++) {
      const t = (L * i) / posts, c = [A[0] + u[0] * t, A[1] + u[1] * t];
      slab(k, M.frame, [c[0] - u[0] * 0.03, c[1] - u[1] * 0.03], [c[0] + u[0] * 0.03, c[1] + u[1] * 0.03], r.n, mid - 0.04, 0.08, 0, H);
    }
    if (thick > 0.12) {
      // the reveal round it: wall above nothing, a sill board at the floor
      slab(k, M.sill, A, B, r.n, mid + 0.035, Math.min(0.05, -mid - 0.035), 0, 0.02);
    }
    addOutline(poly);
  };
  const glassUp = (room, r, t0, t1) => {
    if (filled(r, t0, t1, 0.12)) return;
    const { A, B, poly } = piece(r, t0, t1, 0.12);
    fillers.push(poly);
    curtainWall(k, M, A, B, r.n, H);
    addOutline(poly);
  };
  const railing = (room, r, t0, t1) => {
    if (filled(r, t0, t1, 0.12)) return;
    const { A, B, poly } = piece(r, t0, t1, 0.12);
    fillers.push(poly);
    slab(k, M.frame, A, B, r.n, -0.09, 0.07, 0, 0.1);
    slab(k, M.glass, A, B, r.n, -0.06, 0.012, 0.1, 1.05);
    slab(k, M.frame, A, B, r.n, -0.095, 0.08, 1.05, 1.1);
    addOutline(poly);
  };
  const parapet = (room, r, t0, t1) => {
    if (filled(r, t0, t1, 0.12)) return;
    const { A, B, poly } = piece(r, t0, t1, 0.12);
    fillers.push(poly);
    slab(k, M.wall, A, B, r.n, -0.12, 0.125, 0, 1.0);
    slab(k, M.sill, A, B, r.n, -0.14, 0.16, 1.0, 1.04);
    addOutline(poly);
  };
  // what is across each opening, and the stretches of it that no doorway covers (a doorway made
  // from the other side, or a door of a wide opening)
  const items = pending.map(({ apt, room, r }) => {
    const L = r.len, mid = along(r, L / 2);
    let across = 'outside', other = null, depth = null;
    for (let d = 0.04; d <= 0.8; d += 0.02) {
      const q = out(mid, r, d);
      const hit = roomsAt.at(...q);
      if (hit) {
        across = hit.kind === 'common' ? 'common' : hit.data.apt === apt ? 'same' : 'other';
        other = hit.kind === 'common' ? null : hit.data.room;
        depth = d;
        break;
      }
      const ter = terraceAt.at(...q);
      if (ter) {
        [across, other, depth] = ['terrace', ter.data.room, d];
        break;
      }
      if (solid.at(...q)) {
        [across, depth] = ['solid', d];
        break;
      }
    }
    return { apt, room, r, L, mid, across, other, depth, thick: depth ? Math.min(0.7, Math.max(0.04, depth)) : 0.25 };
  });
  const freeOf = (it) => {
    const { r, L } = it;
    let free = [[0, L]];
    for (const ds of doorSpans) {
      if (Math.abs(ds.u[0] * r.u[0] + ds.u[1] * r.u[1]) < 0.95) continue;
      const ta = (ds.a[0] - r.a[0]) * r.u[0] + (ds.a[1] - r.a[1]) * r.u[1], tb = (ds.b[0] - r.a[0]) * r.u[0] + (ds.b[1] - r.a[1]) * r.u[1];
      const da = (ds.a[0] - r.a[0]) * r.n[0] + (ds.a[1] - r.a[1]) * r.n[1];
      if (Math.abs(da) > 0.9) continue;
      const [c0, c1] = [Math.min(ta, tb) - 0.03, Math.max(ta, tb) + 0.03];
      free = free.flatMap(([f0, f1]) => (c1 <= f0 || c0 >= f1 ? [[f0, f1]] : [[f0, Math.max(f0, c0)], [Math.min(f1, c1), f1]].filter(([x0, x1]) => x1 - x0 > 0.015)));
    }
    return free;
  };
  // a door in a stretch of an opening, centred at t (the drawing's door width, about 0.9 m)
  const doorIn = (it, tc, w) => {
    const { apt, room, r, L, thick } = it;
    const t0 = Math.max(0, tc - w / 2), t1 = Math.min(L, tc + w / 2);
    return t1 - t0 >= 0.55 && doorway(apt, room, { ...r, a: along(r, t0), b: along(r, t1), len: t1 - t0 }, [-thick + 0.02, 0]);
  };
  // 1. the doors the drawing has in wide openings (between rooms, or the entrance in a stretch
  //    of wall the drawing leaves unfilled)
  for (const it of items) {
    if ((it.across !== 'same' && it.across !== 'common') || notFront.has(it.r)) continue;
    for (const q of plan.swings ?? []) {
      const { r } = it;
      const t = (q[0] - r.a[0]) * r.u[0] + (q[1] - r.a[1]) * r.u[1], d = (q[0] - r.a[0]) * r.n[0] + (q[1] - r.a[1]) * r.n[1];
      if (Math.abs(d) > 0.7 || t < -0.2 || t > it.L + 0.2) continue;
      const f = freeOf(it).find(([f0, f1]) => t > f0 - 0.2 && t < f1 + 0.2 && f1 - f0 >= 0.55);
      if (f) doorIn(it, Math.min(Math.max(t, f[0] + 0.45), f[1] - 0.45), it.across === 'common' ? 0.96 : 0.9);
    }
  }
  // 2. every room of a flat can be walked into: where a room has no doorway to the rest of its
  //    flat, a door in the longest stretch of opening between them
  for (const apt of apts) {
    // (the small service loggias, up to 2.6 m2, are closed off on the drawings: no door needed)
    const rooms = apt.data.rooms.filter((rm) => !OUTDOOR.has(rm.kind) || rm.area > 2.6);
    for (let round = 0; round < 6; round++) {
      const reached = new Set(doorSpans.filter((d) => d.aptObj === apt && d.entrance).map((d) => d.rooms[0]));
      if (!reached.size) break;
      let grew = true;
      while (grew) {
        grew = false;
        for (const d of doorSpans) {
          if (d.aptObj !== apt || !d.rooms[1]) continue;
          const [p, q] = d.rooms;
          // (no way on through a small service loggia: it is closed off)
          const through = (x) => !(OUTDOOR.has(x.kind) && x.area <= 2.6);
          if (reached.has(p) !== reached.has(q) && through(reached.has(p) ? p : q)) {
            reached.add(p);
            reached.add(q);
            grew = true;
          }
        }
      }
      const lost = rooms.filter((rm) => !reached.has(rm));
      if (!lost.length) break;
      let made = false;
      for (const rm of lost) {
        const cands = items.filter((it) => it.apt === apt && it.across === 'same' &&
          ((it.room === rm && reached.has(it.other)) || (it.other === rm && reached.has(it.room))))
          .flatMap((it) => freeOf(it).map((f) => ({ it, f })))
          .filter(({ f }) => f[1] - f[0] >= 0.75)
          .sort((p, q) => (q.f[1] - q.f[0]) - (p.f[1] - p.f[0]));
        if (cands.length && doorIn(cands[0].it, (cands[0].f[0] + cands[0].f[1]) / 2, 0.9)) made = true;
      }
      if (!made) break;
    }
  }
  // 2b. a way out onto every terrace (on the top floors of blocks Б and Г the terraces lie behind
  //     glass walls the drawing gives no door in): a glazed door in the longest opening towards
  //     the terrace, from the living room if it has one
  for (const apt of apts) {
    for (const b of apt.data.balconies) {
      if (b.area < 3) continue;
      const mid = (d) => [(d.a[0] + d.b[0]) / 2, (d.a[1] + d.b[1]) / 2];
      // (a door from a room: the service loggia's door onto the terrace is no way out to it)
      if (doorSpans.some((d) => d.aptObj === apt && d.across === 'terrace' && !OUTDOOR.has(d.room) && distToPolygon(b.poly, ...mid(d)) < 0.8)) continue;
      const cands = items.filter((it) => it.apt === apt && it.across === 'terrace' && it.other === b && !OUTDOOR.has(it.room.kind))
        .flatMap((it) => freeOf(it).map((f) => ({ it, f, len: f[1] - f[0] + (it.room.kind === 'living' ? 10 : 0) })))
        .filter(({ f }) => f[1] - f[0] >= 0.9)
        .sort((p, q) => q.len - p.len);
      if (cands.length) doorIn(cands[0].it, (cands[0].f[0] + cands[0].f[1]) / 2, 0.9);
    }
  }
  // 3. the rest closed: walls, glazing towards the outside and the loggias, parapets
  for (const it of items) {
    const { apt, room, r, across, other, depth, thick } = it;
    const free = freeOf(it);
    let done;
    const k1 = room.kind, k2 = other?.kind;
    if (!free.length) done = 'doorways';
    else if (OUTDOOR.has(k1) && (across === 'outside' || across === 'terrace')) {
      // tower A is glass all round (render 4): its small loggias (the air conditioners' ones) are
      // behind the curtain wall, its terraces have glass railings; the slab blocks' loggias and
      // terraces keep their parapets
      const close = !glassTower ? parapet : k1 === 'loggia' ? glassUp : railing;
      for (const [t0, t1] of free) close(room, r, t0, t1);
      done = !glassTower ? 'parapet' : k1 === 'loggia' ? 'glazed' : 'railing';
    } else {
      const glassy = across === 'outside' || across === 'terrace' || (across === 'same' && (OUTDOOR.has(k2) || OUTDOOR.has(k1)));
      for (const [t0, t1] of free) {
        if (glassy && t1 - t0 >= 0.55) glazeUp(room, r, t0, t1, across === 'outside' ? 0.12 : thick);
        else wallUp(room, r, t0, t1, thick);
      }
      done = glassy ? 'glazed' : 'walled';
    }
    gaps.push({ apt, room, r, across, other, depth, done });
  }
  for (const d of later) if (!leaves.some((c) => dist(c, d.centre) < 0.45)) d.hang();
  settleLeaves();
  for (const L of leafPlans) buildLeaf(L);

  // the leaf of a doorway, open 90 degrees into `room`, hinged at the end nearer a corner (both
  // hinges that fit are kept: settleLeaves may turn it round)
  function hang(room, r, face, centre, entrance, s0, s1, fit, glazed = false, other = null) {
    const leafW = r.len - 0.03;
    // hinge on the side with the shorter stretch of wall to the next corner, so the open leaf
    // stands near that corner; the open leaf has to stand inside the room
    const reach = (p, sgn) => {
      let d = 0;
      while (d < 3 && solid.at(p[0] - r.u[0] * sgn * (d + 0.05) + r.n[0] * (s1 - 0.03), p[1] - r.u[1] * sgn * (d + 0.05) + r.n[1] * (s1 - 0.03))) d += 0.1;
      return d;
    };
    const ends = reach(r.a, 1) <= reach(r.b, -1) ? [true, false] : [false, true];
    // (into this room first; then, for settleLeaves, into the room across, from the far face)
    const sides = [[room, face, r.n]];
    if (other) sides.push([other, { a: [r.a[0] + r.n[0] * s0, r.a[1] + r.n[1] * s0], b: [r.b[0] + r.n[0] * s0, r.b[1] + r.n[1] * s0] }, [-r.n[0], -r.n[1]]]);
    // the open leaf with its handles: a strip along it (no drawn piece may stand in it - a TV unit
    // by the door had the leaf behind it and its handle sticking out)
    const strip = (hh, tt, ww) => [
      [hh[0] - ww[0] * 0.04, hh[1] - ww[1] * 0.04], [tt[0] - ww[0] * 0.04, tt[1] - ww[1] * 0.04],
      [tt[0] + ww[0] * 0.12, tt[1] + ww[1] * 0.12], [hh[0] + ww[0] * 0.12, hh[1] + ww[1] * 0.12]];
    const tryAll = (strict) => {
      const out = [];
      for (const [into, fc, n] of sides) {
        for (const atA of ends) {
          const hh = atA ? fc.a : fc.b, ww = atA ? r.u : [-r.u[0], -r.u[1]];
          const tt = [hh[0] + n[0] * leafW, hh[1] + n[1] * leafW];
          // ...and leave room to walk round its edge (not across a narrow hall)
          // ...and not swing into the way to another doorway
          const P = (f) => [hh[0] + n[0] * leafW * f + ww[0] * 0.03, hh[1] + n[1] * leafW * f + ww[1] * 0.03];
          const ok = strict
            ? [0.5, 1, 1 + 0.75 / leafW].every((f) => inside(into.poly, ...P(f))) &&
              !zones.some((z) => dist(z.mid, centre) > 0.6 && [0.15, 0.5, 0.85, 1].some((f) => inside(z.poly, ...P(f))))
            : [0.5, 0.97].every((f) => inside(into.poly, ...P(f)));
          if (ok) out.push({ h: hh, w: ww, tip: tt, room: into, n, hits: drawnFloor.some((q) => overlaps(strip(hh, tt, ww), q)) });
        }
      }
      return out;
    };
    let options = tryAll(true);
    // (a door to a small loggia the leaf of which fits nowhere with room to pass round it: the
    // tests relaxed; failing that the leaf is shown shut - no doorway without its door)
    if (!options.some((o) => !o.hits)) options = [...options, ...tryAll(false)];
    options.sort((p, q) => p.hits - q.hits);
    if (!options.length || options[0].hits) {
      const sh = { a: [r.a[0] + r.n[0] * (s0 + s1) / 2, r.a[1] + r.n[1] * (s0 + s1) / 2], b: [r.b[0] + r.n[0] * (s0 + s1) / 2, r.b[1] + r.n[1] * (s0 + s1) / 2] };
      const shut = { h: [sh.a[0] + r.u[0] * 0.015, sh.a[1] + r.u[1] * 0.015], tip: [sh.b[0] - r.u[0] * 0.015, sh.b[1] - r.u[1] * 0.015], w: r.n, room, n: r.n, shut: true };
      if (!options.length) options = [shut];
      else options = [...options.filter((o) => !o.hits), shut, ...options.filter((o) => o.hits)];
    }
    leaves.push(centre);
    leafPlans.push({ r, entrance, glazed, fit, leafW, options, pick: 0 });
  }
  // Two doors in a small hall, both open: their leaves can meet and shut the hall off from one of
  // the rooms (no way between them). Where two leaves of a flat stand closer than a person's width,
  // the flat's rooms are walked to from its entrance, and the leaves there hinged the other way
  // round until every room reachable with no leaves at all is reachable with them.
  function settleLeaves() {
    const seg = (L) => { const o = L.options[L.pick]; return [o.h[0], o.h[1], o.tip[0], o.tip[1]]; };
    const gap = (A, B) => {
      const [a, b] = [seg(A), seg(B)];
      return Math.min(distToSegment(a[0], a[1], b[0], b[1], b[2], b[3]).d, distToSegment(a[2], a[3], b[0], b[1], b[2], b[3]).d,
        distToSegment(b[0], b[1], a[0], a[1], a[2], a[3]).d, distToSegment(b[2], b[3], a[0], a[1], a[2], a[3]).d);
    };
    for (const apt of apts) {
      const mine = leafPlans.filter((L) => L.options.some((o) => apt.data.rooms.includes(o.room)));
      const tight = mine.filter((A) => mine.some((B) => B !== A && gap(A, B) < 0.5));
      if (!tight.length) continue;
      const door = entranceOf(entrances, apt);
      const start = door?.inside ?? interiorPoint(entranceHall(apt).poly);
      const all = () => [...segments, ...mine.map(seg)];
      const most = reachableRooms(apt, segments, start).size;
      if (reachableRooms(apt, all(), start).size >= most) continue;
      // the hinges (and sides) that let the most of the flat be walked: rooms first, then floor
      // (a room may be reached at its doorway and no further)
      const score = () => reachableRooms(apt, all(), start).size * 1e6 + reachableRooms(apt, all(), start, true);
      let now = score();
      for (let round = 0; round < 3 && now < most * 1e6; round++) {
        for (const L of tight) {
          const was = L.pick;
          let best = now, pick = was;
          for (let i = 0; i < L.options.length; i++) {
            if (i === was || L.options[i].shut || (L.options[i].hits && !L.options[was].hits)) continue;
            L.pick = i;
            const n = score();
            if (n > best) [best, pick] = [n, i];
          }
          L.pick = pick;
          now = best;
        }
      }
    }
  }
  function buildLeaf({ r, entrance, glazed, fit, leafW, options, pick }) {
    const { h, w, tip, room, n, shut } = options[pick];
    if (fit || !walk) doorLeaf(k, M, h, tip, shut ? [w[0], w[1]] : w, entrance, glazed, shut);
    segments.push([h[0], h[1], tip[0], tip[1]]);
    obstacles.push({ what: shut ? 'door shut' : 'door', poly: [h, tip] });
    if (shut) return;
    const sx = w[0] * leafW, sy = w[1] * leafW;
    keepout.push(way([h, tip, [tip[0] + sx, tip[1] + sy], [h[0] + sx, h[1] + sy]], room));
    // and a way round the open leaf's edge (furniture right at its tip would shut the room off)
    const far = [h[0] + n[0] * (leafW + 0.7), h[1] + n[1] * (leafW + 0.7)];
    keepout.push(way([tip, far, [far[0] + sx, far[1] + sy], [tip[0] + sx, tip[1] + sy]], room));
    keepout.push(way([tip, far, [far[0] - w[0] * 0.65, far[1] - w[1] * 0.65], [tip[0] - w[0] * 0.65, tip[1] - w[1] * 0.65]], room));
  }

  // ---- furniture and fittings: as drawn; the rooms the drawing leaves empty, furnished here ----
  let walkBefore = null; // rooms of the walked flat reachable before any furniture (for the checks)
  for (const apt of fitted) {
    // in the flat being walked through, no room may be shut off by furniture: the way from the
    // entrance is checked, and what blocks it loses its collision (the smaller pieces first) or,
    // in the rooms furnished here, is furnished again with the essentials only (or left empty)
    const check = walk === apt;
    const door = entranceOf(entrances, apt);
    const start = check ? door?.inside ?? interiorPoint(entranceHall(apt).poly) : null;
    const before = check ? reachableRooms(apt, segments, start) : null;
    if (check) walkBefore = before;
    const drawnRooms = placeDrawn({ k, M, H, apt, solid, keepout, lights, ceiling: !!walk });
    // the drawn pieces' collisions, the smaller ones given up first if they shut a room off
    const mark0 = { seg: segments.length, obs: obstacles.length };
    for (let keepFrom = 0; keepFrom <= 4; keepFrom++) {
      for (const p of drawnRooms.solids) if (p.prio >= keepFrom) addOutline(p.poly, p.what);
      if (!check) break;
      const now = reachableRooms(apt, segments, start);
      if ([...before].every((i) => now.has(i))) break;
      segments.length = mark0.seg;
      obstacles.length = mark0.obs;
      if (keepFrom === 4) notes.push(`${apt.id}: drawn furniture shuts a room off even without collisions`);
    }
    // take back everything added after a mark (the kit's pieces, collisions, keep-out zones, lights)
    const mark = () => ({ kit: k.mark(), seg: segments.length, keep: keepout.length, obs: obstacles.length, lights: lights.length });
    const rollback = (m) => {
      k.rollback(m.kit);
      segments.length = m.seg;
      keepout.length = m.keep;
      obstacles.length = m.obs;
      lights.length = m.lights;
    };
    for (const room of apt.data.rooms) {
      if (drawnRooms.rooms.has(room) && !room._wet) {
        // furnished as drawn: only the light
        const ctx = { k, M, H, room, apt, keepout, lights, solid, ceiling: !!walk };
        if (walk) {
          const rug = drawnRooms.rugs.find((r) => inside(room.poly, ...r));
          const r = innerRect(room.poly, 0.06);
          const [px, py] = rug ?? [(r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2];
          const outdoors = ['loggia', 'terrace'].includes(room.kind);
          if (!outdoors && (['bedroom', 'living'].includes(room.kind) || !drawnRooms.lit.has(room))) pendant(ctx, px, py, 'drum');
          downlights(ctx);
        }
        continue;
      }
      // a clear way between every two openings of the room (doors, balcony doors, open plan):
      // kept free of furniture when the room, furnished freely, shuts the way through
      const walkways = () => {
        const out = [];
        const mids = (roomInfo.get(room) ?? []).filter((r) => r.kind === 'open' && r.len >= 0.45)
          .map((r) => [(r.a[0] + r.b[0]) / 2 + r.n[0] * 0.3, (r.a[1] + r.b[1]) / 2 + r.n[1] * 0.3]);
        for (let i = 0; i < mids.length; i++) {
          for (let j = i + 1; j < mids.length; j++) {
            const [a, b] = [mids[i], mids[j]];
            const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
            if (L < 0.3) continue;
            const nx = (-(b[1] - a[1]) / L) * 0.32, ny = ((b[0] - a[0]) / L) * 0.32;
            out.push(way([[a[0] + nx, a[1] + ny], [b[0] + nx, b[1] + ny], [b[0] - nx, b[1] - ny], [a[0] - nx, a[1] - ny]], room));
          }
        }
        return out;
      };
      const snap = mark();
      // full; the essentials (no wardrobe, no plant); full with clear walkways between the doors;
      // the essentials with walkways; and if all of them shut a room off or lose the main piece,
      // the essentials with walkways whatever is lost (a loggia must always stay reachable)
      const loggias = new Set();
      const tiers = [[false, false, false], [true, false, false], [false, true, false], [true, true, false], [true, true, true]];
      const notes0 = notes.length;
      for (const [sparse, ways, noLoggias] of tiers) {
        if (ways) keepout.push(...walkways());
        // (in the flat walked through: does every room it could be walked to before still stay so?)
        const open = check ? () => {
          const now = reachableRooms(apt, segments, start);
          return [...before].every((i) => now.has(i));
        } : null;
        const ctx = { k, M, H, room, apt, keepout, addOutline: (p) => addOutline(p, room.kind), lights, solid, runs: roomInfo.get(room), ceiling: !!walk, notes, sparse, mark, rollback, open };
        furnish(ctx);
        if (ctx.ceiling) downlights(ctx);
        if (!check) break;
        const now = reachableRooms(apt, segments, start);
        // a fit-out that lost the room's main piece (sofa, bed, kitchen) only counts on the last tiers
        const lost = notes.slice(notes0).some((n) => / no (place|wall) for /.test(n)) && !noLoggias;
        if (!lost && [...before].every((i) => now.has(i) || (noLoggias && loggias.has(i)))) break;
        rollback(snap);
        notes.length = notes0; // what furnish() said about this attempt no longer applies
        if (noLoggias) notes.push(`${room.kind} ${room.area} m²: left empty, to keep the way through`);
      }
    }
  }
  k.build(group, own);

  // ---- ceiling and lights for the walk ----
  let spawn = null, outline = null, reach = null;
  const lightObjects = [];
  if (walk) {
    outline = walk.data.outline;
    // (2 cm under the clear height: in tower A the slab of the floor above starts right there, and
    // its dark underside showed through the ceiling)
    const ceil = flat(plan.enclosure, H - CEIL);
    own.push(ceil);
    const c = new THREE.Mesh(ceil, M.ceiling);
    // (it casts the sun's shadow: between the walls' tops and the slab above, at a loggia, the sun
    // came in over the wall and through the ceiling, a bright streak on the wall)
    c.castShadow = true;
    group.add(c);
    // and a floor under the whole level, a few millimetres below the rooms' own: the rooms' outlines,
    // traced inside the walls, stop short of the door openings, where the grey slab showed through
    const under = flat(plan.enclosure, 0.0035);
    own.push(under);
    const u = new THREE.Mesh(under, M.floorUnder);
    u.receiveShadow = true;
    group.add(u);
    // one light per room, the biggest rooms first; shadows keep each room's light in the room
    const budget = HIGH ? 6 : 3, shadowed = HIGH ? 4 : 0;
    const byRoom = new Map();
    for (const l of lights) if (!byRoom.has(l.room) || l.main) byRoom.set(l.room, l);
    const chosen = [...byRoom.values()].sort((p, q) => q.room.area - p.room.area).slice(0, budget);
    chosen.forEach((l, i) => {
      const area = l.room.area;
      const range = Math.max(4, Math.sqrt(area) * 2.4);
      let light;
      if (l.spot) {
        // recessed downlights: one spot for the group, pointing down
        light = new THREE.SpotLight(0xffe2bf, THREE.MathUtils.clamp(area * 0.9, 4, 14), range, 1.1, 0.8, 2);
        light.target.position.set(l.x, 0, -l.y);
        group.add(light.target);
      } else {
        light = new THREE.PointLight(0xffdcb6, THREE.MathUtils.clamp(area * 0.36, 3, 9), range, 2);
      }
      light.position.set(l.x, l.z, -l.y);
      if (i < shadowed) {
        light.castShadow = true;
        light.shadow.mapSize.set(512, 512);
        light.shadow.bias = -0.003;
        light.shadow.normalBias = 0.02;
        light.shadow.radius = 3;
        light.shadow.camera.near = 0.03;
      }
      group.add(light);
      lightObjects.push(light);
    });

    // start just inside the entrance door, looking in (the way one walks in: what is on the right
    // on entering is on the right); where a wall is close ahead, turned to the most open view, but
    // never more than a right angle away from the way in
    const door = entranceOf(entrances, walk);
    const rooms = [...walk.data.rooms].sort((p, q) => q.area - p.area);
    const [sx, sy] = door?.inside ?? interiorPoint(entranceHall(walk).poly);
    const ahead = door ? Math.atan2(door.n[1], door.n[0]) : Math.atan2(interiorPoint(rooms[0].poly)[1] - sy, interiorPoint(rooms[0].poly)[0] - sx);
    const N = 72, dists = [];
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2, dx = Math.cos(a), dy = Math.sin(a);
      let d = 10;
      for (const [ax, ay, bx, by] of segments) {
        const ex = bx - ax, ey = by - ay, den = dx * ey - dy * ex;
        if (Math.abs(den) < 1e-9) continue;
        const t = ((ax - sx) * ey - (ay - sy) * ex) / den, u = ((ax - sx) * dy - (ay - sy) * dx) / den;
        if (t > 0 && u >= 0 && u <= 1) d = Math.min(d, t);
      }
      dists.push(d);
    }
    const along = (a) => dists[((Math.round((a / (Math.PI * 2)) * N) % N) + N) % N];
    let best = ahead;
    if (along(ahead) < 2.2) {
      let bestScore = -Infinity;
      for (let i = 0; i < N; i++) {
        const a = (i / N) * Math.PI * 2, off = Math.atan2(Math.sin(a - ahead), Math.cos(a - ahead));
        if (Math.abs(off) > Math.PI / 2) continue;
        let open = 0;
        for (let j = -4; j <= 4; j++) open += Math.min(dists[(i + j + N) % N], 8); // +-20 degrees
        const score = open * (1 + 0.35 * Math.cos(off));
        if (score > bestScore) [bestScore, best] = [score, a];
      }
    }
    const s0 = frame.toScene(sx, sy), t0 = frame.toScene(sx + Math.cos(best), sy + Math.sin(best));
    reach = { rooms: walk.data.rooms.length, before: [...(walkBefore ?? [])], after: [...reachableRooms(walk, segments, [sx, sy])], start: [sx, sy], look: best, door: !!door };
    spawn = { x: s0.x, z: s0.z, yaw: Math.atan2(-(t0.x - s0.x), -(t0.z - s0.z)) };
  }

  const RADIUS = 0.2; // the visitor: half a shoulder width, so a 0.6 m bathroom door lets them through
  return {
    apt: walk,
    group,
    floorMeshes,
    baseY,
    spawn,
    frame,
    plan,
    lights: lightObjects,
    obstacles,
    segments, // collision lines in plan coordinates (for the checks in tools/)
    notes, // rooms where something could not be fitted (for the checks in tools/)
    doors: doors.length,
    liftTags, // { x, y, z (scene), q: [kg, ...] }: one per lift hall, for the floor view's tags
    reach, // walk-through: rooms reachable before furniture and from the start after it (for the checks)
    doorways: doorSpans.map((d) => ({ apt: d.apt, room: d.room, across: d.across, entrance: d.entrance, len: +d.len.toFixed(2), a: d.a.map((v) => +v.toFixed(3)), b: d.b.map((v) => +v.toFixed(3)), n: d.n.map((v) => +v.toFixed(3)), band: d.band.map((v) => +v.toFixed(3)) })),
    entrances: entrances.map((e) => ({ apt: e.apt.id, room: e.room.kind, common: e.common, mid: e.mid.map((v) => +v.toFixed(2)) })),
    gaps: gaps.map((g) => ({ apt: g.apt.id, room: `${g.room.kind} ${g.room.area}`, other: g.other ? `${g.other.kind} ${g.other.area}` : null, across: g.across, done: g.done, len: +g.r.len.toFixed(2), depth: g.depth && +g.depth.toFixed(2), a: g.r.a.map((v) => +v.toFixed(2)), b: g.r.b.map((v) => +v.toFixed(2)) })),
    // Move from (x, z) to (nx, nz) in the scene without walking through walls or out of the flat.
    move(x, z, nx, nz) {
      const p = frame.toPlan(nx, nz);
      let px = p.x, py = p.y;
      for (let iter = 0; iter < 3; iter++) {
        for (const [ax, ay, bx, by] of segments) {
          if (Math.min(ax, bx) - RADIUS > px || Math.max(ax, bx) + RADIUS < px) continue;
          if (Math.min(ay, by) - RADIUS > py || Math.max(ay, by) + RADIUS < py) continue;
          const { d, px: qx, py: qy } = distToSegment(px, py, ax, ay, bx, by);
          if (d < RADIUS && d > 1e-6) {
            px = qx + ((px - qx) / d) * RADIUS;
            py = qy + ((py - qy) / d) * RADIUS;
          }
        }
      }
      if (outline && !onFoot(walk, px, py)) return { x, z };
      const s = frame.toScene(px, py);
      return { x: s.x, z: s.z };
    },
    dispose() {
      group.removeFromParent();
      own.forEach((g) => g.dispose());
      lightObjects.forEach((l) => l.shadow?.map?.dispose());
    },
  };
}

/** the drawing's entrance hall ("Даҳлез"), else any hall, else the smallest room */
function entranceHall(apt) {
  const rooms = apt.data.rooms;
  return rooms.find((r) => r.tj === 'Даҳлез') ?? rooms.find((r) => r.kind === 'hall') ?? [...rooms].sort((p, q) => p.area - q.area)[0];
}

/**
 * Rooms of a flat reachable on foot from `start`: a 10 cm grid over the flat, cells closer than
 * 22 cm to a collision line blocked (the visitor keeps 25 cm), flood-filled from the start.
 */
/** where one can stand in a flat: in its outline or out on its balconies and terraces (and in the
 *  doorway between, where the two outlines stop at the faces of the wall) */
function onFoot(apt, x, y) {
  if (inside(apt.data.outline, x, y)) return true;
  for (const b of apt.data.balconies) {
    if (inside(b.poly, x, y)) return true;
    if (distToPolygon(b.poly, x, y) < 0.4 && distToPolygon(apt.data.outline, x, y) < 0.4) return true;
  }
  return false;
}

function reachableRooms(apt, segments, start, cells = false) {
  // (the balconies and terraces too: a room may be reached across one)
  const out = [...apt.data.outline, ...apt.data.balconies.flatMap((q) => q.poly)], b = bbox(out), step = 0.1, R = 0.23; // a little more than the walker (0.2 m): furniture always leaves a way the visitor fits through
  const nx = Math.ceil((b.x1 - b.x0) / step) + 1, ny = Math.ceil((b.y1 - b.y0) / step) + 1;
  const blocked = new Uint8Array(nx * ny);
  const cx = (i) => b.x0 + i * step, cy = (j) => b.y0 + j * step;
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) if (!onFoot(apt, cx(i), cy(j))) blocked[j * nx + i] = 1;
  for (const [ax, ay, bx, by] of segments) {
    if (Math.max(ax, bx) < b.x0 - R || Math.min(ax, bx) > b.x1 + R || Math.max(ay, by) < b.y0 - R || Math.min(ay, by) > b.y1 + R) continue;
    const i0 = Math.max(0, Math.floor((Math.min(ax, bx) - R - b.x0) / step)), i1 = Math.min(nx - 1, Math.ceil((Math.max(ax, bx) + R - b.x0) / step));
    const j0 = Math.max(0, Math.floor((Math.min(ay, by) - R - b.y0) / step)), j1 = Math.min(ny - 1, Math.ceil((Math.max(ay, by) + R - b.y0) / step));
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) if (!blocked[j * nx + i] && distToSegment(cx(i), cy(j), ax, ay, bx, by).d < R) blocked[j * nx + i] = 1;
  }
  // from the free cell nearest the start
  let s = -1, best = Infinity;
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    if (blocked[j * nx + i]) continue;
    const d = Math.hypot(cx(i) - start[0], cy(j) - start[1]);
    if (d < best) [best, s] = [d, j * nx + i];
  }
  const seen = new Uint8Array(nx * ny), queue = [s], rooms = new Set();
  if (s < 0) return cells ? 0 : rooms;
  seen[s] = 1;
  let count = 1;
  while (queue.length) {
    const c = queue.pop(), i = c % nx, j = (c - i) / nx;
    for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const ii = i + di, jj = j + dj;
      if (ii < 0 || jj < 0 || ii >= nx || jj >= ny) continue;
      const n = jj * nx + ii;
      if (seen[n] || blocked[n]) continue;
      seen[n] = 1;
      count++;
      queue.push(n);
    }
  }
  if (cells) return count;
  // a room is reached when a fair part of it is (not only the cells in its doorway)
  apt.data.rooms.forEach((r, k) => {
    const rb = bbox(r.poly);
    let all = 0, got = 0;
    for (let j = Math.max(0, Math.floor((rb.y0 - b.y0) / step)); j < Math.min(ny, Math.ceil((rb.y1 - b.y0) / step) + 1); j++) {
      for (let i = Math.max(0, Math.floor((rb.x0 - b.x0) / step)); i < Math.min(nx, Math.ceil((rb.x1 - b.x0) / step) + 1); i++) {
        if (blocked[j * nx + i] || !inside(r.poly, cx(i), cy(j))) continue;
        all++;
        if (seen[j * nx + i]) got++;
      }
    }
    if (got && got >= Math.min(20, 0.3 * all)) rooms.add(k);
  });
  return rooms;
}

// ---------- shell details ----------

const dist = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]);
const centre = (poly) => {
  const b = bbox(poly);
  return [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2];
};

/** slab along a -> b on the side `n` points to, from off to off + thick away from the line */
function slab(k, mat, a, b, n, off, thick, z0, z1, ext = 0) {
  const L = dist(a, b);
  if (L < 0.01) return;
  const ux = (b[0] - a[0]) / L, uy = (b[1] - a[1]) / L;
  const p = [a[0] - ux * ext, a[1] - uy * ext], q = [b[0] + ux * ext, b[1] + uy * ext];
  // Kit.along offsets to the left of p -> q
  const left = -uy * n[0] + ux * n[1] > 0;
  if (left) k.along(mat, p[0], p[1], q[0], q[1], off, thick, z0, z1);
  else k.along(mat, q[0], q[1], p[0], p[1], off, thick, z0, z1);
}

function casing(k, mat, r) {
  const w = 0.07, t = 0.016;
  const ext = (p, s) => [p[0] + r.u[0] * s, p[1] + r.u[1] * s];
  slab(k, mat, ext(r.a, -w), r.a, r.n, 0, t, 0, DOOR_H + w);
  slab(k, mat, r.b, ext(r.b, w), r.n, 0, t, 0, DOOR_H + w);
  slab(k, mat, ext(r.a, -w), ext(r.b, w), r.n, 0, t, DOOR_H, DOOR_H + w);
}

/** the frame lining a doorway's opening r through its wall (from s0 to s1 along r.n): both sides
 * and the head; the sides run 3 cm on past the opening's ends into the walls (where the drawing's
 * gap and the wall's end differ by a centimetre or two, no slit between them shows) */
function lining(k, mat, r, s0, s1) {
  const shift = (p, s) => [p[0] + r.n[0] * s, p[1] + r.n[1] * s];
  const t = 0.015, e = 0.03;
  slab(k, mat, shift(r.a, s0), shift(r.a, s1), r.u, -e, t + e, 0, DOOR_H);
  slab(k, mat, shift(r.b, s0), shift(r.b, s1), [-r.u[0], -r.u[1]], -e, t + e, 0, DOOR_H);
  slab(k, mat, shift(r.a, s0), shift(r.b, s0), r.n, 0, s1 - s0, DOOR_H - t, DOOR_H, e);
}

/** a door leaf from hinge h to tip (standing in the room), its face towards w */
function doorLeaf(k, M, h, tip, w, entrance, glazed = false, shut = false) {
  const L = dist(h, tip), d = [(tip[0] - h[0]) / L, (tip[1] - h[1]) / L];
  // (a shut leaf: its line in the middle of the wall, the leaf straddling it)
  if (shut) {
    h = [h[0] - w[0] * 0.026, h[1] - w[1] * 0.026];
    tip = [tip[0] - w[0] * 0.026, tip[1] - w[1] * 0.026];
  }
  const at = (s) => [h[0] + d[0] * s, h[1] + d[1] * s];
  if (glazed) {
    // a balcony door: a slim frame round a glass panel
    const fw = 0.07;
    slab(k, M.frame, h, at(fw), w, 0.006, 0.05, 0.008, DOOR_H - 0.006);
    slab(k, M.frame, at(L - fw), tip, w, 0.006, 0.05, 0.008, DOOR_H - 0.006);
    slab(k, M.frame, at(fw), at(L - fw), w, 0.006, 0.05, 0.008, 0.12);
    slab(k, M.frame, at(fw), at(L - fw), w, 0.006, 0.05, DOOR_H - 0.08, DOOR_H - 0.006);
    slab(k, M.glass, at(fw), at(L - fw), w, 0.026, 0.01, 0.12, DOOR_H - 0.08);
    slab(k, M.chrome, at(L - 0.12), at(L - 0.1), w, 0.056, 0.02, 0.95, 1.15);
    return;
  }
  const mat = entrance ? M.entrance : M.door;
  slab(k, mat, h, tip, w, 0.006, 0.04, 0.008, DOOR_H - 0.006);
  // lever handles on both faces (the leaf's faces are 0.006 and 0.046 from the hinge line)
  for (const [lever, rose] of [[0.058, 0.046], [-0.02, -0.004]]) {
    slab(k, M.blackMetal, at(L - 0.2), at(L - 0.07), w, lever, 0.014, 0.99, 1.012);
    slab(k, M.blackMetal, at(L - 0.09), at(L - 0.05), w, rose, 0.014, 0.97, 1.03);
  }
  if (entrance) {
    // panels: two thin grooves
    for (const y of [0.7, 1.4]) slab(k, M.blackMetal, at(0.12), at(L - 0.12), w, 0.0455, 0.002, y, y + 0.006);
  }
}

/**
 * A flat's front door, shut: a walnut leaf in the middle of the wall (opening r, its wall from s0
 * on the corridor side to s1 on the flat's), lever handles and a spy hole on both faces, the
 * frame on the corridor side too, a threshold and a door mat inside.
 */
function frontDoor(k, M, r, s0, s1) {
  const shift = (p, s) => [p[0] + r.n[0] * s, p[1] + r.n[1] * s];
  const sm = (s0 + s1) / 2;
  const h = shift([r.a[0] + r.u[0] * 0.012, r.a[1] + r.u[1] * 0.012], sm);
  const tip = shift([r.b[0] - r.u[0] * 0.012, r.b[1] - r.u[1] * 0.012], sm);
  doorLeaf(k, M, h, tip, r.n, true, false, true);
  const L = dist(h, tip), at = (t, s) => shift([h[0] + r.u[0] * t, h[1] + r.u[1] * t], s);
  // spy hole, both faces
  for (const s of [sm + 0.025, sm - 0.035]) slab(k, M.chrome, at(L / 2 - 0.012, s), at(L / 2 + 0.012, s), r.n, 0, 0.012, 1.52, 1.545);
  // the frame on the corridor side, a dark threshold under the leaf
  casing(k, M.entrance, { ...r, a: shift(r.a, s0), b: shift(r.b, s0), n: [-r.n[0], -r.n[1]] });
  slab(k, M.color(0x3a3733, 0.6), shift(r.a, s0), shift(r.b, s0), r.n, 0, s1 - s0, 0, 0.012);
  // a door mat inside
  const mw = Math.min(0.9, r.len - 0.1), m0 = (r.len - mw) / 2;
  const ma = shift([r.a[0] + r.u[0] * m0, r.a[1] + r.u[1] * m0], s1), mb = shift([r.a[0] + r.u[0] * (m0 + mw), r.a[1] + r.u[1] * (m0 + mw)], s1);
  slab(k, M.color(0x46423d, 0.98), ma, mb, r.n, 0.08, 0.55, 0.004, 0.018);
}

/** window frame in the middle of the wall: outer frame, mullions every 1.2 m or so */
function windowFrame(k, M, a, b, n, len, z0, z1) {
  const fw = 0.06, fd = 0.07;
  const at = (t) => [a[0] + ((b[0] - a[0]) * t) / len, a[1] + ((b[1] - a[1]) * t) / len];
  slab(k, M.frame, a, b, n, -fd / 2, fd, z0, z0 + fw);
  slab(k, M.frame, a, b, n, -fd / 2, fd, z1 - fw, z1);
  slab(k, M.frame, a, at(fw), n, -fd / 2, fd, z0, z1);
  slab(k, M.frame, at(len - fw), b, n, -fd / 2, fd, z0, z1);
  const panes = Math.max(1, Math.round(len / 1.2));
  for (let i = 1; i < panes; i++) {
    const t = (len * i) / panes;
    slab(k, M.frame, at(t - 0.03), at(t + 0.03), n, -fd / 2, fd, z0, z1);
  }
  // opening sash handle on the first pane
  if (len > 0.6) slab(k, M.chrome, at(len / panes - 0.09), at(len / panes - 0.07), n, fd / 2, 0.03, (z0 + z1) / 2 - 0.08, (z0 + z1) / 2 + 0.08);
}

/** steel panel radiator under a window: front with fine vertical channels, grille on top */
function radiator(k, M, a, b, n, len) {
  const w = Math.min(len * 0.75, 1.6), t0 = (len - w) / 2;
  const at = (t) => [a[0] + ((b[0] - a[0]) * t) / len, a[1] + ((b[1] - a[1]) * t) / len];
  const off = 0.05, z0 = 0.16, z1 = 0.66;
  slab(k, M.radiator, at(t0), at(t0 + w), n, off, 0.09, z0, z1);
  for (let t = t0 + 0.03; t < t0 + w - 0.02; t += 0.05) slab(k, M.radiator, at(t), at(t + 0.022), n, off + 0.09, 0.006, z0 + 0.02, z1 - 0.02);
  slab(k, M.color(0x9a9894, 0.6), at(t0 + 0.02), at(t0 + w - 0.02), n, off + 0.01, 0.07, z1, z1 + 0.002);
  // valve and pipes down to the floor
  slab(k, M.chrome, at(t0 - 0.06), at(t0 - 0.03), n, off + 0.03, 0.03, z0 + 0.05, z0 + 0.12);
  slab(k, M.radiator, at(t0 - 0.055), at(t0 - 0.035), n, off + 0.035, 0.02, 0, z0 + 0.06);
  slab(k, M.radiator, at(t0 + w + 0.035), at(t0 + w + 0.055), n, off + 0.035, 0.02, 0, z0 + 0.06);
}

/** sheer curtains gathered at both ends of a window, on a ceiling track */
function curtains(k, M, a, b, n, H, len) {
  const off = 0.13;
  slab(k, M.blackMetal, a, b, n, off - 0.015, 0.03, H - CEIL - 0.035, H - CEIL - 0.005, 0.3);
  const u = [(b[0] - a[0]) / len, (b[1] - a[1]) / len];
  const facing = Math.atan2(n[1], n[0]);
  const cw = Math.min(0.55, len * 0.3);
  for (const [p, s] of [[a, -1], [b, 1]]) {
    // centre of the gathered panel: half on the wall beside the window, half over the glass
    const c = [p[0] + u[0] * s * 0.08 + n[0] * off, p[1] + u[1] * s * 0.08 + n[1] * off];
    k.at(c[0], c[1], facing);
    F.curtain(k, M.sheer, cw, H - 0.05, 0.015);
  }
}

/**
 * Floor-to-ceiling glazing along a room's edge from a to b (n into the room): the pane 5 cm out
 * from the room's face, black rails at the floor and the ceiling, mullions at both ends and every
 * metre and a half or less.
 */
function curtainWall(k, M, a, b, n, H) {
  const L = dist(a, b);
  if (L < 0.05) return;
  const u = [(b[0] - a[0]) / L, (b[1] - a[1]) / L];
  const at = (t) => [a[0] + u[0] * t, a[1] + u[1] * t];
  // (run on 10 cm past both ends: at a corner the two panes and their rails meet, into a wall
  // they are hidden)
  slab(k, M.glass, a, b, n, -0.06, 0.012, 0, H, 0.1);
  slab(k, M.frame, a, b, n, -0.09, 0.085, 0, 0.08, 0.1);
  slab(k, M.frame, a, b, n, -0.09, 0.085, H - 0.06, H, 0.1);
  const bays = Math.max(1, Math.round(L / 1.4));
  for (let i = 0; i <= bays; i++) {
    const t = Math.min(Math.max((L * i) / bays, 0.025), L - 0.025);
    slab(k, M.frame, at(t - 0.025), at(t + 0.025), n, -0.1, 0.1, 0, H);
  }
}

/** mullions and rails along floor-to-ceiling glazing (also curved) */
function glazingFrame(k, M, poly, H, roomOf, fitted, glassAt) {
  // split the outline at its two farthest points into the two faces, keep the face inside
  let i0 = 0, i1 = 0, best = -1;
  for (let i = 0; i < poly.length; i++) for (let j = i + 1; j < poly.length; j++) {
    const d = dist(poly[i], poly[j]);
    if (d > best) [best, i0, i1] = [d, i, j];
  }
  if (best < 0.5) return;
  const chainA = poly.slice(i0, i1 + 1), chainB = [...poly.slice(i1), ...poly.slice(0, i0 + 1)].reverse();
  const probe = (chain) => {
    const m = chain[Math.floor(chain.length / 2)];
    const [cx, cy] = centre(poly);
    const dx = m[0] - cx, dy = m[1] - cy, L = Math.hypot(dx, dy) || 1;
    return roomOf(m[0] + (dx / L) * 0.2, m[1] + (dy / L) * 0.2);
  };
  const ra = probe(chainA), rb = probe(chainB);
  const chain = ra ? chainA : chainB, owner = ra ?? rb;
  // resample the inside face every ~1.4 m: mullions there, rails along it
  const pts = [chain[0]];
  let acc = 0;
  for (let i = 1; i < chain.length; i++) {
    acc += dist(chain[i - 1], chain[i]);
    if (acc > 0.25) {
      pts.push(chain[i]);
      acc = 0;
    }
  }
  if (dist(pts[pts.length - 1], chain[chain.length - 1]) > 0.01) pts.push(chain[chain.length - 1]);
  const [cx, cy] = centre(poly);
  const inward = (p, q) => {
    const L = dist(p, q) || 1, ux = (q[0] - p[0]) / L, uy = (q[1] - p[1]) / L;
    let nx = -uy, ny = ux;
    const mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2;
    if ((mx - cx) * nx + (my - cy) * ny < 0) (nx = -nx), (ny = -ny);
    return [nx, ny];
  };
  let run = 0;
  for (let i = 1; i < pts.length; i++) {
    const p = pts[i - 1], q = pts[i], n = inward(p, q);
    slab(k, M.frame, p, q, n, -0.06, 0.07, 0, 0.09);
    slab(k, M.frame, p, q, n, -0.06, 0.07, H - 0.07, H);
    run += dist(p, q);
    if (run > 1.3 || i === pts.length - 1 || i === 1) {
      const L = dist(p, q), ux = (q[0] - p[0]) / L, uy = (q[1] - p[1]) / L;
      const m = i === 1 ? p : q;
      slab(k, M.frame, [m[0] - ux * 0.025, m[1] - uy * 0.025], [m[0] + ux * 0.025, m[1] + uy * 0.025], n, -0.07, 0.09, 0, H);
      run = 0;
    }
  }
  // a sheer curtain gathered at each end in living rooms and bedrooms
  if (owner && fitted.includes(owner.apt) && ['living', 'bedroom', 'kitchen'].includes(owner.room.kind)) {
    for (const [p, q] of [[pts[0], pts[1]], [pts[pts.length - 1], pts[pts.length - 2]]]) {
      // only where the glass ends (a wall next to it), not where the next pane of glazing goes on
      const L0 = dist(p, q), along = [(p[0] - q[0]) / L0, (p[1] - q[1]) / L0], n0 = inward(p, q);
      const nb = glassAt(p[0] + along[0] * 0.25 - n0[0] * 0.04, p[1] + along[1] * 0.25 - n0[1] * 0.04);
      if (nb && nb.poly !== poly) continue;
      const n = inward(p, q), L = dist(p, q), ux = (q[0] - p[0]) / L, uy = (q[1] - p[1]) / L;
      const c = [p[0] + ux * 0.3 + n[0] * 0.16, p[1] + uy * 0.3 + n[1] * 0.16];
      k.at(c[0], c[1], Math.atan2(n[1], n[0]));
      F.curtain(k, M.sheer, 0.55, H - 0.05, 0.015);
    }
  }
}

// ---------- what the drawing has: furniture, fittings, lifts ----------

/**
 * A window's opening: the window's own outline as a rectangle along its axis, run on to the wall
 * on either side (the drawings leave slits of a few centimetres between a window and the wall
 * beside it, and the sky showed through them). Returns { poly, ax }.
 */
function windowOpening(w, solid) {
  const ax0 = axisOf(w);
  const mid = (ax0.s0 + ax0.s1) / 2;
  const P = (t, s) => [ax0.cx + ax0.u[0] * t + ax0.v[0] * s, ax0.cy + ax0.u[1] * t + ax0.v[1] * s];
  // how far to the next wall (or window) beyond each end, along the middle of the wall; nothing
  // within 8 cm: the window ends there as drawn
  const reach = (t, sgn) => {
    for (let e = 0.004; e <= 0.08; e += 0.004) {
      const q = P(t + sgn * e, mid);
      const hit = solid.at(q[0], q[1]);
      if (hit && hit.poly !== w) return hit.kind === 'wall' ? e + 0.01 : e;
    }
    return 0;
  };
  const ax = { ...ax0, t0: ax0.t0 - reach(ax0.t0, -1), t1: ax0.t1 + reach(ax0.t1, 1) };
  return { poly: [P(ax.t0, ax.s0), P(ax.t1, ax.s0), P(ax.t1, ax.s1), P(ax.t0, ax.s1)], ax };
}

/** the flat's entrance door (into the corridor), with a point just inside it */
function entranceOf(entrances, apt) {
  const e = entrances.find((x) => x.apt === apt && x.common) ?? entrances.find((x) => x.apt === apt);
  if (!e) return null;
  for (const d of [0.75, 0.6, 0.45, 0.35]) {
    const p = [e.mid[0] + e.n[0] * (e.s1 + d), e.mid[1] + e.n[1] * (e.s1 + d)];
    if (inside(e.room.poly, ...p) && distToEdge(e.room.poly, ...p) > 0.24) return { ...e, inside: p };
  }
  return { ...e, inside: [e.mid[0] + e.n[0] * (e.s1 + 0.4), e.mid[1] + e.n[1] * (e.s1 + 0.4)] };
}

/** door width of a lift by the length of its door wall */
const liftDoor = (w) => (w >= 2.4 ? 1.2 : w >= 2.1 ? 1.1 : 0.9);

/**
 * A lift as drawn: the car in its shaft (origin at the middle of its back wall, the doors at the
 * front, facing lf.f), a steel threshold out to the shaft wall and the landing doors on the hall
 * face of that wall. Returns where the landing doors are (plan), or null.
 */
function lift(k, M, lf, H, solid) {
  const [fx, fy] = [Math.cos(lf.f), Math.sin(lf.f)];
  const doorW = liftDoor(lf.w);
  const back = [lf.c[0] - (fx * lf.d) / 2, lf.c[1] - (fy * lf.d) / 2];
  k.at(back[0], back[1], lf.f);
  F.liftCar(k, M, lf.w, lf.d, H, doorW);
  // the shaft wall in front of the doors: from s0 to s1 beyond the car's front
  let s0 = null, s1 = null;
  for (let e = 0; e < 1.2; e += 0.01) {
    const q = [lf.c[0] + fx * (lf.d / 2 + e), lf.c[1] + fy * (lf.d / 2 + e)];
    const hit = solid.at(q[0], q[1]);
    if (hit && s0 === null) s0 = e;
    if (!hit && s0 !== null) {
      s1 = e;
      break;
    }
  }
  if (s0 === null || s1 === null) return null;
  k.box(M.steel, -doorW / 2 - 0.05, 0, lf.d, doorW / 2 + 0.05, 0.015, lf.d + s0 + 0.01);
  const face = [lf.c[0] + fx * (lf.d / 2 + s1), lf.c[1] + fy * (lf.d / 2 + s1)];
  k.at(face[0], face[1], lf.f);
  F.liftPortal(k, M, doorW);
  return face;
}

/** the floor a drawn piece takes (plan polygons; no snapping to the wall, for the overlap tests) */
function drawnFootprints(it) {
  const rect = (c, w, d, a) => {
    const u = [Math.cos(a), Math.sin(a)], v = [-u[1], u[0]];
    return [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([i, j]) => [c[0] + (u[0] * i * w + v[0] * j * d) / 2, c[1] + (u[1] * i * w + v[1] * j * d) / 2]);
  };
  switch (it.type) {
    case 'bed':
      return [rect(it.c, it.w, it.l, it.f - Math.PI / 2), ...it.stands.map(([x, y, w, d]) => rect([x, y], w, d, it.f - Math.PI / 2))];
    case 'sofa':
      return it.boxes.map((b) => rect([b[0], b[1]], b[2], b[3], b[6]));
    case 'dining':
    case 'ctable':
      return [rect(it.c, it.w, it.d, it.a)];
    case 'rug':
      return [];
    default:
      return it.c && it.w ? [rect(it.c, it.w, Math.max(it.d ?? 0.4, 0.3), it.f - Math.PI / 2)] : [];
  }
}

/**
 * The drawings put two coffee tables one over the other (a nesting pair); in 3D the pair read as
 * two tables stuck into each other. Overlapping coffee tables become one table over both.
 */
function mergedTables(items, rect) {
  const tables = items.filter((it) => it.type === 'ctable');
  const used = new Set(), out = items.filter((it) => it.type !== 'ctable');
  for (const t of tables) {
    if (used.has(t)) continue;
    const group = [t];
    used.add(t);
    for (let grew = true; grew; ) {
      grew = false;
      for (const o of tables) {
        if (used.has(o) || !group.some((g) => overlaps(rect(g.c, g.w, g.d, g.a), rect(o.c, o.w, o.d, o.a)))) continue;
        group.push(o);
        used.add(o);
        grew = true;
      }
    }
    if (group.length === 1) {
      out.push(t);
      continue;
    }
    // the box round all of them, in the first one's direction
    const u = [Math.cos(t.a), Math.sin(t.a)], v = [-u[1], u[0]];
    let s0 = Infinity, s1 = -Infinity, r0 = Infinity, r1 = -Infinity;
    for (const g of group) {
      for (const [x, y] of rect(g.c, g.w, g.d, g.a)) {
        const su = x * u[0] + y * u[1], sv = x * v[0] + y * v[1];
        (s0 = Math.min(s0, su)), (s1 = Math.max(s1, su)), (r0 = Math.min(r0, sv)), (r1 = Math.max(r1, sv));
      }
    }
    const cu = (s0 + s1) / 2, cv = (r0 + r1) / 2;
    out.push({ ...t, c: [u[0] * cu + v[0] * cv, u[1] * cu + v[1] * cv], w: s1 - s0, d: r1 - r0, h: 0.39, merged: group.length }); // (on four legs)
  }
  return out;
}

/** do two convex polygons overlap (more than touch)? */
function overlaps(a, b) {
  for (const [p, q] of [[a, b], [b, a]]) {
    for (let i = 0; i < p.length; i++) {
      const [x0, y0] = p[i], [x1, y1] = p[(i + 1) % p.length];
      const nx = y0 - y1, ny = x1 - x0;
      let pmin = Infinity, pmax = -Infinity, qmin = Infinity, qmax = -Infinity;
      for (const [x, y] of p) (pmin = Math.min(pmin, nx * x + ny * y)), (pmax = Math.max(pmax, nx * x + ny * y));
      for (const [x, y] of q) (qmin = Math.min(qmin, nx * x + ny * y)), (qmax = Math.max(qmax, nx * x + ny * y));
      const L = Math.hypot(nx, ny) || 1;
      if (Math.min(pmax, qmax) - Math.max(pmin, qmin) < 0.01 * L) return false;
    }
  }
  return true;
}

/**
 * Every piece the drawing has in the flat, where it is drawn and turned as drawn (furniture.py:
 * plan metres; `f` the way a piece's front faces, its back against the wall). Returns the rooms
 * that got pieces, the pieces' collision outlines (prio 0: small pieces, the first given up if they
 * shut a room off ... 3: built in), the rugs' centres (where a living room's light hangs) and the
 * rooms lit already (a pendant over the dining table).
 */
function placeDrawn({ k, M, H, apt, solid, keepout, lights, ceiling }) {
  const out = { rooms: new Set(), solids: [], rugs: [], lit: new Set() };
  const rooms = apt.data.rooms;
  const roomAt = (p) => rooms.find((r) => inside(r.poly, p[0], p[1])) ??
    rooms.reduce((b, r) => (distToPolygon(r.poly, ...p) < distToPolygon(b.poly, ...p) ? r : b));
  const dir = (f) => [Math.cos(f), Math.sin(f)];
  // a rectangle centred on c, w along angle a, d across it
  const rect = (c, w, d, a) => {
    const u = dir(a), v = [-u[1], u[0]];
    return [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([i, j]) => [c[0] + (u[0] * i * w + v[0] * j * d) / 2, c[1] + (u[1] * i * w + v[1] * j * d) / 2]);
  };
  const piece = (poly, prio, what) => {
    out.solids.push({ poly, prio, what });
    keepout.push(poly);
  };
  // the middle of a piece's back, moved onto the face of the wall behind it (the drawn pieces
  // stand a centimetre or two off the wall, or a little into it)
  const backOf = (it, d = it.d) => {
    const [fx, fy] = dir(it.f);
    const p = [it.c[0] - (fx * d) / 2, it.c[1] - (fy * d) / 2];
    const at = (e) => solid.at(p[0] - fx * e, p[1] - fy * e);
    if (at(0)) {
      for (let e = 0; e > -0.12; e -= 0.005) if (!at(e)) return [p[0] - fx * e, p[1] - fy * e];
      return p;
    }
    for (let e = 0.005; e < 0.12; e += 0.005) if (at(e)) return [p[0] - fx * (e - 0.004), p[1] - fy * (e - 0.004)];
    return p;
  };
  // window and glass spans behind a run along a wall, in the run's frame x (no wall cabinets there)
  const glassBehind = (p, f, w) => {
    const [fx, fy] = dir(f), rx = [-fy, fx], spans = [];
    for (let t = -w / 2 + 0.025; t < w / 2; t += 0.05) {
      const q = [p[0] + rx[0] * t - fx * 0.06, p[1] + rx[1] * t - fy * 0.06];
      const hit = solid.at(...q);
      if (!hit || (hit.kind !== 'window' && hit.kind !== 'glass')) continue;
      const last = spans[spans.length - 1];
      if (last && t - last[1] < 0.06) last[1] = t + 0.025;
      else spans.push([t - 0.025, t + 0.025]);
    }
    return spans;
  };
  // A drawn piece a few centimetres into a wall (the drawings put a kitchen against a duct, a bath
  // against a boxed-in pipe, that the plan's walls make a little thicker): moved out along its own
  // axes by the least that frees it, up to 25 cm; left as drawn when nothing frees it.
  const clearOf = (polys) => polys.every((q) => !inSolidInset(solid, q, 0.025));
  const settle = (polys, f) => {
    if (clearOf(polys)) return [0, 0];
    const u = dir(f), v = [-u[1], u[0]];
    for (let e = 0.01; e <= 0.25 + 1e-9; e += 0.01) {
      for (const [dx, dy] of [u, v, [-v[0], -v[1]], [-u[0], -u[1]]]) {
        const sh = [dx * e, dy * e];
        if (clearOf(polys.map((q) => q.map(([x, y]) => [x + sh[0], y + sh[1]])))) return sh;
      }
    }
    return [0, 0];
  };
  const moved = (p, sh) => [p[0] + sh[0], p[1] + sh[1]];
  for (const it0 of mergedTables(apt.data.furniture ?? [], rect)) {
    let it = it0;
    // (pieces with a back: their back on the wall's face first, then out of any wall they still reach)
    if (it.c && it.f !== undefined && it.w && it.type !== 'bed') {
      const d = it.type === 'kitchen' ? Math.max(it.d, 0.5) : it.type === 'tv' ? Math.max(it.d, 0.32) : it.d;
      const p = backOf(it, d), w = ['toilet', 'basin'].includes(it.type) ? Math.max(it.w, 0.5) : it.w;
      const sh = settle([footprint(p, it.f, w, 0, d)], it.f);
      if (sh[0] || sh[1]) it = { ...it, c: moved(it.c, sh) };
    } else if (it.type === 'bed') {
      const p = backOf(it, it.l);
      const sh = settle([footprint(p, it.f, it.w, 0, it.l), ...it.stands.map(([x, y, w, d]) => footprint(backOf({ c: [x, y], f: it.f, d }), it.f, w, 0, d))], it.f);
      if (sh[0] || sh[1]) it = { ...it, c: moved(it.c, sh), stands: it.stands.map(([x, y, w, d]) => [x + sh[0], y + sh[1], w, d]) };
    } else if (it.type === 'sofa') {
      const sh = settle(it.boxes.map((b) => rect([b[0], b[1]], b[2], b[3], b[6])), it.boxes[0][6]);
      if (sh[0] || sh[1]) it = { ...it, boxes: it.boxes.map((b) => [b[0] + sh[0], b[1] + sh[1], ...b.slice(2)]) };
    } else if ((it.type === 'dining' || it.type === 'ctable') && it.c) {
      const sh = settle([rect(it.c, it.w, it.d, it.a)], it.a);
      if (sh[0] || sh[1]) it = { ...it, c: moved(it.c, sh), chairs: it.chairs?.map(([x, y, f]) => [x + sh[0], y + sh[1], f]) };
    }
    const c = it.c ?? [it.boxes.reduce((a, b) => a + b[0], 0) / it.boxes.length, it.boxes.reduce((a, b) => a + b[1], 0) / it.boxes.length];
    const room = roomAt(c);
    out.rooms.add(room);
    switch (it.type) {
      case 'bed': {
        const p = backOf(it, it.l);
        k.at(p[0], p[1], it.f);
        // (the model's headboard is 12 cm wider than its bed: the headboard is the drawn width)
        F.bed(k, M, it.w - 0.12, it.l - 0.02);
        if (solid.at(p[0] - Math.cos(it.f) * 0.03, p[1] - Math.sin(it.f) * 0.03)) F.picture(k, M, Math.min(1.2, it.w * 0.65), 0.7, 1.72, 0, M.oak);
        piece(footprint(p, it.f, it.w, 0, it.l), 1, 'bed');
        for (const [x, y, w, d] of it.stands) {
          const q = backOf({ c: [x, y], f: it.f, d });
          k.at(q[0], q[1], it.f);
          F.nightstand(k, M, w, d);
          piece(footprint(q, it.f, w, 0, d), 1, 'nightstand');
        }
        break;
      }
      case 'tv': {
        const d = Math.max(it.d, 0.32), p = backOf(it);
        k.at(p[0], p[1], it.f);
        F.mediaWall(k, M, it.w, d);
        piece(footprint(p, it.f, it.w, 0, d), 2, 'tv');
        break;
      }
      case 'kitchen': {
        const d = Math.max(it.d, 0.5), p = backOf(it);
        k.at(p[0], p[1], it.f);
        F.kitchen(k, M, it.w, H, glassBehind(p, it.f, it.w), { d, sink: it.sink, hob: it.hob, bowls: it.bowls });
        piece(footprint(p, it.f, it.w, 0, d), 3, 'kitchen');
        break;
      }
      case 'toilet': {
        const p = backOf(it), w = Math.max(it.w, 0.5);
        k.at(p[0], p[1], it.f);
        F.toilet(k, M, w, it.d, H);
        keepout.push(footprint(p, it.f, w, 0, it.d));
        break;
      }
      case 'basin': {
        const p = backOf(it), w = Math.max(it.w, 0.5), d = Math.max(it.d, 0.4);
        k.at(p[0], p[1], it.f);
        F.vanity(k, M, w, H, 1, d);
        keepout.push(footprint(p, it.f, w, 0, d));
        break;
      }
      case 'bath': {
        const p = backOf(it);
        k.at(p[0], p[1], it.f);
        F.bathtub(k, M, it.w, it.d, it.tap ?? 1);
        piece(footprint(p, it.f, it.w, 0, it.d), 3, 'bath');
        break;
      }
      case 'ac': {
        const p = backOf(it);
        k.at(p[0], p[1], it.f);
        F.acUnit(k, M, it.w, it.d);
        piece(footprint(p, it.f, it.w, 0, it.d), 0, 'ac');
        break;
      }
      case 'dining': {
        k.at(it.c[0], it.c[1], it.a - Math.PI / 2);
        F.diningTable(k, M, it.w, it.d);
        piece(rect(it.c, it.w, it.d, it.a), 2, 'table');
        // the chairs as drawn, pushed in a little under the table (the drawing shows their backs)
        for (const [x, y, f] of it.chairs) {
          k.at(x - Math.cos(f) * 0.125, y - Math.sin(f) * 0.125, f);
          F.chair(k, M);
        }
        if (ceiling) {
          k.at(it.c[0], it.c[1], it.a - Math.PI / 2);
          F.pendants(k, M, it.w >= 1.4 ? [-it.w / 4, it.w / 4] : [0], 0, H - CEIL, 1.55);
          lights.push({ x: it.c[0], y: it.c[1], z: 1.5, room, main: true });
          out.lit.add(room);
        }
        break;
      }
      case 'rug': {
        k.at(it.c[0], it.c[1], it.a - Math.PI / 2);
        F.rugAt(k, M, it.w, it.d, M.rugGrey);
        out.rugs.push(it.c);
        break;
      }
      case 'sofa': {
        F.sofaBoxes(k, M, it.boxes);
        for (const b of it.boxes) piece(rect([b[0], b[1]], b[2], b[3], b[6]), 1, 'sofa');
        break;
      }
      case 'armchair': {
        const [fx, fy] = dir(it.f), p = [it.c[0] - (fx * it.d) / 2, it.c[1] - (fy * it.d) / 2];
        k.at(p[0], p[1], it.f);
        F.armchair(k, M, it.w, it.d);
        piece(footprint(p, it.f, it.w, 0, it.d), 0, 'armchair');
        break;
      }
      case 'ctable': {
        k.at(it.c[0], it.c[1], it.a - Math.PI / 2);
        F.nestTable(k, M, it.w, it.d, it.h);
        piece(rect(it.c, it.w, it.d, it.a), 0, 'table');
        break;
      }
      default:
        break;
    }
  }
  return out;
}

// ---------- furniture ----------

/**
 * The four sides of the room's largest rectangle, each with what is behind it: samples every
 * 10 cm say 'wall', 'window', 'glass', 'open' (a door or an opening) or 'far' (the room goes on).
 */
function rectSides(room, r, solid) {
  const defs = [
    { a: [r.x0, r.y0], u: [1, 0], n: [0, 1], L: r.x1 - r.x0, across: r.y1 - r.y0 },
    { a: [r.x1, r.y1], u: [-1, 0], n: [0, -1], L: r.x1 - r.x0, across: r.y1 - r.y0 },
    { a: [r.x0, r.y1], u: [0, -1], n: [1, 0], L: r.y1 - r.y0, across: r.x1 - r.x0 },
    { a: [r.x1, r.y0], u: [0, 1], n: [-1, 0], L: r.y1 - r.y0, across: r.x1 - r.x0 },
  ];
  for (const s of defs) {
    s.facing = Math.atan2(s.n[1], s.n[0]);
    s.samples = [];
    const gaps = [];
    for (let t = 0.05; t < s.L; t += 0.1) {
      const x = s.a[0] + s.u[0] * t, y = s.a[1] + s.u[1] * t;
      let label = 'far';
      for (let d = 0; d <= 0.45; d += 0.03) {
        const px = x - s.n[0] * d, py = y - s.n[1] * d;
        if (inside(room.poly, px, py)) continue;
        const hit = solid.at(px - s.n[0] * 0.05, py - s.n[1] * 0.05) ?? solid.at(px, py);
        label = hit ? hit.kind : 'open';
        if (label === 'wall') {
          // the room's edge lies within the last step: find it to the millimetre
          let lo = Math.max(0, d - 0.03), hi = d;
          for (let it = 0; it < 6; it++) {
            const m = (lo + hi) / 2;
            if (inside(room.poly, x - s.n[0] * m, y - s.n[1] * m)) lo = m;
            else hi = m;
          }
          // the wall's face: walls overlap the room outlines by a few centimetres
          let e = 0;
          while (e < 0.1 && solid.at(x - s.n[0] * (lo - e - 0.002), y - s.n[1] * (lo - e - 0.002))) e += 0.005;
          gaps.push(lo - e);
          s.samples.push({ t, label, gap: lo - e });
          break;
        }
        break;
      }
      if (!s.samples.length || s.samples[s.samples.length - 1].t !== t) s.samples.push({ t, label });
    }
    gaps.sort((p, q) => p - q);
    s.gap = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 0;
    // contiguous stretches of solid wall, each in one plane: where the wall face steps (a column
    // a few centimetres proud of the wall, a recess) a new stretch begins, so a piece stands against
    // one flat face and not half in a column (the console's mirror was half inside one)
    s.free = [];
    let cur = null;
    for (const { t, label, gap } of s.samples) {
      if (label === 'wall' && cur && Math.abs(gap - cur.gap) <= 0.025) {
        cur.t1 = t + 0.05;
        cur.gaps.push(gap);
      } else if (label === 'wall') s.free.push((cur = { t0: t - 0.05, t1: t + 0.05, gap, gaps: [gap] }));
      else cur = null;
    }
    for (const f of s.free) {
      f.len = f.t1 - f.t0;
      f.gaps.sort((p, q) => p - q);
      f.gap = f.gaps[Math.floor(f.gaps.length / 2)];
    }
    s.free.sort((p, q) => q.len - p.len);
    // stretches of wall or window: base units (a kitchen run) can stand under a window too
    s.low = [];
    cur = null;
    for (const { t, label } of s.samples) {
      if (label === 'wall' || label === 'window') {
        if (!cur) s.low.push((cur = { t0: t - 0.05, t1: t + 0.05 }));
        else cur.t1 = t + 0.05;
      } else cur = null;
    }
    for (const f of s.low) f.len = f.t1 - f.t0;
    s.low.sort((p, q) => q.len - p.len);
    // any closed stretch (wall, window or floor-to-ceiling glass): the last resort for a bed
    s.any = [];
    cur = null;
    for (const { t, label } of s.samples) {
      if (label === 'wall' || label === 'window' || label === 'glass') {
        if (!cur) s.any.push((cur = { t0: t - 0.05, t1: t + 0.05 }));
        else cur.t1 = t + 0.05;
      } else cur = null;
    }
    for (const f of s.any) f.len = f.t1 - f.t0;
    s.any.sort((p, q) => q.len - p.len);
    s.wall = s.samples.filter((x) => x.label === 'wall').length / Math.max(1, s.samples.length);
    s.windows = s.samples.some((x) => x.label === 'window' || x.label === 'glass');
    // a point on this side, `t` along it and `d` into the room (d = -gap: against the wall)
    s.at = (t, d) => [s.a[0] + s.u[0] * t + s.n[0] * d, s.a[1] + s.u[1] * t + s.n[1] * d];
  }
  return defs;
}

/** footprint of a piece at plan point p facing f: w wide, from z0 to z1 in front of p */
function footprint(p, f, w, z0, z1) {
  const fx = Math.cos(f), fy = Math.sin(f), rx = -fy, ry = fx;
  const P = (x, z) => [p[0] + rx * x + fx * z, p[1] + ry * x + fy * z];
  return [P(-w / 2, z0), P(w / 2, z0), P(w / 2, z1), P(-w / 2, z1)];
}

/** does a footprint fit in the room, clear of door swings and fittings? (a way to walk: clear of
 * the furniture, but it may overlap the other ways) */
function fits(ctx, poly, margin = 0.02, isWay = false) {
  const { room, keepout } = ctx;
  const [a, b, , d] = poly;
  for (let i = 0; i <= 4; i++) {
    for (let j = 0; j <= 4; j++) {
      const x = a[0] + (b[0] - a[0]) * (i / 4) + (d[0] - a[0]) * (j / 4);
      const y = a[1] + (b[1] - a[1]) * (i / 4) + (d[1] - a[1]) * (j / 4);
      if (!inside(room.poly, x, y) && distToPolygon(room.poly, x, y) > margin) return false;
      for (const q of keepout) if (!(isWay && q.way) && !(q.room && q.room !== room) && inside(q, x, y)) return false;
    }
  }
  return true;
}

/**
 * Put a piece against side s at t (centre), d0 from the side line, w wide and `depth` deep.
 * Draws it with draw() when it fits; returns its footprint or null.
 */
function place(ctx, s, t, w, depth, draw, { collide = true, keep = true, z0 = 0, clear = 0, gap = null } = {}) {
  const d0 = -(gap ?? s.gap) + 0.005 + z0;
  const p = s.at(t, d0);
  const fp = footprint(p, s.facing, w, 0, depth);
  // `clear`: space to stand and walk in front of it, kept free of other furniture
  const front = clear ? footprint(p, s.facing, w, depth, depth + clear) : null;
  if (!fits(ctx, fp) || (front && !fits(ctx, front, 0.02, true))) return null;
  // (the room outlines run on over the columns drawn inside them: a piece must not stand in one)
  if (inSolid(ctx.solid, footprint(p, s.facing, w, 0.025, depth))) return null;
  ctx.k.at(p[0], p[1], s.facing);
  draw(p);
  if (collide) ctx.addOutline(fp);
  if (keep) ctx.keepout.push(fp);
  if (front) ctx.keepout.push(Object.assign(front, { way: true, room: ctx.room }));
  return fp;
}

/** does a footprint reach more than `inset` into a wall or a column (sampled on a 7 x 7 grid
 *  `inset` in from its edges)? */
function inSolidInset(solid, poly, inset) {
  if (poly.length !== 4) return false;
  const [a, b, , d] = poly;
  const lu = dist(a, b), lv = dist(a, d);
  if (lu < 2 * inset + 0.01 || lv < 2 * inset + 0.01) return false;
  for (let i = 0; i <= 6; i++) {
    for (let j = 0; j <= 6; j++) {
      const fu = (inset + ((lu - 2 * inset) * i) / 6) / lu, fv = (inset + ((lv - 2 * inset) * j) / 6) / lv;
      const x = a[0] + (b[0] - a[0]) * fu + (d[0] - a[0]) * fv, y = a[1] + (b[1] - a[1]) * fu + (d[1] - a[1]) * fv;
      if (solid.at(x, y)?.kind === 'wall') return true;
    }
  }
  return false;
}

/** does a footprint reach into a wall or a column (sampled on a 6 x 6 grid)? */
function inSolid(solid, poly) {
  const [a, b, , d] = poly;
  for (let i = 0; i <= 5; i++) {
    for (let j = 0; j <= 5; j++) {
      const x = a[0] + (b[0] - a[0]) * (i / 5) + (d[0] - a[0]) * (j / 5);
      const y = a[1] + (b[1] - a[1]) * (i / 5) + (d[1] - a[1]) * (j / 5);
      if (solid.at(x, y)?.kind === 'wall') return true;
    }
  }
  return false;
}

/** best free stretch of wall: the longest of at least `need`, optionally not on the sides in `not` */
function bestWall(sides, need, not = []) {
  let best = null;
  for (const s of sides) {
    if (not.includes(s)) continue;
    const f = s.free[0];
    if (!f || f.len < need) continue;
    if (!best || f.len > best.f.len) best = { s, f };
  }
  return best;
}

const opposite = (sides, s) => sides.find((o) => o.n[0] === -s.n[0] && o.n[1] === -s.n[1]);

/**
 * Fit a piece against the walls: every stretch of every side (longest first; `stretches` 'free'
 * for solid wall, 'low' for wall or window), the widest size from maxW down to minW, slid along
 * the stretch from its middle outwards. draw(w, s, t) draws it once the kit is placed.
 * Returns { s, t, w, fp } or null.
 */
function fitAlong(ctx, sides, { minW, maxW, depth, clear = 0, stretches = 'free', not = [], minAcross = 0, accept = null }, draw) {
  const cands = [];
  for (const s of sides) {
    if (not.includes(s) || s.across < minAcross) continue;
    for (const f of s[stretches]) if (f.len >= minW) cands.push({ s, f });
  }
  cands.sort((p, q) => q.f.len - p.f.len);
  for (const { s, f } of cands) {
    for (let w = Math.min(maxW, f.len - 0.05); w >= minW - 1e-6; w -= 0.2) {
      const mid = (f.t0 + f.t1) / 2, span = (f.len - w) / 2;
      for (let o = 0; o <= span + 1e-6; o += 0.15) {
        for (const t of o ? [mid - o, mid + o] : [mid]) {
          // (`accept`: a test of the piece once placed, e.g. that it shuts no room off; else it is
          // taken back and the next place tried)
          const m = accept && ctx.mark();
          const fp = place(ctx, s, t, w, depth, () => draw(w, s, t), { clear, gap: f.gap ?? null });
          if (fp && (!accept || accept())) return { s, t, w, fp };
          if (fp) ctx.rollback(m);
        }
      }
    }
  }
  return null;
}

/** window spans of side s within a piece centred at t, w wide, in the piece's frame x */
function windowSpans(s, t, w) {
  const out = [];
  for (const smp of s.samples) {
    if (smp.label !== 'window' || Math.abs(smp.t - t) > w / 2 + 0.05) continue;
    const x = -(smp.t - t); // the piece's frame x runs against the side's direction
    const last = out[out.length - 1];
    if (last && Math.abs(last[0] - (x + 0.05)) < 0.11) last[0] = x - 0.05;
    else out.push([x - 0.05, x + 0.05]);
  }
  return out.map(([a, b]) => [Math.min(a, b), Math.max(a, b)]);
}

function furnish(ctx) {
  const { room, k, M, H } = ctx;
  if (room._wet) return bathroom(ctx);
  if (room.kind === 'loggia' || room.kind === 'terrace') {
    // a loggia: a small table with two chairs where it is wide enough, else left clear
    if (!ctx.sparse && room.area >= 3.5) balconyFurniture(k, M, room.poly);
    return;
  }
  const r = innerRect(room.poly, 0.06);
  const w = r.x1 - r.x0, d = r.y1 - r.y0;
  if (w < 0.9 || d < 0.9) return;
  const sides = rectSides(room, r, ctx.solid);
  const cx = (r.x0 + r.x1) / 2, cy = (r.y0 + r.y1) / 2;
  const light = (x, y, z, main = false) => ctx.lights.push({ x, y, z, room, main });

  switch (room.kind) {
    case 'bedroom': {
      // the bed's head against a solid wall, with a nightstand each side if there is room: a double
      // bed if the room allows, else a narrower double or a single
      let bed = null;
      for (const bw of Math.min(w, d) >= 2.6 ? [1.6, 1.4, 0.9] : [0.9]) {
        for (const stands of [true, false]) {
          const total = bw + 0.14 + (stands ? 1.0 : 0);
          bed = fitAlong(ctx, sides, { minW: total, maxW: total, depth: 2.2, clear: 0.45, minAcross: 2.65, accept: ctx.open }, () => {
            k.save().offset(0, 1.15);
            F.rugAt(k, M, bw + 1.2, 2.0, M.rugBeige);
            k.restore();
            F.bed(k, M, bw);
            F.picture(k, M, 1.0, 0.7, 1.72, 0, M.oak);
            if (stands) {
              for (const sg of [-1, 1]) {
                k.save().offset(sg * (bw / 2 + 0.36), 0);
                F.nightstand(k, M);
                k.restore();
              }
            }
          });
          if (bed) break;
        }
        if (bed) break;
      }
      // no free wall long enough (doors and windows on every side): the bed under a window, or
      // against the glass, without nightstands
      for (const [stretches, across, clear] of [['free', 2.3, 0.25], ['low', 2.3, 0.25], ['any', 2.2, 0.2]]) {
        for (const bw of [1.4, 0.9]) {
          if (bed) break;
          bed = fitAlong(ctx, sides, { minW: bw + 0.14, maxW: bw + 0.14, depth: 2.1, clear, minAcross: across, stretches, accept: ctx.open }, () => {
            k.save().offset(0, 1.15);
            F.rugAt(k, M, bw + 1.0, 1.8, M.rugBeige);
            k.restore();
            F.bed(k, M, bw);
          });
        }
      }
      if (!bed) {
        ctx.notes.push(`bedroom ${room.area} m²: no wall for a bed`);
        break;
      }
      // wardrobe on another wall
      if (!ctx.sparse) {
        fitAlong(ctx, sides, { minW: 1.0, maxW: 2.4, depth: 0.62, clear: 0.75 }, (ww) => F.wardrobe(k, M, ww, H));
        // a plant in a free corner
        corners(ctx, sides, 0.5, () => F.plant(k, M, 0.85));
      }
      pendant(ctx, cx, cy, 'drum');
      break;
    }
    case 'living': {
      if (Math.min(w, d) < 2.4) break;
      const beforeTv = ctx.mark();
      // a sofa against a wall with the coffee table and a rug in front of it, a picture above it
      const sofaGroup = (sw2) => {
        F.sofa(k, M, sw2);
        k.save().offset(0, 0.97 + 0.45 + 0.48);
        F.coffeeTable(k, M);
        k.restore();
        k.save().offset(0, 1.3);
        F.rugAt(k, M, sw2 + 0.6, 2.2, M.rugGrey);
        k.restore();
        F.picture(k, M, 1.2, 0.8, 1.55, 1, M.blackMetal);
      };
      // last resort: the sofa on its own against any wall or window, a side table at its end
      const sofaAlone = () => {
        for (const stretches of ['free', 'low']) {
          const got = fitAlong(ctx, sides, { minW: 1.7, maxW: 2.4, depth: 0.97, clear: 0.55, stretches }, (sw2) => {
            F.sofa(k, M, sw2);
            k.save().offset(sw2 / 2 + 0.32, 0.27);
            F.sideTable(k, M);
            k.restore();
          });
          if (got) return got;
        }
        return null;
      };
      const tv = fitAlong(ctx, sides, { minW: 1.4, maxW: 2.2, depth: 0.44, clear: 0.6, minAcross: 3.0 }, (cw) => F.mediaWall(k, M, cw));
      let sofaSide = null, tvT = null, tvS = null;
      if (tv) {
        tvS = tv.s;
        tvT = tv.t;
        sofaSide = opposite(sides, tvS);
      }
      // sofa facing the TV, about 2.8 m from it (against the far wall in smaller rooms)
      const s = sofaSide ?? sides.reduce((p, q) => (q.wall > p.wall ? q : p));
      const across = s.across;
      const back = Math.max(-s.gap, across - (tvS ? 0.44 + 2.5 + 0.96 : across));
      const t = tvS ? s.L - tvT : s.L / 2; // opposite side runs the other way
      let sw = Math.min(2.6, s.L - 0.6);
      let placed = null;
      while (!placed && sw >= 1.7) {
        placed = place(ctx, s, t, sw, 0.97, () => F.sofa(k, M, sw), { z0: back + s.gap });
        if (!placed) sw -= 0.2;
      }
      if (!placed) {
        // against any other solid wall, with the coffee table in front of it
        const alt = fitAlong(ctx, sides, { minW: 1.7, maxW: 2.6, depth: 2.4, clear: 0.3, not: tvS ? [tvS] : [] }, (sw2) => sofaGroup(sw2));
        if (!alt && tv) {
          // the TV took the wall the sofa needs (a square room): sofa first, TV opposite it
          ctx.rollback(beforeTv);
          const first = fitAlong(ctx, sides, { minW: 1.7, maxW: 2.6, depth: 2.4, clear: 0.3 }, (sw2) => sofaGroup(sw2));
          if (first) fitAlong(ctx, [opposite(sides, first.s)].filter(Boolean), { minW: 1.4, maxW: 2.2, depth: 0.44, clear: 0.6 }, (cw) => F.mediaWall(k, M, cw));
          else if (!sofaAlone()) ctx.notes.push(`living ${room.area} m²: no place for the sofa`);
        } else if (!alt && !sofaAlone()) ctx.notes.push(`living ${room.area} m²: no place for the sofa`);
      }
      if (placed) {
        const dz = back + s.gap; // the sofa's back, from the side line
        const tableZ = dz + 0.97 + 0.45 + 0.48;
        place(ctx, s, t, sw + 0.8, Math.min(2.4, across - dz - 0.6), () => F.rugAt(k.offset(0, 1.2), M, sw + 0.8, 2.3, M.rugGrey), { collide: false, keep: false, z0: dz + 0.55 });
        // the coffee table only where it leaves a way past it (a narrow living room gets the sofa
        // and a side table)
        if (across - (tableZ + 0.48) >= 0.8) place(ctx, s, t, 0.96, 0.96, () => F.coffeeTable(k.offset(0, 0.48), M), { z0: tableZ - 0.48 });
        if (back > -s.gap + 0.3) {
          // floating sofa: a console behind? keep it simple: a floor lamp at its end
        } else {
          F.picture(k.at(...s.at(t, -s.gap), s.facing), M, 1.2, 0.8, 1.55, 1, M.blackMetal);
        }
        // floor lamp and side table at the sofa's ends, an armchair beside the table
        const endA = t - sw / 2 - 0.3, endB = t + sw / 2 + 0.3;
        if (endA > 0.2) place(ctx, s, endA, 0.4, 0.4, () => {
          F.floorLamp(k.offset(0, 0.25), M);
          const p = s.at(endA, dz - s.gap + 0.25);
          light(p[0], p[1], 1.4);
        }, { z0: dz });
        if (endB < s.L - 0.2) place(ctx, s, endB, 0.5, 0.5, () => F.sideTable(k.offset(0, 0.27), M), { z0: dz });
        const armT = t + sw / 2 + 0.75, armZ = tableZ;
        if (armT < s.L - 0.45 && !ctx.sparse) {
          const p = s.at(armT, armZ - s.gap);
          const f = s.facing + Math.PI / 2 * (s.u[0] * s.n[1] - s.u[1] * s.n[0] > 0 ? 1 : -1);
          const fp = footprint(p, f + Math.PI, 0.85, -0.42, 0.42);
          if (fits(ctx, fp)) {
            // turn it to face the coffee table
            const tp = s.at(t, tableZ - s.gap);
            const face = Math.atan2(tp[1] - p[1], tp[0] - p[0]);
            const back = [p[0] - Math.cos(face) * 0.42, p[1] - Math.sin(face) * 0.42];
            k.at(back[0], back[1], face);
            F.armchair(k, M);
            ctx.addOutline(fp);
            ctx.keepout.push(fp);
          }
        }
      }
      if (!ctx.sparse) {
        corners(ctx, sides, 0.5, () => F.plant(k, M, 1.1));
        corners(ctx, sides, 0.5, () => F.plant(k, M, 0.8));
      }
      pendant(ctx, cx, cy, 'drum');
      break;
    }
    case 'kitchen': {
      // the run along a wall (under a window too: the sink goes there), 1.5 to 4.4 m long
      const run = fitAlong(ctx, sides, { minW: 1.2, maxW: 4.4, depth: 0.64, clear: 0.9, stretches: 'low' }, (len, s, t) => F.kitchen(k, M, len, H, windowSpans(s, t, len)));
      let runSide = null;
      if (!run) ctx.notes.push(`kitchen ${room.area} m²: no wall for the kitchen run`);
      if (run) {
        // an island 1.1 m in front of a long run in a deep room
        const { s, t, w: len } = run;
        runSide = s;
        if (s.across >= 4.6 && len >= 2.6 && !ctx.sparse) {
          const iw = Math.min(2.2, len - 0.4);
          const p = s.at(t, -s.gap + 0.64 + 1.1 + 0.45);
          const ifp = footprint(p, s.facing, iw, -0.45, 1.1);
          if (fits(ctx, ifp)) {
            k.at(p[0], p[1], s.facing);
            F.island(k, M, iw);
            ctx.addOutline(footprint(p, s.facing, iw + 0.04, -0.47, 0.47));
            ctx.keepout.push(ifp);
            if (ctx.ceiling) F.pendants(k, M, [-iw / 4, iw / 4], 0, H - CEIL, 1.6);
            light(p[0], p[1], 1.65, true);
          }
        }
      }
      // dining table in the most open part of the room
      const tw = Math.min(w, d) >= 3.2 ? 1.8 : 1.4;
      const spotT = ctx.sparse ? null : openSpot(ctx, r, tw + 0.2, 0.9 + 1.4);
      if (spotT) {
        const { p, f } = spotT;
        k.at(p[0], p[1], f);
        const ls = F.dining(k, M, tw, 0.9, ctx.ceiling ? H : 0);
        for (const l of ls) {
          const fx = Math.cos(f), fy = Math.sin(f);
          light(p[0] - fy * l.x + fx * l.z, p[1] + fx * l.x + fy * l.z, l.y, true);
          break;
        }
        ctx.addOutline(footprint([p[0] - Math.cos(f) * 0.45, p[1] - Math.sin(f) * 0.45], f, tw, 0, 0.9));
      }
      if (!ctx.sparse) corners(ctx, sides.filter((s) => s !== runSide), 0.45, () => F.plant(k, M, 0.9));
      break;
    }
    case 'hall': {
      const con = fitAlong(ctx, sides, { minW: 0.8, maxW: 1.3, depth: 0.36, clear: 0.7 }, (cw) => F.console_(k, M, cw));
      if (!ctx.sparse) fitAlong(ctx, sides, { minW: 0.9, maxW: 0.9, depth: 0.2, clear: 0.6, not: con ? [con.s] : [], minAcross: 1.3 }, () => F.coatRack(k, M, 0.9));
      if (Math.min(w, d) >= 1.5 && Math.max(w, d) >= 3) {
        const long = w > d ? sides[0] : sides[2];
        place(ctx, long, long.L / 2, Math.min(long.L - 0.6, 3), Math.min(1.0, long.across - 0.4), () => F.rugAt(k.offset(0, 0.5), M, Math.min(long.L - 0.6, 3), Math.min(1.0, long.across - 0.4) - 0.05, M.rugGrey), { collide: false, keep: false, z0: (long.across - Math.min(1.0, long.across - 0.4)) / 2 });
      }
      if (!ctx.sparse) corners(ctx, sides, 0.45, () => F.plant(k, M, 0.75));
      break;
    }
    case 'storage': {
      const s = sides.reduce((p, q) => ((q.free[0]?.len ?? 0) > (p.free[0]?.len ?? 0) ? q : p));
      if (s.free[0] && s.across >= 0.9) place(ctx, s, (s.free[0].t0 + s.free[0].t1) / 2, s.free[0].len - 0.05, 0.4, () => F.shelving(k, M, s.free[0].len - 0.05, Math.min(H - 0.1, 2.3)));
      break;
    }
    default:
      break;
  }
}

/** the most open spot of the rectangle for a w x d piece (both turns), clear of everything */
function openSpot(ctx, r, w, d) {
  let best = null;
  for (let x = r.x0 + 0.3; x <= r.x1 - 0.3; x += 0.15) {
    for (let y = r.y0 + 0.3; y <= r.y1 - 0.3; y += 0.15) {
      for (const f of [0, Math.PI / 2]) {
        const fp = footprint([x - Math.cos(f) * (d / 2), y - Math.sin(f) * (d / 2)], f, w, 0, d);
        if (!fits(ctx, fp, 0)) continue;
        // prefer the middle of the free space: distance to the room edge and to other pieces
        let clear = distToEdge(ctx.room.poly, x, y);
        for (const q of ctx.keepout) clear = Math.min(clear, distToPolygon(q, x, y));
        if (!best || clear > best.clear) best = { p: [x, y], f, clear };
      }
    }
  }
  return best;
}

function distToEdge(p, x, y) {
  let d = Infinity;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) d = Math.min(d, distToSegment(x, y, p[j][0], p[j][1], p[i][0], p[i][1]).d);
  return d;
}

/** a piece in the first free corner where two walls meet */
function corners(ctx, sides, size, draw) {
  for (const s of sides) {
    for (const t of [0.3, s.L - 0.3]) {
      const near = s.samples.find((x) => Math.abs(x.t - t) < 0.1);
      if (!near || near.label !== 'wall') continue;
      const p = s.at(t, -s.gap + 0.3);
      const fp = footprint(s.at(t, -s.gap), s.facing, size, 0, size + 0.05);
      if (!fits(ctx, fp)) continue;
      ctx.k.at(p[0], p[1], s.facing);
      draw();
      ctx.addOutline(fp);
      ctx.keepout.push(fp);
      return true;
    }
  }
  return false;
}

/** ceiling light: a linen drum pendant in the middle of the room */
function pendant(ctx, x, y, kind) {
  const { k, M, H, room } = ctx;
  if (!ctx.ceiling) return;
  k.at(x, y, 0);
  if (kind === 'drum') {
    k.cyl(M.blackMetal, 0, H - CEIL - 0.012, 0, 0.06, H - CEIL, 20);
    k.cyl(M.blackMetal, 0, H - 0.55, 0, 0.003, H - CEIL, 6);
    k.lathe(M.shade, [[0.3, 0], [0.3, 0.26]], 0, H - 0.8, 0, 48);
    k.cyl(M.shade, 0, H - 0.8, 0, 0.29, H - 0.795, 48);
    k.cyl(M.brass, 0, H - 0.56, 0, 0.012, H - 0.55, 12);
    ctx.lights.push({ x, y, z: H - 0.62, room, main: true });
  }
}

/** recessed downlights in halls, kitchens and bathrooms (the real light goes in the middle) */
function downlights(ctx) {
  const { k, M, H, room } = ctx;
  if (!['hall', 'kitchen', 'bath', 'storage'].includes(room.kind) && !room._wet) return;
  const r = innerRect(room.poly, 0.3);
  const w = r.x1 - r.x0, d = r.y1 - r.y0;
  if (w < 0.2 || d < 0.2) return;
  const nx = Math.max(1, Math.round(w / 1.3)), ny = Math.max(1, Math.round(d / 1.3));
  for (let i = 0; i < nx; i++) {
    for (let j = 0; j < ny; j++) {
      const x = r.x0 + (w * (i + 0.5)) / nx, y = r.y0 + (d * (j + 0.5)) / ny;
      k.at(x, y, 0);
      k.cyl(M.chrome, 0, H - CEIL - 0.004, 0, 0.05, H - CEIL - 0.001, 24);
      k.cyl(M.downlight, 0, H - CEIL - 0.006, 0, 0.035, H - CEIL - 0.003, 24);
    }
  }
  ctx.lights.push({ x: (r.x0 + r.x1) / 2, y: (r.y0 + r.y1) / 2, z: H - 0.03, room, main: false, spot: true });
}

function bathroom(ctx) {
  const { room, k, M } = ctx;
  const r = innerRect(room.poly, 0.06);
  const sides = rectSides(room, r, ctx.solid);
  // towel rail on a free wall, a bath mat
  const spot = bestWall(sides, 0.7);
  if (spot) place(ctx, spot.s, (spot.f.t0 + spot.f.t1) / 2, 0.6, 0.12, () => F.towelRail(k, M), { collide: false });
  const w = r.x1 - r.x0, d = r.y1 - r.y0;
  if (w > 1.2 && d > 1.2) {
    const s = sides[0];
    place(ctx, s, s.L / 2, 0.8, 0.5, () => F.rugAt(k.offset(0, 0.25), M, 0.8, 0.5, M.towel), { collide: false, keep: false, z0: s.across / 2 - 0.25 + s.gap });
  }
}

function balconyFurniture(k, M, poly) {
  const [x, y] = interiorPoint(poly);
  if (distToPolygon(poly, x, y) > 0) return null;
  k.at(x, y, 0);
  k.cyl(M.blackMetal, 0, 0, 0, 0.2, 0.01, 20);
  k.cyl(M.blackMetal, 0, 0, 0, 0.02, 0.72, 10);
  k.cyl(M.oak, 0, 0.72, 0, 0.32, 0.75, 32);
  for (const dx of [-0.65, 0.65]) {
    if (!inside(poly, x + dx, y)) continue;
    k.at(x + dx, y, dx > 0 ? Math.PI : 0).offset(0, -0.25);
    F.chair(k, M);
  }
  return [x, y];
}
