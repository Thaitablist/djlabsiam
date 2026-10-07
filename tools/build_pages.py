#!/usr/bin/env python3
"""Builds the static pages  /courses/  ·  /teachers/<name>/ (x6)  ·  /content/  from the shop's single source of truth.

  courses.json   bots/bot/shared/courses.json   (courses, prices, hours, audience, prerequisite, tracks, teachers)   <- NEVER retyped here
  data/teacher-profiles.json   per-teacher bio / video (empty = that section is not shown at all)
  data/faq.json                FAQ (numbers are {placeholders} filled from courses.json) - the visible FAQ and the JSON-LD both come from it
  data/programs.json           regular programmes of /content/

Each generated file carries the md5 of the courses.json it was built from; tools/check_pages.py compares that with the current file before every push.
Standard library only.  Usage (from anywhere):  python tools/build_pages.py [--courses PATH] [--profiles PATH] [--out DIR]
"""
import argparse, hashlib, html, io, json, os, re, sys, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ORIGIN = "https://djlabsiam.com"
LINE_ADD = "https://line.me/ti/p/@djlabsiam"
LINE_MSG = "https://line.me/R/oaMessage/%40djlabsiam/?"   # the message goes straight after "?" (not "?text=")
E = html.escape


def die(msg):
    sys.exit("build_pages: " + msg)


ap = argparse.ArgumentParser()
ap.add_argument("--courses", default=os.path.join(os.path.dirname(SITE), "bots", "bot", "shared", "courses.json"))
ap.add_argument("--profiles", default=os.path.join(SITE, "data", "teacher-profiles.json"))
ap.add_argument("--faq", default=os.path.join(SITE, "data", "faq.json"))
ap.add_argument("--programs", default=os.path.join(SITE, "data", "programs.json"))
ap.add_argument("--course-images", default=os.path.join(SITE, "data", "course-images.json"))
ap.add_argument("--out", default=SITE)
A = ap.parse_args()


def load(p):
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)


RAW = io.open(A.courses, "rb").read()
MD5 = hashlib.md5(RAW).hexdigest()
D = json.loads(RAW.decode("utf-8"))
COURSES = D["items"]
TEACHERS = D["instructors"]["items"]
PROFILES = load(A.profiles)
FAQ = load(A.faq)["items"]
_PROG = load(A.programs)
PROGRAMS = _PROG["items"]
LISTEN = _PROG["listen"]
CIMG = load(A.course_images) if os.path.exists(A.course_images) else {}   # per-course picture: {file, w, h, alt} or null = no picture, no empty space


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def short(title):
    return title.replace(" Class", "")


def cid(title):
    return slug(short(title))


# ───────── consistency of the inputs (stop instead of publishing something half-true) ─────────
names = [t["name"] for t in TEACHERS]
pk = [k for k in PROFILES if not k.startswith("_")]
if sorted(pk) != sorted(names):
    die(f"teacher-profiles.json keys {sorted(pk)} != teachers in courses.json {sorted(names)}")
for c in COURSES:
    for t in c["instructors"]:
        if t not in names:
            die(f"{c['title']} lists instructor {t!r} who is not in instructors.items")
    for k in ("title", "price", "hours", "audience", "bullets", "instructors"):
        if k not in c:
            die(f"{c['title']} has no {k!r}")
for t, im in CIMG.items():
    if t.startswith("_") or not im:
        continue
    if t not in [c["title"] for c in COURSES]:
        die(f"course-images.json: {t!r} is not a course in courses.json")
    if not all(im.get(k) for k in ("base", "widths", "w", "h", "alt")):
        die(f"course-images.json: {t!r} needs base, widths, w, h and alt")
    for w in im["widths"]:
        if not os.path.exists(os.path.join(SITE, "assets", "img", f"{im['base']}-{w}.webp")):
            die(f"course-images.json: assets/img/{im['base']}-{w}.webp does not exist")
for n, p in PROFILES.items():
    if n.startswith("_"):
        continue
    if bool(p.get("video_id")) != bool(p.get("poster")):
        die(f"{n}: video_id and poster must be given together")
    if p.get("video_id") and not re.fullmatch(r"[A-Za-z0-9_-]{11}", p["video_id"]):
        die(f"{n}: video_id is not an 11-character YouTube id")
    if p.get("poster") and not os.path.exists(os.path.join(SITE, "assets", "img", p["poster"])):
        die(f"{n}: poster assets/img/{p['poster']} does not exist")


# ───────── facts derived from the JSON text ─────────
def facts(c):
    h = c["hours"]
    m = re.search(r"เรียน\s*(\d+)\s*ชม", h)
    s = re.search(r"(\d+)\s*ครั้ง\s*\((\d+)\s*ชม", h)
    if not (m and s):
        die(f"cannot read hours of {c['title']}: {h!r}")
    pr = re.search(r"ห้องซ้อมและอุปกรณ์\s*(\d+)\s*ชม", h)
    equip_b = next((b for b in c["bullets"] if b.startswith("เลือกอุปกรณ์ได้:") or b.startswith("เลือกเรียนได้") or b.startswith("Turntable only")), "")
    if equip_b.startswith("Turntable only"):
        equip = equip_b.split("—", 1)[0].strip().replace(" only", " เท่านั้น")
    else:
        equip = equip_b.split(":", 1)[1].strip() if ":" in equip_b else ""
    content = next((b for b in c["bullets"] if b.startswith("เนื้อหา:")), "")
    if not content and equip_b.startswith("Turntable only") and "—" in equip_b:
        content = equip_b.split("—", 1)[1].strip()
    life = next((b for b in c["bullets"] if "อายุคอร์ส" in b), "")
    return dict(learn=int(m.group(1)), sessions=int(s.group(1)), per=int(s.group(2)), practice=int(pr.group(1)) if pr else 0,
                price=c["price"], equip=equip, content=content.replace("เนื้อหา:", "").strip(), life=life,
                weekly=any("เรียนอย่างน้อยสัปดาห์ละครั้ง" in b for b in c["bullets"]))


F = {c["title"]: facts(c) for c in COURSES}
teaches = {t["name"]: [c["title"] for c in COURSES if t["name"] in c["instructors"]] for t in TEACHERS}
SHARED_ALL = all(len({str(F[t][k]) for t in F}) == 1 for k in ("learn", "sessions", "per", "price"))
F0 = F[COURSES[0]["title"]]
PRACTICE_COURSE = next((c["title"] for c in COURSES if F[c["title"]]["practice"]), None)
FP = F[PRACTICE_COURSE] if PRACTICE_COURSE else None
needle = ""
for c in COURSES:
    m = re.search(r"\(([^)]*ปลายเข็ม[^)]*)\)", F[c["title"]]["equip"])
    if m:
        needle = m.group(1)
        break


def faq_text(a):
    life_m = re.search(r"\d+\s*เดือน", F0["life"])
    if not life_m or len({f["life"] for f in F.values()}) != 1:
        die("the payment FAQ states one course life (e.g. '3 เดือน') for all courses, but courses.json has none or differing ones")
    vals = dict(
        course_names=", ".join(short(c["title"]) for c in COURSES), price=F0["price"], learn=F0["learn"], sessions=F0["sessions"], per=F0["per"],
        practice_course=PRACTICE_COURSE or "", practice=FP["practice"] if FP else 0, total=(FP["learn"] + FP["practice"]) if FP else 0,
        needle_note=needle, life=F0["life"], life_months=life_m.group(0), teacher_count=len(TEACHERS),
        weekly_courses=" และ ".join(short(c["title"]) for c in COURSES if F[c["title"]]["weekly"]),
        equip_sentence=" · ".join(f"{short(c['title'])}: {F[c['title']]['equip']}" for c in COURSES if F[c["title"]]["equip"]))
    try:
        return a.format_map(vals)
    except KeyError as e:
        die(f"faq.json uses an unknown placeholder {e}")


FAQ_RENDERED = [(it["q"], faq_text(it["a"])) for it in FAQ]


# ───────── small helpers ─────────
def line_url(text):
    return LINE_MSG + urllib.parse.quote(text, safe="")


def line_btn(text, label, cls="pri"):
    return f'<a class="btn {cls}" href="{line_url(text)}" rel="noopener"><span class="dot"></span>{E(label)}</a>'


ICON = {
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "play": '<path d="M8 5.5v13l11-6.5z" fill="currentColor" stroke="none"/>',
    "ext": '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1z"/>',
    "alert": '<circle cx="12" cy="12" r="8.5"/><path d="M12 8v5M12 16.2v.1"/>',
}


def ic(n, s=20):
    return (f'<svg class="ico" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICON[n]}</svg>')


def photo(name, w, size_attr, cls=""):
    s = slug(name)
    return (f'<img{(" class=" + chr(34) + cls + chr(34)) if cls else ""} src="/assets/img/teacher-{s}-cut-640.webp" '
            f'srcset="/assets/img/teacher-{s}-cut-320.webp 320w, /assets/img/teacher-{s}-cut-640.webp 640w" sizes="{size_attr}" '
            f'width="640" height="800" alt="" loading="lazy" decoding="async">')


# ───────── page shell ─────────
def fonts_css():
    book = io.open(os.path.join(SITE, "book", "index.html"), encoding="utf-8").read()
    faces = re.findall(r"@font-face\{[^}]*\}", book)
    if len(faces) != 10:
        die(f"expected 10 @font-face rules in book/index.html, found {len(faces)}")
    return "\n".join(f.replace("url(fonts/", "url(/book/fonts/") for f in faces)


TOKENS = io.open(os.path.join(SITE, "design-system", "build", "tokens.inline.css"), encoding="utf-8").read()
FONTS = fonts_css()

CSS = r"""
:root{color-scheme:dark;scrollbar-color:#555 #0F0F0F}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--surface-page);color:var(--text-primary);font:400 16px/1.7 var(--font-family-body);-webkit-font-smoothing:antialiased}
h1,h2,h3,h4{font-family:var(--font-family-display);font-weight:900;margin:0;letter-spacing:0;text-wrap:balance}
h1{font-size:34px;line-height:1.3}
h2{font-size:26px;line-height:1.3}
h3{font-size:18px;line-height:1.4;font-weight:800}
p{margin:0}
a{color:inherit}
img{display:block;max-width:100%;height:auto}
::selection{background:var(--brand-base);color:#fff}
:focus-visible{outline:3px solid #fff;outline-offset:3px}
.skip{position:absolute;left:12px;top:-80px;z-index:20;background:#fff;color:#0F0F0F;padding:12px 16px;font:700 16px/1.25 var(--font-family-display)}
.skip:focus{top:12px}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.ico{flex:0 0 auto}
.dot{width:10px;height:10px;border-radius:50%;background:#06C755;flex:0 0 auto;box-shadow:0 0 0 2px rgba(255,255,255,.9)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:10px;min-height:48px;padding:6px 22px;font:700 16px/1.3 var(--font-family-display);text-align:center;text-decoration:none;border:1px solid transparent;cursor:pointer;background:none;color:inherit}
.btn.pri{background:var(--brand-base);color:var(--brand-on)}
.btn.pri:hover{background:var(--brand-hover)}
.btn.sec{border-color:var(--border-strong);color:var(--text-primary)}
.btn.sec:hover{background:rgba(255,255,255,.08)}
.btn.sm{min-height:44px;padding:4px 16px;font-size:15px}
.chip{display:inline-flex;align-items:center;min-height:28px;padding:0 10px;font:700 14px/1.25 var(--font-family-display);border:1px solid var(--border-strong)}
.chip.rec{background:var(--text-primary);color:var(--surface-page);border-color:var(--text-primary)}
/* header */
.top{position:relative;display:flex;align-items:center;gap:12px;padding:10px 24px;min-height:68px;border-bottom:1px solid var(--border-hairline)}
.logo{display:inline-flex;align-items:center;min-height:44px}
.logo img{width:126px;height:42px}
.tnav{display:none}
.top>.btn{margin-left:auto}
.mnav>summary{list-style:none;display:inline-flex;align-items:center;min-height:44px;padding:0 16px;border:1px solid var(--border-strong);font:700 15px/1 var(--font-family-display);cursor:pointer}
.mnav>summary::-webkit-details-marker{display:none}
.mnav nav{position:absolute;left:0;right:0;top:100%;z-index:10;display:grid;padding:4px 24px 14px;background:var(--surface-page);border-bottom:1px solid var(--border-strong)}
.mnav nav a{display:flex;align-items:center;min-height:52px;text-decoration:none;font:700 18px/1.3 var(--font-family-display);border-bottom:1px solid var(--border-hairline)}
.mnav nav a:last-child{border-bottom:0}
/* footer */
.foot{display:grid;gap:20px;padding:36px 24px 44px;border-top:1px solid var(--border-hairline);color:var(--text-secondary);font-size:15px}
.foot b{font:800 18px/1.4 var(--font-family-display);color:var(--text-primary)}
.foot a{display:inline-flex;align-items:center;min-height:44px}
/* rhythm */
.pgm{padding:0 24px}
.pgm>section{padding:56px 0 0}
.pgm>section:last-child{padding-bottom:64px}
.hero{padding-top:44px!important}
.hero h1{max-width:18ch}
.lede{margin-top:16px;max-width:56ch;color:var(--text-secondary);font-size:17px}
.cta{display:flex;flex-wrap:wrap;gap:12px;margin-top:28px}
.cta .btn{width:100%}
.shared{margin-top:28px;padding-top:18px;border-top:1px solid var(--border-hairline);color:var(--text-secondary);max-width:70ch}
.shared b{color:var(--text-primary)}
/* chooser */
.choose h2{font-size:22px}
.choose ul{list-style:none;margin:16px 0 0;padding:0;border-top:1px solid var(--border-hairline)}
.choose li{display:grid;padding:10px 0 4px;border-bottom:1px solid var(--border-hairline)}
.choose li span{color:var(--text-secondary)}
.choose li a{display:inline-flex;align-items:center;gap:8px;min-height:44px;font:700 17px/1.25 var(--font-family-display);text-decoration:none}
.choose li a:hover{color:var(--text-brand)}
/* course rows */
.courses{padding-top:24px!important}
.course{display:grid;gap:22px;padding:40px 0;border-top:1px solid var(--border-strong)}
.course h2{font-size:30px;line-height:1.25;display:inline}
.course .chip{margin-left:12px;vertical-align:middle}
.fit{margin-top:12px;color:var(--text-primary);font-size:17px}
.cimg{margin:0 0 20px}
.cimg img{width:100%;height:auto}
.spec{display:grid;grid-template-columns:1fr 1fr;margin-top:20px;border:1px solid var(--border-strong)}
.spec>div{padding:12px 16px;display:flex;flex-direction:column;gap:2px}
.spec .s1{order:1;border-right:1px solid var(--border-hairline)}
.spec .s3{order:2}
.spec .s2{order:3;grid-column:1/-1;border-top:1px solid var(--border-hairline)}
.spec .k{font-size:14px;color:var(--text-muted)}
.spec b{font:800 18px/1.4 var(--font-family-display)}
.spec .price{font-size:30px;line-height:1.25;font-weight:900}
.plus{margin-top:12px;font-size:15px;color:var(--text-secondary)}
.plus b{color:var(--text-primary)}
.pre{margin:0 0 20px;padding:14px 16px;border:1px solid var(--border-strong)}
.pre b{display:block;font:800 15px/1.4 var(--font-family-display);margin-bottom:4px}
.bl,.tracks{margin:12px 0 0;padding:0;list-style:none;display:grid;gap:10px}
.bl li,.tracks li{padding-left:18px;position:relative;color:var(--text-secondary)}
.bl li::before,.tracks li::before{content:"";position:absolute;left:0;top:.8em;width:8px;height:2px;background:var(--brand-base)}
.tracks{margin-bottom:18px}
.tracks b{color:var(--text-primary);font-family:var(--font-family-display);font-weight:700}
.tpick{margin:6px 0 14px;color:var(--text-secondary)}
.own{margin:22px 0 0;font:700 15px/1.4 var(--font-family-display);color:var(--text-secondary)}
.faces{display:grid;grid-template-columns:repeat(2,1fr);gap:10px 12px;margin:14px 0 0}
.face{display:flex;align-items:center;gap:10px;min-height:52px;text-decoration:none;font:600 15px/1.25 var(--font-family-display)}
.face:hover span{text-decoration:underline;text-underline-offset:3px}
.av{display:block;width:52px;height:52px;overflow:hidden;background:#EFEEEA;flex:0 0 auto}
.av img{width:52px;height:52px;object-fit:cover;object-position:50% 8%}
.c-c .btn{width:100%}
.c-c .btn+.btn,.stick .btn+.btn{margin-top:10px}
/* compare: only what differs; stacked per attribute on phones */
.cmpsec h2,.team h2,.faq h2,.endcta h2{font-size:26px}
.same{margin-top:14px;color:var(--text-secondary);max-width:70ch}
.same b{color:var(--text-primary)}
.tbl-wrap{margin-top:20px}
.cmp{width:100%;border-collapse:collapse;font-size:15px;line-height:1.6;display:block}
.cmp tbody,.cmp tr{display:block}
.cmp thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.cmp tr{padding:20px 0;border-top:1px solid var(--border-hairline)}
.cmp th,.cmp td{padding:0;text-align:left;vertical-align:top}
.cmp tbody th{display:block;padding-bottom:10px;font:700 18px/1.6 var(--font-family-display);color:var(--text-primary)}
.cmp td{display:grid;grid-template-columns:112px 1fr;gap:12px;padding:6px 0;color:var(--text-secondary)}
.cmp td::before{content:attr(data-label);font:700 14px/1.7 var(--font-family-display);color:var(--text-muted)}
/* team */
.lede2{margin-top:10px;color:var(--text-secondary);max-width:70ch}
.tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:16px 12px;margin-top:24px}
.tile{display:flex;flex-direction:column;gap:8px;text-decoration:none;padding-bottom:8px}
.tile .tp{display:block;aspect-ratio:4/5;overflow:hidden;background:var(--surface-raised)}
.tile .tp img{width:100%;height:100%;object-fit:cover}
.tp img,.pph img{filter:drop-shadow(0 0 4px rgba(190,35,41,.95)) drop-shadow(0 0 20px rgba(190,35,41,.6))}
.tile b{font:800 18px/1.3 var(--font-family-display)}
.tile .tc{font-size:14px;line-height:1.5;color:var(--text-secondary)}
.tile:hover b{text-decoration:underline;text-underline-offset:4px}
.tile.sm .tp{aspect-ratio:1/1}
.tile.sm .tp img{object-position:50% 10%}
/* faq */
.qs{margin-top:20px;border-top:1px solid var(--border-strong)}
.q{border-bottom:1px solid var(--border-hairline)}
.q summary{list-style:none;cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:56px;padding:10px 0;font:700 17px/1.45 var(--font-family-display)}
.q summary::-webkit-details-marker{display:none}
.q summary::after{content:"";flex:0 0 auto;width:10px;height:10px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(45deg);margin-right:6px;transition:transform var(--motion-duration-fast) var(--motion-easing-base)}
.q[open] summary::after{transform:rotate(-135deg)}
.q p{padding:0 0 18px;color:var(--text-secondary);max-width:72ch}
.endcta{border-top:1px solid var(--border-strong)}
/* profile */
.crumb{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;padding-top:20px!important;font-size:15px;color:var(--text-muted)}
.crumb a{display:inline-flex;align-items:center;justify-content:center;min-height:44px;min-width:44px;color:var(--text-secondary)}
.pg2{display:grid;gap:28px;padding-top:8px}
.pph{margin:0;background:var(--surface-raised);aspect-ratio:4/5;overflow:hidden;align-self:start}
.pph img{width:100%;height:100%;object-fit:cover}
.pbody{display:grid;gap:36px;align-content:start}
.pname{display:grid;gap:4px}
.pbody h1{font-size:40px}
.role{color:var(--text-secondary);font-size:17px}
.pbody section{display:grid;gap:12px}
.pbody h2{font-size:22px}
.cchips{display:flex;flex-wrap:wrap;gap:10px}
.cchip{display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 16px;border:1px solid var(--border-strong);text-decoration:none;font:700 16px/1.25 var(--font-family-display)}
.cchip:hover{background:rgba(255,255,255,.08)}
.one{color:var(--text-secondary)}
.bio{color:var(--text-secondary);max-width:62ch}
.stick{display:grid;gap:0;justify-items:start}
.stick .btn{width:100%}
.others h2{font-size:26px}
/* video: click-to-load */
.fc{display:grid;gap:8px}
.fc-box{position:relative;aspect-ratio:16/9;background:var(--surface-sunken);overflow:hidden;border:1px solid var(--border-hairline)}
.fc-box>img,.fc-box>iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.fc-box>img{object-fit:cover}
.fc-btn{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;width:100%;border:0;background:linear-gradient(0deg,rgba(0,0,0,.55),rgba(0,0,0,.05) 60%);color:#fff;cursor:pointer}
.fc-btn svg{width:56px;height:56px;padding:14px;background:var(--brand-base);color:#fff}
.fc-btn:hover svg{background:var(--brand-hover)}
.fc-msg{position:absolute;inset:0;display:none;place-content:center;justify-items:center;gap:12px;padding:16px;text-align:center;background:rgba(0,0,0,.78);color:var(--text-secondary);font-size:15px}
.fc-box.loading .fc-msg.l,.fc-box.failed .fc-msg.e{display:grid}
.fc-box.loading .fc-btn,.fc-box.failed .fc-btn{display:none}
.cl-group{margin-top:32px}
.cl-group h3{font-size:22px;line-height:1.3}
.cl-list{list-style:none;margin:12px 0 0;padding:0;max-width:760px}
.cl-i{display:grid;gap:8px;padding:18px 0;border-top:1px solid var(--border-hairline)}
.cl-title{margin:0;font:700 18px/1.5 var(--font-family-display);overflow-wrap:anywhere}
.cl-meta{margin:0;font-size:15px;color:var(--text-secondary)}
.cl-actions{display:flex;flex-wrap:wrap;gap:10px}
.cl-frame{position:relative;aspect-ratio:16/9;background:var(--surface-sunken);border:1px solid var(--border-hairline)}
.cl-frame.short{aspect-ratio:9/16;max-width:300px}
.cl-frame>iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.cl-fail{position:absolute;left:0;right:0;bottom:0;margin:0;padding:10px 14px;background:rgba(0,0,0,.82);font-size:15px}
.cl-note{margin:8px 0 0;font-size:15px;color:var(--text-secondary)}
.cl-group .btn.sec:not(.sm){margin-top:12px}
.cl-err,.cl-empty{display:flex;flex-wrap:wrap;align-items:center;gap:12px 16px;padding:16px 18px;max-width:760px}
.cl-err p,.cl-empty p{margin:0;flex:1 1 260px}
.cl-err{border:1px solid var(--brand-base);background:rgba(190,35,41,.16)}
.cl-empty{border:1px solid var(--border-strong)}
.fc-priv{font-size:14px}
.fc-priv summary{display:inline-flex;align-items:center;min-height:44px;cursor:pointer;list-style:none;font:600 14px/1.4 var(--font-family-display);color:var(--text-secondary);text-decoration:underline;text-underline-offset:4px}
.fc-priv summary::-webkit-details-marker{display:none}
.fc-priv p{margin:0 0 8px;max-width:64ch;color:var(--text-secondary)}
/* content page */
.listen{display:flex;flex-wrap:wrap;gap:12px;margin-top:24px}
.slgrid{display:grid;gap:16px;margin-top:20px}
.slc{display:grid;gap:12px;justify-items:start;align-content:start;padding:24px;border:1px solid var(--border-strong)}
.slc h3{font-size:30px;line-height:1.25}
.slc p{color:var(--text-secondary);max-width:52ch}
.slc .when{color:var(--text-primary)}
.ytcta{display:grid;gap:14px;justify-items:start;margin-top:20px;padding:24px;border:1px solid var(--border-hairline)}
.ytcta p{color:var(--text-secondary);max-width:56ch}
@media (min-width:960px){
  h1{font-size:44px}
  .top{padding:10px 80px}
  .top>.btn{margin-left:0}
  .tnav{display:flex;gap:4px;margin-left:12px}
  .tnav a{display:inline-flex;align-items:center;min-height:44px;padding:0 14px;text-decoration:none;font:600 16px/1 var(--font-family-display);color:var(--text-secondary)}
  .tnav a:hover{color:var(--text-primary)}
  .tnav a.on{color:var(--text-primary);box-shadow:inset 0 -2px 0 var(--brand-base)}
  .tnav+.btn{margin-left:auto}
  .mnav{display:none}
  .foot{grid-template-columns:2fr 2fr 1fr;padding:48px 80px 56px}
  .pgm{padding:0 80px}
  .pgm>section{padding:88px 0 0}
  .pgm>section:last-child{padding-bottom:96px}
  .hero{padding-top:72px!important}
  .hero h1{font-size:56px;line-height:1.25;max-width:20ch}
  .lede{font-size:19px}
  .cta .btn{width:auto}
  .choose{max-width:760px}
  .choose li{grid-template-columns:1fr auto;align-items:center;gap:24px;padding:4px 0}
  .course{grid-template-columns:5fr 4fr 3fr;gap:44px;padding:56px 0}
  .course h2{font-size:42px}
  .cmpsec h2,.team h2,.faq h2,.endcta h2{font-size:34px}
  .tbl-wrap{margin-top:24px}
  .cmp{display:table}
  .cmp tbody{display:table-row-group}
  .cmp tr{display:table-row;padding:0;border:0}
  .cmp thead{position:static;width:auto;height:auto;overflow:visible;clip:auto;display:table-header-group}
  .cmp th,.cmp td{display:table-cell;padding:14px 16px 14px 0;border-bottom:1px solid var(--border-hairline)}
  .cmp thead th{font:800 17px/1.3 var(--font-family-display);border-bottom:1px solid var(--border-strong)}
  .cmp tbody th{width:150px;padding-bottom:14px;font-size:15px;color:var(--text-secondary)}
  .cmp td::before{content:none}
  .tiles{grid-template-columns:repeat(6,1fr);gap:16px}
  .tiles.s{grid-template-columns:repeat(5,1fr)}
  .qs{max-width:860px}
  .pg2{grid-template-columns:5fr 7fr;gap:72px;padding-top:24px}
  .pph{position:sticky;top:24px}
  .pbody h1{font-size:64px;line-height:1.2}
  .stick .btn{width:auto;min-width:340px}
  .slgrid{grid-template-columns:1fr 1fr;gap:24px}
  .slc{padding:36px}
}
@media (prefers-reduced-motion:reduce){.q summary::after{transition:none}}
"""


# Meta Pixel (assets/js/meta-pixel.js holds the only Pixel ID; empty = nothing loads and this row stays hidden). Never on /book/.
PIXEL_ROW = '<div data-pixel-row hidden><button type="button" data-pixel-toggle>ปิดการวัดผลโฆษณา</button><span data-pixel-state aria-live="polite"></span></div>'
PIXEL_SCRIPT = '<script src="/assets/js/meta-pixel.js" defer></script>\n'


def shell(path, title, desc, body, robots=None, ld=None, script="", active=""):
    links = [("คอร์สเรียน", "/courses/", "courses"), ("ทีมครู", "/courses/#teachers", "teachers"), ("จองห้องซ้อม", "/book/", "book")]
    li = "".join(f'<a href="{h}"{" class=on aria-current=page" if k == active else ""}>{t}</a>' for t, h, k in links)
    top = (f'<a class="skip" href="#main">ข้ามไปเนื้อหาหลัก</a>'
           f'<header class="top"><a class="logo" href="/"><img src="/book/logo-header.png" width="126" height="42" alt="DJ LAB SIAM — หน้าแรก"></a>'
           f'<nav class="tnav" aria-label="เมนูหลัก">{li}</nav>'
           f'<a class="btn pri sm" href="{LINE_ADD}" rel="noopener"><span class="dot"></span>ติดต่อ LINE</a>'
           f'<details class="mnav"><summary>เมนู</summary><nav aria-label="เมนูหลักบนมือถือ">{li}</nav></details></header>')
    foot = ('<footer class="foot"><div><b>DJ LAB SIAM</b><p>Lido Connect ชั้น 2, Siam Square Soi 3<br>ปทุมวัน กรุงเทพฯ 10330</p></div>'
            '<div><p>เปิด 12:00–20:00 น. ทุกวัน<br>02-252-5868 · 088-656-0464<br>LINE @djlabsiam</p></div>'
            '<div><a href="/privacy.html">นโยบายความเป็นส่วนตัว</a></div>' + PIXEL_ROW + '</footer>')
    ldj = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False).replace("</", "<" + chr(92) + "/")}</script>' for x in (ld or []))
    og = (f'<meta property="og:type" content="website"><meta property="og:url" content="{ORIGIN}{path}"><meta property="og:title" content="{E(title)}">'
          f'<meta property="og:description" content="{E(desc)}"><meta property="og:image" content="{ORIGIN}/og_image.png"><meta property="og:locale" content="th_TH">'
          f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(desc)}">'
          f'<meta name="twitter:image" content="{ORIGIN}/og_image.png">')
    return (f'<!DOCTYPE html>\n<!-- generated by tools/build_pages.py from bots/bot/shared/courses.json (md5 {MD5}) — do not edit by hand -->\n'
            f'<html lang="th">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'<title>{E(title)}</title>\n<meta name="description" content="{E(desc)}">\n'
            + (f'<meta name="robots" content="{robots}">\n' if robots else '')
            + f'<link rel="canonical" href="{ORIGIN}{path}">\n{og}\n<meta name="theme-color" content="#0F0F0F">\n'
            f'<link rel="icon" href="/favicon.ico" sizes="any">\n<link rel="icon" href="/favicon-512.png" type="image/png" sizes="512x512">\n<link rel="apple-touch-icon" href="/apple-touch-icon.png">\n'
            f'<link rel="preload" href="/book/fonts/noto-sans-thai-latin.woff2" as="font" type="font/woff2" crossorigin>\n'
            f'<link rel="preload" href="/book/fonts/noto-sans-thai-thai.woff2" as="font" type="font/woff2" crossorigin>\n'
            f'<style>\n{FONTS}\n{TOKENS}\n{CSS}</style>\n{ldj}\n</head>\n<body>\n{top}\n<main id="main" class="pgm">{body}</main>\n{foot}\n{PIXEL_SCRIPT}{script}</body>\n</html>\n')


# ───────── /courses/ ─────────
def cimg(c):
    im = CIMG.get(c["title"])
    if not im:
        return ""
    ws = sorted(int(w) for w in im["widths"])
    srcset = ", ".join(f"/assets/img/{im['base']}-{w}.webp {w}w" for w in ws)
    return (f'<figure class="cimg"><img src="/assets/img/{im["base"]}-{int(im["w"])}.webp" srcset="{srcset}" sizes="(min-width:960px) 424px, 92vw" '
            f'width="{int(im["w"])}" height="{int(im["h"])}" alt="{E(im["alt"])}" loading="lazy" decoding="async"></figure>')


def course_row(c, i):
    f = F[c["title"]]
    extra = ""
    if f["practice"]:
        extra = (f'<p class="plus"><b>รวมห้องซ้อมและอุปกรณ์ {f["practice"]} ชม.</b> · เวลารวม {f["learn"] + f["practice"]} ชม. '
                 f'(เรียน {f["learn"]} + ซ้อม {f["practice"]})</p>')
    bullets = "".join(f"<li>{E(b)}</li>" for b in c["bullets"] if not b.startswith("เวลารวม"))
    rec = '<span class="chip rec">สำหรับผู้เริ่มต้น</span>' if "ผู้เริ่มต้น" in c["audience"] else ""
    faces = "".join(f'<a class="face" href="/teachers/{slug(t)}/" aria-label="โปรไฟล์ {E(t)}"><span class="av">{photo(t, 52, "52px")}</span><span>{E(t)}</span></a>' for t in c["instructors"])
    pre = f'<div class="pre"><b>ก่อนเรียน</b><p>{E(c["prerequisite"])}</p></div>' if c.get("prerequisite") else ""
    tracks = ""
    if c.get("tracks"):
        items = "".join(f'<li><b>{E(t["name"])}</b>{(" — " + E(t["detail"])) if t.get("detail") else ""}</li>' for t in c["tracks"])
        tracks = f'<h3>สายที่เลือกเรียนได้</h3><ul class="tracks">{items}</ul>'
    return (f'<article class="course" id="{cid(c["title"])}">'
            f'<div class="c-a">{cimg(c)}<h2>{E(c["title"])}</h2>{rec}<p class="fit">{E(c["audience"])}</p>'
            f'<div class="spec"><div class="s1"><span class="k">เรียน</span><b>ตัวต่อตัว</b></div>'
            f'<div class="s2"><span class="k">เวลาเรียน</span><b>{f["sessions"]} ครั้ง × {f["per"]} ชม. = {f["learn"]} ชม.</b></div>'
            f'<div class="s3"><span class="k">ราคา</span><b class="price">{E(f["price"])}</b></div></div>{extra}</div>'
            f'<div class="c-b">{pre}{tracks}<h3>รายละเอียดคอร์ส</h3><ul class="bl">{bullets}</ul></div>'
            f'<div class="c-c"><h3>อาจารย์ผู้สอน</h3><p class="tpick">ไม่ต้องเลือกก็ได้ ร้านจัดอาจารย์ที่เหมาะกับคอร์สและเวลาว่างให้</p>'
            f'{line_btn("สนใจคอร์ส " + c["title"] + " ให้ร้านจัดอาจารย์ให้", "ทัก LINE · ให้ร้านจัดอาจารย์ให้")}'
            f'<h4 class="own">อยากเลือกอาจารย์เอง ดูโปรไฟล์ได้</h4><div class="faces">{faces}</div></div></article>')


def compare_table():
    heads = [short(c["title"]) for c in COURSES]
    ft = [F[c["title"]] for c in COURSES]
    rows_all = [
        ("ราคา", [E(f["price"]) for f in ft]),
        ("เวลาเรียน", [f'{f["sessions"]} ครั้ง × {f["per"]} ชม. = {f["learn"]} ชม.' for f in ft]),
        ("อายุคอร์ส", [E(f["life"].replace("อายุคอร์ส", "").strip()) for f in ft]),
        ("ก่อนเรียน", [E(c["prerequisite"]) if c.get("prerequisite") else "ไม่มี" for c in COURSES]),
        ("ห้องซ้อมและอุปกรณ์", [(f'รวม {f["practice"]} ชม.' if f["practice"] else "ไม่รวม") for f in ft]),
        ("เรียนบนอุปกรณ์", [E(f["equip"]) for f in ft]),
        ("สายที่เลือกเรียนได้", [(" · ".join((t.get("detail", "") if t["name"].startswith("เลือก") else t["name"]) for t in c.get("tracks") or []) or "—") for c in COURSES]),
        ("เนื้อหา", [E(f["content"]) if f["content"] else "ดูสายที่เลือกเรียนได้" for f in ft]),
        ("อาจารย์", [" · ".join(E(t) for t in c["instructors"]) for c in COURSES]),
    ]
    same, rows = [], []
    for label, cells in rows_all:
        if len(set(cells)) == 1:
            same.append((label, cells[0]))
        else:
            tds = "".join(f'<td data-label="{E(h)}"><span>{x}</span></td>' for h, x in zip(heads, cells))
            rows.append(f'<tr><th scope="row">{label}</th>{tds}</tr>')
    same_txt = " · ".join(["ตัวต่อตัว"] + [f"{l} {v}" for l, v in same])
    th = "".join(f'<th scope="col">{E(h)}</th>' for h in heads)
    return (f'<p class="same"><b>เหมือนกันทุกคอร์ส:</b> {same_txt}</p>'
            f'<div class="tbl-wrap"><table class="cmp"><caption class="vh">ข้อที่ต่างกันระหว่างคอร์ส</caption>'
            f'<thead><tr><th scope="col"><span class="vh">หัวข้อ</span></th>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def tiles(cls="", small=False, exclude=None):
    out = ""
    for t in TEACHERS:
        n = t["name"]
        if n == exclude:
            continue
        tc = "" if small else f'<span class="tc">สอน: {E(" · ".join(short(x) for x in teaches[n]))}</span>'
        out += (f'<a class="tile{" sm" if small else ""}" href="/teachers/{slug(n)}/"><span class="tp">{photo(n, 320, "(min-width:960px) 16vw, 45vw")}</span>'
                f'<b>{E(n)}</b>{tc}</a>')
    return f'<div class="tiles{cls}">{out}</div>'


def courses_page():
    chooser = "".join(f'<li><span>{E(GOAL.get(c["title"], c["audience"]))}</span><a href="#{cid(c["title"])}">{E(c["title"])} {ic("arrow", 18)}</a></li>' for c in COURSES)
    shared = ""
    if SHARED_ALL:
        shared = (f'<p class="shared"><b>ทุกคอร์สเรียนตัวต่อตัว</b> · {F0["sessions"]} ครั้ง × {F0["per"]} ชม. = {F0["learn"]} ชม. · {E(F0["price"])} '
                  f'· เลือกวัน/เวลาเรียนได้ตามสะดวก</p>')
    faq = "".join(f'<details class="q"{" open" if i == 0 else ""}><summary>{E(q)}</summary><p>{E(a)}</p></details>' for i, (q, a) in enumerate(FAQ_RENDERED))
    body = (f'<section class="hero"><h1>คอร์สเรียน DJ ตัวต่อตัว</h1>'
            f'<p class="lede">เรียน DJ จากมืออาชีพตัวจริง เลือกวัน เลือกเวลา เลือกอุปกรณ์ได้ตามสะดวก</p>'
            f'<div class="cta">{line_btn("ขอคำแนะนำเลือกคอร์ส", "ทักหา LINE ให้ทีมช่วยเลือกคอร์ส")}<a class="btn sec" href="#compare">ดูตารางเทียบคอร์ส</a></div>{shared}</section>'
            f'<section class="choose" aria-labelledby="ch"><h2 id="ch">ไม่แน่ใจว่าเริ่มที่คอร์สไหน</h2><ul>{chooser}</ul></section>'
            f'<section class="courses" aria-label="คอร์สทั้งหมด">{"".join(course_row(c, i) for i, c in enumerate(COURSES))}</section>'
            f'<section class="cmpsec" id="compare"><h2>เทียบคอร์สทีละข้อ</h2>{compare_table()}</section>'
            f'<section class="team" id="teachers"><h2>ทีมครูผู้สอน</h2><p class="lede2">{E(D["instructors"]["intro"])} ไม่ต้องเลือกก็ได้ ร้านจัดอาจารย์ที่เหมาะกับคอร์สและเวลาว่างให้ · อยากเรียนกับท่านใด ดูโปรไฟล์แล้วเลือกได้</p>{tiles()}</section>'
            f'<section class="faq" id="faq"><h2>คำถามที่พบบ่อยเรื่องคอร์ส</h2><div class="qs">{faq}</div></section>'
            f'<section class="endcta"><h2>ยังไม่แน่ใจ? ทักมาคุยก่อนได้</h2><div class="cta">{line_btn("ขอคำแนะนำเลือกคอร์ส", "ทักหา LINE @djlabsiam")}'
            f'<a class="btn sec" href="tel:022525868">{ic("phone", 18)} โทร 02-252-5868</a></div></section>')
    names_ = ", ".join(short(c["title"]) for c in COURSES)
    desc = (f'คอร์สเรียน DJ ตัวต่อตัว {len(COURSES)} คอร์ส ({names_}) ราคา {F0["price"]} เรียน {F0["learn"]} ชั่วโมง เลือกวันและเวลาเรียนได้ '
            f'ที่ DJ LAB SIAM สยามสแควร์') if SHARED_ALL else "คอร์สเรียน DJ ตัวต่อตัว ที่ DJ LAB SIAM สยามสแควร์"
    ld = [{"@context": "https://schema.org", "@type": "FAQPage",
           "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ_RENDERED]}]
    return shell("/courses/", "คอร์สเรียน DJ ตัวต่อตัว — DJ LAB SIAM สยามสแควร์", desc, body, ld=ld, active="courses")


# the chooser's short labels: my own abbreviation of each audience text (the owner sees them in the wording list); falls back to the full audience text
GOAL = {"Basic DJ Class": "เริ่มจาก 0 ก็เรียนได้", "Advance DJ Class": "DJ ที่ต้องการพัฒนาทักษะของตัวเอง",
        "Basic Scratch Class": "สนใจการสแครช", "Advance Scratch Class": "มีพื้นฐานการสแครชแล้ว"}


# ───────── /teachers/<name>/ ─────────
VIDEO_JS = """<script>
(function(){document.querySelectorAll('.fc-box[data-vid]').forEach(function(box){var b=box.querySelector('.fc-btn');if(!b)return;
b.addEventListener('click',function(){var id=box.getAttribute('data-vid');if(!/^[A-Za-z0-9_-]{11}$/.test(id))return;
box.classList.add('loading');var f=document.createElement('iframe');
f.src='https://www.youtube-nocookie.com/embed/'+id+'?autoplay=1&rel=0';f.title=box.getAttribute('data-title');
f.allow='autoplay; encrypted-media; picture-in-picture';f.referrerPolicy='strict-origin-when-cross-origin';f.setAttribute('allowfullscreen','');
var t=setTimeout(function(){box.classList.remove('loading');box.classList.add('failed')},10000);
f.addEventListener('load',function(){clearTimeout(t);box.classList.remove('loading')});box.appendChild(f)})})})();
</script>
"""

PRIVACY_NOTE = ('<details class="fc-priv"><summary>ข้อมูลความเป็นส่วนตัวของวิดีโอ</summary>'
                '<p>ก่อนกดเล่น หน้านี้ไม่เรียกข้อมูลใดจาก YouTube เมื่อกดเล่น เบราว์เซอร์ของคุณจะเชื่อมต่อกับ YouTube (Google) เพื่อแสดงวิดีโอ โดยใช้โหมดความเป็นส่วนตัวขั้นสูง (youtube-nocookie.com) '
                'Google อาจเก็บข้อมูลการใช้งานตามนโยบายของ Google ร้านไม่ได้รับข้อมูลนั้น · <a href="/privacy.html">นโยบายความเป็นส่วนตัวของร้าน</a></p></details>')


def teacher_page(t):
    name = t["name"]
    s = slug(name)
    prof = PROFILES[name]
    chips = "".join(f'<a class="cchip" href="/courses/#{cid(x)}">{E(x)} {ic("arrow", 16)}</a>' for x in teaches[name])
    sections = f'<section><h2>คอร์สที่สอน</h2><div class="cchips">{chips}</div><p class="one">ทุกคอร์สเรียนตัวต่อตัว</p></section>'
    if prof.get("bio"):
        sections += f'<section><h2>เกี่ยวกับ {E(name)}</h2><p class="bio">{E(prof["bio"])}</p></section>'
    if prof.get("highlights"):
        sections += f'<section><h2>ผลงาน</h2><ul class="bl">{"".join("<li>" + E(h) + "</li>" for h in prof["highlights"])}</ul></section>'
    script = ""
    if prof.get("video_id"):
        sections += (f'<section><h2>วิดีโอแนะนำ</h2><div class="fc"><div class="fc-box" data-vid="{E(prof["video_id"])}" data-title="วิดีโอแนะนำ {E(name)}">'
                     f'<img src="/assets/img/{E(prof["poster"])}" width="1280" height="720" alt="" loading="lazy">'
                     f'<button class="fc-btn" type="button" aria-label="เล่นวิดีโอแนะนำของ {E(name)}">{ic("play", 28)}</button>'
                     f'<div class="fc-msg l" role="status">กำลังเชื่อมต่อ YouTube…</div>'
                     f'<div class="fc-msg e">{ic("alert")} เปิดวิดีโอในหน้านี้ไม่ได้<a class="btn sec sm" href="https://www.youtube.com/watch?v={E(prof["video_id"])}" rel="noopener">ดูบน YouTube {ic("ext", 16)}</a></div></div>'
                     f'{PRIVACY_NOTE}</div></section>')
        script = VIDEO_JS
    soc = t.get("social")
    if soc:
        host = urllib.parse.urlparse(soc).netloc.lower()
        label = "Instagram" if "instagram" in host else ("Linktree" if "linktr.ee" in host else "ลิงก์ของ " + name)
        sections += f'<section><h2>ติดตาม</h2><div><a class="btn sec sm" href="{E(soc)}" target="_blank" rel="noopener">{label} {ic("ext", 16)}</a></div></section>'
    sections += (f'<div class="stick"><p class="tpick">ไม่ต้องเลือกอาจารย์ก็ได้ ร้านจัดอาจารย์ที่เหมาะกับคอร์สและเวลาว่างให้</p>'
                 f'{line_btn("สนใจเรียน ให้ร้านจัดอาจารย์ให้", "ทัก LINE · ให้ร้านจัดอาจารย์ให้")}'
                 f'{line_btn("สนใจเรียนกับอาจารย์ " + name, "ขอเรียนกับอาจารย์ " + name, "sec")}</div>')
    body = (f'<nav class="crumb" aria-label="เส้นทาง"><a href="/courses/">คอร์สเรียน</a><span aria-hidden="true">/</span><a href="/courses/#teachers">ทีมครู</a>'
            f'<span aria-hidden="true">/</span><span aria-current="page">{E(name)}</span></nav>'
            f'<div class="pg2"><figure class="pph"><img src="/assets/img/teacher-{s}-cut-640.webp" srcset="/assets/img/teacher-{s}-cut-320.webp 320w, /assets/img/teacher-{s}-cut-640.webp 640w" '
            f'sizes="(min-width:960px) 40vw, 92vw" width="640" height="800" alt="{E(name)} อาจารย์ DJ LAB SIAM" fetchpriority="high" decoding="async"></figure>'
            f'<div class="pbody"><div class="pname"><h1>{E(name)}</h1><p class="role">{E(t["role"].replace(",", " ·"))}</p></div>{sections}</div></div>'
            f'<section class="others"><h2>อาจารย์ท่านอื่น</h2>{tiles(" s", True, exclude=name)}</section>')
    taught = ", ".join(teaches[name])
    return shell(f"/teachers/{s}/", f"{name} — อาจารย์ DJ LAB SIAM",
                 f"{name} สอน {taught} แบบตัวต่อตัว ที่ DJ LAB SIAM สยามสแควร์", body, script=script, active="teachers")


# ───────── /content/ ─────────
def book_backend():
    b = io.open(os.path.join(SITE, "book", "index.html"), encoding="utf-8").read()
    api, key = re.search(r"const API='(https://[a-z0-9.-]+\.supabase\.co/rest/v1/rpc/)'", b), re.search(r"const KEY='([A-Za-z0-9._-]+)'", b)
    if not (api and key):
        die("cannot read the Supabase address / anon key from book/index.html")
    return api.group(1), key.group(1)


CONTENT_JS = r"""<script>
(function(){
var API='@@API@@',KEY='@@KEY@@',PAGE=12,KINDS=[['podcast','Podcast'],['video','วิดีโอ'],['short','Shorts']];
var MONTH=['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
var status=document.getElementById('cl-status'),lists=document.getElementById('cl-lists');
if(!status||!lists)return;
function el(tag,cls,text){var e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
function thDate(iso){var d=new Date(iso);if(isNaN(d))return '';var t=new Date(d.getTime()+7*3600000);return t.getUTCDate()+' '+MONTH[t.getUTCMonth()]+' '+(t.getUTCFullYear()+543)}
function dur(s){if(typeof s!=='number'||!(s>0))return '';if(s<60)return s+' วินาที';var m=Math.round(s/60),h=Math.floor(m/60);return h?h+' ชม.'+(m%60?' '+(m%60)+' นาที':''):m+' นาที'}
async function rpc(args){var ctl=new AbortController(),to=setTimeout(function(){ctl.abort()},15000);
  try{var r=await fetch(API+'web_content_videos',{method:'POST',headers:{apikey:KEY,Authorization:'Bearer '+KEY,'Content-Type':'application/json'},body:JSON.stringify(args),signal:ctl.signal});
    if(!r.ok)throw new Error('http '+r.status);var j=await r.json();if(!j||j.ok!==true||!Array.isArray(j.items))throw new Error('bad answer');return j}
  finally{clearTimeout(to)}}
function play(li,v,btn){
  var short=v.kind==='short',box=el('div','cl-frame'+(short?' short':'')),f=document.createElement('iframe'),msg=el('p','cl-fail','เปิดวิดีโอในหน้านี้ไม่ได้ ');
  var a=el('a','','ดูบน YouTube');a.href='https://www.youtube.com/watch?v='+v.id;a.target='_blank';a.rel='noopener';msg.appendChild(a);msg.hidden=true;
  f.src='https://www.youtube-nocookie.com/embed/'+v.id+'?autoplay=1&rel=0';f.title=v.title;
  f.allow='autoplay; encrypted-media; picture-in-picture';f.referrerPolicy='strict-origin-when-cross-origin';f.setAttribute('allowfullscreen','');
  var t=setTimeout(function(){msg.hidden=false},10000);f.addEventListener('load',function(){clearTimeout(t)});
  box.appendChild(f);box.appendChild(msg);btn.hidden=true;li.appendChild(box)}
function item(v){
  var li=el('li','cl-i');li.appendChild(el('p','cl-title',v.title));
  var meta=[thDate(v.published_at),dur(v.duration_s)].filter(Boolean).join(' · ');if(meta)li.appendChild(el('p','cl-meta',meta));
  var row=el('div','cl-actions'),btn=null;
  if(v.embeddable!==false){btn=el('button','btn pri sm','เล่นที่นี่');btn.type='button';btn.setAttribute('aria-label','เล่น: '+v.title);btn.addEventListener('click',function(){play(li,v,btn)});row.appendChild(btn)}
  var a=el('a','btn sec sm','ดูบน YouTube');a.href='https://www.youtube.com/watch?v='+v.id;a.target='_blank';a.rel='noopener';row.appendChild(a);li.appendChild(row);return li}
function validItems(j){return j.items.filter(function(v){return v&&typeof v.id==='string'&&/^[A-Za-z0-9_-]{11}$/.test(v.id)&&typeof v.title==='string'&&v.title})}
function makeGroup(kind,label){
  var box=el('section','cl-group'),ul=el('ul','cl-list'),more=el('button','btn sec','โหลดเพิ่ม'),note=el('p','cl-note');more.type='button';more.hidden=true;note.hidden=true;
  box.hidden=true;box.appendChild(el('h3','',label));box.appendChild(ul);box.appendChild(more);box.appendChild(note);lists.appendChild(box);
  var g={next:null,count:0,failed:false};
  g.load=async function(){
    var args={p_limit:PAGE,p_kind:kind};if(g.next){args.p_before=g.next.before;args.p_before_id=g.next.before_id}
    more.disabled=true;note.hidden=true;
    try{var j=await rpc(args);validItems(j).forEach(function(v){ul.appendChild(item(v));g.count++});
      g.next=j.next&&j.next.before&&j.next.before_id?j.next:null;g.failed=false;more.hidden=!g.next;box.hidden=g.count===0}
    catch(e){if(g.count){note.textContent='โหลดเพิ่มไม่สำเร็จ ลองกดอีกครั้ง';note.hidden=false;more.hidden=false}else g.failed=true}
    more.disabled=false};
  more.addEventListener('click',g.load);return g}
var groups=KINDS.map(function(k){return makeGroup(k[0],k[1])});
function banner(){status.textContent='';status.removeAttribute('role');
  var failed=groups.some(function(g){return g.failed}),total=groups.reduce(function(n,g){return n+g.count},0);
  if(failed){status.setAttribute('role','alert');var b=el('div','cl-err');b.appendChild(el('p','','โหลดรายการคลิปไม่สำเร็จ ตรวจสอบอินเทอร์เน็ตแล้วลองใหม่'));
    var r=el('button','btn sec sm','ลองใหม่');r.type='button';r.addEventListener('click',start);b.appendChild(r);status.appendChild(b);return}
  if(!total){var e=el('div','cl-empty');e.appendChild(el('p','','ตอนนี้ยังไม่มีคลิปแสดงที่หน้านี้ ดูคลิปทั้งหมดได้ที่ช่อง YouTube ของ DJ LAB SIAM'));
    var a=el('a','btn pri','ดูคลิปทั้งหมดบน YouTube');a.href='https://www.youtube.com/@DJLABSIAM';a.target='_blank';a.rel='noopener';e.appendChild(a);status.appendChild(e)}}
async function start(){status.removeAttribute('role');status.textContent='กำลังโหลดรายการคลิป…';
  await Promise.all(groups.filter(function(g){return !g.count}).map(function(g){return g.load()}));banner()}
start();
})();
</script>
"""


CONTENT_NOTE = ('<details class="fc-priv"><summary>ข้อมูลความเป็นส่วนตัวของหน้านี้</summary>'
                '<p>รายการคลิปดึงจากฐานข้อมูลของร้านบน Supabase เมื่อเปิดหน้านี้ Supabase จะได้รับข้อมูลทางเทคนิคของคุณ เช่น หมายเลข IP และชนิดเบราว์เซอร์ '
                'ก่อนกดเล่น หน้านี้ไม่เรียกข้อมูลใดจาก YouTube เมื่อกด "เล่นที่นี่" เบราว์เซอร์ของคุณจะเชื่อมต่อกับ YouTube (Google) เพื่อแสดงวิดีโอ โดยใช้โหมดความเป็นส่วนตัวขั้นสูง (youtube-nocookie.com) '
                'Google อาจเก็บข้อมูลการใช้งานตามนโยบายของ Google ร้านไม่ได้รับข้อมูลนั้น · <a href="/privacy.html">นโยบายความเป็นส่วนตัวของร้าน</a></p></details>')


def content_page():
    cards = ""
    for p in PROGRAMS:
        inner = f'<h3>{E(p["name"])}</h3>'
        if p.get("when"):
            inner += f'<p class="when"><b>{E(p["when"])}</b></p>'
        if p.get("desc"):
            inner += f'<p>{E(p["desc"])}</p>'
        if p.get("link"):
            inner += f'<a class="btn pri" href="{E(p["link"])}" target="_blank" rel="noopener">{E(p.get("link_label", "ดูรายการ"))} {ic("ext", 18)}</a>'
        cards += f'<div class="slc">{inner}</div>'
    listen = "".join(f'<a class="btn {"pri" if i == 0 else "sec"}" href="{E(x["url"])}" target="_blank" rel="noopener">{E(x["label"])} {ic("ext", 18)}</a>' for i, x in enumerate(LISTEN))
    api, key = book_backend()
    body = (f'<section class="hero"><h1>วิดีโอและรายการจาก DJ LAB SIAM</h1>'
            f'<p class="lede">เทคนิค อุปกรณ์ และเรื่องราววงการ DJ จากทีมงานที่เป็น DJ จริง</p><div class="listen">{listen}</div></section>'
            f'<section><h2>รายการประจำ</h2><div class="slgrid">{cards}</div></section>'
            f'<section id="clips"><h2>คลิปล่าสุด</h2><div id="cl-status" aria-live="polite"></div><div id="cl-lists"></div>'
            f'<noscript><p class="lede2">ต้องเปิด JavaScript เพื่อดูรายการคลิปในหน้านี้ หรือดูคลิปทั้งหมดได้ที่ช่อง YouTube</p></noscript>{CONTENT_NOTE}</section>'
            f'<section><h2>คลิปบน YouTube</h2><div class="ytcta"><p>คลิปทั้งหมดของร้านอยู่ที่ช่อง YouTube</p>'
            f'<a class="btn pri" href="https://www.youtube.com/@DJLABSIAM" target="_blank" rel="noopener">ดูคลิปทั้งหมดบน YouTube {ic("ext", 18)}</a></div></section>')
    return shell("/content/", "วิดีโอและรายการ — DJ LAB SIAM", "รายการประจำและคลิปจากทีม DJ LAB SIAM", body, robots="noindex,follow", active="content",
                 script=CONTENT_JS.replace("@@API@@", api).replace("@@KEY@@", key))


def write(path, text):
    full = os.path.join(A.out, path.strip("/").replace("/", os.sep), "index.html")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with io.open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return full, len(text.encode("utf-8"))


made = [write("/courses/", courses_page())]
for t in TEACHERS:
    made.append(write(f"/teachers/{slug(t['name'])}/", teacher_page(t)))
made.append(write("/content/", content_page()))
for p, n in made:
    print(f"{n / 1024:6.1f} KB  {os.path.relpath(p, A.out)}")
print(f"courses.json md5 {MD5} · {len(COURSES)} courses · {len(TEACHERS)} teachers")
