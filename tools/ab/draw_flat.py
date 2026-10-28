"""Draw one flat of plans.json with walls, windows, doorways (with what they lead to) at 60 px/m.
    tools/ab/py tools/ab/draw_flat.py KEY FLAT OUT.png"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon, box
sys.path.insert(0, os.path.dirname(__file__))
from check_doors import openings
key, fi, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
P = json.load(open(os.path.join(os.path.dirname(__file__), '..', '..', 'blender', 'ab', 'plans.json')))[key]
a = P['apartments'][fi]
o = Polygon(a['outline']).buffer(1.2)
x0, y0, x1, y1 = o.bounds
S = 70
im = Image.new('RGB', (int((x1 - x0) * S), int((y1 - y0) * S)), 'white')
g = ImageDraw.Draw(im)
T = lambda p: ((p[0] - x0) * S, (y1 - p[1]) * S)
clip = box(x0, y0, x1, y1)
def poly(pts, **k):
    q = Polygon(pts).buffer(0).intersection(clip)
    for h in getattr(q, 'geoms', [q]):
        if h.geom_type == 'Polygon' and not h.is_empty:
            g.polygon([T(p) for p in h.exterior.coords], **k)
C = {'living': (255, 225, 170), 'bedroom': (190, 210, 255), 'kitchen': (255, 190, 190), 'hall': (230, 230, 205), 'bath': (170, 235, 235), 'wc': (150, 220, 225), 'storage': (215, 195, 235), 'loggia': (200, 240, 180), 'terrace': (170, 230, 150)}
for r in a['rooms'] + a['balconies']:
    poly(r['poly'], fill=C.get(r['kind'], (220, 220, 220)), outline=(120, 120, 120))
for w in P['walls'] + P['struct']:
    poly(w, fill=(30, 30, 30))
for w in P['windows'] + P['glazing']:
    poly(w, fill=(0, 170, 255))
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 13)
# FLAT_LANG=ru: the room names in Russian (for pictures sent to the client)
RU = {'living': 'Гостиная', 'bedroom': 'Спальня', 'kitchen': 'Кухня', 'hall': 'Холл', 'bath': 'Ванная', 'wc': 'С/У', 'storage': 'Кладовая', 'loggia': 'Лоджия', 'terrace': 'Терраса'}
rooms, ops = openings(P)
byid = {r['id']: r for r in rooms}
for r in rooms:
    if r['apt'] != fi:
        continue
    c = r['poly'].representative_point()
    name = RU.get(r['kind'], r['kind']) if os.environ.get('FLAT_LANG') == 'ru' else r['kind']
    g.text(T((c.x, c.y)), f"{name} {r['area']}", fill=(0, 0, 0), font=font, anchor='mm')
    for op in ops.get(r['id'], []):
        m = op['mid']
        g.ellipse([T((m.x, m.y))[0] - 5, T((m.x, m.y))[1] - 5, T((m.x, m.y))[0] + 5, T((m.x, m.y))[1] + 5], fill=(255, 0, 120))
        g.text((T((m.x, m.y))[0] + 6, T((m.x, m.y))[1]), f"{op['length']}", fill=(200, 0, 90), font=font)
# the side each drawn door opens to (an arrow from the doorway into that room)
for x0_, y0_, x1_, y1_ in P.get('swings', []):
    if o.contains(Polygon([(x0_ - 0.01, y0_), (x0_ + 0.01, y0_), (x0_, y0_ + 0.01)])):
        g.line([T((x0_, y0_)), T((x1_, y1_))], fill=(0, 140, 0), width=4)
        q = T((x1_, y1_))
        g.ellipse([q[0] - 4, q[1] - 4, q[0] + 4, q[1] + 4], fill=(0, 140, 0))
im.save(out)
