// PBR look of the complex, by the material names the Blender build exports (blender/complex/materials.py).
// The model carries geometry, UVs (metres) and plain base values; here every material gets its
// texture set (public/textures, CC0, see ASSETS.md), real-world tile size, roughness and
// reflections. Nothing is swapped for a simpler material: the loaded MeshStandardMaterial is
// configured in place, and names missing from the table keep what the model says.
import * as THREE from 'three';
import { Q } from './quality.js';
import { alphaTexture, brickTextures, groundTexture } from './textures.js';

const BASE = `${import.meta.env.BASE_URL}textures/`;
// lights on at dusk and at night, 0..1 (src/night.js): the windows of the complex and of the city
export const NIGHT = { value: 0 };

// The light of the street lamps, the pitch's floodlights and the shop windows at night: a map of it
// seen from above (src/night.js draws it from the lamps' places), added on every lit surface by its
// colour, fading with height (the ground, the paths, benches, trees, people, cars and the lower
// floors are lit; the flats above are not). Every standard material gets it (the prototype's hook
// below; the materials with a hook of their own call lampChunk too). k = 0 by day.
export const LAMP = {
  map: { value: new THREE.DataTexture(new Uint8Array(4), 1, 1) },
  box: { value: new THREE.Vector4(0, 0, 1, 1) }, // scene x0, z0, 1 / width, 1 / depth (m)
  k: { value: 0 },
};
LAMP.map.value.needsUpdate = true;
// The ground's sky occlusion, baked in Blender with Cycles (blender/bake_ground_ao.py): how much sky
// each point of the ground sees with the buildings, trees, hedges and cars round it. The sky's light on
// the ground (paths, lawns, the road) is darkened by it: the soft contact shade at the foot of the
// walls, under the trees and the cars, in the passages. High quality only (k = 0 until it is loaded).
export const GROUND_AO = {
  map: { value: LAMP.map.value },
  box: { value: new THREE.Vector4(0, 0, 1, 1) }, // scene x0, z0, 1 / width, 1 / depth (m)
  k: { value: 0 },
};
export function lampChunk(sh) {
  if (sh.vertexShader.includes('vLampW')) return;
  sh.uniforms.uLampMap = LAMP.map;
  sh.uniforms.uLampBox = LAMP.box;
  sh.uniforms.uLampK = LAMP.k;
  sh.uniforms.uGroundAO = GROUND_AO.map;
  sh.uniforms.uGroundBox = GROUND_AO.box;
  sh.uniforms.uGroundK = GROUND_AO.k;
  sh.vertexShader = sh.vertexShader
    .replace('#include <common>', '#include <common>\nvarying vec3 vLampW;')
    .replace('#include <project_vertex>', `#include <project_vertex>
      {
        vec4 lw = vec4(transformed, 1.0);
        #ifdef USE_INSTANCING
          lw = instanceMatrix * lw;
        #endif
        vLampW = (modelMatrix * lw).xyz;
      }`);
  sh.fragmentShader = sh.fragmentShader
    .replace('#include <common>', '#include <common>\nvarying vec3 vLampW;\nuniform sampler2D uLampMap;\nuniform vec4 uLampBox;\nuniform float uLampK;\nuniform sampler2D uGroundAO;\nuniform vec4 uGroundBox;\nuniform float uGroundK;')
    .replace('#include <aomap_fragment>', `#include <aomap_fragment>
      if (uGroundK > 0.0 && vLampW.y < 0.36) {
        vec2 guv = (vLampW.xz - uGroundBox.xy) * uGroundBox.zw;
        vec3 gn = inverseTransformDirection(normal, viewMatrix);
        if (gn.y > 0.5 && guv.x > 0.0 && guv.y > 0.0 && guv.x < 1.0 && guv.y < 1.0) {
          float g = mix(1.0, pow(texture2D(uGroundAO, guv).r, 0.75), uGroundK);
          reflectedLight.indirectDiffuse *= g;
          reflectedLight.indirectSpecular *= mix(1.0, g, 0.7);
        }
      }`)
    .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
      if (uLampK > 0.0) {
        vec2 luv = (vLampW.xz - uLampBox.xy) * uLampBox.zw;
        if (luv.x > 0.0 && luv.y > 0.0 && luv.x < 1.0 && luv.y < 1.0) {
          float fall = 1.0 - smoothstep(0.3, 10.0, vLampW.y);
          totalEmissiveRadiance += diffuseColor.rgb * texture2D(uLampMap, luv).rgb * uLampK * fall;
        }
      }`);
}
THREE.MeshStandardMaterial.prototype.onBeforeCompile = lampChunk;
const loader = new THREE.TextureLoader();
const sources = new Map(); // `${set}/${kind}` -> Promise<Texture> (one download / GPU upload per file)
let anisotropy = 8;

function loadMap(set, kind) {
  const key = `${set}/${kind}`;
  if (!sources.has(key)) {
    sources.set(
      key,
      loader.loadAsync(`${BASE}${set}/${kind}_${Q.textureSize}.webp`).then((t) => {
        t.wrapS = t.wrapT = THREE.RepeatWrapping;
        t.anisotropy = anisotropy;
        t.colorSpace = kind === 'color' ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        return t;
      }),
    );
  }
  return sources.get(key);
}

// A texture of the set for one tile size (clones share the image and its GPU upload).
async function map(set, kind, tile) {
  const t = (await loadMap(set, kind)).clone();
  t.repeat.set(1 / tile, 1 / tile);
  t.needsUpdate = true;
  return t;
}

// ---------- shader additions ----------
// vary:   large-scale light/dark and hue drift in world space, so big surfaces are not uniform
// detile: a second, rotated and scaled read of the colour map blended in by a noise mask (no
//         visible repeat on lawns and paving)
// leafy:  a bumpy normal and patchy colour for the shrub and hedge volumes
const NOISE = /* glsl */ `
  float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
  float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), u.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), u.x), u.y);
  }
  float fbm(vec2 p) { return 0.55 * vnoise(p) + 0.3 * vnoise(p * 2.13 + 7.1) + 0.15 * vnoise(p * 4.37 + 3.7); }
  float hash13(vec3 p) { p = fract(p * .1031); p += dot(p, p.zyx + 31.32); return fract((p.x + p.y) * p.z); }
  float vnoise3(vec3 p) {
    vec3 i = floor(p), f = fract(p); vec3 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(hash13(i), hash13(i + vec3(1, 0, 0)), u.x), mix(hash13(i + vec3(0, 1, 0)), hash13(i + vec3(1, 1, 0)), u.x), u.y),
               mix(mix(hash13(i + vec3(0, 0, 1)), hash13(i + vec3(1, 0, 1)), u.x), mix(hash13(i + vec3(0, 1, 1)), hash13(i + vec3(1, 1, 1)), u.x), u.y), u.z);
  }
`;

// facade: storeys and window bays drawn on plain massing boxes (the neighbours), in world space:
//         glass (some windows lit or curtained), frames, floor bands; roofs a darker membrane
const FACADE = /* glsl */ `
  float facadeGlass = 0.0;
  vec3 facadeLight = vec3(0.0);
  {
    vec3 fn = normalize(vWorldNormal);
    if (abs(fn.y) < 0.5) {
      vec2 ft = normalize(vec2(-fn.z, fn.x));
      float fu = dot(vWorldPos.xz, ft), fv = vWorldPos.y;
      float storey = floor(fv / uFacade.x), bay = floor(fu / uFacade.y);
      vec2 f = vec2(fract(fu / uFacade.y), fract(fv / uFacade.x));
      float upper = step(1.0, storey) * step(fv, uFacade.z - 0.9);
      // ground floor: wide shop windows; upper floors: punched windows
      vec2 lo = mix(vec2(0.08, 0.12), vec2(0.2, 0.3), upper), hi = mix(vec2(0.92, 0.85), vec2(0.8, 0.86), upper);
      float win = step(lo.x, f.x) * step(f.x, hi.x) * step(lo.y, f.y) * step(f.y, hi.y) * step(fv, uFacade.z - 0.9);
      float inner = step(lo.x + 0.03, f.x) * step(f.x, hi.x - 0.03) * step(lo.y + 0.03, f.y) * step(f.y, hi.y - 0.03);
      float h = hash12(vec2(bay, storey) + floor(vWorldPos.xz / 60.0) * 17.0);
      vec3 room = mix(vec3(0.05, 0.065, 0.08), vec3(0.2, 0.21, 0.22), h);
      room = mix(room, vec3(0.62, 0.56, 0.46), step(0.88, h) * 0.7);   // curtains, a lit room
      room = mix(room, vec3(0.78, 0.78, 0.76), step(0.8, h) * step(h, 0.88) * step(0.6, f.y) * 0.6); // blinds half down
      diffuseColor.rgb = mix(diffuseColor.rgb, room, win * inner * 0.7);
      // at night about a third of the windows are lit, warm, a few cooler (a television, LEDs)
      float on = step(1.0 - 0.36 * uNight, hash12(vec2(bay, storey) * 1.31 + floor(vWorldPos.xz / 60.0) * 5.0 + 3.7));
      facadeLight = win * inner * on * uNight * mix(vec3(1.0, 0.72, 0.42), vec3(0.75, 0.8, 0.9), step(0.85, h)) * 0.9;
      diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * 1.08, win * (1.0 - inner));
      facadeGlass = win * inner;
      // a band at each floor slab, a darker plinth
      diffuseColor.rgb *= 1.0 - 0.1 * step(f.y, 0.05) * upper;
      diffuseColor.rgb *= 1.0 - 0.25 * step(fv, 0.5);
    } else if (fn.y > 0.5) {
      diffuseColor.rgb *= vec3(0.55, 0.54, 0.52);
    }
  }`;

// Windows: interior mapping. Behind every pane the shader traces the view ray into a virtual room
// (a box one storey high, uInt.x wide, uInt.z deep, in step with the real floor levels) and shades
// what it hits: back wall, side walls, floor, ceiling, a piece of furniture, curtains or blinds
// close behind the glass, a few rooms with the lights on. The room is emitted (it does not take the
// sun on the facade); the glass itself stays the physical material, so the sky and the clouds are
// reflected on top of it, strongest at grazing angles, as on real glass. Each pane is tilted by a
// hair (a fraction of a degree), so the reflections break up from pane to pane like a real facade.
const INTERIOR = /* glsl */ `
  vec3 roomLight = vec3(0.0);
  vec3 paneTilt = vec3(0.0);
  {
    vec3 fn = normalize(vWorldNormal);
    if (abs(fn.y) < 0.5) {
      vec3 Nn = normalize(vec3(fn.x, 0.0, fn.z));
      vec3 Tg = vec3(-Nn.z, 0.0, Nn.x);
      vec3 dir = normalize(vWorldPos - cameraPosition);
      float W = uInt.x, H = uInt.y, D = uInt.z;
      float u = dot(vWorldPos, Tg), v = vWorldPos.y - uInt.w;
      vec2 cell = floor(vec2(u / W, v / H));
      // which way the facade faces, in steps (the shading normal wavers a little across a pane)
      vec2 face = floor(Nn.xz * 3.0 + 0.5);
      vec2 key = cell + face * vec2(31.7, 57.3);
      float r1 = hash12(key), r2 = hash12(key * 1.37 + 3.1), r3 = hash12(key * 2.11 + 7.7);
      vec3 p = vec3(fract(u / W) * W, fract(v / H) * H, 0.0);
      vec3 d = vec3(dot(dir, Tg), dir.y, max(-dot(dir, Nn), 0.02));
      vec3 dd = vec3(abs(d.x) < 1e-4 ? 1e-4 : d.x, abs(d.y) < 1e-4 ? 1e-4 : d.y, d.z);
      vec3 tm = vec3((dd.x > 0.0 ? W - p.x : -p.x) / dd.x, (dd.y > 0.0 ? H - p.y : 0.02 - p.y) / dd.y, (D - p.z) / dd.z);
      float t = min(min(tm.x, tm.y), tm.z);
      vec3 h = p + d * t;
      vec3 wallC = mix(vec3(0.66, 0.62, 0.56), vec3(0.80, 0.78, 0.74), r2);
      wallC = mix(wallC, vec3(0.62, 0.68, 0.70), step(0.8, r3));
      vec3 col;
      if (t == tm.z) {
        col = wallC * 0.85;
        // a sofa, a bed or a cupboard against the back wall
        float fw = W * (0.25 + 0.3 * r3);
        if (h.y < 0.55 + 1.6 * step(0.7, r1) && abs(h.x - W * (0.3 + 0.4 * r2)) < fw) col = mix(vec3(0.28, 0.24, 0.21), vec3(0.55, 0.5, 0.45), r3);
        // a picture
        if (abs(h.y - 1.6) < 0.35 && abs(h.x - W * 0.5) < 0.45 && r3 > 0.45) col = vec3(0.2, 0.25, 0.3) + 0.4 * r1;
      } else if (t == tm.x) {
        col = wallC * 0.68;
      } else if (d.y < 0.0) {
        col = mix(vec3(0.40, 0.29, 0.20), vec3(0.62, 0.55, 0.47), r1);
      } else {
        col = vec3(0.88, 0.87, 0.85);
      }
      // daylight from the window falls off into the room
      col *= mix(1.0, 0.35, clamp(h.z / D, 0.0, 1.0));
      // a few rooms have the lights on by day, nearly half at night (warm; some cooler, a TV's blue)
      float lit = step(mix(0.972, 1.0 - uNightLamp.w, uNight), r1);
      vec3 lamp = mix(uNightLamp.rgb, vec3(0.5, 0.52, 0.56), step(0.8, r3) * uNight) * (1.0 + 1.3 * uNight);
      // the unlit rooms at night: dark, or (the glass tower, its night render) the glass's own teal glow
      vec3 light = mix(vec3(uInt2.x * (1.0 - 0.94 * uNight)) + uNightLamp.rgb * uNightDim * uNight, lamp, lit);
      if (lit > 0.5 && t != tm.z && d.y > 0.0) col = vec3(1.0, 0.94, 0.82);   // the lit ceiling
      vec3 room = col * light;
      // curtains half drawn, or blinds let down, just behind the glass
      float zc = 0.12;
      vec3 pc = p + d * (zc / d.z);
      float cw = W * (0.12 + 0.2 * r3);
      if (r2 > 0.62 && pc.y < H - 0.25 && (pc.x < cw || pc.x > W - cw)) {
        vec3 cc = mix(vec3(0.82, 0.78, 0.70), vec3(0.55, 0.50, 0.46), r1);
        room = cc * mix(uInt2.y * 0.9 * (1.0 - 0.92 * uNight), 0.7 * (1.0 + 0.8 * uNight), lit);
      }
      if (r2 < 0.18 && pc.y > H * (0.45 + 0.4 * r3)) {
        float sy = pc.y / 0.06, fw = max(fwidth(sy), 1e-3);
        float slat = 0.8 + 0.2 * clamp((abs(fract(sy) - 0.5) - 0.25) / fw + 0.5, 0.0, 1.0) * (1.0 - clamp(fw - 0.5, 0.0, 1.0));
        room = vec3(0.86, 0.85, 0.82) * mix(uInt2.y * (1.0 - 0.92 * uNight), 0.55 + 0.5 * uNight, lit * uNight) * slat;
      }
      // coated glass is a part mirror: the sky (blue above, haze at the horizon, the ground below)
      // over the room, more of it at grazing angles; the real reflections (clouds) come on top
      vec3 rr = reflect(dir, normalize(Nn + paneTilt * 2.0));
      float up = rr.y;
      vec3 skyR = mix(vec3(0.80, 0.85, 0.88), vec3(0.36, 0.52, 0.74), smoothstep(0.02, 0.7, up));
      skyR = mix(vec3(0.30, 0.31, 0.28), skyR, smoothstep(-0.06, 0.03, up));
      skyR *= 1.0 - 0.9 * uNight;   // the night sky (and the lit city in it) is dark in the glass
      float cosv = clamp(-dot(dir, Nn), 0.0, 1.0);
      float fres = uMirror + (1.0 - uMirror) * pow(1.0 - cosv, 5.0);
      // a lit room at night shows its own warm light, not the glass's daytime tint
      roomLight = room * mix(uTint, vec3(1.0), lit * uNight * 0.85) * (1.0 - fres) + skyR * uTint * fres * uRefl;
      // the tilt of this pane (world space; turned into view space where the normal is set)
      paneTilt = (Tg * (r2 - 0.5) + vec3(0.0, 1.0, 0.0) * (r3 - 0.5)) * uInt2.z;
    }
  }`;

function patch(mat, { vary = 0, detile = false, leafy = false, tint = null, facade = null, interior = null, night = null } = {}) {
  if (!vary && !detile && !leafy && !facade && !interior) return;
  const tintColor = new THREE.Color(tint ?? '#ffffff');
  mat.onBeforeCompile = (sh) => {
    lampChunk(sh);
    sh.uniforms.uVary = { value: vary };
    sh.uniforms.uTint = { value: tintColor };
    sh.uniforms.uFacade = { value: new THREE.Vector3(...(facade ?? [3, 3, 0])) };
    // interior: [width, storey, depth, floor 3 level, daylight in the room, curtains, pane tilt]
    const it = interior ?? [3, 3.3, 4, 8.7, 0.2, 0.3, 0.02];
    sh.uniforms.uInt = { value: new THREE.Vector4(it[0], it[1], it[2], it[3]) };
    sh.uniforms.uInt2 = { value: new THREE.Vector3(it[4], it[5], it[6]) };
    sh.uniforms.uMirror = { value: it[7] ?? 0.1 };
    sh.uniforms.uRefl = { value: it[8] ?? 0.9 };
    sh.uniforms.uNight = NIGHT;
    // the rooms' light at night: colour and the share of rooms lit; the glow of the unlit ones
    const nl = new THREE.Color(night?.lamp ?? '#9e8561');
    sh.uniforms.uNightLamp = { value: new THREE.Vector4(nl.r, nl.g, nl.b, night?.share ?? 0.44) };
    sh.uniforms.uNightDim = { value: night?.dim ?? 0 };
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vWorldPos;\nvarying vec3 vWorldNormal;')
      .replace('#include <worldpos_vertex>', `#include <worldpos_vertex>
        vec4 wp = vec4(transformed, 1.0);
        #ifdef USE_INSTANCING
          wp = instanceMatrix * wp;
        #endif
        vWorldPos = (modelMatrix * wp).xyz;
        vec3 on = objectNormal;
        #ifdef USE_INSTANCING
          on = mat3(instanceMatrix) * on; // the typical floors are instances, turned with their block
        #endif
        vWorldNormal = normalize(mat3(modelMatrix) * on);`);
    let frag = sh.fragmentShader.replace('#include <common>', `#include <common>\nvarying vec3 vWorldPos;\nvarying vec3 vWorldNormal;\nuniform float uVary;\nuniform vec3 uTint;\nuniform vec3 uFacade;\nuniform vec4 uInt;\nuniform vec3 uInt2;\nuniform float uMirror;\nuniform float uRefl;\nuniform float uNight;\nuniform vec4 uNightLamp;\nuniform float uNightDim;\n${NOISE}`);
    if (detile) {
      frag = frag.replace('#include <map_fragment>', `
        #ifdef USE_MAP
          vec4 t1 = texture2D(map, vMapUv);
          vec2 uv2 = mat2(0.81, -0.59, 0.59, 0.81) * vMapUv * 0.43 + vec2(0.37, 0.71);
          vec4 t2 = texture2D(map, uv2);
          float w = smoothstep(0.38, 0.62, fbm(vWorldPos.xz * 0.11));
          diffuseColor *= mix(t1, t2, w);
        #endif`);
    }
    frag = frag.replace('#include <color_fragment>', `#include <color_fragment>
      {
        float m = fbm(vWorldPos.xz * 0.045 + vWorldPos.y * 0.02);
        float s = fbm(vWorldPos.xz * 0.31 + 11.0);
        diffuseColor.rgb *= 1.0 + uVary * ((m - 0.5) * 1.6 + (s - 0.5) * 0.6);
        diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * uTint, smoothstep(0.45, 0.8, m));
      }`);
    if (interior) {
      frag = frag
        .replace('#include <color_fragment>', `#include <color_fragment>\n${INTERIOR}\n  diffuseColor.rgb = vec3(0.0);`)
        .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>\n  normal = normalize(normal + mat3(viewMatrix) * paneTilt);`)
        .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>\n  totalEmissiveRadiance += roomLight;`);
    }
    if (facade) {
      frag = frag
        .replace('#include <color_fragment>', `#include <color_fragment>\n${FACADE}`)
        .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
          roughnessFactor = mix(roughnessFactor, 0.06, facadeGlass);`)
        .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>\n  totalEmissiveRadiance += facadeLight;`);
    }
    if (leafy) {
      frag = frag
        .replace('#include <color_fragment>', `#include <color_fragment>
          float leafA = vnoise3(vWorldPos * 7.0), leafB = vnoise3(vWorldPos * 2.3 + 5.0);
          diffuseColor.rgb *= 0.62 + 0.55 * leafA * (0.6 + 0.4 * leafB);`)
        .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
          {
            vec3 q = vWorldPos * 9.0;
            vec3 g = vec3(vnoise3(q + vec3(0.13, 0, 0)) - vnoise3(q - vec3(0.13, 0, 0)),
                          vnoise3(q + vec3(0, 0.13, 0)) - vnoise3(q - vec3(0, 0.13, 0)),
                          vnoise3(q + vec3(0, 0, 0.13)) - vnoise3(q - vec3(0, 0, 0.13)));
            normal = normalize(normal - mat3(viewMatrix) * g * 2.2);
          }`);
    }
    sh.fragmentShader = frag;
  };
  mat.customProgramCacheKey = () => `v${vary}d${+detile}l${+leafy}i${interior ?? ''}f${facade ?? ''}${tintColor.getHexString()}`;
}

// ---------- the table ----------
// set: texture set in public/textures; tile: metres per repeat of the texture (the model's UVs
// are in metres); color: multiplies the colour map (tinted sets are neutral grey); normal: normal
// map strength; roughness/metalness: multiply the maps (or set the value when there is no map).
// Facade glass is MeshPhysicalMaterial for one reason: `ior`. Coated architectural glass reflects
// more than plain float glass (F0 ~0.04); ior 2.2 gives F0 ~0.14, so the sky and the clouds show in
// the windows as on a real facade, with the rooms behind at steep angles. The base colour is the room
// seen through the glass in daylight (a tenth or so of the brightness outside), not a glass tint. Nothing else of
// the physical material (transmission, clearcoat...) is switched on, so it costs about the same.
const glass = (color, roughness = 0.035, extra = {}) => ({ glass: true, physical: { ior: 2.2 }, color, roughness, metalness: 0, env: 1.3, ...extra });
const LIB = {
  // facades: smooth render on the towers, painted concrete slab edges, powder-coated frames
  Terracotta: { set: 'plaster', tile: 2.2, color: '#b67d68', roughness: 1, normal: 0.55, vary: 0.05, env: 0.6 },
  'Terracotta dark': { set: 'plaster', tile: 2.2, color: '#6f4132', roughness: 1, normal: 0.55, vary: 0.05, env: 0.6 },
  // white stone and render: the plaster set's relief and roughness, no colour map (its grey would
  // make the white stone grey; the renders' white is white)
  'White band': { set: 'plaster', mapless: true, tile: 2.2, color: '#f1efea', roughness: 0.6, normal: 0.15, vary: 0.01, env: 1.0 },
  'Plant room': { set: 'plaster', tile: 2.2, color: '#e4e1db', roughness: 0.9, normal: 0.4 },
  'Stone fin': { set: 'concrete', tile: 3, color: '#e3d6c2', roughness: 0.9, normal: 0.5 },
  Frame: { color: '#d7d1c6', roughness: 0.42, metalness: 0, env: 0.8 },
  Metal: { color: '#9aa0a5', roughness: 0.32, metalness: 0.9, env: 1 },
  'Shop frame': { color: '#2b2f33', roughness: 0.38, metalness: 0.7 },
  'Lamp white': { color: '#ecebe6', roughness: 0.35, metalness: 0.2 },
  Bollard: { color: '#e8e7e2', roughness: 0.5 },
  Roof: { set: 'concrete', tile: 3, color: '#a3a19c', roughness: 0.95, normal: 0.6, vary: 0.04 },
  'Solar panel': { color: '#1b2232', roughness: 0.18, metalness: 0.2, env: 1.1 },
  // glass: dark body seen through, reflections of the sky do the rest; slight tints only
  'Window glass': { ...glass('#000000', 0.03, { env: 0.9, tint: '#c4d4dc', interior: [2.9, 3.5, 4.2, 12.0, 0.17, 0.26, 0.012, 0.1, 0.6] }), physical: { ior: 1.6 } },
  // block A (renders 1, 2, 4): dark blue-green coated glass, the rooms behind it readable (curtains,
  // furniture, a light here and there), the sky in it strongest towards the top and at grazing angles
  // (22.10.2026: darker, as on renders 1, 2 and 4: a charcoal-blue body, the sky in it, not a pale blue face)
  // at night (the tower's night render): most rooms lit, the light and the glass teal
  'Tower glass': { ...glass('#000000', 0.02, { env: 1.35, tint: '#97b0c2', interior: [3.2, 3.75, 6.0, 12.0, 0.2, 0.36, 0.006, 0.3, 1.05], specular: '#d6e3ec', night: { lamp: '#4fa9b6', share: 0.6, dim: 0.14 } }), physical: { ior: 2.1 } },
  'Strip dark': { color: '#3e3934', roughness: 0.55, metalness: 0.25, env: 0.6 },
  // the slab blocks (renders 1-3): golden sandstone cornices and bay frames; the narrow tall
  // glazing light grey, the dark strips dark green, the corner bays blue
  'Stone pale': { set: 'plaster', mapless: true, tile: 2.2, color: '#b8bbbe', roughness: 0.7, normal: 0.25, env: 0.6 },
  // the cornice bands: bronze-gold as on the renders (the earlier #e8c08a was the yellowest thing on the facade)
  'Stone gold': { set: 'plaster', mapless: true, tile: 2.2, color: '#d0a062', roughness: 0.62, normal: 0.35, vary: 0.03, env: 0.6 },
  'Glass light': { ...glass('#000000', 0.03, { env: 1.4, tint: '#e6edf0', interior: [1.6, 3.5, 3.5, 12.0, 0.5, 0.75, 0.008, 0.45, 1.15] }), physical: { ior: 1.9 } },
  'Glass dark': { ...glass('#000000', 0.03, { env: 1.0, tint: '#b3a69c', interior: [1.2, 3.5, 2.5, 12.0, 0.2, 0.3, 0.006, 0.32, 0.75] }), physical: { ior: 2.0 } },
  'Bay glass': { ...glass('#000000', 0.03, { env: 1.15, tint: '#8db0c6', interior: [2.0, 3.5, 3.5, 12.0, 0.36, 0.55, 0.008, 0.3, 1.0], specular: '#d2e2ea' }), physical: { ior: 2.1 } },
  // Ali Binokor facades (renders 1-4): tan facing brick, dark grey brick, white stone crown
  // facing brick drawn in the browser (textures.js brickTextures): sandy multi-tone and graphite
  'Brick tan': { brick: 'tan', tile: 2.0, color: '#ffffff', roughness: 1, normal: 0.8, vary: 0.04, env: 0.45 },
  'Brick dark': { brick: 'dark', tile: 2.0, color: '#ffffff', roughness: 1, normal: 0.8, vary: 0.03, env: 0.5 },
  'Stone white': { set: 'plaster', mapless: true, tile: 2.2, color: '#efede7', roughness: 0.75, normal: 0.22, vary: 0.015, env: 0.8 },
  'Stone dark': { set: 'concrete', tile: 2.5, color: '#51545d', roughness: 0.72, normal: 0.35, vary: 0.02, env: 0.6 },
  'Frame dark': { color: '#2c3034', roughness: 0.38, metalness: 0.55, env: 0.9 },
  'Frame crown': { color: '#80868b', roughness: 0.45, metalness: 0.5, env: 0.8 },
  'Stone beige': { set: 'plaster', tile: 2.2, color: '#e3c597', roughness: 0.75, normal: 0.3, vary: 0.02, env: 0.6 },
  'Screen dark': { roughness: 0.75, metalness: 0.1, env: 0.55 },
  Poster: { roughness: 0.4, env: 0.4 },
  'Stair glass': glass('#000000', 0.03, { tint: '#a8d4e6', interior: [5.0, 3.5, 3.0, 12.0, 0.3, 0.25, 0.01, 0.4, 1.1] }),
  'Frame light': { color: '#eceeee', roughness: 0.4, metalness: 0.2, env: 0.9 },
  // block A's corner loggias (render 4): dark grey render, a light grey slab edge
  'Loggia wall': { set: 'plaster', tile: 2.2, color: '#5b5e63', roughness: 0.85, normal: 0.25, env: 0.5 },
  'Loggia soffit': { set: 'plaster', tile: 2.2, color: '#6a6d71', roughness: 0.9, normal: 0.2, env: 0.5 },
  'Loggia slab': { set: 'plaster', tile: 2.2, color: '#d6d7d6', roughness: 0.7, normal: 0.2, env: 0.7 },
  // block A's crown (render 4): perforated light grey sheet on the dark frame, the sky through it
  'Mesh screen': { color: '#f0f1f1', roughness: 0.6, metalness: 0.15, opacity: 1, transparent: true, env: 0.5, alpha: 'perforated', alphaTile: 0.5 },
  'Shop floor': { set: 'concrete', tile: 1.4, color: '#e9e4da', roughness: 0.3, normal: 0.15, env: 1 },
  // the shops behind the glass read warm and lit (renders 1 and 3)
  'Shop ceiling': { color: '#f3e7d4', roughness: 0.9 },
  'Shop wall': { color: '#e7d8c2', roughness: 0.9 },
  Shelf: { color: '#ece7de', roughness: 0.6 },
  Counter: { color: '#7c5b42', roughness: 0.5 },
  // the ground beyond the plot: a mown green with a little variation (no large mottling)
  Ground: { set: 'grass', tile: 3.2, color: '#6e9650', roughness: 1, normal: 0.6, vary: 0.07, detile: true, tint: '#9cb372' },
  'Rubber orange': { set: 'rubber', tile: 2, color: '#e08a45', roughness: 1, normal: 0.6 },
  'Rubber yellow': { set: 'rubber', tile: 2, color: '#e6c452', roughness: 1, normal: 0.6 },
  'Sport green': { set: 'grass', tile: 1.0, color: '#4f9a3c', roughness: 0.95, normal: 0.5, vary: 0.04 },
  'Track red': { set: 'rubber', tile: 2, color: '#b5573e', roughness: 1, normal: 0.6 },
  'Kinder wall': { set: 'brick', tile: 2.0, color: '#d98f6c', roughness: 0.92, normal: 0.8, vary: 0.04 },
  'Hospital wall': { set: 'plaster', tile: 2.5, color: '#f0f3f4', roughness: 0.85, normal: 0.3 },
  'School wall': { set: 'plaster', tile: 2.5, color: '#ecdfcc', roughness: 0.9, normal: 0.3 },
  City: { set: 'plaster', tile: 3, color: '#ffffff', roughness: 0.92, normal: 0.25, vary: 0.05, env: 0.5, facade: [3.0, 3.4, 400] },
  'Curtain glass': glass('#33494a'),
  'Shop glass': { color: '#e9e4d8', roughness: 0.03, opacity: 0.16, transparent: true, env: 0.55 },
  'Shop window': glass('#56605d', 0.05),
  'Gallery glass': glass('#7f8a88', 0.06),
  'Stained orange': glass('#8a4a22', 0.05),
  'Stained pink': glass('#86364f', 0.05),
  'Stained blue': glass('#27427c', 0.05),
  'Stained violet': glass('#53357a', 0.05),
  'Railing glass': { color: '#c8d8dc', roughness: 0.04, opacity: 0.2, transparent: true, env: 1 },
  'Railing glass dark': { color: '#2d3d46', roughness: 0.04, opacity: 0.72, transparent: true, env: 1 },
  // ground
  // asphalt: the photographed set at 6 m a tile (its stains then read as wear, not as blotches),
  // detiled and a little lighter; concrete paving slabs for the sidewalks
  Asphalt: { set: 'asphalt', tile: 6, color: '#dedbd3', roughness: 1, normal: 0.6, vary: 0.05, detile: true },
  'Road line': { color: '#e4e2db', roughness: 0.7 },
  Sidewalk: { color: '#ffffff', roughness: 0.95, vary: 0.05, env: 0.6 },
  // the plaza and the sidewalks: drawn pavers (textures.js), the photographed sets are dark and stained
  Paving: { color: '#ffffff', roughness: 0.95, vary: 0.05, env: 0.6 },
  Kerb: { set: 'concrete', tile: 2, color: '#d9d4ca', roughness: 0.95, normal: 0.6 },
  Lawn: { set: 'grass', tile: 2.4, color: '#6c9a52', roughness: 1, normal: 0.9, vary: 0.06, detile: true, tint: '#9ebb74' },
  Grass: { set: 'grass', tile: 2.4, color: '#73955a', roughness: 1, normal: 0.9, vary: 0.08, detile: true, tint: '#a8b97c' },
  Mulch: { set: 'grass', mapless: true, tile: 1.2, color: '#4b3527', roughness: 1, normal: 1.2, vary: 0.05 },
  Embankment: { set: 'concrete', tile: 4, color: '#c4b8a6', roughness: 1, normal: 0.7, vary: 0.08 },
  Bridge: { set: 'concrete', tile: 4, color: '#bdb9b1', roughness: 0.95, normal: 0.6, vary: 0.05 },
  Planter: { set: 'concrete', tile: 2, color: '#dcd7cd', roughness: 0.9, normal: 0.5 },
  // podium deck, shop front and promenade (render 2)
  'Deck paving': { set: 'patio', tile: 2.15, color: '#f0d5b8', roughness: 1, normal: 0.6, vary: 0.05 },
  'Deck stone': { set: 'patio', tile: 2.15, color: '#e8c9a4', roughness: 1, normal: 0.6, vary: 0.05 },
  Promenade: { set: 'paving', tile: 2, color: '#f2e2d8', roughness: 1, normal: 0.7, vary: 0.05, detile: true },
  Cobble: { set: 'setts', tile: 1.1, color: '#ece8e2', roughness: 1, normal: 0.6, vary: 0.05, detile: true },
  // the crazy paving of the decks, the hotel terrace and the promenade: one natural stone in four
  // close tones (the model gives each stone one of four shared materials; see flagstone() below)
  'Flag light': { set: 'concrete', tile: 1.4, color: '#dcd8d0', roughness: 0.95, normal: 0.7, vary: 0.06 },
  'Flag mid': { set: 'concrete', tile: 1.4, color: '#c4bfb6', roughness: 0.95, normal: 0.7, vary: 0.06 },
  'Flag warm': { set: 'concrete', tile: 1.4, color: '#d2c8b9', roughness: 0.95, normal: 0.7, vary: 0.06 },
  'Flag dark': { set: 'concrete', tile: 1.4, color: '#aeaaa3', roughness: 0.95, normal: 0.7, vary: 0.06 },
  'Cobble joint': { color: '#8a857e', roughness: 1 },
  Wood: { set: 'deck', tile: 1.8, color: '#d9b08c', roughness: 0.9, normal: 0.6 },
  'Lattice wood': { set: 'deck', tile: 1.8, color: '#f0d2ad', roughness: 0.85, normal: 0.4 },
  'Rubber blue': { set: 'rubber', tile: 2, color: '#3f6ea8', roughness: 1, normal: 0.7 },
  // the school (21.10.2026): white render, coloured fins, a dark stone plinth
  'School render': { set: 'plaster', mapless: true, tile: 2.2, color: '#f2eee6', roughness: 0.8, normal: 0.25, vary: 0.015, env: 0.7 },
  'School plinth': { set: 'concrete', tile: 2.5, color: '#66635e', roughness: 0.8, normal: 0.4, env: 0.5 },
  'School terracotta': { set: 'plaster', mapless: true, tile: 2.2, color: '#c4633f', roughness: 0.75, normal: 0.25, env: 0.6 },
  'School ochre': { set: 'plaster', mapless: true, tile: 2.2, color: '#dba849', roughness: 0.75, normal: 0.25, env: 0.6 },
  'School teal': { set: 'plaster', mapless: true, tile: 2.2, color: '#318c88', roughness: 0.75, normal: 0.25, env: 0.6 },
  'Court blue': { set: 'rubber', tile: 2, color: '#3a74ad', roughness: 0.95, normal: 0.4 },
  // the six-a-side pitch: artificial turf mown in stripes, white goals, nets and a green mesh fence
  Turf: { set: 'grass', tile: 1.2, color: '#4a9440', roughness: 0.95, normal: 0.45, vary: 0.02 },
  'Turf light': { set: 'grass', tile: 1.2, color: '#5ca64f', roughness: 0.95, normal: 0.45, vary: 0.02 },
  'Goal white': { color: '#f5f5f3', roughness: 0.35, metalness: 0.2, env: 0.9 },
  Net: { color: '#f4f4f2', roughness: 0.7, opacity: 1, transparent: true, alpha: 'perforated', alphaTile: 0.12, env: 0.4 },
  'Pitch fence': { color: '#32503f', roughness: 0.6, metalness: 0.3, opacity: 1, transparent: true, alpha: 'perforated', alphaTile: 0.09, env: 0.5 },
  // playgrounds and the kindergarten
  Sand: { set: 'concrete', mapless: true, tile: 1.5, color: '#e6d3a1', roughness: 1, normal: 0.8, vary: 0.04 },
  Canopy: { color: '#f3f0e8', roughness: 0.85, env: 0.5 },
  'Kinder render': { set: 'plaster', mapless: true, tile: 2.2, color: '#f7f3ec', roughness: 0.8, normal: 0.22, vary: 0.015, env: 0.7 },
  // flower beds
  'Flowers red': { color: '#c43048', roughness: 0.85, leafy: true, env: 0.35 },
  'Flowers yellow': { color: '#e8c13c', roughness: 0.85, leafy: true, env: 0.35 },
  'Flowers violet': { color: '#8f54b5', roughness: 0.85, leafy: true, env: 0.35 },
  'Flowers white': { color: '#f2f0ea', roughness: 0.85, leafy: true, env: 0.35 },
  'Play orange': { set: 'rubber', tile: 2, color: '#c0603e', roughness: 1, normal: 0.7 },
  'Play blue': { set: 'rubber', tile: 2, color: '#2f6da8', roughness: 0.8, normal: 0.5 },
  // neighbours: plain massing in the model; storeys and windows are drawn on (facade: storey
  // height, bay width, roof level, metres)
  Neighbour: { set: 'plaster', tile: 3, color: '#d9cfc0', roughness: 0.92, normal: 0.25, vary: 0.04, env: 0.6, facade: [3.0, 3.3, 48] },
  'Neighbour solid': { set: 'plaster', tile: 3, color: '#e3d9c9', roughness: 0.92, normal: 0.3, vary: 0.04, env: 0.6, facade: [3.0, 3.2, 15] },
  'Neighbour cream': { set: 'plaster', tile: 3, color: '#e8d4a2', roughness: 0.92, normal: 0.3, vary: 0.04, env: 0.6, facade: [3.0, 3.2, 15] },
  'Neighbour peach': { set: 'plaster', tile: 3, color: '#e6bd9b', roughness: 0.92, normal: 0.3, vary: 0.04, env: 0.6, facade: [3.0, 3.2, 15] },
  'Neighbour blue': { set: 'plaster', tile: 3, color: '#b8cbd8', roughness: 0.92, normal: 0.3, vary: 0.04, env: 0.6, facade: [3.0, 3.2, 15] },
  'Neighbour mint': { set: 'plaster', tile: 3, color: '#c0d5bf', roughness: 0.92, normal: 0.3, vary: 0.04, env: 0.6, facade: [3.0, 3.2, 15] },
  'Neighbour rose': { set: 'plaster', tile: 3, color: '#dfb5ab', roughness: 0.92, normal: 0.3, vary: 0.04, env: 0.6, facade: [3.0, 3.2, 15] },
  // plants in the model (balcony planters, hedges, deck planting)
  Shrub: { color: '#3c5a26', roughness: 0.95, leafy: true, env: 0.35 },
  Leaves: { color: '#36531f', roughness: 0.95, leafy: true, env: 0.35 },
  'Leaves light': { color: '#557a2a', roughness: 0.95, leafy: true, env: 0.35 },
  Trunk: { color: '#4a3a2e', roughness: 0.95 },
  // water: the sky in it does the work
  River: { water: true, color: '#20363c', roughness: 0.06, tile: 9, env: 1 },
  // white flecks drawn on the river of the stylised render: not part of a real river surface
  Foam: { hidden: true },
  'Pool water': { water: true, color: '#2c8fa6', roughness: 0.03, tile: 2.5, env: 1 },
};

// textures made on a canvas (textures.js) for surfaces with no photographed set
const CANVAS = { 'Pool mosaic': 'mosaic', 'Copper screen': 'copper', Sidewalk: 'slabs', Paving: 'plaza', 'Screen dark': 'screen', Poster: 'poster' };

let waterNormal = null;
export const water = []; // normal maps to scroll each frame

function waterNormalMap() {
  if (waterNormal) return waterNormal;
  // tileable ripples: a few crossing sine waves with integer frequencies
  const N = 256, c = document.createElement('canvas');
  c.width = c.height = N;
  const g = c.getContext('2d'), img = g.createImageData(N, N);
  const waves = [[3, 1, 0.9], [-2, 4, 0.7], [5, -3, 0.45], [1, 7, 0.3], [-7, -2, 0.25], [9, 5, 0.15]];
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      let dx = 0, dy = 0;
      for (const [kx, ky, a] of waves) {
        const ph = ((kx * x + ky * y) / N) * Math.PI * 2 + kx * 1.7;
        dx += a * kx * Math.cos(ph);
        dy += a * ky * Math.cos(ph);
      }
      const nx = -dx * 0.035, ny = -dy * 0.035, l = Math.hypot(nx, ny, 1);
      const i = (y * N + x) * 4;
      img.data[i] = (nx / l * 0.5 + 0.5) * 255;
      img.data[i + 1] = (ny / l * 0.5 + 0.5) * 255;
      img.data[i + 2] = (1 / l * 0.5 + 0.5) * 255;
      img.data[i + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  waterNormal = new THREE.CanvasTexture(c);
  waterNormal.wrapS = waterNormal.wrapT = THREE.RepeatWrapping;
  waterNormal.colorSpace = THREE.NoColorSpace;
  return waterNormal;
}

// stones of the crazy paving: the same four materials also make bridges, kerbs and sidewalks
// elsewhere, so only the paving's meshes get the flagstone twins
const FLAG = { Cobble: 'Flag light', Bridge: 'Flag mid', Kerb: 'Flag warm', Sidewalk: 'Flag dark' };
const PAVED = /^(Podium_decks|Hotel_terrace_wing|Promenade)$/;
const flags = new Map();
/** The material for a stone of the crazy paving (mesh in one of the paved groups), else null. */
export function flagstone(mesh, m) {
  const name = FLAG[m.name];
  if (!name || !PAVED.test(mesh.parent?.name ?? '')) return null;
  if (!flags.has(name)) {
    const f = m.clone();
    f.name = name;
    flags.set(name, f);
  }
  return flags.get(name);
}

/**
 * Configure one material of the model. Returns a promise that settles when its textures are in
 * (the model shows at once with its base colours, textures fade in as they arrive).
 */
const replaced = new Map();
/** The material a mesh should use: the loaded one, or for facade glass its physical twin. */
export function materialFor(m) {
  const spec = LIB[m.name];
  if (!spec?.physical) return m;
  if (!replaced.has(m)) {
    const p = new THREE.MeshPhysicalMaterial();
    THREE.MeshStandardMaterial.prototype.copy.call(p, m); // every standard property, as loaded
    p.name = m.name;
    p.userData = { ...m.userData };
    Object.assign(p, spec.physical);
    if (spec.specular) p.specularColor.set(spec.specular); // a faint green in the reflections (coated glass)
    replaced.set(m, p);
  }
  return replaced.get(m);
}

export function setupMaterial(m, renderer) {
  anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  const spec = LIB[m.name];
  if (spec?.hidden) {
    m.visible = false;
    return Promise.resolve();
  }
  if (spec?.alpha) {
    // a cut-out pattern (the perforated screen): the pattern's mips average to the open share far off
    const a = alphaTexture(spec.alpha);
    a.repeat.set(1 / spec.alphaTile, 1 / spec.alphaTile);
    m.alphaMap = a;
    m.needsUpdate = true;
  }
  if (CANVAS[m.name]) {
    m.map = groundTexture(CANVAS[m.name]);
    m.color.set(0xffffff);
    if (m.name === 'Poster') {
      // lit from behind like a light box
      m.emissive?.set(0xffffff);
      m.emissiveMap = m.map;
      m.emissiveIntensity = 0.55;
    }
    if (m.name === 'Copper screen') {
      m.metalness = 0.55;
      m.roughness = 0.42;
    }
    m.needsUpdate = true;
  }
  if (!spec) return Promise.resolve();
  if (spec.color) m.color.set(spec.color);
  if (spec.roughness !== undefined) m.roughness = spec.roughness;
  if (spec.metalness !== undefined) m.metalness = spec.metalness;
  m.envMapIntensity = spec.env ?? 0.85;
  if (spec.glass) m.userData.glass = true;   // world.js gives it the real sky to reflect
  // the model's glass carries KHR_materials_specular from Blender; plain F0 = 0.04 is right for glass
  if (m.specularIntensity !== undefined && spec.glass) m.specularIntensity = 1;
  if (spec.transparent) {
    m.transparent = true;
    m.opacity = spec.opacity;
    m.depthWrite = false;
    m.side = THREE.FrontSide; // the rails are modelled as two faces back to back
  } else {
    m.transparent = false;
    m.opacity = 1;
    m.depthWrite = true;
  }
  if (m.emissive && !m.name.startsWith('Lamp') && !m.name.startsWith('Sign')) m.emissiveIntensity = m.name.startsWith('Stained') ? 0.08 : m.emissiveIntensity;
  patch(m, spec);
  if (spec.water) {
    const n = waterNormalMap().clone();
    n.repeat.set(1 / spec.tile, 1 / spec.tile);
    n.needsUpdate = true;
    m.normalMap = n;
    m.normalScale.set(0.35, 0.35);
    water.push(n);
    m.needsUpdate = true;
    return Promise.resolve();
  }
  if (spec.brick) {
    const t = brickTextures(spec.brick);
    const rep = (x) => {
      const c = x.clone();
      c.repeat.set(1 / spec.tile, 1 / spec.tile);
      c.needsUpdate = true;
      return c;
    };
    m.map = rep(t.map);
    m.normalMap = rep(t.normal);
    m.normalScale.set(spec.normal ?? 1, spec.normal ?? 1);
    m.roughnessMap = rep(t.rough);
    m.aoMap = null;
    m.needsUpdate = true;
    return Promise.resolve();
  }
  if (!spec.set) {
    m.needsUpdate = true;
    return Promise.resolve();
  }
  return Promise.all([map(spec.set, 'color', spec.tile), map(spec.set, 'normal', spec.tile), map(spec.set, 'orm', spec.tile)])
    .then(([color, normal, orm]) => {
      m.map = spec.mapless ? null : color;
      m.normalMap = normal;
      m.normalScale.set(spec.normal ?? 1, spec.normal ?? 1);
      m.roughnessMap = orm; // green channel
      m.aoMap = orm; // red channel: the surface's own small-scale occlusion (indirect light only)
      m.aoMapIntensity = 0.8;
      m.needsUpdate = true;
    })
    .catch((e) => console.warn('texture set', spec.set, e));
}
