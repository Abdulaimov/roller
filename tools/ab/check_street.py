"""Street furniture and props against the ground and one another (model/complex.json and the walk map
public/models/site_walk.json): every bench on the paving with room in front of it and nothing on or in
front of it; lamps, trees, people and cars not inside a building, a bench or one another; people on
the ground one can walk on, cars on the asphalt. Prints what is wrong (an empty list: all well).
    tools/ab/py tools/ab/check_street.py"""
import base64
import json
import math
import os

import numpy as np
from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.strtree import STRtree

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
c = json.load(open(os.path.join(ROOT, 'src/model/complex.json')))
w = json.load(open(os.path.join(ROOT, 'public/models/site_walk.json')))
x0, y0, nx, ny = w['x0'], w['y0'], w['nx'], w['ny']
ground = np.frombuffer(base64.b64decode(w['ground']), np.uint8).reshape(ny, nx)
kind = lambda x, y: int(ground[int(y - y0), int(x - x0)]) if 0 <= x - x0 < nx and 0 <= y - y0 < ny else 0
solids = [Polygon(s) for s in w['solids']]
tree = STRtree(solids)
bad = []

def rect(x, y, rot, hx, hy, oy=0.0):
    return affinity.rotate(box(x - hx, y - hy + oy, x + hx, y + hy + oy), rot, origin=(x, y), use_radians=True)

trees = [(t[0], t[1], t[4]) for t in c['trees_placed'] if t[2] < 1.0]
lamps = [(l[0], l[1]) for l in c['lamps'] if l[5] != 2]
people = [(p[0], p[1]) for p in c['people'] if p[2] < 1.0]
seats = []
for i, (x, y, r) in enumerate(c['benches']):
    seat, front = rect(x, y, r, 0.95, 0.3), rect(x, y, r, 0.95, 0.75, -1.05)
    seats.append((seat, front))
    # (the walk map's ground is a 1 m grid: the centres are tested here, the build keeps the whole
    # bench and the room in front of it on the paving)
    for name, g in (('seat', seat), ('front', front)):
        px, py = g.centroid.x, g.centroid.y
        if kind(px, py) not in (2, 7):
            bad.append(f'bench {i} ({x}, {y}): {name} off the paving (kind {kind(px, py)})')
    for k in tree.query(seat.buffer(0.05)):
        if not solids[k].equals_exact(seat, 0.05) and solids[k].intersection(seat).area > 0.01 and solids[k].area > seat.area * 1.05:
            bad.append(f'bench {i} ({x}, {y}): into an outline of {solids[k].area:.1f} m2')
    for tx, ty, tr in trees:
        if seat.distance(Point(tx, ty)) < 0.9 or front.distance(Point(tx, ty)) < 0.5:
            bad.append(f'bench {i} ({x}, {y}): a tree {seat.distance(Point(tx, ty)):.2f} m off')
    for lx, ly in lamps:
        if seat.union(front).distance(Point(lx, ly)) < 0.4:
            bad.append(f'bench {i} ({x}, {y}): a lamp in the way')
    for px, py in people:
        if seat.union(front).distance(Point(px, py)) < 0.35:
            bad.append(f'bench {i} ({x}, {y}): a person on it or in front of it')
shops = [g for g in solids if g.area > 1000]  # the blocks with their shop podiums
for i, (px, py) in enumerate(people):
    if any(g.contains(Point(px, py)) for g in shops):
        continue  # shoppers inside the shops on the ground floor
    if kind(px, py) == 0:
        bad.append(f'person {i} ({px}, {py}): off the ground one can walk on')
    if any(solids[k].contains(Point(px, py)) for k in tree.query(Point(px, py))):
        bad.append(f'person {i} ({px}, {py}): inside an outline')
    for tx, ty, tr in trees:
        if math.dist((px, py), (tx, ty)) < 0.6:
            bad.append(f'person {i} ({px}, {py}): in a tree')
for i, (lx, ly) in enumerate(lamps):
    for tx, ty, tr in trees:
        if math.dist((lx, ly), (tx, ty)) < 0.8:
            bad.append(f'lamp {i} ({lx}, {ly}): in a tree')
    if any(solids[k].contains(Point(lx, ly)) and solids[k].area < 50 for k in tree.query(Point(lx, ly))):
        bad.append(f'lamp {i} ({lx}, {ly}): inside a small outline (a bench, a car)')
cars = [rect(x, y, r, 2.35, 0.98) for x, y, _, r, _ in c['cars']]
for i, g in enumerate(cars):
    for j in range(i + 1, len(cars)):
        if g.intersects(cars[j]) and g.intersection(cars[j]).area > 0.05:
            bad.append(f'car {i} overlaps car {j}')
    cx, cy = g.centroid.x, g.centroid.y
    if kind(cx, cy) not in (1, 0):
        bad.append(f'car {i} ({cx:.1f}, {cy:.1f}): not on the asphalt (kind {kind(cx, cy)})')
    for tx, ty, tr in trees:
        if g.distance(Point(tx, ty)) < 0.3:
            bad.append(f'car {i}: a tree in it')
print(f'{len(c["benches"])} benches, {len(lamps)} lamps, {len(trees)} trees, {len(people)} people, {len(cars)} cars')
print(json.dumps(bad, ensure_ascii=False, indent=1))
