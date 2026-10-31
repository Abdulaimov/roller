#!/usr/bin/env bash
# Rebuild Regnum Plaza and copy it into the web viewer.
#
#   tools/ab/py tools/rp/extract.py       # (only when the plans change)  -> blender/rp/plans.json
#   tools/ab/py tools/rp/frame.py         # (only when the plans change)  -> blender/rp/frame.json
#   tools/ab/py tools/rp/osm.py           # (only when the OSM extract changes) -> blender/rp/osm.json
#   blender/export_rp.sh                  # -> public/models/regnum.glb, src/model/*.json
set -euo pipefail
cd "$(dirname "$0")/.."
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
export PATH="$HOME/.local/opt/node/bin:$PATH"
OUT=build/rp/rp
mkdir -p build/rp public/models src/model
PYTHONPATH=.pylib-blender "$BLENDER" -b --factory-startup --python-use-system-env --python-exit-code 1 -P blender/build_rp.py -- --out "$OUT" "$@"
GT=(npx --yes @gltf-transform/cli@4.1.1)
"${GT[@]}" dedup "$OUT.glb" "$OUT.dedup.glb"
"${GT[@]}" weld "$OUT.dedup.glb" "$OUT.weld.glb"
"${GT[@]}" meshopt "$OUT.weld.glb" public/models/regnum.glb
rm -f "$OUT.dedup.glb" "$OUT.weld.glb"
cp "$OUT.json" src/model/complex.json
cp "$OUT.plans.json" src/model/plans.json
tools/ab/py tools/ab/close_seams.py src/model/plans.json
cp "$OUT.walk.json" public/models/site_walk.json
ls -la public/models/regnum.glb public/models/site_walk.json src/model/complex.json src/model/plans.json
