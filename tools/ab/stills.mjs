// High-quality stills from the site's scene (as tools/ab/tv_film.mjs renders a film frame: the camera
// held level with a shift lens, several samples averaged), for start frames of generated video and the
// like. The dev server on :5191 must be running.
//   node tools/ab/stills.mjs OUTDIR views.json [--w 1920 --h 1080] [--samples 6] [--signs brands]
// views.json: { "name": { "from": [x, y, z], "to": [x, y, z], "fov": 40, "hour": 15 }, ... }
// in site metres (x east, y north, z up); fov in degrees (vertical).
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const [out, viewsFile] = args;
const W = +opt('--w', 1920), H = +opt('--h', 1080), samples = +opt('--samples', 6);
const views = JSON.parse(fs.readFileSync(viewsFile, 'utf8'));
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
await page.goto(`http://localhost:5191/?still&quality=high&clouds=8k&signs=${opt('--signs', 'brands')}`);
await page.waitForFunction(() => window.__app?.building && window.__app.daytime && window.__app.scene.getObjectByName('signs') && window.__app.hqDone, null, { timeout: 240000 });
await page.waitForTimeout(4000);
await page.evaluate(() => {
  const app = window.__app;
  document.body.classList.add('clean');
  for (const s of ['#eye', '#toast', '#fade', '#loading']) document.querySelector(s).style.display = 'none';
  app.renderer.setAnimationLoop(null);
  app.controls.enabled = false;
  const gl = app.renderer.getContext();
  const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
  const out = document.createElement('canvas');
  out.width = w;
  out.height = h;
  window.__still = { gl, w, h, px: new Uint8Array(w * h * 4), sum: new Float32Array(w * h * 4), out, ctx: out.getContext('2d') };
});

for (const [name, v] of Object.entries(views)) {
  const b64 = await page.evaluate(async ({ v, samples }) => {
    const app = window.__app, sun = app.world.sun, F = window.__still;
    const cfg = await import('/src/config.js');
    const a = cfg.toScene(v.from[0], v.from[1]), b = cfg.toScene(v.to[0], v.to[1]);
    const pos = [a.x, v.from[2], a.z], look = [b.x, v.to[2], b.z];
    app.setHours(v.hour ?? 15);
    // the sun's shadow over what the camera looks at
    const sc = sun.shadow.camera, d = sun.position.clone().sub(sun.target.position).normalize();
    sun.target.position.set(look[0], 0, look[2]);
    [sc.left, sc.right, sc.top, sc.bottom, sc.near, sc.far] = [-110, 110, 110, -110, 200, 1100];
    sun.target.updateMatrixWorld();
    sc.updateProjectionMatrix();
    const c = app.camera, fov = v.fov ?? 40;
    c.fov = fov;
    c.near = 0.3;
    c.position.set(...pos);
    const [dx, dy, dz] = look.map((q, i) => q - pos[i]);
    const pitch = Math.atan2(dy, Math.hypot(dx, dz));
    c.lookAt(pos[0] + dx, pos[1], pos[2] + dz);
    const Wd = app.renderer.domElement.width, Hd = app.renderer.domElement.height;
    const shift = (Math.tan(pitch) / Math.tan((fov * Math.PI) / 360)) * (Hd / 2);
    app.film.WIND.t.value = 3;
    app.film.updateCars(c);
    app.grass?.update(c);
    const halton = (i, bb) => { let f = 1, r = 0; for (; i > 0; i = Math.floor(i / bb)) { f /= bb; r += f * (i % bb); } return r; };
    const u = new app.THREE.Vector3(0, 1, 0).cross(d).normalize(), vv = d.clone().cross(u).normalize();
    const { gl, w, h, px, sum } = F;
    sum.fill(0);
    for (let k = 0; k < samples; k++) {
      const jx = samples > 1 ? halton(k + 1, 2) - 0.5 : 0, jy = samples > 1 ? halton(k + 1, 3) - 0.5 : 0;
      c.setViewOffset(Wd, Hd, jx, -shift + jy, Wd, Hd);
      c.updateProjectionMatrix();
      const ang = (k / samples) * Math.PI * 2 + 0.4, r = samples > 1 ? 0.0024 * Math.sqrt((k + 0.5) / samples) : 0;
      const dd = d.clone().addScaledVector(u, Math.cos(ang) * r).addScaledVector(vv, Math.sin(ang) * r).normalize();
      sun.position.copy(sun.target.position).addScaledVector(dd, 600);
      app.renderer.shadowMap.needsUpdate = true;
      app.pipeline.render(1 / 30);
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
      for (let i = 0; i < px.length; i++) sum[i] += px[i];
    }
    sun.position.copy(sun.target.position).addScaledVector(d, 600);
    const img = F.ctx.createImageData(w, h), o = img.data, row = w * 4, kk = 1 / samples;
    for (let y = 0; y < h; y++) {
      const s0 = (h - 1 - y) * row, o0 = y * row;
      for (let i = 0; i < row; i++) o[o0 + i] = sum[s0 + i] * kk + 0.5;
      for (let i = 3; i < row; i += 4) o[o0 + i] = 255;
    }
    F.ctx.putImageData(img, 0, 0);
    const blob = await new Promise((res) => F.out.toBlob(res, 'image/jpeg', 0.95));
    const buf = new Uint8Array(await blob.arrayBuffer());
    let str = '';
    for (let k = 0; k < buf.length; k += 0x8000) str += String.fromCharCode(...buf.subarray(k, k + 0x8000));
    return btoa(str);
  }, { v, samples });
  fs.writeFileSync(`${out}/${name}.jpg`, Buffer.from(b64, 'base64'));
  console.log('wrote', `${out}/${name}.jpg`);
}
if (errors.length) console.log('errors:', errors);
await browser.close();
