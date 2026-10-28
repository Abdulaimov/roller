// First-person walking inside an apartment, or on the ground round the complex (src/sitewalk.js).
// Drag to look, click the floor to walk there, WASD/arrows, or the on-screen joystick on touch screens.
import * as THREE from 'three';

const EYE = 1.62;

export class WalkControls {
  constructor(camera, dom) {
    this.camera = camera;
    this.dom = dom;
    this.enabled = false;
    this.yaw = 0;
    this.pitch = -0.05;
    this.keys = new Set();
    this.joy = { x: 0, y: 0 };
    this.pos = new THREE.Vector2();
    this.target = null;
    this.ray = new THREE.Raycaster();
    this.ndc = new THREE.Vector2();
    this.bob = 0;

    // ring that shows where a click will take you
    this.ring = new THREE.Mesh(
      new THREE.RingGeometry(0.16, 0.22, 40),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.85, depthWrite: false }),
    );
    this.ring.rotation.x = -Math.PI / 2;
    this.ring.renderOrder = 20;
    this.ring.visible = false;

    dom.addEventListener('pointerdown', (e) => this.onDown(e));
    dom.addEventListener('pointermove', (e) => this.onMove(e));
    dom.addEventListener('pointerup', (e) => this.onUp(e));
    dom.addEventListener('pointerleave', () => (this.ring.visible = false));
    addEventListener('keydown', (e) => this.enabled && this.keys.add(e.code));
    addEventListener('keyup', (e) => this.keys.delete(e.code));
    addEventListener('blur', () => this.keys.clear());
  }

  start(interior, scene) {
    this.interior = interior;
    this.enabled = true;
    const { spawn } = interior;
    this.pos.set(spawn.x, spawn.z);
    this.yaw = spawn.yaw;
    this.pitch = spawn.pitch ?? -0.08;
    this.target = null;
    this.path = null;
    this.base = interior.groundAt ? interior.groundAt(spawn.x, spawn.z) : interior.baseY;
    scene.add(this.ring);
    this.apply(0);
  }

  stop() {
    this.enabled = false;
    this.interior = null;
    this.keys.clear();
    this.ring.removeFromParent();
  }

  setJoystick(x, y) {
    this.joy.x = x;
    this.joy.y = y;
  }

  // forward/backward and look
  floorHit(e) {
    const r = this.dom.getBoundingClientRect();
    this.ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    this.ray.setFromCamera(this.ndc, this.camera);
    if (this.interior.pick) return this.interior.pick(this.ray);
    const hit = this.ray.intersectObject(this.interior.group, true)[0];
    if (!hit || !this.interior.floorMeshes.includes(hit.object)) return null;
    return hit.point;
  }

  onDown(e) {
    if (!this.enabled) return;
    this.drag = { x: e.clientX, y: e.clientY, moved: false };
    this.dom.setPointerCapture(e.pointerId);
  }

  onMove(e) {
    if (!this.enabled) return;
    if (this.drag) {
      const dx = e.clientX - this.drag.x, dy = e.clientY - this.drag.y;
      if (!this.drag.moved && Math.hypot(dx, dy) > 5) this.drag.moved = true;
      if (this.drag.moved) {
        const k = e.pointerType === 'touch' ? 0.006 : 0.0045;
        this.yaw += dx * k;
        this.pitch = THREE.MathUtils.clamp(this.pitch + dy * k, -1.2, 1.2);
        this.drag.x = e.clientX;
        this.drag.y = e.clientY;
        this.ring.visible = false;
      }
      return;
    }
    if (e.pointerType === 'touch') return;
    const p = this.floorHit(e);
    this.ring.visible = !!p;
    if (p) {
      this.ring.position.set(p.x, p.y + 0.01, p.z);
      // far off on the grounds the ring grows so it stays visible
      this.ring.scale.setScalar(this.interior.outdoor ? Math.max(1, this.camera.position.distanceTo(p) / 7) : 1);
    }
  }

  onUp(e) {
    if (!this.enabled || !this.drag) return;
    const wasDrag = this.drag.moved;
    this.drag = null;
    if (wasDrag) return;
    const p = this.floorHit(e);
    if (p) {
      // outdoors the way goes round hedges, fences and benches; indoors straight to the point
      const way = this.interior.route?.(this.pos.x, this.pos.y, p.x, p.z);
      this.path = way?.length ? way : null;
      this.target = this.path ? this.path.shift() : new THREE.Vector2(p.x, p.z);
      this.stuck = 0;
    }
  }

  update(dt) {
    if (!this.enabled) return;
    const k = this.keys;
    const run = k.has('ShiftLeft') || k.has('ShiftRight');
    const pace = this.interior.speed ?? 1;
    const speed = (run ? 3.2 : 1.7) * pace;
    let fwd = 0, side = 0, turn = 0;
    if (k.has('KeyW') || k.has('ArrowUp')) fwd += 1;
    if (k.has('KeyS') || k.has('ArrowDown')) fwd -= 1;
    if (k.has('KeyA')) side -= 1;
    if (k.has('KeyD')) side += 1;
    if (k.has('ArrowLeft') || k.has('KeyQ')) turn += 1;
    if (k.has('ArrowRight') || k.has('KeyE')) turn -= 1;
    fwd += -this.joy.y;
    side += this.joy.x;
    this.yaw += turn * 1.7 * dt;

    let mx = 0, mz = 0;
    if (fwd || side) {
      this.target = null;
      this.path = null;
      const len = Math.min(1, Math.hypot(fwd, side));
      const a = Math.atan2(side, fwd);
      const fx = -Math.sin(this.yaw), fz = -Math.cos(this.yaw);
      const rx = Math.cos(this.yaw), rz = -Math.sin(this.yaw);
      const dirx = fx * Math.cos(a) + rx * Math.sin(a), dirz = fz * Math.cos(a) + rz * Math.sin(a);
      mx = dirx * speed * len * dt;
      mz = dirz * speed * len * dt;
    } else if (this.target) {
      const dx = this.target.x - this.pos.x, dz = this.target.y - this.pos.y;
      const dist = Math.hypot(dx, dz);
      const last = !this.path?.length;
      if (dist < (last ? 0.05 : 0.35)) this.target = last ? null : this.path.shift();
      else {
        const step = Math.min(dist, 2.2 * pace * (last ? Math.min(1, dist * 1.5 + 0.3) : 1) * dt);
        mx = (dx / dist) * step;
        mz = (dz / dist) * step;
        // outdoors the walker turns to face the way, unless looking round with the pointer
        if (this.interior.outdoor && !this.drag?.moved && dist > 0.6) {
          let d = Math.atan2(-dx, -dz) - this.yaw;
          d = Math.atan2(Math.sin(d), Math.cos(d));
          this.yaw += d * Math.min(1, dt * 2.5);
        }
      }
    }

    if (mx || mz) {
      const before = this.pos.clone();
      const w = this.interior.move(this.pos.x, this.pos.y, this.pos.x + mx, this.pos.y + mz);
      this.pos.set(w.x, w.z);
      const moved = before.distanceTo(this.pos);
      this.bob += moved * 9;
      if (this.target) {
        // give up on click-to-walk if furniture blocks the way
        this.stuck = moved < Math.hypot(mx, mz) * 0.3 ? (this.stuck ?? 0) + dt : 0;
        if (this.stuck > 0.25) (this.target = null), (this.path = null);
      }
    }
    this.apply(dt);
  }

  apply(dt = 0) {
    const bob = Math.sin(this.bob) * 0.012;
    // outdoors the ground's level under the walker (kerbs, the road a step down), eased in
    if (this.interior.groundAt) {
      const h = this.interior.groundAt(this.pos.x, this.pos.y);
      this.base += (h - this.base) * Math.min(1, dt * 8);
    } else this.base = this.interior.baseY;
    this.camera.position.set(this.pos.x, this.base + EYE + bob, this.pos.y);
    this.camera.rotation.set(this.pitch, this.yaw, 0, 'YXZ');
  }

  // position + view direction on the apartment's floor plan, for the mini-map
  localState() {
    const { frame } = this.interior;
    const p = frame.toPlan(this.pos.x, this.pos.y);
    const f = frame.toPlan(this.pos.x - Math.sin(this.yaw), this.pos.y - Math.cos(this.yaw));
    return { x: p.x, y: p.y, dx: f.x - p.x, dy: f.y - p.y };
  }
}
