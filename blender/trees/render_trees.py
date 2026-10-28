"""Render the CC0 tree models (Poly Haven, see blender/assets/fetch_assets.py) into billboard views.

    blender -b --factory-startup -P blender/trees/render_trees.py -- [--size 512] [--samples 48] [--only broad]

For every tree variant: six side views (every 60 degrees round the trunk) and one from straight
above, each as a colour image and a normal image, orthographic, transparent background:
    build/trees/<variant>_<view>_color.png    the tree under an even white sky: its own colour with
                                              the shade deep in the crown (ambient occlusion) baked in
    build/trees/<variant>_<view>_normal.png   surface normals in the view's frame (x right, y up,
                                              z towards the viewer), encoded 0..1
    build/trees/trees.json                    sizes in metres and the camera of each view
scripts/build_tree_atlas.py packs them for the site; src/props.js draws each tree as three crossed
upright quads (two views each, back to back) and one level quad seen from above.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
MODELS = os.path.join(ROOT, 'blender', 'assets', 'models')
OUT = os.path.join(ROOT, 'build', 'trees')

# variant -> (model, node name of the tree in the file)
VARIANTS = {
    'broad': ('tree_small_02', 'tree_small_02_LOD0'),
    'broad_b': ('jacaranda_tree', 'jacaranda_tree'),
    'fir_a': ('fir_sapling_medium', 'fir_sapling_medium_a_LOD0'),
    'fir_b': ('fir_sapling_medium', 'fir_sapling_medium_b_LOD0'),
    'poplar': ('pine_sapling_small', 'pine_sapling_small_a'),
    'shrub': ('searsia_lucida', 'searsia_lucida_a_LOD0'),
    # 21.10.2026: a full-crowned broadleaf for the courtyards (atlas c: scripts/build_tree_atlas_c.py)
    'full': ('island_tree_02', 'island_tree_02_LOD0'),
}
SIDE_VIEWS = 6


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    return int(opt('--size', 512)), int(opt('--samples', 48)), [x for x in opt('--only', '').split(',') if x]


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_render(size, samples):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('METAL', 'OPTIX', 'CUDA', 'HIP', 'ONEAPI'):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = True
                sc.cycles.device = 'GPU'
                break
        except TypeError:
            continue
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 64
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.color_depth = '8'
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.render.filter_size = 1.0
    # an even white sky all round: what the tree looks like before any sun
    world = bpy.data.worlds.new('white')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (1, 1, 1, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    sc.world = world


def import_tree(model, node):
    path = os.path.join(MODELS, model, f'{model}_1k.gltf')
    bpy.ops.import_scene.gltf(filepath=path)
    keep = None
    for ob in list(bpy.context.scene.objects):
        if ob.name.startswith(node) or ob.name == node:
            keep = ob
    for ob in list(bpy.context.scene.objects):
        if ob is not keep and not (keep and ob.parent is keep):
            bpy.data.objects.remove(ob, do_unlink=True)
    keep.location = (0, 0, 0)
    bpy.context.view_layer.update()

    def points():
        import numpy as np
        me = keep.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        Mw = np.array(keep.matrix_world)
        return co @ Mw[:3, :3].T + Mw[:3, 3]

    # pivot: where the trunk meets the ground
    P = points()
    low = P[P[:, 2] < P[:, 2].min() + 0.08 * (P[:, 2].max() - P[:, 2].min()) + 0.05]
    keep.location = (-float(low[:, 0].mean()), -float(low[:, 1].mean()), -float(P[:, 2].min()))
    bpy.context.view_layer.update()
    P = points()
    H = float(P[:, 2].max())
    R = float(((P[:, 0] ** 2 + P[:, 1] ** 2) ** 0.5).max())
    return keep, H, R


def leaves_two_sided(ob):
    """Alpha-blended leaf cards render as alpha-clipped (crisp cut-outs, no sorting noise)."""
    for slot in ob.material_slots:
        m = slot.material
        if m and hasattr(m, 'surface_render_method'):
            m.surface_render_method = 'DITHERED'


def normal_materials(ob):
    """Swap every material for one that emits the surface normal in camera space (0..1), keeping
    the leaf cut-outs; leaves seen from behind get their normal turned to the viewer."""
    for slot in ob.material_slots:
        src = slot.material
        m = bpy.data.materials.new(src.name + ' normal')
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        N, L = nt.nodes.new, nt.links.new
        out = N('ShaderNodeOutputMaterial')
        geo = N('ShaderNodeNewGeometry')
        vt = N('ShaderNodeVectorTransform')
        vt.vector_type = 'NORMAL'
        vt.convert_from = 'WORLD'
        vt.convert_to = 'CAMERA'
        L(geo.outputs['Normal'], vt.inputs['Vector'])
        # backfacing -> flip
        flip = N('ShaderNodeMath')
        flip.operation = 'MULTIPLY_ADD'
        L(geo.outputs['Backfacing'], flip.inputs[0])
        flip.inputs[1].default_value = -2.0
        flip.inputs[2].default_value = 1.0
        sgn = N('ShaderNodeVectorMath')
        sgn.operation = 'SCALE'
        L(vt.outputs['Vector'], sgn.inputs[0])
        L(flip.outputs[0], sgn.inputs['Scale'])
        # Cycles camera space: x right, y up, z away from the viewer; the map wants z towards it
        enc = N('ShaderNodeVectorMath')
        enc.operation = 'MULTIPLY_ADD'
        L(sgn.outputs['Vector'], enc.inputs[0])
        enc.inputs[1].default_value = (0.5, 0.5, -0.5)
        enc.inputs[2].default_value = (0.5, 0.5, 0.5)
        em = N('ShaderNodeEmission')
        L(enc.outputs['Vector'], em.inputs['Color'])
        em.inputs['Strength'].default_value = 1.0
        mix = N('ShaderNodeMixShader')
        tr = N('ShaderNodeBsdfTransparent')
        alpha = None
        if src and src.use_nodes:
            p = next((n for n in src.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if p and p.inputs['Alpha'].is_linked:
                lk = p.inputs['Alpha'].links[0]
                # copy the alpha source (an image texture, maybe through a UV map node)
                img_src = lk.from_node
                if img_src.type == 'TEX_IMAGE':
                    t = N('ShaderNodeTexImage')
                    t.image = img_src.image
                    t.interpolation = img_src.interpolation
                    alpha = t.outputs[lk.from_socket.name]
            elif p:
                alpha = None
        if alpha is not None:
            # hard cut, like the alpha test on the site
            cut = N('ShaderNodeMath')
            cut.operation = 'GREATER_THAN'
            L(alpha, cut.inputs[0])
            cut.inputs[1].default_value = 0.5
            L(cut.outputs[0], mix.inputs['Fac'])
        else:
            mix.inputs['Fac'].default_value = 1.0
        L(tr.outputs['BSDF'], mix.inputs[1])
        L(em.outputs['Emission'], mix.inputs[2])
        L(mix.outputs['Shader'], out.inputs['Surface'])
        slot.material = m


def camera(name, loc, target, scale, up=Vector((0, 0, 1))):
    cd = bpy.data.cameras.new(name)
    cd.type = 'ORTHO'
    cd.ortho_scale = scale
    cd.clip_start = 0.1
    cd.clip_end = 1000
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = (Vector(target) - Vector(loc)).normalized()
    ob.rotation_euler = d.to_track_quat('-Z', 'Y' if abs(d.z) < 0.99 else 'Y').to_euler()
    return ob


def views(H, R):
    """(name, camera location, target, ortho scale, right vector) per view; trees stand at the origin."""
    S = max(2 * R, H) * 1.02
    out = []
    for k in range(SIDE_VIEWS):
        a = 2 * math.pi * k / SIDE_VIEWS
        d = Vector((math.sin(a), -math.cos(a), 0))          # from the tree towards the camera
        right = Vector((math.cos(a), math.sin(a), 0))       # image right, seen from the camera
        out.append((f'side{k}', d * 60 + Vector((0, 0, S / 2)), Vector((0, 0, S / 2)), S, right, a))
    St = 2 * R * 1.04
    out.append(('top', Vector((0, 0, H + 60)), Vector((0, 0, 0)), St, Vector((1, 0, 0)), None))
    return S, St, out


def main():
    size, samples, only = args()
    os.makedirs(OUT, exist_ok=True)
    meta = json.load(open(os.path.join(OUT, 'trees.json'))) if os.path.exists(os.path.join(OUT, 'trees.json')) else {}
    for name, (model, node) in VARIANTS.items():
        if only and name not in only:
            continue
        reset()
        setup_render(size, samples)
        ob, H, R = import_tree(model, node)
        leaves_two_sided(ob)
        S, St, vs = views(H, R)
        sc = bpy.context.scene
        cams = []
        for vname, loc, tgt, scale, right, a in vs:
            cam = camera(vname, loc, tgt, scale)
            if vname == 'top':
                cam.rotation_euler = (0, 0, 0)  # looking down, image up = +y
            cams.append((vname, cam))
        for vname, cam in cams:
            sc.camera = cam
            sc.render.filepath = os.path.join(OUT, f'{name}_{vname}_color.png')
            bpy.ops.render.render(write_still=True)
        normal_materials(ob)
        sc.cycles.samples = max(8, samples // 4)
        sc.cycles.use_denoising = False
        sc.view_settings.view_transform = 'Raw'  # the normals are data: no display transform
        for vname, cam in cams:
            sc.camera = cam
            sc.render.filepath = os.path.join(OUT, f'{name}_{vname}_normal.png')
            bpy.ops.render.render(write_still=True)
        meta[name] = dict(model=model, node=node, height=round(H, 3), radius=round(R, 3), side_size=round(S, 3),
                          top_size=round(St, 3), side_views=SIDE_VIEWS, source=f'https://polyhaven.com/a/{model}', licence='CC0')
        print('tree', name, meta[name], flush=True)
        json.dump(meta, open(os.path.join(OUT, 'trees.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
