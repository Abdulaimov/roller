// Apartments of blocks А, Б and Г, as drawn on the floor plans (model/plans.json). Areas and the
// number of rooms are the ones written on the sheets. Prices: the developer's price list per m² by
// floor (BAYTULLO SOKHTMON, REGNUM PLAZA DUSHANBE, 28.10.2026); floors it does not list (the 25th of
// В) show no price. No sales statuses.
import { PLANS, RESIDENTIAL, planFrame, LETTER } from './config.js';
import { centroid, polygonArea } from './geometry.js';
import { L, plural } from './i18n.js';

// which way the windows face: the compass sides of the apartment's outside walls
function sidesOf(a, frame, centre) {
  const out = new Set();
  const ring = a.outline;
  for (let i = 0; i < ring.length; i++) {
    const p = ring[i], q = ring[(i + 1) % ring.length];
    const mx = (p[0] + q[0]) / 2 - centre[0], my = (p[1] + q[1]) / 2 - centre[1];
    const len = Math.hypot(q[0] - p[0], q[1] - p[1]);
    if (len < 2) continue;
    // outward normal of the edge (rings are counter-clockwise)
    const nx = (q[1] - p[1]) / len, ny = -(q[0] - p[0]) / len;
    if (nx * mx + ny * my < 0) continue;
    const far = Math.abs(nx) > Math.abs(ny) ? Math.abs(mx) : Math.abs(my);
    const half = Math.abs(nx) > Math.abs(ny) ? frame.halfX : frame.halfY;
    if (far < half - 2.5) continue; // an inner wall, not the facade
    const b = frame.f.bearing(nx, ny);
    out.add(b < 45 || b >= 315 ? 'N' : b < 135 ? 'E' : b < 225 ? 'S' : 'W');
  }
  return ['N', 'E', 'S', 'W'].filter((s) => out.has(s));
}

export function summaryOf(rooms) {
  const T = L().summary;
  const count = (k) => rooms.filter((r) => r.kind === k).length;
  const parts = [];
  if (count('living')) parts.push(T.living);
  if (count('kitchen')) parts.push(T.kitchen);
  const beds = count('bedroom');
  if (beds) parts.push(`${beds} ${plural(beds, ...T.bedroom)}`);
  const baths = count('bath') + count('wc');
  if (baths) parts.push(`${baths} ${plural(baths, ...T.bath)}`);
  if (count('storage')) parts.push(T.storage);
  const s = parts.join(', ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// price per m² by floor (the price list: floors 3-7, 8-12, 13-18, 19-24)
const PRICES = [[3, 7, 1400], [8, 12, 1300], [13, 18, 1200], [19, 24, 1100]];
export const priceOf = (floor) => PRICES.find(([a, b]) => floor >= a && floor <= b)?.[2] ?? null;

export const apartments = [];
for (const tower of RESIDENTIAL) {
  const f = planFrame(tower);
  let number = 0;
  for (const fl of tower.floors) {
    const plan = PLANS[fl.plan];
    const xs = plan.enclosure.map((p) => p[0]), ys = plan.enclosure.map((p) => p[1]);
    const frame = { f, halfX: (Math.max(...xs) - Math.min(...xs)) / 2, halfY: (Math.max(...ys) - Math.min(...ys)) / 2 };
    const centre = [(Math.max(...xs) + Math.min(...xs)) / 2, (Math.max(...ys) + Math.min(...ys)) / 2];
    plan.apartments.forEach((a, i) => {
      const loggia = a.rooms.filter((r) => r.kind === 'loggia').reduce((s, r) => s + r.area, 0) + a.balconies.reduce((s, b) => s + b.area, 0);
      apartments.push({
        id: `${tower.key}${fl.floor}-${i}`,
        tower: tower.key,
        letter: LETTER[tower.key],
        number: ++number,
        floor: fl.floor,
        floors: tower.levels,
        unit: i,
        plan: fl.plan,
        data: a, // outline, rooms, balconies, fixtures (plan coordinates)
        baseY: fl.z + tower.slab,
        ceiling: Math.round((fl.h - 0.5) * 10) / 10,
        sides: sidesOf(a, frame, centre),
        rooms: a.rooms_count,
        area: a.area,
        loggia: Math.round(loggia * 10) / 10,
        outlineArea: polygonArea(a.outline),
        centroid: centroid(a.outline),
      });
    });
  }
}

export const aptsOnFloor = (tower, floor) => apartments.filter((a) => a.tower === tower && a.floor === floor);
