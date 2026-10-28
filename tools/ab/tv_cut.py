"""Put the TV film together from the frames tools/ab/tv_film.mjs rendered: each shot in turn, a
one-second dissolve where they overlap (tools/ab/tv_shots.mjs); for the day-to-night version a
dissolve back to the first frame over the last 1.5 s (it loops into daylight). Encodes H.264,
yuv420p, Rec.709 (SDR, limited range), constant 30 fps, no audio track; the 4K master and a Full HD
copy scaled from it.
    FFMPEG=/path/to/ffmpeg tools/ab/py tools/ab/tv_cut.py FRAMES_DIR OUT_4K.mp4 OUT_HD.mp4"""
import json
import os
import subprocess
import sys

import cv2
import numpy as np

frames_dir, out4k, outhd = sys.argv[1:4]
FF = os.environ.get('FFMPEG', os.path.expanduser('~/Desktop/KIMCHI_promo_reel/node_modules/ffmpeg-static/ffmpeg'))
film = json.load(open(os.path.join(frames_dir, 'film.json')))
FPS, length, W, H = film['FPS'], film['length'], film['W'], film['H']
FADE = 1.0
shots = film['shots']
total = round(length * FPS)
cache = {}


def frame(shot, k):
    k = max(0, min(round(shot['dur'] * FPS) - 1, k))
    key = (shot['name'], k)
    if key not in cache:
        if len(cache) > 8:
            cache.clear()
        im = cv2.imread(os.path.join(frames_dir, shot['name'], f'f_{k:04d}.jpg'))
        if im is None:
            raise SystemExit(f'missing frame {shot["name"]} {k}')
        cache[key] = im.astype(np.float32)
    return cache[key]


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


vf = 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p'
enc = [FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
       '-an', '-vf', vf, '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-maxrate', '60M', '-bufsize', '120M',
       '-profile:v', 'high', '-level:v', '5.1', '-g', str(FPS * 2), '-r', str(FPS),
       '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
       '-movflags', '+faststart', out4k]
p = subprocess.Popen(enc, stdin=subprocess.PIPE)
first = None
loop = film['variant'] == 'daynight'
for g in range(total):
    T = g / FPS
    on = [s for s in shots if s['start'] - 1e-6 <= T < s['start'] + s['dur'] - 1e-6]
    a = on[0]
    im = frame(a, round((T - a['start']) * FPS))
    if len(on) > 1:
        b = on[1]
        w = smooth((T - b['start']) / FADE)
        im = im * (1 - w) + frame(b, round((T - b['start']) * FPS)) * w
    if g == 0:
        first = im.copy()
    if loop and T > length - 1.5:
        w = smooth((T - (length - 1.5)) / 1.5)
        im = im * (1 - w) + first * w
    p.stdin.write(np.clip(im + 0.5, 0, 255).astype(np.uint8).tobytes())
    if g % 300 == 0:
        print(f'{g}/{total}', flush=True)
p.stdin.close()
if p.wait() != 0:
    raise SystemExit('ffmpeg failed')
subprocess.run([FF, '-y', '-loglevel', 'error', '-i', out4k, '-an', '-vf', 'scale=1920:1080:flags=lanczos:in_color_matrix=bt709:out_color_matrix=bt709:in_range=tv:out_range=tv,format=yuv420p',
                '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-profile:v', 'high', '-level:v', '4.2', '-g', str(FPS * 2), '-r', str(FPS),
                '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
                '-movflags', '+faststart', outhd], check=True)
print('done', out4k, outhd)
