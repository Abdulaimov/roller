"""A camera for tools/rp/match_shot.mjs set by hand, where a render cannot be fitted (its crowns out
of the frame or hidden): position and target in the sheets' frame, the vertical field of view.

    tools/ab/py tools/rp/look_cam.py NAME X Y Z TX TY TZ FOV W H [HOUR]
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROT = -49.5


def scene(x, y, z):
    a = math.radians(ROT)
    return [round(math.cos(a) * x - math.sin(a) * y, 2), round(z, 2), round(-(math.sin(a) * x + math.cos(a) * y), 2)]


name = sys.argv[1]
if sys.argv[2] == 'level':
    # a street camera: level, the horizon at row v0 of the W x H frame, focal length f (px)
    x, y, z, tx, ty, f, v0, W, H = map(float, sys.argv[3:12])
    hour = float(sys.argv[12]) if len(sys.argv) > 12 else None
    p, t = scene(x, y, z), scene(tx, ty, z)
    yaw = math.degrees(math.atan2(t[0] - p[0], -(t[2] - p[2])))
    path = os.path.join(HERE, 'cameras.json')
    cams = json.load(open(path)) if os.path.exists(path) else {}
    cams[name] = dict(model='level', size=[int(W), int(H)], pos=p, yaw=round(yaw, 3), pitch=0.0, f=f, v0=v0,
                      target=[round(p[0] + (t[0] - p[0]) * 5, 2), round(z, 2), round(p[2] + (t[2] - p[2]) * 5, 2)], time=hour,
                      sheet=dict(pos=[x, y, z], toward=[tx, ty]))
    json.dump(cams, open(path, 'w'), indent=1)
    print(name, cams[name])
    sys.exit(0)
x, y, z, tx, ty, tz, fov, W, H = map(float, sys.argv[2:11])
hour = float(sys.argv[11]) if len(sys.argv) > 11 else None
path = os.path.join(HERE, 'cameras.json')
cams = json.load(open(path)) if os.path.exists(path) else {}
cams[name] = dict(model='look', size=[int(W), int(H)], pos=scene(x, y, z), target=scene(tx, ty, tz), fov=fov, time=hour,
                  sheet=dict(pos=[x, y, z], target=[tx, ty, tz]))
json.dump(cams, open(path, 'w'), indent=1)
print(name, cams[name])
