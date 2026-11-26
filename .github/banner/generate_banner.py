#!/usr/bin/env python3
"""Generate the animated `dark.svg` / `light.svg` hero banners of the profile README.

    python3 .github/banner/generate_banner.py --avatar ~/path/to/Artboard.png --out .
    python3 .github/banner/generate_banner.py --avatar ... --out /tmp/preview --static   # no animation

Needs Pillow only. The avatar (your profile picture, light shapes on a transparent
background) is turned into a dot-matrix outline drawn with SVG strokes, so the
banners contain no raster image at all. Every fact shown lives in PROFILE below.
"""
import argparse
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps

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
        "and content creator. Terminal style profile card with a dot-matrix avatar."
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

# Dot-matrix avatar: a DOT_COLS x DOT_ROWS field of dots (DOT_PITCH px apart); the logo
# occupies the central LOGO_CELLS x LOGO_CELLS cells.
DOT_PITCH = 5
DOT_COLS, DOT_ROWS = 78, 78
LOGO_CELLS = 68


def num(x):
    s = f"{x:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------- #
# Dot-matrix avatar                                                            #
# --------------------------------------------------------------------------- #
def logo_dots(path, cells=LOGO_CELLS):
    """Return (edge, fill): sets of (col, row) cells. `edge` follows the outline of the
    logo, `fill` is a sparse checkerboard inside its shapes."""
    im = Image.open(path).convert("RGBA")
    alpha = im.getchannel("A")
    mask = alpha if alpha.getextrema()[0] < 255 else ImageOps.grayscale(im)
    mask = mask.point(lambda p: 255 if p > 127 else 0)
    l, t, r, b = mask.getbbox()
    side = max(r - l, b - t)
    cx, cy = (l + r) / 2, (t + b) / 2
    box = (round(cx - side / 2), round(cy - side / 2), round(cx + side / 2), round(cy + side / 2))
    big = mask.crop(box).resize((cells * 8, cells * 8), Image.LANCZOS).point(lambda p: 255 if p > 127 else 0)
    band = ImageChops.subtract(big.filter(ImageFilter.MaxFilter(3)), big.filter(ImageFilter.MinFilter(3)))
    edge_c = band.resize((cells, cells), Image.BOX).load()
    fill_c = big.resize((cells, cells), Image.BOX).load()
    edge, fill = set(), set()
    for y in range(cells):
        for x in range(cells):
            if edge_c[x, y] > 28:
                edge.add((x, y))
    for y in range(cells):
        for x in range(cells):
            if fill_c[x, y] > 215 and (x + y) % 2 == 0 and (x, y) not in edge:
                fill.add((x, y))
    return edge, fill


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
    pill="#22D3EE", pill_fill_op=0.09, pill_stroke_op=0.40, pill_text="#E2E8F0",
    user="#34D399", cursor="#22D3EE", scan="#22D3EE", scan_op=0.20,
    dot_a="#22D3EE", dot_b="#A78BFA", dot_bg="#67E8F9", dot_bg_op=0.24, dot_fill_op=0.40, dot_glow_op=0.75,
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
    pill="#2563EB", pill_fill_op=0.07, pill_stroke_op=0.34, pill_text="#1E293B",
    user="#047857", cursor="#2563EB", scan="#2563EB", scan_op=0.16,
    dot_a="#2563EB", dot_b="#7C3AED", dot_bg="#475569", dot_bg_op=0.26, dot_fill_op=0.42, dot_glow_op=0.28,
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
def build_svg(theme, dots, static=False):
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

    # ---- dot-matrix avatar geometry ----------------------------------------
    gx0 = LP["x"] + (LP["w"] - DOT_COLS * DOT_PITCH) / 2
    gy0 = 110.0
    gw, gh = DOT_COLS * DOT_PITCH, DOT_ROWS * DOT_PITCH
    d.append(f'<clipPath id="dotfield"><rect x="{num(gx0)}" y="{num(gy0)}" width="{gw}" height="{gh}"/></clipPath>')
    d.append(
        f'<pattern id="dotgrid" x="{num(gx0)}" y="{num(gy0)}" width="{DOT_PITCH}" height="{DOT_PITCH}" patternUnits="userSpaceOnUse">'
        f'<circle cx="{DOT_PITCH / 2}" cy="{DOT_PITCH / 2}" r=".85" fill="{t["dot_bg"]}"/></pattern>'
    )
    dg_anim = (
        ""
        if static
        else anim("y1", [gy0, gy0 + 90, gy0], [0, 0.5, 1], 12, repeat="indefinite", fill=None)
        + anim("y2", [gy0 + gh, gy0 + gh + 90, gy0 + gh], [0, 0.5, 1], 12, repeat="indefinite", fill=None)
    )
    d.append(
        f'<linearGradient id="dotgrad" gradientUnits="userSpaceOnUse" x1="0" y1="{num(gy0)}" x2="0" y2="{num(gy0 + gh)}" spreadMethod="reflect">'
        f'<stop offset="0" stop-color="{t["dot_a"]}"/><stop offset=".55" stop-color="{t["dot_a"]}"/>'
        f'<stop offset="1" stop-color="{t["dot_b"]}"/>{dg_anim}</linearGradient>'
    )
    d.append(
        f'<linearGradient id="scanh" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["dot_a"]}" stop-opacity="0"/>'
        f'<stop offset=".25" stop-color="{t["dot_a"]}"/><stop offset=".75" stop-color="{t["dot_b"]}"/>'
        f'<stop offset="1" stop-color="{t["dot_b"]}" stop-opacity="0"/></linearGradient>'
    )
    d.append('<filter id="dotglow" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="2.4"/></filter>')

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
        f'DOT {DOT_COLS}×{DOT_ROWS}</text>'
        f'<line x1="{lx}" y1="100" x2="{LP["x"] + LP["w"] - 20}" y2="100" stroke="{t["sep"]}" stroke-opacity="{t["sep_op"]}"/>'
    )
    add("</g>")

    # dot-matrix avatar: faint dot grid, dim fill dots, bright outline dots with glow, scan line
    edge, fill = dots
    oc = (DOT_COLS - LOGO_CELLS) // 2
    orow = (DOT_ROWS - LOGO_CELLS) // 2

    def row_paths(cells, width, opacity, delay0):
        out = []
        for r in range(DOT_ROWS):
            xs = sorted(cx for cx, cy in cells if cy + orow == r)
            if not xs:
                continue
            y = gy0 + (r + 0.5) * DOT_PITCH
            dpath = "".join(f"M{num(gx0 + (cx + oc + 0.5) * DOT_PITCH)} {num(y)}h0" for cx in xs)
            out.append(
                f'<path d="{dpath}" fill="none" stroke="url(#dotgrad)" stroke-width="{width}" stroke-linecap="round" '
                f'opacity="{opacity}">{reveal(c, delay0 + r * 0.014, 0.35)}</path>'
            )
        return "".join(out)

    add(f'<g>{reveal(c, 0.45, 0.8)}<rect x="{num(gx0)}" y="{num(gy0)}" width="{gw}" height="{gh}" fill="url(#dotgrid)" opacity="{t["dot_bg_op"]}"/></g>')
    add(f'<g>{row_paths(fill, 2.0, t["dot_fill_op"], 0.7)}</g>')
    add(f'<g id="edgedots">{row_paths(edge, 2.9, 1, 0.7)}</g>')
    add(f'<use href="#edgedots" filter="url(#dotglow)" opacity="{t["dot_glow_op"]}"/>')
    add(
        f'<g>{reveal(c, 1.6, 0.5)}<text x="{num(LP["x"] + LP["w"] / 2)}" y="520" font-size="13" fill="{t["muted"]}" text-anchor="middle" '
        'letter-spacing="1.6">@cmrnrbs</text></g>'
    )
    if not static:
        ys, ye = gy0 - 16, gy0 + gh
        sweep = anim("y", [num(ys), num(ye)], [0, 1], 7, begin="2.8s", repeat="indefinite", fill=None)
        add(
            f'<g clip-path="url(#dotfield)">'
            f'<rect x="{num(gx0)}" y="{num(ys)}" width="{gw}" height="16" fill="url(#beam)">{sweep}</rect>'
            f'<rect x="{num(gx0)}" y="{num(ys + 15)}" width="{gw}" height="1.6" fill="url(#scanh)">{sweep.replace(num(ys), num(ys + 15)).replace(num(ye), num(ye + 15))}</rect></g>'
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
    ap.add_argument("--avatar", required=True, help="profile picture PNG (light shapes on a transparent background)")
    ap.add_argument("--out", default=".", help="output directory for dark.svg and light.svg")
    ap.add_argument("--static", action="store_true", help="omit animations (for previews)")
    args = ap.parse_args()

    avatar = Path(args.avatar).expanduser()
    if not avatar.is_file():
        sys.exit(f"avatar not found: {avatar}")
    dots = logo_dots(avatar)
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    for theme in (DARK, LIGHT):
        svg = build_svg(theme, dots, args.static)
        target = out / f"{theme['name']}.svg"
        target.write_text(svg, encoding="utf-8")
        print(f"{target}  {len(svg.encode()) / 1024:.0f} KB  ({len(dots[0])} outline dots, {len(dots[1])} fill dots)")


if __name__ == "__main__":
    main()
