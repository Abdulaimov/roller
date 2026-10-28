"""Room names from the lettering of the plan sheets.

The names are drawn as outlined glyphs (blue fills), not text. Each room carries two lines: its name
("Спальня") and its area ("19,61м²"). The area line is the one with a comma; the name is told by its
length in cap heights (the words differ in length: С/У < Холл < Кухня, Ванна < Спальня < Гостиная, Гардероб).
"""
import numpy as np
from shapely.ops import unary_union

GLYPH_FILL = (0.0, 0.0, 1.0)


def glyphs(by):
    from extract_plan import parts
    return parts(unary_union([p.buffer(0.01) for p in by.get(GLYPH_FILL, [])]))


def lines_in(room_poly, gl):
    """Glyphs inside a room, grouped into lines. Returns (lines, axis): axis 0 = text runs along x."""
    g = [q for q in gl if room_poly.contains(q.centroid)]
    if not g:
        return [], None
    best = None
    for axis in (0, 1):
        perp = 1 - axis
        items = sorted(g, key=lambda q: q.centroid.coords[0][perp])
        groups = []
        for q in items:
            c = q.centroid.coords[0][perp]
            if groups and abs(c - groups[-1][-1][1]) < 0.16:
                groups[-1].append((q, c))
            else:
                groups.append([(q, c)])
        # the right axis gives lines that are long along it and thin across it
        aspects = []
        for grp in groups:
            b = np.array([q.bounds for q, _ in grp])
            along = b[:, 2 + axis].max() - b[:, axis].min()
            across = b[:, 3 - axis].max() - b[:, 1 - axis].min()
            aspects.append(along / max(across, 1e-6))
        score = -float(np.mean(aspects))
        if best is None or score < best[0]:
            best = (score, axis, [[q for q, _ in grp] for grp in groups])
    return best[2], best[1]


def describe(line, axis):
    b = np.array([q.bounds for q in line])  # x0 y0 x1 y1
    lo, hi = b[:, axis].min(), b[:, axis + 2].max()
    hs = b[:, 3 - axis] - b[:, 1 - axis]   # extent across the line
    ws = b[:, 2 + axis] - b[:, axis]
    cap = hs.max()
    small = [(w, h) for w, h in zip(ws, hs) if max(w, h) < 0.125 and min(w, h) < 0.1]
    return dict(length=hi - lo, cap=cap, n=len(line), comma=bool(small), rel=(hi - lo) / max(cap, 1e-6))


def room_name(room_poly, gl):
    ls, axis = lines_in(room_poly, gl)
    if not ls:
        return None
    d = [describe(l, axis) for l in ls]
    names = [x for x in d if not x['comma'] and x['n'] >= 2]
    if not names:
        return dict(lines=d, name=None)
    nm = max(names, key=lambda x: x['length'])
    return dict(lines=d, name=nm)
