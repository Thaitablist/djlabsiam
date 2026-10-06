#!/usr/bin/env python3
"""Checks the generated pages (courses/, teachers/*/, content/) before they are pushed.  Exit code 1 = at least one check failed.

  python tools/check_pages.py [--courses PATH]

What it proves: every page was built from the courses.json that is on disk NOW (md5), every price / hour / name / teacher / audience / prerequisite /
track on the pages matches that file, the visible FAQ equals the JSON-LD FAQ, nothing is loaded from another domain, no banned words, no "coming soon"
placeholders, every image has width/height/alt, the privacy policy covers YouTube if any page can load a video, and the sitemap lists exactly the
indexable pages.  Standard library only.
"""
import argparse, glob, hashlib, html, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ap = argparse.ArgumentParser()
ap.add_argument("--courses", default=os.path.join(os.path.dirname(SITE), "bots", "bot", "shared", "courses.json"))
A = ap.parse_args()

fails, passes = [], 0


def ok(cond, msg):
    global passes
    if cond:
        passes += 1
    else:
        fails.append(msg)


def read(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def text_of(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


raw = io.open(A.courses, "rb").read()
md5 = hashlib.md5(raw).hexdigest()
D = json.loads(raw.decode("utf-8"))
COURSES, TEACHERS = D["items"], D["instructors"]["items"]

pages = {"courses": os.path.join(SITE, "courses", "index.html"), "content": os.path.join(SITE, "content", "index.html")}
for t in TEACHERS:
    pages["teacher:" + t["name"]] = os.path.join(SITE, "teachers", slug(t["name"]), "index.html")
SRC = {}
for k, p in pages.items():
    ok(os.path.exists(p), f"{k}: file missing ({os.path.relpath(p, SITE)})")
    if os.path.exists(p):
        SRC[k] = read(p)

BANNED = [r"DJplus", r"DJZLEX", r"ZX24", r"Group Class", r"รีวิว", r"★", r"เร็ว ?ๆ ?นี้", r"coming soon"]
ALLOWED_RES_HOSTS = ("djlabsiam.com",)

for k, s in SRC.items():
    # 1. built from the courses.json that is on disk now
    m = re.search(r"courses\.json \(md5 ([0-9a-f]{32})\)", s)
    ok(bool(m) and m.group(1) == md5, f"{k}: built from a different courses.json (page {m.group(1) if m else 'no stamp'} vs now {md5}) — run tools/build_pages.py")
    # 2. structure
    ok(s.count("<h1") == 1, f"{k}: expected exactly one <h1>")
    ok('<html lang="th">' in s, f"{k}: missing lang=th")
    ok('rel="canonical"' in s, f"{k}: missing canonical")
    ok('class="skip"' in s and 'id="main"' in s, f"{k}: missing skip link / main landmark")
    ok(len(s.encode("utf-8")) < 80 * 1024, f"{k}: page is {len(s.encode('utf-8')) // 1024} KB (limit 80 KB)")
    # 3. banned words / placeholders (visible text only)
    vis = text_of(s)
    for b in BANNED:
        ok(not re.search(b, vis, re.I), f"{k}: banned phrase {b!r} on the page")
    # 4. nothing loaded from another domain (img / script / iframe / stylesheet / preload / icon)
    for tag, attr in (("img", "src"), ("script", "src"), ("iframe", "src"), ("link", "href")):
        for t in re.findall(rf"<{tag}\b[^>]*>", s):
            if tag == "link" and not re.search(r'rel="(stylesheet|preload|icon|apple-touch-icon)"', t):
                continue
            v = re.search(rf'\b{attr}="([^"]*)"', t)
            if v and re.match(r"https?://", v.group(1)):
                ok(any(v.group(1).startswith("https://" + h) for h in ALLOWED_RES_HOSTS), f"{k}: loads {v.group(1)} from another domain")
            elif v and v.group(1).startswith("//"):
                ok(False, f"{k}: protocol-relative resource {v.group(1)}")
    # 5. images: width/height/alt + the file exists
    for t in re.findall(r"<img\b[^>]*>", s):
        ok("width=" in t and "height=" in t and "alt=" in t, f"{k}: <img> without width/height/alt: {t[:80]}")
        for u in re.findall(r'(?:src|srcset)="([^"]*)"', t):
            for part in u.split(","):
                path = part.strip().split(" ")[0]
                if path.startswith("/"):
                    ok(os.path.exists(os.path.join(SITE, path.lstrip("/").replace("/", os.sep))), f"{k}: image {path} does not exist")

# ---- courses page: every fact comes from courses.json ----
cs = text_of(SRC.get("courses", ""))
for c in COURSES:
    ok(c["title"] in cs, f"courses: title {c['title']!r} missing")
    ok(c["price"] in cs, f"courses: price {c['price']!r} missing for {c['title']}")
    h = re.search(r"(\d+)\s*ครั้ง\s*\((\d+)\s*ชม", c["hours"])
    L = re.search(r"เรียน\s*(\d+)\s*ชม", c["hours"])
    ok(bool(h and L) and f"{h.group(1)} ครั้ง × {h.group(2)} ชม. = {L.group(1)} ชม." in cs, f"courses: hours line of {c['title']} missing/different")
    ok(c["audience"] in cs, f"courses: audience of {c['title']} missing")
    if c.get("prerequisite"):
        ok(c["prerequisite"] in cs, f"courses: prerequisite of {c['title']} missing")
    for tr in c.get("tracks") or []:
        ok(tr["name"] in cs and (tr.get("detail") or "") in cs, f"courses: track {tr['name']!r} of {c['title']} missing")
    for b in c["bullets"]:
        if not b.startswith("เวลารวม"):
            ok(b in cs, f"courses: bullet missing for {c['title']}: {b[:40]}")
    for t in c["instructors"]:
        block = re.search(rf'<article class="course" id="{slug(c["title"].replace(" Class", ""))}">(.*?)</article>', SRC.get("courses", ""), re.S)
        ok(bool(block) and f'href="/teachers/{slug(t)}/"' in block.group(1), f"courses: {t} is not linked in the {c['title']} row")
    ok("ตัวต่อตัว" in cs, "courses: no 'ตัวต่อตัว'")
ok(all(("กลุ่ม" not in c["title"]) for c in COURSES), "courses.json has a course whose title mentions a group")

# ---- no stray numbers: every price / hours line anywhere in a page (visible text AND meta tags) must be one that courses.json produces ----
valid_prices = {c["price"] for c in COURSES}
valid_hours = set()
for c in COURSES:
    h = re.search(r"(\d+)\s*ครั้ง\s*\((\d+)\s*ชม", c["hours"])
    L = re.search(r"เรียน\s*(\d+)\s*ชม", c["hours"])
    if h and L:
        valid_hours.add((h.group(1), h.group(2), L.group(1)))
for k, s in SRC.items():
    blob = html.unescape(s)
    for pr in re.findall(r"\d{1,3}(?:,\d{3})+ บาท", blob):
        ok(pr in valid_prices, f"{k}: stray price {pr!r} (courses.json has {sorted(valid_prices)})")
    for t3 in re.findall(r"(\d+) ครั้ง × (\d+) ชม\. = (\d+) ชม\.", blob):
        ok(t3 in valid_hours, f"{k}: stray hours line {t3} (courses.json has {sorted(valid_hours)})")
raw_courses = SRC.get("courses", "")
for c in COURSES:
    block = re.search(rf'<article class="course" id="{slug(c["title"].replace(" Class", ""))}">(.*?)</article>', raw_courses, re.S)
    if block:
        pr = re.search(r'<b class="price">(.*?)</b>', block.group(1))
        ok(bool(pr) and html.unescape(pr.group(1)) == c["price"], f"courses: the price shown in the {c['title']} row is {pr.group(1) if pr else None!r}, courses.json says {c['price']!r}")

# ---- teacher pages ----
profiles = json.loads(read(os.path.join(SITE, "data", "teacher-profiles.json")))
for t in TEACHERS:
    k = "teacher:" + t["name"]
    s = SRC.get(k, "")
    prof = profiles.get(t["name"], {})
    taught = [c["title"] for c in COURSES if t["name"] in c["instructors"]]
    chips = re.findall(r'class="cchip" href="/courses/#([a-z-]+)"', s)
    ok(chips == [slug(x.replace(" Class", "")) for x in taught], f"{k}: course chips {chips} != courses that list {t['name']}")
    ok(f"<h1>{html.escape(t['name'])}</h1>" in s, f"{k}: h1 is not the teacher's name")
    if t.get("social"):
        ok(html.escape(t["social"]) in s, f"{k}: social link missing")
    ok(("เกี่ยวกับ " + t["name"] in s) == bool(prof.get("bio")), f"{k}: bio section shown/hidden wrongly (bio data {'present' if prof.get('bio') else 'empty'})")
    ok(("<h2>ผลงาน</h2>" in s) == bool(prof.get("highlights")), f"{k}: highlights section shown/hidden wrongly")
    ok(("data-vid=" in s) == bool(prof.get("video_id")), f"{k}: video block shown/hidden wrongly")
    ok("ให้ร้านจัดอาจารย์ให้" in s, f"{k}: main CTA missing")

# ---- FAQ: visible == JSON-LD ----
s = SRC.get("courses", "")
vis_faq = [(html.unescape(re.sub(r"<[^>]+>", "", q)), html.unescape(re.sub(r"<[^>]+>", "", a))) for q, a in re.findall(r'<details class="q"[^>]*><summary>(.*?)</summary><p>(.*?)</p></details>', s, re.S)]
ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)]
faq_ld = next((x for x in ld if x.get("@type") == "FAQPage"), None)
ok(faq_ld is not None, "courses: no FAQPage JSON-LD")
if faq_ld:
    ld_pairs = [(e["name"], e["acceptedAnswer"]["text"]) for e in faq_ld["mainEntity"]]
    ok(vis_faq == ld_pairs, f"courses: visible FAQ ({len(vis_faq)}) differs from JSON-LD FAQ ({len(ld_pairs)})")
    ok(len(vis_faq) == len(json.loads(read(os.path.join(SITE, "data", "faq.json")))["items"]), "courses: FAQ count differs from data/faq.json")
ok(sum("ชำระเงิน" in q for q, _ in vis_faq) == 1, "courses: the FAQ must have exactly one payment question")
for q, a in vis_faq:
    ok("{" not in a and "}" not in a, f"courses: unfilled placeholder in FAQ answer: {a[:50]}")
    if "ชำระเงิน" in q:
        ok("ยังไม่มีบริการผ่อนชำระ" in a and "LINE @djlabsiam เท่านั้น" in a, f"courses: the payment answer must say 'no installments yet' and that the account number is given on LINE only: {a[:60]}")
        ok(not any(len(re.sub(r"\D", "", m)) >= 10 for m in re.findall(r"\d[\d\- ]*\d", a)), f"courses: the payment answer must not contain a bank account number (a run of 10+ digits): {a[:60]}")
    if "เลื่อน" in q:
        ok("อย่างน้อย 3 วัน" in a and not re.search(r"(?<!\d)[12](?!\d)\s*(?:[–-]\s*[12]\s*)?วัน", a), f"courses: the reschedule answer must say 'at least 3 days' and never a 1–2 day case: {a[:60]}")

# ---- course pictures: shown exactly for the courses listed in data/course-images.json ----
cimg = json.loads(read(os.path.join(SITE, "data", "course-images.json")))
for c in COURSES:
    block = re.search(rf'<article class="course" id="{slug(c["title"].replace(" Class", ""))}">(.*?)</article>', SRC.get("courses", ""), re.S)
    has = bool(block) and "<figure" in block.group(1)
    ok(has == bool(cimg.get(c["title"])), f"courses: picture of {c['title']} is {'shown' if has else 'hidden'} but data/course-images.json says otherwise")

# ---- images: every /assets/img file a generated page points at exists; the teacher cut-outs are transparent (the dark panel + red glow need the alpha) ----
for k, s in SRC.items():
    for u in sorted(set(re.findall(r"/assets/img/[\w.\-]+\.(?:webp|png|jpe?g|svg)", s))):
        ok(os.path.exists(os.path.join(SITE, u.lstrip("/").replace("/", os.sep))), f"{k}: image {u} does not exist")


def webp_has_alpha(p):
    with open(p, "rb") as fh:
        h = fh.read(32)
    return h[:4] == b"RIFF" and h[8:12] == b"WEBP" and h[12:16] == b"VP8X" and bool(h[20] & 0x10)


for t in TEACHERS:
    for w in (320, 640):
        p = os.path.join(SITE, "assets", "img", f"teacher-{slug(t['name'])}-cut-{w}.webp")
        ok(os.path.exists(p) and webp_has_alpha(p), f"teacher:{t['name']}: assets/img/teacher-{slug(t['name'])}-cut-{w}.webp is missing or has no transparency")
        ok(f"/assets/img/teacher-{slug(t['name'])}-cut-{w}.webp" in SRC.get("teacher:" + t["name"], ""), f"teacher:{t['name']}: page does not use the {w}px cut-out")

# ---- YouTube ↔ privacy policy ----
if any("youtube-nocookie" in s for s in SRC.values()):
    for pol in ("privacy.html", "privacy-en.html"):
        ok("youtube-nocookie" in read(os.path.join(SITE, pol)), f"a page can load a YouTube video but {pol} does not mention youtube-nocookie")

# ---- sitemap == indexable pages ----
sm = read(os.path.join(SITE, "sitemap.xml"))
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
for k, s in SRC.items():
    path = "/" + os.path.relpath(pages[k], SITE).replace(os.sep, "/").replace("index.html", "")
    listed = ("https://djlabsiam.com" + path) in locs
    noindex = bool(re.search(r'name="robots" content="[^"]*noindex', s))
    ok(listed != noindex, f"{k}: sitemap listing ({listed}) must be the opposite of noindex ({noindex})")

# ---- artist names (owner-approved 6 Oct) only inside Maniac's own list of achievements: never elsewhere, never in <head>, headings, alt text ----
ARTISTS = ["Blackpink", "Lisa", "Jennie", "Dajim", "Zentyarb", "K.aglet"]
for k, s in SRC.items():
    head = s.split("</head>")[0]
    heads = " ".join(re.findall(r"<h[1-4][^>]*>.*?</h[1-4]>", s, re.S))
    alts = " ".join(re.findall(r'alt="([^"]*)"', s))
    for n in ARTISTS:
        if k != "teacher:Maniac":
            ok(n not in s, f"{k}: artist name {n!r} appears outside Maniac's page")
        else:
            ok(n not in head, f"{k}: artist name {n!r} in <head> (title/meta/og)")
            ok(n not in heads, f"{k}: artist name {n!r} in a heading")
            ok(n not in alts, f"{k}: artist name {n!r} in image alt text")

# ---- personal data must not sit in the public data files ----
for fp in sorted(glob.glob(os.path.join(SITE, "data", "*.json"))):
    fn = os.path.basename(fp)
    s = read(fp)
    ok(not re.search(r"\b0\d{2}[- ]?\d{3}[- ]?\d{4}\b|\+66\d{8,9}|[\w.]+@[\w.]+\.\w{2,}", s.replace("02-252-5868", "").replace("@djlabsiam", "").replace("@DJLABSIAM", "")), f"data/{fn}: looks like a phone number or e-mail address")

# ---- Meta Pixel: one ID in one file · never on /book/ · every page that carries the script has the off switch · policies cover it when it can run ----
PX = os.path.join(SITE, "assets", "js", "meta-pixel.js")
ok(os.path.exists(PX), "assets/js/meta-pixel.js is missing")
px = read(PX) if os.path.exists(PX) else ""
ids = re.findall(r'var PIXEL_ID = "([^"]*)"', px)
ok(len(ids) == 1 and re.fullmatch(r"(\d{15,16})?", ids[0]) is not None, "meta-pixel.js: PIXEL_ID must be set exactly once, to 15–16 digits or empty")
PIXEL_ID = ids[0] if len(ids) == 1 else ""
site_html = [f for f in glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True) if not any(os.sep + x + os.sep in f for x in ("design-system", "node_modules", ".git", "vendor"))]
site_text = site_html + [f for ext in ("js", "json", "xml") for f in glob.glob(os.path.join(SITE, "**", "*." + ext), recursive=True) if f != PX and not any(os.sep + x + os.sep in f for x in ("design-system", "node_modules", ".git", "vendor"))]
for f in site_text:
    s = read(f)
    rel = os.path.relpath(f, SITE)
    ok("fbq(" not in s and "connect.facebook.net" not in s, f"{rel}: Pixel code outside assets/js/meta-pixel.js")
    ok(not PIXEL_ID or PIXEL_ID not in s, f"{rel}: the Pixel ID must appear only in assets/js/meta-pixel.js")
for f in site_html:
    s = read(f)
    rel = os.path.relpath(f, SITE).replace(os.sep, "/")
    has_script, has_switch = "/assets/js/meta-pixel.js" in s, "data-pixel-toggle" in s and "data-pixel-row" in s
    ok(has_script == has_switch, f"{rel}: carries the Pixel script ({has_script}) but the off switch is {'there' if has_switch else 'missing'} (both or neither)")
    if rel.startswith("book/"):
        ok(not has_script and not has_switch, f"{rel}: the booking page must not carry the Pixel (it holds customers' names and phone numbers)")
for rel in ("index.html", "privacy.html", "privacy-en.html"):
    s = read(os.path.join(SITE, rel))
    ok("/assets/js/meta-pixel.js" in s, f"{rel}: Pixel script missing")
for k, s in SRC.items():
    ok("/assets/js/meta-pixel.js" in s and "data-pixel-toggle" in s, f"{k}: Pixel script or off switch missing")
tracked = re.findall(r'fbq\("track", "(\w+)"(?:, \{([^}]*)\})?', px)
ok({n for n, _ in tracked} == {"PageView", "ViewContent", "Contact"}, f"meta-pixel.js tracks {sorted({n for n, _ in tracked})}, expected exactly PageView, ViewContent, Contact")
sent = {k for _, body in tracked for k in re.findall(r"(\w+):", body)}
ok(sent <= {"content_name", "content_category", "channel"}, f"meta-pixel.js sends parameters {sorted(sent)}: only content_name, content_category, channel are allowed")
ok(px.find('fbq("set", "autoConfig", false, PIXEL_ID)') != -1 and px.find('fbq("set", "autoConfig", false, PIXEL_ID)') < px.find('fbq("init", PIXEL_ID);'), "meta-pixel.js: autoConfig must be switched off before init, and init must pass no user data")
if PIXEL_ID:
    th, en = read(os.path.join(SITE, "privacy.html")), read(os.path.join(SITE, "privacy-en.html"))
    ok("Meta Pixel" in th and "ปิดการวัดผลโฆษณา" in th, "the Pixel can run but privacy.html does not describe Meta Pixel and the off switch")
    ok("Meta Pixel" in en and "Turn off ad measurement" in en, "the Pixel can run but privacy-en.html does not describe Meta Pixel and the off switch")
    ok("ไม่มีสคริปต์วัดผลหรือติดตามการเข้าชม" not in th, "privacy.html still says there is no tracking script while the Pixel can run")
    ok("no shop analytics or tracking scripts run" not in en, "privacy-en.html still says there are no tracking scripts while the Pixel can run")

print(f"check_pages: {passes} passed, {len(fails)} failed · courses.json md5 {md5}")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
