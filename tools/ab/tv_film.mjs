// The TV film for the sales office: the exterior rendered frame by frame from the site's own scene
// (the browser's renderer, the site's materials and light), cameras from tools/ab/tv_shots.mjs.
// No interface, no sound. Frames as JPEG (quality 95) per shot; tools/ab/tv_cut.py puts them
// together (dissolves) and encodes the MP4s.
//   node tools/ab/tv_film.mjs OUTDIR [--variant day|daynight] [--w 3840 --h 2160] [--only s1_wide,...]
//        [--every 10] [--signs neutral|brands] [--samples 4]
// Film quality (23.10.2026): each frame is the average of --samples renders, the camera moved by a
// fraction of a pixel and the sun by a fraction of its own width between them: smooth edges, no
// shimmer in the windows as the camera moves, the soft-edged shadows of a real sun.
// Moving: a few cars on the avenue (each laps exactly twice in 70 s), the trees in a breeze (periods
// dividing 70 s): the film loops without a jump. The day-to-night version runs 15:30 -> 22:20.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import { FPS, hourAt, timeline } from './tv_shots.mjs';

const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const out = args[0];
const variant = opt('--variant', 'day');
const W = +opt('--w', 3840), H = +opt('--h', 2160);
const only = opt('--only', '').split(',').filter(Boolean);
const every = +opt('--every', 1);
const signs = opt('--signs', 'neutral');
const samples = +opt('--samples', 4);
const { shots, length } = timeline();

const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
await page.goto(`http://localhost:5191/?still&quality=high&clouds=8k&signs=${signs}`); // the sharpest clouds
// everything in: the model, the hour, the signs, the high quality (grass, reflections, the ground's shade)
await page.waitForFunction(() => window.__app?.building && window.__app.daytime && window.__app.scene.getObjectByName('signs') && window.__app.hqDone, null, { timeout: 240000 });
await page.waitForTimeout(4000);
await page.evaluate(() => {
  const app = window.__app, { THREE } = app;
  document.body.classList.add('clean');
  for (const s of ['#eye', '#toast', '#fade', '#loading']) document.querySelector(s).style.display = 'none';
  app.renderer.setAnimationLoop(null);
  app.controls.enabled = false;
  // the avenue south of blocks Б and В (site metres): straight, its centre 36 m off Б's shop front;
  // eastbound in the far lane, westbound in the near one, 12.57 m/s (two laps of 440 m in 70 s)
  const m = [-29.5, -50.8], d = [0.9958, -0.092], n = [-0.092, -0.9958], v = 880 / 70;
  const car = (type, color, s0, east) => ({
    type, color,
    at: (t) => {
      let s = ((s0 + (east ? v : -v) * t + 220) % 440 + 440) % 440 - 220;
      const off = east ? 39.6 : 32.4;
      return { x: m[0] + d[0] * s + n[0] * off, y: m[1] + d[1] * s + n[1] * off, r: Math.atan2(d[1], d[0]) + (east ? 0 : Math.PI) };
    },
  });
  app.film.setDrivers([
    car('saloon', 0xe8e9eb, -150, true), car('suv', 0x24272c, 20, true), car('hatch', 0x8f1f22, 160, true),
    car('suv', 0xc4c7cb, 110, false), car('saloon', 0x1c2638, -40, false), car('hatch', 0xf2efe8, -180, false),
  ]);
  app.film.WIND.amp.value = 0.18;
  const sun = app.world.sun;
  window.__film = { home: { target: sun.target.position.clone(), cam: [...['left', 'right', 'top', 'bottom', 'near', 'far'].map((k) => sun.shadow.camera[k])] } };
  // the frame's samples, summed (8-bit renders, a float sum: no banding in the sky)
  const gl = app.renderer.getContext();
  const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
  const out = document.createElement('canvas');
  out.width = w;
  out.height = h;
  Object.assign(window.__film, { gl, w, h, px: new Uint8Array(w * h * 4), sum: new Float32Array(w * h * 4), out, ctx: out.getContext('2d') });
});

const ease = (u) => 0.5 - 0.5 * Math.cos(Math.PI * u);
const lerp3 = (a, b, k) => a.map((v, i) => v + (b[i] - v) * k);
function cameraAt(s, u) {
  const k = ease(u);
  let pos;
  if (s.orbit) {
    const o = s.orbit, a = ((o.from + (o.to - o.from) * k) * Math.PI) / 180;
    const R = o.radius[0] + (o.radius[1] - o.radius[0]) * k, h = o.height[0] + (o.height[1] - o.height[0]) * k;
    pos = [o.centre[0] + R * Math.cos(a), h, o.centre[2] + R * Math.sin(a)];
  } else pos = lerp3(s.pos[0], s.pos[1], k);
  return { pos, look: lerp3(s.look[0], s.look[1], k) };
}

let n = 0;
const t0 = Date.now();
for (const s of shots) {
  if (only.length && !only.includes(s.name)) continue;
  const dir = `${out}/${s.name}`;
  fs.mkdirSync(dir, { recursive: true });
  const frames = Math.round(s.dur * FPS);
  for (let f = 0; f < frames; f += every) {
    // (a frame already there is kept: a render broken off goes on where it stopped)
    if (fs.existsSync(`${dir}/f_${String(f).padStart(4, '0')}.jpg`)) continue;
    const T = s.start + f / FPS;
    const cam = cameraAt(s, f / (frames - 1));
    const b64 = await page.evaluate(async ({ cam, fov, shadow, focus, T, hour, length, samples }) => {
      const app = window.__app, sun = app.world.sun, sc = sun.shadow.camera, F = window.__film;
      if (hour !== null) app.setHours(hour);
      // the sun's shadow: the whole complex for the wide views, 140 m round the subject up close
      const d = sun.position.clone().sub(sun.target.position).normalize();
      if (shadow === 'close') {
        sun.target.position.set(focus[0], 0, focus[2]);
        [sc.left, sc.right, sc.top, sc.bottom, sc.near, sc.far] = [-70, 70, 70, -70, 200, 1100];
      } else {
        sun.target.position.copy(F.home.target);
        [sc.left, sc.right, sc.top, sc.bottom, sc.near, sc.far] = F.home.cam;
      }
      sun.target.updateMatrixWorld();
      sc.updateProjectionMatrix();
      // upright verticals, as an architectural camera's shift lens: the camera held level, the
      // frame slid up or down until what it looks at sits in the middle
      const c = app.camera;
      c.fov = fov;
      c.near = 0.3;
      c.position.set(...cam.pos);
      const [dx, dy, dz] = cam.look.map((v, i) => v - cam.pos[i]);
      const pitch = Math.atan2(dy, Math.hypot(dx, dz));
      c.lookAt(cam.pos[0] + dx, cam.pos[1], cam.pos[2] + dz);
      const W = app.renderer.domElement.width, H = app.renderer.domElement.height;
      const shift = (Math.tan(pitch) / Math.tan((fov * Math.PI) / 360)) * (H / 2);
      app.film.WIND.t.value = T;
      app.film.driveCars(T % length);
      app.film.updateCars(c);
      app.grass?.update(c);
      // the samples: sub-pixel offsets of the camera (Halton 2, 3) and points over the sun's disc
      // (0.27 degrees across: the penumbra of a real sun)
      const halton = (i, b) => { let f = 1, r = 0; for (; i > 0; i = Math.floor(i / b)) { f /= b; r += f * (i % b); } return r; };
      const u = new app.THREE.Vector3(0, 1, 0).cross(d).normalize(), v = d.clone().cross(u).normalize();
      const { gl, w, h, px, sum } = F;
      sum.fill(0);
      for (let k = 0; k < samples; k++) {
        const jx = samples > 1 ? halton(k + 1, 2) - 0.5 : 0, jy = samples > 1 ? halton(k + 1, 3) - 0.5 : 0;
        c.setViewOffset(W, H, jx, -shift + jy, W, H);
        c.updateProjectionMatrix();
        const a = (k / samples) * Math.PI * 2 + 0.4, r = samples > 1 ? 0.0024 * Math.sqrt((k + 0.5) / samples) : 0;
        const dd = d.clone().addScaledVector(u, Math.cos(a) * r).addScaledVector(v, Math.sin(a) * r).normalize();
        sun.position.copy(sun.target.position).addScaledVector(dd, 600);
        app.renderer.shadowMap.needsUpdate = true;
        app.pipeline.render(1 / 30);
        gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
        for (let i = 0; i < px.length; i++) sum[i] += px[i];
      }
      sun.position.copy(sun.target.position).addScaledVector(d, 600);
      // the average, the rows turned top-down (GL reads bottom-up)
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
    }, { cam, fov: s.fov, shadow: s.shadow, focus: s.focus ?? [0, 0, 0], T, hour: variant === 'daynight' ? hourAt(T, length) : null, length, samples });
    fs.writeFileSync(`${dir}/f_${String(f).padStart(4, '0')}.jpg`, Buffer.from(b64, 'base64'));
    n++;
  }
  console.log(s.name, 'done', `${Math.round((Date.now() - t0) / 1000)} s`);
}
fs.writeFileSync(`${out}/film.json`, JSON.stringify({ variant, W, H, FPS, length, every, signs, samples, shots: shots.map(({ name, start, dur }) => ({ name, start, dur })) }, null, 1));
console.log(JSON.stringify({ frames: n, seconds: Math.round((Date.now() - t0) / 1000), errors }));
await browser.close();
