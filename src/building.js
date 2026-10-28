// The building (block V) and its surroundings, loaded from the Blender export.
// Floors are separate objects so they can be hidden for the cut-away view,
// and every apartment has an invisible pick volume used for hovering and highlighting.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { MODEL_URL, toScene } from './config.js';
import { flagstone, materialFor, setupMaterial } from './materials.js';

// The published artifact page can't serve .glb files, so it gets the same bytes base64-encoded
// in a JSON file ({ "glb": "..." }); everywhere else the .glb is loaded directly.
async function loadModel(loader, url, onProgress) {
  if (!url.endsWith('.json')) return loader.loadAsync(url, (e) => e.total && onProgress?.(e.loaded / e.total));
  const { glb } = await (await fetch(url)).json();
  const bytes = Uint8Array.from(atob(glb), (c) => c.charCodeAt(0));
  return loader.parseAsync(bytes.buffer, '');
}

// outlines of the apartments (lines a few pixels wide): a floor under the pointer, the flats of the
// open floor, and the flat under the pointer / chosen, drawn bright over everything
const line = (color, linewidth, opacity, depthTest = true) =>
  new LineMaterial({ color, linewidth, transparent: true, opacity, depthTest, depthWrite: false });
export const OUTLINE = {
  floor: line(0xffffff, 3, 1),
  open: line(0xf2c98f, 1.6, 0.9),
  hover: line(0xffa42b, 4.5, 1, false),
  chosen: line(0xff8a00, 4.5, 1, false),
};

export async function loadComplex(apartments, renderer, onProgress) {
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  const gltf = await loadModel(loader, MODEL_URL, onProgress);
  const root = gltf.scene;
  const o = toScene(0, 0);
  root.position.set(o.x, 0, o.z);

  const towers = {}; // key -> { floors: { n: { slab, walls } }, roof }
  const tower = (k) => (towers[k] ??= { floors: {}, roof: null });
  const picks = [];
  const tuned = new Set();
  const textures = []; // material texture loads (the model shows before they are all in)

  root.traverse((obj) => {
    const d = obj.userData;
    if (d.pick) {
      picks.push(obj);
      return;
    }
    if (obj.isMesh) {
      obj.castShadow = true;
      obj.receiveShadow = true;
      obj.material = Array.isArray(obj.material) ? obj.material.map(materialFor) : flagstone(obj, obj.material) ?? materialFor(obj.material);
      for (const m of [obj.material].flat()) {
        if (!tuned.has(m)) {
          textures.push(setupMaterial(m, renderer));
          tuned.add(m);
        }
        if (m.transparent) obj.castShadow = false;
      }
    }
    if (d.tower && d.part === 'roof') tower(d.tower).roof = obj;
    else if (d.tower && d.floor) {
      const f = (tower(d.tower).floors[d.floor] ??= {});
      f[d.part === 'walls' ? 'walls' : 'slab'] = obj;
    }
  });

  // pick volumes -> highlight overlays
  const units = new Map();
  const box = new THREE.Box3();
  root.updateMatrixWorld(true);
  for (const mesh of picks) {
    mesh.material = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false });
    mesh.renderOrder = 10;
    mesh.visible = false;
    mesh.castShadow = mesh.receiveShadow = false;
    const d = mesh.userData;
    const id = `${d.tower}${d.floor}-${d.unit}`;
    const apt = apartments.find((a) => a.id === id);
    if (!apt) continue;
    mesh.userData.apt = apt;
    const eg = new THREE.EdgesGeometry(mesh.geometry, 35);
    const edges = new LineSegments2(new LineSegmentsGeometry().fromEdgesGeometry(eg), OUTLINE.floor);
    edges.renderOrder = 11;
    edges.visible = false;
    mesh.add(edges);
    // the flat's outline on its floor (for the plan of the open floor): the bottom edges, raised a little
    const pos = eg.attributes.position.array;
    let y0 = Infinity;
    for (let i = 1; i < pos.length; i += 3) y0 = Math.min(y0, pos[i]);
    const flat = [];
    for (let i = 0; i < pos.length; i += 6) {
      if (pos[i + 1] < y0 + 0.01 && pos[i + 4] < y0 + 0.01) flat.push(pos[i], y0 + 0.08, pos[i + 2], pos[i + 3], y0 + 0.08, pos[i + 5]);
    }
    const ring = new LineSegments2(new LineSegmentsGeometry().setPositions(flat), OUTLINE.open);
    ring.renderOrder = 11;
    ring.visible = false;
    mesh.add(ring);
    box.setFromObject(mesh);
    const c = box.getCenter(new THREE.Vector3());
    units.set(apt.id, { overlay: mesh, edges, ring, center: new THREE.Vector3(c.x, apt.baseY, c.z), top: box.max.y });
  }

  // Floors that share a mesh (the typical floors: same plan, same height) are drawn as one instanced
  // mesh per material instead of one mesh per floor and material: about a third of the draw calls,
  // shadows included, with the geometry still stored once. A hidden floor is a zero-scaled instance.
  const ZERO = new THREE.Matrix4().makeScale(0, 0, 0);
  const shared = new Map(); // geometry+material -> [{ mesh, holder, part }]
  for (const t of Object.values(towers)) {
    for (const f of Object.values(t.floors)) {
      for (const part of ['slab', 'walls']) {
        f[part]?.traverse((m) => {
          if (!m.isMesh) return;
          const key = `${m.geometry.uuid}/${m.material.uuid}`;
          if (!shared.has(key)) shared.set(key, []);
          shared.get(key).push({ mesh: m, holder: f, part });
        });
      }
    }
  }
  const rootInv = new THREE.Matrix4().copy(root.matrixWorld).invert();
  for (const list of shared.values()) {
    if (list.length < 2) continue;
    const { mesh } = list[0];
    const im = new THREE.InstancedMesh(mesh.geometry, mesh.material, list.length);
    im.castShadow = mesh.castShadow;
    im.receiveShadow = mesh.receiveShadow;
    im.name = `floors ${mesh.name}`;
    list.forEach(({ mesh: m, holder, part }, i) => {
      const matrix = new THREE.Matrix4().multiplyMatrices(rootInv, m.matrixWorld);
      im.setMatrixAt(i, matrix);
      ((holder.instances ??= { slab: [], walls: [] })[part]).push({ im, i, matrix });
      m.removeFromParent();
    });
    im.computeBoundingSphere();
    root.add(im);
  }
  const each = (fn) => {
    for (const [k, t] of Object.entries(towers)) {
      for (const [n, f] of Object.entries(t.floors)) fn(k, +n, f, t);
    }
  };
  const touched = new Set();
  const setVisible = (o, v) => o && (o.visible = v);
  const setPart = (f, part, v) => {
    setVisible(f[part], v); // whatever of the floor stayed a plain mesh
    for (const { im, i, matrix } of f.instances?.[part] ?? []) {
      im.setMatrixAt(i, v ? matrix : ZERO);
      touched.add(im);
    }
  };
  const flush = () => {
    for (const im of touched) im.instanceMatrix.needsUpdate = true;
    touched.clear();
  };

  return {
    texturesReady: Promise.all(textures),
    group: root,
    towers,
    units,
    pickables: [...units.values()].map((u) => u.overlay),
    // Cut-away: hide everything above `floor` in `towerKey` and open up that floor.
    showUpTo(towerKey, floor) {
      each((k, n, f, t) => {
        const above = k === towerKey && n > floor;
        setPart(f, 'slab', !above);
        setPart(f, 'walls', !above && !(k === towerKey && n === floor));
        setVisible(t.roof, k !== towerKey);
      });
      flush();
    },
    // Everything visible, except the walls of an apartment floor someone is walking around in.
    showAll(openTower = null, openFloor = null) {
      each((k, n, f, t) => {
        setPart(f, 'slab', true);
        setPart(f, 'walls', !(k === openTower && n === openFloor));
        setVisible(t.roof, true);
      });
      flush();
    },
  };
}
