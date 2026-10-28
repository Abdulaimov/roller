// SVG logos -> PNG in their own colours on a transparent ground, for tools/ab/brand_signs.py.
//   node tools/ab/svg_raster.mjs tools/ab/brand_logos build/brand_png [height=600]
// Each SVG is drawn as an <img> (no scripts run) at the given height (no wider than 8000 px).
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const [src, out, height = '600'] = process.argv.slice(2);
const H = Number(height);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 8200, height: H + 40 } });
for (const f of fs.readdirSync(src).filter((n) => n.endsWith('.svg')).sort()) {
  const url = 'data:image/svg+xml;base64,' + fs.readFileSync(path.join(src, f)).toString('base64');
  await page.setContent(`<html><body style="margin:0;background:transparent">
    <img id="i" src="${url}" style="display:block;height:${H}px;max-width:8000px;object-fit:contain"></body></html>`);
  await page.waitForFunction(() => document.getElementById('i').complete);
  const img = await page.$('#i');
  await img.screenshot({ path: path.join(out, f.replace(/\.svg$/, '.png')), omitBackground: true });
}
console.log('rasterized', fs.readdirSync(out).length, 'logos ->', out);
await browser.close();
