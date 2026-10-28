// Grass you can see the blades of (high quality): tufts of blades on the lawns round the camera,
// when it is low (the walks, the street views). The lawns are known from the walk map's ground grid
// (public/models/site_walk.json: what is underfoot, 1 m cells); within 36 m of the camera every lawn
// cell gets a few tufts, placed by the cell's own hash (they stay put when the patch is rebuilt as
// the camera moves on), thinning out with distance. A breeze sways the tips.
import * as THREE from 'three';
import { lampChunk } from './materials.js';
import { lawnTest } from './sitewalk.js';
import { bedTest } from './flowers.js';

const R = 30; // metres round the camera
const PER_CELL = 16; // tufts in a square metre of lawn, near the camera
const LAWN = { 3: 0.15, 6: 0.05 }; // ground kinds with grass -> their level (sitewalk.js KINDS)

function tuft() {
  // a tuft: 11 tapered, bent blades round a point, 7-13 cm tall (a kept lawn); colour from the root (dark)
  // to the tip, the lawn's own green (23.10.2026: lighter tips stood out as pale spikes)
  const pos = [], col = [], rnd = (() => { let s = 7; return () => ((s = (s * 16807) % 2147483647) / 2147483647); })();
  const root = new THREE.Color(0.05, 0.1, 0.025), tip = new THREE.Color(0.17, 0.33, 0.07), dry = new THREE.Color(0.32, 0.36, 0.14);
  for (let b = 0; b < 11; b++) {
    const a = rnd() * Math.PI * 2, r = rnd() * 0.08, h = 0.07 + rnd() * 0.06, w = 0.008 + rnd() * 0.006;
    const lean = 0.25 + rnd() * 0.45, la = rnd() * Math.PI * 2;
    const x0 = Math.cos(a) * r, z0 = Math.sin(a) * r;
    const t = (rnd() < 0.2 ? tip.clone().lerp(dry, 0.6) : tip.clone().offsetHSL((rnd() - 0.5) * 0.03, 0, (rnd() - 0.5) * 0.06));
    const px = Math.cos(la + Math.PI / 2), pz = Math.sin(la + Math.PI / 2);
    const seg = 2;
    for (let k = 0; k < seg; k++) {
      const u0 = k / seg, u1 = (k + 1) / seg;
      const p = (u) => [x0 + Math.cos(la) * lean * h * u * u, h * u, z0 + Math.sin(la) * lean * h * u * u];
      const [ax, ay, az] = p(u0), [bx, by, bz] = p(u1);
      const w0 = w * (1 - u0), w1 = w * (1 - u1);
      const c0 = root.clone().lerp(t, u0), c1 = root.clone().lerp(t, u1);
      const quad = [[ax - px * w0, ay, az - pz * w0, c0], [ax + px * w0, ay, az + pz * w0, c0], [bx + px * w1, by, bz + pz * w1, c1], [bx - px * w1, by, bz - pz * w1, c1]];
      for (const i of [0, 1, 2, 0, 2, 3]) {
        pos.push(quad[i][0], quad[i][1], quad[i][2]);
        col.push(quad[i][3].r, quad[i][3].g, quad[i][3].b);
      }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.computeVertexNormals();
  // the blades' normals up: lit like the lawn under them, not like thin cards
  const n = g.attributes.normal;
  for (let i = 0; i < n.count; i++) n.setXYZ(i, n.getX(i) * 0.25, 1, n.getZ(i) * 0.25);
  n.needsUpdate = true;
  return g;
}

const hash = (i, j, k) => {
  let h = (i * 374761393 + j * 668265263 + k * 2147483647) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
};

export function addGrass(scene, map, wind, beds = []) {
  const ground = Uint8Array.from(atob(map.ground), (ch) => ch.charCodeAt(0));
  const { x0, y0, nx, ny } = map;
  // on the lawn itself (the build's 25 cm mask), never on its kerb or the paving, nor in a flower bed
  const lawn = lawnTest(map);
  const inBed = bedTest(beds, 0.25);
  const onLawn = (x, y) => lawn(x, y) && !inBed(x, y);
  const MAX = Math.ceil(Math.PI * R * R * PER_CELL * 0.8);
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.9, side: THREE.DoubleSide, envMapIntensity: 0.6 });
  mat.onBeforeCompile = (sh) => {
    lampChunk(sh);
    sh.uniforms.uWindT = wind.t;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nuniform float uWindT;')
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        {
          float ph = instanceMatrix[3].x * 0.9 + instanceMatrix[3].z * 0.7;
          float sw = position.y * position.y * 6.0;
          transformed.x += sw * 0.03 * sin(uWindT * 1.9 + ph);
          transformed.z += sw * 0.02 * sin(uWindT * 1.5 + ph * 1.3);
        }`);
  };
  mat.customProgramCacheKey = () => 'grass';
  const im = new THREE.InstancedMesh(tuft(), mat, MAX);
  im.count = 0;
  im.frustumCulled = false;
  im.receiveShadow = true;
  im.name = 'grass';
  scene.add(im);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);
  let at = null;
  return {
    mesh: im,
    // the patch round the camera (rebuilt when it has moved 6 m; hidden from high up)
    update(camera) {
      const low = camera.position.y < 45;
      im.visible = low;
      if (!low) return;
      const cx = camera.position.x, cy = -camera.position.z;
      if (at && Math.hypot(cx - at[0], cy - at[1]) < 6) return;
      at = [cx, cy];
      let n = 0;
      const i0 = Math.max(0, Math.floor(cx - R - x0)), i1 = Math.min(nx - 1, Math.floor(cx + R - x0));
      const j0 = Math.max(0, Math.floor(cy - R - y0)), j1 = Math.min(ny - 1, Math.floor(cy + R - y0));
      for (let j = j0; j <= j1 && n < MAX; j++) {
        for (let i = i0; i <= i1 && n < MAX; i++) {
          const level = LAWN[ground[j * nx + i]];
          if (level === undefined) continue;
          const x = x0 + i + 0.5, y = y0 + j + 0.5, d = Math.hypot(x - cx, y - cy);
          if (d > R) continue;
          const keep = d < 14 ? 1 : 1 - (d - 14) / (R - 14) * 0.75;
          for (let k = 0; k < PER_CELL && n < MAX; k++) {
            if (hash(i, j, k + 11) > keep) continue;
            const gx = x0 + i + hash(i, j, k), gy = y0 + j + hash(j, i, k + 3);
            if (!onLawn(gx, gy)) continue;
            const sc = 0.85 + hash(i, k, j) * 0.4;
            q.setFromAxisAngle(up, hash(k, i, j) * Math.PI * 2);
            im.setMatrixAt(n++, m4.compose(p.set(gx, level - 0.005, -gy), q, s.set(sc, sc * (0.85 + hash(j, k, i) * 0.4), sc)));
          }
        }
      }
      im.count = n;
      im.instanceMatrix.needsUpdate = true;
    },
  };
}
