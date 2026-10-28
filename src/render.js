// Renderer and frame pipeline.
//   high: scene -> (4x MSAA, half-float) -> ambient occlusion (N8AO) -> tone mapping -> screen (src/post.js,
//         loaded on demand; until it is in, frames go straight to the screen)
//   low:  scene -> tone mapping -> screen, directly (no extra passes: phones, older laptops)
// Exposure and tone mapping are the same in both, so the two levels differ in detail, not in look.
import * as THREE from 'three';
import { Q } from './quality.js';

const params = new URLSearchParams(location.search);
export const EXPOSURE = +(params.get('exposure') ?? 1.12);
// tone mapping: Khronos PBR Neutral keeps the colours of the materials as they are (no extra
// saturation or contrast) and rolls off only the highlights; ?tonemap=agx|aces to compare
const TONE = ['neutral', 'agx', 'aces'].includes(params.get('tonemap')) ? params.get('tonemap') : 'neutral';
const THREE_TONE = { neutral: THREE.NeutralToneMapping, agx: THREE.AgXToneMapping, aces: THREE.ACESFilmicToneMapping };

export function createRenderer() {
  const probe = document.createElement('canvas');
  if (!window.WebGL2RenderingContext || !probe.getContext('webgl2')) throw new Error('WebGL 2 is not available');
  const renderer = new THREE.WebGLRenderer({
    antialias: Q.level !== 'high', // high renders into a multisampled target instead
    powerPreference: 'high-performance',
    stencil: false,
  });
  renderer.setPixelRatio(Q.pixelRatio);
  renderer.setSize(innerWidth, innerHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE_TONE[TONE];
  renderer.toneMappingExposure = EXPOSURE;
  return renderer;
}

export function createPipeline(renderer, scene, camera) {
  const pipeline = {
    render: () => renderer.render(scene, camera),
    setSize: (w, h) => renderer.setSize(w, h),
    walk: () => {},
    bloom: () => {},
    ao: null,
    ready: Promise.resolve(),
  };
  if (Q.ao) {
    pipeline.ready = import('./post.js')
      .then(({ postPipeline }) => {
        Object.assign(pipeline, postPipeline(renderer, scene, camera, TONE));
        renderer.toneMapping = THREE.NoToneMapping; // done by the last pass now
      })
      .catch((e) => console.warn('post-processing unavailable, rendering directly', e));
  }
  return pipeline;
}
