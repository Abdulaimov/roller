"""Before / after from the same cameras: two folders of screenshots with the same names (tools/shots.mjs)
side by side, labelled, one JPEG a view.
    tools/ab/py tools/ab/before_after.py BEFORE_DIR AFTER_DIR OUT_DIR [view ...]"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = ImageFont.truetype('/System/Library/Fonts/Avenir Next.ttc', 30, index=2)


def label(im, text):
    pil = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    w = d.textlength(text, font=FONT)
    d.rounded_rectangle((16, 16, 16 + w + 32, 66), 12, fill=(31, 29, 36))
    d.text((32, 22), text, font=FONT, fill=(246, 241, 233))
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

before, after, out = sys.argv[1:4]
names = sys.argv[4:] or sorted(f[:-4] for f in os.listdir(before) if f.endswith('.png'))
os.makedirs(out, exist_ok=True)
for n in names:
    a, b = cv2.imread(os.path.join(before, n + '.png')), cv2.imread(os.path.join(after, n + '.png'))
    if a is None or b is None:
        print('skip', n)
        continue
    h = 720
    a = cv2.resize(a, (round(a.shape[1] * h / a.shape[0]), h), interpolation=cv2.INTER_AREA)
    b = cv2.resize(b, (round(b.shape[1] * h / b.shape[0]), h), interpolation=cv2.INTER_AREA)
    a, b = label(a, 'До'), label(b, 'После')
    cv2.imwrite(os.path.join(out, f'{n}.jpg'), np.hstack([a, np.full((h, 12, 3), 255, np.uint8), b]), [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(n)
