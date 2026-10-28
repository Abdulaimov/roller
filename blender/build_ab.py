"""Build the Ali Binokor complex in Blender: five blocks from the architect's plans, the site from
the genplan, the neighbours (school, hospital, kindergarten, houses across the road).

    blender/export_ab.sh                     # -> public/models/ali_binokor.glb, src/model/*.json
    blender -b -P blender/build_ab.py -- --out build/ab --render build/ab.png [--view NAME]

Inputs: blender/ab/plans.json (tools/ab/extract_plan.py) and build/site_raw.json (tools/ab/site_map.py).
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
    # roughly the marketing renders: from the street south of blocks Б / В, and from the south-west
    'street': dict(location=(30.0, -175.0, 14.0), target=(10.0, -20.0, 40.0), lens=24.0),
    'southwest': dict(location=(-210.0, -150.0, 60.0), target=(-20.0, 0.0, 30.0), lens=30.0),
    'aerial': dict(location=(150.0, -260.0, 230.0), target=(0.0, 0.0, 10.0), lens=32.0),
    'north': dict(location=(80.0, 260.0, 150.0), target=(0.0, 0.0, 20.0), lens=30.0),
    'shops': dict(location=(-10.0, -70.0, 3.0), target=(-30.0, -40.0, 5.0), lens=26.0),
    'atower': dict(location=(-170.0, -80.0, 20.0), target=(-99.0, -19.5, 45.0), lens=28.0),
    'top': dict(location=(0.0, 0.0, 600.0), target=(0.0, 0.1, 0.0), lens=30.0),
}


def parse_args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='build/ab')
    p.add_argument('--render', help='write a still to this PNG')
    p.add_argument('--view', default='street')
    p.add_argument('--res', default='1600x1000')
    p.add_argument('--samples', type=int, default=32)
    p.add_argument('--engine', default='EEVEE')
    p.add_argument('--blocks', default='A,B,V,G,D')
    p.add_argument('--no-site', action='store_true')
    p.add_argument('--no-glb', action='store_true')
    return p.parse_args(argv)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def add_view(scene, name, location, target, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.clip_start = 0.5
    cd.clip_end = 20000.0
    ob = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(ob)
    ob.location = location
    ob.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def setup_light(scene):
    sun_data = bpy.data.lights.new('Sun', 'SUN')
    sun_data.energy = 3.4
    sun_data.angle = math.radians(1.5)
    sun_data.color = (1.0, 0.96, 0.9)
    sun = bpy.data.objects.new('Sun', sun_data)
    scene.collection.objects.link(sun)
    az, el = math.radians(150), math.radians(42)   # afternoon sun from the south-south-east
    d = Vector((-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), -math.sin(el)))
    sun.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    world = bpy.data.worlds.new('Sky')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes['Background']
    sky = nt.nodes.new('ShaderNodeTexSky')
    try:
        sky.sky_type = 'NISHITA'
        sky.sun_elevation = el
        sky.sun_rotation = math.radians(180 - 150)
        sky.sun_disc = False
        bg.inputs['Strength'].default_value = 0.35
    except Exception:
        bg.inputs['Strength'].default_value = 1.0
    nt.links.new(sky.outputs['Color'], bg.inputs['Color'])


def setup_render(scene, engine, samples, res):
    if engine.upper() == 'CYCLES':
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        try:
            prefs = bpy.context.preferences.addons['cycles'].preferences
            prefs.compute_device_type = 'METAL'
            prefs.get_devices()
            for d in prefs.devices:
                d.use = True
            scene.cycles.device = 'GPU'
        except Exception:
            scene.cycles.device = 'CPU'
    else:
        for name in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
            try:
                scene.render.engine = name
                break
            except TypeError:
                continue
        try:
            scene.eevee.taa_render_samples = samples
            scene.eevee.use_shadows = True
            scene.eevee.use_raytracing = True
        except AttributeError:
            pass
    w, h = map(int, res.lower().split('x'))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in scene.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'
    scene.view_settings.look = 'None'


def podium_sites():
    """Two-storey podium outlines (genplan pink "2-ош." and the dark strips by blocks A, Б, В), site metres."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from ab.towers import footprint
    from ab.config import load_plans, site_raw
    path = os.path.join(ROOT, 'build', 'site_raw.json')
    if not os.path.exists(path):
        return {}
    raw = site_raw()['classes']
    polys = []
    for cls in ('podium', 'building'):
        for p in raw.get(cls, []):
            g = Polygon(p['ring'], p['holes']).buffer(0)
            if g.area > 20:
                polys.append(g)
    plans = load_plans()
    out = {}
    for key in ('A', 'B', 'V'):
        fp = footprint(key, plans)
        near = [g for g in polys if g.distance(fp) < 1.5]
        if not near:
            continue
        u = unary_union(near + [fp]).buffer(1.0, join_style='mitre').buffer(-1.0, join_style='mitre')
        u = max(getattr(u, 'geoms', [u]), key=lambda g: g.area)
        # keep it compact: the podium is what lies within 22 m of the tower
        u = u.intersection(fp.buffer(22.0, join_style='mitre'))
        out[key] = max(getattr(u, 'geoms', [u]), key=lambda g: g.area).simplify(0.4)
    return out


def main():
    args = parse_args()
    reset_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    from ab.materials import build_materials
    from ab.towers import build_block
    from ab.config import load_plans
    from ab import podium
    from complex import geom
    mats = build_materials()
    geom.TREE_LOG = None if args.render else []
    plans = load_plans()
    pods = podium_sites()
    root = get_collection('Ali Binokor')
    towers = []
    for key in args.blocks.split(','):
        towers.append(build_block(key, mats, root, plans, pods.get(key)))
    site = None
    if not args.no_site:
        from ab import site as site_mod
        site = site_mod.build_site(mats, get_collection('Site'), towers, pods)
    views = {n: add_view(scene, n, **v) for n, v in VIEWS.items()}
    setup_light(scene)
    setup_render(scene, args.engine, args.samples, args.res)
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out + '.blend', compress=True)
    used = sorted({fl['plan'] for t in towers for fl in t['floors']})
    keep = ('title', 'slab', 'enclosure', 'walls', 'struct', 'windows', 'glazing', 'common', 'apartments', 'lifts', 'swings')
    if site and site.get('walk'):
        with open(out + '.walk.json', 'w') as f:
            json.dump(site['walk'], f, separators=(',', ':'))
    with open(out + '.plans.json', 'w') as f:
        json.dump({k: {kk: plans[k][kk] for kk in keep if kk in plans[k]} for k in used}, f, separators=(',', ':'), ensure_ascii=False)
    info = dict(site_centre=[0.0, 0.0], towers=towers, people=podium.PEOPLE + (site['people'] if site else []),
                trees_placed=(geom.TREE_LOG or []) + podium.TREES + (site['trees'] if site else []),
                tree_protos=[], trees=[], cars=site['cars'] if site else [], benches=site['benches'] if site else [],
                labels=site['labels'] if site else [], lamps=site['lamps'] if site else [], shops=podium.SHOPS)
    with open(out + '.json', 'w') as f:
        json.dump(info, f, ensure_ascii=False)
    if not args.no_glb:
        for name in ('Trees', 'Cars', 'People'):
            col = bpy.data.collections.get(name)
            if col:
                for ob in list(col.objects):
                    bpy.data.objects.remove(ob)
        bpy.ops.export_scene.gltf(filepath=out + '.glb', export_format='GLB', export_apply=True,
                                  export_cameras=False, export_lights=False, export_extras=True)
    if args.render:
        scene.camera = views[args.view]
        scene.render.filepath = os.path.abspath(args.render)
        bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main()
