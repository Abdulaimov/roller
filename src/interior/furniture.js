// Furniture and fittings, modelled from primitives at real sizes. Each piece is drawn in its own
// frame (see kit.js: x to the right, y up, front towards +z, origin at the middle of the back on
// the floor) after the caller has placed the kit with kit.at(...).
// Pieces that give light return where the light is (in the piece's frame), so the caller can put
// a real light there.
import * as THREE from 'three';
import { Q } from '../quality.js';

const HIGH = Q.level === 'high';
const GAP = 0x24211e; // shadow gap between fronts

function rnd(seed) {
  return () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
}

// ---------- living room ----------

export function sofa(k, M, w = 2.4, mat = M.sofa) {
  const arm = 0.2, d = 0.96, legH = 0.09;
  for (const x of [-w / 2 + 0.1, w / 2 - 0.1]) for (const z of [0.1, d - 0.1]) k.cyl(M.walnut, x, 0, z, 0.022, legH, 10, 0.026);
  k.rbox(mat, 0, legH + 0.13, d / 2, w, 0.26, d, 0.05);
  for (const s of [-1, 1]) k.rbox(mat, s * (w / 2 - arm / 2), legH + 0.27, d / 2, arm, 0.54, d, 0.07);
  k.rbox(mat, 0, legH + 0.39, 0.11, w - 0.02, 0.78, 0.22, 0.07);
  const n = w > 2.1 ? 3 : 2, cw = (w - 2 * arm) / n;
  for (let i = 0; i < n; i++) {
    const x = -w / 2 + arm + cw * (i + 0.5);
    k.rbox(mat, x, legH + 0.33, 0.25 + 0.355, cw - 0.012, 0.16, 0.71, 0.06);
    k.rbox(mat, x, legH + 0.62, 0.3, cw - 0.03, 0.44, 0.18, 0.08);
  }
  // scatter cushions
  k.rbox(M.cushionA, -w / 2 + arm + 0.3, legH + 0.6, 0.45, 0.46, 0.44, 0.15, 0.07);
  k.rbox(M.cushionB, w / 2 - arm - 0.3, legH + 0.6, 0.45, 0.46, 0.44, 0.15, 0.07);
  if (w > 2.1) k.rbox(M.cushionC, w / 2 - arm - 0.62, legH + 0.56, 0.48, 0.4, 0.38, 0.14, 0.07);
}

export function armchair(k, M, w = 0.82, d = 0.84) {
  const arm = Math.min(0.14, w * 0.17);
  for (const x of [-w / 2 + 0.08, w / 2 - 0.08]) for (const z of [0.1, d - 0.1]) k.cyl(M.walnut, x, 0, z, 0.02, 0.16, 10, 0.024);
  k.rbox(M.chairSeat, 0, 0.29, d / 2, w, 0.26, d, 0.09);
  k.rbox(M.chairSeat, 0, 0.6, 0.12, w, 0.42, 0.22, 0.1);
  for (const s of [-1, 1]) k.rbox(M.chairSeat, s * (w / 2 - arm / 2), 0.5, d / 2, arm, 0.24, d - 0.04, 0.06);
  k.rbox(M.chairSeat, 0, 0.47, d / 2 + 0.06, w - 2 * arm - 0.02, 0.1, d - 0.2, 0.05);
}

export function coffeeTable(k, M, r = 0.48) {
  k.cyl(M.walnut, 0, 0, 0, r * 0.55, 0.34, 32, r * 0.5);
  k.cyl(M.quartz, 0, 0.34, 0, r, 0.38, 48);
  // books and a bowl
  const R = rnd(7);
  let y = 0.38;
  for (const [c, w, d, h] of [[0x30475e, 0.3, 0.22, 0.03], [0xc9b79c, 0.26, 0.2, 0.025], [0x8a3b2e, 0.22, 0.17, 0.02]]) {
    k.save().offset(-0.14 + R() * 0.02, -0.06, R() * 0.4 - 0.2);
    k.box(M.color(c, 0.7), -w / 2, y, -d / 2, w / 2, y + h, d / 2);
    k.restore();
    y += h;
  }
  k.lathe(M.ceramic, [[0, 0], [0.05, 0.002], [0.11, 0.03], [0.13, 0.07], [0.125, 0.07], [0.1, 0.035], [0, 0.03]], 0.17, 0.38, 0.1, 28);
}

export function sideTable(k, M) {
  k.cyl(M.blackMetal, 0, 0, 0, 0.18, 0.012, 24);
  k.cyl(M.blackMetal, 0, 0, 0, 0.014, 0.52, 10);
  k.cyl(M.walnut, 0, 0.52, 0, 0.24, 0.545, 32);
}

/** TV console with fluted fronts and a wall-mounted TV; w = console width */
export function mediaWall(k, M, w = 2.0, d = 0.42) {
  const h = 0.46, y0 = 0.16;
  k.box(M.color(GAP, 0.9), -w / 2, y0, 0, w / 2, y0 + h, d - 0.02);
  const n = Math.max(2, Math.round(w / 0.6)), fw = w / n;
  for (let i = 0; i < n; i++) {
    const x0 = -w / 2 + i * fw + 0.003, x1 = x0 + fw - 0.006;
    // fluting: slim vertical slats
    const slats = Math.round((x1 - x0) / 0.035);
    for (let s = 0; s < slats; s++) {
      const sx = x0 + ((x1 - x0) * (s + 0.5)) / slats;
      k.rbox(M.walnut, sx, y0 + h / 2, d - 0.012, (x1 - x0) / slats - 0.004, h - 0.01, 0.02, 0.008, 1);
    }
  }
  k.box(M.walnut, -w / 2, y0 + h, 0, w / 2, y0 + h + 0.025, d);
  for (const x of [-w / 2 + 0.12, w / 2 - 0.12]) for (const z of [0.08, d - 0.08]) k.box(M.blackMetal, x - 0.015, 0, z - 0.015, x + 0.015, y0, z + 0.015);
  // TV, 65"
  const tw = Math.min(1.45, w * 0.8), th = tw * 0.5625, ty = y0 + h + 0.32;
  k.box(M.blackMetal, -tw / 2, ty, 0.02, tw / 2, ty + th, 0.05);
  k.box(M.screen, -tw / 2 + 0.006, ty + 0.006, 0.05, tw / 2 - 0.006, ty + th - 0.006, 0.052);
  // on the console: a speaker bar, a vase with branches, books
  k.rbox(M.blackMetal, 0, y0 + h + 0.05, Math.min(0.22, d / 2), 0.9, 0.06, 0.09, 0.02);
  vase(k, M, w / 2 - 0.25, y0 + h + 0.025, Math.min(0.2, d / 2), 0.32);
  k.box(M.color(0xd8cfc0, 0.8), -w / 2 + 0.15, y0 + h + 0.025, 0.06, -w / 2 + 0.45, y0 + h + 0.065, Math.min(0.32, d - 0.04));
  k.box(M.color(0x384a3c, 0.8), -w / 2 + 0.17, y0 + h + 0.065, 0.08, -w / 2 + 0.42, y0 + h + 0.09, Math.min(0.3, d - 0.06));
}

export function vase(k, M, x, y, z, h = 0.3) {
  k.lathe(M.terracotta, [[0, 0], [0.05, 0], [0.075, h * 0.35], [0.06, h * 0.75], [0.035, h * 0.9], [0.04, h], [0.032, h], [0, h * 0.9]], x, y, z, 24);
  // dried branches
  const R = rnd(Math.round(x * 100 + 500));
  for (let i = 0; i < 4; i++) {
    const a = R() * Math.PI * 2, s = 0.12 + R() * 0.12;
    k.tube(M.color(0x6b5440, 0.9), [[x, y + h * 0.8, z], [x + Math.cos(a) * s * 0.4, y + h + 0.25, z + Math.sin(a) * s * 0.4], [x + Math.cos(a) * s, y + h + 0.45 + R() * 0.2, z + Math.sin(a) * s]], 0.004, 8);
  }
}

export function floorLamp(k, M) {
  k.cyl(M.blackMetal, 0, 0, 0, 0.16, 0.02, 28);
  k.cyl(M.blackMetal, 0, 0.02, 0, 0.012, 1.45, 10);
  k.lathe(M.shade, [[0.21, 0], [0.16, 0.3]], 0, 1.3, 0, 32);
  k.lathe(M.shade, [[0.16, 0.3], [0.0, 0.3]], 0, 1.3, 0, 32);
  return new THREE.Vector3(0, 1.42, 0);
}

export function plant(k, M, size = 1) {
  const potH = 0.42 * size, potR = 0.2 * size;
  k.lathe(M.pot, [[0, 0], [potR * 0.8, 0], [potR, potH * 0.15], [potR, potH], [potR * 0.92, potH], [potR * 0.92, potH * 0.92], [0, potH * 0.92]], 0, 0, 0, 32);
  k.cyl(M.soil, 0, potH * 0.86, 0, potR * 0.9, potH * 0.9, 24);
  // a fiddle-leaf fig: a few stems, large leaves along them
  const R = rnd(Math.round(size * 1000));
  const stems = 3, leaves = HIGH ? 18 : 10;
  for (let s = 0; s < stems; s++) {
    const a = (s / stems) * Math.PI * 2 + R();
    const lean = 0.08 + R() * 0.1;
    const top = potH + (0.8 + R() * 0.5) * size;
    const tx = Math.cos(a) * lean * size, tz = Math.sin(a) * lean * size;
    k.tube(M.color(0x5b4a35, 0.9), [[0, potH * 0.9, 0], [tx * 0.5, (potH + top) / 2, tz * 0.5], [tx, top, tz]], 0.01 * size, 10);
    for (let i = 0; i < leaves; i++) {
      const t = 0.25 + (i / leaves) * 0.78;
      const px = tx * t, py = potH + (top - potH) * t, pz = tz * t;
      const yaw = R() * Math.PI * 2, tilt = 0.5 + R() * 0.7, ls = (0.16 + R() * 0.1) * size;
      const g = new THREE.PlaneGeometry(ls * 0.75, ls);
      g.translate(0, ls / 2, 0);
      g.rotateX(-tilt);
      g.rotateY(yaw);
      g.translate(px + Math.cos(yaw) * 0.02, py, pz + Math.sin(yaw) * 0.02);
      k.add(M.leaf, g);
    }
  }
}

export function rugAt(k, M, w, d, mat = M.rugBeige) {
  k.rbox(mat, 0, 0.007, 0, w, 0.014, d, 0.006, 1);
}

/** framed picture hanging with its centre at height y */
export function picture(k, M, w, h, y, variant = 0, frame = M.oak) {
  const t = 0.025, z = 0.0;
  k.box(frame, -w / 2, y - h / 2, z, w / 2, y - h / 2 + t, z + 0.035);
  k.box(frame, -w / 2, y + h / 2 - t, z, w / 2, y + h / 2, z + 0.035);
  k.box(frame, -w / 2, y - h / 2, z, -w / 2 + t, y + h / 2, z + 0.035);
  k.box(frame, w / 2 - t, y - h / 2, z, w / 2, y + h / 2, z + 0.035);
  k.box(M.color(0xf7f5f0, 0.9), -w / 2 + t, y - h / 2 + t, z + 0.005, w / 2 - t, y + h / 2 - t, z + 0.02);
  const m = 0.06 + t;
  k.plane(M.art[variant % M.art.length], 0, y, z + 0.021, w - 2 * m, h - 2 * m);
}

// ---------- bedroom ----------

/** double (w 1.6-1.8) or single (0.9) bed with its head against the wall, L long (headboard to foot) */
export function bed(k, M, w = 1.6, L = 2.12) {
  const single = w < 1.2;
  // headboard: upholstered channels
  const hw = w + 0.12, n = Math.max(4, Math.round(hw / 0.22));
  for (let i = 0; i < n; i++) k.rbox(M.headboard, -hw / 2 + (hw / n) * (i + 0.5), 0.6, 0.06, hw / n - 0.006, 1.2, 0.1, 0.045);
  // base and mattress
  k.box(M.color(GAP, 0.9), -w / 2 + 0.08, 0, 0.2, w / 2 - 0.08, 0.1, L - 0.1);
  k.rbox(M.headboard, 0, 0.24, L / 2 + 0.05, w + 0.06, 0.28, L - 0.1, 0.04);
  k.rbox(M.bedding, 0, 0.47, L / 2 + 0.06, w - 0.02, 0.2, L - 0.16, 0.06);
  // duvet, folded back at the top, hanging over the sides and the foot
  const dz0 = 0.75, dz1 = L + 0.02;
  k.rbox(M.duvet, 0, 0.6, (dz0 + dz1) / 2, w + 0.08, 0.07, dz1 - dz0, 0.035);
  k.rbox(M.duvet, 0, 0.62, dz0 + 0.12, w + 0.09, 0.08, 0.26, 0.04);
  for (const s of [-1, 1]) k.rbox(M.duvet, s * (w / 2 + 0.035), 0.47, (dz0 + dz1) / 2, 0.03, 0.3, dz1 - dz0, 0.014);
  k.rbox(M.duvet, 0, 0.47, dz1, w + 0.08, 0.3, 0.03, 0.014);
  // throw across the foot
  k.rbox(M.throw, 0, 0.645, L - 0.32, w + 0.12, 0.03, 0.5, 0.014);
  for (const s of [-1, 1]) k.rbox(M.throw, s * (w / 2 + 0.06), 0.5, L - 0.32, 0.025, 0.3, 0.5, 0.01);
  // pillows in rows, none through another: large ones standing against the headboard, the
  // sleeping pillows lying in front of them, two small cushions standing in front of those
  const pw = Math.min(single ? 0.66 : 0.68, single ? w - 0.1 : w / 2 - 0.06);
  const xs = single ? [0] : [-w / 4, w / 4];
  for (const x of xs) {
    k.rbox(M.bedding, x, 0.8, 0.2, pw - 0.04, 0.4, 0.15, 0.07);
    k.rbox(M.bedding, x, 0.655, 0.505, pw, 0.15, 0.4, 0.07);
  }
  const cw = Math.min(0.4, (w - 0.2) / 2);
  k.rbox(M.cushionC, single ? 0 : -cw / 2 - 0.02, 0.8, 0.79, cw, 0.3, 0.11, 0.05);
  if (!single) k.rbox(M.cushionB, cw / 2 + 0.02, 0.8, 0.79, cw, 0.3, 0.11, 0.05);
}

/** returns the lamp's light position */
export function nightstand(k, M, w = 0.48, d = 0.4) {
  const h = 0.5;
  k.box(M.walnut, -w / 2, 0.12, 0, w / 2, h, d);
  k.box(M.color(GAP, 0.9), -w / 2 + 0.01, h - 0.19, d, w / 2 - 0.01, h - 0.186, d + 0.001);
  k.box(M.brass, -0.08, h - 0.12, d, 0.08, h - 0.11, d + 0.015);
  for (const x of [-w / 2 + 0.03, w / 2 - 0.03]) for (const z of [0.03, d - 0.03]) k.cyl(M.blackMetal, x, 0, z, 0.01, 0.12, 8);
  // lamp: ceramic base, linen shade
  k.lathe(M.ceramic, [[0, 0], [0.07, 0], [0.09, 0.08], [0.08, 0.17], [0.03, 0.24], [0.012, 0.26], [0, 0.26]], 0, h, d / 2, 28);
  k.lathe(M.shade, [[0.15, 0.24], [0.11, 0.44]], 0, h, d / 2, 32);
  k.box(M.color(0x2a3644, 0.7), 0.06, h, 0.04, 0.22, h + 0.03, 0.26);
  return new THREE.Vector3(0, h + 0.33, d / 2);
}

/** built-in wardrobe, w wide, up to height h */
export function wardrobe(k, M, w, h) {
  const d = 0.6;
  k.box(M.lacquer, -w / 2, 0, 0, w / 2, h, d - 0.03);
  k.box(M.color(GAP, 0.9), -w / 2 + 0.01, 0.08, d - 0.03, w / 2 - 0.01, h - 0.01, d - 0.021);
  const n = Math.max(2, Math.round(w / 0.5)), fw = w / n;
  for (let i = 0; i < n; i++) {
    const x0 = -w / 2 + i * fw + 0.002, x1 = x0 + fw - 0.004;
    k.box(M.lacquer, x0, 0.08, d - 0.02, x1, h - 0.004, d);
    const hx = i % 2 ? x0 + 0.04 : x1 - 0.04;
    k.box(M.brass, hx - 0.008, 0.95, d, hx + 0.008, 1.35, d + 0.025);
  }
  k.box(M.color(GAP, 0.9), -w / 2, 0, d - 0.06, w / 2, 0.08, d - 0.04);
}

// ---------- kitchen and dining ----------

/**
 * Kitchen along a wall, `len` long, wall cabinets up to `h`. `windows`: [x0, x1] spans of the run
 * (frame x) in front of a window, base units only there. `opt`: d (depth), sink and hob (frame x of
 * their middles, as drawn), bowls (1 or 2). Without them the sink goes under a window and the hob
 * away from it, with a fridge at the right end of a long run. Returns light positions.
 */
export function kitchen(k, M, len, h, windows = [], opt = {}) {
  const over = (a, b) => windows.some(([w0, w1]) => Math.min(b, w1) - Math.max(a, w0) > 0.02);
  const drawn = opt.sink !== undefined || opt.hob !== undefined;
  const fridge = !drawn && len >= 2.8 && !over(len / 2 - 0.62, len / 2);
  const d = opt.d ?? 0.62, top = 0.9;
  const runL = fridge ? len - 0.62 : len, x0 = -len / 2, x1 = x0 + runL;
  // plinth and base carcass (the fronts' finish; dark only in the gaps between fronts)
  k.box(M.oak, x0, 0.1, 0, x1, top - 0.03, d - 0.07);
  k.box(M.color(GAP, 0.9), x0 + 0.01, 0.1, d - 0.07, x1 - 0.01, top - 0.03, d - 0.061);
  k.box(M.color(0x2b2724, 0.9), x0, 0, d - 0.1, x1, 0.1, d - 0.08);
  // the units: [a, b, kind] side by side along the run
  const units = [];
  let sink, hob;
  const clampC = (c, w) => Math.min(Math.max(c, x0 + w / 2), x1 - w / 2);
  if (drawn) {
    const sw = opt.bowls === 2 ? 0.8 : 0.6, hw = 0.6;
    const sc = clampC(opt.sink ?? x1 - sw / 2, sw);
    let hc = clampC(opt.hob ?? (sc > 0 ? x0 + hw / 2 : x1 - hw / 2), hw);
    if (Math.abs(hc - sc) < (sw + hw) / 2) hc = clampC(sc + Math.sign(hc - sc || 1) * (sw + hw) / 2, hw);
    sink = [sc - sw / 2, sc + sw / 2];
    hob = [hc - hw / 2, hc + hw / 2];
    const fixed = [[...sink, 'sink'], [...hob, 'hob']].sort((p, q) => p[0] - q[0]);
    // the stretches between them in modules of up to 60 cm, drawers at the ends of the run
    let a0 = x0;
    for (const f of [...fixed, [x1, x1, 'end']]) {
      const span = f[0] - a0;
      if (span > 0.05) {
        const n = Math.max(1, Math.ceil(span / 0.6 - 0.05));
        for (let i = 0; i < n; i++) units.push([a0 + (span * i) / n, a0 + (span * (i + 1)) / n, a0 <= x0 + 1e-6 || f[2] === 'end' ? 'drawers' : 'door']);
      }
      if (f[2] !== 'end') units.push(f);
      a0 = Math.max(a0, f[1]);
    }
  } else {
    // modules of 60 cm: sink, dishwasher, hob over oven, drawers; the sink under a window when
    // there is one, the hob away from it (and never under a window)
    const n = Math.max(2, Math.floor(runL / 0.6)), mw = runL / n;
    const mod = (i) => [x0 + i * mw, x0 + (i + 1) * mw];
    const underWin = [...Array(n).keys()].filter((i) => over(...mod(i)));
    const sinkAt = underWin.length ? underWin[Math.floor(underWin.length / 2)] : Math.min(n - 1, 1);
    const free = [...Array(n).keys()].filter((i) => i !== sinkAt && !over(...mod(i)));
    const hobAt = free.length ? free.reduce((p, q) => (Math.abs(q - sinkAt) > Math.abs(p - sinkAt) ? q : p)) : (sinkAt + 1) % n;
    for (let i = 0; i < n; i++) units.push([...mod(i), i === sinkAt ? 'sink' : i === hobAt ? 'hob' : i === n - 1 && n > 2 ? 'drawers' : 'door']);
    sink = mod(sinkAt);
    hob = mod(hobAt);
  }
  for (const [ua, ub, kind] of units) {
    const a = ua + 0.002, b = ub - 0.004;
    if (kind === 'hob') {
      // oven: black glass with a steel bar
      k.box(M.blackGlass, a, 0.3, d - 0.06, b, 0.84, d - 0.04);
      k.box(M.steel, a + 0.05, 0.78, d - 0.04, b - 0.05, 0.795, d - 0.015);
      k.box(M.oak, a, 0.1, d - 0.06, b, 0.298, d - 0.04);
    } else if (kind === 'drawers') {
      for (const [y0, y1] of [[0.1, 0.38], [0.382, 0.62], [0.622, 0.86]]) {
        k.box(M.oak, a, y0, d - 0.06, b, y1, d - 0.04);
        k.box(M.blackMetal, (a + b) / 2 - Math.min(0.14, (b - a) / 3), y1 - 0.035, d - 0.04, (a + b) / 2 + Math.min(0.14, (b - a) / 3), y1 - 0.025, d - 0.015);
      }
    } else if (kind === 'sink' && b - a > 0.7) {
      // two doors under a double sink
      const m = (a + b) / 2;
      for (const [p, q] of [[a, m - 0.002], [m + 0.002, b]]) {
        k.box(M.oak, p, 0.1, d - 0.06, q, 0.86, d - 0.04);
        k.box(M.blackMetal, (p + q) / 2 - 0.1, 0.81, d - 0.04, (p + q) / 2 + 0.1, 0.82, d - 0.015);
      }
    } else {
      k.box(M.oak, a, 0.1, d - 0.06, b, 0.86, d - 0.04);
      k.box(M.blackMetal, (a + b) / 2 - Math.min(0.14, (b - a) / 3), 0.81, d - 0.04, (a + b) / 2 + Math.min(0.14, (b - a) / 3), 0.82, d - 0.015);
    }
  }
  // worktop with the sink cut out
  const bowls = drawn ? opt.bowls ?? 1 : 1;
  const sa = sink[0] + 0.06, sb = sink[1] - 0.06, sz0 = 0.08, sz1 = Math.min(0.52, d - 0.1);
  const T = 0.03, wt = (mat, ax, az, bx, bz) => k.box(mat, ax, top - T, az, bx, top, bz);
  wt(M.quartz, x0, 0, sa, d);
  wt(M.quartz, sb, 0, x1, d);
  wt(M.quartz, sa, 0, sb, sz0);
  wt(M.quartz, sa, sz1, sb, d);
  // the bowls (a ridge between two)
  const bw = (sb - sa - (bowls - 1) * 0.04) / bowls;
  for (let i = 0; i < bowls; i++) {
    const ba = sa + i * (bw + 0.04), bb = ba + bw;
    k.box(M.steel, ba, top - 0.2, sz0, bb, top - 0.19, sz1);
    k.box(M.steel, ba, top - 0.2, sz0, ba + 0.01, top - T, sz1);
    k.box(M.steel, bb - 0.01, top - 0.2, sz0, bb, top - T, sz1);
    k.box(M.steel, ba, top - 0.2, sz0, bb, top - T, sz0 + 0.01);
    k.box(M.steel, ba, top - 0.2, sz1 - 0.01, bb, top - T, sz1);
    if (i > 0) k.box(M.steel, ba - 0.04, top - 0.012, sz0, ba, top - 0.002, sz1);
  }
  // tap
  const tx = (sa + sb) / 2;
  k.cyl(M.chrome, tx, top, 0.05, 0.025, top + 0.05, 16);
  k.tube(M.chrome, [[tx, top + 0.04, 0.05], [tx, top + 0.3, 0.05], [tx, top + 0.36, 0.12], [tx, top + 0.3, 0.2], [tx, top + 0.24, 0.21]], 0.012, 24);
  // hob
  const ha = hob[0] + 0.04, hb = hob[1] - 0.04;
  k.box(M.blackGlass, ha, top, 0.05, hb, top + 0.006, Math.min(0.56, d - 0.04));
  for (const [fx, fz, r] of [[0.28, 0.3, 0.09], [0.72, 0.3, 0.07], [0.28, 0.7, 0.07], [0.72, 0.7, 0.09]]) {
    k.lathe(M.color(0x3a3b3d, 0.3), [[r, 0], [r - 0.005, 0.0008], [0, 0.0008]], ha + (hb - ha) * fx, top + 0.006, 0.05 + (Math.min(0.56, d - 0.04) - 0.05) * fz, 32);
  }
  // splashback and wall cabinets with a light strip under them, in the stretches between windows
  const ub = 1.48, ut = Math.min(h - 0.01, 2.36), ud = Math.min(0.35, d - 0.12);
  const spans = [];
  let a0 = x0;
  for (const [w0, w1] of [...windows].sort((p, q) => p[0] - q[0])) {
    if (w1 <= x0 || w0 >= x1) continue;
    if (w0 - a0 > 0.05) spans.push([a0, Math.min(w0, x1)]);
    a0 = Math.max(a0, w1);
  }
  if (x1 - a0 > 0.05) spans.push([a0, x1]);
  for (const [sx0, sx1] of spans) {
    k.box(M.splash, sx0, top, 0, sx1, ub, 0.012);
    if (sx1 - sx0 < 0.3) continue; // too narrow for a cabinet: tiles only
    k.box(M.lacquer, sx0, ub, 0, sx1, ut, ud - 0.03);
    k.box(M.color(GAP, 0.9), sx0 + 0.01, ub + 0.01, ud - 0.03, sx1 - 0.01, ut - 0.01, ud - 0.021);
    const un = Math.max(1, Math.round((sx1 - sx0) / 0.5)), uw = (sx1 - sx0) / un;
    for (let i = 0; i < un; i++) {
      const a = sx0 + i * uw + 0.002, b = a + uw - 0.004;
      k.box(M.lacquer, a, ub + 0.002, ud - 0.02, b, ut, ud);
    }
    k.box(M.strip, sx0 + 0.05, ub - 0.012, ud - 0.06, sx1 - 0.05, ub - 0.004, ud - 0.04);
    // above the cabinets up to the ceiling: a plain bulkhead
    if (h - ut > 0.02) k.box(M.lacquer, sx0, ut, 0, sx1, h, ud);
  }
  // hood over the hob, under the cabinets
  if (drawn) k.box(M.steel, hob[0] + 0.04, ub - 0.06, 0.02, hob[1] - 0.04, ub - 0.01, Math.min(0.48, d - 0.06));
  // tall fridge housing
  if (fridge) {
    const a = x1 + 0.002, b = x0 + len;
    k.box(M.lacquer, a, 0, 0, b, h, d - 0.03);
    k.box(M.color(GAP, 0.9), a + 0.01, 0.1, d - 0.03, b - 0.01, h - 0.01, d - 0.021);
    k.box(M.lacquer, a, 0.1, d - 0.02, b - 0.002, 0.86, d);
    k.box(M.lacquer, a, 0.864, d - 0.02, b - 0.002, 2.0, d);
    k.box(M.lacquer, a, 2.004, d - 0.02, b - 0.002, h, d);
    k.box(M.blackMetal, a + 0.04, 0.6, d, a + 0.055, 0.84, d + 0.025);
    k.box(M.blackMetal, a + 0.04, 0.9, d, a + 0.055, 1.35, d + 0.025);
  }
  // on the worktop, away from the sink and the hob: chopping board, a bowl of fruit, a bottle
  const freeX = (w) => {
    for (const [ua, ub, kind] of units) if (kind !== 'sink' && kind !== 'hob' && ub - ua >= w + 0.05) return (ua + ub) / 2;
    return null;
  };
  const bx = freeX(0.42);
  if (bx !== null) k.box(M.oak, bx - 0.2, top, 0.08, bx + 0.2, top + 0.02, 0.36);
  const fx = units.length > 1 ? (() => { for (let i = units.length - 1; i >= 0; i--) if (!['sink', 'hob'].includes(units[i][2])) return (units[i][0] + units[i][1]) / 2; return null; })() : null;
  if (fx !== null && fx !== bx) {
    k.lathe(M.ceramic, [[0, 0], [0.06, 0], [0.12, 0.05], [0.13, 0.09], [0.12, 0.09], [0.11, 0.055], [0, 0.01]], fx, top, 0.3, 24);
    for (let i = 0; i < 3; i++) k.sphere(M.color([0xd9902b, 0xb43b2c, 0x8fb04a][i], 0.4), fx + (i - 1) * 0.05, top + 0.08, 0.3 + (i % 2) * 0.03, 0.035, 1, 1, 1, 1);
  }
  k.lathe(M.blackGlass, [[0, 0], [0.035, 0], [0.035, 0.2], [0.012, 0.26], [0.012, 0.3], [0, 0.3]], Math.min(sb + 0.2, x1 - 0.06), top, 0.12, 16);
  return [new THREE.Vector3((x0 + x1) / 2, ub - 0.05, ud)];
}

export function chair(k, M) {
  const s = 0.46;
  for (const [x, z] of [[-0.19, 0.04], [0.19, 0.04], [-0.19, 0.42], [0.19, 0.42]]) k.cyl(M.oak, x, 0, z, 0.016, 0.44, 10, 0.02);
  k.rbox(M.chairSeat, 0, 0.465, s / 2, s, 0.06, s, 0.025);
  k.box(M.oak, -0.2, 0.44, 0.015, -0.18, 0.84, 0.035);
  k.box(M.oak, 0.18, 0.44, 0.015, 0.2, 0.84, 0.035);
  k.rbox(M.oak, 0, 0.75, 0.02, 0.44, 0.16, 0.025, 0.01, 1);
}

/** dining table centred on the origin (not against a wall), long side along x; pendants from a ceiling at h (0: none) */
export function dining(k, M, w = 1.6, d = 0.9, h = 2.8) {
  k.rbox(M.oak, 0, 0.735, 0, w, 0.04, d, 0.012, 1);
  for (const sx of [-1, 1]) {
    k.box(M.walnut, sx * (w / 2 - 0.12) - 0.03, 0, -d / 2 + 0.1, sx * (w / 2 - 0.12) + 0.03, 0.715, -d / 2 + 0.16);
    k.box(M.walnut, sx * (w / 2 - 0.12) - 0.03, 0, d / 2 - 0.16, sx * (w / 2 - 0.12) + 0.03, 0.715, d / 2 - 0.1);
    k.box(M.walnut, sx * (w / 2 - 0.12) - 0.025, 0.66, -d / 2 + 0.1, sx * (w / 2 - 0.12) + 0.025, 0.715, d / 2 - 0.1);
  }
  const per = w >= 1.5 ? 2 : 1;
  for (let i = 0; i < per; i++) {
    const x = per === 1 ? 0 : (i - 0.5) * (w / 2);
    for (const s of [-1, 1]) {
      k.save().offset(x, s * (d / 2 + 0.38), s > 0 ? Math.PI : 0);
      chair(k, M);
      k.restore();
    }
  }
  // a runner, a vase of flowers
  k.box(M.drape, -w / 2 + 0.25, 0.755, -0.16, w / 2 - 0.25, 0.758, 0.16);
  k.lathe(M.ceramic, [[0, 0], [0.05, 0], [0.07, 0.08], [0.04, 0.2], [0.045, 0.22], [0, 0.2]], 0.05, 0.755, 0, 24);
  for (let i = 0; i < 5; i++) {
    const a = i * 1.3;
    k.tube(M.color(0x5f7a45, 0.8), [[0.05, 0.95, 0], [0.05 + Math.cos(a) * 0.08, 1.1, Math.sin(a) * 0.08], [0.05 + Math.cos(a) * 0.14, 1.2 + (i % 2) * 0.06, Math.sin(a) * 0.14]], 0.004, 8);
    k.sphere(M.color(0xf2efe6, 0.8), 0.05 + Math.cos(a) * 0.14, 1.22 + (i % 2) * 0.06, Math.sin(a) * 0.14, 0.03, 1, 0.8, 1, 1);
  }
  return h ? pendants(k, M, per === 2 ? [-w / 4, w / 4] : [0], 0, h, 1.55) : [];
}

/** dome pendants hanging from the ceiling (h) down to y; returns their light positions */
export function pendants(k, M, xs, z, h, y) {
  return xs.map((x) => {
    k.cyl(M.blackMetal, x, y + 0.2, z, 0.003, h, 6);
    k.cyl(M.blackMetal, x, h - 0.012, z, 0.06, h, 20);
    k.lathe(M.blackMetal, [[0.004, 0.2], [0.06, 0.19], [0.14, 0.12], [0.19, 0.02], [0.2, 0]], x, y, z, 32);
    k.lathe(M.shade, [[0.195, 0.001], [0.135, 0.115], [0.055, 0.185], [0.004, 0.195]], x, y, z, 32);
    k.sphere(M.bulb, x, y + 0.08, z, 0.04, 1, 1, 1, 1);
    return new THREE.Vector3(x, y + 0.02, z);
  });
}

export function island(k, M, w, d = 0.9) {
  k.box(M.color(GAP, 0.9), -w / 2 + 0.05, 0, -d / 2 + 0.05, w / 2 - 0.05, 0.1, d / 2 - 0.05);
  k.box(M.oak, -w / 2, 0.1, -d / 2, w / 2, 0.87, d / 2);
  k.box(M.quartz, -w / 2 - 0.02, 0.87, -d / 2 - 0.02, w / 2 + 0.02, 0.9, d / 2 + 0.25);
  for (const x of [-w / 4, w / 4]) {
    k.cyl(M.blackMetal, x, 0, d / 2 + 0.45, 0.18, 0.012, 24);
    k.cyl(M.blackMetal, x, 0, d / 2 + 0.45, 0.02, 0.64, 10);
    k.cyl(M.chairSeat, x, 0.64, d / 2 + 0.45, 0.19, 0.69, 24);
  }
}

// ---------- hall ----------

export function console_(k, M, w = 1.2) {
  const d = 0.35;
  k.box(M.walnut, -w / 2, 0.72, 0, w / 2, 0.76, d);
  for (const x of [-w / 2 + 0.03, w / 2 - 0.05]) k.box(M.blackMetal, x, 0, 0.02, x + 0.02, 0.72, d - 0.02);
  k.box(M.blackMetal, -w / 2 + 0.03, 0.14, 0.02, w / 2 - 0.03, 0.16, d - 0.02);
  // round mirror above, bowl and a small lamp
  roundMirror(k, M, 0, 1.45, 0.36);
  k.lathe(M.ceramic, [[0, 0], [0.04, 0], [0.11, 0.04], [0.12, 0.06], [0.11, 0.06], [0.1, 0.045], [0, 0.01]], -w / 4, 0.76, d / 2, 24);
  vase(k, M, w / 3, 0.76, d / 2, 0.26);
}

export function roundMirror(k, M, x, y, r) {
  const g = new THREE.CircleGeometry(r, 48);
  g.translate(x, y, 0.025);
  k.add(M.mirror, g);
  const ring = new THREE.TorusGeometry(r, 0.012, 8, 64);
  ring.translate(x, y, 0.025);
  k.add(M.brass, ring);
}

export function shoeCabinet(k, M, w, d = 0.3) {
  k.box(M.lacquer, -w / 2, 0.1, 0, w / 2, 0.98, d - 0.03);
  k.box(M.color(GAP, 0.9), -w / 2 + 0.01, 0.1, d - 0.03, w / 2 - 0.01, 0.97, d - 0.021);
  const n = Math.max(1, Math.round(w / 0.45)), fw = w / n;
  for (let i = 0; i < n; i++) k.box(M.lacquer, -w / 2 + i * fw + 0.002, 0.1, d - 0.02, -w / 2 + (i + 1) * fw - 0.002, 0.98, d);
  k.box(M.oak, -w / 2 - 0.01, 0.98, 0, w / 2 + 0.01, 1.01, d + 0.01);
  k.box(M.strip, -w / 2 + 0.02, 0.09, d - 0.04, w / 2 - 0.02, 0.098, d - 0.03);
}

export function coatRack(k, M, w = 0.9) {
  k.box(M.oak, -w / 2, 1.68, 0, w / 2, 1.76, 0.02);
  const n = Math.round(w / 0.2);
  for (let i = 0; i < n; i++) {
    const x = -w / 2 + (w / n) * (i + 0.5);
    k.tube(M.blackMetal, [[x, 1.72, 0.02], [x, 1.71, 0.07], [x, 1.74, 0.09]], 0.006, 8);
  }
  // a coat and a scarf
  k.rbox(M.color(0x3b4048, 0.95), -w / 4, 1.3, 0.12, 0.42, 0.78, 0.12, 0.05);
  k.rbox(M.cushionA, w / 4, 1.45, 0.08, 0.16, 0.5, 0.05, 0.02);
}

export function shelving(k, M, w, h, d = 0.4) {
  for (const x of [-w / 2, w / 2 - 0.02]) k.box(M.lacquer, x, 0, 0, x + 0.02, h, d);
  const R = rnd(Math.round(w * 977));
  for (let y = 0.1; y < h - 0.2; y += 0.4) {
    k.box(M.lacquer, -w / 2, y, 0, w / 2, y + 0.02, d);
    // boxes and baskets
    let x = -w / 2 + 0.05;
    while (x < w / 2 - 0.3) {
      const bw = 0.2 + R() * 0.2, bh = 0.15 + R() * 0.15;
      k.rbox(M.color([0xcbb894, 0xe4ded2, 0x8e8a83, 0xb7a58b][Math.floor(R() * 4)], 0.9), x + bw / 2, y + 0.02 + bh / 2, d / 2, bw, bh, d * 0.8, 0.01, 1);
      x += bw + 0.05 + R() * 0.1;
    }
  }
}

// ---------- bathroom ----------
// The drawing gives each fitting's outline; these fill an outline of `w` x `d` (d from the wall).

/** wall-hung WC in front of a tiled cistern boxing */
export function toilet(k, M, w, d, h) {
  const bw = Math.min(w, 0.6);
  k.box(M.tileWall, -bw / 2, 0, 0, bw / 2, 1.1, 0.2);
  k.box(M.chrome, -0.12, 0.98, 0.2, 0.12, 1.07, 0.208);
  k.box(M.ceramic, -0.06, 1.0, 0.208, 0.06, 1.05, 0.212);
  k.save().offset(0, 0.2);
  const bowl = new THREE.LatheGeometry([[0.0, 0.0], [0.12, 0.0], [0.17, 0.08], [0.185, 0.17], [0.18, 0.19], [0.0, 0.19]].map(([r, y]) => new THREE.Vector2(r, y)), 32);
  bowl.scale(1, 1, 1.45);
  bowl.translate(0, 0.22, 0.25);
  k.add(M.ceramic, bowl);
  k.box(M.ceramic, -0.15, 0.25, 0, 0.15, 0.41, 0.12);
  const seat = new THREE.CylinderGeometry(0.185, 0.185, 0.025, 32);
  seat.scale(1, 1, 1.45);
  seat.translate(0, 0.425, 0.25);
  k.add(M.ceramic, seat);
  k.restore();
  // paper holder on the boxing's side: an arm and the roll on it
  k.box(M.chrome, bw / 2 + 0.002, 0.7, 0.12, bw / 2 + 0.02, 0.715, 0.135);
  k.box(M.chrome, bw / 2 + 0.02, 0.7, 0.12, bw / 2 + 0.13, 0.715, 0.135);
  const roll = new THREE.CylinderGeometry(0.055, 0.055, 0.1, 24);
  roll.rotateZ(Math.PI / 2);
  roll.translate(bw / 2 + 0.075, 0.66, 0.127);
  k.add(M.color(0xfbfaf7, 0.95), roll);
}

/** floating vanity with a vessel basin, mirror cabinet and a light above */
/** floating vanity w wide with one or two vessel basins, a mirror and a light bar */
export function vanity(k, M, w, h, bowls = 1, d = 0.48) {
  const y0 = 0.42, y1 = 0.82;
  k.box(M.walnut, -w / 2, y0, 0, w / 2, y1 - 0.03, d - 0.02);
  k.box(M.color(GAP, 0.9), -w / 2 + 0.01, (y0 + y1) / 2 - 0.004, d - 0.02, w / 2 - 0.01, (y0 + y1) / 2 + 0.004, d - 0.018);
  if (bowls > 1) k.box(M.color(GAP, 0.9), -0.004, y0 + 0.01, d - 0.02, 0.004, y1 - 0.04, d - 0.018);
  k.box(M.quartz, -w / 2, y1 - 0.03, 0, w / 2, y1, d);
  for (let i = 0; i < bowls; i++) {
    const x = bowls > 1 ? (i - 0.5) * (w / 2) : 0;
    const r = Math.min(0.2, d / 2 - 0.03, (bowls > 1 ? w / 4 : w / 2) - 0.04) / 0.2;
    k.lathe(M.ceramic, [[0, 0], [0.12, 0], [0.19, 0.04], [0.2, 0.13], [0.19, 0.13], [0.18, 0.05], [0.11, 0.015], [0, 0.015]].map(([a, b]) => [a * r, b]), x, y1, d / 2 + 0.02, 32);
    k.cyl(M.chrome, x, y1, 0.08, 0.02, y1 + 0.28, 16);
    k.box(M.chrome, x - 0.012, y1 + 0.25, 0.08, x + 0.012, y1 + 0.27, 0.24);
  }
  // one mirror and light bar over the whole vanity
  const mw = Math.min(w, bowls > 1 ? 1.6 : 1.0);
  k.box(M.color(GAP, 0.9), -mw / 2, 1.1, 0, mw / 2, 1.9, 0.02);
  k.box(M.mirror, -mw / 2 + 0.005, 1.105, 0.02, mw / 2 - 0.005, 1.895, 0.025);
  k.rbox(M.strip, 0, 1.97, 0.06, mw * 0.8, 0.03, 0.06, 0.012, 1);
  k.rbox(M.chrome, 0, 1.97, 0.03, mw * 0.8 + 0.02, 0.04, 0.02, 0.008, 1);
  // soap, a small plant
  k.rbox(M.color(0xd9cbb2, 0.4), w / 2 - 0.15, y1 + 0.06, 0.12, 0.07, 0.12, 0.07, 0.02, 1);
  k.cyl(M.pot, -w / 2 + 0.12, y1, 0.14, 0.05, y1 + 0.1, 16);
  k.sphere(M.color(0x5f8a48, 0.7), -w / 2 + 0.12, y1 + 0.16, 0.14, 0.08, 1, 1.1, 1, 1);
  return new THREE.Vector3(0, 1.9, 0.3);
}

/** built-in bath, `w` along the wall, `d` deep; tap and hand shower at the end `side` (+1: frame +x) */
export function bathtub(k, M, w, d, side = 1) {
  const h = 0.56, rim = 0.07;
  // tiled apron round the sides
  k.box(M.tileWall, -w / 2, 0, d - 0.06, w / 2, h - 0.02, d);
  k.box(M.tileWall, -w / 2, 0, 0, -w / 2 + 0.06, h - 0.02, d);
  k.box(M.tileWall, w / 2 - 0.06, 0, 0, w / 2, h - 0.02, d);
  // deck with an oval opening, and the basin sunk into it
  const iw = w - 2 * rim, id = d - 2 * rim;
  const deck = new THREE.Shape([new THREE.Vector2(-w / 2, 0), new THREE.Vector2(w / 2, 0), new THREE.Vector2(w / 2, d), new THREE.Vector2(-w / 2, d)]);
  const hole = new THREE.Path();
  hole.absellipse(0, d / 2, iw / 2, id / 2, 0, Math.PI * 2, true);
  deck.holes.push(hole);
  const dg = new THREE.ExtrudeGeometry(deck, { depth: 0.03, bevelEnabled: false, curveSegments: 40 });
  dg.rotateX(Math.PI / 2);
  dg.translate(0, h, 0);
  k.add(M.ceramic, dg);
  const bowl = new THREE.SphereGeometry(1, 40, 12, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2);
  bowl.scale(iw / 2, 0.42, id / 2);
  bowl.translate(0, h - 0.002, d / 2);
  // seen from inside: turn the faces round
  const idx = bowl.index.array;
  for (let i = 0; i < idx.length; i += 3) [idx[i + 1], idx[i + 2]] = [idx[i + 2], idx[i + 1]];
  const n = bowl.attributes.normal;
  for (let i = 0; i < n.count; i++) n.setXYZ(i, -n.getX(i), -n.getY(i), -n.getZ(i));
  k.add(M.ceramic, bowl);
  // mixer and hand shower on the wall at the tap end
  const s = side >= 0 ? 1 : -1, tx = s * (w / 2 - 0.3);
  k.box(M.chrome, tx - 0.08, h + 0.2, 0, tx + 0.08, h + 0.26, 0.04);
  k.tube(M.chrome, [[tx, h + 0.23, 0.04], [tx, h + 0.22, 0.14], [tx, h + 0.15, 0.18]], 0.012, 12);
  k.cyl(M.chrome, tx + s * 0.2, h + 0.3, 0.03, 0.012, h + 1.4, 12);
  k.cyl(M.chrome, tx + s * 0.2, h + 1.3, 0.06, 0.05, h + 1.33, 24);
  // glass screen at the shower end
  const g0 = s * (w / 2 - 0.9), g1 = s * (w / 2 - 0.1);
  k.box(M.showerGlass, Math.min(g0, g1), h, d - 0.01, Math.max(g0, g1), h + 1.4, d);
  k.box(M.chrome, Math.min(g0, g1), h + 1.39, d - 0.015, Math.max(g0, g1), h + 1.4, d + 0.005);
  // rolled towels on the deck at the other end
  for (let i = 0; i < 2; i++) {
    const g = new THREE.CylinderGeometry(0.06, 0.06, 0.3, 16);
    g.rotateZ(Math.PI / 2);
    g.translate(-s * (w / 2 - 0.3), h + 0.06 + i * 0.11, 0.04 + 0.03);
    k.add(M.towel, g);
  }
}

/** a counter over washing machine and dryer */
export function laundry(k, M, w, d) {
  const n = Math.max(1, Math.min(2, Math.floor(w / 0.6)));
  const mw = 0.6;
  for (let i = 0; i < n; i++) {
    const x = -w / 2 + 0.02 + i * (mw + 0.02) + mw / 2;
    k.rbox(M.color(0xf5f5f3, 0.3), x, 0.42, d / 2, mw - 0.01, 0.84, Math.min(d, 0.58) - 0.02, 0.02, 1);
    k.disc(M.steel, x, 0.42, d - 0.01, 0.2, 0.03);
    k.disc(M.blackGlass, x, 0.42, d + 0.003, 0.16, 0.02);
    k.box(M.color(0xdedcd8, 0.4), x - 0.26, 0.74, d - 0.01, x + 0.1, 0.8, d + 0.005);
  }
  k.box(M.quartz, -w / 2, 0.86, 0, w / 2, 0.9, d + 0.01);
  // folded towels
  for (let i = 0; i < 3; i++) k.rbox(M.towel, w / 2 - 0.25 + (i % 2) * 0.01, 0.92 + i * 0.045, d / 2, 0.32, 0.04, 0.24, 0.015, 1);
}

export function towelRail(k, M, h = 1.2) {
  for (const x of [-0.25, 0.25]) k.cyl(M.chrome, x, 0.4, 0.06, 0.012, h + 0.4, 10);
  for (let y = 0.5; y < h + 0.4; y += 0.16) k.box(M.chrome, -0.25, y, 0.05, 0.25, y + 0.018, 0.07);
  k.rbox(M.towel, 0, 1.05, 0.085, 0.42, 0.55, 0.04, 0.015);
}

/** a pleated curtain panel, w wide, from the floor up to h, centred on the origin, facing +z */
export function curtain(k, mat, w, h, amp = 0.02) {
  const folds = Math.max(3, Math.round(w / 0.11)), seg = folds * 6;
  const g = new THREE.PlaneGeometry(w, h - 0.02, seg, 1);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i);
    p.setZ(i, Math.sin(((x + w / 2) / w) * folds * Math.PI * 2) * amp);
  }
  g.computeVertexNormals();
  g.translate(0, h / 2 + 0.01, 0);
  k.add(mat, g);
  // gathered heading at the top
  k.box(mat, -w / 2, h - 0.08, -amp, w / 2, h, amp);
}

// ---------- pieces as the drawings give them ----------

/**
 * Corner sofa from the drawing's boxes in plan space: [cx, cy, w, d, z0, z1, angle, part] - each
 * box w along `angle`, d across it; parts: seat (base and cushion), back, arm. Drawn with the kit
 * placed per box (the boxes come turned and mirrored as drawn).
 */
export function sofaBoxes(k, M, boxes, mat = M.sofa) {
  for (const [cx, cy, w, d, , , a, part] of boxes) {
    // the kit's frame x along the box's w: facing a - 90 degrees
    k.at(cx, cy, a - Math.PI / 2);
    const legH = 0.08;
    if (part === 'seat') {
      k.rbox(mat, 0, legH + 0.11, 0, w, 0.22, d, 0.04);
      // seat cushions of about 60 cm along the longer side
      const along = w >= d, L = along ? w : d, n = Math.max(1, Math.round(L / 0.62));
      for (let i = 0; i < n; i++) {
        const t = -L / 2 + (L / n) * (i + 0.5);
        if (along) k.rbox(mat, t, legH + 0.29, 0, L / n - 0.012, 0.15, d - 0.01, 0.06);
        else k.rbox(mat, 0, legH + 0.29, t, w - 0.01, 0.15, L / n - 0.012, 0.06);
      }
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) k.cyl(M.walnut, sx * (w / 2 - 0.08), 0, sz * (d / 2 - 0.08), 0.02, legH, 8, 0.024);
    } else if (part === 'back') {
      k.rbox(mat, 0, legH + 0.36, 0, w, 0.72, d, 0.07);
      // loose back cushions leaning on it
      const n = Math.max(1, Math.round(w / 0.62));
      for (let i = 0; i < n; i++) {
        const t = -w / 2 + (w / n) * (i + 0.5);
        k.rbox(mat, t, legH + 0.58, 0, w / n - 0.03, 0.42, d * 0.9, 0.08);
      }
    } else {
      k.rbox(mat, 0, legH + 0.26, 0, w, 0.52, d, 0.06);
    }
  }
}

/**
 * A coffee table of a nesting pair, centred on the origin: w x d top at height h. The higher one
 * stands on a pedestal (the lower one slides in under its edge), the lower one on four legs.
 */
export function nestTable(k, M, w, d, h = 0.42) {
  k.rbox(M.walnut, 0, h - 0.015, 0, w, 0.03, d, 0.012, 1);
  if (h >= 0.4) {
    k.rbox(M.blackMetal, 0, (h - 0.03) / 2, 0, Math.min(0.16, w * 0.3), h - 0.03, Math.min(0.16, d * 0.3), 0.02, 1);
    k.rbox(M.blackMetal, 0, 0.01, 0, Math.min(0.34, w * 0.6), 0.02, Math.min(0.34, d * 0.6), 0.01, 1);
  } else {
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) k.cyl(M.blackMetal, sx * (w / 2 - 0.04), 0, sz * (d / 2 - 0.04), 0.011, h - 0.03, 8);
  }
}

/** a dining table centred on the origin, long side along x (the chairs are placed by the caller) */
export function diningTable(k, M, w = 1.6, d = 0.9) {
  k.rbox(M.oak, 0, 0.735, 0, w, 0.04, d, 0.012, 1);
  for (const sx of [-1, 1]) {
    const x = sx * (w / 2 - 0.12);
    k.box(M.walnut, x - 0.03, 0, -d / 2 + 0.1, x + 0.03, 0.715, -d / 2 + 0.16);
    k.box(M.walnut, x - 0.03, 0, d / 2 - 0.16, x + 0.03, 0.715, d / 2 - 0.1);
    k.box(M.walnut, x - 0.025, 0.66, -d / 2 + 0.1, x + 0.025, 0.715, d / 2 - 0.1);
  }
  // a runner, a vase of flowers
  k.box(M.drape, -w / 2 + 0.25, 0.755, -0.16, w / 2 - 0.25, 0.758, 0.16);
  k.lathe(M.ceramic, [[0, 0], [0.05, 0], [0.07, 0.08], [0.04, 0.2], [0.045, 0.22], [0, 0.2]], 0.05, 0.755, 0, 24);
  for (let i = 0; i < 5; i++) {
    const a = i * 1.3;
    k.tube(M.color(0x5f7a45, 0.8), [[0.05, 0.95, 0], [0.05 + Math.cos(a) * 0.08, 1.1, Math.sin(a) * 0.08], [0.05 + Math.cos(a) * 0.14, 1.2 + (i % 2) * 0.06, Math.sin(a) * 0.14]], 0.004, 8);
    k.sphere(M.color(0xf2efe6, 0.8), 0.05 + Math.cos(a) * 0.14, 1.22 + (i % 2) * 0.06, Math.sin(a) * 0.14, 0.03, 1, 0.8, 1, 1);
  }
}

/** an air-conditioner's outdoor unit standing on the loggia floor, w wide, d deep */
export function acUnit(k, M, w = 0.8, d = 0.3) {
  const h = 0.55;
  k.rbox(M.color(0xeeeeea, 0.45), 0, h / 2 + 0.04, d / 2, w, h, d, 0.015, 1);
  // the fan behind a round grille, on the left of the front
  const fx = -w / 2 + h / 2 + 0.03;
  k.disc(M.color(0x2e3033, 0.6), fx, h / 2 + 0.04, d + 0.001, h * 0.4, 0.004);
  for (const r of [0.08, 0.14, 0.2]) {
    const ring = new THREE.TorusGeometry(Math.min(r, h * 0.4), 0.004, 4, 32);
    ring.translate(fx, h / 2 + 0.04, d + 0.005);
    k.add(M.color(0xd9d9d4, 0.4), ring);
  }
  for (const x of [-w / 2 + 0.06, w / 2 - 0.06]) k.box(M.blackMetal, x - 0.02, 0, 0.02, x + 0.02, 0.04, d - 0.02);
}

// ---------- lifts ----------

/**
 * A lift car standing at the floor, in its shaft: origin at the middle of its back wall, the doors
 * at z = d. w across, up to height h (the cut of the floor view). Brushed steel walls, a stone
 * floor, a mirror and a handrail on the back wall, the closed centre-opening doors.
 */
export function liftCar(k, M, w, d, h, doorW) {
  const t = 0.03, top = Math.min(h, 2.3);
  k.box(M.darkStone, -w / 2, 0, 0, w / 2, 0.02, d);
  k.box(M.steel, -w / 2, 0, 0, w / 2, top, t);
  for (const s of [-1, 1]) k.box(M.steel, s * (w / 2) - (s > 0 ? t : 0), 0, t, s * (w / 2) + (s < 0 ? t : 0), top, d - t);
  // front: panels each side of the doors, the two leaves meeting in the middle
  for (const s of [-1, 1]) {
    const a = s * (doorW / 2), b = s * (w / 2);
    k.box(M.steel, Math.min(a, b), 0, d - t, Math.max(a, b), top, d);
  }
  k.box(M.steel, -doorW / 2, 2.1, d - t, doorW / 2, top, d);
  k.box(M.chrome, -doorW / 2, 0.02, d - t + 0.005, -0.003, 2.1, d - 0.005);
  k.box(M.chrome, 0.003, 0.02, d - t + 0.005, doorW / 2, 2.1, d - 0.005);
  // mirror and handrail on the back wall, the button panel beside the doors
  k.box(M.mirror, -w / 2 + 0.2, 0.95, t, w / 2 - 0.2, Math.min(2.15, top - 0.05), t + 0.004);
  k.box(M.chrome, -w / 2 + 0.15, 0.88, t + 0.04, w / 2 - 0.15, 0.92, t + 0.06);
  for (const x of [-w / 2 + 0.2, w / 2 - 0.2]) k.box(M.chrome, x - 0.01, 0.88, t, x + 0.01, 0.92, t + 0.05);
  const px = doorW / 2 + Math.min(0.25, (w - doorW) / 4);
  k.box(M.blackGlass, px - 0.08, 0.9, d - t - 0.006, px + 0.08, 1.45, d - t);
  for (let i = 0; i < 6; i++) k.disc(M.chrome, px - 0.03 + (i % 2) * 0.06, 1.0 + Math.floor(i / 2) * 0.12, d - t - 0.008, 0.014, 0.006, 16);
}

/**
 * The landing side of a lift: a stainless portal on the hall face of the shaft wall (origin there,
 * facing the hall), the closed doors in it and the call buttons beside it.
 */
export function liftPortal(k, M, doorW) {
  const jw = 0.07, hh = 2.1;
  k.box(M.steel, -doorW / 2 - jw, 0, -0.01, -doorW / 2, hh + jw, 0.02);
  k.box(M.steel, doorW / 2, 0, -0.01, doorW / 2 + jw, hh + jw, 0.02);
  k.box(M.steel, -doorW / 2, hh, -0.01, doorW / 2, hh + jw, 0.02);
  k.box(M.chrome, -doorW / 2, 0, -0.02, -0.003, hh, 0.008);
  k.box(M.chrome, 0.003, 0, -0.02, doorW / 2, hh, 0.008);
  // the sill in front
  k.box(M.steel, -doorW / 2 - 0.02, 0, 0, doorW / 2 + 0.02, 0.012, 0.09);
  // call buttons
  const bx = doorW / 2 + jw + 0.18;
  k.box(M.steel, bx - 0.05, 0.95, -0.005, bx + 0.05, 1.25, 0.012);
  for (const y of [1.04, 1.16]) k.disc(M.chrome, bx, y, 0.016, 0.018, 0.008, 16);
  k.box(M.blackGlass, bx - 0.04, 1.32, -0.005, bx + 0.04, 1.38, 0.012);
}
