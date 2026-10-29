"""The camera of each client render (00_Материалы_клиента/Рендеры, the sales book's sheets 1-8),
fitted to points picked on the render whose place on the sheets is known: the corners of the blocks
at the crown's top and at the roof, the podium's corners. So the model can be shot as the render was
taken (tools/rp/match_shot.mjs) and the two compared, not from a view that only looks alike.

    tools/ab/py tools/rp/calib.py [NAME ...]      # tools/rp/calib_points.json -> tools/rp/cameras.json

Points: `sheet` [x, y] in the sales book's frame (block Б's middle at 0, x towards кӯчаи Ҳусейнзода,
y towards кӯчаи Нарзиқулова, metres), `z` the height (m), `uv` the pixel in the render scaled to
1600 px wide. Two camera models:
  level   - the street renders (1-3, 6, 7): level, verticals vertical, the frame shifted up or down
            (a 2-point perspective): position, heading, focal length, the horizon's row
  pinhole - the aerial renders (4, 5, 8): position, heading, pitch, focal length, centred
The residual at each point says how far the model's corner is from the render's (px): large ones
where the render and the model disagree (a block placed or sized otherwise, a crown of another
height) - printed, and kept in cameras.json for the audit.
"""
import json
import math
import os
import sys

import numpy as np
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
ROT = -49.5   # the sheet's frame on the ground (blender/rp/config.py)


def to_scene(sheet, z):
    """sheet metres -> the viewer's scene (x east, y up, z south; site origin, src/config.js)"""
    a = math.radians(ROT)
    x, y = sheet
    sx, sy = math.cos(a) * x - math.sin(a) * y, math.sin(a) * x + math.cos(a) * y
    return np.array([sx, z, -sy])


def basis(yaw, pitch):
    fwd = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), -math.cos(yaw) * math.cos(pitch)])
    right = np.array([math.cos(yaw), 0.0, math.sin(yaw)])
    up = np.cross(right, fwd)
    return fwd, right, up


def project(model, q, P, W, H):
    if model == 'level':
        cx, cy, cz, yaw, f, v0 = q
        fwd, right, up = basis(yaw, 0.0)
        d = P - np.array([cx, cy, cz])
        xc, yc, zc = d @ right, d[:, 1], d @ fwd
        return np.stack([W / 2 + f * xc / zc, v0 - f * yc / zc], axis=1)
    cx, cy, cz, yaw, pitch, f = q
    fwd, right, up = basis(yaw, pitch)
    d = P - np.array([cx, cy, cz])
    xc, yc, zc = d @ right, d @ up, d @ fwd
    return np.stack([W / 2 + f * xc / zc, H / 2 - f * yc / zc], axis=1)


def fit(view):
    W, H = view['size']
    model = view.get('model', 'level')
    P = np.array([to_scene(p['sheet'], p['z']) for p in view['points']])
    uv = np.array([p['uv'] for p in view['points']], float)
    g = view['guess']
    # (a street render: the camera at eye height - the cars' roofs and the road's far end on the
    # horizon - so the height is given, not fitted: with it free the fit trades height against the
    # crown's heights, which are what the comparison is to check)
    eye = view.get('eye')
    pos = to_scene(g['sheet'], g['z'])
    yaw0 = math.radians(g['yaw'])
    best = None
    for dyaw in (-20, -10, 0, 10, 20):
        for scale in (0.7, 1.0, 1.4):
            p0 = pos * np.array([scale, 1, scale])
            if model == 'level':
                s = [*p0, yaw0 + math.radians(dyaw), g.get('f', 2000), g.get('v0', H * 0.7)]
            else:
                s = [*p0, yaw0 + math.radians(dyaw), math.radians(g.get('pitch', -30)), g.get('f', 1500)]
            if eye is not None:
                s[1] = eye
            fix = (lambda q: np.concatenate([q[:1], [eye], q[1:]])) if eye is not None else (lambda q: q)
            s0 = [v for i, v in enumerate(s) if eye is None or i != 1]
            try:
                r = least_squares(lambda q: (project(model, fix(q), P, W, H) - uv).ravel(), s0, loss='soft_l1', f_scale=5.0, max_nfev=4000)
                r.x = fix(r.x)
            except ValueError:
                continue
            if best is None or r.cost < best.cost:
                best = r
    q = best.x
    # (the angles as the fit left them may be a turn or two round)
    wrap = lambda t: (t + math.pi) % (2 * math.pi) - math.pi
    q[3] = wrap(q[3])
    if model == 'pinhole':
        q[4] = wrap(q[4])
    return model, q, project(model, q, P, W, H) - uv


def main():
    data = json.load(open(os.path.join(HERE, 'calib_points.json')))
    path = os.path.join(HERE, 'cameras.json')
    cams = json.load(open(path)) if os.path.exists(path) else {}
    for name in sys.argv[1:] or list(data):
        view = data[name]
        model, q, err = fit(view)
        W, H = view['size']
        fwd, right, up = basis(q[3], q[4] if model == 'pinhole' else 0.0)
        pos = q[:3]
        f = q[5] if model == 'pinhole' else q[4]
        cam = dict(model=model, size=[W, H], pos=[round(v, 2) for v in pos], yaw=round(math.degrees(q[3]), 3),
                   pitch=round(math.degrees(q[4]), 3) if model == 'pinhole' else 0.0, f=round(float(f), 1),
                   v0=round(float(q[5]), 1) if model == 'level' else H / 2,
                   target=[round(v, 2) for v in pos + fwd * 100],
                   residuals={p['name']: [round(float(e[0]), 1), round(float(e[1]), 1)] for p, e in zip(view['points'], err)},
                   rms=round(float(np.sqrt((err ** 2).sum(axis=1).mean())), 1), time=view.get('time'))
        cams[name] = cam
        site = (pos[0], -pos[2])
        print(f"{name}: {model}  scene pos [{pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}] (site {site[0]:.1f}, {site[1]:.1f}, "
              f"{pos[1]:.1f} m up)  yaw {cam['yaw']:.1f}  pitch {cam['pitch']:.1f}  f {cam['f']:.0f}  v0 {cam['v0']:.0f}  rms {cam['rms']} px")
        for p, e in zip(view['points'], err):
            flag = '  <--' if math.hypot(*e) > 8 else ''
            print(f"    {p['name']:18s} {e[0]:+7.1f} {e[1]:+7.1f}{flag}")
    json.dump(cams, open(path, 'w'), indent=1)


if __name__ == '__main__':
    main()
