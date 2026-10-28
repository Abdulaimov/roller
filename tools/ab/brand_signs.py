"""Brand signs for the shop fronts: the developer wants popular brands' logos over the shops (a concept,
not confirmed tenants). For each brand three pictures in public/signs/brands/:
  <id>.png         the sign over the shop's portals: lit letters (white, or the brand's colour) on a
                   transparent ground, for the dark stone frieze of blocks Б, В, Г, Д
  <id>_band.png    the same logo in dark / brand colours for the white band of block A's podium
  <id>_banner.jpg  a lit poster hung behind the shop's second-floor glass (render 3 has posters there):
                   the brand's colour with the logo
The logos (tools/ab/brand_logos, SOURCES.md) are rasterized first, then composed here:
    node tools/ab/svg_raster.mjs tools/ab/brand_logos build/brand_png 1600
    tools/ab/py tools/ab/brand_signs.py            # + build/brand_signs.png, a sheet of them all"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
SRC = os.path.join(ROOT, 'build', 'brand_png')
OUT = os.path.join(ROOT, 'public', 'signs', 'brands')
F = '/System/Library/Fonts/'
S = F + 'Supplemental/'
FUTURA = (S + 'Futura.ttc', 0)           # Futura Medium
FUTURA_XB = (S + 'Futura.ttc', 4)        # Futura Condensed ExtraBold
AVENIR = (F + 'Avenir Next.ttc', 5)      # Avenir Next Medium

SIGN_H = 192       # px: the sign's full height (the tallest part)
BANNER = (360, 504)  # px: a 2.2 x 3.1 m poster


def P(src, col=None, s=1.0, crop=None, back=None):
    """a logo part: rasterized SVG `src`; col None = the picture's own colour role (white sign, dark
    band, banner foreground), 'orig' = the logo's colours, '#rrggbb' = that colour; s = height
    relative to the sign; crop ('x'|'y', i) = the i-th piece of a logo split by empty columns / rows;
    back 'box:#hex[:inset]' / 'disc:#hex[:inset]' / 'pad:#hex' = a ground under it (knocked-out
    letters of a badge, a box round white letters)"""
    return dict(src=src, col=col, s=s, crop=crop, back=back)


def T(text, font=FUTURA, track=0.08, col=None, s=1.0):
    return dict(text=text, font=font, track=track, col=col, s=s)


# id: sign parts (in a row), band parts (default: the sign's), banner (bg, fg, parts stacked, tag)
BRANDS = {
    # luxury and premium (the street faces)
    'louisvuitton': dict(sign=[P('lv_mono', crop=('y', 0)), P('lv_word', s=0.5)],
                         banner=('#4a3426', '#e6d2aa', [P('lv_mono', crop=('y', 0)), P('lv_word', s=0.16)], 'PARIS')),
    'gucci': dict(sign=[P('gucci', crop=('y', 0))],
                  banner=('#173b2c', '#d2b273', [P('gucci')], None)),
    'prada': dict(sign=[P('prada')], banner=('#121212', '#ffffff', [P('prada')], 'MILANO')),
    'chanel': dict(sign=[P('chanel')], banner=('#0e0e0e', '#ffffff', [P('chanel')], 'PARIS')),
    'dior': dict(sign=[P('dior')], banner=('#ece8e1', '#111111', [P('dior')], 'PARIS')),
    'versace': dict(sign=[P('versace', crop=('y', 0), col='#d8b96e'), P('versace', crop=('y', 1), s=0.42)],
                    banner=('#101010', '#d8b96e', [P('versace')], None)),
    'burberry': dict(sign=[P('burberry')], banner=('#f1ece3', 'orig', [P('burberry_knight')], None)),
    'armani': dict(sign=[P('armani')], banner=('#1b1b1b', '#ffffff', [P('armani')], 'NEW COLLECTION')),
    'boss': dict(sign=[P('boss')], banner=('#0f0f0f', '#ffffff', [P('boss')], 'NEW COLLECTION')),
    'hugo': dict(sign=[P('hugo', col='orig')], banner=('#121212', 'orig', [P('hugo')], None)),
    'lacoste': dict(sign=[P('lacoste', crop=('x', 0)), P('lacoste', crop=('x', 1), col='#2f9e5b', s=0.8)],
                    band=[P('lacoste', col='orig')],
                    banner=('#ffffff', 'orig', [P('lacoste', crop=('x', 1)), P('lacoste', crop=('x', 0), s=0.3)], None)),
    'calvinklein': dict(sign=[P('calvinklein')], banner=('#ffffff', '#111111', [P('calvinklein')], 'NEW COLLECTION')),
    'tommy': dict(sign=[P('tommy_flag', col='orig', s=0.62), T('TOMMY HILFIGER', s=0.5, track=0.1)],
                  band=[P('tommy_flag', col='orig', s=0.62), T('TOMMY HILFIGER', s=0.5, track=0.1, col='#0b1f4b')],
                  banner=('#0b1f4b', '#ffffff', [P('tommy_flag', col='orig'), T('TOMMY HILFIGER', s=0.24, track=0.1)], None)),
    'massimodutti': dict(sign=[P('massimodutti')], banner=('#ebe4d8', '#1a1a1a', [P('massimodutti')], 'NEW COLLECTION')),
    'michaelkors': dict(sign=[P('michaelkors')], banner=('#e9e1d6', '#1a1a1a', [P('michaelkors')], None)),
    'guess': dict(sign=[P('guess')], banner=('#141414', '#ffffff', [P('guess')], None)),
    # fashion for everyone
    'zara': dict(sign=[P('zara')], banner=('#ffffff', '#111111', [P('zara')], 'NEW COLLECTION')),
    'hm': dict(sign=[P('hm', col='#e50010')], banner=('#ffffff', '#e50010', [P('hm')], None)),
    'mango': dict(sign=[P('mango')], banner=('#121212', '#ffffff', [P('mango')], None)),
    'bershka': dict(sign=[P('bershka')], banner=('#121212', '#ffffff', [P('bershka')], None)),
    'uniqlo': dict(sign=[P('uniqlo', col='#ff0000', back='box:#ffffff')], band=None,
                   banner=('#ffffff', None, [P('uniqlo', col='#ff0000', back='box:#ffffff')], None)),
    'levis': dict(sign=[P('levis', col='orig')], banner=('#ffffff', 'orig', [P('levis')], None)),
    'lcwaikiki': dict(sign=[P('lcwaikiki', col='#ffffff', back='pad:#0047ba')], band=[P('lcwaikiki', col='orig')],
                      banner=('#0047ba', '#ffffff', [P('lcwaikiki')], None)),
    # sport
    'nike': dict(sign=[P('nike_word'), P('nike_swoosh', s=0.8)], banner=('#111111', '#ffffff', [P('nike_swoosh')], None)),
    'adidas': dict(sign=[P('adidas')], h=0.76,
                   banner=('#111111', '#ffffff', [P('adidas')], None)),
    'puma': dict(sign=[P('puma_word', s=0.8), P('puma_cat')],
                 banner=('#111111', '#ffffff', [P('puma_cat'), P('puma_word', s=0.32)], None)),
    'newbalance': dict(sign=[P('newbalance', crop=('y', 0), col='#e21836'), P('newbalance', crop=('y', 1), s=0.5)],
                       band=[P('newbalance', col='orig')],
                       banner=('#e4e3e0', 'orig', [P('newbalance')], None)),
    'underarmour': dict(sign=[P('underarmour')], banner=('#111111', '#ffffff', [P('underarmour')], None)),
    'reebok': dict(sign=[P('reebok', crop=('y', 1), s=0.75), P('reebok', crop=('y', 0), s=0.7)],
                   banner=('#ffffff', '#111111', [P('reebok')], None)),
    'thenorthface': dict(sign=[P('thenorthface')], banner=('#d62a26', '#ffffff', [P('thenorthface')], None)),
    'jordan': dict(sign=[P('jordan'), T('JORDAN', FUTURA_XB, 0.06, s=0.5)],
                   banner=('#b5121b', '#ffffff', [P('jordan')], None)),
    'fila': dict(sign=[P('fila')], banner=('#002d62', '#ffffff', [P('fila')], None)),
    'skechers': dict(sign=[P('skechers')], banner=('#1d4f91', '#ffffff', [P('skechers')], None)),
    'converse': dict(sign=[P('converse', crop=('y', 0), s=0.85), P('converse', crop=('y', 1), s=0.5)],
                     banner=('#ffffff', '#111111', [P('converse')], None)),
    'timberland': dict(sign=[P('timberland')], banner=('#e1a43c', '#1a1a1a', [P('timberland')], None)),
    'columbia': dict(sign=[P('columbia')], banner=('#ffffff', 'orig', [P('columbia')], None)),
    'decathlon': dict(sign=[P('decathlon', col='#ffffff', back='pad:#3643ba')], band=[P('decathlon', col='orig')],
                      banner=('#3643ba', '#ffffff', [P('decathlon')], None)),
    # tech
    'apple': dict(sign=[P('apple')], banner=('#f5f5f7', '#1d1d1f', [P('apple')], None)),
    'samsung': dict(sign=[P('samsung')], band=[P('samsung', col='#1428a0')],
                    banner=('#1428a0', '#ffffff', [P('samsung')], None)),
    'xiaomi': dict(sign=[P('xiaomi', col='#ff6900', back='box:#ffffff:0.15'), T('Xiaomi', AVENIR, 0.02, s=0.62)],
                   band=[P('xiaomi', col='#ff6900', back='box:#ffffff:0.15'), T('Xiaomi', AVENIR, 0.02, s=0.62, col='#1a1a1a')],
                   banner=('#ff6900', '#ffffff', [P('xiaomi', col='#ffffff', back='box:#ff6900:0.15')], None)),
    'huawei': dict(sign=[P('huawei_flower', col='#c7000b'), P('huawei_word', s=0.5)],
                   band=[P('huawei_flower', col='#c7000b'), P('huawei_word', s=0.5)],
                   banner=('#ffffff', '#1a1a1a', [P('huawei_flower', col='#c7000b'), P('huawei_word', s=0.22)], None)),
    'sony': dict(sign=[P('sony')], banner=('#111111', '#ffffff', [P('sony')], None)),
    # beauty, jewellery, children
    'sephora': dict(sign=[P('sephora')], banner=('#111111', '#ffffff', [P('sephora')], None)),
    'rolex': dict(sign=[P('rolex', col='#d8b96e')], band=[P('rolex', col='orig')],
                  banner=('#006039', '#d8b96e', [P('rolex')], None)),
    'pandora': dict(sign=[P('pandora')], banner=('#f6e4e1', '#1a1a1a', [P('pandora')], None)),
    'swarovski': dict(sign=[P('swarovski')], banner=('#ffffff', '#111111', [P('swarovski')], None)),
    'lego': dict(sign=[P('lego', col='orig')], banner=('#ffcf00', 'orig', [P('lego')], None)),
    # food
    'starbucks': dict(sign=[P('starbucks_siren', col='#00704a', back='disc:#ffffff:0.03'), P('starbucks_word', s=0.42)],
                      band=[P('starbucks_siren', col='#00704a', back='disc:#ffffff:0.03'), P('starbucks_word', s=0.42, col='orig')],
                      banner=('#00704a', '#ffffff', [P('starbucks_siren', col='#00704a', back='disc:#ffffff:0.03'),
                                                      P('starbucks_word', s=0.14)], None)),
    'mcdonalds': dict(sign=[P('mcdonalds', col='#ffc72c')], banner=('#da291c', '#ffc72c', [P('mcdonalds')], None)),
    'kfc': dict(sign=[P('kfc', col='#ffffff', back='pad:#e4002b')], band=[P('kfc', col='#e4002b')],
                banner=('#e4002b', '#ffffff', [P('kfc')], None)),
}

_cache = {}


def logo(name):
    if name not in _cache:
        im = Image.open(os.path.join(SRC, name + '.png')).convert('RGBA')
        _cache[name] = im.crop(im.getchannel('A').getbbox())
    return _cache[name]


def pieces(im, axis, gap):
    """runs of content along x (columns) or y (rows), split by empty gaps wider than `gap` px"""
    a = np.asarray(im.getchannel('A')) > 24
    full = a.any(axis=0 if axis == 'x' else 1)
    runs, start, last = [], None, None
    for i, f in enumerate(full):
        if f:
            if start is None:
                start = i
            elif i - last > gap:
                runs.append((start, last + 1))
                start = i
            last = i
    if start is not None:
        runs.append((start, last + 1))
    return runs


def colour(im, col):
    if col in (None, 'orig'):
        return im
    solid = Image.new('RGBA', im.size, col)
    solid.putalpha(im.getchannel('A'))
    return solid


def text_img(t, h, col):
    path, idx = t['font']
    size = 400
    font = ImageFont.truetype(path, size, index=idx)
    gap = t['track'] * size
    widths = [font.getlength(ch) for ch in t['text']]
    W = int(sum(widths) + gap * (len(t['text']) - 1)) + 80
    img = Image.new('RGBA', (W, size * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 40
    for ch, w in zip(t['text'], widths):
        d.text((x, size * 1.4), ch, font=font, fill=col, anchor='ls')
        x += w + gap
    img = img.crop(img.getbbox())
    return img.resize((max(1, round(img.width * h / img.height)), h), Image.LANCZOS)


def part_img(p, h, default):
    """one part at height h px"""
    col = p['col'] if p['col'] is not None else default
    if 'text' in p:
        return text_img(p, h, '#ffffff' if col in (None, 'orig') else col)
    im = logo(p['src'])
    if p['crop']:
        axis, i = p['crop']
        runs = pieces(im, axis, 0.12 * im.height if axis == 'x' else 0.03 * im.height)
        a, b = runs[i]
        im = im.crop((a, 0, b, im.height) if axis == 'x' else (0, a, im.width, b))
        im = im.crop(im.getchannel('A').getbbox())
    im = colour(im, col)
    if p['back']:
        kind, bc, *rest = p['back'].split(':')
        if kind == 'pad':
            pad = int(0.28 * im.height)
            g = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), bc)
            g.alpha_composite(im, (pad, pad))
            im = g
        else:
            inset = float(rest[0]) if rest else 0.0
            g = Image.new('RGBA', im.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(g)
            box = (inset * im.width, inset * im.height, (1 - inset) * im.width - 1, (1 - inset) * im.height - 1)
            (d.rectangle if kind == 'box' else d.ellipse)(box, fill=bc)
            g.alpha_composite(im)
            im = g
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


def row(parts, h, default, gap=0.3):
    ims = [part_img(p, max(1, round(h * p['s'])), default) for p in parts]
    g = int(gap * h)
    W = sum(i.width for i in ims) + g * (len(ims) - 1)
    out = Image.new('RGBA', (W + 8, h + 8), (0, 0, 0, 0))
    x = 4
    for i in ims:
        out.alpha_composite(i, (x, 4 + (h - i.height) // 2))
        x += i.width + g
    return out


def stack(parts, w, h, default, gap=0.12):
    """parts one over another, fitted into w x h px"""
    base = 400
    ims = [part_img(p, max(1, round(base * p['s'])), default) for p in parts]
    g = int(gap * base)
    W, H = max(i.width for i in ims), sum(i.height for i in ims) + g * (len(ims) - 1)
    k = min(w / W, h / H)
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    y = 0
    for i in ims:
        out.alpha_composite(i, ((W - i.width) // 2, y))
        y += i.height + g
    return out.resize((max(1, round(W * k)), max(1, round(H * k))), Image.LANCZOS)


def hexrgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def banner(bg, fg, parts, tag):
    W, H = BANNER
    top, bot = hexrgb(bg), hexrgb(bg)
    lum = sum(top) / 3
    # a slight vertical gradient, as a lit box is brighter in the middle
    img = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = abs(y / H - 0.45) * 2
        k = 1.06 - 0.12 * t if lum < 200 else 1.0 - 0.05 * t
        d.line([(0, y), (W, y)], fill=tuple(max(0, min(255, int(c * k))) for c in top))
    lg = stack(parts, int(W * 0.8), int(H * 0.4), fg)
    img.paste(lg, ((W - lg.width) // 2, int(H * 0.44 - lg.height / 2)), lg)
    if tag:
        fc = fg if fg not in (None, 'orig') else ('#111111' if lum > 128 else '#ffffff')
        t = text_img(T(tag, AVENIR, 0.32), 15, fc)
        img.paste(t, ((W - t.width) // 2, int(H * 0.82)), t)
        ln = Image.new('RGBA', (34, 2), fc)
        img.paste(ln, ((W - 34) // 2, int(H * 0.78)), ln)
    # a thin frame (the box's edge)
    d.rectangle((0, 0, W - 1, H - 1), outline=tuple(int(c * 0.8) for c in bot), width=3)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    sheet = []
    for bid, b in BRANDS.items():
        sign = row(b['sign'], SIGN_H, '#ffffff')
        sign.save(os.path.join(OUT, f'{bid}.png'), optimize=True)
        band_parts = b.get('band') or [dict(p, col=(p['col'] if p['col'] not in (None, '#ffffff') else '#1a1a1a'))
                                       for p in b['sign']]
        band = row(band_parts, SIGN_H, '#1a1a1a')
        band.save(os.path.join(OUT, f'{bid}_band.png'), optimize=True)
        bn = banner(*b['banner'])
        bn.save(os.path.join(OUT, f'{bid}_banner.jpg'), quality=86, optimize=True)
        sheet.append((bid, sign, band, bn))
    # a sheet for checking: the sign on dark stone, the band variant on white, the banner
    cw, ch = 700, 300
    cols = 4
    rows = (len(sheet) + cols - 1) // cols
    im = Image.new('RGB', (cols * cw, rows * ch), '#7a7f85')
    d = ImageDraw.Draw(im)
    for k, (bid, sign, band, bn) in enumerate(sheet):
        x, y = (k % cols) * cw, (k // cols) * ch
        d.rectangle((x + 6, y + 6, x + 470, y + 140), fill='#2b2d33')
        s = sign.copy()
        s.thumbnail((450, 110))
        im.paste(s, (x + 16, y + 20 + (110 - s.height) // 2), s)
        d.rectangle((x + 6, y + 150, x + 470, y + 290), fill='#f4f4f2')
        s = band.copy()
        s.thumbnail((450, 110))
        im.paste(s, (x + 16, y + 165 + (110 - s.height) // 2), s)
        bb = bn.copy()
        bb.thumbnail((200, 284))
        im.paste(bb, (x + 480, y + 8))
        d.text((x + 10, y + 2), bid, fill='#ffd')
    im.save(os.path.join(ROOT, 'build', 'brand_signs.png'))
    print(len(sheet), 'brands ->', OUT)


if __name__ == '__main__':
    main()
