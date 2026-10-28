"""Turn the downloaded CC0 sources (blender/assets, see fetch_assets.py) into the files the site loads.

    python3 scripts/build_web_assets.py          # needs: pip install pillow numpy

public/textures/<set>/{color,normal,orm}_{1k,512}.webp
    PBR sets, 1k for computers and 512 px for phones (src/materials.js picks one). Sets meant to
    be tinted by the material colour (plaster, concrete, rubber) get a neutral grey colour map:
    the hue is removed, the light and dark of the surface kept.
public/env/sky_{1k,2k}.hdr, public/env/sky.json
    the sky HDRI with its sun disc taken out (the sun is the viewer's shadow-casting light), and
    where that sun was, so the light lines up with the sky.
"""
import json
import math
import os

import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, 'blender', 'assets')
OUT = os.path.join(ROOT, 'public')

# web set -> (Poly Haven texture, neutral colour map for tinting?)
SETS = {
    'plaster': ('painted_plaster_wall', True),
    'concrete': ('concrete_wall_008', True),
    'asphalt': ('aerial_asphalt_01', False),
    'grass': ('sparse_grass', True),
    'pavers': ('concrete_pavers', False),
    'patio': ('patio_tiles', False),
    'paving': ('rectangular_paving', False),
    'setts': ('grey_stone_path', False),
    'deck': ('wood_floor_deck', False),
    'rubber': ('rubber_tiles', True),
    'brick': ('brick_wall_09', True),
}
SIZES = {'1k': 1024, '512': 512}
SKY = 'kloofendal_48d_partly_cloudy_puresky'


def src(name, kind, res='1k'):
    return os.path.join(SRC, 'textures', name, f'{name}_{kind}_{res}.jpg')


def save(img, path, quality):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, 'WEBP', quality=quality, method=6)


def neutral(img):
    """Colour map -> grey with the same light and dark, mean lifted to ~0.78 (so the material
    colour gives the final hue and brightness)."""
    a = np.asarray(img.convert('RGB'), np.float32) / 255.0
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    y = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    y = y / max(float(y.mean()), 1e-4) * 0.58          # 0.58 linear = 0.78 sRGB
    y = np.clip(y, 0, 1)
    s = np.where(y <= 0.0031308, y * 12.92, 1.055 * np.power(y, 1 / 2.4) - 0.055)
    g = (np.clip(s, 0, 1) * 255 + 0.5).astype(np.uint8)
    return Image.fromarray(np.stack([g, g, g], axis=-1))


def textures():
    for web, (ph, tint) in SETS.items():
        base = '2k' if os.path.exists(src(ph, 'diff', '2k')) else '1k'
        maps = {'color': src(ph, 'diff', base), 'normal': src(ph, 'nor_gl', base), 'orm': src(ph, 'arm', base)}
        for kind, path in maps.items():
            img = Image.open(path)
            if kind == 'color' and tint:
                img = neutral(img)
            for tag, px in SIZES.items():
                out = img.convert('RGB').resize((px, px), Image.LANCZOS)
                save(out, os.path.join(OUT, 'textures', web, f'{kind}_{tag}.webp'), 82 if kind == 'color' else 88)
        print('textures', web, '<-', ph, base)


def read_hdr(path):
    """Radiance RGBE (new-style RLE) -> float32 HxWx3."""
    with open(path, 'rb') as f:
        data = f.read()
    head_end = data.index(b'\n\n') + 2
    line_end = data.index(b'\n', head_end)
    dims = data[head_end:line_end].split()
    H, W = int(dims[1]), int(dims[3])
    pos = line_end + 1
    img = np.zeros((H, W, 4), np.uint8)
    for y in range(H):
        assert data[pos] == 2 and data[pos + 1] == 2, 'only RLE scanlines supported'
        pos += 4
        for c in range(4):
            x = 0
            while x < W:
                n = data[pos]
                pos += 1
                if n > 128:
                    n -= 128
                    img[y, x:x + n, c] = data[pos]
                    pos += 1
                else:
                    img[y, x:x + n, c] = np.frombuffer(data, np.uint8, n, pos)
                    pos += n
                x += n
    e = img[..., 3].astype(np.int32)
    scale = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0).astype(np.float32)
    return img[..., :3].astype(np.float32) * scale[..., None]


def write_hdr(path, img):
    """float32 HxWx3 -> Radiance RGBE with run-length encoded scanlines."""
    H, W, _ = img.shape
    m = img.max(axis=2)
    e = np.zeros((H, W), np.int32)
    mant = np.zeros((H, W), np.float32)
    nz = m > 1e-32
    mant[nz], e[nz] = np.frexp(m[nz])
    scale = np.where(nz, mant * 256.0 / np.maximum(m, 1e-32), 0)
    rgbe = np.zeros((H, W, 4), np.uint8)
    rgbe[..., :3] = np.clip(img * scale[..., None], 0, 255).astype(np.uint8)
    rgbe[..., 3] = np.where(nz, e + 128, 0).astype(np.uint8)
    out = bytearray(b'#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n' + f'-Y {H} +X {W}\n'.encode())
    for y in range(H):
        out += bytes([2, 2, W >> 8, W & 255])
        for c in range(4):
            row = rgbe[y, :, c]
            x = 0
            while x < W:
                # a run of 3+ equal bytes, else a literal stretch up to the next run
                r = 1
                while x + r < W and r < 127 and row[x + r] == row[x]:
                    r += 1
                if r >= 3:
                    out += bytes([128 + r, int(row[x])])
                    x += r
                    continue
                start = x
                while x < W and x - start < 128:
                    if x + 2 < W and row[x] == row[x + 1] == row[x + 2]:
                        break
                    x += 1
                out += bytes([x - start]) + row[start:x].tobytes()
    open(path, 'wb').write(out)


def sky():
    """The sky for lighting and background, with the sun disc taken out: the sun is the
    viewer's directional light (with shadows), so leaving it in the sky would light the scene twice."""
    os.makedirs(os.path.join(OUT, 'env'), exist_ok=True)
    for res in ('1k', '2k'):
        img = read_hdr(os.path.join(SRC, 'hdri', f'{SKY}_{res}.hdr'))
        lum = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        cap = float(np.percentile(lum[: img.shape[0] // 2], 99.5)) * 1.5
        k = np.minimum(1.0, cap / np.maximum(lum, 1e-9))
        write_hdr(os.path.join(OUT, 'env', f'sky_{res}.hdr'), img * k[..., None])
    hdr = read_hdr(os.path.join(SRC, 'hdri', f'{SKY}_1k.hdr'))
    H, W, _ = hdr.shape
    lum = hdr @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    # the sun: centroid of the brightest pixels
    thr = np.percentile(lum, 99.995)
    ys, xs = np.nonzero(lum >= thr)
    w = lum[ys, xs]
    u, v = (xs + 0.5) @ w / w.sum() / W, (ys + 0.5) @ w / w.sum() / H
    # three.js equirect: u = 0.5 + atan2(dir.z, dir.x) / 2pi ... expressed as the direction itself
    phi = (u - 0.5) * 2 * math.pi       # angle about +y, from +x towards +z
    theta = (0.5 - v) * math.pi         # elevation
    d = [math.cos(theta) * math.cos(phi), math.sin(theta), math.cos(theta) * math.sin(phi)]
    info = dict(file=SKY, source=f'https://polyhaven.com/a/{SKY}', licence='CC0',
                sun_dir=[round(x, 5) for x in d], sun_elevation_deg=round(math.degrees(theta), 2),
                sun_uv=[round(float(u), 5), round(float(v), 5)],
                sun_to_sky=round(float(lum[ys, xs].mean() / np.median(lum[: H // 2])), 1))
    json.dump(info, open(os.path.join(OUT, 'env', 'sky.json'), 'w'), indent=1)
    print('sky', info)


if __name__ == '__main__':
    textures()
    sky()
