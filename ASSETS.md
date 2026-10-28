# Third-party assets and licences

Everything the site loads is either made in this repository (Blender scripts, code) or comes from
the sources below. All of them allow commercial use.

## Poly Haven (CC0 1.0, public domain; no attribution required, credited here anyway)

Downloaded by `blender/assets/fetch_assets.py` through the Poly Haven API; the site ships only the
derived files listed in the last column (resized, converted to WebP, colour maps of tinted sets made
neutral grey, sun disc removed from the sky). Licence: https://polyhaven.com/license

| Asset | Author (Poly Haven page) | Used for | Shipped as |
|---|---|---|---|
| [Kloofendal 48d Partly Cloudy (Pure Sky)](https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky) | Greg Zaal, Jarod Guest | sky: background, ambient light, reflections; sun direction | `public/env/sky_{1k,2k}.hdr`, `sky.json` |
| [Painted Plaster Wall](https://polyhaven.com/a/painted_plaster_wall) | Amal Kumar | facade render, slab edges, plant rooms | `public/textures/plaster/` |
| [Concrete Wall 008](https://polyhaven.com/a/concrete_wall_008) | Dario Barresi, Charlotte Baglioni | kerbs, bridge, embankment, planters, roofs, context blocks | `public/textures/concrete/` |
| [Aerial Asphalt 01](https://polyhaven.com/a/aerial_asphalt_01) | Rob Tuytel | roads (one tile = 30 m) | `public/textures/asphalt/` |
| [Sparse Grass](https://polyhaven.com/a/sparse_grass) | Amal Kumar | lawns | `public/textures/grass/` |
| [Concrete Pavers](https://polyhaven.com/a/concrete_pavers) | Amal Kumar | sidewalks, paving | `public/textures/pavers/` |
| [Patio Tiles](https://polyhaven.com/a/patio_tiles) | Dario Barresi | podium roof deck | `public/textures/patio/` |
| [Rectangular Paving](https://polyhaven.com/a/rectangular_paving) | Dimitrios Savva | promenade | `public/textures/paving/` |
| [Grey Stone Path](https://polyhaven.com/a/grey_stone_path) | Amal Kumar | stone setts on the deck | `public/textures/setts/` |
| [Wood Floor Deck](https://polyhaven.com/a/wood_floor_deck) | Dimitrios Savva | timber decking, pergolas | `public/textures/deck/` |
| [Rubber Tiles](https://polyhaven.com/a/rubber_tiles) | Amal Kumar | playground surface | `public/textures/rubber/` |
| [Brick Wall 09](https://polyhaven.com/a/brick_wall_09) | Poly Haven | facing brick of the blocks (tinted tan / dark grey) | `public/textures/brick/` |
| [Tree Small 02](https://polyhaven.com/a/tree_small_02) | Rico Cilliers | broadleaf street trees | rendered into `public/trees/` |
| [Fir Sapling Medium](https://polyhaven.com/a/fir_sapling_medium) | Rob Tuytel, Rico Cilliers | conifers (two variants) | rendered into `public/trees/` |
| [Pine Sapling Small](https://polyhaven.com/a/pine_sapling_small) | Rob Tuytel, Rico Cilliers | tall narrow trees | rendered into `public/trees/` |
| [Searsia Lucida](https://polyhaven.com/a/searsia_lucida) | James Ray Cock, Jenelle van Heerden | small ornamental trees | rendered into `public/trees/` |
| [Island Tree 02](https://polyhaven.com/a/island_tree_02) | Rob Tuytel, Rico Cilliers | full-crowned broadleaf trees (courtyards, school) | rendered into `public/trees/` (atlas c) |

Authors as listed by the Poly Haven API (api.polyhaven.com/info/<asset>) on 13 Oct 2026.

## Made in this repository

- The blocks, the shops, the site, the neighbours: `blender/build_ab.py` and `blender/ab/` from the
  architect's floor plans, the genplan and the marketing renders (no third-party geometry).
- Cars: `blender/props/build_cars.py` (modelled from typical dimensions).
- People, water ripples and the furniture, playground and street details: generated in `src/`.

## Code libraries (npm)

| Package | Licence | Use |
|---|---|---|
| three | MIT | 3D rendering |
| postprocessing | Zlib | frame passes (multisampling, tone mapping) |
| n8ao | ISC | ambient occlusion pass (high graphics level) |
| vite | MIT | build tool (not shipped) |
| playwright-core | Apache-2.0 | screenshot and check scripts in `tools/` (not shipped) |
