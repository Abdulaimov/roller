// Load time and frame rate in Chrome, for the report.
//
//   npm run build && npx vite preview --port 4173 &
//   node tools/perf.mjs [--url http://localhost:4173/] [--out docs/compare/perf.json]
//
// Profiles: computer (1600x1000, high), computer light mode (?quality=low), and a phone screen
// emulated on the same machine (390x844 at 3x, touch: the site picks the light mode itself).
// Each runs twice: unthrottled (local files) and over an emulated 4G line (9 Mbit/s, 60 ms), cache off.
// Frame rate is measured on this computer's GPU: the phone profile shows the light mode's load on the
// GPU and the layout, not how fast a real phone renders it.
import { chromium } from 'playwright-core';
import { HOME } from './views.mjs';
import { writeFileSync } from 'node:fs';

const args = process.argv.slice(2);
const opt = (k, d) => (args.includes(`--${k}`) ? args[args.indexOf(`--${k}`) + 1] : d);
const url = opt('url', 'http://localhost:4173/');
const out = opt('out', 'build/perf.json');

const PROFILES = {
  computer: { viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1, query: '' },
  'computer, light mode': { viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1, query: 'quality=low' },
  'phone (emulated)': { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true, query: '' },
};
const NETS = { local: null, '4G': { offline: false, latency: 60, downloadThroughput: (9e6 / 8), uploadThroughput: (3e6 / 8) } };

const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true,
  args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const gpuName = { value: '' };
const results = [];
for (const [pname, p] of Object.entries(PROFILES)) {
  for (const [nname, net] of Object.entries(NETS)) {
    const ctx = await browser.newContext({ viewport: p.viewport, deviceScaleFactor: p.deviceScaleFactor, isMobile: p.isMobile, hasTouch: p.hasTouch });
    const page = await ctx.newPage();
    const cdp = await ctx.newCDPSession(page);
    await cdp.send('Network.enable');
    await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });
    if (net) await cdp.send('Network.emulateNetworkConditions', net);
    let bytes = 0;
    cdp.on('Network.loadingFinished', (e) => (bytes += e.encodedDataLength));
    const t0 = Date.now();
    await page.goto(`${url}?still${p.query ? `&${p.query}` : ''}`);
    await page.waitForFunction(() => window.__app?.building, null, { timeout: 300000 });
    const tModel = Date.now() - t0;
    // everything the first view needs: model textures, sky, trees, cars
    // (the version before this work has no texture / sky promises: nothing extra to wait for)
    await page.evaluate(() => Promise.all([window.__app.building.texturesReady, window.__app.world?.ready, window.__app.pipeline?.ready]));
    await page.waitForLoadState('networkidle');
    const tAll = Date.now() - t0;
    const info = await page.evaluate(async (HOME) => {
      const app = window.__app;
      const gl = app.renderer.getContext();
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      const measure = async (pos, target) => {
        app.setView(pos, target);
        await new Promise((r) => setTimeout(r, 800));
        return new Promise((resolve) => {
          const times = [];
          let last = performance.now();
          const end = last + 4000;
          const tick = () => {
            const now = performance.now();
            times.push(now - last);
            last = now;
            if (now < end) requestAnimationFrame(tick);
            else {
              times.sort((a, b) => a - b);
              const i = app.renderer.info;
              resolve({
                fps: Math.round((1000 * times.length) / times.reduce((s, x) => s + x, 0)),
                p95_ms: +times[Math.floor(times.length * 0.95)].toFixed(1),
                draw_calls: i.render.calls,
                triangles: i.render.triangles,
              });
            }
          };
          requestAnimationFrame(tick);
        });
      };
      const aerial = await measure(HOME.pos, HOME.target);
      const street = await measure([62, 1.7, 112], [25, 12, 40]);
      return {
        gpu: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown',
        quality: app.quality?.level ?? 'one level',
        pixelRatio: app.renderer.getPixelRatio(),
        canvas: [app.renderer.domElement.width, app.renderer.domElement.height],
        textures: app.renderer.info.memory.textures,
        geometries: app.renderer.info.memory.geometries,
        aerial,
        street,
      };
    }, HOME);
    gpuName.value = info.gpu;
    const r = { profile: pname, network: nname, model_ready_s: +(tModel / 1000).toFixed(2), all_loaded_s: +(tAll / 1000).toFixed(2), transferred_MB: +(bytes / 1e6).toFixed(1), ...info };
    results.push(r);
    console.log(JSON.stringify(r));
    await ctx.close();
  }
}
writeFileSync(out, JSON.stringify({ date: new Date().toISOString(), url, machine: 'MacBook Pro, Apple M5 Pro, 24 GB, macOS (headless Chrome, Metal)', results }, null, 2));
await browser.close();
