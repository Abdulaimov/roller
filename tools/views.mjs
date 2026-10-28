// Fixed cameras for screenshots (scene metres: x east, y up, z south; site origin in the middle of the plot).
// The start view of the site (src/main.js HOME_WIDE).
export const HOME = { pos: [-150, 165, 285], target: [5, 22, -5] };

export const VIEWS = {
  // the client renders' cameras (tools/ab/calib.py, points in tools/ab/calib_points.json), one per
  // building where the render's composition does not follow the genplan exactly
  r1_B: { cam: { pos: [-76.64, 3.0, 449.93], yaw: 7.007, f: 2714.6, v0: 843.9, size: [1600, 900] }, noCity: true },
  r1_A: { cam: { pos: [-81.08, 15.5, 419.92], yaw: 9.918, f: 2500.4, v0: 751.2, size: [1600, 900] }, noCity: true },
  r2_A: { cam: { pos: [-314.99, 2.74, -158.2], yaw: 118.053, f: 1998.7, v0: 851.9, size: [1600, 900] }, noCity: true },
  r4_A: { cam: { pos: [-149.57, 61.07, 143.68], yaw: 23.436, f: 2022.0, v0: 1128.0, size: [1131, 1600] }, noCity: true },
  r2_B: { cam: { pos: [-348.69, 0.5, -148.07], yaw: 115.613, f: 2055.9, v0: 868.5, size: [1600, 900] }, noCity: true, hideTower: 'A' },
  r1_V: { cam: { pos: [-162.92, 3.0, 620.62], yaw: 12.237, f: 3854.0, v0: 839.5, size: [1600, 900] }, noCity: true },
  // presentation views (natural perspective, fov 38): the overview like render 1, the opposite view
  // like render 2, a pedestrian at the shops, the glass tower close up, a corner of a slab block,
  // the courtyard
  p1_overview: { cam: { pos: [-81.08, 15.5, 419.92], yaw: 9.918, f: 1300, v0: 610, size: [1600, 900] } },
  p2_opposite: { cam: { pos: [-314.99, 2.74, -158.2], yaw: 118.053, f: 1250, v0: 640, size: [1600, 900] } },
  p3_street: { pos: [-12, 1.7, 66], target: [-44, 9, 42] },
  p4_tower: { cam: { pos: [-149.57, 61.07, 143.68], yaw: 23.436, f: 1600, v0: 980, size: [1600, 900] } },
  p5_corner: { pos: [-110, 66, 120], target: [-62, 62, 52] },
  p6_courtyard: { pos: [-20, 32, -120], target: [10, 4, -40] },
  // straight down on the site (ground, roads, paving, lawns)
  top_site: { pos: [-10, 520, 1], target: [-10, 0, 0], noCity: true },
  top_south: { pos: [-40, 260, 60.5], target: [-40, 0, 60], noCity: true },
  // the start view, with the sales UI
  aerial: { ...HOME, ui: true },
  aerial_clean: { ...HOME },
  // like render 1: blocks Б and В from the street to the south
  // the camera of render 1 (from the park south of the avenue) and of render 2 (from the south-west)
  render1: { pos: [-10, 24, 250], target: [-22, 30, 0], noCity: true },
  render2: { pos: [-330, 12, -40], target: [-40, 40, 0], noCity: true },
  a_west: { pos: [-234, 40, 85.5], target: [-99, 40, 19.5] },
  a_south: { pos: [-99 + 0.44 * 150, 40, 19.5 + 0.9 * 150], target: [-99, 40, 19.5] },
  a_north: { pos: [-99 - 0.44 * 150, 40, 19.5 - 0.9 * 150], target: [-99, 40, 19.5] },
  a_east: { pos: [-99 + 0.9 * 150, 40, 19.5 - 0.44 * 150], target: [-99, 40, 19.5] },
  // render 3: the shop front of block Б from the pavement, block A's podium in the distance
  render3: { pos: [-5, 2.2, 70], target: [-45, 9, 48], noCity: true },
  poster: { pos: [-22, 4, 62], target: [-30, 4, 46], noCity: true },
  // the user's screenshot of 20.10: from the north-west over the kindergarten
  user_nw: { pos: [-210, 95, -190], target: [-40, 25, -10] },
  mid_stripe: { pos: [-20, 40, 120], target: [-30, 40, 30], noCity: true },
  // block Б's street face straight on, like render 1 (camera on the avenue, 1.7 m up... raised to see the top)
  b_front: { pos: [-33.6 + 0.42 * 190, 40, 31 + 0.906 * 190], target: [-33.6, 38, 31], noCity: true },
  win_close: { pos: [-20, 30, 55], target: [-28, 30, 30] },
  street: { pos: [10, 9, 120], target: [5, 38, 20] },
  // like render 2: from the south-west, the glass tower in front
  southwest: { pos: [-240, 30, 150], target: [-60, 45, 0] },
  tower_a: { pos: [-150, 20, 60], target: [-99, 40, 19] },
  shops: { pos: [-20, 4, 75], target: [-35, 6, 40] },
  courtyard: { pos: [10, 40, 10], target: [40, 0, -40] },
  playground: { pos: [150, 45, 20], target: [80, 0, -80] },
  kindergarten: { pos: [-40, 30, 10], target: [-8, 3, -29] },
  hospital: { pos: [150, 30, 60], target: [117, 8, 14] },
  school: { pos: [60, 60, -60], target: [118, 5, -150] },
  north: { pos: [80, 140, -300], target: [0, 20, 0] },
  // cut-away floor, an apartment's card, walking inside
  floor_b10: { floor: ['B', 10], ui: true, from: HOME, wait: 2500 },
  apt_b10: { floor: ['B', 10], apt: 'B10-3', ui: true, from: HOME, wait: 2500 },
  floor_a12: { floor: ['A', 12], ui: true, from: HOME, wait: 2500 },
  apt_g12: { floor: ['G', 12], apt: 'G12-4', ui: true, from: HOME, wait: 2500 },
  floor_g20: { floor: ['G', 20], ui: true, from: HOME },
};
