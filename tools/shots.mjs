// Screenshots from fixed cameras (tools/views.mjs).
//
//   npx vite --port 5173 &            (or any running copy of the site)
//   node tools/shots.mjs build/shots [--url http://localhost:5191/] [--only aerial,garden] [--size 1600x1000]
//
// Uses the installed Google Chrome (playwright-core drives it; nothing else is downloaded).
import { chromium } from 'playwright-core';
import { mkdirSync, writeFileSync } from 'node:fs';
import { HOME, VIEWS } from './views.mjs';

const args = process.argv.slice(2);
const out = args.find((a) => !a.startsWith('--') && !args[args.indexOf(a) - 1]?.startsWith('--')) ?? 'build/shots';
const opt = (k, d) => (args.includes(`--${k}`) ? args[args.indexOf(`--${k}`) + 1] : d);
const url = opt('url', 'http://localhost:5191/');
const only = opt('only', '')?.split(',').filter(Boolean);
const [W, H] = opt('size', '1600x1000').split('x').map(Number);
const query = opt('query', '');

mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true,
  args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('console', (m) => m.type() === 'error' && console.log('console:', m.text()));
const t0 = Date.now();
await page.goto(`${url}?still${query ? `&${query}` : ''}`);
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
const loadMs = Date.now() - t0;
const gpu = await page.evaluate(() => {
  const gl = window.__app.renderer.getContext();
  const ext = gl.getExtension('WEBGL_debug_renderer_info');
  return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown';
});
console.log(`loaded in ${loadMs} ms on ${gpu}`);
// let textures and shaders settle
await page.waitForTimeout(2500);

const log = { loadMs, gpu, size: `${W}x${H}`, shots: [] };
for (const [name, v] of Object.entries(VIEWS)) {
  if (only.length && !only.includes(name)) continue;
  await page.evaluate(async (v) => {
    const app = window.__app;
    for (const id of ['ext-ui', 'labels', 'places', 'tooltip', 'quality', 'daytime', 'eye', 'hint']) {
      const el = document.getElementById(id);
      if (el) el.style.visibility = v.ui ? '' : 'hidden';
    }
    if (v.from) app.setView(v.from.pos, v.from.target);
    if (v.floor) {
      if (app.state.mode === 'walk') app.exitWalk();
      app.selectFloor(v.floor[0], v.floor[1]);
      if (v.apt != null) app.selectApt(app.apartments.find((a) => a.id === v.apt));
      await new Promise((r) => setTimeout(r, 1600));
    } else if (v.walk) {
      app.selectApt(app.apartments.find((a) => a.id === v.walk));
      app.enterWalk(app.apartments.find((a) => a.id === v.walk));
      await new Promise((r) => setTimeout(r, 900));
      if (v.yaw != null) app.walk.yaw = v.yaw;
      if (v.at) app.walk.pos.set(v.at[0], v.at[1]);
      if (v.pitch != null) app.walk.pitch = v.pitch;
    } else if (app.state.mode !== 'overview') {
      if (app.state.mode === 'walk') app.exitWalk();
      await new Promise((r) => setTimeout(r, 600));
      app.goOverview();
      await new Promise((r) => setTimeout(r, 1500));
    }
    if (v.pos) app.setView(v.pos, v.target);
    // a client render's camera (tools/ab/calib.py): level, with the shift of a 2-point perspective
    // and the render's focal length, on a frame of the render's proportions
    const cam = app.camera;
    if (v.cam) {
      const { pos, yaw, f, v0, size } = v.cam;
      const k = innerWidth / size[0]; // the render's pixels in this frame
      const a = (yaw * Math.PI) / 180;
      app.controls.maxPolarAngle = Math.PI / 2 + 0.01; // level view (the site's own limit stops short of it)
      app.setView(pos, [pos[0] + Math.sin(a) * 100, pos[1], pos[2] - Math.cos(a) * 100]);
      const H = innerHeight, F = f * k, V0 = v0 * k;
      const full = 2 * Math.max(V0, H - V0);
      cam.fov = (2 * Math.atan(full / 2 / F) * 180) / Math.PI;
      cam.aspect = innerWidth / full; // the full (shifted) frame's proportions: square pixels
      cam.setViewOffset(innerWidth, full, 0, full / 2 - V0, innerWidth, H);
      cam.updateProjectionMatrix();
      app.controls.update?.();
    } else if (cam.view?.enabled) {
      cam.clearViewOffset();
      cam.aspect = innerWidth / innerHeight;
      cam.fov = 38;
      cam.updateProjectionMatrix();
    }
    // a building that stands in front of the one compared (the renders are composed per building)
    if (v.hideTower) app.building.showUpTo(v.hideTower, 0);
    // the city round the site off (it stands where the cameras of the marketing renders stood)
    for (const o of app.scene.children) if (o.name === 'city' || o.name?.startsWith('trees')) o.visible = !v.noCity || (o.name.startsWith('trees') && !v.noCity);
  }, v);
  await page.waitForTimeout(v.wait ?? 1200);
  const file = `${out}/${name}.png`;
  await page.screenshot({ path: file });
  log.shots.push(name);
  console.log('wrote', file);
}
// frame time at the aerial view, 3 s of rendering
await page.evaluate(() => window.__app.goOverview?.());
await page.waitForTimeout(1500);
const perf = await page.evaluate(
  (home) =>
    new Promise((resolve) => {
      const app = window.__app;
      app.setView(home.pos, home.target);
      const times = [];
      let last = performance.now();
      const t1 = last + 3000;
      const tick = () => {
        const now = performance.now();
        times.push(now - last);
        last = now;
        if (now < t1) requestAnimationFrame(tick);
        else {
          times.sort((a, b) => a - b);
          const info = app.renderer.info;
          resolve({
            fps: Math.round((1000 * times.length) / times.reduce((s, x) => s + x, 0)),
            p95ms: +times[Math.floor(times.length * 0.95)].toFixed(1),
            calls: info.render.calls,
            triangles: info.render.triangles,
            textures: info.memory.textures,
            geometries: info.memory.geometries,
          });
        }
      };
      requestAnimationFrame(tick);
    }),
  HOME,
);
log.perf = perf;
console.log(perf);
writeFileSync(`${out}/log.json`, JSON.stringify(log, null, 2));
await browser.close();
