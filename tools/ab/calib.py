"""Find the camera of a client render: position, heading, focal length and the shift of a
2-point perspective (the renders keep verticals vertical) from points picked on the render whose
place in the model is known (block corners at the roof and at the podium).

    tools/ab/py tools/ab/calib.py tools/ab/calib_points.json [NAME]

Scene metres as the viewer: x east, y up, z south. Prints the camera for tools/views.mjs
({ pos, yaw, f, v0 }) and the error at each point.
"""
import json
import math
import sys

import numpy as np
from scipy.optimize import least_squares


def project(params, P, W):
    cx, cy, cz, yaw, f, v0 = params
    fwd = np.array([math.sin(yaw), 0.0, -math.cos(yaw)])
    right = np.array([math.cos(yaw), 0.0, math.sin(yaw)])
    d = P - np.array([cx, cy, cz])
    xc, yc, zc = d @ right, d[:, 1], d @ fwd
    return np.stack([W / 2 + f * xc / zc, v0 - f * yc / zc], axis=1)


def fit(view):
    W, H = view['size']
    P = np.array([p['xyz'] for p in view['points']], float)
    uv = np.array([p['uv'] for p in view['points']], float)
    g = view.get('guess', {})
    x0 = [*g.get('pos', [0, 30, 500]), math.radians(g.get('yaw', 0)), g.get('f', 3000), g.get('v0', H * 0.8)]
    best = None
    # a few starting headings and distances: the fit has local minima
    for dyaw in (-30, -15, 0, 15, 30):
        for scale in (0.6, 1.0, 1.6):
            s = list(x0)
            s[3] += math.radians(dyaw)
            s[0] *= scale
            s[2] *= scale
            s[4] *= scale
            r = least_squares(lambda q: (project(q, P, W) - uv).ravel(), s, loss='soft_l1', f_scale=4.0)
            if best is None or r.cost < best.cost:
                best = r
    q = best.x
    err = project(q, P, W) - uv
    return q, err


def main():
    data = json.load(open(sys.argv[1]))
    names = sys.argv[2:] or list(data)
    for name in names:
        view = data[name]
        q, err = fit(view)
        cx, cy, cz, yaw, f, v0 = q
        W, H = view['size']
        fov = 2 * math.degrees(math.atan(H / 2 / f))
        print(f"{name}: pos [{cx:.1f}, {cy:.1f}, {cz:.1f}]  yaw {math.degrees(yaw):.2f} deg  f {f:.0f} px (vfov {fov:.2f})  v0 {v0:.0f}")
        for p, e in zip(view['points'], err):
            print(f"   {p['name']:14s} err {e[0]:6.1f} {e[1]:6.1f}")
        print('   rms', round(float(np.sqrt((err ** 2).sum(axis=1).mean())), 2), 'px')
        print('   view:', json.dumps({'cam': {'pos': [round(cx, 1), round(cy, 1), round(cz, 1)], 'yaw': round(math.degrees(yaw), 3),
                                               'f': round(f, 1), 'v0': round(v0, 1), 'size': [W, H]}}))


if __name__ == '__main__':
    main()
