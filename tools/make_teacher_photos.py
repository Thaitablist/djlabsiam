"""Crops the six teacher photos to one portrait shape (4:5) for the courses / teacher pages.

Source: Picture/Teacher/* (the originals the owner confirmed on 2026-10-06). Output: assets/img/teacher-<slug>-640.webp and -320.webp.
Only cropping + resizing happens here: no retouching, no pixels are painted over. The crop boxes are chosen so every head sits at a similar height
(the shots differ a lot in framing: Zlex is a full-body shot, Alldayz a square one). Run from the website folder: python tools/make_teacher_photos.py
"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "Picture", "Teacher")
OUT = os.path.join(ROOT, "assets", "img")

# slug: (file, cx, fw, y0)   cx = horizontal centre of the box, fw = box width, y0 = top edge  (all as a fraction of the source size; height follows 4:5)
BOXES = {
    "zlex":    ("Zlex.png",              0.54, 0.535, 0.020),
    "leonie":  ("LEONIE.jpg",            0.43, 0.820, 0.020),
    "nutty":   ("Nutty.jpg",             0.50, 1.000, 0.060),
    "tibass":  ("Tibass white bg.jpg",   0.50, 0.700, 0.100),
    "maniac":  ("Maniacหมิง.jpg",        0.54, 0.900, 0.020),
    "alldayz": ("alldayz white bg.png",  0.49, 0.800, 0.000),
}
SIZES = (640, 320)

for slug, (f, cx, fw, y0) in BOXES.items():
    im = Image.open(os.path.join(SRC, f)).convert("RGB")
    W, H = im.size
    bw = fw * W
    bh = bw * 5 / 4
    x0 = min(max(cx * W - bw / 2, 0), W - bw)
    top = y0 * H
    if top + bh > H:
        top = H - bh
    box = tuple(int(round(v)) for v in (x0, top, x0 + bw, top + bh))
    crop = im.crop(box)
    for w in SIZES:
        out = crop.resize((w, w * 5 // 4), Image.LANCZOS)
        p = os.path.join(OUT, f"teacher-{slug}-{w}.webp")
        out.save(p, "WEBP", quality=80, method=6)
    print(f"{slug:8s} source {W}x{H}  box {box}  -> {crop.size[0]}x{crop.size[1]}  ({os.path.getsize(os.path.join(OUT, f'teacher-{slug}-640.webp')) // 1024} KB @640)")
