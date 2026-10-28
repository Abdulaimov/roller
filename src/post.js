// The high level's frame passes, loaded only on that level (a separate chunk: phones never download it).
//   scene -> 4x MSAA, half-float -> ambient occlusion (N8AO, full resolution) -> bloom (a touch by day,
//   more at dusk and night) -> tone mapping -> grade (contrast, saturation, a soft vignette) -> screen
import * as THREE from 'three';
import { BloomEffect, BrightnessContrastEffect, EffectComposer, EffectPass, HueSaturationEffect, RenderPass, ToneMappingEffect, ToneMappingMode, VignetteEffect } from 'postprocessing';
import { N8AOPostPass } from 'n8ao';

const MODES = { agx: ToneMappingMode.AGX, neutral: ToneMappingMode.NEUTRAL, aces: ToneMappingMode.ACES_FILMIC };

export function postPipeline(renderer, scene, camera, tone) {
  const composer = new EffectComposer(renderer, { multisampling: 4, frameBufferType: THREE.HalfFloatType });
  composer.addPass(new RenderPass(scene, camera));
  const ao = new N8AOPostPass(scene, camera, innerWidth, innerHeight);
  Object.assign(ao.configuration, {
    aoRadius: 2.2, // metres: under balconies, at the foot of walls, where planters meet paving
    distanceFalloff: 0.6,
    intensity: 2.2,
    aoSamples: 24,
    denoiseSamples: 12,
    denoiseRadius: 10,
    halfRes: false,
    depthAwareUpsampling: true,
    gammaCorrection: false,
    color: new THREE.Color(0x0b0d10),
  });
  composer.addPass(ao);
  // the glow round the lamps, the lit windows and the signs at night (off by day: no cost)
  // by day a touch on the sun's glints in the glass and the white stone (as a lens does)
  const DAY_BLOOM = 0.14;
  const bloom = new BloomEffect({ intensity: DAY_BLOOM, luminanceThreshold: 0.88, luminanceSmoothing: 0.3, mipmapBlur: true, radius: 0.72, levels: 7 });
  const bloomPass = new EffectPass(camera, bloom);
  composer.addPass(bloomPass);
  // the grade of the client's renders: a little more contrast and colour, the corners a shade darker
  composer.addPass(new EffectPass(camera,
    new ToneMappingEffect({ mode: MODES[tone] }),
    new BrightnessContrastEffect({ brightness: 0.0, contrast: 0.06 }),
    new HueSaturationEffect({ saturation: 0.14 }),
    new VignetteEffect({ offset: 0.38, darkness: 0.32 })));
  composer.setSize(innerWidth, innerHeight);
  return {
    render: (dt) => composer.render(dt),
    setSize: (w, h) => {
      renderer.setSize(w, h);
      composer.setSize(w, h);
    },
    // inside a flat: smaller radius, rooms are a few metres across
    walk: (on) => {
      ao.configuration.aoRadius = on ? 0.6 : 2.2;
      ao.configuration.distanceFalloff = on ? 0.35 : 0.6;
      ao.configuration.intensity = on ? 2.4 : 2.2;
    },
    ao,
    bloom: (k) => {
      bloom.intensity = DAY_BLOOM + k;
    },
  };
}
