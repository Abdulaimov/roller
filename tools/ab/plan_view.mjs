// A flat seen straight from above in the floor view (furnished as for the walk), and where three
// plan points land in the picture, so the shot can be put into plan orientation and laid over the
// architect's sheet (tools/ab/match_sheet.py).
//   node tools/ab/plan_view.mjs APT_ID OUT.png [--walk]
//   node tools/ab/plan_view.mjs --all OUTDIR      # one flat of every layout: OUTDIR/<id>.png
import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync } from 'node:fs';

const all = process.argv.includes('--all');
const [id0, out0] = all ? [null, process.argv[process.argv.indexOf('--all') + 1]] : process.argv.slice(2);
const walk = process.argv.includes('--walk');
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 1000, height: 1000 } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1500);
const jobs = [];
if (all) {
  mkdirSync(out0, { recursive: true });
  const ids = await page.evaluate(() => {
    const seen = new Map();
    for (const a of window.__app.apartments) {
      const k = `${a.plan}:${a.data.outline[0].join(',')}`;
      if (!seen.has(k)) seen.set(k, a.id);
    }
    return [...seen.values()];
  });
  for (const id of ids) jobs.push([id, `${out0}/${id}.png`]);
} else jobs.push([id0, out0]);
for (const [id, out] of jobs) {
const info = await page.evaluate(async ([id, walk]) => {
  const app = window.__app;
  for (const elId of ['ext-ui', 'labels', 'places', 'tooltip', 'quality']) {
    const el = document.getElementById(elId);
    if (el) el.style.visibility = 'hidden';
  }
  const a = app.apartments.find((x) => x.id === id);
  app.selectFloor(a.tower, a.floor);
  await new Promise((r) => setTimeout(r, 1200));
  if (walk) {
    // the walk-through's furnishing (the flat's own fit-out), seen from above with the ceiling off
    app.selectApt(a);
    await new Promise((r) => setTimeout(r, 600));
  }
  const { THREE } = app;
  const cfg = await import('/src/config.js');
  const tower = cfg.towerByKey[a.tower];
  const { toScene } = cfg.planFrame(tower);
  // straight down from high up with a narrow lens: nearly a plan, the walls hardly lean
  const baseY = tower.floors.find((f) => f.floor === a.floor).z + tower.slab;
  const xs = a.data.outline.map((p) => p[0]), ys = a.data.outline.map((p) => p[1]);
  const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
  const mid = toScene((Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2);
  const cam = app.camera;
  cam.fov = 14;
  cam.updateProjectionMatrix();
  const h = span * 1.2 / (2 * Math.tan((cam.fov * Math.PI) / 360));
  app.setView([mid.x + 0.001, baseY + h, mid.z + 0.001], [mid.x, baseY, mid.z]);
  await new Promise((r) => setTimeout(r, 900));
  cam.fov = 14;
  cam.updateProjectionMatrix();
  await new Promise((r) => setTimeout(r, 300));
  // (no highlight over the flat: the furniture and the doors as they are)
  for (const u of app.building.units.values()) for (const o of [u.overlay, u.ring, u.edges]) if (o) o.visible = false;
  await new Promise((r) => setTimeout(r, 200));
  // plan points -> screen, at the height of the furniture
  cam.updateMatrixWorld(true);
  const pr = (x, y) => {
    const s = toScene(x, y);
    const v = new THREE.Vector3(s.x, baseY + 0.45, s.z).project(cam);
    return [((v.x + 1) / 2) * innerWidth, ((1 - v.y) / 2) * innerHeight];
  };
  const x0 = Math.min(...xs), y0 = Math.min(...ys);
  return { pts: [[x0, y0], [x0 + 5, y0], [x0, y0 + 5]].map(([x, y]) => ({ plan: [x, y], px: pr(x, y) })), outline: a.data.outline, plan: a.plan };
}, [id, walk]);
await page.screenshot({ path: out });
writeFileSync(out.replace('.png', '.json'), JSON.stringify(info));
console.log('wrote', out);
}
await browser.close();
