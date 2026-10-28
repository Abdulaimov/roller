"""Shared parts: slab edge bands, glass rails, the roof's solar panels and the invisible picking material."""
import math

import numpy as np
from shapely.geometry import Polygon

SLAB = 0.32        # slab top above floor level datum
SLAB_BELOW = 0.18  # band continues below floor level
RAIL = 1.05        # glass rail height
FASCIA = 0.42      # solid white upstand on the balcony edge, under the glass rail


def add_rails(mb, segs, z, h=RAIL, mat='Railing glass', post_step=1.2):
    for seg in segs:
        # solid white upstand, then glass
        if len(seg) > 1:
            mb.tube(seg, [z - 0.05] * len(seg), [z + FASCIA] * len(seg), 0.16, 'White band')
        mb.ribbon(seg, z + FASCIA, z + h, mat, double=True)
        # slim metal handrail on posts (glass held between them)
        zs0 = [z + h - 0.04] * len(seg)
        zs1 = [z + h + 0.02] * len(seg)
        if len(seg) > 1:
            mb.tube(seg, zs0, zs1, 0.06, 'Frame')
        if post_step and len(seg) > 1:
            P = np.array(seg, float)
            d = np.linalg.norm(np.diff(P, axis=0), axis=1)
            s = np.concatenate([[0.0], np.cumsum(d)])
            total = s[-1]
            for k in range(int(total // post_step) + 1):
                at = min(total, k * post_step + (total - post_step * int(total // post_step)) / 2)
                i = min(int(np.searchsorted(s, at, side='right')) - 1, len(d) - 1)
                f = (at - s[i]) / max(d[i], 1e-9)
                q = P[i] + (P[i + 1] - P[i]) * f
                t = (P[i + 1] - P[i]) / max(d[i], 1e-9)
                mb.box(q[0], q[1], z + FASCIA, 0.04, 0.05, h - FASCIA - 0.04, 'Metal', rot=math.atan2(t[1], t[0]))


def slab_band(mb, slab, z, top='White band'):
    mb.prism_chamfer(slab, z - SLAB_BELOW, z + SLAB, 'White band', top, 'White band', c=0.025)


# ----------------------------------------------------------------------------
# Residential tower
# ----------------------------------------------------------------------------

def pick_material():
    """Plain material for the invisible pick volumes (the viewer replaces it)."""
    import bpy
    m = bpy.data.materials.get('Pick')
    if m is None:
        m = bpy.data.materials.new('Pick')
        m.diffuse_color = (1, 1, 1, 0.2)
    return m


def solar_field(mb, area, z, angle=-30, pw=1.0, pl=1.7, row=4.6, group=6, gap=3.6):
    """Strips of tilted PV panels; the field is rotated by `angle` degrees like on the renders."""
    if area.is_empty:
        return
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    minx, miny, maxx, maxy = area.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    R = max(maxx - minx, maxy - miny)
    tilt = math.radians(18)
    v = -R
    row_i = 0
    while v < R:
        u = -R + (row_i % 2) * 2.5
        while u < R:
            for k in range(group):
                uu = u + k * (pw + 0.04)
                x = cx + ca * uu - sa * v
                y = cy + sa * uu + ca * v
                corners = [(x + ca * du - sa * dv, y + sa * du + ca * dv)
                           for du, dv in [(-pw / 2, -pl / 2), (pw / 2, -pl / 2), (pw / 2, pl / 2), (-pw / 2, pl / 2)]]
                if not area.contains(Polygon(corners)):
                    continue
                for dv2 in (0.0, pl + 0.05):
                    cc = [(px - sa * dv2, py + ca * dv2) for px, py in corners]
                    if not area.contains(Polygon(cc)):
                        continue
                    zl = z + 0.3 + dv2 * math.sin(tilt) * 0.0
                    zh = zl + pl * math.sin(tilt)
                    c0, c1 = cc[:2], cc[2:]
                    mb.face([(*c0[0], zl), (*c0[1], zl), (*c1[0], zh), (*c1[1], zh)], 'Solar panel')
                    mb.face([(*c1[1], zh), (*c1[0], zh), (*c0[1], zl), (*c0[0], zl)], 'Frame')
            u += group * (pw + 0.04) + gap
        v += row
        row_i += 1


def longest_run(mask):
    """Indices of the longest cyclic run of True values in a boolean array."""
    n = len(mask)
    if mask.all():
        return list(range(n))
    if not mask.any():
        return []
    f = int(np.where(~mask)[0][0])
    runs, cur = [], []
    for i in np.roll(np.arange(n), -f):
        if mask[i]:
            cur.append(int(i))
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return max(runs, key=len)
