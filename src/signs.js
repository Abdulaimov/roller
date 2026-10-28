// Shop signs over the shop windows: a layer laid over the model, so the tenants' names and logos
// change without rebuilding the scene. public/signs/signs.json says which artwork goes where
// (?signs=neutral picks another set). A place is given one of two ways:
//   - block, face, bay, span: over the portals of a street face as exported by the build
//     (model/complex.json shops: the street faces' portals with the dark frieze over them, model/build
//     blender/ab/podium.py); the sign is centred over the frieze
//   - a, b, n, z: the span's two ends on the facade plane, the way the face looks and the middle height,
//     site metres (tools/ab/place_signs.py writes these for every shop, street and yard faces alike)
// kind (default 'sign'):
//   sign    the artwork's letters standing `off` (7 cm) off the dark frieze, white metal (or the
//           brand's colour) by day, lit at night (src/night.js reads userData.nightGlow)
//   poster  a lit poster hung inside the shop behind the second-floor glass (off < 0)
//   band    dark / brand-coloured letters on block A's white podium band; the coloured ones glow at night
// Every sign is as tall as asked and no wider than its span (less `margin`), never stretched.
import * as THREE from 'three';
import { Q } from './quality.js';

const BASE = `${import.meta.env.BASE_URL}signs/`;
// [day, night] emissive intensity per kind
const GLOW = { sign: [0.35, 2.4], poster: [0.55, 1.5], band: [0, 0.9] };

export async function addSigns(scene, shops, toScene, setName = null) {
  const conf = await fetch(`${BASE}signs.json`).then((r) => r.json());
  let list = conf.sets[setName ?? conf.set] ?? conf.sets[conf.set];
  // phones: the signs only (the posters are 39 more pictures in memory)
  if (Q.level === 'low') list = list.filter((s) => s.kind !== 'poster');
  const loader = new THREE.TextureLoader();
  const group = new THREE.Group();
  group.name = 'signs';
  const textures = new Map();
  const texture = (file) => {
    if (!textures.has(file)) {
      textures.set(file, loader.loadAsync(BASE + file).then((t) => {
        t.colorSpace = THREE.SRGBColorSpace;
        t.anisotropy = 8;
        return t;
      }));
    }
    return textures.get(file);
  };
  await Promise.all(list.map(async (s) => {
    const place = s.a ? s : fromBays(s, shops);
    if (!place) {
      console.warn('sign: no such shop', s);
      return;
    }
    let tex;
    try {
      tex = await texture(s.file);
    } catch {
      console.warn('sign: no picture', s.file);
      return;
    }
    const kind = s.kind ?? 'sign';
    const [ax, ay] = place.a, [bx, by] = place.b, [nx, ny] = place.n;
    const span = Math.hypot(bx - ax, by - ay) - (s.margin ?? 0.3);
    let h = s.h ?? s.height, w = (h * tex.image.width) / tex.image.height;
    if (w > span) (h *= span / w), (w = span);
    const mat = new THREE.MeshStandardMaterial({
      map: tex, emissive: 0xffffff, emissiveMap: tex, roughness: kind === 'poster' ? 0.6 : 0.45,
      metalness: kind === 'sign' ? 0.2 : 0, alphaTest: kind === 'poster' ? 0 : 0.5,
    });
    mat.userData.nightGlow = s.glow ?? GLOW[kind];
    mat.emissiveIntensity = mat.userData.nightGlow[0];
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
    const off = s.off ?? 0.07;
    const p = toScene((ax + bx) / 2 + nx * off, (ay + by) / 2 + ny * off);
    mesh.position.set(p.x, place.z, p.z);
    mesh.rotation.y = Math.atan2(nx, -ny); // the plane's face (+z) to the street (site n -> scene (nx, -ny))
    mesh.name = `${kind} ${s.file}`;
    group.add(mesh);
  }));
  scene.add(group);
  return group;
}

// the older way: block, face, bay and span over the street faces' portals in the build's shop list
function fromBays(s, shops) {
  const bays = shops.filter((b) => b[0] === s.block && b[1] === s.face).sort((a, b) => a[2] - b[2]);
  const first = bays[s.bay], last = bays[s.bay + (s.span ?? 1) - 1];
  if (!first || !last) return null;
  return { a: [first[3], first[4]], b: [last[5], last[6]], n: [first[9], first[10]], z: (first[7] + first[8]) / 2 };
}
