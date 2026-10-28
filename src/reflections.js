// Glass that reflects what is round it (high quality only): the scene seen from two points, as cube
// maps for the glass's reflections, instead of the sky alone. The glass tower's from its own middle
// (the tower hidden while it is taken: the neighbours, the streets, the trees and the city in its
// panes); the slab blocks' from the courtyard's middle at the eighth floor (the other blocks, the
// courtyard, the sky). Taken once, in daylight, when the model, the trees and the cars are in; the
// night scales the reflections down (src/night.js).
import * as THREE from 'three';

function probe(renderer, scene, at, size) {
  const rt = new THREE.WebGLCubeRenderTarget(size, { type: THREE.HalfFloatType, generateMipmaps: false });
  const cam = new THREE.CubeCamera(0.5, 6000, rt);
  cam.position.copy(at);
  scene.add(cam);
  const tone = renderer.toneMapping;
  renderer.toneMapping = THREE.NoToneMapping; // linear light: the glass shader tone maps with the rest
  cam.update(renderer, scene);
  renderer.toneMapping = tone;
  scene.remove(cam);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const env = pmrem.fromCubemap(rt.texture).texture;
  pmrem.dispose();
  rt.dispose();
  return env;
}

/**
 * @param building  the loaded model (building.js): towers, showUpTo, showAll
 * @param towers    complex.json towers (centre, top)
 */
export function captureReflections({ renderer, scene, building, towers, toScene, size = 512 }) {
  const glass = [];
  scene.traverse((o) => {
    for (const m of [o.material].flat()) if (m?.userData?.glass && !glass.includes(m)) glass.push(m);
  });
  const a = towers.find((t) => t.key === 'A');
  const slabs = towers.filter((t) => t.key !== 'A');
  // the courtyard's middle: the slab blocks' centres averaged
  const cx = slabs.reduce((s, t) => s + t.centre[0], 0) / slabs.length;
  const cy = slabs.reduce((s, t) => s + t.centre[1], 0) / slabs.length;
  const c = toScene(cx, cy);
  const envCourt = probe(renderer, scene, new THREE.Vector3(c.x, 30, c.z), size);
  let envTower = envCourt;
  if (a) {
    building.showUpTo('A', 0);
    const p = toScene(a.centre[0], a.centre[1]);
    envTower = probe(renderer, scene, new THREE.Vector3(p.x, Math.min(48, a.top * 0.5), p.z), size);
    building.showAll();
  }
  for (const m of glass) {
    m.envMap = m.name === 'Tower glass' ? envTower : envCourt;
    m.needsUpdate = true;
  }
  return { envCourt, envTower, count: glass.length };
}
