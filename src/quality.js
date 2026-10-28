// Graphics level: 'high' on computers, 'low' on phones and small tablets (or ?quality=low|high,
// or the switch in the corner, remembered per browser).
//   high  1k textures, 4096 shadow map, ambient occlusion pass, the ground's baked occlusion, glass
//         reflecting its surroundings, bloom and a grade, pixel ratio up to 1.5
//   low   512 px textures, 2048 shadow map, no post-processing, pixel ratio up to 1.25
// The pixel ratio then follows the frame rate (src/main.js): a Retina screen at full size was
// rendered at four times the pixels and stuttered.
const KEY = 'regnum.quality';

function detect() {
  const q = new URLSearchParams(location.search).get('quality');
  if (q === 'low' || q === 'high') return q;
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === 'low' || saved === 'high') return saved;
  } catch {
    // storage blocked: fall through to the device guess
  }
  const coarse = matchMedia('(pointer: coarse)').matches && !matchMedia('(pointer: fine)').matches;
  const small = Math.max(screen.width, screen.height) < 1100;
  const lowMemory = navigator.deviceMemory !== undefined && navigator.deviceMemory < 4;
  return (coarse && small) || lowMemory ? 'low' : 'high';
}

export const QUALITY = detect();
const high = QUALITY === 'high';

export const Q = {
  level: QUALITY,
  textureSize: high ? '1k' : '512',
  // (the start; src/main.js lowers it while the frame rate stays under 42 and raises it back)
  pixelRatio: Math.min(devicePixelRatio || 1, high ? 1.5 : 1.25),
  shadowMap: high ? 4096 : 2048,
  ao: high,
  antialias: true,
};

export function setQuality(level) {
  try {
    localStorage.setItem(KEY, level);
  } catch {
    // not remembered; the reload below still uses the URL
  }
  const u = new URL(location.href);
  u.searchParams.set('quality', level);
  location.replace(u);
}
