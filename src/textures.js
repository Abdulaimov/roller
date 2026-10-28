// Procedural canvas textures so the demo needs no image files.
import * as THREE from 'three';

function finish(canvas, anisotropy = 8) {
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = anisotropy;
  return tex;
}

// 512px = 1.2 m of oak planks
export function woodTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 512;
  const g = c.getContext('2d');
  const plankH = 64;
  for (let y = 0; y < 512; y += plankH) {
    let x = -Math.random() * 300;
    while (x < 512) {
      const len = 200 + Math.random() * 220;
      const light = 52 + Math.random() * 12;
      for (const off of [-512, 0, 512]) {
        g.fillStyle = `hsl(30, 38%, ${light}%)`;
        g.fillRect(x + off, y, len, plankH);
        g.strokeStyle = 'rgba(80, 50, 25, 0.12)';
        g.lineWidth = 1;
        for (let k = 0; k < 6; k++) {
          const gy = y + 6 + Math.random() * (plankH - 12);
          g.beginPath();
          g.moveTo(x + off, gy);
          g.bezierCurveTo(x + off + len / 3, gy + 3, x + off + (2 * len) / 3, gy - 3, x + off + len, gy);
          g.stroke();
        }
        g.fillStyle = 'rgba(60, 38, 20, 0.45)';
        g.fillRect(x + off, y, 2, plankH);
      }
      x += len;
    }
    g.fillStyle = 'rgba(60, 38, 20, 0.45)';
    g.fillRect(0, y, 512, 2);
  }
  return finish(c);
}

// 512px = 1.2 m, 4x4 tiles
export function tileTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 512;
  const g = c.getContext('2d');
  g.fillStyle = '#b9b6b0';
  g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 4; i++) {
    for (let j = 0; j < 4; j++) {
      const l = 86 + Math.random() * 4;
      g.fillStyle = `hsl(40, 8%, ${l}%)`;
      g.fillRect(i * 128 + 2, j * 128 + 2, 124, 124);
    }
  }
  return finish(c);
}

// Ground textures for the site (model UVs are in metres; `metres` = size of one tile)
function noiseCanvas(size, base, spots) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  g.fillStyle = base;
  g.fillRect(0, 0, size, size);
  let seed = 3;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (const [n, rmin, rmax, colors, alpha] of spots) {
    for (let i = 0; i < n; i++) {
      const x = rnd() * size, y = rnd() * size, r = rmin + rnd() * (rmax - rmin);
      g.globalAlpha = alpha * (0.4 + rnd() * 0.6);
      g.fillStyle = colors[Math.floor(rnd() * colors.length)];
      for (const ox of [-size, 0, size]) {
        for (const oy of [-size, 0, size]) {
          g.beginPath();
          g.arc(x + ox, y + oy, r, 0, Math.PI * 2);
          g.fill();
        }
      }
    }
  }
  g.globalAlpha = 1;
  return { c, g };
}

// Facing brick (renders 1-3): stretcher bond, 30 courses and 10 bricks to a 2 m tile (65 mm bricks,
// 10 mm joints), each brick one of a few shades; a matching normal map (bricks proud of the joints,
// slightly rounded arrises) and a roughness map. kind 'tan' (the sandy multi-tone facing brick) or
// 'dark' (the graphite brick of the base).
const BRICK = {
  // the renders' facing brick: caramel to warm brown, a few light and a few dark bricks (sRGB; the
  // earlier sandy set, 232/190/135 on average, read pale yellow on the site), light grey joints
  // (23.10.2026: warmer and fuller, the golden caramel of render 1; the graphite a little blue, as there)
  tan: { mortar: [206, 199, 187], shades: [[214, 156, 96, 24], [200, 140, 84, 22], [224, 172, 112, 16], [184, 124, 74, 14], [160, 104, 62, 8], [232, 188, 134, 12], [206, 148, 94, 4]] },
  dark: { mortar: [118, 119, 124], shades: [[72, 74, 82, 30], [86, 88, 97, 28], [62, 64, 72, 22], [100, 102, 112, 12], [54, 56, 64, 8]] },
};
const brickCache = new Map();
export function brickTextures(kind) {
  if (brickCache.has(kind)) return brickCache.get(kind);
  const N = 1024, courses = 30, perRow = 10;
  const ch = N / courses, bw = N / perRow, joint = 4.6;
  const spec = BRICK[kind];
  const rnd = seeded(kind === 'tan' ? 7 : 11);
  const pick = () => {
    const tot = spec.shades.reduce((a, s) => a + s[3], 0);
    let r = rnd() * tot;
    for (const s of spec.shades) if ((r -= s[3]) <= 0) return s;
    return spec.shades[0];
  };
  const col = new Uint8ClampedArray(N * N * 4), hgt = new Float32Array(N * N), rough = new Uint8ClampedArray(N * N * 4);
  // brick cells: per course, the offset of half a brick every other course
  const shade = [];
  for (let r = 0; r < courses; r++) {
    shade.push([]);
    for (let k = 0; k <= perRow; k++) {
      const s = pick(), v = 0.92 + 0.16 * rnd();
      shade[r].push([s[0] * v, s[1] * v, s[2] * v, rnd()]);
    }
  }
  for (let y = 0; y < N; y++) {
    const r = Math.floor(y / ch), fy = y - r * ch;
    const off = (r % 2) * (bw / 2);
    for (let x = 0; x < N; x++) {
      const xx = (x + off) % N, k = Math.floor(xx / bw), fx = xx - k * bw;
      const dj = Math.min(fx, bw - fx, fy, ch - fy); // distance to the nearest joint (px)
      const i = y * N + x;
      let c, h;
      if (dj < joint / 2) {
        c = spec.mortar;
        h = 0;
        rough[i * 4 + 1] = 245;
      } else {
        const sh = shade[r][k % perRow];
        // speckle and a slight fade across the brick face
        const n = (Math.sin(x * 12.9898 + y * 78.233) * 43758.5453) % 1;
        const sp = 1 + 0.07 * (n - 0.5) * 2;
        c = [sh[0] * sp, sh[1] * sp, sh[2] * sp];
        h = Math.min(1, (dj - joint / 2) / 2.2);
        rough[i * 4 + 1] = 205 + 30 * sh[3];
      }
      col[i * 4] = c[0]; col[i * 4 + 1] = c[1]; col[i * 4 + 2] = c[2]; col[i * 4 + 3] = 255;
      hgt[i] = h;
      rough[i * 4] = 255; rough[i * 4 + 2] = 0; rough[i * 4 + 3] = 255;
    }
  }
  const nrm = new Uint8ClampedArray(N * N * 4);
  const H = (x, y) => hgt[((y + N) % N) * N + ((x + N) % N)];
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const dx = (H(x + 1, y) - H(x - 1, y)) * 1.6, dy = (H(x, y + 1) - H(x, y - 1)) * 1.6;
      const l = Math.hypot(dx, dy, 1), i = (y * N + x) * 4;
      nrm[i] = (-dx / l * 0.5 + 0.5) * 255;
      nrm[i + 1] = (dy / l * 0.5 + 0.5) * 255;
      nrm[i + 2] = (1 / l * 0.5 + 0.5) * 255;
      nrm[i + 3] = 255;
    }
  }
  const tex = (data, srgb) => {
    const c = document.createElement('canvas');
    c.width = c.height = N;
    c.getContext('2d').putImageData(new ImageData(data, N, N), 0, 0);
    const t = new THREE.CanvasTexture(c);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    t.anisotropy = 8;
    return t;
  };
  const out = { map: tex(col, true), normal: tex(nrm, false), rough: tex(rough, false) };
  brickCache.set(kind, out);
  return out;
}

// Cut-out patterns (alpha maps: white solid, black open), tiling.
export function alphaTexture(kind) {
  const size = 256, c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  g.fillStyle = '#ffffff';
  g.fillRect(0, 0, size, size);
  if (kind === 'perforated') {
    // perforated sheet (render 4): staggered round holes, about a quarter open (the screen reads as a
    // light grey sheet with the sky showing through it)
    g.fillStyle = '#000000';
    const p = 16;
    for (let y = 0; y < size; y += p) {
      for (let x = ((y / p) % 2) * (p / 2); x < size + p; x += p) {
        g.beginPath();
        g.arc(x, y + p / 2, p * 0.24, 0, Math.PI * 2);
        g.fill();
      }
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.NoColorSpace;
  tex.anisotropy = 8;
  return tex;
}

export function groundTexture(kind) {
  let canvas, metres;
  if (kind === 'grass') {
    const { c } = noiseCanvas(256, '#5f6e1a', [
      [60, 18, 40, ['#6f7f22', '#56661a', '#4d5c16', '#7a8a2a'], 0.35],
      [1800, 0.6, 1.8, ['#84952e', '#46541a', '#6a7a20'], 0.5],
    ]);
    canvas = c; metres = 14;
  } else if (kind === 'asphalt') {
    const { c } = noiseCanvas(256, '#57585c', [
      [40, 10, 30, ['#5d5e62', '#515256'], 0.3],
      [4000, 0.4, 1.0, ['#6a6b70', '#47484c', '#77787c'], 0.6],
    ]);
    canvas = c; metres = 6;
  } else if (kind in SURFACES) {
    ({ canvas, metres } = SURFACES[kind]());
  } else {
    // paving slabs with joints
    const { c, g } = noiseCanvas(256, kind === 'deck' ? '#dcb88f' : '#c8bcab', [[1200, 0.5, 1.2, ['#d4c9b9', '#b9ad9c'], 0.4]]);
    g.strokeStyle = 'rgba(90, 80, 70, 0.35)';
    g.lineWidth = 2;
    for (let i = 0; i <= 4; i++) {
      g.beginPath(); g.moveTo(i * 64, 0); g.lineTo(i * 64, 256); g.stroke();
      g.beginPath(); g.moveTo(0, i * 64); g.lineTo(256, i * 64); g.stroke();
    }
    canvas = c; metres = 2.4;
  }
  const tex = finish(canvas, 8);
  tex.repeat.set(1 / metres, 1 / metres);
  return tex;
}

// Surfaces of the roof deck, shop front and promenade (render 2). Each returns { canvas, metres }.
function seeded(seed) {
  return () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
}

function blocks(size, base, joint, rows, cols, stagger, shades, seed) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  const rnd = seeded(seed);
  g.fillStyle = joint;
  g.fillRect(0, 0, size, size);
  const h = size / rows, w = size / cols;
  for (let r = 0; r < rows; r++) {
    const off = stagger ? (r % 2) * w * stagger : 0;
    for (let k = -1; k <= cols; k++) {
      g.fillStyle = shades[Math.floor(rnd() * shades.length)];
      g.fillRect(k * w + off + 1.5, r * h + 1.5, w - 3, h - 3);
      g.globalAlpha = 0.25;
      g.fillStyle = base;
      g.fillRect(k * w + off + 1.5 + rnd() * w * 0.3, r * h + 1.5, w * 0.4, h - 3);
      g.globalAlpha = 1;
    }
  }
  return { c, g, rnd };
}

const SURFACES = {
  // the perforated screens in front of the small loggias (renders): dark grey metal with a lighter
  // lattice ornament; 256 px = 1.2 m
  // the perforated metal screens (renders 1 and 3): charcoal sheet with a lattice of openings, the
  // light of the loggia behind showing through them (mid grey from a distance)
  screen() {
    const size = 256, c = document.createElement('canvas');
    c.width = c.height = size;
    const g = c.getContext('2d');
    g.fillStyle = '#5a5857';
    g.fillRect(0, 0, size, size);
    const rnd = seeded(5);
    for (let k = 0; k < 900; k++) {
      g.fillStyle = rnd() < 0.5 ? 'rgba(176,172,168,0.55)' : 'rgba(42,40,40,0.45)';
      g.fillRect(rnd() * size, rnd() * size, 3, 3);
    }
    g.strokeStyle = '#a9a5a1';
    g.lineWidth = 6;
    const q = size / 4;
    for (let i = 0; i < 4; i++) {
      for (let j = 0; j < 4; j++) {
        const x = i * q + q / 2, y = j * q + q / 2;
        g.beginPath();
        g.moveTo(x, y - q * 0.42); g.lineTo(x + q * 0.42, y); g.lineTo(x, y + q * 0.42); g.lineTo(x - q * 0.42, y); g.closePath();
        g.stroke();
        g.beginPath();
        g.arc(x, y, q * 0.12, 0, Math.PI * 2);
        g.stroke();
      }
    }
    g.fillStyle = 'rgba(0,0,0,0.15)';
    for (let i = 0; i <= 4; i++) g.fillRect(i * q - 2, 0, 4, size);
    return { canvas: c, metres: 1.1 };
  },
  // the posters on the shop fronts: one picture over the whole panel (UV 0..1)
  poster() {
    const W = 512, H = 768, c = document.createElement('canvas');
    c.width = W;
    c.height = H;
    const g = c.getContext('2d');
    const gr = g.createLinearGradient(0, 0, 0, H);
    gr.addColorStop(0, '#2c2a28');
    gr.addColorStop(1, '#4a3a2a');
    g.fillStyle = gr;
    g.fillRect(0, 0, W, H);
    // a stylised tower and the slab blocks
    g.fillStyle = '#d8a66b';
    g.fillRect(150, 230, 70, 330);
    g.fillRect(240, 290, 60, 270);
    g.fillRect(320, 260, 60, 300);
    g.fillStyle = '#7fa6b8';
    g.fillRect(70, 180, 60, 380);
    g.fillStyle = 'rgba(255,255,255,0.75)';
    for (let y = 195; y < 560; y += 22) g.fillRect(70, y, 60, 4);
    g.fillStyle = '#f3e7d6';
    g.textAlign = 'center';
    g.font = '800 64px system-ui, sans-serif';
    g.fillText('АЛИ', W / 2, 650);
    g.fillText('БИНОКОР', W / 2, 715);
    g.font = '600 30px system-ui, sans-serif';
    g.fillStyle = '#d8a66b';
    g.fillText('ЖИЛОЙ КОМПЛЕКС', W / 2, 120);
    g.strokeStyle = '#d8a66b';
    g.lineWidth = 6;
    g.strokeRect(14, 14, W - 28, H - 28);
    return { canvas: c, metres: 1 };
  },
  // grey irregular stone setts
  cobble() {
    const size = 256, c = document.createElement('canvas');
    c.width = c.height = size;
    const g = c.getContext('2d'), rnd = seeded(17);
    g.fillStyle = '#7d7a76';
    g.fillRect(0, 0, size, size);
    const n = 9;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const cx = (i + 0.5 + (rnd() - 0.5) * 0.35) * (size / n), cy = (j + 0.5 + (rnd() - 0.5) * 0.35) * (size / n);
        const r = (size / n) * (0.42 + rnd() * 0.08);
        const l = 60 + rnd() * 16;
        g.fillStyle = `hsl(30, 4%, ${l}%)`;
        const k = 6 + Math.floor(rnd() * 3);
        const pts = [];
        for (let t = 0; t < k; t++) {
          const a = (t / k) * Math.PI * 2 + rnd() * 0.4, rr = r * (0.8 + rnd() * 0.25);
          pts.push([Math.cos(a) * rr, Math.sin(a) * rr]);
        }
        // draw wrapped copies so the tile repeats without seams
        for (const [ox, oy] of [[0, 0], [size, 0], [-size, 0], [0, size], [0, -size]]) {
          g.beginPath();
          pts.forEach(([px, py], t) => (t ? g.lineTo(cx + ox + px, cy + oy + py) : g.moveTo(cx + ox + px, cy + oy + py)));
          g.closePath();
          g.fill();
        }
      }
    }
    return { canvas: c, metres: 2.2 };
  },
  // warm tan large-format stone around the pool
  stone() {
    const { c } = blocks(256, '#e2bd92', '#b48d66', 4, 2, 0.5, ['#d9b088', '#d4a97c', '#ddb58c', '#cfa477'], 23);
    return { canvas: c, metres: 2.4 };
  },
  // blue-grey pebble mosaic
  mosaic() {
    const { c } = noiseCanvas(128, '#6f8fa3', [[700, 1.5, 3.2, ['#89a7b8', '#5a7a8f', '#9bb4c2', '#4f6d82', '#b5c6cf'], 0.9]]);
    return { canvas: c, metres: 0.6 };
  },
  // perforated copper screen: panels with darker joints and a dot pattern
  copper() {
    const size = 256, c = document.createElement('canvas');
    c.width = c.height = size;
    const g = c.getContext('2d');
    g.fillStyle = '#d2a08a'; // light pinkish copper sheet, as on the renders
    g.fillRect(0, 0, size, size);
    for (let y = 4; y < size; y += 8) {
      for (let x = 4 + ((y / 8) % 2) * 4; x < size; x += 8) {
        const k = 0.5 + 0.5 * Math.sin(x * 0.05) * Math.cos(y * 0.04);
        g.fillStyle = `rgba(110, 60, 40, ${0.25 + 0.3 * k})`;
        g.beginPath();
        g.arc(x, y, 1.6 + 1.2 * k, 0, Math.PI * 2);
        g.fill();
      }
    }
    g.fillStyle = 'rgba(90, 50, 34, 0.8)';
    g.fillRect(0, 0, 4, size);
    g.fillRect(0, 0, size, 3);
    return { canvas: c, metres: 1.5 };
  },
  rubber() {
    const { c } = noiseCanvas(128, '#1f63b0', [[900, 0.6, 1.4, ['#2a73c4', '#18559a', '#3a82cc'], 0.7]]);
    return { canvas: c, metres: 2 };
  },
  promenade() {
    const { c } = blocks(256, '#ddd5ca', '#b9afa3', 8, 4, 0.5, ['#d8cfc4', '#d2c8bc', '#ddd4c9', '#cec4b8'], 31);
    return { canvas: c, metres: 1.6 };
  },
  // sidewalks: 40 cm grey concrete slabs, laid square, with a little weathering
  slabs() {
    const size = 512, c = document.createElement('canvas');
    c.width = c.height = size;
    const g = c.getContext('2d'), rnd = seeded(41);
    g.fillStyle = '#8f8f8c';
    g.fillRect(0, 0, size, size);
    const n = 6, s = size / n;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const l = 74 + rnd() * 7;
        g.fillStyle = `hsl(${40 + rnd() * 20}, ${3 + rnd() * 4}%, ${l}%)`;
        g.fillRect(i * s + 2, j * s + 2, s - 4, s - 4);
        // aggregate speckle and a stain now and then
        for (let k = 0; k < 220; k++) {
          g.globalAlpha = 0.25;
          g.fillStyle = rnd() < 0.5 ? '#9a9893' : '#d9d8d3';
          g.fillRect(i * s + 2 + rnd() * (s - 6), j * s + 2 + rnd() * (s - 6), 1.5, 1.5);
        }
        if (rnd() < 0.18) {
          g.globalAlpha = 0.12;
          g.fillStyle = '#6f6a62';
          g.beginPath();
          g.ellipse(i * s + s * rnd(), j * s + s * rnd(), s * 0.3, s * 0.2, rnd() * 3, 0, Math.PI * 2);
          g.fill();
        }
        g.globalAlpha = 1;
      }
    }
    return { canvas: c, metres: 2.4 };
  },
  // the plaza round the complex: pale stone pavers 30 x 60 cm in running bond, mixed tones
  plaza() {
    const { c, g, rnd } = blocks(512, '#d6d1c8', '#a9a39a', 8, 4, 0.5, ['#d9d4cb', '#cfc9bf', '#e0dbd2', '#c8c2b8', '#d4cdc1'], 53);
    for (let k = 0; k < 9000; k++) {
      g.globalAlpha = 0.18;
      g.fillStyle = rnd() < 0.5 ? '#a8a299' : '#ebe7df';
      g.fillRect(rnd() * 512, rnd() * 512, 1.5, 1.5);
    }
    g.globalAlpha = 1;
    return { canvas: c, metres: 2.4 };
  },
};
