// Geometry kit for the interiors: collects pieces per material and merges them into one mesh per
// material at the end (a whole furnished floor is a few dozen draw calls).
//
// Coordinates: the floor group's local space is plan (x, y) at (x, height, -y). Furniture is drawn
// in its own frame - x to its right, y up, z towards the room (its front faces +z), origin at the
// middle of its back on the floor - and placed with at(planX, planY, facing).
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { Q } from '../quality.js';

const SEG = Q.level === 'high' ? 3 : 1;

// box-projected UVs in metres, from the geometry's final position (seamless across pieces)
function boxUV(g, metres) {
  const p = g.attributes.position, n = g.attributes.normal;
  const uv = new Float32Array(p.count * 2);
  for (let i = 0; i < p.count; i++) {
    const ax = Math.abs(n.getX(i)), ay = Math.abs(n.getY(i)), az = Math.abs(n.getZ(i));
    let u, v;
    if (ay >= ax && ay >= az) (u = p.getX(i)), (v = p.getZ(i));
    else if (ax >= az) (u = p.getZ(i)), (v = p.getY(i));
    else (u = p.getX(i)), (v = p.getY(i));
    uv[2 * i] = u / metres;
    uv[2 * i + 1] = v / metres;
  }
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
}

export class Kit {
  constructor() {
    this.parts = new Map();
    this.m = new THREE.Matrix4();
    this.q = new THREE.Quaternion();
    this.up = new THREE.Vector3(0, 1, 0);
  }

  /** Place the next pieces: furniture origin at plan (x, y), raised by z, front facing plan angle `facing` */
  at(x, y, facing = 0, z = 0) {
    const phi = Math.atan2(Math.cos(facing), -Math.sin(facing));
    this.q.setFromAxisAngle(this.up, phi);
    this.m.compose(new THREE.Vector3(x, z, -y), this.q, new THREE.Vector3(1, 1, 1));
    return this;
  }

  /** Move / turn the current frame (for a chair around a table, a lamp on a nightstand...) */
  offset(x, z, turn = 0, y = 0) {
    this.q.setFromAxisAngle(this.up, turn);
    this.m.multiply(new THREE.Matrix4().compose(new THREE.Vector3(x, y, z), this.q, new THREE.Vector3(1, 1, 1)));
    return this;
  }

  save() {
    (this.stack ??= []).push(this.m.clone());
    return this;
  }

  restore() {
    this.m.copy(this.stack.pop());
    return this;
  }

  /** Pieces given directly in the floor group's space */
  world() {
    this.m.identity();
    return this;
  }

  add(mat, geo) {
    geo.applyMatrix4(this.m);
    if (!this.parts.has(mat)) this.parts.set(mat, []);
    this.parts.get(mat).push(geo.index ? geo.toNonIndexed() : geo);
    return this;
  }

  // ---- primitives, in the current frame ----
  box(mat, x0, y0, z0, x1, y1, z1) {
    const g = new THREE.BoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0));
    g.translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
    return this.add(mat, g);
  }

  /** rounded box by centre and size */
  rbox(mat, cx, cy, cz, w, h, d, r = 0.03, seg = SEG) {
    r = Math.min(r, w / 2 - 1e-3, h / 2 - 1e-3, d / 2 - 1e-3);
    const g = new RoundedBoxGeometry(w, h, d, Math.max(1, seg), Math.max(r, 1e-3));
    g.translate(cx, cy, cz);
    return this.add(mat, g);
  }

  cyl(mat, x, y0, z, r, y1, seg = 20, rTop = r) {
    const g = new THREE.CylinderGeometry(rTop, r, y1 - y0, seg);
    g.translate(x, (y0 + y1) / 2, z);
    return this.add(mat, g);
  }

  /** lathe around the vertical axis through (x, z); pts = [[radius, height], ...] */
  lathe(mat, pts, x, y, z, seg = 24) {
    const g = new THREE.LatheGeometry(pts.map(([r, h]) => new THREE.Vector2(r, h)), seg);
    g.translate(x, y, z);
    return this.add(mat, g);
  }

  sphere(mat, x, y, z, r, sx = 1, sy = 1, sz = 1, detail = 2) {
    const g = new THREE.IcosahedronGeometry(r, detail);
    g.scale(sx, sy, sz);
    g.translate(x, y, z);
    return this.add(mat, g);
  }

  /** a plane facing +z, centred at (x, y, z) */
  plane(mat, x, y, z, w, h, ry = 0) {
    const g = new THREE.PlaneGeometry(w, h);
    if (ry) g.rotateY(ry);
    g.translate(x, y, z);
    return this.add(mat, g);
  }

  /** a disc facing +z (oven door, washing machine porthole), centred at (x, y, z) */
  disc(mat, x, y, z, r, depth, seg = 28) {
    const g = new THREE.CylinderGeometry(r, r, depth, seg);
    g.rotateX(Math.PI / 2);
    g.translate(x, y, z);
    return this.add(mat, g);
  }

  /** tube through points [[x, y, z], ...] */
  tube(mat, pts, r, seg = 24, radial = 8) {
    const curve = new THREE.CatmullRomCurve3(pts.map((p) => new THREE.Vector3(...p)));
    return this.add(mat, new THREE.TubeGeometry(curve, seg, r, radial, false));
  }

  /** a straight round bar from point a to point b ([x, y, z]) */
  rod(mat, a, b, r, seg = 6) {
    const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b), len = A.distanceTo(B);
    if (len < 1e-4) return this;
    const g = new THREE.CylinderGeometry(r, r, len, seg, 1);
    g.translate(0, len / 2, 0);
    g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), B.clone().sub(A).normalize()));
    g.translate(A.x, A.y, A.z);
    return this.add(mat, g);
  }

  /**
   * A slab along a plan segment a -> b, on its left side (the side the room is on when the room
   * polygon runs counter-clockwise), from `off` to `off + thick` away from the line, heights z0..z1.
   */
  along(mat, ax, ay, bx, by, off, thick, z0, z1, trim = 0) {
    const L = Math.hypot(bx - ax, by - ay);
    if (L - 2 * trim < 0.02) return this;
    const ux = (bx - ax) / L, uy = (by - ay) / L, nx = -uy, ny = ux;
    const g = new THREE.BoxGeometry(L - 2 * trim, z1 - z0, thick);
    // box: x along the segment, z across (towards -plan normal after the flip below)
    const ang = Math.atan2(uy, ux);
    g.rotateY(ang);
    const mx = (ax + bx) / 2 + nx * (off + thick / 2), my = (ay + by) / 2 + ny * (off + thick / 2);
    g.translate(mx, (z0 + z1) / 2, -my);
    const keep = this.m.clone();
    this.m.identity();
    this.add(mat, g);
    this.m.copy(keep);
    return this;
  }

  /** remember what has been added so far, to take the pieces after it back out with rollback() */
  mark() {
    return new Map([...this.parts].map(([mat, list]) => [mat, list.length]));
  }

  rollback(mark) {
    for (const [mat, list] of this.parts) {
      const n = mark.get(mat) ?? 0;
      list.splice(n).forEach((g) => g.dispose());
    }
  }

  build(group, own, { cast = true } = {}) {
    for (const [mat, geos] of this.parts) {
      if (!geos.length) continue; // everything of this material was taken back out (rollback)
      // every piece needs the same attributes to merge: normals and (placeholder) UVs
      for (const geo of geos) {
        if (!geo.attributes.normal) geo.computeVertexNormals();
        if (!geo.attributes.uv) geo.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(geo.attributes.position.count * 2), 2));
        for (const name of Object.keys(geo.attributes)) if (!['position', 'normal', 'uv'].includes(name)) geo.deleteAttribute(name);
      }
      const g = mergeGeometries(geos, false);
      geos.forEach((x) => x.dispose());
      if (!g) continue;
      if (mat.userData.boxUV) boxUV(g, mat.userData.boxUV);
      own.push(g);
      const mesh = new THREE.Mesh(g, mat);
      mesh.castShadow = cast && !mat.transparent && (mat.userData.castShadow ?? !mat.emissive?.getHex?.());
      mesh.receiveShadow = !mat.emissive?.getHex?.();
      group.add(mesh);
    }
    this.parts.clear();
  }
}
