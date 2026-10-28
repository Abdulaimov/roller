"""The Regnum Plaza sales book (Китоби Фуруш А-Б-В RPD.pdf): sheets, blocks and their axes.

Every plan sheet draws the three blocks in their true places at one scale (about 1:300, 9.52 pt to
the metre). A block's axes are found from the lettered bubbles (the PDF keeps their text) and set
exactly on the green axis lines of the drawing; plan metres are counted from the middle of the
block's axes, x along the sheet to the right, y up the sheet.

    tools/ab/py tools/rp/sheet.py        # prints the axis fit of every sheet
"""
import os
import re

import numpy as np
import pymupdf

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
PDF = os.path.join(ROOT, '..', '00_Материалы_клиента', 'Китоби Фуруш А-Б-В RPD.pdf')

# sheet -> page index in the PDF
PAGES = {'b2': 8, 'b1': 9, 's1': 10, 's1m': 11, 's2': 12, 'f3': 13, 'typ': 14, 'f19': 15, 'f23': 16, 'f25': 17}

# axes of each block: bubble labels and their positions in metres (from the dimension chains)
AXES = {
    'A': dict(x=['1а', '2а', '3а', '4а', '5а'], xm=[0, 7.0, 13.0, 19.0, 26.0],
              y=['Аа', 'Ба', 'Ва', 'Га', 'Да', 'Еа'], ym=[0, 7.4, 14.0, 20.6, 27.6, 29.2]),
    'B': dict(x=['Аб', 'Бб', 'Вб', 'Гб', 'Дб', 'Еб', 'Жб'], xm=[0, 6.5, 13.0, 18.4, 25.6, 28.0, 29.6],
              y=['1б', '2б', '3б', '4б', '5б', '6б', '7б'], ym=[0, 6.5, 13.0, 20.0, 25.6, 28.0, 29.6]),
    'V': dict(x=['1в', '2в', '3в', '4в', '5в', '6в', '7в', '8в', '9в', '10в', '11в', '12в'],
              xm=[0, 6.0, 12.5, 19.0, 25.8, 27.25, 28.7, 35.5, 42.0, 48.5, 55.3, 56.7],
              y=['Ав', 'Бв', 'Вв', 'Гв', 'Дв'], ym=[0, 7.0, 13.0, 19.0, 26.0]),
}
# on the shop sheets some letters of block Б are misprinted with the В suffix
ALIAS = {'B': {'Вб': ['Бв'], 'Гб': ['Гв'], 'Дб': ['Дв'], 'Еб': ['Ев'], 'Жб': ['Жв']}}

GREEN = np.array([116, 196, 36])
DPI = 600


def doc():
    return pymupdf.open(PDF)


def labels(pg):
    out = {}
    for b in pg.get_text('dict')['blocks']:
        for line in b.get('lines', []):
            for s in line['spans']:
                if s['size'] < 6:
                    continue
                for tok in s['text'].split():
                    if re.fullmatch(r'(\d{1,2}|[АБВГДЕЖ])[абв]', tok):
                        x0, y0, x1, y1 = s['bbox']
                        out.setdefault(tok, []).append(((x0 + x1) / 2, (y0 + y1) / 2))
    return out


class Frame:
    """plan metres <-> sheet points for one block on one sheet"""

    def __init__(self, key, s, x0, y0):
        a = AXES[key]
        self.key, self.s = key, s
        self.cxm = (a['xm'][0] + a['xm'][-1]) / 2   # the middle of the axes, in axis metres
        self.cym = (a['ym'][0] + a['ym'][-1]) / 2
        self.x0, self.y0 = x0, y0                    # sheet point of axis 0 / 0

    def to_plan(self, x, y):
        return ((x - self.x0) / self.s - self.cxm, (self.y0 - y) / self.s - self.cym)

    def to_sheet(self, X, Y):
        return (self.x0 + (X + self.cxm) * self.s, self.y0 - (Y + self.cym) * self.s)

    def axes_rect(self, margin=3.5):
        a = AXES[self.key]
        x0, y1 = self.to_sheet(-self.cxm - margin, -self.cym - margin)
        x1, y0 = self.to_sheet(a['xm'][-1] - self.cxm + margin, a['ym'][-1] - self.cym + margin)
        return pymupdf.Rect(x0, y0, x1, y1)


def green_cols(pg, rect, vertical):
    """count of axis-green pixels per sheet column (vertical lines) or row, at DPI"""
    pix = pg.get_pixmap(dpi=DPI, clip=rect, alpha=False)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).astype(np.int16)
    g = (np.abs(a - GREEN).max(axis=2) < 40)
    prof = g.sum(axis=0 if vertical else 1)
    return prof, pix


def fit(pg, key):
    """least-squares axis fit of a block from its bubbles, refined on the green axis lines"""
    a, lab = AXES[key], labels(pg)
    alias = ALIAS.get(key, {})

    def found(name, axis):
        cands = lab.get(name, []) + [p for al in alias.get(name, []) for p in lab.get(al, [])]
        return cands

    pts = {}
    for axis in ('x', 'y'):
        rows = []
        for name, m in zip(a[axis], a[axis + 'm']):
            c = found(name, axis)
            if not c:
                continue
            rows.append((m, c))
        # a label printed twice (a misprint of another block's letter, or the balcony line «Аа»):
        # the bubble in line with the block's other bubbles of this direction
        k = 1 if axis == 'x' else 0
        ref = np.median([c[0][k] for m, c in rows if len(c) == 1])
        pts[axis] = [(m, min(c, key=lambda q: (abs(q[k] - ref), q[1]))[1 - k]) for m, c in rows]
    # first estimate: scale from both directions together
    xs = np.array(pts['x']); ys = np.array(pts['y'])
    sx, bx = np.polyfit(xs[:, 0], xs[:, 1], 1)
    sy, by = np.polyfit(ys[:, 0], ys[:, 1], 1)   # sy < 0 (y down the sheet)
    s = (sx - sy) / 2
    # refine each axis on its green line
    fr = Frame(key, s, bx, by)
    rect = fr.axes_rect(1.0)
    out = {}
    for axis in ('x', 'y'):
        prof, pix = green_cols(pg, rect, vertical=(axis == 'x'))
        k = 72 / DPI
        rows = []
        for m in a[axis + 'm']:
            v0 = bx + s * m if axis == 'x' else by - s * m
            i0 = (v0 - (rect.x0 if axis == 'x' else rect.y0)) / k
            lo, hi = int(max(0, i0 - 0.35 * s / k)), int(min(len(prof) - 1, i0 + 0.35 * s / k))
            seg = prof[lo:hi + 1]
            if seg.size and seg.max() > 0.25 * (pix.h if axis == 'x' else pix.w):
                i = lo + int(np.argmax(seg))
                rows.append((m, (rect.x0 if axis == 'x' else rect.y0) + (i + 0.5) * k))
            else:
                rows.append((m, v0))
        out[axis] = np.array(rows)
    sx, bx = np.polyfit(out['x'][:, 0], out['x'][:, 1], 1)
    sy, by = np.polyfit(out['y'][:, 0], out['y'][:, 1], 1)
    res = max(np.abs(out['x'][:, 1] - (bx + sx * out['x'][:, 0])).max() / sx,
              np.abs(out['y'][:, 1] - (by + sy * out['y'][:, 0])).max() / -sy)
    return Frame(key, (sx - sy) / 2, bx, by), res


if __name__ == '__main__':
    d = doc()
    for sheet, pno in PAGES.items():
        if sheet in ('b2', 'b1'):
            continue
        for key in ('A', 'B', 'V'):
            try:
                fr, res = fit(d[pno], key)
            except Exception as e:  # a block missing from the sheet
                print(sheet, key, 'no axes', e)
                continue
            print(f'{sheet:4s} {key} s={fr.s:.4f} pt/m  origin=({fr.x0:.2f}, {fr.y0:.2f})  worst axis off {res * 100:.1f} cm')
