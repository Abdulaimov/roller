"""Download the CC0 assets the build uses from Poly Haven (https://polyhaven.com, all CC0).

    python3 blender/assets/fetch_assets.py            # everything missing
    python3 blender/assets/fetch_assets.py --list     # what would be fetched

File URLs come from Poly Haven's public API, so nothing here depends on their URL layout.
Downloads land in blender/assets/{hdri,textures,models}/<asset>/ (git-ignored);
scripts/build_web_assets.py turns them into the small files the site loads.
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
API = 'https://api.polyhaven.com/files/'
UA = {'User-Agent': 'ali-binokor-3d asset fetch'}


def urlopen(url, timeout):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)

# name -> (kind, resolution, maps or None)
ASSETS = {
    # sky: daylight, partly cloudy, sun ~48 deg up; lights the scene and is its background
    'kloofendal_48d_partly_cloudy_puresky': ('hdri', ['1k', '2k'], None),
    # surfaces (diffuse, OpenGL normal, AO/roughness/metal)
    'painted_plaster_wall': ('texture', ['1k'], None),     # facade render, slab bands
    'concrete_wall_008': ('texture', ['1k'], None),        # kerbs, bridge, embankment, planters
    'aerial_asphalt_01': ('texture', ['1k', '2k'], None),  # roads (one tile = 30 m: no visible repeat)
    'sparse_grass': ('texture', ['1k'], None),             # lawns
    'concrete_pavers': ('texture', ['1k'], None),          # sidewalks, paving (interlocking pavers)
    'patio_tiles': ('texture', ['1k'], None),              # podium deck, large warm stone
    'rectangular_paving': ('texture', ['1k'], None),       # promenade
    'grey_stone_path': ('texture', ['1k'], None),          # grey irregular setts
    'wood_floor_deck': ('texture', ['1k'], None),          # timber decks
    'rubber_tiles': ('texture', ['1k'], None),             # playground surface (normal / roughness)
    'brick_wall_09': ('texture', ['1k'], None),            # facing brick of blocks Б-Д (tinted tan / dark grey)
    # trees, rendered into billboards (scripts/build_trees.py)
    'tree_small_02': ('model', ['1k'], None),              # broadleaf street tree, open crown
    'jacaranda_tree': ('model', ['1k'], None),             # broadleaf street tree, dense round crown
    'fir_sapling_medium': ('model', ['1k'], None),         # conifers
    'pine_sapling_small': ('model', ['1k'], None),         # tall narrow trees
    'searsia_lucida': ('model', ['1k'], None),             # small ornamental trees / large shrubs
    'island_tree_02': ('model', ['1k'], None),             # full-crowned broadleaf (atlas c)
}


def get(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + '.part'
    with urlopen(url, 600) as r, open(tmp, 'wb') as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    os.replace(tmp, dest)
    return os.path.getsize(dest)


def files_for(name, kind, res):
    info = json.load(urlopen(API + name, 60))
    out = []
    for r in res:
        if kind == 'hdri':
            f = info['hdri'][r]['hdr']
            out.append((f['url'], os.path.join(ROOT, 'hdri', f'{name}_{r}.hdr'), f['size']))
        elif kind == 'texture':
            for m in ('Diffuse', 'nor_gl', 'arm'):
                f = info[m][r]['jpg']
                out.append((f['url'], os.path.join(ROOT, 'textures', name, os.path.basename(f['url'])), f['size']))
        else:
            g = info['gltf'][r]['gltf']
            out.append((g['url'], os.path.join(ROOT, 'models', name, os.path.basename(g['url'])), g['size']))
            for rel, f in g['include'].items():
                out.append((f['url'], os.path.join(ROOT, 'models', name, rel), f['size']))
    return out


def main():
    todo = []
    for name, (kind, res, _) in ASSETS.items():
        todo += files_for(name, kind, res)
    missing = [t for t in todo if not (os.path.exists(t[1]) and os.path.getsize(t[1]) > 0)]
    print(f'{len(todo)} files, {len(missing)} missing, {sum(t[2] for t in missing) / 1e6:.1f} MB to download')
    if '--list' in sys.argv:
        for u, d, s in missing:
            print(f'  {s / 1e6:7.1f} MB  {os.path.relpath(d, ROOT)}')
        return
    for u, d, s in missing:
        get(u, d)
        print(f'  got {os.path.relpath(d, ROOT)} ({s / 1e6:.1f} MB)', flush=True)


if __name__ == '__main__':
    main()
