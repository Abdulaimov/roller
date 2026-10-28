// Regnum Plaza: three blocks (А, Б, В) on a common podium. Block placement and floor levels come from the
// Blender build (model/complex.json, blender/build_ab.py); apartments, rooms and walls from the
// architect's floor plans (model/plans.json, tools/ab/extract_plan.py).
import complex from './model/complex.json';
import plans from './model/plans.json';

export const MODEL_URL = `${import.meta.env.BASE_URL}models/regnum.glb`;
export const PLANS = plans;

// Site plan coordinates (metres, x east, y north) -> scene (x, z) with the site centre at the origin.
const [CX, CY] = complex.site_centre;
export const toScene = (x, y) => ({ x: x - CX, z: -(y - CY) });

export const TOWERS = complex.towers;
export const RESIDENTIAL = TOWERS.filter((t) => t.sales);
export const towerByKey = Object.fromEntries(TOWERS.map((t) => [t.key, t]));
export const TREES = { protos: complex.tree_protos ?? [], list: complex.trees ?? [], placed: complex.trees_placed ?? [] };
export const CARS = complex.cars ?? [];
export const PEOPLE = complex.people ?? [];
export const PLACES = complex.labels ?? [];
// block letters as written on the drawings
export const LETTER = { A: 'А', B: 'Б', V: 'В' };

// A tower's floor plans are drawn in its own frame. In the scene, a group at `position` turned by
// `rotY` holds plan point (x, y) at local (x, height, -y).
export function planFrame(t) {
  const a = (t.rot * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  const [px, py] = t.plan_centre;
  const o = toScene(t.centre[0] - (c * px - s * py), t.centre[1] - (s * px + c * py));
  return {
    position: { x: o.x, z: o.z },
    rotY: a,
    toScene: (x, y) => ({ x: o.x + c * x - s * y, z: o.z - (s * x + c * y) }),
    toPlan: (X, Z) => {
      const dx = X - o.x, dy = -(Z - o.z);
      return { x: c * dx + s * dy, y: -s * dx + c * dy };
    },
    // plan direction -> site compass bearing (0 = north, 90 = east)
    bearing: (dx, dy) => {
      const ex = c * dx - s * dy, ny = s * dx + c * dy;
      return ((Math.atan2(ex, ny) * 180) / Math.PI + 360) % 360;
    },
  };
}
export const LAMPS = complex.lamps ?? [];
export const SHOPS = complex.shops ?? [];
