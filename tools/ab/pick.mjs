// What is at a few pixels of a walk-through view (as tools/ab/looks.mjs sets it up): the piece's
// material, its colour and the plan point and height hit.
//   node tools/ab/pick.mjs APT_ID SX,SY,TX,TY,PITCH "x,y" ["x,y" ...]   (pixels of a 1200 x 800 view)
import { chromium } from 'playwright-core';
const [id, view, ...pix] = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 1200, height: 800 } });
await page.goto('http://localhost:5191/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(1200);
const r = await page.evaluate(async ([id, view, pix]) => {
  const app = window.__app;
  const a = app.apartments.find((x) => x.id === id);
  app.selectApt(a);
  app.enterWalk(a);
  await new Promise((r) => setTimeout(r, 1800));
  const [sx, sy, tx, ty, pitch] = view.split(',').map(Number);
  const it = app.interior;
  const s = it.frame.toScene(sx, sy), t = it.frame.toScene(tx, ty);
  app.walk.target = null;
  app.walk.pos.set(s.x, s.z);
  app.walk.yaw = Math.atan2(-(t.x - s.x), -(t.z - s.z));
  app.walk.pitch = pitch || 0;
  await new Promise((r) => setTimeout(r, 600));
  const { THREE, camera, scene } = app;
  camera.updateMatrixWorld();
  const ray = new THREE.Raycaster();
  return pix.map((p) => {
    const [x, y] = p.split(',').map(Number);
    ray.setFromCamera(new THREE.Vector2((x / innerWidth) * 2 - 1, -(y / innerHeight) * 2 + 1), camera);
    const hits = ray.intersectObjects(scene.children, true).filter((h) => h.object.visible && h.object.material && !h.object.isSprite).slice(0, 3);
    return { px: p, hits: hits.map((h) => {
      const m = [h.object.material].flat()[h.face?.materialIndex ?? 0] ?? [h.object.material].flat()[0];
      const q = it.frame.toPlan(h.point.x, h.point.z);
      return { obj: h.object.name || h.object.type, mat: m.name || m.type, color: m.color?.getHexString(), map: !!m.map, plan: [+q.x.toFixed(3), +q.y.toFixed(3)], h: +(h.point.y - it.baseY).toFixed(3), d: +h.distance.toFixed(2), inInterior: (() => { let o = h.object; while (o) { if (o === it.group) return true; o = o.parent; } return false; })() };
    }) };
  });
}, [id, view, pix]);
console.log(JSON.stringify(r, null, 1));
await browser.close();
