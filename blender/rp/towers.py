"""The three residential blocks, floor by floor from the sales book's plans (blender/rp/plans.json,
tools/rp/extract.py), dressed in the look of the client's renders (00_Материалы_клиента/Рендеры) and
the developer's model (фото макета):

  - the plan's walls and concrete stand as drawn (light grey-blue cladding outside); the windows are
    the plan's windows (dark glass in black frames);
  - white pilasters where the sheets draw them (the grey outlines on the facades), a white band at
    every slab: the white grid of the renders;
  - balconies: white slab edge, glass railing; their back walls warm wood (the lit loggias of the
    night renders); on Б's face to кӯчаи Ҳусейнзода the balconies are glazed floor to ceiling (the
    big glass corner of renders 1 and 2);
  - the crown: a tall white frame with posts and a railing round the roof terrace, solar panels.

Every apartment floor is two objects (slab, walls) tagged tower / floor / part: the viewer hides the
floors above an opened one; floors that look the same share their meshes.
"""
import math

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from complex.geom import MeshBuilder, get_collection, log_tree, make_object
from complex.towers import add_rails, pick_material, solar_field

from .config import BLOCKS, FIRST_FLAT_FLOOR, SLAB, height, level

WALL = {'A': 'Facade white', 'B': 'Facade white', 'V': 'Facade white'}   # (the model's white stone)
SILL, HEAD = 0.45, 0.35
PANORAMIC = 2.4   # m: windows this long on the sheets are the model's dark curtain-glass strips
GLASS_FACE = {'B': lambda x, y: x > 12.5}   # Б: the balconies on the east face are glazed full height


def P(p):
    g = Polygon(p).buffer(0)
    return max(g.geoms, key=lambda q: q.area) if g.geom_type == 'MultiPolygon' else g


def U(polys, grow=0.0):
    return unary_union([P(p).buffer(grow, join_style='mitre') for p in polys if len(p) >= 3])


def parts(g):
    if g.is_empty:
        return []
    return [q for q in getattr(g, 'geoms', [g]) if q.geom_type == 'Polygon']


def outdoor_rooms(plan):
    return [P(r['poly']) for a in plan['apartments'] for r in a['rooms'] + a['balconies'] if r['kind'] in ('loggia', 'terrace')]


def axis(q):
    """long axis of a quad: (centre, u (along), v (across), length, thickness)"""
    r = q.minimum_rotated_rectangle
    c = list(r.exterior.coords)[:4]
    e1 = (c[1][0] - c[0][0], c[1][1] - c[0][1])
    e2 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
    l1, l2 = math.hypot(*e1), math.hypot(*e2)
    if l1 < l2:
        e1, e2, l1, l2 = e2, e1, l2, l1
    u = (e1[0] / l1, e1[1] / l1)
    v = (-u[1], u[0])
    ct = r.centroid
    return (ct.x, ct.y), u, v, l1, l2


def pane(mb, c, u, v, L, t, off, z0, z1, glass, frame='Frame dark', mullion=1.5, fw=0.06):
    """a glazed opening across a wall: glass at offset `off` across the wall, a frame round it and
    mullions about every `mullion` metres"""
    cx, cy = c[0] + v[0] * off, c[1] + v[1] * off
    rot = math.atan2(u[1], u[0])
    mb.box(cx, cy, z0, L, 0.03, z1 - z0, glass, rot=rot)
    for zz in (z0, z1 - fw):
        mb.box(cx, cy, zz, L, 0.09, fw, frame, rot=rot)
    n = max(1, round(L / mullion))
    for k in range(n + 1):
        s = -L / 2 + L * k / n
        s = max(-L / 2 + fw / 2, min(L / 2 - fw / 2, s))
        mb.box(cx + u[0] * s, cy + u[1] * s, z0, fw, 0.09, z1 - z0, frame, rot=rot)


def facade_floor(mb, block, plan, h, top=False):
    key = block['key']
    enc = P(plan['enclosure'])
    outside = box(*enc.buffer(30).bounds).difference(enc)
    out_rooms = outdoor_rooms(plan)
    outdoor = unary_union(out_rooms) if out_rooms else Polygon()
    air = outside.union(outdoor)
    glass_face = GLASS_FACE.get(key, lambda x, y: False)
    wall_mat = WALL[key]
    # walls and concrete as drawn (the inner ones show through the windows); the back walls of the
    # balconies light, as on the renders (warm wood there read as red from afar)
    for w in plan['walls'] + plan['struct']:
        g = P(w)
        if g.area < 0.01:
            continue
        # (the back walls of the loggias: warm beige, as on the developer's model)
        back = not outdoor.is_empty and g.distance(outdoor) < 0.06 and g.distance(outside) > 0.3
        mb.prism(g, 0.0, h, 'Loggia beige' if back else wall_mat, 'Loggia beige' if back else wall_mat)
    # windows: dark glass in black frames, wall below and above
    for wq in plan['windows']:
        g = P(wq)
        c, u, v, L, t = axis(g)
        if L < 0.3:
            continue
        to_balcony = not outdoor.is_empty and g.distance(outdoor) < 0.12
        # the side the outside is on
        s_out = 1 if air.contains(Point(c[0] + v[0] * (t / 2 + 0.15), c[1] + v[1] * (t / 2 + 0.15))) else -1
        if L >= PANORAMIC and not to_balcony:
            # a panoramic strip (the model's dark curtain glass): floor to floor in a black grid,
            # a dark panel over the slab's white band
            pane(mb, c, u, v, L, t, s_out * (t / 2 - 0.08), 0.0, h, 'Window glass', frame='Frame dark', mullion=1.0)
            # (flush with the white band it hides: 1 cm proud of it, no ledge)
            fc = (c[0] + v[0] * s_out * (t / 2 + 0.055), c[1] + v[1] * s_out * (t / 2 + 0.055))
            mb.box(fc[0], fc[1], -0.33, L - 0.02, 0.11, 0.48, 'Facade dark', rot=math.atan2(u[1], u[0]))
            continue
        sill = 0.0 if to_balcony else SILL
        if sill > 0:
            mb.prism(g, 0.0, sill, wall_mat, wall_mat)
        mb.prism(g, h - HEAD, h, wall_mat, wall_mat, wall_mat)
        pane(mb, c, u, v, L, t, s_out * (t / 2 - 0.08), sill, h - HEAD, 'Window glass', mullion=1.4 if not to_balcony else 0.9)
    # glazing drawn in the plan (cyan): balcony rails, or glass floor to ceiling
    for gq in plan['glazing']:
        g = P(gq)
        if g.area < 0.004:
            continue
        c, u, v, L, t = axis(g)
        if L < 0.25:
            continue
        on_balcony = not outdoor.is_empty and g.distance(outdoor) < 0.15
        if on_balcony and not glass_face(*c):
            add_rails(mb, [[(c[0] - u[0] * L / 2, c[1] - u[1] * L / 2), (c[0] + u[0] * L / 2, c[1] + u[1] * L / 2)]], 0.0, post_step=0)
        else:
            pane(mb, c, u, v, L, t, 0.0, 0.0, h - 0.05, 'Tower glass', frame='Frame dark', mullion=1.0)
    # balcony parapets: glass railings (or, on Б's glazed face, glass to the ceiling)
    for pq in plan.get('parapets', []):
        g = P(pq)
        c, u, v, L, t = axis(g)
        if L < 0.25:
            continue
        a = (c[0] - u[0] * L / 2, c[1] - u[1] * L / 2)
        b = (c[0] + u[0] * L / 2, c[1] + u[1] * L / 2)
        if glass_face(*c):
            pane(mb, c, u, v, L, t, 0.0, 0.0, h - 0.05, 'Tower glass', frame='Frame dark', mullion=1.0)
        else:
            add_rails(mb, [[a, b]], 0.0, post_step=0)
    # the white pilasters (grey outlines on the sheets), through the slab bands
    for q in plan.get('pilasters', []):
        mb.prism_chamfer(P(q), -0.25, h, 'Stone white', 'Stone white' if top else None, None, c=0.02)


def slab_mesh(mb, plan, h):
    enc = P(plan['enclosure'])
    mb.prism(enc.buffer(-0.04, join_style='mitre'), -0.25, SLAB, 'Stone white', 'Shop floor', 'Stone white')
    ring = enc.buffer(0.1, join_style='mitre').difference(enc.buffer(-0.04, join_style='mitre'))
    mb.prism_chamfer(ring, -0.32, 0.14, 'White band', 'White band', 'White band', c=0.02)


def crown(mb, block, plan, zr):
    """the roof: a terrace with a tall white parapet frame, posts, a railing; plant rooms over the
    stairs and lifts; solar panels; planters with small trees"""
    enc = P(plan['enclosure'])
    roof = enc.buffer(-0.05, join_style='mitre')
    mb.prism(roof, zr - 0.25, zr + 0.15, 'Stone white', 'Roof', None)
    ring = enc.buffer(0.18, join_style='mitre').difference(enc.buffer(-0.3, join_style='mitre'))
    mb.prism_chamfer(ring, zr - 0.3, zr + 1.15, 'Stone white', 'White band', None, c=0.02)
    # the crown band, standing proud
    band = enc.buffer(0.55, join_style='mitre').difference(enc.buffer(0.05, join_style='mitre'))
    mb.prism_chamfer(band, zr + 0.6, zr + 1.35, 'White band', 'White band', 'White band', c=0.03)
    # the frame's posts and top rail (renders: a white frame over the terrace edge)
    line = enc.buffer(0.3, join_style='mitre').exterior
    L = line.length
    n = max(8, int(L / 6.5))
    for k in range(n):
        p = line.interpolate(k * L / n)
        mb.box(p.x, p.y, zr + 1.35, 0.35, 0.35, 2.6, 'Stone white')
    top_ring = enc.buffer(0.45, join_style='mitre').difference(enc.buffer(0.12, join_style='mitre'))
    mb.prism_chamfer(top_ring, zr + 3.95, zr + 4.35, 'White band', 'White band', 'White band', c=0.03)
    # the light lines of the night renders: round the crown band and the frame's top rail
    for zz in (zr + 1.36, zr + 3.92):
        line_ring = enc.buffer(0.57 if zz < zr + 2 else 0.47, join_style='mitre').difference(enc.buffer(0.5 if zz < zr + 2 else 0.4, join_style='mitre'))
        mb.prism(line_ring, zz, zz + 0.05, 'Night line', 'Night line', 'Night line')
    # railing on the parapet
    pts = list(enc.buffer(-0.12, join_style='mitre').exterior.coords)
    mb.tube(pts, [zr + 1.15] * len(pts), [zr + 2.2] * len(pts), 0.04, 'Frame dark', closed=True)
    # plant rooms over the stairs and lift halls
    core = unary_union([P(c) for c in plan['common']]).buffer(0.3, join_style='mitre')
    for lf in plan.get('lifts', []):
        core = core.union(P(lf['shaft']).buffer(0.3, join_style='mitre'))
    core = core.intersection(roof.buffer(-1.5))
    for q in parts(core.buffer(0.6).buffer(-0.6)):
        if q.area < 6:
            continue
        q = q.simplify(0.3)
        mb.prism_chamfer(q, zr + 0.15, zr + 3.6, 'Stone white', None, None, c=0.02)
        mb.prism(q.buffer(0.25, join_style='mitre'), zr + 3.6, zr + 3.9, 'White band', 'Roof', 'White band')
    # solar panels on the free roof (the renders' roofs: plant rooms and panels, no trees - the
    # small trees along the edge read as trees standing in the sky)
    free = roof.buffer(-2.2).difference(core.buffer(1.2))
    solar_field(mb, free, zr + 0.15, angle=0)


def frame(b):
    a = math.radians(b['rot'])
    cx, cy = b['centre']
    ca, sa = math.cos(a), math.sin(a)
    return a, (lambda x, y: (cx + ca * x - sa * y, cy + sa * x + ca * y))


def footprint(key, plans):
    b = BLOCKS[key]
    _, to_site = frame(b)
    return Polygon([to_site(x, y) for x, y in plans[b['plans'][FIRST_FLAT_FLOOR]]['enclosure']]).buffer(0)


def build_block(key, mats, root_col, plans):
    b = BLOCKS[key]
    b['key'] = key
    col = get_collection(f'Block {key}', root_col)
    a, to_site = frame(b)
    cx, cy = b['centre']

    def put(ob, z=0.0):
        ob.location = (cx, cy, z)
        ob.rotation_euler = (0, 0, a)
        return ob

    cache, floors = {}, []
    pick_col = get_collection(f'Picking {key}', col)
    top_floor = b['floors']
    for f in range(FIRST_FLAT_FLOOR, top_floor + 1):
        pk = b['plans'][f]
        z, h = level(f), height(f)
        ck = (pk, f == top_floor)
        if ck not in cache:
            sm, wm = MeshBuilder(), MeshBuilder()
            slab_mesh(sm, plans[pk], h)
            facade_floor(wm, b, plans[pk], h, top=f == top_floor)
            nm = f'{key} {pk} {len(cache)}'
            cache[ck] = (sm.to_mesh(nm + ' slab', mats), wm.to_mesh(nm + ' walls', mats))
        sm, wm = cache[ck]
        for part, me in (('slab', sm), ('walls', wm)):
            ob = put(make_object(f"{key} {'floor' if part == 'slab' else 'walls'} {f:02d}", me, col), z)
            ob['tower'], ob['floor'], ob['part'] = key, f, part
        for i, apt in enumerate(plans[pk]['apartments']):
            mb = MeshBuilder()
            mb.prism(P(apt['outline']).buffer(0.2, join_style='mitre').simplify(0.1), -0.15, h - 0.1, 'Pick', 'Pick', 'Pick')
            nm = f'pick {key} {f:02d} {i}'
            ob = put(make_object(nm, mb.to_mesh(nm, {'Pick': pick_material()}), pick_col), z + SLAB)
            ob['tower'], ob['floor'], ob['unit'], ob['pick'] = key, f, i, 1
            ob.hide_render = True
        floors.append(dict(floor=f, z=round(z, 3), h=round(h, 3), plan=pk))
    top = plans[b['plans'][top_floor]]
    zr = level(top_floor + 1)
    mb = MeshBuilder()
    crown(mb, b, top, zr)
    ob = put(make_object(f'{key} roof', mb.to_mesh(f'{key} roof', mats), col))
    ob['tower'], ob['part'] = key, 'roof'
    return dict(key=key, label=b['label'], tj=b['tj'], centre=[round(v, 3) for v in b['centre']], rot=round(b['rot'], 3),
                plan_centre=[0.0, 0.0], slab=SLAB, floors=floors, levels=top_floor, top=round(zr, 3), sales=True,
                outline=[[round(x, 2), round(y, 2)] for x, y in footprint(key, plans).exterior.coords])
