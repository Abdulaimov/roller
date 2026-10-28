"""Realistic people for the site (replacing the procedural figures of src/props.js): MakeHuman bodies,
skins, clothes and hair (MPFB 2 for Blender and the MakeHuman system assets, both CC0 for what they
produce), posed (walking, standing, talking, looking at a phone), the pose applied, the rig removed,
decimated for the web, exported as one glTF: one node per person (name = variant), meshes per
material, metres, feet at z = 0, facing +y (Blender) = -z (three.js) ... the viewer turns them.
    Blender -b -P blender/people/build_people.py -- [--only m_walk_a] [--preview] [--out build/people.glb]
Needs: MPFB 2 installed as a Blender extension, the asset pack in its user data (see README)."""
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
ONLY = [x for x in opt('--only', '').split(',') if x]
PREVIEW = '--preview' in argv
OUT = os.path.join(ROOT, opt('--out', 'build/people.glb'))
DATA = os.path.expanduser('~/Library/Application Support/Blender/5.2/mpfb/data')

from bl_ext.user_default.mpfb.services.humanservice import HumanService  # noqa: E402

D = math.radians
# poses: bone -> the direction it points (armature space: the figure faces -y, z up); each bone is
# turned from its rest direction to this one, parents first
def n(x, y, z):
    v = Vector((x, y, z))
    return v.normalized()


ARMS = {'upperarm_l': n(0.18, 0.02, -1), 'upperarm_r': n(-0.18, 0.02, -1),
        'lowerarm_l': n(0.08, -0.22, -1), 'lowerarm_r': n(-0.08, -0.22, -1)}
FEET = {'foot_l': n(0.08, -1, -0.35), 'foot_r': n(-0.08, -1, -0.35)}
POSES = {
    'stand': {**ARMS, **FEET},
    'walk_l': {  # left leg forward, right arm forward
        'upperarm_l': n(0.15, 0.32, -1), 'upperarm_r': n(-0.15, -0.3, -1),
        'lowerarm_l': n(0.1, 0.12, -1), 'lowerarm_r': n(-0.08, -0.75, -1),
        'thigh_l': n(0.03, -0.42, -1), 'calf_l': n(0.02, -0.18, -1), 'foot_l': n(0.08, -1, 0.1),
        'thigh_r': n(-0.03, 0.3, -1), 'calf_r': n(-0.02, 0.62, -1), 'foot_r': n(-0.08, -0.6, -1),
    },
    'walk_r': {
        'upperarm_r': n(-0.15, 0.32, -1), 'upperarm_l': n(0.15, -0.3, -1),
        'lowerarm_r': n(-0.1, 0.12, -1), 'lowerarm_l': n(0.08, -0.75, -1),
        'thigh_r': n(-0.03, -0.42, -1), 'calf_r': n(-0.02, -0.18, -1), 'foot_r': n(-0.08, -1, 0.1),
        'thigh_l': n(0.03, 0.3, -1), 'calf_l': n(0.02, 0.62, -1), 'foot_l': n(0.08, -0.6, -1),
    },
    'phone': {**ARMS, **FEET, 'upperarm_r': n(-0.25, -0.15, -1), 'lowerarm_r': n(0.35, -1, 0.45),
              'neck_01': n(0, -0.25, 1), 'head': n(0, -0.45, 1)},
    'talk': {**ARMS, **FEET, 'upperarm_l': n(0.25, -0.2, -1), 'lowerarm_l': n(0.15, -1, 0.05)},
}
# variant: (macro, skin, clothes, hair, pose)
CENTRAL = {'asian': 0.35, 'caucasian': 0.6, 'african': 0.05}
VARIANTS = {
    'm_walk_a': (dict(gender=1.0, age=0.5, muscle=0.55, weight=0.5, height=0.6, race=CENTRAL), 'young_asian_male', ['male_casualsuit01', 'shoes01'], 'short02', 'walk_l'),
    'm_walk_b': (dict(gender=1.0, age=0.6, muscle=0.5, weight=0.6, height=0.5, race=CENTRAL), 'middleage_caucasian_male', ['male_casualsuit05', 'shoes02'], 'short04', 'walk_r'),
    'm_stand_a': (dict(gender=1.0, age=0.7, muscle=0.5, weight=0.65, height=0.45, race=CENTRAL), 'middleage_asian_male', ['male_elegantsuit01', 'shoes03'], 'short01', 'phone'),
    'm_stand_b': (dict(gender=1.0, age=0.45, muscle=0.6, weight=0.45, height=0.65, race=CENTRAL), 'young_caucasian_male', ['male_casualsuit03', 'shoes01'], 'short03', 'talk'),
    'm_walk_c': (dict(gender=1.0, age=0.4, muscle=0.5, weight=0.5, height=0.55, race=CENTRAL), 'young_caucasian_male2', ['male_casualsuit06', 'shoes02'], 'short02', 'walk_r'),
    'm_stand_c': (dict(gender=1.0, age=0.55, muscle=0.55, weight=0.55, height=0.5, race=CENTRAL), 'middleage_caucasian_male', ['male_casualsuit05', 'shoes03'], 'short04', 'stand'),
    'f_walk_a': (dict(gender=0.0, age=0.45, muscle=0.45, weight=0.45, height=0.5, race=CENTRAL), 'young_caucasian_female', ['female_elegantsuit01', 'shoes04'], 'long01', 'walk_r'),
    'f_walk_b': (dict(gender=0.0, age=0.55, muscle=0.4, weight=0.55, height=0.45, race=CENTRAL), 'young_asian_female', ['female_casualsuit01', 'shoes05'], 'bob02', 'walk_l'),
    'f_stand_a': (dict(gender=0.0, age=0.5, muscle=0.45, weight=0.5, height=0.5, race=CENTRAL), 'middleage_caucasian_female', ['female_elegantsuit01', 'shoes06'], 'ponytail01', 'phone'),
    'f_stand_b': (dict(gender=0.0, age=0.4, muscle=0.5, weight=0.4, height=0.55, race=CENTRAL), 'young_caucasian_female2', ['female_elegantsuit01', 'shoes04'], 'braid01', 'talk'),
}
TRIS = 9000  # per person, all parts


def asset(kind, name, ext):
    return os.path.join(DATA, kind, name, f'{name}.{ext}')


def build(name, macro, skin, clothes, hair, pose):
    full = {'gender': 0.5, 'age': 0.5, 'muscle': 0.5, 'weight': 0.5, 'proportions': 0.6, 'height': 0.5,
            'cupsize': 0.5, 'firmness': 0.5, 'race': {'asian': 0.33, 'caucasian': 0.33, 'african': 0.33}}
    full.update(macro)
    # (feet_on_ground would shift the mesh away from where the rig's joints are placed: lifted after posing)
    body = HumanService.create_human(mask_helpers=True, detailed_helpers=False, extra_vertex_groups=True, feet_on_ground=False, scale=0.1, macro_detail_dict=full)
    sk = os.path.join(DATA, 'skins', skin, f'{skin}.mhmat')
    HumanService.set_character_skin(sk, body, skin_type='GAMEENGINE', material_instances=False)
    # the rig first: the clothes, the hair and the eyes then come rigged to it (and mask the skin under them)
    rig = HumanService.add_builtin_rig(body, 'game_engine', import_weights=True)
    parts = [body]
    for c in clothes:
        parts.append(HumanService.add_mhclo_asset(asset('clothes', c, 'mhclo'), body, asset_type='Clothes', subdiv_levels=0, material_type='MAKESKIN'))
    parts.append(HumanService.add_mhclo_asset(asset('hair', hair, 'mhclo'), body, asset_type='Hair', subdiv_levels=0, material_type='MAKESKIN'))
    parts.append(HumanService.add_mhclo_asset(os.path.join(DATA, 'eyes', 'low-poly', 'low-poly.mhclo'), body, asset_type='Eyes', subdiv_levels=0, material_type='MAKESKIN'))
    want = POSES[pose]
    order = []   # parents first
    def walk(b):
        order.append(b)
        for c in b.children:
            walk(c)
    for b in rig.pose.bones:
        if b.parent is None:
            walk(b)
    for pb in order:
        if pb.name not in want:
            continue
        bpy.context.view_layer.update()
        head, tail = pb.head.copy(), pb.tail.copy()
        cur = (tail - head).normalized()
        # the wanted direction is in the world (z up, facing -y): into the armature's own space
        w = (rig.matrix_world.inverted().to_3x3() @ want[pb.name]).normalized()
        q = cur.rotation_difference(w)
        from mathutils import Matrix
        m = pb.matrix.copy()
        r = q.to_matrix().to_4x4()
        pb.matrix = Matrix.Translation(head) @ r @ Matrix.Translation(-head) @ m
    bpy.context.view_layer.update()

    if '--keep-rig' in argv:
        return None
    # the pose and every modifier made real, the rig gone
    out = []
    for o in [body] + [p for p in parts[1:] if p]:
        bpy.context.view_layer.objects.active = o
        if o.data.shape_keys:   # the body's targets (its shape) baked in first
            o.shape_key_add(name='mix', from_mix=True)
            keys = o.data.shape_keys.key_blocks
            mix = keys['mix'].data
            co = [v.co.copy() for v in mix]
            o.shape_key_clear()
            for v, c in zip(o.data.vertices, co):
                v.co = c
        for m in list(o.modifiers):
            try:
                bpy.ops.object.modifier_apply(modifier=m.name)
            except RuntimeError as e:
                print('modifier', o.name, m.name, e)
        for m in list(o.modifiers):
            o.modifiers.remove(m)
        o.parent = None
        out.append(o)
    bpy.data.objects.remove(rig, do_unlink=True)
    # the helpers' faces (masked) out of the body
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    vg = [g for g in body.vertex_groups if g.name.startswith('HelperGeometry') or g.name.startswith('JointCubes')]
    if vg:
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(body.data)
        dl = bm.verts.layers.deform.active
        ids = {g.index for g in vg}
        kill = [v for v in bm.verts if dl and any(k in ids for k in v[dl].keys())]
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
        bm.to_mesh(body.data)
        bm.free()
    total = sum(len(o.data.polygons) for o in out)
    # decimated to the budget, each part in its share
    tris = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)
    T = sum(tris(o) for o in out)
    for o in out:
        r = min(1.0, TRIS / max(1, T))
        if r < 0.98 and tris(o) > 300:
            d = o.modifiers.new('dec', 'DECIMATE')
            d.ratio = r
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.modifier_apply(modifier='dec')
    # feet on the ground
    zmin = min((o.matrix_world @ v.co).z for o in out for v in o.data.vertices)
    for o in out:
        o.location.z -= zmin
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    for o in out:
        o.parent = root
        o.name = f'{name}_{o.name}'
    print('PERSON', name, 'faces before', total, 'tris after', sum(tris(o) for o in out), [o.name for o in out])
    return root


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module='bl_ext.user_default.mpfb')
roots = []
for i, (name, spec) in enumerate(VARIANTS.items()):
    if ONLY and name not in ONLY:
        continue
    r = build(name, *spec)
    if r:
        r.location.x = i * 1.2
        roots.append(r)

if PREVIEW:
    sc = bpy.context.scene
    for r in roots:
        r.rotation_euler.z = D(35)   # three-quarter: the stride shows
    cx = (len(VARIANTS if not ONLY else ONLY) - 1) * 0.6
    bpy.ops.object.camera_add(location=(cx, -9.5, 1.0), rotation=(D(88), 0, 0))
    sc.camera = bpy.context.object
    bpy.context.object.data.lens = 38
    bpy.ops.object.light_add(type='SUN', rotation=(D(50), D(10), D(30)))
    bpy.context.object.data.energy = 3.5
    w = bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.8, 0.85, 0.9, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1400, 800
    sc.render.filepath = os.path.join(ROOT, 'build', 'people_preview.png')
    bpy.ops.render.render(write_still=True)
else:
    for r in roots:
        r.location.x = 0
    # textures at most 512 px (people are small on screen; the viewer tints the clothes per person)
    for img in bpy.data.images:
        if img.size[0] > 512 or img.size[1] > 512:
            k = 512 / max(img.size)
            img.scale(max(1, int(img.size[0] * k)), max(1, int(img.size[1] * k)))
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_apply=True, export_image_format='AUTO', export_yup=True, export_texcoords=True, export_normals=True,
                              export_materials='EXPORT', export_animations=False)
    print('EXPORTED', OUT)
