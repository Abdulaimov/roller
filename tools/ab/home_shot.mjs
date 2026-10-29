import { chromium } from 'playwright-core';
import CHROME from './chrome.mjs';
const [out, w, h] = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: +(w || 1440), height: +(h || 900) } });
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto('http://localhost:5197/?still');
await page.waitForFunction(() => window.__app?.building, null, { timeout: 120000 });
await page.waitForTimeout(3500);
await page.screenshot({ path: out });
console.log('wrote', out);
await browser.close();
