// Flower beds on the lawns along the walks (23.10.2026: "make the landscape more beautiful"): round
// beds of bedding flowers as in Dushanbe's parks and boulevards (petunias, salvia, tagetes, begonias),
// set into the lawn a couple of metres from the paving, 9 m apart at the least; dark soil in a stone
// edging, the flowers of one colour or a centre and a border of two. A clump is three crossed cards
// and one seen from above, its picture drawn here on a canvas (leaves, flower heads): the heads take
// the bed's colour, the leaves stay green. The walker goes round the beds (sitewalk.js takes them as
// posts) and the grass's blades keep out of them (grass.js).
import * as THREE from 'three';
import { TREES } from './config.js';
import { WIND } from './props.js';
import { lampChunk } from './materials.js';
import { lawnTest } from './sitewalk.js';

const LAWNS = { 3: 0.15, 6: 0.05 }; // ground kinds with grass -> their level (sitewalk.js KINDS)
const PATHS = new Set([2, 7]); // paving, the school's paving
const SPACING = 9; // metres between beds, at the least
// the flowers' colours (sRGB): magenta and red petunias, white begonias, yellow and orange tagetes,
// violet salvia, pink
const COLOURS = ['#e8336f', '#d8202c', '#f6f2ea', '#f6c11c', '#8e4fd2', '#ff7b1c', '#f27ea9', '#c2185b'];
// two-colour beds: centre, border
const PAIRS = [[1, 2], [0, 2], [4, 3], [5, 3], [3, 1], [6, 2], [7, 6]];

const hash = (i, j, k) => {
  let h = (i * 374761393 + j * 668265263 + k * 2147483647) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
};

function inPoly(p, x, y) {
  let c = false;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
    const [xi, yi] = p[i], [xj, yj] = p[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}
const segDist = (x, y, ax, ay, bx, by) => {
  const dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy;
  const t = L ? Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / L)) : 0;
  return Math.hypot(x - ax - t * dx, y - ay - t * dy);
};

let cache = null;
/** the beds, from the walk map: [{ x, y, r, level, colours: [centre, border] }] in site metres */
export function flowerBeds(map) {
  if (cache?.map === map) return cache.beds;
  const ground = Uint8Array.from(atob(map.ground), (ch) => ch.charCodeAt(0));
  const { x0, y0, nx, ny } = map;
  const kind = (i, j) => (i < 0 || j < 0 || i >= nx || j >= ny ? 0 : ground[j * nx + i]);
  const onLawn = lawnTest(map);
  // what a bed keeps clear of: tree trunks (and their roots), lamps, people, benches, play
  // equipment, cars, hedges and fences, the walk's starting points
  const trees = [
    ...TREES.list.map(([x, y]) => [x, y]),
    ...TREES.placed.filter((t) => t[2] < 1).map(([x, y]) => [x, y]),
  ];
  const starts = [map.spawn, ...Object.values(map.blocks ?? {})].filter(Boolean);
  const solids = map.solids.map((s) => {
    let bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity;
    for (const [x, y] of s) (bx0 = Math.min(bx0, x)), (by0 = Math.min(by0, y)), (bx1 = Math.max(bx1, x)), (by1 = Math.max(by1, y));
    return { s, bx0, by0, bx1, by1 };
  });
  const clear = (x, y, r) => {
    for (let k = 0; k < 16; k++) {
      const a = (k / 16) * Math.PI * 2;
      if (!onLawn(x + Math.cos(a) * (r + 0.3), y + Math.sin(a) * (r + 0.3))) return false;
    }
    if (!onLawn(x, y)) return false;
    for (const [px, py, pr] of map.posts) if (Math.hypot(x - px, y - py) < r + pr + 0.6) return false;
    for (const [tx, ty] of trees) if (Math.hypot(x - tx, y - ty) < r + 1.6) return false;
    for (const p of starts) if (Math.hypot(x - p.x, y - p.y) < r + 3) return false;
    const m = r + 0.6;
    for (const o of solids) {
      if (x < o.bx0 - m || x > o.bx1 + m || y < o.by0 - m || y > o.by1 + m) continue;
      if (inPoly(o.s, x, y)) return false;
      for (let i = 0, j = o.s.length - 1; i < o.s.length; j = i++) if (segDist(x, y, ...o.s[j], ...o.s[i]) < m) return false;
    }
    for (const [w, pts] of map.lines) {
      for (let i = 1; i < pts.length; i++) if (segDist(x, y, ...pts[i - 1], ...pts[i]) < r + w / 2 + 0.5) return false;
    }
    return true;
  };
  // lawn cells 2-3 m from the paving, in an order of their own (the cells' hash)
  const cand = [];
  for (let j = 0; j < ny; j++) {
    for (let i = 0; i < nx; i++) {
      if (LAWNS[kind(i, j)] === undefined) continue;
      let d = Infinity;
      for (let dj = -3; dj <= 3; dj++) for (let di = -3; di <= 3; di++) if (PATHS.has(kind(i + di, j + dj))) d = Math.min(d, Math.hypot(di, dj));
      if (d >= 1.9 && d <= 3.2) cand.push([i, j, hash(i, j, 5)]);
    }
  }
  cand.sort((a, b) => a[2] - b[2]);
  const beds = [], grid = new Map();
  const gk = (x, y) => `${Math.floor(x / SPACING)},${Math.floor(y / SPACING)}`;
  const crowded = (x, y) => {
    const ci = Math.floor(x / SPACING), cj = Math.floor(y / SPACING);
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (const o of grid.get(`${ci + a},${cj + b}`) ?? []) if (Math.hypot(x - o.x, y - o.y) < SPACING) return true;
    return false;
  };
  for (const [i, j, h] of cand) {
    const x = x0 + i + 0.5 + (hash(i, j, 6) - 0.5) * 0.5, y = y0 + j + 0.5 + (hash(i, j, 7) - 0.5) * 0.5;
    const r = 0.75 + hash(i, j, 8) * 0.5;
    if (crowded(x, y) || !clear(x, y, r)) continue;
    const two = h < 0.5;
    const pair = PAIRS[Math.floor(hash(i, j, 9) * PAIRS.length)];
    const one = Math.floor(hash(i, j, 10) * COLOURS.length);
    const bed = { x, y, r, level: LAWNS[kind(i, j)], colours: two ? pair : [one, one] };
    beds.push(bed);
    (grid.get(gk(x, y)) ?? grid.set(gk(x, y), []).get(gk(x, y))).push(bed);
  }
  cache = { map, beds };
  return beds;
}

/** (x, y) in site metres -> inside a bed (with a margin): for the grass's blades */
export function bedTest(beds, pad = 0.2) {
  const C = 4, cells = new Map();
  for (const d of beds) {
    for (let i = Math.floor((d.x - d.r - pad) / C); i <= Math.floor((d.x + d.r + pad) / C); i++) {
      for (let j = Math.floor((d.y - d.r - pad) / C); j <= Math.floor((d.y + d.r + pad) / C); j++) {
        const k = i * 100003 + j;
        if (!cells.has(k)) cells.set(k, []);
        cells.get(k).push(d);
      }
    }
  }
  return (x, y) => (cells.get(Math.floor(x / C) * 100003 + Math.floor(y / C)) ?? []).some((d) => Math.hypot(x - d.x, y - d.y) < d.r + pad);
}

// ---------- the clumps' picture ----------
// 512 x 256: a clump from the side on the left, from above on the right; leaves in greens, the
// flower heads light grey (tinted per bed in the shader), their centres golden (kept)
function clumpTexture() {
  const c = document.createElement('canvas');
  c.width = 512;
  c.height = 256;
  const g = c.getContext('2d');
  let s = 11;
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  const leaf = (x, y, w, h, a) => {
    g.save();
    g.translate(x, y);
    g.rotate(a);
    g.fillStyle = `hsl(${96 + rnd() * 30}, ${42 + rnd() * 20}%, ${15 + rnd() * 20}%)`;
    g.beginPath();
    g.ellipse(0, 0, w, h, 0, 0, Math.PI * 2);
    g.fill();
    g.restore();
  };
  const head = (x, y, r) => {
    const n = 5 + Math.floor(rnd() * 2), a0 = rnd() * Math.PI;
    for (let k = 0; k < n; k++) {
      const a = a0 + (k / n) * Math.PI * 2;
      const v = 200 + Math.floor(rnd() * 46) - (Math.sin(a) > 0.3 ? 30 : 0); // the lower petals in shade
      g.fillStyle = `rgb(${v}, ${v}, ${v})`;
      g.beginPath();
      g.ellipse(x + Math.cos(a) * r * 0.55, y + Math.sin(a) * r * 0.55, r * 0.55, r * 0.36, a, 0, Math.PI * 2);
      g.fill();
    }
    g.fillStyle = '#b8911f';
    g.beginPath();
    g.arc(x, y, r * 0.24, 0, Math.PI * 2);
    g.fill();
  };
  // side: a mound of leaves, the heads over its top half
  for (let k = 0; k < 110; k++) {
    const u = rnd(), x = 128 + (rnd() - 0.5) * 236 * Math.sqrt(1 - u * 0.7);
    const top = 256 - 170 * Math.sqrt(Math.max(0, 1 - ((x - 128) / 122) ** 2));
    leaf(x, top + (256 - top) * rnd() ** 0.7, 10 + rnd() * 12, 5 + rnd() * 4, rnd() * Math.PI);
  }
  for (let k = 0; k < 38; k++) {
    const x = 20 + rnd() * 216;
    const top = 256 - 186 * Math.sqrt(Math.max(0, 1 - ((x - 128) / 118) ** 2));
    head(x, top + 6 + rnd() * 52, 9 + rnd() * 5);
  }
  // from above: leaves over a disc, the heads all over it
  for (let k = 0; k < 170; k++) {
    const a = rnd() * Math.PI * 2, d = 112 * Math.sqrt(rnd());
    leaf(384 + Math.cos(a) * d, 128 + Math.sin(a) * d, 11 + rnd() * 12, 6 + rnd() * 4, rnd() * Math.PI);
  }
  for (let k = 0; k < 60; k++) {
    const a = rnd() * Math.PI * 2, d = 104 * Math.sqrt(rnd());
    head(384 + Math.cos(a) * d, 128 + Math.sin(a) * d, 9 + rnd() * 5);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

// three crossed cards and one from above, each face its own quad (front-facing both ways, the
// normals leaning up: lit like the lawn round them)
function clumpGeometry() {
  const pos = [], nor = [], uv = [], idx = [];
  const W = 0.2, H = 0.32;
  const quad = (p, n, cell) => {
    for (const flip of [false, true]) {
      const b = pos.length / 3;
      const nn = new THREE.Vector3(...n).multiplyScalar(flip ? -0.35 : 0.35).add(new THREE.Vector3(0, 1, 0)).normalize();
      for (let k = 0; k < 4; k++) {
        pos.push(...p[k]);
        nor.push(nn.x, nn.y, nn.z);
      }
      const [u0, u1] = cell;
      uv.push(u0, 0, u1, 0, u1, 1, u0, 1);
      if (flip) idx.push(b, b + 2, b + 1, b, b + 3, b + 2);
      else idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
    }
  };
  for (let k = 0; k < 3; k++) {
    const a = (k * Math.PI) / 3, dx = Math.cos(a) * W, dz = Math.sin(a) * W;
    quad([[-dx, 0, -dz], [dx, 0, dz], [dx, H, dz], [-dx, H, -dz]], [dz, 0, -dx], [0, 0.5]);
  }
  const T = W * 0.95, y = H * 0.7;
  const b = pos.length / 3;
  for (const p of [[-T, y, T], [T, y, T], [T, y, -T], [-T, y, -T]]) {
    pos.push(...p);
    nor.push(0, 1, 0);
  }
  uv.push(0.5, 0, 1, 0, 1, 1, 0.5, 1);
  idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geo.setIndex(idx);
  return geo;
}

/** the beds in the scene: soil, edging and flowers, four draw calls */
export function addFlowers(scene, map, toScene) {
  const beds = flowerBeds(map);
  if (!beds.length) return { beds, group: null };
  const group = new THREE.Group();
  group.name = 'flower beds';
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);
  const lit = (mat, key) => {
    mat.onBeforeCompile = lampChunk;
    mat.customProgramCacheKey = () => key;
    return mat;
  };

  // the soil, a little proud of the lawn, and the stone edging round it (a band and its top)
  const soil = new THREE.InstancedMesh(new THREE.CircleGeometry(1, 32).rotateX(-Math.PI / 2),
    lit(new THREE.MeshStandardMaterial({ color: 0x45362a, roughness: 1, envMapIntensity: 0.5 }), 'bed soil'), beds.length);
  const rim = new THREE.InstancedMesh(new THREE.RingGeometry(1, 1.12, 40).rotateX(-Math.PI / 2),
    lit(new THREE.MeshStandardMaterial({ color: 0xd8d2c6, roughness: 0.9, envMapIntensity: 0.6 }), 'bed rim'), beds.length);
  const band = new THREE.InstancedMesh(new THREE.CylinderGeometry(1.12, 1.12, 1, 40, 1, true).translate(0, 0.5, 0),
    rim.material, beds.length);
  beds.forEach((d, i) => {
    const w = toScene(d.x, d.y), R = d.r + 0.04;
    soil.setMatrixAt(i, m4.compose(p.set(w.x, d.level + 0.02, w.z), q.identity(), s.set(R, 1, R)));
    rim.setMatrixAt(i, m4.compose(p.set(w.x, d.level + 0.06, w.z), q, s.set(R, 1, R)));
    band.setMatrixAt(i, m4.compose(p.set(w.x, d.level - 0.03, w.z), q, s.set(R, 0.09, R)));
  });
  for (const m of [soil, rim, band]) {
    m.receiveShadow = true;
    m.frustumCulled = false;
    group.add(m);
  }

  // the flowers: clumps on a sunflower spiral, taller towards the middle (a mound), the border's
  // colour on the outer ring of a two-colour bed
  const list = [];
  beds.forEach((d, b) => {
    const n = Math.max(8, Math.round(Math.PI * d.r * d.r * 11));
    for (let k = 0; k < n; k++) {
      const t = Math.sqrt((k + 0.5) / n), a = k * 2.39996 + b;
      const rr = t * (d.r - 0.12);
      const x = d.x + Math.cos(a) * rr, y = d.y + Math.sin(a) * rr;
      const colour = COLOURS[t > 0.66 ? d.colours[1] : d.colours[0]];
      const sc = (0.85 + hash(b, k, 1) * 0.35) * (1.25 - 0.35 * t);
      list.push({ x, y, level: d.level + 0.02, sc, rot: hash(b, k, 2) * Math.PI * 2, colour });
    }
  });
  const geo = clumpGeometry();
  const bloom = new Float32Array(list.length * 3);
  const col = new THREE.Color();
  list.forEach((c, i) => {
    col.set(c.colour).offsetHSL((hash(i, 3, 3) - 0.5) * 0.02, 0, (hash(i, 4, 4) - 0.5) * 0.08);
    bloom.set([col.r, col.g, col.b], i * 3);
  });
  geo.setAttribute('aBloom', new THREE.InstancedBufferAttribute(bloom, 3));
  const mat = new THREE.MeshStandardMaterial({ map: clumpTexture(), alphaTest: 0.45, alphaToCoverage: true, roughness: 0.8, envMapIntensity: 0.55 });
  mat.onBeforeCompile = (sh) => {
    lampChunk(sh);
    sh.uniforms.uWindAmp = WIND.amp;
    sh.uniforms.uWindT = WIND.t;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec3 aBloom;\nvarying vec3 vBloom;\nuniform float uWindAmp;\nuniform float uWindT;')
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vBloom = aBloom;
        if (uWindAmp > 0.0) {
          float ph = instanceMatrix[3].x * 1.3 + instanceMatrix[3].z * 0.9;
          transformed.x += uWindAmp * position.y * position.y * 0.6 * sin(uWindT * 2.1 + ph);
          transformed.z += uWindAmp * position.y * position.y * 0.4 * sin(uWindT * 1.7 + ph * 1.3);
        }`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vBloom;')
      .replace('#include <map_fragment>', `#include <map_fragment>
        {
          // the petals (light grey in the picture) take the bed's colour, their shading kept
          vec3 c = diffuseColor.rgb;
          float petal = smoothstep(0.28, 0.45, min(min(c.r, c.g), c.b));
          diffuseColor.rgb = mix(c, vBloom * (0.35 + 0.75 * c.g), petal);
        }`)
      .replace('#include <alphatest_fragment>', `
        {
          // the cut-out thins out in the smaller mip levels: alpha up with the level sampled
          vec2 t = vMapUv * vec2(512.0, 256.0);
          vec2 dx = dFdx(t), dy = dFdy(t);
          diffuseColor.a *= 1.0 + 0.3 * max(0.0, 0.5 * log2(max(dot(dx, dx), dot(dy, dy))));
        }
        #include <alphatest_fragment>`);
  };
  mat.customProgramCacheKey = () => 'flowers';
  const clumps = new THREE.InstancedMesh(geo, mat, list.length);
  list.forEach((c, i) => {
    const w = toScene(c.x, c.y);
    q.setFromAxisAngle(up, c.rot);
    clumps.setMatrixAt(i, m4.compose(p.set(w.x, c.level, w.z), q, s.set(c.sc, c.sc * (0.9 + hash(i, 5, 5) * 0.25), c.sc)));
  });
  clumps.receiveShadow = true;
  clumps.castShadow = false;
  clumps.frustumCulled = false;
  clumps.name = 'flowers';
  group.add(clumps);
  scene.add(group);
  return { beds, group, count: list.length };
}
