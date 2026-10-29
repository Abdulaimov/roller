// The model shot with the camera of a client render (tools/rp/cameras.json, fitted by
// tools/rp/calib.py): the same position, heading, pitch and focal length, on a frame of the
// render's proportions, the panels hidden - to put next to the render.
//   node tools/rp/match_shot.mjs NAME OUT.png [--hour H] [--url URL] [--w 1600]
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import CHROME from '../ab/chrome.mjs';

const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const [name, out] = args;
const cam = JSON.parse(fs.readFileSync(new URL('./cameras.json', import.meta.url)))[name];
if (!cam) throw new Error(`no camera ${name} in tools/rp/cameras.json`);
const W = +opt('--w', 1600), H = Math.round((W * cam.size[1]) / cam.size[0]);
const browser = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto(opt('--url', 'http://localhost:5197/?still'));
await page.waitForFunction(() => window.__app?.building && window.__app.daytime, null, { timeout: 180000 });
await page.waitForTimeout(2000);
await page.evaluate(async ([cam, hour]) => {
  const app = window.__app;
  for (const id of ['ext-ui', 'labels', 'places', 'tooltip', 'quality', 'hint', 'daytime', 'eye']) {
    const el = document.getElementById(id);
    if (el) el.style.visibility = 'hidden';
  }
  if (hour) app.setHours(hour);
  const c = app.camera;
  const k = innerWidth / cam.size[0]; // the render's pixels in this frame
  const F = cam.f * k;
  app.controls.minPolarAngle = 0;
  app.controls.maxPolarAngle = Math.PI;
  app.controls.minDistance = 0;
  app.controls.maxDistance = Infinity;
  app.setView(cam.pos, cam.target);
  if (cam.model === 'look') {
    // (a camera set by hand: tools/rp/look_cam.py)
    c.clearViewOffset();
    c.fov = cam.fov;
    c.aspect = innerWidth / innerHeight;
  } else if (cam.model === 'level') {
    // level, the frame shifted: the horizon at row v0 (a 2-point perspective)
    const V0 = cam.v0 * k, full = 2 * Math.max(V0, innerHeight - V0);
    c.fov = (2 * Math.atan(full / 2 / F) * 180) / Math.PI;
    c.aspect = innerWidth / full;
    c.setViewOffset(innerWidth, full, 0, full / 2 - V0, innerWidth, innerHeight);
  } else {
    c.clearViewOffset();
    c.fov = (2 * Math.atan(innerHeight / 2 / F) * 180) / Math.PI;
    c.aspect = innerWidth / innerHeight;
  }
  c.updateProjectionMatrix();
  c.position.set(...cam.pos);
  c.lookAt(...cam.target);
  app.controls.target.set(...cam.target);
  await new Promise((r) => setTimeout(r, 3500));
}, [cam, +opt('--hour', cam.time ?? 0)]);
await page.screenshot({ path: out });
console.log('wrote', out, `${W}x${H}`);
await browser.close();
