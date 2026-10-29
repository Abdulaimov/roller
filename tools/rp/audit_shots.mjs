// The audit's fixed views of the complex, shot the same way before and after a change: the
// cameras of the client's renders (tools/rp/cameras.json), every side of each block on its own,
// the site from above and from eye height. One browser, one page load.
//   node tools/rp/audit_shots.mjs OUTDIR [NAME ...] [--url URL]
// Views: render1..render8 (as cameras.json has them), elev_<block>_<side> (side: px, mx, py, my -
// the sheets' +x towards кӯчаи Ҳусейнзода, +y towards кӯчаи Нарзиқулова), top_site, top_wide,
// eye_* (1.6 m up).
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import CHROME from '../ab/chrome.mjs';

const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const out = args[0];
const only = args.slice(1).filter((a, i, all) => !a.startsWith('--') && !(all[i - 1] ?? '').startsWith('--'));
fs.mkdirSync(out, { recursive: true });
const cams = JSON.parse(fs.readFileSync(new URL('./cameras.json', import.meta.url)));
const [CX, CY] = JSON.parse(fs.readFileSync(new URL('../../src/model/complex.json', import.meta.url))).site_centre;

// sheet metres -> scene (src/config.js: x east, y up, z south; the sheet turned -49.5 deg)
const A = (-49.5 * Math.PI) / 180;
const scene = ([x, y, z]) => {
  const sx = Math.cos(A) * x - Math.sin(A) * y, sy = Math.sin(A) * x + Math.cos(A) * y;
  return [sx - CX, z, -(sy - CY)];
};
const BLOCKS = { A: { c: [3.844, -30.809], h: 83, w: 32 }, B: { c: [0, 0], h: 70, w: 32 }, V: { c: [-44.508, 3.805], h: 90, w: 60 } };
const SIDES = { px: [1, 0], mx: [-1, 0], py: [0, 1], my: [0, -1] };
const views = {};
for (const [name, c] of Object.entries(cams)) views[name] = { cam: c, size: c.size, noContext: ['render1', 'render2', 'render3'].includes(name) };
for (const [k, b] of Object.entries(BLOCKS)) {
  for (const [s, [nx, ny]] of Object.entries(SIDES)) {
    // (the neighbourhood off, the other blocks left standing: a side that faces another block is
    // seen past it, as from the street)
    const D = 125, z = b.h * 0.62;
    views[`elev_${k}_${s}`] = {
      level: { pos: scene([b.c[0] + nx * D, b.c[1] + ny * D, z]), target: scene([b.c[0], b.c[1], b.h * 0.45]), fov: 2 * Math.atan((b.h / 2 + 16) / D) * 57.2958 },
      size: [1200, 900], noContext: true,
    };
  }
}
views.top_site = { top: { c: scene([-20, -30, 0]), span: 190 }, size: [1400, 1100] };
views.top_wide = { top: { c: scene([-30, -40, 0]), span: 420 }, size: [1400, 1100] };
views.eye_corner = { level: { pos: scene([46, 46, 1.6]), target: scene([5, 5, 1.6]), fov: 62 }, size: [1400, 900] };
views.eye_narz = { level: { pos: scene([-46, 52, 1.6]), target: scene([-46, 0, 1.6]), fov: 62 }, size: [1400, 900] };
views.eye_husz = { level: { pos: scene([48, -32, 1.6]), target: scene([0, -32, 1.6]), fov: 62 }, size: [1400, 900] };
views.eye_yard = { level: { pos: scene([-62, -55, 1.6]), target: scene([-20, -12, 1.6]), fov: 62 }, size: [1400, 900] };
views.eye_yard2 = { level: { pos: scene([-30, -48, 1.6]), target: scene([-60, -10, 1.6]), fov: 62 }, size: [1400, 900] };

const browser = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto(opt('--url', 'http://localhost:5197/?still'));
await page.waitForFunction(() => window.__app?.building && window.__app.daytime, null, { timeout: 180000 });
// (everything in: the textures, the sky in the glass - shots taken before it differ from run to run)
await page.waitForFunction(() => window.__app.hqDone, null, { timeout: 120000 }).catch(() => console.log('hq not done, going on'));
await page.waitForTimeout(4000);
for (const [name, v] of Object.entries(views)) {
  if (only.length && !only.some((o) => name === o || name.startsWith(o))) continue;
  const [W, H] = v.size;
  const w = 1400, h = Math.round((w * H) / W);
  await page.setViewportSize({ width: w, height: h });
  // (the viewer's own resize handler sets its camera's aspect and view offset: let it run first)
  await page.waitForTimeout(600);
  const setup = async ([v, name]) => {
    const app = window.__app, c = app.camera;
    for (const id of ['ext-ui', 'labels', 'places', 'tooltip', 'quality', 'hint', 'daytime', 'eye']) {
      const el = document.getElementById(id);
      if (el) el.style.visibility = 'hidden';
    }
    if (app.building.hideTowers) app.building.hideTowers(v.hide ?? []);
    else {
      // (an older build without it: the towers' meshes by name)
      // (only ever hiding: the viewer keeps meshes of its own hidden - the flats' outlines)
      const re = new RegExp(`^(floors )?(${(v.hide ?? []).join('|') || '#'})_`);
      app.building.group.traverse((o) => { if (o.isMesh && re.test(o.name)) o.visible = false; });
    }
    // (the renders 1-3 stand their camera on a boulevard the real street has houses on: the
    // neighbourhood off for them, the scheme's houses and the streets stay)
    app.scene.traverse((o) => {
      if (o.name === 'city') o.visible = !v.noCity && !v.noContext;
      if (/^Neighbours/.test(o.name)) o.visible = !v.noContext;
    });
    app.setHours(v.cam?.time ?? 15);
    Object.assign(app.controls, { minPolarAngle: 0, maxPolarAngle: Math.PI, minDistance: 0, maxDistance: Infinity });
    c.clearViewOffset();
    c.aspect = innerWidth / innerHeight;
    if (v.cam) {
      const cam = v.cam, k = innerWidth / cam.size[0];
      app.setView(cam.pos, cam.target);
      if (cam.model === 'look') c.fov = cam.fov;
      else if (cam.model === 'level') {
        const F = cam.f * k, V0 = cam.v0 * k, full = 2 * Math.max(V0, innerHeight - V0);
        c.fov = (2 * Math.atan(full / 2 / F) * 180) / Math.PI;
        c.aspect = innerWidth / full;
        c.setViewOffset(innerWidth, full, 0, full / 2 - V0, innerWidth, innerHeight);
      } else c.fov = (2 * Math.atan(innerHeight / 2 / (cam.f * k)) * 180) / Math.PI;
      c.position.set(...cam.pos);
      c.lookAt(...cam.target);
    } else if (v.level) {
      app.setView(v.level.pos, v.level.target);
      c.fov = v.level.fov;
    } else if (v.top) {
      const [x, , z] = v.top.c, H = (v.top.span / 2) / Math.tan((19 * Math.PI) / 180);
      app.setView([x, H, z + 0.01], [x, 0, z]);
      c.fov = 38;
    }
    c.updateProjectionMatrix();
  };
  await page.evaluate(setup, [v, name]);
  await page.waitForTimeout(2600);
  // (and once more right before the shot: nothing of the viewer's may have moved it meanwhile)
  await page.evaluate(setup, [v, name]);
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${out}/${name}.png` });
  console.log('wrote', `${out}/${name}.png`);
}
await browser.close();
