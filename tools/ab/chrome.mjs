// The Chrome the screenshot tools launch: what Playwright has in its cache now (the build number
// changes when Playwright is updated; the tools used to name one and broke when it was replaced).
// The tools run headless the old way, which newer Chrome builds dropped, so the headless shell
// (the old headless Chrome on its own) when it is there. CHROME in the environment wins.
import fs from 'node:fs';

const dir = `${process.env.HOME}/Library/Caches/ms-playwright`;
const newest = (re) => fs.readdirSync(dir).filter((d) => re.test(d)).sort((a, b) => b.split('-').pop() - a.split('-').pop())[0];
const shell = newest(/^chromium_headless_shell-\d+$/);
const full = newest(/^chromium-\d+$/);
export default process.env.CHROME ??
  (shell
    ? `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`
    : `${dir}/${full}/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`);
