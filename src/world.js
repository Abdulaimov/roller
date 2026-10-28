// Sky, sun, mountains, trees, cars and people. Ground, roads and buildings come with the model.
//
// Light: the sky is an HDRI (Poly Haven, CC0) that lights the scene through the environment map
// and is the background; its sun disc was taken out (scripts/build_web_assets.py) and replaced by
// a directional light from the same direction, so the sun casts shadows and is counted once.
// Dushanbe lies in a valley: the Hissar range rises to the north, lower ridges close it in the
// south; they are drawn here as a ring of hazy ridges far beyond the city.
import * as THREE from 'three';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';
import { CARS, PEOPLE, TREES, toScene } from './config.js';
import { addCars, addPeople, addRealPeople, addTrees } from './props.js';
import { Q } from './quality.js';
import skyInfo from '../public/env/sky.json';

const ENV = `${import.meta.env.BASE_URL}env/`;
// daylight like the marketing renders: a clear afternoon sun, nearly white (a yellow sun and a
// warmed sky light made the brick and the white stone read yellow, 22.10.2026); a bright, clear sky
// whose light fills the shade (the walls in the shade read in their colours, not grey: 23.10.2026,
// "the houses look dull"); ?sun= ?sky= ?suncolor= ?skysat= ?clouds= to compare
const LIGHT = new URLSearchParams(location.search);
const SKY_INTENSITY = +(LIGHT.get('sky') ?? 1.85);
const SUN_INTENSITY = +(LIGHT.get('sun') ?? 3.3);
const SUN_COLOR = LIGHT.get('suncolor') ? `#${LIGHT.get('suncolor')}` : '#fff6ea';
const HAZE = new THREE.Color(0xcad6e0);

function rng(seed) {
  return () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
}

// the views of the client renders (render 1 from the south, render 2 from the north-west): the
// background city keeps out of the way between these cameras and the complex
const CORRIDORS = [
  { from: [-81, 420], to: [[-150, 40], [80, 40]] },
  { from: [-315, -158], to: [[-140, 60], [-60, -100]] },
];
function inCorridor(x, z, w, l) {
  const r = Math.hypot(w, l) / 2 + 12;
  for (const c of CORRIDORS) {
    const [ax, az] = c.from;
    for (const [bx, bz] of [c.to[0], c.to[1], [(c.to[0][0] + c.to[1][0]) / 2, (c.to[0][1] + c.to[1][1]) / 2]]) {
      const dx = bx - ax, dz = bz - az, L2 = dx * dx + dz * dz;
      const t = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / L2));
      if (Math.hypot(x - (ax + dx * t), z - (az + dz * t)) < r + 18 * t) return true;
    }
    // and the wedge between the two edge rays
    const cross = (p, q) => p[0] * q[1] - p[1] * q[0];
    const v0 = [c.to[0][0] - ax, c.to[0][1] - az], v1 = [c.to[1][0] - ax, c.to[1][1] - az], v = [x - ax, z - az];
    const inside = cross(v0, v) * cross(v0, v1) >= 0 && cross(v1, v) * cross(v1, v0) >= 0;
    if (inside && Math.hypot(...v) < Math.hypot(...v0) + 20) return true;
  }
  return false;
}

/** the city round the complex: quarters of four- to nine-storey blocks on the street grid of the
 * site (turned 27 degrees), with trees along the streets and in the yards; returns the trees */
// the modelled site in scene metres: the genplan's area and the school's ground (blender/ab)
// the neighbourhood within 600 m is modelled from OpenStreetMap (blender/rp/site.py)
const offSite = (p) => Math.hypot(p.x, p.z) < 600;

function city(scene) {
  const rnd = rng(31);
  const boxes = [], trees = [], lights = [];
  const a = (40.5 * Math.PI) / 180, ca = Math.cos(a), sa = Math.sin(a);
  const Q = 150; // a quarter with its streets
  const site = (u, v) => ({ x: ca * u - sa * v, z: -(sa * u + ca * v) });
  for (let i = -9; i <= 9; i++) {
    for (let j = -9; j <= 9; j++) {
      const u0 = i * Q, v0 = j * Q;
      const d = Math.hypot(u0, v0);
      if (d > 1400) continue;
      // not on the modelled site (the genplan area, spread 1.1 times, and the school's ground to
      // the north-west) nor on its roads
      const c = site(u0, v0);
      if (offSite(c)) continue;
      const kind = rnd();
      const n = kind < 0.15 ? 0 : 2 + Math.floor(rnd() * 4);
      for (let k = 0; k < n; k++) {
        const long = rnd() < 0.6;
        const w = long ? 50 + rnd() * 50 : 14 + rnd() * 14, l = long ? 12 + rnd() * 3 : 14 + rnd() * 10;
        const floors = d < 600 ? (rnd() < 0.25 ? 9 : 4 + Math.floor(rnd() * 2)) : 4 + Math.floor(rnd() * 3);
        const u = u0 + (rnd() - 0.5) * (Q - 60), v = v0 + (rnd() - 0.5) * (Q - 50);
        const p = site(u, v);
        if (offSite(p)) continue;
        // nothing between the presentation cameras (renders 1 and 2) and the complex
        if (inCorridor(p.x, p.z, w, l)) continue;
        boxes.push({ x: p.x, z: p.z, w, l, h: floors * 3.0, r: a + (rnd() < 0.5 ? 0 : Math.PI / 2) });
      }
      // street trees on the quarter's edges, a few in the yard
      for (let k = 0; k < 18; k++) {
        const side = Math.floor(rnd() * 4), t = (rnd() - 0.5) * Q;
        const e = Q / 2 - 6;
        const [u, v] = side === 0 ? [u0 + t, v0 - e] : side === 1 ? [u0 + t, v0 + e] : side === 2 ? [u0 - e, v0 + t] : [u0 + e, v0 + t];
        trees.push({ ...site(u, v), h: 7 + rnd() * 6 });
      }
      for (let k = 0; k < 8; k++) trees.push({ ...site(u0 + (rnd() - 0.5) * Q * 0.8, v0 + (rnd() - 0.5) * Q * 0.8), h: 6 + rnd() * 6 });
      // street lights along two of its edges (the next quarter has the other two), lit at night
      for (let t = -Q / 2 + 12; t < Q / 2; t += 27) {
        for (const [u, v] of [[u0 + t, v0 - Q / 2 + 4], [u0 - Q / 2 + 4, v0 + t]]) lights.push({ ...site(u, v), y: 7.5 });
      }
    }
  }
  const geo = new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0);
  const mat = new THREE.MeshStandardMaterial({ name: 'City', color: 0xffffff, roughness: 0.95 });
  const im = new THREE.InstancedMesh(geo, mat, boxes.length);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3(), col = new THREE.Color();
  boxes.forEach((b, i) => {
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), b.r);
    m4.compose(p.set(b.x, 0, b.z), q, s.set(b.w, b.h, b.l));
    im.setMatrixAt(i, m4);
    // walls painted as in Dushanbe's quarters (22.10.2026: no more grey boxes): cream, peach,
    // terracotta, dusty pink, pale blue, mint, sand, white, brick; soft, not loud
    const tones = [[0.11, 0.42, 0.74], [0.07, 0.4, 0.72], [0.03, 0.34, 0.62], [0.97, 0.22, 0.74], [0.56, 0.24, 0.72], [0.42, 0.18, 0.7], [0.09, 0.26, 0.66], [0.08, 0.05, 0.84], [0.03, 0.36, 0.5]];
    const t = tones[Math.floor(rnd() * tones.length)];
    im.setColorAt(i, col.setHSL(t[0] + (rnd() - 0.5) * 0.02, t[1] * (0.8 + rnd() * 0.4), t[2] * (0.94 + rnd() * 0.1)));
  });
  im.castShadow = false;
  im.receiveShadow = true;
  im.name = 'city';
  scene.add(im);
  return { mat, trees, lights };
}

// ---------- the sky ----------
// A clear deep blue, paler towards the horizon (as on the competitor's site the client liked,
// 23.10.2026), and over it the photographed cumulus of the HDRI, cut out of its own paler sky
// (tools/ab/clouds.py: public/env/clouds_*.webp; drawn clouds read as smears next to real ones).
// Drawn per pixel on a sphere round the camera. Below the horizon the haze's colour for a degree
// and a half (the plain's far edge meets it without a line), then the ground's dark green-grey
// (only reflections see it). Colours sRGB, by elevation.
const SKY_STOPS = [[-90, [38, 46, 34]], [-6, [70, 80, 64]], [-1.5, [186, 214, 244]], [0, [186, 214, 244]], [2, [158, 200, 243]], [5, [110, 172, 235]],
  [10, [62, 142, 228]], [15, [32, 122, 216]], [30, [16, 102, 206]], [90, [10, 86, 194]]];
const HORIZON = 3; // the stop at the horizon
const lin = (c) => ((c / 255 + 0.055) / 1.055) ** 2.4;
// the cloud layer, shared by the sky and the sky the glass reflects (loaded in buildWorld)
// (tint: the light on them, warm and dimmer at dusk, src/night.js)
const CLOUDS = { map: { value: null }, on: { value: 0 }, rot: { value: new THREE.Matrix3() }, tint: { value: new THREE.Color(1, 1, 1) } };
// light: the sky's brightness, 0..1 (src/night.js dims it at dusk; the night's dome covers it)
function makeSky(sunDir, light = { value: 1 }) {
  const el = SKY_STOPS.map((s) => s[0]);
  const col = SKY_STOPS.map((s) => new THREE.Vector3(...s[1].map(lin)));
  const mat = new THREE.ShaderMaterial({
    name: 'Sky',
    side: THREE.BackSide,
    depthWrite: false,
    depthTest: false,
    fog: false,
    uniforms: {
      uEl: { value: el },
      uCol: { value: col },
      uSun: { value: sunDir.clone().normalize() },
      uClouds: CLOUDS.map,
      uCloudsOn: CLOUDS.on,
      uRot: CLOUDS.rot,
      uCloudTint: CLOUDS.tint,
      uLight: light,
    },
    vertexShader: /* glsl */ `
      varying vec3 vDir;
      void main() {
        vDir = (modelMatrix * vec4(position, 0.0)).xyz;
        vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        gl_Position = p.xyww;
      }`,
    fragmentShader: /* glsl */ `
      uniform float uEl[${el.length}];
      uniform vec3 uCol[${el.length}];
      uniform vec3 uSun;
      uniform sampler2D uClouds;
      uniform float uCloudsOn;
      uniform mat3 uRot;
      uniform vec3 uCloudTint;
      uniform float uLight;
      varying vec3 vDir;
      vec3 gradient(float e) {
        vec3 c = uCol[0];
        for (int i = 1; i < ${el.length}; i++) {
          float k = clamp((e - uEl[i - 1]) / (uEl[i] - uEl[i - 1]), 0.0, 1.0);
          c = e > uEl[i - 1] ? mix(uCol[i - 1], uCol[i], k) : c;
        }
        return c;
      }
      void main() {
        vec3 d = normalize(vDir);
        float e = degrees(asin(clamp(d.y, -1.0, 1.0)));
        vec3 col = gradient(e);
        // a soft glow round the sun (the disc itself is the directional light's, not drawn)
        float s = max(dot(d, normalize(uSun)), 0.0);
        col += vec3(1.0, 0.96, 0.88) * (0.25 * pow(s, 24.0) + 0.06 * pow(s, 4.0)) * step(0.0, d.y);
        if (uCloudsOn > 0.5 && d.y > 0.0) {
          // the photographed clouds: the HDRI's panorama turned as the scene's light is (uRot), its
          // upper half (v = elevation / 90); light stored as sqrt(c / 3), cover in alpha
          vec3 q = uRot * d;
          vec2 uv = vec2(atan(q.z, q.x) * 0.15915494 + 0.5, asin(clamp(q.y, 0.0, 1.0)) * 0.63661977);
          vec4 cl = texture2D(uClouds, uv);
          col = mix(col, cl.rgb * cl.rgb * 3.0 * uCloudTint, cl.a);
        }
        gl_FragColor = vec4(col * uLight, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(1000, 48, 24), mat);
  mesh.name = 'sky';
  mesh.frustumCulled = false;
  mesh.renderOrder = -1000;
  // round the camera, whichever is drawing (the cube cameras of the glass's reflections too)
  mesh.onBeforeRender = (r, sc, cam) => {
    mesh.position.setFromMatrixPosition(cam.matrixWorld);
    mesh.updateMatrixWorld();
  };
  return mesh;
}

/**
 * @param after  resolves when the model is in: sky, trees and cars wait for it
 */
export function buildWorld(scene, renderer, after = Promise.resolve()) {
  // The HDRI's sun stands in the east-south-east (azimuth 124 deg). The sky is turned so that the sun
  // comes from the south-south-west (210 deg), the afternoon light of the renders: the street faces of
  // the blocks and the west face of the glass tower are in the sun.
  const SKY_TURN = THREE.MathUtils.degToRad(-86);
  const sunDir = new THREE.Vector3(...skyInfo.sun_dir).normalize().applyAxisAngle(new THREE.Vector3(0, 1, 0), SKY_TURN);
  scene.backgroundRotation.set(0, SKY_TURN, 0);
  scene.environmentRotation.set(0, SKY_TURN, 0);
  // the HDRI's clouds turned with its light: a direction in the scene -> in the panorama
  CLOUDS.rot.value.setFromMatrix4(new THREE.Matrix4().makeRotationY(-SKY_TURN));

  // aerial perspective: the city a kilometre out a little hazy, the complex (100-400 m) clear; the
  // haze the sky's colour at the horizon, so the plain runs into the sky
  scene.fog = new THREE.FogExp2(HAZE.getHex(), +(LIGHT.get('fog') ?? 0.0007));
  scene.fog.color.setRGB(...SKY_STOPS[HORIZON][1].map(lin)).multiplyScalar(0.97);
  const skyLight = { value: 1 };
  scene.add(makeSky(sunDir, skyLight));
  scene.background = null;
  scene.environmentIntensity = SKY_INTENSITY;

  const sun = new THREE.DirectionalLight(new THREE.Color(SUN_COLOR), SUN_INTENSITY);
  sun.position.copy(sunDir).multiplyScalar(600);
  sun.castShadow = true;
  sun.shadow.mapSize.set(Q.shadowMap, Q.shadowMap);
  const sc = sun.shadow.camera;
  sc.left = -250;
  sc.right = 250;
  sc.top = 250;
  sc.bottom = -250;
  sc.near = 200;
  sc.far = 1100;
  sun.shadow.bias = -0.0003;
  sun.shadow.normalBias = 0.06;
  scene.add(sun, sun.target);

  const fill = new THREE.HemisphereLight(0xd8e6f5, 0x8a8170, 1.2);
  scene.add(fill);
  // (no mountains: the renders show none, and a drawn ridge reads as fake at this distance)
  // the plain beyond the modelled ground (3 x 3 km) out to the haze, so the horizon is the fog's
  const plain = new THREE.Mesh(
    new THREE.RingGeometry(1400, 16000, 64, 1).rotateX(-Math.PI / 2),
    new THREE.MeshStandardMaterial({ color: 0x86955c, roughness: 1 }),
  );
  plain.position.y = -0.12;
  plain.receiveShadow = false;
  scene.add(plain);
  const { mat: cityMat, trees: cityTrees, lights: cityLights } = city(scene);

  const pmrem = new THREE.PMREMGenerator(renderer);
  const hdr = new RGBELoader().setDataType(THREE.FloatType);
  const sky = (res) => hdr.loadAsync(`${ENV}sky_${res}.hdr`).then((t) => ((t.mapping = THREE.EquirectangularReflectionMapping), t));
  // the light of the sky on the buildings: part of the HDRI's blue taken out (the renders' white
  // stone is white, not blue-grey), no warmth added (it turned the facades yellow); below the horizon
  // the HDRI mirrors its sky: the light from below is the ground's instead (lawns and paving in the
  // sun, a green-beige, darker straight down), so the undersides are not lit blue
  const neutral = (t) => {
    const src = t.image.data, n = src.length / 4;
    const out = new Float32Array(src.length);
    const K = +(LIGHT.get('skysat') ?? 0.62);
    const W_ = t.image.width, H_ = t.image.height;
    const GROUND = [0.27, 0.27, 0.2];
    for (let i = 0; i < n; i++) {
      const r = src[i * 4], g = src[i * 4 + 1], b = src[i * 4 + 2];
      const l = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      let o = [l + (r - l) * K, l + (g - l) * K, l + (b - l) * K];
      const el = 90 - ((Math.floor(i / W_) + 0.5) / H_) * 180;
      if (el < 1) {
        const k = THREE.MathUtils.clamp((1 - el) / 4, 0, 1);
        const dark = 1 - 0.35 * THREE.MathUtils.clamp(-el / 90, 0, 1);
        o = o.map((v, j) => v + (GROUND[j] * dark - v) * k);
      }
      out[i * 4] = o[0];
      out[i * 4 + 1] = o[1];
      out[i * 4 + 2] = o[2];
      out[i * 4 + 3] = 1;
    }
    const e = new THREE.DataTexture(out, t.image.width, t.image.height, THREE.RGBAFormat, THREE.FloatType);
    e.mapping = THREE.EquirectangularReflectionMapping;
    e.colorSpace = t.colorSpace;
    e.flipY = t.flipY; // the HDR's rows run top-down (RGBELoader flips it on upload)
    e.needsUpdate = true;
    return e;
  };
  // the clouds: 4k on computers, 2k on phones, ?clouds=8k for the TV film, ?clouds=none for a clear sky
  const cloudsRes = LIGHT.get('clouds') ?? (Q.level === 'high' ? '4k' : '2k');
  const clouds = cloudsRes === 'none'
    ? Promise.resolve()
    : new THREE.TextureLoader().loadAsync(`${ENV}clouds_${cloudsRes}.webp`).then((t) => {
      t.colorSpace = THREE.NoColorSpace;
      t.wrapS = THREE.RepeatWrapping;
      t.generateMipmaps = false; // (a seam where the panorama's ends meet otherwise)
      t.minFilter = THREE.LinearFilter;
      CLOUDS.map.value = t;
      CLOUDS.on.value = 1;
    }).catch((e) => console.warn('clouds', e));
  const ready = after
    .then(() => Promise.all([sky('1k'), clouds]))
    .then(([t]) => {
      const e = neutral(t);
      scene.environment = pmrem.fromEquirectangular(e).texture;
      e.dispose();
      t.dispose();
      // the glass reflects the sky as drawn (the blue, the white clouds; on computers the whole scene
      // round it, src/reflections.js); the walls and the ground are lit by the neutral HDRI
      const skyScene = new THREE.Scene();
      skyScene.add(makeSky(sunDir));
      const cubeRT = new THREE.WebGLCubeRenderTarget(256, { type: THREE.HalfFloatType });
      const cubeCam = new THREE.CubeCamera(0.1, 2000, cubeRT);
      const tm = renderer.toneMapping;
      renderer.toneMapping = THREE.NoToneMapping;
      cubeCam.update(renderer, skyScene);
      renderer.toneMapping = tm;
      const skyEnv = pmrem.fromCubemap(cubeRT.texture).texture;
      cubeRT.dispose();
      scene.traverse((o) => {
        for (const m of [o.material].flat()) {
          if (m?.userData?.glass && !m.envMap) {
            m.envMap = skyEnv;
            m.needsUpdate = true;
          }
        }
      });
      // dark from now on, kept for the moonlit sky at night (src/night.js): the number of lights stays
      // the same, so no shader is rebuilt when the evening comes
      fill.intensity = 0;
      pmrem.dispose();
    })
    .catch((e) => console.warn('sky', e));

  // people: modelled ones on computers (a 1.7 MB model), the light figures on phones and as a fallback
  if (Q.level === 'high') {
    after.then(() => addRealPeople(scene, PEOPLE, toScene)).catch((e) => {
      console.warn('people', e);
      addPeople(scene, PEOPLE, toScene);
    });
  } else addPeople(scene, PEOPLE, toScene);
  const props = after.then(() => {
    // the complex's trees, then the city's (site metres for both: scene z = -north); in the city now
    // and then a tree in flower
    const kindOf = (i) => (i % 7 === 0 ? 'conifer' : i % 5 === 0 ? 'poplar' : i % 19 === 3 ? 'blossom' : i % 29 === 4 ? 'white' : 'broad');
    const around = cityTrees.map((t, i) => [t.x, -t.z, 0, t.h, t.h * 0.38, kindOf(i), 'city']);
    addTrees(scene, TREES.protos, TREES.list, [...TREES.placed, ...around], toScene);
    addCars(scene, CARS, toScene);
  });
  return { sun, fill, cityMat, cityLights, skyLight, cloudTint: CLOUDS.tint.value, ready: Promise.all([ready, props]) };
}
