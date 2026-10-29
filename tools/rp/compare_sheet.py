"""Side-by-side sheets for the audit: each client render next to the model shot with its camera
(tools/rp/audit_shots.mjs), before and after a change; and contact sheets of the other views.

    tools/ab/py tools/rp/compare_sheet.py renders BEFORE_DIR [AFTER_DIR] OUT.jpg [render1 ...]
    tools/ab/py tools/rp/compare_sheet.py views BEFORE_DIR [AFTER_DIR] OUT.jpg NAME ...
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, '..', '..', '..', '00_Материалы_клиента', 'Рендеры')
F = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 22)
W = 640


def fit(path, w=W):
    im = Image.open(path).convert('RGB')
    return im.resize((w, int(w * im.size[1] / im.size[0])), Image.LANCZOS)


def sheet(rows, out, head):
    cols = max(len(r) for r in rows)
    H = sum(max(p.size[1] for p, _ in r) + 44 for r in rows)
    im = Image.new('RGB', (cols * (W + 12) + 12, H + 50), (246, 241, 233))
    d = ImageDraw.Draw(im)
    d.text((12, 12), head, fill=(31, 29, 36), font=F)
    y = 50
    for r in rows:
        for i, (p, lab) in enumerate(r):
            x = 12 + i * (W + 12)
            d.text((x, y + 4), lab, fill=(30, 122, 87) if lab.startswith('Стало') else (31, 29, 36), font=F)
            im.paste(p, (x, y + 34))
        y += max(p.size[1] for p, _ in r) + 44
    im.save(out, quality=88)
    print(out, im.size)


def main():
    mode, a = sys.argv[1], sys.argv[2]
    rest = sys.argv[3:]
    b = rest.pop(0) if rest and os.path.isdir(rest[0]) else None
    out = rest.pop(0)
    names = rest
    rows = []
    if mode == 'renders':
        for n in names or [f'render{k}' for k in range(1, 9)]:
            row = [(fit(os.path.join(R, f'render_{n[-1]}.jpg')), f'Рендер {n[-1]} (книга продаж, лист {n[-1]})'),
                   (fit(os.path.join(a, f'{n}.png')), 'Было')]
            if b:
                row.append((fit(os.path.join(b, f'{n}.png')), 'Стало'))
            rows.append(row)
        sheet(rows, out, 'Regnum Plaza: рендеры застройщика и модель с той же точки')
    else:
        for n in names:
            row = [(fit(os.path.join(a, f'{n}.png')), f'Было: {n}')]
            if b:
                row.append((fit(os.path.join(b, f'{n}.png')), f'Стало: {n}'))
            rows.append(row)
        sheet(rows, out, 'Regnum Plaza: ' + ', '.join(names[:3]) + ('…' if len(names) > 3 else ''))


if __name__ == '__main__':
    main()
