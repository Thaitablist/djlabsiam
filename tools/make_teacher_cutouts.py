"""Cuts the six teachers out of their photo backgrounds (the owner asked for it on 2026-10-06; the page puts them on a dark panel with a red glow).

Source: Picture/Teacher/* — the originals, never modified.  Output: assets/img/teacher-<slug>-cut-640.webp and -cut-320.webp (4:5, transparent).
Only the background is removed: no retouching of faces or bodies; a clean-up pass removes the light halo of the old backdrop from the edge pixels.
Alldayz is shot at the DJ decks and the owner wants the equipment kept, so for that photo the decks (dark, on a near-white backdrop) are added to the person mask.

Needs (not part of the site, only of this tool):  pip install rembg onnxruntime pymatting numpy scipy pillow
The first run downloads the u2net_human_seg model (176 MB) to ~/.rembg.   Run from the website folder:  python tools/make_teacher_cutouts.py
"""
import os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from pymatting import estimate_foreground_ml
from rembg import new_session, remove

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "Picture", "Teacher")
OUT = os.path.join(ROOT, "assets", "img")

# slug: (file, cx, fw, y0)  — the same crop boxes as tools/make_teacher_photos.py, so every head sits at a similar height (fractions of the source; height follows 4:5)
BOXES = {
    "zlex":    ("Zlex.png",              0.54, 0.535, 0.020),
    "leonie":  ("LEONIE.jpg",            0.43, 0.820, 0.020),
    "nutty":   ("Nutty.jpg",             0.50, 1.000, 0.060),
    "tibass":  ("Tibass white bg.jpg",   0.50, 0.700, 0.100),
    "maniac":  ("Maniacหมิง.jpg",        0.54, 0.900, 0.020),
    "alldayz": ("alldayz white bg.png",  0.49, 0.800, 0.000),
}
KEEP_DECKS = {"alldayz"}
WORK = (960, 1200)      # cut at twice the size of the biggest output, then scale down
SIZES = (640, 320)


def decks_mask(rgb):
    """Everything that is not the light backdrop (flood-filled from the border), limited to the deck area at the bottom and the tonearm on the right."""
    h, w = rgb.shape[:2]
    light = rgb.min(axis=2) > 205
    lab, _ = ndi.label(light)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    fg = ndi.binary_opening(~np.isin(lab, list(edge)), iterations=1).astype(np.float64)
    fg = ndi.gaussian_filter(fg, 0.9)
    yy, xx = np.mgrid[0:h, 0:w]
    return fg * ((yy >= int(0.77 * h)) | ((xx >= int(0.78 * w)) & (yy >= int(0.58 * h))))


session = new_session("u2net_human_seg")
for slug, (f, cx, fw, y0) in BOXES.items():
    im = Image.open(os.path.join(SRC, f)).convert("RGB")
    W, H = im.size
    alpha = np.asarray(remove(im, session=session).getchannel("A"), dtype=np.float64) / 255.0
    if slug in KEEP_DECKS:
        alpha = np.maximum(alpha, decks_mask(np.asarray(im).astype(np.int32)))
    bw = fw * W
    bh = bw * 5 / 4
    x0 = min(max(cx * W - bw / 2, 0), W - bw)
    top = y0 * H
    if top + bh > H:
        top = H - bh
    box = tuple(int(round(v)) for v in (x0, top, x0 + bw, top + bh))
    rgb = np.asarray(im.crop(box).resize(WORK, Image.LANCZOS), dtype=np.float64) / 255.0
    a = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).crop(box).resize(WORK, Image.LANCZOS), dtype=np.float64) / 255.0
    fg = estimate_foreground_ml(rgb, a)            # edge pixels get the person's colour, not the old backdrop's
    cut = Image.fromarray((np.dstack([np.clip(fg, 0, 1), a]) * 255 + 0.5).astype(np.uint8), "RGBA")
    for w in SIZES:
        cut.resize((w, w * 5 // 4), Image.LANCZOS).save(os.path.join(OUT, f"teacher-{slug}-cut-{w}.webp"), "WEBP", quality=82, alpha_quality=100, method=6)
    print(f"{slug:8s} source {W}x{H}  box {box}  ({os.path.getsize(os.path.join(OUT, f'teacher-{slug}-cut-640.webp')) // 1024} KB @640)")
