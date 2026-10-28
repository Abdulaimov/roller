"""The shop signs' artwork for the sign layer (src/signs.js, public/signs/signs.json): white letters on
a transparent ground, cut close, 256 px high, one PNG a sign. Real logos supplied later simply replace
these files (any width; the height in metres is set in signs.json).
    tools/ab/py tools/ab/make_signs.py"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'public', 'signs')
F = '/System/Library/Fonts/'
S = F + 'Supplemental/'
# name: text, font file, face index, tracking (em), colour
SIGNS = {
    # the brands the developer asked to see (a concept: not confirmed tenants)
    'boss': ('BOSS', F + 'HelveticaNeue.ttc', 1, 0.06, (255, 255, 255)),
    'lacoste': ('LACOSTE', F + 'Avenir Next.ttc', 2, 0.16, (255, 255, 255)),
    # neutral signs, to be replaced by the real tenants'
    'boutique': ('BOUTIQUE', S + 'Didot.ttc', 0, 0.2, (255, 248, 236)),
    'cafe': ('CAFÉ', S + 'Futura.ttc', 0, 0.22, (255, 244, 226)),
    'fashion': ('FASHION', F + 'Avenir Next.ttc', 5, 0.24, (255, 255, 255)),
    'beauty': ('BEAUTY', F + 'Optima.ttc', 0, 0.22, (255, 248, 240)),
    'optics': ('OPTICS', F + 'HelveticaNeue.ttc', 10, 0.2, (255, 255, 255)),
    'store': ('STORE', F + 'Avenir Next.ttc', 2, 0.26, (255, 255, 255)),
}
H = 256

os.makedirs(OUT, exist_ok=True)
meta = {}
for name, (text, path, index, track, col) in SIGNS.items():
    size = 200
    font = ImageFont.truetype(path, size, index=index)
    gap = track * size
    widths = [font.getlength(ch) for ch in text]
    W = int(sum(widths) + gap * (len(text) - 1)) + 40
    img = Image.new('RGBA', (W, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 20
    for ch, w in zip(text, widths):
        d.text((x, H), ch, font=font, fill=col + (255,), anchor='ls')
        x += w + gap
    box = img.getbbox()
    img = img.crop((box[0] - 8, box[1] - 8, box[2] + 8, box[3] + 8))
    img = img.resize((max(1, round(img.width * H / img.height)), H), Image.LANCZOS)
    img.save(os.path.join(OUT, f'{name}.png'))
    meta[name] = dict(text=text, aspect=round(img.width / img.height, 4))
print(json.dumps(meta, ensure_ascii=False, indent=1))
