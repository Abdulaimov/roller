// Procedural canvas textures for the interiors: oak floor, porcelain and marble, plaster, woven
// fabric, wood veneers, rugs, paintings and leaves. Drawn once per page, seeded so every visit looks
// the same. Sizes are given in metres per texture tile where the texture repeats.
import * as THREE from 'three';
import { Q } from '../quality.js';

const BIG = Q.level === 'high' ? 1024 : 512;

function seeded(seed) {
  return () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
}

function canvas(w, h = w) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return { c, g: c.getContext('2d') };
}

function tex(c, { srgb = true, repeat = true, aniso = 8 } = {}) {
  const t = new THREE.CanvasTexture(c);
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.anisotropy = aniso;
  return t;
}

// fine speckle over the whole canvas (breaks up flat colour)
function speckle(g, w, h, n, alpha, rnd, colors = ['#000', '#fff']) {
  for (let i = 0; i < n; i++) {
    g.globalAlpha = alpha * rnd();
    g.fillStyle = colors[i % colors.length];
    g.fillRect(rnd() * w, rnd() * h, 1 + rnd() * 1.5, 1 + rnd() * 1.5);
  }
  g.globalAlpha = 1;
}

// wood grain along x inside the rectangle: wavy fibres, a few darker growth rings
function grain(g, x, y, w, h, rnd, { hue = 32, sat = 34, light = 62, contrast = 1 } = {}) {
  g.save();
  g.beginPath();
  g.rect(x, y, w, h);
  g.clip();
  g.fillStyle = `hsl(${hue}, ${sat}%, ${light}%)`;
  g.fillRect(x, y, w, h);
  // broad tone bands
  for (let k = 0; k < 4; k++) {
    g.globalAlpha = 0.12 * contrast;
    g.fillStyle = rnd() < 0.5 ? `hsl(${hue - 4}, ${sat + 6}%, ${light - 12}%)` : `hsl(${hue + 3}, ${sat - 6}%, ${light + 8}%)`;
    const by = y + rnd() * h, bh = h * (0.15 + rnd() * 0.4);
    g.fillRect(x, by, w, bh);
  }
  // fibres
  const n = Math.round(h * 0.9);
  const phase = rnd() * 10, freq = 0.004 + rnd() * 0.01, amp = h * (0.05 + rnd() * 0.12);
  for (let i = 0; i < n; i++) {
    const fy = y + (i / n) * h + (rnd() - 0.5) * 2;
    const dark = rnd() < 0.62;
    g.globalAlpha = (dark ? 0.09 : 0.06) * contrast * (0.4 + rnd());
    g.strokeStyle = dark ? `hsl(${hue - 6}, ${sat + 10}%, ${light - 28}%)` : `hsl(${hue + 4}, ${sat}%, ${light + 14}%)`;
    g.lineWidth = 0.5 + rnd() * 1.2;
    g.beginPath();
    for (let sx = x - 4; sx <= x + w + 4; sx += 8) {
      const yy = fy + Math.sin(sx * freq + phase + i * 0.02) * amp * 0.3 + Math.sin(sx * freq * 3.1 + phase) * amp * 0.08;
      sx === x - 4 ? g.moveTo(sx, yy) : g.lineTo(sx, yy);
    }
    g.stroke();
  }
  // cathedral rings: nested arches here and there
  if (rnd() < 0.7) {
    const cx = x + w * (0.2 + rnd() * 0.6), cy = y + h * (0.3 + rnd() * 0.4);
    for (let r = 0; r < 7; r++) {
      g.globalAlpha = 0.07 * contrast;
      g.strokeStyle = `hsl(${hue - 6}, ${sat + 8}%, ${light - 24}%)`;
      g.lineWidth = 1;
      g.beginPath();
      g.ellipse(cx, cy, w * (0.06 + r * 0.035), h * (0.12 + r * 0.06), 0, 0, Math.PI * 2);
      g.stroke();
    }
  }
  // a small knot now and then
  if (rnd() < 0.25) {
    const kx = x + rnd() * w, ky = y + h * (0.25 + rnd() * 0.5);
    const grd = g.createRadialGradient(kx, ky, 0, kx, ky, h * 0.18);
    grd.addColorStop(0, `hsla(${hue - 8}, ${sat + 10}%, ${light - 35}%, 0.55)`);
    grd.addColorStop(1, `hsla(${hue}, ${sat}%, ${light}%, 0)`);
    g.globalAlpha = 1;
    g.fillStyle = grd;
    g.fillRect(kx - h, ky - h, 2 * h, 2 * h);
  }
  g.restore();
  g.globalAlpha = 1;
}

/** Oiled oak planks, 19 cm wide and 1.2-2.2 m long: { map, rough, bump, metres } */
export function oakFloor() {
  const S = BIG, rnd = seeded(11);
  const { c, g } = canvas(S);
  const r = canvas(S);
  const metres = 2.4, rows = 12, ph = S / rows; // 20 cm rows
  r.g.fillStyle = '#8a8a8a';
  r.g.fillRect(0, 0, S, S);
  for (let row = 0; row < rows; row++) {
    let x = -rnd() * S * 0.6;
    while (x < S) {
      const len = S * (0.5 + rnd() * 0.42);
      const tone = { hue: 31 + rnd() * 5, sat: 21 + rnd() * 9, light: 60 + rnd() * 9 };
      // the same plank again one tile left and right, so the texture wraps without a seam
      const seed = 1 + Math.floor(rnd() * 1e8);
      for (const off of [0, -S, S]) grain(g, x + off, row * ph, len, ph, seeded(seed), tone);
      // roughness: each plank a little different, joints rough
      const v = Math.floor(110 + rnd() * 40);
      r.g.fillStyle = `rgb(${v},${v},${v})`;
      for (const off of [0, -S, S]) r.g.fillRect(x + off, row * ph, len, ph);
      // end joint
      g.fillStyle = 'rgba(55, 35, 18, 0.55)';
      for (const off of [0, -S, S]) g.fillRect(x + off, row * ph, 1.5, ph);
      x += len;
    }
    // long joint with a micro bevel
    g.fillStyle = 'rgba(50, 32, 16, 0.6)';
    g.fillRect(0, row * ph, S, 1.5);
    g.fillStyle = 'rgba(255, 240, 220, 0.12)';
    g.fillRect(0, row * ph + 1.5, S, 1);
    r.g.fillStyle = '#e0e0e0';
    r.g.fillRect(0, row * ph, S, 2);
  }
  speckle(g, S, S, S * 6, 0.05, rnd, ['#3a2814', '#fff4e0']);
  return { map: tex(c), rough: tex(r.c, { srgb: false }), bump: tex(c, { srgb: false }), metres };
}

/** Wood veneer for furniture (no planks): walnut or light oak */
export function veneer(kind) {
  const S = BIG / 2, rnd = seeded(kind === 'walnut' ? 41 : 43);
  const { c, g } = canvas(S);
  const tone = kind === 'walnut' ? { hue: 24, sat: 32, light: 33, contrast: 1.3 } : { hue: 33, sat: 36, light: 66, contrast: 0.9 };
  const strips = 4;
  for (let k = 0; k < strips; k++) grain(g, 0, (k * S) / strips, S, S / strips, rnd, { ...tone, light: tone.light + (rnd() - 0.5) * 4 });
  return { map: tex(c), metres: 0.9 };
}

// soft marble veins: a few long wandering strokes, blurred, plus fine cracks
function veins(g, S, rnd, { color = '#8f8b86', n = 7, width = 6, alpha = 0.35 } = {}) {
  for (let pass = 0; pass < 2; pass++) {
    g.filter = pass ? 'blur(0.6px)' : `blur(${width * 0.6}px)`;
    for (let i = 0; i < n; i++) {
      g.globalAlpha = pass ? alpha * 0.35 : alpha * 0.5;
      g.strokeStyle = color;
      g.lineWidth = pass ? 0.6 + rnd() * 0.6 : width * (0.5 + rnd());
      let x = rnd() * S, y = -20, a = Math.PI / 2 + (rnd() - 0.5) * 1.2;
      g.beginPath();
      g.moveTo(x, y);
      while (y < S + 20 && x > -40 && x < S + 40) {
        a += (rnd() - 0.5) * 0.5;
        x += Math.cos(a) * 12;
        y += Math.abs(Math.sin(a)) * 12 + 2;
        g.lineTo(x, y);
      }
      g.stroke();
    }
  }
  g.filter = 'none';
  g.globalAlpha = 1;
}

/** Large-format porcelain with soft grey veining, 60 x 120 cm with 2 mm joints: { map, metres } */
export function porcelain(kind = 'warm') {
  const S = BIG, rnd = seeded(kind === 'warm' ? 7 : 9);
  const { c, g } = canvas(S);
  const base = kind === 'warm' ? '#e9e5df' : '#d5d4d1';
  g.fillStyle = base;
  g.fillRect(0, 0, S, S);
  // cloudy tone
  g.filter = 'blur(30px)';
  for (let i = 0; i < 30; i++) {
    g.globalAlpha = 0.18;
    g.fillStyle = rnd() < 0.5 ? '#f6f3ee' : kind === 'warm' ? '#d6d0c7' : '#c3c1bd';
    g.beginPath();
    g.arc(rnd() * S, rnd() * S, 30 + rnd() * 120, 0, Math.PI * 2);
    g.fill();
  }
  g.filter = 'none';
  g.globalAlpha = 1;
  veins(g, S, rnd, { color: kind === 'warm' ? '#aaa399' : '#8a8885', n: 9, width: 7, alpha: 0.22 });
  speckle(g, S, S, S * 4, 0.06, rnd);
  // joints: 2.4 m tile = 4 columns of 60 cm, 2 rows of 120 cm
  g.fillStyle = 'rgba(150, 145, 138, 0.9)';
  const cw = S / 4, rh = S / 2;
  for (let i = 0; i < 4; i++) g.fillRect(i * cw, 0, 2, S);
  for (let j = 0; j < 2; j++) g.fillRect(0, j * rh + (0), S, 2);
  return { map: tex(c), metres: 2.4 };
}

/** Quartz / marble slab for worktops and table tops (no joints) */
export function stoneSlab(kind = 'white') {
  const S = BIG / 2, rnd = seeded(kind === 'white' ? 19 : 21);
  const { c, g } = canvas(S);
  g.fillStyle = kind === 'white' ? '#efede9' : '#2c2d2f';
  g.fillRect(0, 0, S, S);
  veins(g, S, rnd, { color: kind === 'white' ? '#a8a29a' : '#6d6c69', n: 5, width: 3, alpha: kind === 'white' ? 0.35 : 0.45 });
  speckle(g, S, S, S * 8, 0.12, rnd, kind === 'white' ? ['#b9b2a8', '#ffffff'] : ['#111', '#555']);
  return { map: tex(c), metres: 1.2 };
}

/** Faint plaster / paint texture for walls: { map, metres } (multiplies the paint colour) */
export function plaster() {
  const S = 256, rnd = seeded(5);
  const { c, g } = canvas(S);
  g.fillStyle = '#f6f6f6';
  g.fillRect(0, 0, S, S);
  g.filter = 'blur(6px)';
  for (let i = 0; i < 70; i++) {
    g.globalAlpha = 0.05;
    g.fillStyle = rnd() < 0.5 ? '#e4e4e4' : '#ffffff';
    g.beginPath();
    g.arc(rnd() * S, rnd() * S, 6 + rnd() * 28, 0, Math.PI * 2);
    g.fill();
  }
  g.filter = 'none';
  speckle(g, S, S, 3000, 0.05, rnd, ['#d0d0d0', '#ffffff']);
  return { map: tex(c), metres: 1.6 };
}

/** Woven fabric: near-white weave that the material colour tints: { map, bump, metres } */
export function weave(kind = 'linen') {
  const S = 256, rnd = seeded(kind === 'linen' ? 13 : 17);
  const { c, g } = canvas(S);
  g.fillStyle = '#e8e8e8';
  g.fillRect(0, 0, S, S);
  const step = kind === 'boucle' ? 3 : 4;
  for (let y = 0; y < S; y += step) {
    g.globalAlpha = 0.25 + rnd() * 0.25;
    g.fillStyle = rnd() < 0.5 ? '#c9c9c9' : '#f8f8f8';
    g.fillRect(0, y, S, step / 2);
  }
  for (let x = 0; x < S; x += step) {
    g.globalAlpha = 0.18 + rnd() * 0.2;
    g.fillStyle = rnd() < 0.5 ? '#cfcfcf' : '#fdfdfd';
    g.fillRect(x, 0, step / 2, S);
  }
  if (kind === 'boucle') {
    for (let i = 0; i < 2600; i++) {
      g.globalAlpha = 0.25;
      g.fillStyle = rnd() < 0.5 ? '#bdbdbd' : '#ffffff';
      g.beginPath();
      g.arc(rnd() * S, rnd() * S, 0.8 + rnd() * 1.6, 0, Math.PI * 2);
      g.fill();
    }
  }
  // slubs: thicker threads here and there
  for (let i = 0; i < 90; i++) {
    g.globalAlpha = 0.2;
    g.fillStyle = rnd() < 0.5 ? '#b5b5b5' : '#ffffff';
    g.fillRect(rnd() * S, rnd() * S, 6 + rnd() * 20, 1.2);
  }
  g.globalAlpha = 1;
  return { map: tex(c), bump: tex(c, { srgb: false }), metres: kind === 'boucle' ? 0.12 : 0.18 };
}

/** Wool rug with a border, mapped once over the rug (uv 0..1) */
export function rug(kind) {
  const S = 512, rnd = seeded(kind === 'beige' ? 29 : 31);
  const { c, g } = canvas(S);
  const [base, dark, light] = kind === 'beige' ? ['#d8ccb8', '#a8987e', '#ece4d6'] : ['#8e918f', '#5f6261', '#b3b5b2'];
  g.fillStyle = base;
  g.fillRect(0, 0, S, S);
  for (let i = 0; i < 26000; i++) {
    g.globalAlpha = 0.12;
    g.fillStyle = rnd() < 0.5 ? dark : light;
    g.fillRect(rnd() * S, rnd() * S, 1.5, 3);
  }
  g.globalAlpha = 0.85;
  g.strokeStyle = dark;
  g.lineWidth = 7;
  g.strokeRect(22, 22, S - 44, S - 44);
  g.lineWidth = 2;
  g.strokeRect(38, 38, S - 76, S - 76);
  if (kind !== 'beige') {
    // a loose geometric field
    g.globalAlpha = 0.25;
    g.lineWidth = 3;
    for (let i = 0; i < 9; i++) {
      g.beginPath();
      g.moveTo(60 + i * 50, 60);
      g.lineTo(60 + i * 50 + 40, S - 60);
      g.stroke();
    }
  }
  g.globalAlpha = 1;
  return { map: tex(c, { repeat: false }) };
}

/** Abstract paintings for the walls (uv 0..1); variant 0..3 */
export function painting(variant) {
  const W = 480, H = 336, rnd = seeded(100 + variant);
  const { c, g } = canvas(W, H);
  const palettes = [
    ['#efe7da', '#c86b4a', '#e2b07a', '#3e4a4f', '#a9b4a4'],
    ['#f1efe9', '#1f2a36', '#8fa2b3', '#d9cbb5', '#b08155'],
    ['#ebe4d8', '#6b7f5e', '#c9b48f', '#2c2b29', '#d98e66'],
    ['#f4f1ea', '#b9a48a', '#8a6b4f', '#e6d8c3', '#3b3a36'],
  ][variant % 4];
  g.fillStyle = palettes[0];
  g.fillRect(0, 0, W, H);
  if (variant % 4 === 0) {
    // arcs and a sun
    for (let i = 0; i < 4; i++) {
      g.fillStyle = palettes[1 + (i % 4)];
      g.beginPath();
      g.arc(W * (0.25 + rnd() * 0.5), H * (0.55 + i * 0.12), W * (0.42 - i * 0.07), Math.PI, 0);
      g.fill();
    }
    g.fillStyle = palettes[2];
    g.beginPath();
    g.arc(W * 0.7, H * 0.25, W * 0.1, 0, Math.PI * 2);
    g.fill();
  } else if (variant % 4 === 1) {
    // layered landscape bands
    for (let i = 0; i < 6; i++) {
      g.fillStyle = palettes[1 + (i % 4)];
      g.globalAlpha = 0.85;
      g.beginPath();
      g.moveTo(0, H * (0.35 + i * 0.11));
      for (let x = 0; x <= W; x += 16) g.lineTo(x, H * (0.35 + i * 0.11) + Math.sin(x * 0.02 + i) * 14 + rnd() * 4);
      g.lineTo(W, H);
      g.lineTo(0, H);
      g.fill();
    }
  } else if (variant % 4 === 2) {
    // overlapping organic shapes
    for (let i = 0; i < 6; i++) {
      g.fillStyle = palettes[1 + (i % 4)];
      g.globalAlpha = 0.8;
      g.beginPath();
      g.ellipse(W * rnd(), H * rnd(), W * (0.12 + rnd() * 0.25), H * (0.08 + rnd() * 0.2), rnd() * 3, 0, Math.PI * 2);
      g.fill();
    }
  } else {
    // a single brush line drawing
    g.strokeStyle = palettes[4];
    g.lineWidth = 5;
    g.lineCap = 'round';
    g.beginPath();
    let x = W * 0.2, y = H * 0.8;
    g.moveTo(x, y);
    for (let i = 0; i < 9; i++) {
      const nx = W * (0.15 + rnd() * 0.7), ny = H * (0.15 + rnd() * 0.7);
      g.quadraticCurveTo(W * rnd(), H * rnd(), nx, ny);
    }
    g.stroke();
    g.fillStyle = palettes[1];
    g.globalAlpha = 0.6;
    g.beginPath();
    g.arc(W * 0.35, H * 0.4, W * 0.18, 0, Math.PI * 2);
    g.fill();
  }
  g.globalAlpha = 1;
  // canvas texture: paint tooth
  speckle(g, W, H, 9000, 0.06, rnd);
  return tex(c, { repeat: false });
}

/** One leaf on transparent ground (alpha cut-out), pointing up the texture */
export function leaf() {
  const S = 128, rnd = seeded(3);
  const { c, g } = canvas(S);
  const grd = g.createLinearGradient(0, 0, S, S);
  grd.addColorStop(0, '#4f7a37');
  grd.addColorStop(1, '#2f5222');
  g.fillStyle = grd;
  g.beginPath();
  g.moveTo(S / 2, 4);
  g.bezierCurveTo(S * 0.98, S * 0.3, S * 0.86, S * 0.82, S / 2, S - 4);
  g.bezierCurveTo(S * 0.14, S * 0.82, S * 0.02, S * 0.3, S / 2, 4);
  g.fill();
  g.strokeStyle = 'rgba(200, 225, 160, 0.55)';
  g.lineWidth = 2;
  g.beginPath();
  g.moveTo(S / 2, 8);
  g.lineTo(S / 2, S - 6);
  g.stroke();
  g.lineWidth = 1;
  for (let i = 1; i < 7; i++) {
    const y = (i / 7) * S;
    for (const s of [-1, 1]) {
      g.beginPath();
      g.moveTo(S / 2, y);
      g.quadraticCurveTo(S / 2 + s * S * 0.18, y - 6, S / 2 + s * S * (0.28 + rnd() * 0.06), y - 14);
      g.stroke();
    }
  }
  return tex(c, { repeat: false, aniso: 4 });
}

/** Small glazed wall tiles (kitchen splashback), 7.5 x 15 cm: { map, metres } */
export function splashTiles() {
  const S = 512, rnd = seeded(47);
  const { c, g } = canvas(S);
  g.fillStyle = '#cfcac2';
  g.fillRect(0, 0, S, S);
  const rows = 8, cols = 4, h = S / rows, w = S / cols;
  for (let r = 0; r < rows; r++) {
    for (let k = -1; k <= cols; k++) {
      const x = k * w + (r % 2) * w * 0.5;
      const l = 88 + rnd() * 6;
      const grd = g.createLinearGradient(x, r * h, x + w, r * h + h);
      grd.addColorStop(0, `hsl(${150 + rnd() * 20}, ${10 + rnd() * 8}%, ${l - 4}%)`);
      grd.addColorStop(1, `hsl(${150 + rnd() * 20}, ${10 + rnd() * 8}%, ${l - 10}%)`);
      g.fillStyle = grd;
      g.fillRect(x + 2, r * h + 2, w - 4, h - 4);
    }
  }
  return { map: tex(c), metres: 0.6 };
}
