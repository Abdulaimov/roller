// The TV film's cameras (tools/ab/tv_film.mjs): six shots of the exterior, 70 s at 30 fps, each
// shot overlapping the next by a second (a dissolve). Scene metres (x east, y up, z south; the
// complex's middle at the origin). A shot is a path of camera points and of points looked at, eased
// in and out; an orbit goes round a centre. The last shot ends where the first begins (the loop).
// Every shot is taken level with the frame shifted (tv_film.mjs): the verticals stay upright.
export const FPS = 30;
export const FADE = 1.0; // seconds of dissolve between shots

export const SHOTS = [
  {
    // the whole complex in three-quarter view from the south-west, a slow push in
    name: 's1_wide', dur: 12, fov: 34, shadow: 'wide',
    pos: [[-300, 88, 300], [-246, 74, 246]],
    look: [[-8, 40, -5], [-12, 42, -5]],
  },
  {
    // round the complex from the south-west to the south-east: how the five blocks stand
    name: 's2_orbit', dur: 13, fov: 34, shadow: 'wide',
    orbit: { centre: [12, 0, -8], radius: [310, 290], height: [84, 72], from: 128, to: 58 },
    look: [[0, 40, -8], [15, 40, -10]],
  },
  {
    // along the street front of blocks Б and В at the height of the eighth floor
    name: 's3_track', dur: 13, fov: 40, shadow: 'wide',
    pos: [[-95, 30, 130], [80, 30, 128]],
    look: [[-80, 38, 30], [92, 38, 28]],
  },
  {
    // on foot along the street front of block Б, 10.5 m out (the lamps pass 5 m to the right, not
    // across the view): the shop windows lit inside, the signs over them
    name: 's4_shops', dur: 13, fov: 48, shadow: 'close', focus: [-24, 0, 52],
    pos: [[-8, 1.7, 63.3], [-34, 1.7, 60.8]],
    look: [[-28, 6.4, 54.3], [-54, 6.8, 51.8]],
  },
  {
    // block A, the glass tower, from across the avenue (the cars passing below), the camera rising
    // to show it with block Б beside it; verticals kept upright (a long lens, a gentle tilt)
    name: 's5_tower', dur: 13, fov: 40, shadow: 'close', focus: [-90, 0, 50],
    pos: [[-70, 2.2, 98], [-58, 30, 106]],
    look: [[-104, 34, 24], [-98, 46, 22]],
  },
  {
    // back out to the first view (the film loops: its last frame is its first)
    name: 's6_return', dur: 11, fov: 34, shadow: 'wide',
    pos: [[-200, 64, 205], [-300, 88, 300]],
    look: [[-14, 42, -5], [-8, 40, -5]],
  },
];

// when each shot starts on the film's timeline (seconds), and the film's length
export function timeline() {
  let t = 0;
  const out = SHOTS.map((s, i) => {
    const start = t;
    t += s.dur - (i < SHOTS.length - 1 ? FADE : 0);
    return { ...s, start };
  });
  return { shots: out, length: t };
}

// the day-to-night version: the hour at a moment of the film
export function hourAt(T, length) {
  const keys = [[0, 15.5], [0.26, 17.6], [0.52, 19.8], [0.66, 20.8], [0.8, 21.6], [1, 22.4]];
  const u = T / length;
  for (let i = 1; i < keys.length; i++) {
    if (u <= keys[i][0]) {
      const [u0, h0] = keys[i - 1], [u1, h1] = keys[i];
      const k = (u - u0) / (u1 - u0), s = k * k * (3 - 2 * k);
      return h0 + (h1 - h0) * s;
    }
  }
  return keys[keys.length - 1][1];
}
