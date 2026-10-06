"""Crops the four course illustrations (photos the owner supplied on 2026-10-06) to one 3:2 shape and writes webp files in several widths.

Source folder (NOT in the repo, 4.5 MB): E:\\ZLEXX\\DJ LAB\\รูปถ่าย\\ภาพประกอบคอร์ส\\   (override with --src)
Output: assets/img/course-photo-<course>-<width>.webp and data/course-images.json (the page reads that file).
Only cropping + resizing happens here: no retouching. The two DJ-class photos are cropped to the hands on the controller (no face, no clothing print).
Never upscales: a width is only written when the crop is at least that wide. Run from the website folder:  python tools/make_course_photos.py
"""
import argparse, io, json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ap = argparse.ArgumentParser()
ap.add_argument("--src", default=r"E:\ZLEXX\DJ LAB\รูปถ่าย\ภาพประกอบคอร์ส")
A = ap.parse_args()
OUT = os.path.join(ROOT, "assets", "img")
RATIO = 3 / 2
WIDTHS = (480, 800, 1200)

# course title in courses.json -> (source file, cx, fw, y0, alt)   cx = horizontal centre of the box, fw = box width, y0 = top edge (fractions of the source)
CROPS = {
    "Basic DJ Class":        ("basic-dj",        "Basic DJ Mixing.jpg",    0.54, 0.691, 0.712, "มือกำลังเล่นแพดบนคอนโทรลเลอร์ DJ"),
    "Advance DJ Class":      ("advance-dj",      "Advance DJ Mixing.jpg",  0.45, 0.833, 0.680, "มือกำลังเล่นแพดและปุ่มบนคอนโทรลเลอร์ DJ"),
    "Basic Scratch Class":   ("basic-scratch",   "Basic Scratching.jpg",   0.536, 0.9275, 0.0, "มือวางบนจานเสียงสีน้ำเงินของเครื่อง DJ"),
    "Advance Scratch Class": ("advance-scratch", "Advance Scratching.jpg", 0.52, 0.92, 0.08, "DJ ยืนหลังเทิร์นเทเบิลสองเครื่องและมิกเซอร์"),
}

entries = {}
for title, (slug, f, cx, fw, y0, alt) in CROPS.items():
    im = Image.open(os.path.join(A.src, f)).convert("RGB")
    W, H = im.size
    bw = fw * W
    bh = bw / RATIO
    x0 = min(max(cx * W - bw / 2, 0), W - bw)
    top = min(max(y0 * H, 0), H - bh)
    box = tuple(int(round(v)) for v in (x0, top, x0 + bw, top + bh))
    crop = im.crop(box)
    cw, ch = crop.size
    widths = [w for w in WIDTHS if w <= cw] or [cw]
    for w in widths:
        h = round(w / RATIO)
        crop.resize((w, h), Image.LANCZOS).save(os.path.join(OUT, f"course-photo-{slug}-{w}.webp"), "WEBP", quality=78, method=6)
    dw = 800 if 800 in widths else widths[-1]
    entries[title] = {"base": f"course-photo-{slug}", "widths": widths, "w": dw, "h": round(dw / RATIO), "alt": alt}
    print(f"{slug:16s} source {W}x{H}  box {box} -> {cw}x{ch}  widths {widths}")

with io.open(os.path.join(ROOT, "data", "course-images.json"), "w", encoding="utf-8", newline="\n") as fh:
    json.dump({"_about": "ภาพประกอบของแต่ละคอร์สบน /courses/ — สร้างโดย tools/make_course_photos.py จากรูปที่เจ้าของให้ 6 ต.ค. 2569 (ครอป 3:2 หลายขนาด ไม่แต่งภาพ) · base = ชื่อไฟล์ใน assets/img/ (ต่อท้าย -<กว้าง>.webp) · null = ไม่แสดงภาพและไม่เว้นช่องว่าง · ห้ามใช้ภาพเดิม course-*.webp (เขียนชื่อเก่า BASIC/ADVNC MIXING)", **entries},
              fh, ensure_ascii=False, indent=2)
    fh.write("\n")
