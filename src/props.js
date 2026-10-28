// Trees, cars and people around the complex, drawn as instanced meshes at the positions the
// Blender build exports (model/complex.json): tree billboards (public/trees), car bodies
// (public/models/cars.glb), people generated here.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { Q } from './quality.js';
import { lampChunk } from './materials.js';
import TREES_INFO from '../public/trees/trees.json';

// deterministic noise so every visit looks the same
function rng(seed) {
  return () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
}

// ---------- trees ----------
// Billboards of photographed CC0 trees (Poly Haven), rendered in Blender (blender/trees): three
// upright quads crossed at 60 degrees, each face showing the tree from its side, plus one quad
// seen from above. Colour, cut-out and normals come from the renders, so the sun and the sky light
// them like the rest of the scene and they cast proper shadows. 14 triangles per tree, one draw
// call per kind; size, turn and tint vary per tree.
const TREE_URL = `${import.meta.env.BASE_URL}trees/`; // + a_ / b_ atlas prefix from trees.json
const SIDES = 6;

function impostorGeometry(v) {
  const pos = [], nor = [], uv = [], idx = [];
  const quad = (p0, p1, p2, p3, n, cell) => {
    const [u0, v0, du, dv] = cell;
    const base = pos.length / 3;
    pos.push(...p0, ...p1, ...p2, ...p3);
    for (let i = 0; i < 4; i++) nor.push(...n);
    uv.push(u0, v0, u0 + du, v0, u0 + du, v0 + dv, u0, v0 + dv);
    idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
  };
  const S = v.side, h = S / 2;
  for (let k = 0; k < SIDES; k++) {
    // view k was rendered from direction (sin a, -cos a) on the Blender ground plane = (sin a, cos a) here
    const a = (2 * Math.PI * k) / SIDES;
    const d = [Math.sin(a), 0, Math.cos(a)], r = [Math.cos(a), 0, -Math.sin(a)];
    quad([-r[0] * h, 0, -r[2] * h], [r[0] * h, 0, r[2] * h], [r[0] * h, S, r[2] * h], [-r[0] * h, S, -r[2] * h], d, v.cells[`side${k}`]);
  }
  // from above, level with the middle of the crown; image up = Blender +y = -z here
  const T = v.top / 2, y = v.height * 0.62;
  quad([-T, y, T], [T, y, T], [T, y, -T], [-T, y, -T], [0, 1, 0], v.cells.top);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}

/**
 * @param protos, list  the site plan's trees (model/complex.json: trees, tree_protos)
 * @param placed        trees on the podium decks, terraces and promenade: [x, y, z, height, radius, kind]
 */
// Foliage cut-outs thin out in the smaller mip levels (averaging leaves with sky lowers alpha below the
// cut), so distant trees would look bare. Alpha is scaled up with the mip level actually sampled
// (keeps the crown's coverage), then three.js sharpens it for alpha-to-coverage.
// a breeze in the trees (the TV film sets it; the site keeps them still): amplitude and time
export const WIND = { amp: { value: 0 }, t: { value: 0 } };

// bloom: '' (green), 'pink' or 'white': flowering trees (crape myrtle, sakura, white lilac): the
// leaves of the photographed crown recoloured in patches, the trunk and the shade left as they are
const BLOOM = { pink: '0.95, 0.5, 0.68', white: '0.97, 0.95, 0.9' };
function treeMaterial(atlas, size, bloom = '') {
  const loader = new THREE.TextureLoader();
  const color = loader.load(`${TREE_URL}${atlas}color_${size}.webp`);
  color.colorSpace = THREE.SRGBColorSpace;
  const normal = loader.load(`${TREE_URL}${atlas}normal_${size}.webp`);
  for (const t of [color, normal]) t.anisotropy = 4;
  const mat = new THREE.MeshStandardMaterial({
    map: color,
    normalMap: normal,
    alphaTest: 0.42,
    alphaToCoverage: true,
    roughness: 0.82,
    envMapIntensity: 0.55,
  });
  const px = size === '2k' ? 2048 : 1024;
  mat.onBeforeCompile = (sh) => {
    lampChunk(sh); // lit by the street lamps at night
    sh.uniforms.uWindAmp = WIND.amp;
    sh.uniforms.uWindT = WIND.t;
    // the crown sways a few centimetres, more towards the top, each tree in its own phase (the
    // periods divide 70 s: the film loops without a jump)
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nuniform float uWindAmp;\nuniform float uWindT;')
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        if (uWindAmp > 0.0) {
          float ph = 0.0;
          #ifdef USE_INSTANCING
            ph = instanceMatrix[3].x * 0.37 + instanceMatrix[3].z * 0.23;
          #endif
          float sw = uWindAmp * position.y * position.y * 0.004;
          transformed.x += sw * sin(uWindT * 1.0771 + ph);
          transformed.z += sw * 0.6 * sin(uWindT * 0.8976 + ph * 1.7);
        }`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <alphatest_fragment>', `
      {
        vec2 t = vMapUv * ${px.toFixed(1)};
        vec2 dx = dFdx(t), dy = dFdy(t);
        float mip = max(0.0, 0.5 * log2(max(dot(dx, dx), dot(dy, dy))));
        diffuseColor.a *= 1.0 + mip * 0.28;
        // a card seen edge-on is a thin smear through the crown: let it fade out as it turns away
        float facing = abs(dot(normalize(vNormal), normalize(vViewPosition)));
        diffuseColor.a *= smoothstep(0.12, 0.4, facing);
      }
      #include <alphatest_fragment>`);
    // the photographed crowns are a muted olive; the trees of the renders a fresh, sunny green: the
    // leaves (where green is not below red; the trunks are brown) are graded towards it (23.10.2026)
    sh.fragmentShader = sh.fragmentShader.replace('#include <map_fragment>', `#include <map_fragment>
      {
        vec3 c = diffuseColor.rgb;
        float leaf = smoothstep(-0.004, 0.006, c.g - c.r);
        vec3 outc = mix(c, c * vec3(0.9, 1.4, 0.55) * 1.3, leaf);
        ${bloom ? `
        vec2 q = vMapUv * 230.0;
        vec2 i = floor(q), f = fract(q);
        f = f * f * (3.0 - 2.0 * f);
        float h00 = fract(sin(dot(i, vec2(12.9898, 78.233))) * 43758.5453);
        float h10 = fract(sin(dot(i + vec2(1, 0), vec2(12.9898, 78.233))) * 43758.5453);
        float h01 = fract(sin(dot(i + vec2(0, 1), vec2(12.9898, 78.233))) * 43758.5453);
        float h11 = fract(sin(dot(i + vec2(1, 1), vec2(12.9898, 78.233))) * 43758.5453);
        float n = mix(mix(h00, h10, f.x), mix(h01, h11, f.x), f.y);
        float lum = dot(c, vec3(0.299, 0.587, 0.114));
        vec3 flower = vec3(${BLOOM[bloom]}) * (0.3 + 7.0 * lum);
        outc = mix(outc, flower, leaf * smoothstep(0.32, 0.6, n) * 0.95);` : ''}
        diffuseColor.rgb = outc;
      }`);
  };
  mat.customProgramCacheKey = () => `tree${px}${bloom}`;
  return mat;
}

export function addTrees(scene, protos, list, placed, toScene) {
  const size = Q.level === 'high' ? '2k' : '1k';
  const mats = {};
  const matFor = (atlas, bloom) => (mats[atlas + bloom] ??= treeMaterial(atlas, size, bloom));
  // kinds of tree -> rendered variants (alternating where there are two)
  // (full: the full-crowned broadleaf added on 21.10.2026, atlas c)
  const kinds = { broad: ['broad_b', 'full', 'broad', 'broad_b', 'full'], conifer: ['fir_a', 'fir_b'], poplar: ['poplar'], small: ['shrub'], shrub: ['shrub'],
    blossom: ['full', 'broad_b', 'shrub'], white: ['shrub', 'full'] };
  const bloomOf = { blossom: 'pink', white: 'white' };
  // site plan proto (height, radius, light crown) -> kind
  const pick = (p, i) => {
    if (p.light && p.h <= 6) return 'small';
    if (p.h >= 9 && i % 3 === 0) return 'conifer';
    if (p.r < 2.4 && i % 4 === 1) return 'poplar';
    return 'broad';
  };
  const items = [
    ...list.map(([x, y, sc, sz, rot, k], i) => ({ x, y, z: 0, h: protos[k].h * sc * sz, r: protos[k].r * sc, rot, kind: pick(protos[k], i) })),
    ...placed.map(([x, y, z, h, r, kind, city], i) => ({ x, y, z, h, r, rot: i * 2.39996, kind, city: !!city })),
  ];
  // the courtyards and the walks in flower (23.10.2026: "beautiful, saturated trees"): now and then a
  // small or middling broadleaf of the plan a pink-flowering one, more rarely a white one
  items.forEach((t, i) => {
    if (t.city || t.z > 1 || (t.kind !== 'broad' && t.kind !== 'small') || t.h > 11) return;
    if (i % 5 === 2) t.kind = 'blossom';
    else if (i % 11 === 7) t.kind = 'white';
  });
  const groups = {};
  items.forEach((t, i) => {
    const vs = kinds[t.kind] ?? kinds.broad;
    (groups[`${vs[i % vs.length]}|${bloomOf[t.kind] ?? ''}`] ??= []).push(t);
  });
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s = new THREE.Vector3(), e = new THREE.Euler();
  const tint = new THREE.Color(), white = new THREE.Color(1, 1, 1);
  const rnd = rng(23);
  for (const [key, group] of Object.entries(groups)) {
    const [variant, bloom] = key.split('|');
    const v = TREES_INFO[variant] ?? TREES_INFO.broad;
    if (!v) continue;
    const mesh = new THREE.InstancedMesh(impostorGeometry(v), matFor(v.atlas ?? '', bloom), group.length);
    group.forEach((t, i) => {
      const w = toScene(t.x, t.y);
      // the plan's height and crown radius, within the photographed tree's proportions
      const kv = t.h / v.height;
      const kh = THREE.MathUtils.clamp(t.r / v.radius, kv * 0.8, kv * 1.25);
      q.setFromEuler(e.set(0, t.rot + rnd() * Math.PI * 2, 0));
      m4.compose(p.set(w.x, t.z, w.z), q, s.set(kh, kv, kh));
      mesh.setMatrixAt(i, m4);
      // a little more or less green and light from tree to tree; a touch brighter than the
      // renders under an even sky, the fresh green of the client's renders in the sun
      tint.setHSL(0.27 + (rnd() - 0.5) * 0.05, 0.3 + rnd() * 0.15, 0.5 + (rnd() - 0.5) * 0.12).lerp(white, 0.7).multiplyScalar(1.1 + rnd() * 0.12);
      if (bloom) tint.setRGB(1, 1, 1).multiplyScalar(1.02 + rnd() * 0.12);
      mesh.setColorAt(i, tint);
    });
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.frustumCulled = false; // instances spread over the whole site
    mesh.name = bloom ? `trees ${variant} ${bloom}` : `trees ${variant}`;
    scene.add(mesh);
  }
}

// ---------- cars ----------
// Saloon, SUV and hatchback modelled in Blender (blender/props/build_cars.py): one instanced mesh
// per body type and material, a close-up and a far version (a quarter of the triangles) chosen per
// car by its distance from the camera. Paint is a clearcoat (MeshPhysicalMaterial: the lacquer layer
// is what makes car paint read as car paint); everything else is the standard material.
const CAR_URL = `${import.meta.env.BASE_URL}models/cars.glb`;
const CAR_PAINT = [0xe8e9eb, 0xc4c7cb, 0x24272c, 0x8f1f22, 0xf2efe8, 0x51606e, 0x1c2638, 0x7d8085];
const CAR_TYPES = ['saloon', 'saloon', 'suv', 'saloon', 'hatch', 'suv', 'saloon', 'hatch'];
const CAR_NEAR = Q.level === 'high' ? 120 : 60; // metres: closer than this, the detailed body

const carMats = {
  'Car paint': () => new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.42, metalness: 0.55, clearcoat: 1, clearcoatRoughness: 0.08, envMapIntensity: 1.1 }),
  'Car glass': () => new THREE.MeshStandardMaterial({ color: 0x121619, roughness: 0.05, metalness: 0.0, envMapIntensity: 1.3 }),
  'Car tyre': () => new THREE.MeshStandardMaterial({ color: 0x1b1b1d, roughness: 0.92 }),
  'Car rim': () => new THREE.MeshStandardMaterial({ color: 0xb9bdc1, roughness: 0.3, metalness: 0.9 }),
  'Car lamp': () => new THREE.MeshStandardMaterial({ color: 0xf4f4f0, roughness: 0.1, emissive: 0xfff6e2, emissiveIntensity: 0.15 }),
  'Car rear lamp': () => new THREE.MeshStandardMaterial({ color: 0x8c0d10, roughness: 0.2, emissive: 0x5a0000, emissiveIntensity: 0.3 }),
  'Car under': () => new THREE.MeshStandardMaterial({ color: 0x141414, roughness: 0.95 }),
};

// The file is quantized (KHR_mesh_quantization: 16-bit positions, 8-bit normals, the scale in the
// node). Baking the node's transform into those integer arrays would clamp every point to +-1 (cars
// squashed into boxes), so the attributes become plain floats first.
function dequantize(geo) {
  const g = geo.clone();
  for (const [name, a] of Object.entries(g.attributes)) {
    if (a.array instanceof Float32Array && !a.normalized) continue;
    const out = new Float32Array(a.count * a.itemSize);
    for (let i = 0; i < a.count; i++) for (let c = 0; c < a.itemSize; c++) out[i * a.itemSize + c] = a.getComponent(i, c);
    g.setAttribute(name, new THREE.BufferAttribute(out, a.itemSize));
  }
  return g;
}

let carUpdate = null;
// cars driving (the TV film): [{ type, color, at(t) -> { x, y, r } site metres }], placed by driveCars(t)
const movers = [];
let moversDirty = false;
/** Sort the cars into near / far bodies for this camera; true when anything changed. */
export function updateCars(camera) {
  return carUpdate?.(camera) ?? false;
}

/** Cars on the move (the TV film): set once with their routes, then placed for each frame. */
export function setDrivers(list) {
  movers.length = 0;
  movers.push(...list);
  moversDirty = true;
}
export function driveCars(t) {
  for (const m of movers) m.t = t;
  moversDirty = true;
}

export function addCars(scene, list, toScene) {
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  loader.load(CAR_URL, (gltf) => {
    const mats = {};
    const mat = (name) => (mats[name] ??= (carMats[name] ?? carMats['Car under'])());
    // body type -> { near: [InstancedMesh], far: [InstancedMesh] }
    const byType = {};
    const cars = list.map(([x, y, z, r, k], i) => ({ type: CAR_TYPES[(k + i) % CAR_TYPES.length], x, y, z, r, color: CAR_PAINT[(k * 3 + i) % CAR_PAINT.length] }));
    const SPARE = 3; // room in each body type for a few cars on the move
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      const node = o.parent?.isMesh || o.parent === gltf.scene ? o : o.parent;
      const [type, far] = (node.name || o.name).split('_');
      const parked = cars.filter((c) => c.type === type).length;
      if (!parked) return;
      const n = parked + SPARE;
      const slot = (byType[type] ??= { near: [], far: [] })[far ? 'far' : 'near'];
      const g = dequantize(o.geometry).applyMatrix4(o.matrixWorld);
      const im = new THREE.InstancedMesh(g, mat(o.material.name), n);
      im.castShadow = true;
      im.receiveShadow = true;
      im.frustumCulled = false;
      im.count = 0;
      slot.push(im);
      scene.add(im);
    });
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), one = new THREE.Vector3(1, 1, 1), c = new THREE.Color();
    const up = new THREE.Vector3(0, 1, 0);
    for (const car of cars) {
      const w = toScene(car.x, car.y);
      car.pos = new THREE.Vector3(w.x, car.z, w.z);
      // the build's cars face +x at r = 0 (Blender), the model's nose is +x too
      car.matrix = m4.compose(p.copy(car.pos), q.setFromAxisAngle(up, car.r), one).clone();
    }
    const last = new THREE.Vector3(1e9, 0, 0);
    carUpdate = (camera) => {
      if (camera.position.distanceToSquared(last) < 4 && !moversDirty) return false; // re-sort only when the camera or a car moved
      last.copy(camera.position);
      moversDirty = false;
      const driving = movers.filter((m) => byType[m.type]).map((m) => {
        const s = m.at(m.t ?? 0), w = toScene(s.x, s.y);
        const pos = new THREE.Vector3(w.x, 0.0, w.z);
        return { type: m.type, color: m.color, pos, matrix: m4.compose(pos, q.setFromAxisAngle(up, s.r), one).clone() };
      });
      for (const [type, slots] of Object.entries(byType)) {
        let nn = 0, nf = 0;
        for (const car of [...cars, ...driving.filter((d) => d.type === type).slice(0, SPARE)]) {
          if (car.type !== type) continue;
          const near = car.pos.distanceTo(camera.position) < CAR_NEAR;
          const set = near ? slots.near : slots.far;
          const idx = near ? nn++ : nf++;
          for (const im of set) {
            im.setMatrixAt(idx, car.matrix);
            if (im.material === mats['Car paint']) im.setColorAt(idx, c.setHex(car.color));
          }
        }
        for (const im of slots.near) (im.count = nn), (im.instanceMatrix.needsUpdate = true), im.instanceColor && (im.instanceColor.needsUpdate = true);
        for (const im of slots.far) (im.count = nf), (im.instanceMatrix.needsUpdate = true), im.instanceColor && (im.instanceColor.needsUpdate = true);
      }
      return true;
    };
  });
}

// ---------- people ----------
// Figures with real proportions (about 1.6-1.85 m): shaped torso and shoulders, upper and lower
// arms and legs, shoes, hands, neck, head and hair; in trousers or a skirt (with longer hair),
// standing or mid-stride (arms swinging against the legs), coloured per person. Instanced: one
// mesh per part, outfit and pose.
const CLOTHES = [0x2f3b52, 0x9b3a3a, 0xe3ddd0, 0x3d5f4a, 0x6a5a86, 0xc79a3c, 0x22252a, 0x7a8794, 0xb8a58a, 0xd6cfc2, 0x4d6b8a];
const TROUSERS = [0x262a33, 0x384b66, 0x4a4038, 0x1d1f22, 0x6b6f75, 0xb9ae9a];
const SKIRTS = [0x2a2c33, 0x6b2f3a, 0x3e4f6b, 0xb7a58c, 0x5a6b4a];
const SKIN = [0xe2b896, 0xc89878, 0xa06e4f, 0x7d533b];
const HAIR = [0x1f1a17, 0x3b2b20, 0x5a4330, 0x9a8f86, 0x1a1a1a, 0x7a5a3a];
const SHOES = [0x1b1b1d, 0x3a2a20, 0xe8e6e0, 0x2b2f38];
const TIGHTS = [0x1b1b1d, 0x2b2f38, 0x3a2a20, 0x9a7b66];

// a limb segment from a to b (points [x, y, z]), radius r0 at a, r1 at b
function limb(a, b, r0, r1, seg = 6) {
  const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b);
  const len = A.distanceTo(B);
  const g = new THREE.CylinderGeometry(r1, r0, len, seg, 1);
  g.translate(0, len / 2, 0);
  g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), B.clone().sub(A).normalize()));
  return g.translate(A.x, A.y, A.z);
}
const merge = (list) => mergeGeometries(list.map((g) => (g.index ? g.toNonIndexed() : g)));

function personParts(stride, skirt) {
  // legs from the hip, swung by `stride` (radians); the back leg bends a little at the knee
  const leg = (side) => {
    const swing = side * stride, hip = [side * 0.09, 0.92, 0];
    const knee = [hip[0], hip[1] - 0.44 * Math.cos(swing), 0.44 * Math.sin(swing)];
    const bend = side < 0 ? stride * 0.6 : 0;
    const ankle = [hip[0], knee[1] - 0.42 * Math.cos(swing - bend), knee[2] + 0.42 * Math.sin(swing - bend)];
    const thigh = skirt ? 0.055 : 0.075;
    return [limb(hip, knee, thigh, 0.052), limb(knee, ankle, 0.05, 0.038), new THREE.SphereGeometry(0.045, 6, 4).translate(...knee)];
  };
  const shoe = (side) => {
    const swing = side * stride, bend = side < 0 ? stride * 0.6 : 0;
    const kz = 0.44 * Math.sin(swing), ky = 0.92 - 0.44 * Math.cos(swing);
    const ay = ky - 0.42 * Math.cos(swing - bend), az = kz + 0.42 * Math.sin(swing - bend);
    return new THREE.SphereGeometry(0.5, 8, 5).scale(0.095, 0.085, 0.25).translate(side * 0.09, Math.max(0.04, ay - 0.025), az + 0.05);
  };
  // trousers: legs and hips in one colour, shoes in another; a skirt: the skirt in one colour,
  // the legs (tights) with the shoes
  const limbs = [...leg(1), ...leg(-1)];
  const legs = skirt
    ? merge([new THREE.CylinderGeometry(0.17, 0.25, 0.42, 10, 1, true).scale(1, 1, 0.8).translate(0, 0.78, 0)])
    : merge([...limbs, new THREE.CylinderGeometry(0.155, 0.16, 0.16, 8).scale(1, 1, 0.68).translate(0, 0.92, 0)]);
  const shoes = merge(skirt ? [...limbs, shoe(1), shoe(-1)] : [shoe(1), shoe(-1)]);
  // torso: hips to shoulders, flattened front to back
  const prof = [[0.0, 0.86], [0.155, 0.88], [0.15, 0.98], [0.135, 1.08], [0.155, 1.2], [0.172, 1.32], [0.175, 1.39], [0.14, 1.45], [0.06, 1.49], [0.0, 1.49]];
  const torso = new THREE.LatheGeometry(prof.map(([r, y]) => new THREE.Vector2(r, y)), 10).scale(1, 1, 0.64);
  // arms: shoulder, elbow, wrist; swinging against the legs
  const arm = (side) => {
    const swing = -side * stride * 0.7, sh = [side * 0.2, 1.4, 0];
    const el = [side * 0.235, sh[1] - 0.29 * Math.cos(swing), 0.29 * Math.sin(swing)];
    const wr = [side * 0.24, el[1] - 0.26 * Math.cos(swing * 1.4 + 0.12), el[2] + 0.26 * Math.sin(swing * 1.4 + 0.12)];
    return { parts: [limb(sh, el, 0.05, 0.042), limb(el, wr, 0.04, 0.032), new THREE.SphereGeometry(0.047, 6, 4).translate(sh[0] * 0.95, sh[1] - 0.01, sh[2])], wrist: wr };
  };
  const L = arm(1), R = arm(-1);
  const body = merge([torso, ...L.parts, ...R.parts]);
  // skin: head, neck, hands
  const head = merge([
    new THREE.SphereGeometry(0.1, 10, 7).scale(0.88, 1.12, 0.98).translate(0, 1.62, 0.01),
    new THREE.SphereGeometry(0.06, 7, 4).scale(1, 0.8, 1).translate(0, 1.54, 0.04), // jaw
    new THREE.CylinderGeometry(0.042, 0.05, 0.1, 6).translate(0, 1.5, 0),
    new THREE.SphereGeometry(0.038, 5, 4).scale(0.8, 1.3, 0.6).translate(L.wrist[0], L.wrist[1] - 0.05, L.wrist[2]),
    new THREE.SphereGeometry(0.038, 5, 4).scale(0.8, 1.3, 0.6).translate(R.wrist[0], R.wrist[1] - 0.05, R.wrist[2]),
  ]);
  const hairParts = [new THREE.SphereGeometry(0.106, 10, 5, 0, Math.PI * 2, 0, Math.PI * 0.56).scale(0.92, 1.08, 1.02).translate(0, 1.63, -0.005)];
  if (skirt) hairParts.push(new THREE.CylinderGeometry(0.1, 0.12, 0.26, 6, 1, true, Math.PI * 0.6, Math.PI * 0.8).scale(0.95, 1, 0.9).translate(0, 1.5, -0.01));
  const hair = merge(hairParts);
  return { legs, shoes, body, head, hair };
}

export function addPeople(scene, list, toScene) {
  const rnd = rng(5);
  const n = list.length;
  // [standing, walking] x [trousers, skirt]
  const kinds = [[0.02, false], [0.3, false], [0.02, true], [0.24, true]];
  const mk = (geo, rough, side = THREE.FrontSide) => new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: rough, side }), n);
  const sets = kinds.map(([stride, skirt]) => {
    const p = personParts(stride, skirt);
    return { legs: mk(p.legs, 0.9, THREE.DoubleSide), shoes: mk(p.shoes, 0.55), body: mk(p.body, 0.85), head: mk(p.head, 0.6), hair: mk(p.hair, 0.75, THREE.DoubleSide) };
  });
  const counts = kinds.map(() => 0);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), pp = new THREE.Vector3(), sc = new THREE.Vector3(), c = new THREE.Color();
  const pick = (arr) => arr[Math.floor(rnd() * arr.length)];
  list.forEach(([x, y, z]) => {
    const w = toScene(x, y);
    const skirt = rnd() < 0.3, walking = rnd() < 0.45;
    const k = (skirt ? 2 : 0) + (walking ? 1 : 0);
    const set = sets[k], i = counts[k]++;
    const h = skirt ? 0.92 + rnd() * 0.08 : 0.95 + rnd() * 0.12; // 1.55 .. 1.85 m
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), rnd() * Math.PI * 2);
    m4.compose(pp.set(w.x, z, w.z), q, sc.set(h, h, h));
    for (const m of Object.values(set)) m.setMatrixAt(i, m4);
    set.legs.setColorAt(i, c.setHex(pick(skirt ? SKIRTS : TROUSERS)));
    set.shoes.setColorAt(i, c.setHex(pick(skirt ? TIGHTS : SHOES)));
    set.body.setColorAt(i, c.setHex(pick(CLOTHES)));
    const skin = pick(SKIN);
    set.head.setColorAt(i, c.setHex(skin));
    set.hair.setColorAt(i, c.setHex(pick(HAIR)));
  });
  sets.forEach((set, k) => {
    for (const m of Object.values(set)) {
      m.count = counts[k];
      m.castShadow = true;
      m.receiveShadow = true;
      m.frustumCulled = false;
      scene.add(m);
    }
  });
}

// ---------- realistic people (high quality) ----------
// Ten people modelled with MakeHuman (MPFB 2, CC0 assets: bodies, skins, clothes, hair), posed walking,
// standing, talking, looking at a phone (blender/people/build_people.py -> public/models/people.glb).
// Each of them drawn as instances at the plan's places, turned at random, the clothes tinted a little
// differently from person to person (white shirts, light blues, beige, greys) so no two look the same.
const PEOPLE_URL = `${import.meta.env.BASE_URL}models/people.glb`;
const CLOTH_TINTS = [0xffffff, 0xffffff, 0xf2ece4, 0xdde6f2, 0xe8e0d6, 0xd4d4d4, 0xf6e6dc, 0xcfdccf, 0xb8bcc4, 0xe6dfef];
export function addRealPeople(scene, list, toScene) {
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  return loader.loadAsync(PEOPLE_URL).then((gltf) => {
    const rnd = rng(9);
    gltf.scene.updateMatrixWorld(true);
    const variants = gltf.scene.children.filter((o) => o.children.length).map((root) => {
      const parts = [];
      root.traverse((o) => {
        if (!o.isMesh) return;
        // (dequantized first: the quantized positions cannot hold the node transform put into them)
        const g = dequantize(o.geometry).applyMatrix4(new THREE.Matrix4().multiplyMatrices(new THREE.Matrix4().copy(root.matrixWorld).invert(), o.matrixWorld));
        const m = o.material;
        if (m.transparent || m.alphaMap || m.map?.format === THREE.RGBAFormat) {
          // the hair's strands, the lashes: cut out, not sorted (instances cannot be)
          m.transparent = false;
          m.alphaTest = 0.45;
          m.alphaToCoverage = true;
          m.side = THREE.DoubleSide;
          m.depthWrite = true;
        }
        m.roughness = Math.max(m.roughness ?? 0.8, 0.55);
        const cloth = /suit|shirt|cloth/i.test(o.name) || /suit/i.test(m.name);
        parts.push({ g, m, cloth });
      });
      return { name: root.name, walking: /walk/.test(root.name), female: /^f_/.test(root.name), parts };
    });
    if (!variants.length) throw new Error('no people in the model');
    // who stands where: walkers on the paths, standing people in the shops and by the benches
    const byVariant = variants.map(() => []);
    list.forEach(([x, y, z], i) => {
      const walking = z < 1.0 ? rnd() < 0.55 : rnd() < 0.2;   // (z over a metre: inside the shops)
      const pool = variants.map((v, k) => k).filter((k) => variants[k].walking === walking);
      const k = pool[Math.floor(rnd() * pool.length)];
      byVariant[k].push({ x, y, z, rot: rnd() * Math.PI * 2, s: 0.96 + rnd() * 0.08, tint: CLOTH_TINTS[Math.floor(rnd() * CLOTH_TINTS.length)] });
    });
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), sc = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0), c = new THREE.Color();
    variants.forEach((v, k) => {
      const people = byVariant[k];
      if (!people.length) return;
      for (const part of v.parts) {
        const im = new THREE.InstancedMesh(part.g, part.m, people.length);
        people.forEach((pe, i) => {
          const w = toScene(pe.x, pe.y);
          im.setMatrixAt(i, m4.compose(p.set(w.x, pe.z, w.z), q.setFromAxisAngle(up, pe.rot), sc.set(pe.s, pe.s, pe.s)));
          if (part.cloth) im.setColorAt(i, c.setHex(pe.tint));
        });
        im.castShadow = true;
        im.receiveShadow = true;
        im.frustumCulled = false;
        im.name = `people ${v.name}`;
        scene.add(im);
      }
    });
    return variants.length;
  });
}
