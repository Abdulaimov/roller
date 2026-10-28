"""Build Regnum Plaza in Blender: the three blocks from the sales book's plans, the podium, the
courtyard and the streets, the neighbourhood (OSM), and the JSON the viewer reads.

    blender/export_rp.sh                     # -> public/models/regnum.glb, src/model/*.json
    blender -b -P blender/build_rp.py -- --out build/rp/rp --render build/rp/v.png --view corner
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from complex.geom import get_collection  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

VIEWS = {
    # render 1: from the crossing of the two streets, looking into the corner of Б
    'corner': dict(location=(95.0, 70.0, 6.0), target=(-15.0, 0.0, 40.0), lens=24.0),
    'street': dict(location=(40.0, 160.0, 8.0), target=(-40.0, 30.0, 40.0), lens=24.0),
    'aerial': dict(location=(220.0, 160.0, 190.0), target=(-20.0, -5.0, 20.0), lens=28.0),
    'yard': dict(location=(-110.0, -90.0, 40.0), target=(-25.0, 5.0, 35.0), lens=24.0),
    'top': dict(location=(-10.0, 0.0, 700.0), target=(-10.0, 0.1, 0.0), lens=30.0),
}


def parse_args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='build/rp/rp')
    p.add_argument('--render')
    p.add_argument('--view', default='corner')
    p.add_argument('--res', default='1600x1000')
    p.add_argument('--samples', type=int, default=16)
    p.add_argument('--blocks', default='A,B,V')
    p.add_argument('--no-site', action='store_true')
    p.add_argument('--no-glb', action='store_true')
    return p.parse_args(argv)


def main():
    from build_ab import add_view, setup_light, setup_render
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    from ab.materials import build_materials
    from complex import geom
    from rp import config as C
    from rp import podium, towers as T
    mats = build_materials()
    geom.TREE_LOG = None if args.render else []
    fr = C.setup()
    plans = C.load_plans()
    root = get_collection('Regnum Plaza')
    tw = [T.build_block(k, mats, root, plans) for k in args.blocks.split(',')]
    from shapely.ops import unary_union
    from shapely.geometry import Polygon
    fp = unary_union([Polygon(t['outline']) for t in tw])
    O, _ = podium.build(mats, get_collection('Podium', root), fr, fp)
    site = None
    if not args.no_site:
        from rp import site as S
        site = S.build_site(mats, get_collection('Site'), tw, O)
    views = {n: add_view(scene, n, **v) for n, v in VIEWS.items()}
    setup_light(scene)
    setup_render(scene, 'EEVEE', args.samples, args.res)
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out + '.blend', compress=True)
    used = sorted({f['plan'] for t in tw for f in t['floors']})
    keep = ('title', 'slab', 'enclosure', 'walls', 'struct', 'windows', 'glazing', 'common', 'apartments', 'lifts', 'swings')
    with open(out + '.plans.json', 'w') as f:
        json.dump({k: {kk: plans[k][kk] for kk in keep if kk in plans[k]} for k in used}, f, separators=(',', ':'), ensure_ascii=False)
    if site:
        with open(out + '.walk.json', 'w') as f:
            json.dump(site['walk'], f, separators=(',', ':'))
    for t in tw:
        site and site['labels'].append(dict(x=t['centre'][0], y=t['centre'][1], z=t['top'] + 7, ru=t['label'], tj=t['tj'], kind='block', key=t['key']))
    info = dict(site_centre=[0.0, 0.0], towers=tw, people=site['people'] if site else [],
                trees_placed=geom.TREE_LOG or [], tree_protos=[], trees=[], cars=site['cars'] if site else [],
                benches=site['benches'] if site else [], labels=site['labels'] if site else [],
                lamps=site['lamps'] if site else [], shops=[],
                podium=[[round(x, 2), round(y, 2)] for x, y in O.exterior.coords])
    with open(out + '.json', 'w') as f:
        json.dump(info, f, ensure_ascii=False)
    if not args.no_glb:
        bpy.ops.export_scene.gltf(filepath=out + '.glb', export_format='GLB', export_apply=True,
                                  export_cameras=False, export_lights=False, export_extras=True)
    if args.render:
        scene.camera = views[args.view]
        scene.render.filepath = os.path.abspath(args.render)
        bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main()
