// Where every pixel of a view lands on the buildings: the complex is drawn from one of the client
// renders' cameras (tools/views.mjs `cam`) with a material that writes the scene position of the
// surface, and the result is saved as raw float32 (x, y, z, 1 where a building was hit) per pixel.
// With it a render can be unwrapped onto the model's facades (tools/ab/unwrap.py).
//
//   node tools/ab/posmap.mjs VIEW OUT.f32 [--url http://localhost:5191/]
import { chromium } from 'playwright-core';
import { writeFileSync } from 'node:fs';
import { VIEWS } from '../views.mjs';

const [name, out] = process.argv.slice(2);
const args = process.argv.slice(2);
const url = args.includes('--url') ? args[args.indexOf('--url') + 1] : 'http://localhost:5191/';
const v = VIEWS[name];
if (!v?.cam) throw new Error(`view ${name} has no render camera`);
const [W, H] = v.cam.size;
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true,
  args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto(`${url}?still`);
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1500);
const data = await page.evaluate((cam) => {
  const app = window.__app;
  const { THREE, scene, camera, renderer } = app;
  const { pos, yaw, f, v0, size } = cam;
  const a = (yaw * Math.PI) / 180;
  app.controls.maxPolarAngle = Math.PI / 2 + 0.01;
  app.setView(pos, [pos[0] + Math.sin(a) * 100, pos[1], pos[2] - Math.cos(a) * 100]);
  const [w, h] = size;
  const full = 2 * Math.max(v0, h - v0);
  camera.fov = (2 * Math.atan(full / 2 / f) * 180) / Math.PI;
  camera.aspect = w / full;
  camera.setViewOffset(w, full, 0, full / 2 - v0, w, h);
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
  // only the model's opaque surfaces (no city, trees, cars, people, glass rails, mesh screens)
  const keep = new Set();
  app.building.group.traverse((o) => keep.add(o));
  const hidden = [];
  scene.traverse((o) => {
    if (!o.isMesh && !o.isLine && !o.isPoints && !o.isSprite) return;
    const mats = [o.material].flat();
    const clear = mats.some((m) => m?.transparent);
    if (!keep.has(o) || clear || o.userData.pick) {
      if (o.visible) hidden.push(o);
      o.visible = false;
    }
  });
  const mat = new THREE.ShaderMaterial({
    vertexShader: `
      varying vec3 vPos;
      void main() {
        vec4 p = vec4(position, 1.0);
        #ifdef USE_INSTANCING
          p = instanceMatrix * p;
        #endif
        vec4 wp = modelMatrix * p;
        vPos = wp.xyz;
        gl_Position = projectionMatrix * viewMatrix * wp;
      }`,
    fragmentShader: `
      varying vec3 vPos;
      void main() { gl_FragColor = vec4(vPos, 1.0); }`,
    side: THREE.DoubleSide,
  });
  const rt = new THREE.WebGLRenderTarget(w, h, { type: THREE.FloatType, format: THREE.RGBAFormat, depthBuffer: true });
  const bg = scene.background, env = scene.fog;
  scene.background = null;
  scene.fog = null;
  scene.overrideMaterial = mat;
  renderer.setRenderTarget(rt);
  renderer.setClearColor(0x000000, 0);
  renderer.clear();
  renderer.render(scene, camera);
  const px = new Float32Array(w * h * 4);
  renderer.readRenderTargetPixels(rt, 0, 0, w, h, px);
  renderer.setRenderTarget(null);
  scene.overrideMaterial = null;
  scene.background = bg;
  scene.fog = env;
  for (const o of hidden) o.visible = true;
  // flip to top-down rows, as the image
  const outp = new Float32Array(w * h * 4);
  for (let y = 0; y < h; y++) outp.set(px.subarray((h - 1 - y) * w * 4, (h - y) * w * 4), y * w * 4);
  let s = '';
  const bytes = new Uint8Array(outp.buffer);
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}, v.cam);
writeFileSync(out, Buffer.from(data, 'base64'));
console.log('wrote', out, `${W}x${H}x4 float32`);
await browser.close();
