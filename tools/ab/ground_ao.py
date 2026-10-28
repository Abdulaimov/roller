"""The baked ground occlusion (blender/bake_ground_ao.py -> build/ground_ao.npy) cleaned for the viewer:
where the receiving plane runs inside something (kerbs, mulch rings, walls: no sky at all) the value
is taken from round about, the sampling grain smoothed. -> public/models/ground_ao.webp
    tools/ab/py tools/ab/ground_ao.py"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
a = np.load(os.path.join(ROOT, 'build/ground_ao.npy')).astype(np.float32) / 255
inside = a < 0.1
# thin things (kerbs, rings, fences): filled from their surroundings; large ones (under buildings)
# are left dark, nothing on the ground is there
thin = inside & ~ndimage.binary_opening(inside, iterations=4)
filled = ndimage.grey_dilation(np.where(inside, 0, a), size=(9, 9))
a = np.where(thin, filled, a)
a = ndimage.gaussian_filter(a, 1.2)
Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), 'L').save(os.path.join(ROOT, 'public/models/ground_ao.webp'), quality=90, method=6)
print('ground AO', a.shape, 'mean', round(float(a.mean()), 3))
