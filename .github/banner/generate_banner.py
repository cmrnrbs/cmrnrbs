#!/usr/bin/env python3
"""Generate the animated `dark.svg` / `light.svg` hero banners of the profile README.

    python3 .github/banner/generate_banner.py --photo ~/path/to/photo.jpeg --out .
    python3 .github/banner/generate_banner.py --photo ... --out /tmp/preview --static   # no animation

Needs Pillow only. The photo is read, converted to ASCII characters and is NOT
embedded: the SVGs contain text, never the original picture. Every fact shown
in the banner lives in PROFILE below; edit it and run the script again.
"""
import argparse
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

# --------------------------------------------------------------------------- #
# Profile data. Only facts that can be verified from the GitHub account.       #
# --------------------------------------------------------------------------- #
PROFILE = {
    "name": "Cemre Onur Baş",
    "host": "cmrnrbs@github",
    "roles": [
        "Mobile Developer",
        "React Native · Expo",
        "iOS · Swift / SwiftUI",
        "Android · Kotlin",
        "Content Creator",
    ],
    "focus": "Mobile apps · UI animation · tutorials",
    "stack": [
        ["React Native", "Expo", "TypeScript", "Reanimated"],
        ["Swift", "SwiftUI", "Kotlin", "Compose", "Flutter"],
    ],
    "projects": [
        ("expo-hero", "Hero transitions for Expo Router"),
        ("KotlinRoom", "Room CRUD tutorial series"),
        ("Movie Catch", "Kotlin MVVM video series"),
    ],
    "links": "YouTube · dev.to/cmrnrbs · in/cemreonur · X @CmrNrBs",
    "left_prompt": "npx expo start",
    "aria": (
        "Cemre Onur Baş, mobile developer working with React Native, Expo, Swift and Kotlin, "
        "and content creator. Terminal style profile card with an ASCII portrait."
    ),
}

# --------------------------------------------------------------------------- #
# Geometry                                                                     #
# --------------------------------------------------------------------------- #
W, H = 1180, 610
FONT = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace"
CW = 0.6  # monospace advance as a fraction of font size

LP = dict(x=24, y=60, w=424, h=526)  # left panel
RP = dict(x=468, y=60, w=688, h=526)  # right panel

# ASCII portrait grid
RAMP = " .,:;!ilxo0O8#%@"
A_FS, A_CW, A_LH = 6.4, 3.84, 7.2
A_COLS = 92

# Crop (head + shoulders) and subject outline, in the coordinate space of the
# 1500x2000 preview of the source photo.
CROP = (80, 380, 1330, 1750)
OUTLINE = [
    (690, 392), (800, 398), (920, 428), (1000, 488), (1060, 570), (1072, 680),
    (1045, 800), (1030, 940), (1090, 1010), (1090, 1100), (1010, 1200),
    (990, 1340), (945, 1440), (880, 1452), (1000, 1525), (1192, 1630),
    (1300, 1740), (1330, 1800), (1330, 1900), (80, 1900), (80, 1478),
    (300, 1440), (392, 1405), (405, 1300), (412, 1195), (375, 1150),
    (335, 1100), (334, 1000), (352, 925), (392, 895), (396, 800),
    (402, 700), (440, 620), (520, 520), (600, 455),
]
# Face core that is always kept (sunlit skin can look like the orange wall).
KEEP = (500, 650, 960, 1300)


def num(x):
    s = f"{x:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------- #
# ASCII portrait                                                               #
# --------------------------------------------------------------------------- #
def subject_mask(work):
    """Polygon around the subject minus the orange wooden wall and the grey beam."""
    ww, hh = work.size
    cw_, ch_ = CROP[2] - CROP[0], CROP[3] - CROP[1]

    def to_work(p):
        return ((p[0] - CROP[0]) / cw_ * ww, (p[1] - CROP[1]) / ch_ * hh)

    poly = Image.new("L", (ww, hh), 0)
    ImageDraw.Draw(poly).polygon([to_work(p) for p in OUTLINE], fill=255)

    h, s, v = work.convert("HSV").split()
    hue = h.point(lambda p: 255 if 14 <= p <= 32 else 0)
    sat = s.point(lambda p: 255 if p >= 160 else 0)
    val = v.point(lambda p: 255 if p >= 55 else 0)
    wood = ImageChops.multiply(ImageChops.multiply(hue, sat), val)

    top = Image.new("L", (ww, hh), 0)
    ImageDraw.Draw(top).rectangle([0, 0, ww, to_work((0, 1010))[1]], fill=255)
    grey = ImageChops.multiply(
        ImageChops.multiply(s.point(lambda p: 255 if p < 50 else 0), v.point(lambda p: 255 if p > 105 else 0)),
        top,
    )

    core = Image.new("L", (ww, hh), 0)
    x0, y0 = to_work((KEEP[0], KEEP[1]))
    x1, y1 = to_work((KEEP[2], KEEP[3]))
    ImageDraw.Draw(core).rectangle([x0, y0, x1, y1], fill=255)

    mask = ImageChops.subtract(ImageChops.subtract(poly, wood), grey)
    mask = ImageChops.lighter(mask, ImageChops.multiply(poly, core))
    mask = mask.filter(ImageFilter.MedianFilter(9)).filter(ImageFilter.GaussianBlur(2))
    return mask.point(lambda p: 255 if p > 127 else 0)


def build_portrait(photo, debug_dir=None):
    """Return (rows_dark, rows_light): lists of strings, one per text row."""
    src = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
    scale = src.width / 1500
    crop = src.crop(tuple(int(v * scale) for v in CROP))
    cw_, ch_ = CROP[2] - CROP[0], CROP[3] - CROP[1]
    rows = round(A_COLS * (ch_ / cw_) * (A_CW / A_LH))
    ww = A_COLS * 6
    hh = round(ww * ch_ / cw_)
    work = crop.resize((ww, hh), Image.LANCZOS)
    mask = subject_mask(work)

    gray = work.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=1, mask=mask)

    if debug_dir:
        d = Path(debug_dir)
        d.mkdir(parents=True, exist_ok=True)
        cut = Image.new("RGB", work.size, (8, 12, 24))
        cut.paste(work, mask=mask)
        cut.save(d / "mask_preview.png")

    # Work on the character grid. Normalising each cell against its (masked)
    # neighbourhood removes the strong side lighting so that facial features,
    # glasses, beard and hair stay readable.
    small = gray.resize((A_COLS, rows), Image.BOX)
    cov = mask.resize((A_COLS, rows), Image.BOX)
    sg = ImageChops.multiply(small, cov)
    radius = A_COLS / 11
    blur_g = sg.filter(ImageFilter.GaussianBlur(radius)).load()
    blur_c = cov.filter(ImageFilter.GaussianBlur(radius)).load()
    gp, cp = small.load(), cov.load()

    def inside(x, y):
        return 0 <= x < A_COLS and 0 <= y < rows and cp[x, y] >= 110

    def tone(x, y):
        mean = blur_g[x, y] * 255 / max(blur_c[x, y], 1)
        local = 0.5 + (gp[x, y] - mean) / 95.0
        glob = gp[x, y] / 255
        t = 0.62 * local + 0.38 * glob
        return min(1.0, max(0.0, (t - 0.10) / 0.78))

    out = {}
    for name, invert, gamma in (("dark", False, 1.45), ("light", True, 0.85)):
        lines = []
        for y in range(rows):
            line = []
            for x in range(A_COLS):
                if not inside(x, y):
                    line.append(" ")
                    continue
                t = tone(x, y)
                t = (1 - t) if invert else t
                idx = max(1, min(len(RAMP) - 1, round((t ** gamma) * (len(RAMP) - 1))))
                edge = not all(inside(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if edge:
                    idx = max(idx, 4)
                line.append(RAMP[idx])
            lines.append("".join(line))
        out[name] = lines
    return out["dark"], out["light"]


# --------------------------------------------------------------------------- #
# SVG helpers                                                                  #
# --------------------------------------------------------------------------- #
class Ctx:
    def __init__(self, theme, static):
        self.t = theme
        self.static = static
        self.n = 0
        self.defs = []

    def uid(self, p):
        self.n += 1
        return f"{p}{self.n}"


def anim(attr, values, key_times, dur, begin="0s", fill="freeze", repeat=None, calc=None):
    s = (
        f'<animate attributeName="{attr}" values="{";".join(str(v) for v in values)}" '
        f'keyTimes="{";".join(num(k) for k in key_times)}" dur="{num(dur)}s" begin="{begin}"'
    )
    if calc:
        s += f' calcMode="{calc}"'
    if fill:
        s += f' fill="{fill}"'
    if repeat:
        s += f' repeatCount="{repeat}"'
    return s + "/>"


def reveal(c, delay, fade=0.5, dy=0.0):
    """Fade (and optionally slide) an element in. Visible by default, so the card
    still reads fine in renderers without SMIL support."""
    if c.static:
        return ""
    total = delay + fade
    if delay > 0:
        kt, ov, tv = [0, delay / total, 1], [0, 0, 1], [dy, dy, 0]
    else:
        kt, ov, tv = [0, 1], [0, 1], [dy, 0]
    s = anim("opacity", ov, kt, total)
    if dy:
        s += (
            '<animateTransform attributeName="transform" type="translate" '
            f'values="{";".join(f"0 {num(v)}" for v in tv)}" keyTimes="{";".join(num(k) for k in kt)}" '
            f'dur="{num(total)}s" begin="0s" fill="freeze"/>'
        )
    return s


def typed(c, text, x, y, fs, fill, delay, step, weight=400, keep_cursor=False, text_extra=""):
    """Character-by-character typing: a clip rect grows in whole-character steps and a
    block cursor follows. Returns SVG markup (clipPath goes to c.defs)."""
    n, cw = len(text), fs * CW
    width = n * cw
    base = (
        f'<text x="{num(x)}" y="{num(y)}" font-size="{num(fs)}" font-weight="{weight}" fill="{fill}" '
        f'textLength="{num(width)}" lengthAdjust="spacing" {text_extra}'
    )
    if c.static:
        return f"{base}>{esc(text)}</text>"
    cid = c.uid("typ")
    total = delay + n * step
    kt = [0] + [(delay + (k - 1) * step) / total for k in range(1, n + 1)]
    wv = [0] + [num(k * cw) for k in range(1, n + 1)]
    xv = [num(x + k * cw) for k in range(0, n + 1)]
    c.defs.append(
        f'<clipPath id="{cid}"><rect x="{num(x)}" y="{num(y - fs * 1.05)}" width="{num(width)}" '
        f'height="{num(fs * 1.5)}">{anim("width", wv, kt, total, calc="discrete")}</rect></clipPath>'
    )
    cur_color = c.t["cursor"]
    ch, cwid = fs * 1.15, cw * 0.6
    cy = y - fs * 0.95
    if keep_cursor:
        win = anim("opacity", [0, 1], [0, delay / total], total, calc="discrete")
    else:
        win = anim("opacity", [0, 1, 0], [0, delay / total, 0.999], total, calc="discrete")
    # the block cursor follows the typing (x steps in sync with the clip) and blinks
    cursor = (
        f'<g opacity="0">{win}'
        f'<rect x="{num(x)}" y="{num(cy)}" width="{num(cwid)}" height="{num(ch)}" fill="{cur_color}">'
        f'{anim("x", xv, kt, total, calc="discrete")}'
        '<animate attributeName="opacity" values="0.95;0.1" keyTimes="0;0.55" dur="1.1s" '
        'calcMode="discrete" repeatCount="indefinite"/></rect></g>'
    )
    return f'{base} clip-path="url(#{cid})">{esc(text)}</text>{cursor}'


def role_rotator(c, roles, x, y, fs, fill, d0, step=0.07, hold=2.3, fade=0.45):
    """Loop: type each role character by character, hold, fade, next."""
    cw = fs * CW
    if c.static:
        return (
            f'<text x="{num(x)}" y="{num(y)}" font-size="{fs}" font-weight="600" fill="{fill}" '
            f'textLength="{num(len(roles[0]) * cw)}" lengthAdjust="spacing">{esc(roles[0])}</text>'
        )
    N = len(roles)
    P = max(len(r) for r in roles) * step + hold + fade
    T = N * P
    out = []
    for i, role in enumerate(roles):
        n = len(role)
        width = n * cw
        s = i * P / T
        E = (i + 1) * P / T
        fs_ = E - fade / T
        cid = c.uid("role")
        kt = [0] + [s + (k - 1) * step / T for k in range(1, n + 1)]
        wv = [0] + [num(k * cw) for k in range(1, n + 1)]
        xv = [num(x + k * cw) for k in range(0, n + 1)]
        last = i == N - 1
        if not last:
            kt.append(E)
            wv.append(0)
        begin = f"{num(d0)}s"
        pre = f'<set attributeName="width" to="0" begin="0s" dur="{num(d0)}s"/>' if i == 0 else ""
        c.defs.append(
            f'<clipPath id="{cid}"><rect x="{num(x)}" y="{num(y - fs * 1.05)}" width="{num(width)}" '
            f'height="{num(fs * 1.5)}">{pre}{anim("width", wv, kt, T, begin=begin, fill=None, repeat="indefinite", calc="discrete")}'
            "</rect></clipPath>"
        )
        if last:
            okt, ov = [0, fs_, 1], [1, 1, 0]
        else:
            okt, ov = [0, fs_, E, min(E + 0.0004, 1), 1], [1, 1, 0, 1, 1]
        opacity = "1" if i == 0 else "0"
        out.append(
            f'<g opacity="{opacity}">{anim("opacity", ov, okt, T, begin=begin, fill=None, repeat="indefinite")}'
            f'<text x="{num(x)}" y="{num(y)}" font-size="{fs}" font-weight="600" fill="{fill}" '
            f'textLength="{num(width)}" lengthAdjust="spacing" clip-path="url(#{cid})">{esc(role)}</text></g>'
        )
        wkt, wv2 = ([0, s], [0, 1]) if last else ([0, s, E], [0, 1, 0])
        if s == 0:
            wkt, wv2 = ([0, E], [1, 0]) if not last else ([0], [1])
        cur = c.t["cursor"]
        out.append(
            f'<g opacity="0">{anim("opacity", wv2, wkt, T, begin=begin, fill=None, repeat="indefinite", calc="discrete")}'
            f'<rect x="{num(x)}" y="{num(y - fs * 0.95)}" width="{num(cw * 0.6)}" height="{num(fs * 1.15)}" fill="{cur}">'
            f'{anim("x", xv, kt[: n + 1], T, begin=begin, fill=None, repeat="indefinite", calc="discrete")}'
            '<animate attributeName="opacity" values="0.95;0.1" keyTimes="0;0.55" dur="1.1s" '
            'calcMode="discrete" repeatCount="indefinite"/></rect></g>'
        )
    return "".join(out)


# --------------------------------------------------------------------------- #
# Themes                                                                       #
# --------------------------------------------------------------------------- #
DARK = dict(
    name="dark",
    bg=("#030712", "#07111F", "#0B1220"),
    panel="#0F172A", panel_op=0.45, panel_stroke="#7DD3FC", panel_stroke_op=0.16,
    text="#F8FAFC", muted="#94A3B8", label="#22D3EE", proj="#67E8F9",
    name_grad=("#C4B5FD", "#67E8F9", "#6EE7B7"), role="#67E8F9",
    acc=("#7C3AED", "#22D3EE", "#10B981"),
    grid="#94A3B8", grid_op=0.055, noise_op=0.06,
    glow=(("#7C3AED", 0.34), ("#22D3EE", 0.20), ("#10B981", 0.10)),
    ascii_grad=("#A5F3FC", "#22D3EE", "#818CF8", "#C4B5FD"), ascii_op=0.82,
    ascii_hi="#F0F9FF", ascii_hi_op=0.95,
    pill="#22D3EE", pill_fill_op=0.09, pill_stroke_op=0.40, pill_text="#E2E8F0",
    user="#34D399", cursor="#22D3EE", scan="#22D3EE", scan_op=0.20,
    scanline="#000000", scanline_op=0.10, sweep="#FFFFFF", sweep_op=0.07,
    sep="#94A3B8", sep_op=0.14, particle=("#22D3EE", "#A78BFA"), shadow=None,
    frame="#7DD3FC", frame_op=0.14,
)
LIGHT = dict(
    name="light",
    bg=("#FFFFFF", "#F8FAFC", "#EEF6FF"),
    panel="#FFFFFF", panel_op=0.66, panel_stroke="#2563EB", panel_stroke_op=0.16,
    text="#0F172A", muted="#475569", label="#0E7490", proj="#1D4ED8",
    name_grad=("#4338CA", "#1D4ED8", "#0E7490"), role="#1D4ED8",
    acc=("#2563EB", "#06B6D4", "#10B981"),
    grid="#0F172A", grid_op=0.045, noise_op=0.045,
    glow=(("#2563EB", 0.16), ("#06B6D4", 0.16), ("#10B981", 0.09)),
    ascii_grad=("#1E3A8A", "#1D4ED8", "#0E7490", "#4338CA"), ascii_op=0.78,
    ascii_hi="#0B1B4D", ascii_hi_op=0.95,
    pill="#2563EB", pill_fill_op=0.07, pill_stroke_op=0.34, pill_text="#1E293B",
    user="#047857", cursor="#2563EB", scan="#2563EB", scan_op=0.16,
    scanline="#0F172A", scanline_op=0.025, sweep="#FFFFFF", sweep_op=0.55,
    sep="#334155", sep_op=0.16, particle=("#2563EB", "#06B6D4"), shadow="#1E3A8A",
    frame="#2563EB", frame_op=0.18,
)


def perimeter(w, h, r):
    import math
    return 2 * (w + h) - 8 * r + 2 * math.pi * r


# --------------------------------------------------------------------------- #
# Build                                                                        #
# --------------------------------------------------------------------------- #
def build_svg(theme, ascii_rows, static=False):
    c = Ctx(theme, static)
    t = theme
    P = PROFILE
    body = []
    add = body.append

    # ---- static defs ------------------------------------------------------
    d = c.defs
    d.append(
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{t["bg"][0]}"/><stop offset=".55" stop-color="{t["bg"][1]}"/>'
        f'<stop offset="1" stop-color="{t["bg"][2]}"/></linearGradient>'
    )
    glow_pos = [(220, 120, 520), (900, 560, 560), (1080, 80, 300)]
    for i, ((col, op), (gx, gy, gr)) in enumerate(zip(t["glow"], glow_pos)):
        drift = (
            ""
            if static
            else anim("cx", [gx, gx + 60, gx], [0, 0.5, 1], 22 + i * 5, repeat="indefinite", fill=None, calc="spline")
            .replace('calcMode="spline"', 'calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1"')
        )
        d.append(
            f'<radialGradient id="glow{i}" cx="{gx}" cy="{gy}" r="{gr}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{col}" stop-opacity="{op}"/><stop offset="1" stop-color="{col}" stop-opacity="0"/>'
            f"{drift}</radialGradient>"
        )
    d.append(
        f'<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">'
        f'<path d="M40 0H0V40" fill="none" stroke="{t["grid"]}" stroke-width="1"/></pattern>'
    )
    d.append(
        '<filter id="noise" x="0" y="0" width="100%" height="100%">'
        '<feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" stitchTiles="stitch"/>'
        '<feColorMatrix type="saturate" values="0"/></filter>'
    )
    d.append(
        f'<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">'
        f'<rect width="4" height="1" fill="{t["scanline"]}"/></pattern>'
    )
    a0, a1, a2 = t["acc"]
    d.append(
        f'<linearGradient id="shim" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{W}" y2="0">'
        f'<stop offset="0" stop-color="{a0}"/><stop offset=".5" stop-color="{a1}"/><stop offset="1" stop-color="{a2}"/></linearGradient>'
    )
    n0, n1, n2 = t["name_grad"]
    d.append(
        f'<linearGradient id="namegrad" gradientUnits="userSpaceOnUse" x1="668" y1="0" x2="1000" y2="0">'
        f'<stop offset="0" stop-color="{n0}"/><stop offset=".55" stop-color="{n1}"/><stop offset="1" stop-color="{n2}"/></linearGradient>'
    )
    g = t["ascii_grad"]
    gy0, gy1 = 110, 330
    grad_anim = (
        ""
        if static
        else anim("y1", [gy0, gy0 + 70, gy0], [0, 0.5, 1], 14, repeat="indefinite", fill=None)
        + anim("y2", [gy1, gy1 + 70, gy1], [0, 0.5, 1], 14, repeat="indefinite", fill=None)
    )
    d.append(
        f'<linearGradient id="ascii" gradientUnits="userSpaceOnUse" x1="0" y1="{gy0}" x2="0" y2="{gy1}" spreadMethod="reflect">'
        f'<stop offset="0" stop-color="{g[0]}"/><stop offset=".4" stop-color="{g[1]}"/>'
        f'<stop offset=".75" stop-color="{g[2]}"/><stop offset="1" stop-color="{g[3]}"/>{grad_anim}</linearGradient>'
    )
    d.append(
        f'<linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["scan"]}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{t["scan"]}" stop-opacity="{t["scan_op"]}"/><stop offset="1" stop-color="{t["scan"]}" stop-opacity="0"/></linearGradient>'
    )
    d.append(
        f'<linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["sweep"]}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{t["sweep"]}" stop-opacity="{t["sweep_op"]}"/><stop offset="1" stop-color="{t["sweep"]}" stop-opacity="0"/></linearGradient>'
    )
    d.append(f'<clipPath id="frame"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="24"/></clipPath>')
    d.append(
        f'<clipPath id="panels"><rect x="{LP["x"]}" y="{LP["y"]}" width="{LP["w"]}" height="{LP["h"]}" rx="16"/>'
        f'<rect x="{RP["x"]}" y="{RP["y"]}" width="{RP["w"]}" height="{RP["h"]}" rx="16"/></clipPath>'
    )
    d.append('<filter id="soft" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="14"/></filter>')

    # ---- portrait geometry -------------------------------------------------
    rows = len(ascii_rows)
    p_w = A_COLS * A_CW
    p_h = rows * A_LH
    p_x = LP["x"] + (LP["w"] - p_w) / 2
    p_y = 108.0
    d.append(f'<clipPath id="portrait"><rect x="{num(LP["x"] + 8)}" y="{num(p_y)}" width="{num(LP["w"] - 16)}" height="{num(p_h)}"/></clipPath>')

    # ---- background --------------------------------------------------------
    add(f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="24" fill="url(#bg)"/>')
    add('<g clip-path="url(#frame)">')
    for i in range(3):
        add(f'<rect width="{W}" height="{H}" fill="url(#glow{i})"/>')
    add(f'<rect width="{W}" height="{H}" fill="url(#grid)" opacity="{t["grid_op"]}"/>')
    add(f'<rect width="{W}" height="{H}" filter="url(#noise)" opacity="{t["noise_op"]}"/>')
    rnd = random.Random(7)
    for i in range(16):
        px, py = rnd.uniform(40, W - 40), rnd.uniform(40, H - 40)
        dx, dy = rnd.uniform(-60, 60), rnd.uniform(-90, -20)
        r = rnd.uniform(0.8, 1.7)
        col = t["particle"][i % 2]
        op = rnd.uniform(0.18, 0.5)
        mo = (
            ""
            if static
            else f'<animateMotion path="M0 0 L{num(dx)} {num(dy)} L0 0" dur="{num(rnd.uniform(16, 30))}s" repeatCount="indefinite"/>'
        )
        add(f'<circle cx="{num(px)}" cy="{num(py)}" r="{num(r)}" fill="{col}" opacity="{num(op)}">{mo}</circle>')
    add("</g>")
    add(
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="24" fill="none" stroke="{t["frame"]}" '
        f'stroke-opacity="{t["frame_op"]}" stroke-width="1.5"/>'
    )

    # ---- chrome bar --------------------------------------------------------
    add(f'<g>{reveal(c, 0.05, 0.4)}')
    for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        add(f'<circle cx="{40 + i * 22}" cy="27" r="6" fill="{col}"/>')
    add(
        f'<text x="{W // 2}" y="32" font-size="13" fill="{t["muted"]}" text-anchor="middle" letter-spacing=".4">'
        f'{esc(P["host"])}:~/profile</text>'
    )
    pulse = (
        ""
        if static
        else '<animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/>'
        '<animate attributeName="r" values="4;5.2;4" dur="2.4s" repeatCount="indefinite"/>'
    )
    add(f'<circle cx="1028" cy="27" r="4" fill="{t["user"]}">{pulse}</circle>')
    add(f'<text x="1136" y="32" font-size="13" fill="{t["muted"]}" text-anchor="end" letter-spacing="1.6">[ ONLINE ]</text>')
    add(f'<line x1="24" y1="44" x2="{W - 24}" y2="44" stroke="{t["sep"]}" stroke-opacity="{t["sep_op"]}"/>')
    add("</g>")

    # ---- panels ------------------------------------------------------------
    def panel(box, delay, shim_len):
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        per = perimeter(w, h, 16)
        out = [f'<g>{reveal(c, delay, 0.6)}']
        if t["shadow"]:
            out.append(
                f'<rect x="{x}" y="{y + 10}" width="{w}" height="{h}" rx="16" fill="{t["shadow"]}" opacity=".12" filter="url(#soft)"/>'
            )
        out.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{t["panel"]}" fill-opacity="{t["panel_op"]}" '
            f'stroke="{t["panel_stroke"]}" stroke-opacity="{t["panel_stroke_op"]}"/>'
        )
        shimmer = (
            ""
            if static
            else f'<animate attributeName="stroke-dashoffset" from="0" to="{num(-per)}" dur="11s" repeatCount="indefinite"/>'
        )
        out.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="none" stroke="url(#shim)" stroke-width="1.4" '
            f'stroke-linecap="round" stroke-dasharray="{shim_len} {num(per - shim_len)}" opacity=".85">{shimmer}</rect>'
        )
        out.append("</g>")
        return "".join(out)

    add(panel(LP, 0.15, 150))
    add(panel(RP, 0.3, 190))

    # glass reflection sweep
    if not static:
        add(
            '<g clip-path="url(#panels)"><rect x="-300" y="40" width="110" height="560" fill="url(#sweep)" transform="skewX(-18)">'
            '<animate attributeName="x" values="-300;1500" dur="9s" begin="5s;18s" fill="freeze"/></rect></g>'
        )

    # ---- left panel --------------------------------------------------------
    lx = LP["x"] + 20
    add(f'<g>{reveal(c, 0.35, 0.5)}')
    add(
        f'<text x="{lx}" y="88" font-size="12.5" font-weight="600" fill="{t["label"]}" letter-spacing="2.4">VISUAL.MAP</text>'
        f'<text x="{LP["x"] + LP["w"] - 20}" y="88" font-size="12" fill="{t["muted"]}" text-anchor="end" letter-spacing="1">'
        f'ASCII {A_COLS}×{rows}</text>'
        f'<line x1="{lx}" y1="100" x2="{LP["x"] + LP["w"] - 20}" y2="100" stroke="{t["sep"]}" stroke-opacity="{t["sep_op"]}"/>'
    )
    add("</g>")

    # portrait (text only)
    float_anim = (
        ""
        if static
        else '<animateTransform attributeName="transform" type="translate" values="0 0;0 -2;0 0" keyTimes="0;.5;1" '
        'dur="7s" repeatCount="indefinite" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1"/>'
    )
    flicker = (
        ""
        if static
        else '<animate attributeName="opacity" values="1;1;.72;1;.9;1;1" keyTimes="0;.46;.48;.5;.52;.54;1" dur="11s" begin="4s" repeatCount="indefinite"/>'
    )
    glow_pulse = (
        ""
        if static
        else '<animate attributeName="opacity" values=".85;1;.85" dur="4.5s" begin="3s" repeatCount="indefinite"/>'
    )
    add(f'<g><g>{float_anim}')
    base_layer, hi_layer = [], []
    hi_set = set(RAMP[-2:])
    for r, line in enumerate(ascii_rows):
        stripped = line.lstrip(" ")
        if not stripped.strip():
            continue
        lead = len(line) - len(stripped)
        text = stripped.rstrip(" ")
        x = p_x + lead * A_CW
        y = p_y + (r + 1) * A_LH - 1.6
        tl = len(text) * A_CW
        rv = reveal(c, 0.55 + r * 0.022, 0.3)
        base_layer.append(
            f'<text x="{num(x)}" y="{num(y)}" textLength="{num(tl)}" lengthAdjust="spacing" xml:space="preserve">{esc(text)}{rv}</text>'
        )
        hi = "".join(ch if ch in hi_set else " " for ch in text)
        if hi.strip():
            hl = hi.lstrip(" ")
            hx = x + (len(hi) - len(hl)) * A_CW
            ht = hl.rstrip(" ")
            hi_layer.append(
                f'<text x="{num(hx)}" y="{num(y)}" textLength="{num(len(ht) * A_CW)}" lengthAdjust="spacing" xml:space="preserve">{esc(ht)}{rv}</text>'
            )
    add(
        f'<g font-size="{A_FS}" fill="url(#ascii)" fill-opacity="{t["ascii_op"]}" font-weight="500">{"".join(base_layer)}</g>'
        f'<g font-size="{A_FS}" fill="{t["ascii_hi"]}" fill-opacity="{t["ascii_hi_op"]}" font-weight="700">{glow_pulse}{flicker}{"".join(hi_layer)}</g>'
    )
    add("</g></g>")

    # scan beam + scanlines
    if not static:
        add(
            f'<g clip-path="url(#portrait)"><rect x="{LP["x"] + 8}" y="{num(p_y - 30)}" width="{LP["w"] - 16}" height="30" fill="url(#beam)">'
            f'<animate attributeName="y" values="{num(p_y - 30)};{num(p_y + p_h)}" dur="6.5s" begin="3.2s" repeatCount="indefinite"/></rect></g>'
        )
    add(
        f'<rect x="{LP["x"]}" y="{LP["y"]}" width="{LP["w"]}" height="{LP["h"]}" rx="16" fill="url(#scan)" opacity="{t["scanline_op"]}" pointer-events="none"/>'
    )

    # left footer prompt
    fy = 559
    add(f'<line x1="{lx}" y1="534" x2="{LP["x"] + LP["w"] - 20}" y2="534" stroke="{t["sep"]}" stroke-opacity="{t["sep_op"]}"/>')
    pre = "~/cmrnrbs $ "
    add(f'<g>{reveal(c, 2.3, 0.3)}<text x="{lx}" y="{fy}" font-size="14" fill="{t["user"]}" xml:space="preserve">{esc(pre)}</text></g>')
    add(typed(c, P["left_prompt"], lx + len(pre) * 14 * CW, fy, 14, t["text"], 2.7, 0.06, keep_cursor=True))

    # ---- right panel -------------------------------------------------------
    rx = RP["x"] + 24
    right = RP["x"] + RP["w"] - 24
    labx, valx = 640, 668
    add(f'<g>{reveal(c, 0.5, 0.5)}')
    add(
        f'<text x="{rx}" y="88" font-size="12.5" font-weight="600" fill="{t["label"]}" letter-spacing="2.4">SYSTEM.INFO</text>'
        f'<text x="{right}" y="88" font-size="12" fill="{t["muted"]}" text-anchor="end" letter-spacing="1">zsh · utf-8</text>'
        f'<line x1="{rx}" y1="100" x2="{right}" y2="100" stroke="{t["sep"]}" stroke-opacity="{t["sep_op"]}"/>'
    )
    add("</g>")
    pre = P["host"] + ":~$ "
    add(f'<g>{reveal(c, 0.9, 0.3)}<text x="{rx}" y="128" font-size="14" fill="{t["user"]}" xml:space="preserve">{esc(pre)}</text></g>')
    add(typed(c, "./profile.sh", rx + len(pre) * 14 * CW, 128, 14, t["text"], 1.2, 0.05))

    # separators + vertical rule
    seps = [148, 208, 254, 300, 392, 504]
    add(f'<g>{reveal(c, 1.9, 0.6)}')
    for y in seps:
        add(f'<line x1="{rx}" y1="{y}" x2="{right}" y2="{y}" stroke="{t["sep"]}" stroke-opacity="{num(t["sep_op"] * 0.6)}"/>')
    add(
        f'<line x1="654" y1="148" x2="654" y2="562" stroke="{t["sep"]}" stroke-opacity="{num(t["sep_op"])}" stroke-dasharray="2 5"/>'
    )
    add("</g>")

    def label(txt, y, delay):
        return (
            f'<g>{reveal(c, delay, 0.4)}<text x="{labx}" y="{y}" font-size="12.5" fill="{t["label"]}" '
            f'text-anchor="end" letter-spacing="1.6" font-weight="600">{txt}</text></g>'
        )

    # NAME
    add(label("NAME", 188, 1.9))
    add(typed(c, P["name"], valx, 188, 38, "url(#namegrad)", 2.0, 0.06, weight=700))
    # ROLE
    add(label("ROLE", 236, 2.5))
    add(f'<g>{role_rotator(c, P["roles"], valx, 236, 22, t["role"], 3.4)}</g>')
    # FOCUS
    add(label("FOCUS", 282, 2.9))
    add(f'<g>{reveal(c, 3.0, 0.5, 5)}<text x="{valx}" y="282" font-size="16" fill="{t["text"]}">{esc(P["focus"])}</text></g>')
    # STACK
    add(label("STACK", 330, 3.2))
    pill_fs = 13
    pcw = pill_fs * CW
    delay = 3.3
    for ri, row in enumerate(P["stack"]):
        px = valx
        py = 311 + ri * 36
        for name in row:
            pw = len(name) * pcw + 34
            fl = ""
            if not static:
                fl = (
                    f'<animateTransform attributeName="transform" type="translate" values="0 0;0 -1.6;0 0" keyTimes="0;.5;1" '
                    f'dur="{num(5 + (delay * 3) % 3)}s" begin="{num(6 + (delay * 7) % 4)}s" repeatCount="indefinite" '
                    'calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1"/>'
                )
            add(
                f'<g>{reveal(c, delay, 0.35, 4)}<g>{fl}'
                f'<rect x="{num(px)}" y="{py}" width="{num(pw)}" height="28" rx="14" fill="{t["pill"]}" fill-opacity="{t["pill_fill_op"]}" '
                f'stroke="{t["pill"]}" stroke-opacity="{t["pill_stroke_op"]}"/>'
                f'<circle cx="{num(px + 14)}" cy="{py + 14}" r="3" fill="{t["user"]}"/>'
                f'<text x="{num(px + 24)}" y="{py + 18.5}" font-size="{pill_fs}" fill="{t["pill_text"]}" textLength="{num(len(name) * pcw)}" '
                f'lengthAdjust="spacing">{esc(name)}</text></g></g>'
            )
            px += pw + 8
            delay += 0.07
    # PROJECTS
    add(label("PROJECTS", 424, 4.0))
    for i, (pn, pd) in enumerate(P["projects"]):
        y = 424 + i * 28
        add(
            f'<g>{reveal(c, 4.1 + i * 0.18, 0.45, 5)}'
            f'<text x="{valx}" y="{y}" font-size="14" font-weight="700" fill="{t["proj"]}">{esc(pn)}</text>'
            f'<text x="{valx + 132}" y="{y}" font-size="14" fill="{t["muted"]}">{esc(pd)}</text></g>'
        )
    # LINKS
    add(label("LINKS", 541, 4.8))
    add(f'<g>{reveal(c, 4.9, 0.5, 5)}<text x="{valx}" y="541" font-size="13.5" fill="{t["text"]}">{esc(P["links"])}</text></g>')

    # ---- assemble ----------------------------------------------------------
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="{esc(P["aria"])}" font-family="{FONT}">'
        f'<title>{esc(P["name"])} — profile</title><desc>{esc(P["aria"])}</desc>'
    )
    return head + "<defs>" + "".join(c.defs) + "</defs>" + "".join(body) + "</svg>\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photo", required=True, help="portrait photo (JPEG/PNG), used only to build the ASCII art")
    ap.add_argument("--out", default=".", help="output directory for dark.svg and light.svg")
    ap.add_argument("--static", action="store_true", help="omit animations (for previews)")
    ap.add_argument("--debug", help="directory for a cut-out preview of the subject mask")
    args = ap.parse_args()

    photo = Path(args.photo).expanduser()
    if not photo.is_file():
        sys.exit(f"photo not found: {photo}")
    dark_rows, light_rows = build_portrait(photo, args.debug)
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    for theme, rows in ((DARK, dark_rows), (LIGHT, light_rows)):
        svg = build_svg(theme, rows, args.static)
        target = out / f"{theme['name']}.svg"
        target.write_text(svg, encoding="utf-8")
        print(f"{target}  {len(svg.encode()) / 1024:.0f} KB  ({len(rows)} rows x {A_COLS} cols)")


if __name__ == "__main__":
    main()
