"""Base materials of the model (the Ali Binokor set is added in blender/ab/materials.py).

Names are kept stable on purpose: the web viewer looks materials up by name.
"""
import bpy


def srgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# name: (hex colour, roughness, metallic, extra)
SPECS = {
    'Terracotta': ('#b88472', 0.85, 0.0, {}),
    'Terracotta dark': ('#6e3e30', 0.8, 0.0, {}),
    'White band': ('#efebe5', 0.45, 0.0, {}),
    'Roof': ('#d36a68', 0.9, 0.0, {}),
    'Plant room': ('#5a3a2f', 0.85, 0.0, {}),
    'Solar panel': ('#56627e', 0.3, 0.4, {}),
    'Window glass': ('#35524c', 0.08, 0.0, {}),
    'Curtain glass': ('#2f8070', 0.05, 0.0, {}),
    'Shop glass': ('#3a5559', 0.05, 0.0, {}),
    'Frame': ('#d9d2c6', 0.45, 0.0, {}),
    'Railing glass': ('#c9dbe2', 0.05, 0.0, {'alpha': 0.14}),
    'Copper screen': ('#9c5a3c', 0.45, 0.55, {}),
    'Sign': ('#f4efe6', 0.4, 0.0, {'emission': ('#ffffff', 0.6)}),
    'Stone fin': ('#d9cbb6', 0.7, 0.0, {}),
    'Paving': ('#c9bcab', 0.85, 0.0, {}),
    'Deck paving': ('#e6bb8c', 0.85, 0.0, {}),
    'Wood': ('#9b6a44', 0.7, 0.0, {}),
    'Pool water': ('#38b4dc', 0.03, 0.0, {}),
    'Play orange': ('#d0653a', 0.8, 0.0, {}),
    'Play blue': ('#0f8dc4', 0.8, 0.0, {}),
    'Grass': ('#5c6a06', 1.0, 0.0, {}),
    'Lawn': ('#647608', 1.0, 0.0, {}),
    'Shrub': ('#35521a', 0.9, 0.0, {}),
    'Leaves': ('#34501a', 0.9, 0.0, {}),
    'Leaves light': ('#4f6e1e', 0.9, 0.0, {}),
    'Trunk': ('#5a4030', 0.9, 0.0, {}),
    'Asphalt': ('#58585c', 0.9, 0.0, {}),
    'Road line': ('#f0efe8', 0.6, 0.0, {}),
    'Kerb': ('#c9c3b8', 0.8, 0.0, {}),
    'Sidewalk': ('#b9aaa2', 0.85, 0.0, {}),
    'Stained orange': ('#c8702f', 0.1, 0.0, {'emission': ('#e07a2e', 0.12)}),
    'Stained pink': ('#c25586', 0.1, 0.0, {'emission': ('#d9508a', 0.12)}),
    'Stained blue': ('#3c63b8', 0.1, 0.0, {'emission': ('#2f5fd8', 0.12)}),
    'Stained violet': ('#7f52b0', 0.1, 0.0, {'emission': ('#8a48c8', 0.12)}),
    'Embankment': ('#b5ab9c', 0.95, 0.0, {}),
    'River': ('#0d78b4', 0.25, 0.0, {}),
    'Foam': ('#e8f2f4', 0.6, 0.0, {}),
    'Bridge': ('#b9b6b0', 0.8, 0.0, {}),
    'Metal': ('#7d8288', 0.35, 0.8, {}),
    'Neighbour': ('#d6d7d6', 0.85, 0.0, {}),   # context blocks: plain light grey massing, opaque
    'Neighbour solid': ('#e9e7e3', 0.7, 0.0, {}),
    # the houses across the roads, each in its own paint (22.10.2026: they were all grey)
    'Neighbour cream': ('#ecd9a8', 0.7, 0.0, {}),
    'Neighbour peach': ('#eac2a0', 0.7, 0.0, {}),
    'Neighbour blue': ('#bccfdc', 0.7, 0.0, {}),
    'Neighbour mint': ('#c4d9c4', 0.7, 0.0, {}),
    'Neighbour rose': ('#e3b9b0', 0.7, 0.0, {}),
    'Car': ('#d8dade', 0.3, 0.5, {}),
    'Car dark': ('#2a2e33', 0.3, 0.5, {}),
    'Car red': ('#b02a2a', 0.3, 0.5, {}),
    # roof deck and promenade (render 2)
    'Cobble': ('#a9a7a3', 0.9, 0.0, {}),          # grey irregular stone paving
    'Deck stone': ('#d4a97c', 0.85, 0.0, {}),     # warm tan large-format stone around the pool
    'Pool mosaic': ('#6f8fa3', 0.4, 0.0, {}),     # blue-grey pebble mosaic pool surround
    'Pool tile': ('#8fd6ec', 0.2, 0.0, {}),       # light blue pool walls / floor
    'Lamp white': ('#f2f1ec', 0.35, 0.1, {}),
    'Lamp glow': ('#fff6dd', 0.4, 0.0, {'emission': ('#fff3d6', 1.5)}),
    'Umbrella': ('#9c6f47', 0.8, 0.0, {}),        # square brown sail umbrellas
    'Lounger': ('#e9e3d8', 0.6, 0.0, {}),
    'Lattice wood': ('#c8a77e', 0.7, 0.0, {}),    # light timber geodesic pergolas, decks
    'Dark lattice': ('#5b3a2c', 0.7, 0.0, {}),    # dark brown climbing dome
    'Rubber blue': ('#1f63b0', 0.95, 0.0, {}),    # play surface
    'Fitness green': ('#4f9a35', 0.5, 0.3, {}),
    'Fitness yellow': ('#e0bd35', 0.5, 0.3, {}),
    'Planter': ('#d7d2c8', 0.8, 0.0, {}),         # light concrete planter walls
    'Bollard': ('#f1f0eb', 0.5, 0.0, {}),
    'Promenade': ('#bfaa9c', 0.85, 0.0, {}),      # warm pinkish-beige street paving (renders ~#cbbbb3 in sun)
    'Shop frame': ('#2c3034', 0.4, 0.5, {}),      # dark mullions / transoms of the shop front
    'Gallery glass': ('#eef1f0', 0.12, 0.0, {}),   # light glazing of the shop front's 2nd level
    'Umbrella sand': ('#c88b51', 0.8, 0.0, {}),   # light ochre canvas of the pool's sail umbrellas (renders ~#d9a067 sunlit)
    'Cobble joint': ('#8e8a86', 0.9, 0.0, {}),    # mid-grey joints between the playground cobbles
    'Shop window': ('#c8d0cc', 0.12, 0.0, {}),   # light grey-green shop glazing (ground floor)
    'Sign blue': ('#3d8fe8', 0.4, 0.0, {'emission': ('#3a8cff', 0.5)}),   # LC Waikiki logo on the copper band
    'Railing glass dark': ('#3c5463', 0.05, 0.0, {'alpha': 0.7}),   # tinted balustrade of the hotel's terrace wing
}


def build_materials():
    mats = {}
    for name, (hexc, rough, metal, extra) in SPECS.items():
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        bsdf = nt.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (*srgb(hexc), 1.0)
        bsdf.inputs['Roughness'].default_value = rough
        bsdf.inputs['Metallic'].default_value = metal
        if 'specular' in extra:
            bsdf.inputs['Specular IOR Level'].default_value = extra['specular']
        if 'alpha' in extra:
            bsdf.inputs['Alpha'].default_value = extra['alpha']
            m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else None
            try:
                m.surface_render_method = 'BLENDED'
            except AttributeError:
                pass
        if 'emission' in extra:
            col, strength = extra['emission']
            bsdf.inputs['Emission Color'].default_value = (*srgb(col), 1.0)
            bsdf.inputs['Emission Strength'].default_value = strength
        m.diffuse_color = (*srgb(hexc), extra.get('alpha', 1.0))
        mats[name] = m
    if 'Copper screen' in mats:
        try:
            perforated_copper(mats['Copper screen'])
        except Exception:  # plain copper if the node setup is not available
            pass
    return mats


def perforated_copper(m):
    """Blender renders only: dot perforation (UV in metres) whose dot size follows a soft ornament,
    as on the copper screen of the shop front. The sheet stays the Principled BSDF (so the glTF
    export keeps its colour); the holes are a dark diffuse mixed in by the dot mask."""
    nt = m.node_tree
    if nt.nodes.get('Perforation') is not None:
        return
    bsdf = nt.nodes.get('Principled BSDF')
    out = nt.nodes.get('Material Output')
    N = nt.nodes.new
    bsdf.inputs['Base Color'].default_value = (*srgb('#ffd4be'), 1.0)   # light, pinkish copper sheet
    bsdf.inputs['Metallic'].default_value = 0.05
    bsdf.inputs['Roughness'].default_value = 0.55
    m.diffuse_color = (*srgb('#d29f86'), 1.0)
    tc = N('ShaderNodeTexCoord')
    vor = N('ShaderNodeTexVoronoi')            # regular grid of dots (randomness 0), ~0.11 m apart
    vor.inputs['Scale'].default_value = 9.0
    vor.inputs['Randomness'].default_value = 0.0
    noise = N('ShaderNodeTexNoise')            # ornament: where the dots grow
    noise.inputs['Scale'].default_value = 1.2
    noise.inputs['Detail'].default_value = 1.0
    rad = N('ShaderNodeMapRange')
    rad.inputs['From Min'].default_value = 0.38
    rad.inputs['From Max'].default_value = 0.62
    rad.inputs['To Min'].default_value = 0.04
    rad.inputs['To Max'].default_value = 0.42
    dots = N('ShaderNodeMath')
    dots.operation = 'LESS_THAN'
    hole = N('ShaderNodeBsdfDiffuse')          # dark cavity behind the holes
    hole.inputs['Color'].default_value = (*srgb('#c4907a'), 1.0)
    mix = N('ShaderNodeMixShader')
    mix.name = 'Perforation'
    L = nt.links.new
    L(tc.outputs['UV'], vor.inputs['Vector'])
    L(tc.outputs['UV'], noise.inputs['Vector'])
    L(noise.outputs['Fac'], rad.inputs['Value'])
    L(vor.outputs['Distance'], dots.inputs[0])
    L(rad.outputs['Result'], dots.inputs[1])
    L(dots.outputs['Value'], mix.inputs['Fac'])
    L(bsdf.outputs['BSDF'], mix.inputs[1])
    L(hole.outputs['BSDF'], mix.inputs[2])
    L(mix.outputs['Shader'], out.inputs['Surface'])
    try:
        panel_joints(m, tc, mix)
    except Exception:  # dots only
        pass


def panel_joints(m, tc, sheet):
    """Dark dashed lines on every copper panel (two rows across, one down each side), as the
    joints / fixings of the screen on the render. The facade gives the panels UVs in metres:
    u centred on the panel (return faces sit at u >= 5), v = height above the street."""
    nt = m.node_tree
    N, L = nt.nodes.new, nt.links.new
    out = nt.nodes.get('Material Output')
    sep = N('ShaderNodeSeparateXYZ')
    L(tc.outputs['UV'], sep.inputs[0])

    def op(kind, a, b=None):
        n = N('ShaderNodeMath')
        n.operation = kind
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L(x, n.inputs[i])
        return n.outputs[0]

    u, v = sep.outputs['X'], sep.outputs['Y']
    H1, H2, UX, W, P = 13.8, 11.6, 0.6, 0.035, 0.17     # rows, side lines, half width, dash period

    def line(x, at):
        return op('LESS_THAN', op('ABSOLUTE', op('SUBTRACT', x, at)), W)

    def dashes(x):
        return op('LESS_THAN', op('FRACT', op('DIVIDE', x, P)), 0.55)

    rows = op('MULTIPLY', op('MAXIMUM', line(v, H1), line(v, H2)), dashes(u))
    side = op('MULTIPLY', line(op('ABSOLUTE', u), UX), dashes(v))
    side = op('MULTIPLY', side, op('MULTIPLY', op('GREATER_THAN', v, H2 - W), op('LESS_THAN', v, H1 + W)))
    dash = op('MAXIMUM', rows, side)
    dark = N('ShaderNodeBsdfDiffuse')
    dark.inputs['Color'].default_value = (*srgb('#6e4232'), 1.0)
    mix = N('ShaderNodeMixShader')
    mix.name = 'Panel joints'
    L(dash, mix.inputs['Fac'])
    L(sheet.outputs['Shader'], mix.inputs[1])
    L(dark.outputs['BSDF'], mix.inputs[2])
    L(mix.outputs['Shader'], out.inputs['Surface'])
