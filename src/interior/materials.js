// Materials of the interiors, created once and shared by every flat. Materials with a repeating
// texture carry userData.boxUV = metres per tile: the kit gives their geometry box-projected UVs
// in metres, so the grain and weave keep their real size on every piece.
import * as THREE from 'three';
import * as T from './textures.js';

let M = null;

// the rooms' lights at night, for a floor opened from outside (main.js sets it from src/night.js;
// walking through a flat its own light does)
export const ROOM_LIGHT = { value: 0 };
const roomLit = (m) => {
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uRoomLight = ROOM_LIGHT;
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform float uRoomLight;')
      .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n  totalEmissiveRadiance += diffuseColor.rgb * vec3(1.0, 0.86, 0.68) * uRoomLight;');
  };
  m.customProgramCacheKey = () => 'roomLit';
  return m;
};

export function interiorMaterials() {
  if (M) return M;
  const std = (o, boxUV) => {
    const m = roomLit(new THREE.MeshStandardMaterial(o));
    if (boxUV) m.userData.boxUV = boxUV;
    return m;
  };
  const phys = (o, boxUV) => {
    const m = roomLit(new THREE.MeshPhysicalMaterial(o));
    if (boxUV) m.userData.boxUV = boxUV;
    return m;
  };

  const oak = T.oakFloor();
  for (const t of [oak.map, oak.rough, oak.bump]) t.repeat.set(1 / oak.metres, 1 / oak.metres);
  const tile = T.porcelain('warm');
  const tileFloor = tile.map.clone();
  tileFloor.repeat.set(1 / tile.metres, 1 / tile.metres);
  tileFloor.needsUpdate = true;
  const plaster = T.plaster();
  const linen = T.weave('linen'), boucle = T.weave('boucle');
  const walnut = T.veneer('walnut'), lightOak = T.veneer('oak');
  const quartz = T.stoneSlab('white'), dark = T.stoneSlab('dark');
  const splash = T.splashTiles();
  const leafTex = T.leaf();

  const fabric = (color, w = linen, sheen = 0.6) =>
    phys({ color, map: w.map, bumpMap: w.bump, bumpScale: 0.6, roughness: 0.95, sheen, sheenRoughness: 0.6, sheenColor: new THREE.Color(color).lerp(new THREE.Color(0xffffff), 0.5), envMapIntensity: 0.6 }, w.metres);

  M = {
    // shell
    floor: std({ map: oak.map, roughnessMap: oak.rough, roughness: 0.62, bumpMap: oak.bump, bumpScale: 0.35, envMapIntensity: 0.9 }),
    tileFloor: std({ map: tileFloor, roughness: 0.22, envMapIntensity: 0.9 }),
    // the floor under the rooms' own, seen only where they stop short (under the doorways, along
    // walls). No polygon offset: pushed back, it lost to the building's slab 3 mm below at grazing
    // angles and a grey strip of concrete showed by the doorways
    floorUnder: std({ map: oak.map, roughnessMap: oak.rough, roughness: 0.62, bumpMap: oak.bump, bumpScale: 0.35, envMapIntensity: 0.9 }),
    tileWall: std({ map: tile.map, roughness: 0.16, envMapIntensity: 0.9 }, tile.metres),
    wall: std({ color: 0xf1ede6, map: plaster.map, roughness: 0.92, envMapIntensity: 0.55 }, plaster.metres),
    struct: std({ color: 0xebe7e0, map: plaster.map, roughness: 0.92, envMapIntensity: 0.55 }, plaster.metres),
    ceiling: std({ color: 0xf7f5f1, roughness: 0.96, side: THREE.DoubleSide, envMapIntensity: 0.5 }),
    skirting: std({ color: 0xf4f2ee, roughness: 0.45 }),
    corridor: std({ color: 0xd2cfc9, roughness: 0.6 }),
    balcony: std({ color: 0xc9c3b9, roughness: 0.8 }),
    door: std({ color: 0xeeebe5, roughness: 0.42 }),
    entrance: std({ map: walnut.map, roughness: 0.5 }, walnut.metres),
    frame: std({ color: 0x34373b, roughness: 0.38, metalness: 0.6 }),
    sill: std({ color: 0xf2f0ec, roughness: 0.25 }),
    glass: new THREE.MeshPhysicalMaterial({ color: 0xc9dbe4, roughness: 0.03, metalness: 0, transparent: true, opacity: 0.16, depthWrite: false, side: THREE.DoubleSide, envMapIntensity: 1.4 }),
    frosted: new THREE.MeshPhysicalMaterial({ color: 0xeef2f2, roughness: 0.6, transparent: true, opacity: 0.55, depthWrite: false, side: THREE.DoubleSide }),
    showerGlass: new THREE.MeshPhysicalMaterial({ color: 0xe4eef0, roughness: 0.02, transparent: true, opacity: 0.12, depthWrite: false, side: THREE.DoubleSide, envMapIntensity: 1.5 }),
    sheer: phys({ color: 0xf6f3ec, map: linen.map, roughness: 1, transparent: true, opacity: 0.8, side: THREE.DoubleSide, depthWrite: false, sheen: 0.4, sheenColor: new THREE.Color(0xffffff) }, 0.25),
    drape: fabric(0xb9ad9c),

    // soft furnishings
    sofa: fabric(0x9c968c, boucle, 0.8),
    sofaDark: fabric(0x5d6266),
    cushionA: fabric(0xb86a4b),
    cushionB: fabric(0xd2b77c),
    cushionC: fabric(0x7f8c7a),
    bedding: fabric(0xf4f2ed, linen, 0.3),
    duvet: fabric(0xe7e1d5, linen, 0.4),
    throw: fabric(0x6f7c80, boucle, 0.7),
    headboard: fabric(0xc9bfae, linen, 0.6),
    chairSeat: fabric(0xcfc4b0, boucle, 0.7),

    // wood, stone, metal
    walnut: std({ map: walnut.map, roughness: 0.48, envMapIntensity: 0.8 }, walnut.metres),
    oak: std({ map: lightOak.map, roughness: 0.55, envMapIntensity: 0.8 }, lightOak.metres),
    quartz: std({ map: quartz.map, roughness: 0.14, envMapIntensity: 1 }, quartz.metres),
    darkStone: std({ map: dark.map, roughness: 0.2, envMapIntensity: 1 }, dark.metres),
    splash: std({ map: splash.map, roughness: 0.12, envMapIntensity: 1 }, splash.metres),
    lacquer: std({ color: 0xe9e5dd, roughness: 0.35, envMapIntensity: 0.8 }),
    sage: std({ color: 0x8e9a88, roughness: 0.55 }),
    blackMetal: std({ color: 0x1c1d1f, roughness: 0.42, metalness: 0.6 }),
    brass: std({ color: 0xc8a165, roughness: 0.28, metalness: 1 }),
    chrome: std({ color: 0xe6e6e6, roughness: 0.06, metalness: 1, envMapIntensity: 1.2 }),
    steel: std({ color: 0xc9cbcd, roughness: 0.32, metalness: 1 }),
    ceramic: std({ color: 0xfbfbfa, roughness: 0.08, envMapIntensity: 1.1 }),
    blackGlass: std({ color: 0x0c0d0f, roughness: 0.06, metalness: 0.2, envMapIntensity: 1.2 }),
    screen: std({ color: 0x08090a, roughness: 0.12, metalness: 0.3, envMapIntensity: 1 }),
    // no real reflection (that would be another render of the room): bright silver with the studio in it
    mirror: std({ color: 0xdfe5e8, roughness: 0.06, metalness: 0.55, envMapIntensity: 3 }),
    rubber: std({ color: 0x222222, roughness: 0.9 }),
    radiator: std({ color: 0xf5f4f1, roughness: 0.32 }),

    // light
    shade: std({ color: 0xf3ece0, emissive: 0xffd7a6, emissiveIntensity: 0.55, roughness: 0.9, side: THREE.DoubleSide }),
    bulb: std({ color: 0xffffff, emissive: 0xfff0d8, emissiveIntensity: 6 }),
    downlight: std({ color: 0xffffff, emissive: 0xfff4e4, emissiveIntensity: 4 }),
    strip: std({ color: 0xffffff, emissive: 0xffe8c8, emissiveIntensity: 2.2 }),

    // decor
    leaf: std({ map: leafTex, alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.6, envMapIntensity: 0.5 }),
    soil: std({ color: 0x2e2620, roughness: 1 }),
    pot: std({ color: 0xd8d2c7, roughness: 0.7 }),
    terracotta: std({ color: 0xb46a48, roughness: 0.85 }),
    rugBeige: std({ map: T.rug('beige').map, roughness: 1, envMapIntensity: 0.4 }),
    rugGrey: std({ map: T.rug('grey').map, roughness: 1, envMapIntensity: 0.4 }),
    art: [0, 1, 2, 3].map((v) => std({ map: T.painting(v), roughness: 0.85 })),
    towel: fabric(0xe9e4da, T.weave('boucle'), 0.5),
  };
  M.byColor = new Map();
  M.color = (c, roughness = 0.6) => {
    const k = `${c}/${roughness}`;
    if (!M.byColor.has(k)) M.byColor.set(k, std({ color: c, roughness }));
    return M.byColor.get(k);
  };
  return M;
}
