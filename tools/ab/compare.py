"""Side by side: a client render above, the same view of the model below.

    tools/ab/py tools/ab/compare.py RENDER.jpg SHOT.png OUT.png
"""
import sys
from PIL import Image

r, s, out = sys.argv[1:4]
a = Image.open(r).convert('RGB')
b = Image.open(s).convert('RGB')
W = 1600
a = a.resize((W, round(a.height * W / a.width)), Image.LANCZOS)
b = b.resize((W, round(b.height * W / b.width)), Image.LANCZOS)
im = Image.new('RGB', (W, a.height + b.height + 8), 'white')
im.paste(a, (0, 0))
im.paste(b, (0, a.height + 8))
im.save(out)
