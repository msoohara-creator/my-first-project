#!/usr/bin/env python3
"""Pixel-art layers for the 国税専門官募集 recruitment poster.

Every layer is drawn on the poster's art grid (546 x 773 "dots", the B3
ratio 1:1.414 at 1.5 dots/mm) and written to poster/art/.  The HTML page
stacks these layers, scales them up with nearest-neighbour sampling and
sets all text on top as real type.
"""
import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "art")
W, H = 546, 773


def C(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


# --------------------------------------------------------------------------
# Palette: navy, sky blue, white, fresh green; gold is the only accent.
# --------------------------------------------------------------------------
OUTLINE = "#141B33"
SKIN = dict(base="#F8D5B8", hi="#FDE6D3", sh="#EBB797", line="#C98B6E")
SUIT = dict(base="#2E4374", hi="#47639E", sh="#1F2F55", line="#16213F")
SUIT_GRAY = dict(base="#6F7F99", hi="#8E9DB5", sh="#56657E", line="#3E4A60")
SHIRT = dict(base="#FFFFFF", sh="#D3E1EE", line="#9FB3C8")
APRON = dict(base="#5FB548", hi="#86CF6B", sh="#45913A", line="#2F6A2A")
WORK = dict(base="#7FA88A", hi="#9DC2A6", sh="#61886D", line="#46664F")
SHOE = dict(base="#1E2236", hi="#3A4262", sh="#141826")
STOCK = dict(base="#E9C3A6", sh="#D7AC8D")
HAIR = {
    "black": dict(base="#2B2638", hi="#55507A", sh="#1B1726"),
    "brown": dict(base="#6A4430", hi="#956A4C", sh="#4A2E20"),
    "dark": dict(base="#45302A", hi="#745345", sh="#2E1F1A"),
    "chestnut": dict(base="#7E5236", hi="#A97955", sh="#5A3925"),
    "gray": dict(base="#A3A9B6", hi="#D0D5DE", sh="#7E8592"),
}
GOLD = dict(base="#E9B92F", hi="#FBE27E", sh="#B98A1C", line="#7D5A10")
SKY = dict(base="#6CBDE8", hi="#A9DDF7", sh="#4A9BCB", line="#2E6F9A")
SILVER = dict(base="#CBD5E0", hi="#EEF3F8", sh="#9AA9BA", line="#6B7B8E")


# --------------------------------------------------------------------------
# Mask helpers
# --------------------------------------------------------------------------
def shift(m, dx, dy):
    """out[y, x] = m[y - dy, x - dx] (zero filled)."""
    out = np.zeros_like(m)
    h, w = m.shape
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    if xs1 > xs0 and ys1 > ys0:
        out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = m[ys0:ys1, xs0:xs1]
    return out


def dilate4(m):
    return m | shift(m, 1, 0) | shift(m, -1, 0) | shift(m, 0, 1) | shift(m, 0, -1)


class Sprite:
    """An RGBA dot buffer that is painted part by part.

    Each part is a boolean mask painted with a base colour, a shadow band on
    its lower-right edge and a highlight on its upper-left edge (light comes
    from the upper left).  Where a part borders something already painted it
    gets a darker 1-dot line, which gives the clean 16-bit inner contours.
    """

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)

    # -- mask constructors --------------------------------------------------
    def _mask(self, fn):
        im = Image.new("L", (self.w, self.h), 0)
        fn(ImageDraw.Draw(im))
        return np.array(im) > 0

    def blank(self):
        return np.zeros((self.h, self.w), bool)

    def rect(self, x0, y0, x1, y1):
        return self._mask(lambda d: d.rectangle([x0, y0, x1, y1], fill=255))

    def ell(self, cx, cy, rx, ry):
        return self._mask(lambda d: d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255))

    def poly(self, pts):
        return self._mask(lambda d: d.polygon([tuple(p) for p in pts], fill=255))

    def line(self, pts, w):
        def f(d):
            d.line([tuple(p) for p in pts], fill=255, width=max(1, int(w)))
            if w >= 3:
                r = w / 2 - 0.5
                for x, y in pts:
                    d.ellipse([x - r, y - r, x + r, y + r], fill=255)
        return self._mask(f)

    # -- painting -----------------------------------------------------------
    def part(self, m, base, hi=None, sh=None, line=None, shw=1, hiw=1, bottom=True):
        if not m.any():
            return
        occ = self.a[..., 3] > 0
        col = np.empty((self.h, self.w, 4), np.uint8)
        col[:] = C(base)
        shadow = m & ~shift(m, -shw, 0)
        if bottom:
            shadow |= m & ~shift(m, 0, -shw)
        if hi:
            col[m & (~shift(m, hiw, 0) | ~shift(m, 0, hiw)) & ~shadow] = C(hi)
        if sh:
            col[shadow] = C(sh)
        if line:
            col[m & dilate4(occ & ~m)] = C(line)
        self.a[m] = col[m]

    def p(self, m, pal, **kw):
        self.part(m, pal["base"], pal.get("hi"), pal.get("sh"), pal.get("line"), **kw)

    def fill(self, m, c):
        self.a[m] = C(c) if isinstance(c, str) else c

    def dot(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = C(c)

    def outline(self, c=OUTLINE):
        occ = self.a[..., 3] > 0
        self.a[dilate4(occ) & ~occ] = C(c)

    def over(self, other, dx=0, dy=0):
        src = Image.fromarray(other.a, "RGBA")
        dst = Image.fromarray(self.a, "RGBA")
        dst.alpha_composite(src, (dx, dy))
        self.a = np.array(dst)

    def image(self):
        return Image.fromarray(self.a, "RGBA")


# --------------------------------------------------------------------------
# People
# --------------------------------------------------------------------------
def person(sp, cx, by, H=200, gender="m", hair="black", style="short",
           outfit="suit", tie="#5AAFE0", fx=0, mouth="smile", arms=None,
           prop=None, glasses=False, helmet=False, legs=True, towel=False):
    """Draw one front-facing, four-heads-tall person.

    Coordinates below are design units for a 200-dot figure; they are
    scaled by H/200 and anchored with the feet on `by`, centred on `cx`.
    `fx` (-1..1) turns the face toward the viewer's left/right.
    """
    s = H / 200.0
    top = by - H

    def X(x):
        return cx + int(round(x * s))

    def Y(y):
        return top + int(round(y * s))

    def R(v, lo=1):
        return max(lo, int(round(v * s)))

    def P(pts):
        return [(X(x), Y(y)) for x, y in pts]

    hp = HAIR[hair]
    suit = {"suit": SUIT, "suit_gray": SUIT_GRAY, "apron": SHIRT, "work": WORK}[outfit]
    small = H < 110
    fo = fx * 3  # face feature offset

    # ---- back hair (behind everything) ----
    if style == "bob":
        sp.p(sp.ell(X(0), Y(31), R(25), R(25)) & sp.rect(0, 0, sp.w, Y(56)), hp)
    if style == "pony":
        side = 1 if fx <= 0 else -1
        sp.p(sp.ell(X(23 * side), Y(40), R(7), R(17)), hp)

    # ---- legs and shoes ----
    if legs:
        if gender == "m" or outfit == "work":
            pal = SUIT if outfit == "apron" else suit
            for sx in (-1, 1):
                x0, x1 = sorted((X(sx * 2), X(sx * 15)))
                sp.p(sp.rect(x0, Y(112), x1, Y(189)), pal, shw=R(2))
            for sx in (-1, 1):
                x0, x1 = sorted((X(sx * 1), X(sx * 18)))
                sp.p(sp.rect(x0, Y(186), x1, Y(199)) & sp.ell((x0 + x1) // 2, Y(199), (x1 - x0) // 2 + 1, R(13)), SHOE)
        else:
            for sx in (-1, 1):
                x0, x1 = sorted((X(sx * 4), X(sx * 12)))
                sp.p(sp.rect(x0, Y(140), x1, Y(190)), STOCK)
            for sx in (-1, 1):
                x0, x1 = sorted((X(sx * 3), X(sx * 14)))
                sp.p(sp.rect(x0, Y(189), x1, Y(199)) & sp.ell((x0 + x1) // 2, Y(199), (x1 - x0) // 2 + 1, R(11)), SHOE)
            sp.p(sp.poly(P([(-20, 112), (20, 112), (24, 152), (-24, 152)])), suit, shw=R(2))

    # ---- neck and torso ----
    sp.p(sp.rect(X(-6), Y(44), X(6), Y(60)), SKIN)
    if gender == "m" or outfit in ("apron", "work"):
        body = [(-14, 54), (14, 54), (25, 62), (23, 124), (-23, 124), (-25, 62)]
    else:
        body = [(-13, 54), (13, 54), (23, 62), (19, 92), (22, 122), (-22, 122), (-19, 92), (-23, 62)]
    if outfit == "apron":
        sp.p(sp.poly(P(body)), SHIRT, shw=R(2))
        sp.p(sp.poly(P([(-15, 74), (15, 74), (19, 130), (-19, 130)])), APRON, shw=R(2))
        sp.p(sp.rect(X(-15), Y(60), X(-11), Y(76)) | sp.rect(X(11), Y(60), X(15), Y(76)), APRON)
        sp.p(sp.rect(X(-7), Y(92), X(7), Y(102)), APRON)
    else:
        sp.p(sp.poly(P(body)), suit, shw=R(2))
        if outfit == "work":
            sp.p(sp.poly(P([(-9, 53), (9, 53), (0, 70)])), SHIRT)
            sp.p(sp.rect(X(-1), Y(70), X(0), Y(122)), dict(base=WORK["line"]))
            sp.p(sp.rect(X(-17), Y(76), X(-7), Y(84)), dict(base=WORK["sh"]))
        else:
            v = 84 if gender == "m" else 80
            sp.p(sp.poly(P([(-9, 53), (9, 53), (0, v)])), SHIRT)
            if gender == "m":
                sp.p(sp.poly(P([(-3, 56), (3, 56), (4, 78), (0, 84), (-4, 78)])), dict(base=tie, sh="#3C86B8"))
                sp.p(sp.rect(X(-3), Y(55), X(3), Y(59)), dict(base=tie, sh="#3C86B8"))
            for sx in (-1, 1):  # lapels
                sp.p(sp.line(P([(sx * 10, 54), (sx * 1, v + 2)]), R(2)), dict(base=suit["sh"]))
            sp.p(sp.line(P([(0, v + 2), (0, 122)]), 1), dict(base=suit["line"]))
            if not small:
                for by_ in (94, 107):
                    sp.fill(sp.rect(X(1), Y(by_), X(2), Y(by_ + 1)), suit["line"])
                sp.p(sp.rect(X(-18), Y(104), X(-8), Y(106)), dict(base=suit["sh"]))

    # ---- head ----
    sp.p(sp.ell(X(-19 + fo * 0.3), Y(33), R(3.5), R(5.5)) | sp.ell(X(19 + fo * 0.3), Y(33), R(3.5), R(5.5)), SKIN)
    sp.p(sp.ell(X(fo * 0.4), Y(30), R(19), R(21)), SKIN, shw=R(2))
    # eyes
    ew, eh = R(4), R(7, 2)
    for sx in (-1, 1):
        ex = X(sx * 8 + fo) - ew // 2
        ey = Y(29)
        sp.fill(sp.rect(ex, ey, ex + ew - 1, ey + eh - 1), "#4A3B5C")
        sp.fill(sp.rect(ex, ey, ex + ew - 1, ey + max(0, eh // 3 - 1)), "#1E1A30")
        if not small:
            sp.fill(sp.rect(ex, ey + 1, ex + 1, ey + 2), "#FFFFFF")
            if gender == "f":
                ox = ex - 1 if sx < 0 else ex + ew
                sp.dot(ox, ey, "#1E1A30")
            # eyebrows
            sp.fill(sp.rect(X(sx * 8 + fo) - R(3), Y(23), X(sx * 8 + fo) + R(3), Y(23) + 1), hp["sh"])
            # blush
            sp.fill(sp.rect(X(sx * 13 + fo) - 2, Y(41), X(sx * 13 + fo) + 1, Y(41) + 1), "#F4A39C")
    # nose
    if not small:
        sp.dot(X(fo + 1), Y(38), SKIN["line"])
    # mouth
    mx, my = X(fo), Y(44)
    if small:
        if mouth == "grin":
            sp.fill(sp.rect(mx - 1, my, mx + 1, my + 1), "#A8443F")
        else:
            sp.fill(sp.rect(mx - 1, my, mx + 1, my), "#A8443F")
    elif mouth == "grin":
        sp.fill(sp.poly([(mx - 6, my - 1), (mx + 6, my - 1), (mx + 4, my + 4), (mx - 4, my + 4)]), "#A8443F")
        sp.fill(sp.rect(mx - 5, my - 1, mx + 5, my), "#FFFFFF")
        sp.fill(sp.rect(mx - 2, my + 3, mx + 2, my + 3), "#E07A70")
    elif mouth == "open":
        sp.fill(sp.poly([(mx - 4, my - 1), (mx + 4, my - 1), (mx + 2, my + 3), (mx - 2, my + 3)]), "#A8443F")
        sp.fill(sp.rect(mx - 1, my + 2, mx + 1, my + 2), "#E07A70")
    else:
        for i, dy in zip(range(-4, 5), (0, 1, 1, 2, 2, 2, 1, 1, 0)):
            sp.dot(mx + i, my + dy - 1, "#A8443F")

    if glasses and not small:
        for sx in (-1, 1):
            gx = X(sx * 8 + fo)
            m = sp.rect(gx - 6, Y(27), gx + 6, Y(37)) & ~sp.rect(gx - 5, Y(28), gx + 5, Y(36))
            sp.fill(m, "#2A3558")
        sp.fill(sp.rect(X(fo) - 2, Y(29), X(fo) + 2, Y(29)), "#2A3558")

    # ---- front hair / helmet ----
    if helmet:
        dome = sp.ell(X(0), Y(22), R(24), R(19)) & sp.rect(0, 0, sp.w, Y(23))
        sp.p(dome, dict(base="#FFFFFF", hi="#FFFFFF", sh="#D6E0EA"), shw=R(2))
        sp.p(sp.rect(X(-26), Y(21), X(26), Y(25)), dict(base="#F2F6FA", sh="#C9D5E2"))
        sp.p(sp.rect(X(-3), Y(7), X(3), Y(19)) | sp.rect(X(-7), Y(11), X(7), Y(15)), dict(base="#5FB548"))
        sp.p(sp.rect(X(-17), Y(25), X(-14), Y(32)) | sp.rect(X(14), Y(25), X(17), Y(32)), hp)
    else:
        cap = sp.ell(X(0), Y(24), R(22), R(21))
        if style == "short":
            m = cap & sp.rect(0, 0, sp.w, Y(18))
            m |= sp.poly(P([(-22, 16), (-20, 25), (-15, 19), (-11, 24), (-6, 18), (-1, 23), (4, 17),
                            (9, 23), (13, 18), (18, 24), (22, 16), (0, 10)]))
            m |= sp.rect(X(-21), Y(16), X(-18), Y(33)) | sp.rect(X(18), Y(16), X(21), Y(33))
        elif style == "part":
            m = cap & sp.rect(0, 0, sp.w, Y(17))
            m |= sp.poly(P([(-22, 14), (-21, 27), (-15, 22), (-9, 21), (-2, 18), (6, 16), (13, 15), (22, 18), (20, 10)]))
            m |= sp.rect(X(-21), Y(16), X(-18), Y(32)) | sp.rect(X(18), Y(16), X(21), Y(32))
        elif style == "gray":
            m = cap & sp.rect(0, 0, sp.w, Y(15))
            m |= sp.poly(P([(-22, 13), (-21, 22), (-14, 16), (0, 14), (14, 16), (21, 22), (22, 13)]))
            m |= sp.rect(X(-21), Y(15), X(-18), Y(30)) | sp.rect(X(18), Y(15), X(21), Y(30))
        elif style == "bob":
            m = cap & sp.rect(0, 0, sp.w, Y(18))
            m |= sp.poly(P([(-22, 15), (-19, 24), (-14, 20), (-9, 24), (-4, 20), (2, 23), (8, 19), (13, 23),
                            (18, 20), (22, 15)]))
            m |= sp.poly(P([(-22, 18), (-17, 22), (-17, 50), (-25, 54), (-24, 30)]))
            m |= sp.poly(P([(22, 18), (17, 22), (17, 50), (25, 54), (24, 30)]))
        else:  # pony: side-swept bangs, hair pulled back
            m = cap & sp.rect(0, 0, sp.w, Y(17))
            m |= sp.poly(P([(-22, 15), (-20, 30), (-16, 22), (-8, 21), (2, 19), (10, 17), (17, 15), (22, 22), (21, 12)]))
            m |= sp.rect(X(18), Y(16), X(21), Y(30))
        sp.p(m, hp, shw=R(2))
        if not small:  # glossy hair shine, upper left
            sp.fill(sp.line(P([(-13, 9), (-6, 6), (2, 6)]), R(2)) & m, hp["hi"])
        if towel:
            sp.p(sp.rect(X(-22), Y(12), X(22), Y(17)) & sp.ell(X(0), Y(24), R(23), R(22)),
                 dict(base="#FFFFFF", sh="#C9D5E2"))

    # ---- arms, props, hands ----
    arms = arms or {}
    sleeve = SHIRT if outfit == "apron" else suit
    hands = []
    for side in (-1, 1):
        pts = arms.get(side, [(side * 21, 62), (side * 25, 90), (side * 25, 114)])
        sp.p(sp.line(P(pts), R(10, 2)), sleeve, shw=R(2) if not small else 1)
        hx, hy = pts[-1]
        if not small and outfit in ("suit", "suit_gray"):
            px_, py_ = pts[-2]
            d = max(1e-6, ((hx - px_) ** 2 + (hy - py_) ** 2) ** 0.5)
            ux, uy = (hx - px_) / d, (hy - py_) / d
            sp.p(sp.line(P([(hx - ux * 2, hy - uy * 2), (hx, hy)]), R(9, 2)), SHIRT)
        hands.append((hx, hy))
    if prop:
        prop(sp, X, Y, R, P, small)
    point = arms.get("point")
    for i, (hx, hy) in enumerate(hands):
        sp.p(sp.ell(X(hx), Y(hy + 4), R(5.5), R(5.5)), SKIN)
    if point:
        sp.p(sp.line(P(point), R(3.4, 1)), SKIN)
    return sp


# -- props ------------------------------------------------------------------
def prop_tablet(sp, X, Y, R, P, small):
    sp.p(sp.rect(X(-16), Y(68), X(5), Y(100)), dict(base="#E9EFF6", sh="#B9C7D6", line=OUTLINE))
    scr = sp.rect(X(-14), Y(71), X(3), Y(96))
    sp.fill(scr, "#9ED8F4")
    sp.fill(scr & sp.rect(0, Y(84), sp.w, sp.h), "#7CC7EE")
    sp.p(sp.line(P([(-12, 92), (-8, 86), (-4, 89), (1, 78)]), R(2)), dict(base="#4FAE3E"))
    for i, hgt in enumerate((5, 8, 11)):
        sp.fill(sp.rect(X(-12 + i * 5), Y(95 - hgt), X(-10 + i * 5), Y(95)) & ~sp.blank(), "#FFFFFF")
    sp.p(sp.line(P([(-12, 92), (-8, 86), (-4, 89), (1, 78)]), R(2)), dict(base="#2F8F3A"))
    sp.fill(sp.rect(X(1), Y(76), X(3), Y(78)), GOLD["base"])


def prop_laptop(sp, X, Y, R, P, small):
    sp.p(sp.rect(X(-20), Y(74), X(20), Y(101)), dict(base=SILVER["base"], hi=SILVER["hi"], sh=SILVER["sh"], line=OUTLINE))
    scr = sp.rect(X(-17), Y(77), X(17), Y(98))
    sp.fill(scr, "#9ED8F4")
    sp.fill(scr & sp.rect(0, Y(90), sp.w, sp.h), "#84CCEF")
    for i, hgt in enumerate((6, 10, 8, 14, 17)):
        c = GOLD["base"] if i == 4 else ("#FFFFFF" if i % 2 else "#5FB548")
        sp.fill(sp.rect(X(-13 + i * 6), Y(95 - hgt), X(-10 + i * 6), Y(95)), c)
    sp.p(sp.poly(P([(-22, 100), (22, 100), (25, 107), (-25, 107)])), dict(base=SILVER["base"], hi=SILVER["hi"], sh=SILVER["sh"], line=OUTLINE))


def prop_file(sp, X, Y, R, P, small):
    sp.p(sp.rect(X(-2), Y(66), X(21), Y(100)), dict(base="#FFFFFF", sh="#D3E1EE", line=OUTLINE))
    sp.p(sp.rect(X(1), Y(64), X(23), Y(99)), dict(base=SKY["base"], hi=SKY["hi"], sh=SKY["sh"], line=SKY["line"]), shw=R(2))
    sp.fill(sp.rect(X(6), Y(70), X(18), Y(74)), "#FFFFFF")
    sp.fill(sp.rect(X(1), Y(66), X(3), Y(97)), "#3C86B8")
    sp.fill(sp.rect(X(8), Y(85), X(16), Y(86)), GOLD["base"])


def prop_notepad(sp, X, Y, R, P, small):
    sp.p(sp.rect(X(17), Y(98), X(33), Y(120)), dict(base="#FFFFFF", sh="#D3E1EE", line=OUTLINE))
    for yy in (106, 110, 114):
        sp.fill(sp.rect(X(20), Y(yy), X(30), Y(yy)), "#A9C9E6")
    for xx in (19, 23, 27, 31):
        sp.fill(sp.rect(X(xx), Y(96), X(xx + 1), Y(99)), GOLD["base"])


def prop_small_notepad(side=1, with_pen=True):
    def f(sp, X, Y, R, P, small):
        x0 = 4 if side > 0 else -24
        sp.p(sp.rect(X(x0), Y(70), X(x0 + 20), Y(96)), dict(base="#FFFFFF", sh="#C9D7E5", line=OUTLINE))
        sp.fill(sp.rect(X(x0 + 3), Y(78), X(x0 + 16), Y(79)) | sp.rect(X(x0 + 3), Y(86), X(x0 + 14), Y(87)), "#A9C9E6")
        sp.fill(sp.rect(X(x0), Y(68), X(x0 + 20), Y(71)), GOLD["base"])
    return f


def prop_doc_check(sp, X, Y, R, P, small):
    sp.p(sp.rect(X(2), Y(60), X(30), Y(98)), dict(base="#FFFFFF", sh="#C9D7E5", line=OUTLINE))
    sp.fill(sp.line(P([(7, 80), (13, 88), (25, 66)]), R(5)), "#3DA845")
    sp.fill(sp.line(P([(7, 80), (13, 88), (25, 66)]), R(2.4)), "#7FD66A")


def prop_tablet_small(sp, X, Y, R, P, small):
    sp.p(sp.rect(X(4), Y(70), X(24), Y(98)), dict(base="#E9EFF6", sh="#B9C7D6", line=OUTLINE))
    sp.fill(sp.rect(X(7), Y(73), X(21), Y(95)), "#8FD2F2")
    sp.fill(sp.line(P([(8, 90), (13, 84), (16, 86), (20, 77)]), 1), "#2F8F3A")


def prop_folder_small(sp, X, Y, R, P, small):
    sp.p(sp.rect(X(-24), Y(76), X(-2), Y(100)), dict(base="#FFFFFF", sh="#C9D7E5", line=OUTLINE))
    sp.fill(sp.rect(X(-20), Y(82), X(-6), Y(83)) | sp.rect(X(-20), Y(89), X(-8), Y(90)), "#A9C9E6")


def person_sprite(w, h, **kw):
    sp = Sprite(w, h)
    person(sp, **kw)
    sp.outline()
    return sp


# --------------------------------------------------------------------------
# Layer 3: the four main characters
# --------------------------------------------------------------------------
CHAR_BASE = 486
CHAR_X = [184, 244, 304, 364]


def build_characters():
    layer = Sprite(W, H)
    pad = 40
    specs = [
        # left woman: tablet
        dict(cx=CHAR_X[0], gender="f", hair="brown", style="bob", fx=0.4, mouth="open",
             arms={-1: [(-21, 62), (-27, 90), (-14, 99)]}, prop=prop_tablet),
        # right woman: document file
        dict(cx=CHAR_X[3], gender="f", hair="dark", style="pony", fx=-0.4, mouth="open",
             arms={1: [(21, 62), (27, 90), (16, 96)]}, prop=prop_file),
        # inner right man: laptop, glasses
        dict(cx=CHAR_X[2], gender="m", hair="chestnut", style="part", fx=-0.2, mouth="smile",
             glasses=True, tie="#5FB548",
             arms={-1: [(-21, 62), (-27, 90), (-21, 103)], 1: [(21, 62), (27, 90), (21, 103)]},
             prop=prop_laptop),
        # centre man: points forward and up, notepad in the other hand
        dict(cx=CHAR_X[1], gender="m", hair="black", style="short", fx=0.0, mouth="grin",
             tie=GOLD["base"],
             arms={-1: [(-21, 62), (-31, 38), (-36, 10)], 1: [(21, 62), (27, 92), (23, 106)],
                   "point": [(-37, 4), (-40, -9)]},
             prop=prop_notepad),
    ]
    for sp_kw in specs:
        cx = sp_kw.pop("cx")
        lift = 2 if cx == CHAR_X[1] else 0
        sp = person_sprite(140, 260, cx=70, by=250, H=200, **sp_kw)
        layer.over(sp, cx - 70, CHAR_BASE + lift - 250)
    layer.image().save(os.path.join(OUT, "characters.png"))


# --------------------------------------------------------------------------
# Layer 1: sky, clouds, distant town, meadow
# --------------------------------------------------------------------------
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16.0


def dither_gradient(img, y0, y1, colours, x0=0, x1=W):
    cols = [np.array(C(c)) for c in colours]
    n = len(cols) - 1
    for y in range(y0, y1):
        t = (y - y0) / max(1, (y1 - y0 - 1)) * n
        for x in range(x0, x1):
            v = t + BAYER[y % 4, x % 4] - 0.5
            i = int(min(n, max(0, round(v))))
            img[y, x] = cols[i]


def cloud(sp, x, y, w, pal=None):
    pal = pal or dict(base="#FFFFFF", sh="#DCEBF6")
    h = int(w * 0.42)
    m = sp.ell(x + w // 2, y + h * 0.75, w // 2, h // 3)
    bumps = [(0.22, 0.55, 0.20), (0.42, 0.35, 0.26), (0.64, 0.45, 0.22), (0.80, 0.62, 0.16), (0.12, 0.70, 0.13)]
    for bx, byy, br in bumps:
        m |= sp.ell(x + int(w * bx), y + int(h * byy), int(w * br), int(w * br * 0.85))
    m &= sp.rect(0, 0, W, y + int(h * 0.92))
    sp.part(m, pal["base"], None, pal["sh"], None, shw=3)
    low = m & ~shift(m, 0, -5)
    sp.a[low & ~(m & ~shift(m, 0, -2))] = C("#C6DCEE")


def build_background():
    sp = Sprite(W, H)
    dither_gradient(sp.a, 0, 446, ["#3E9BDD", "#4FA8E4", "#62B4EA", "#78C0EE", "#8FCBF2",
                                   "#A6D6F5", "#BCE0F7", "#D0E9F9", "#E2F2FB"])
    # sun, upper left
    for r, c in ((30, "#BFE3F8"), (24, "#DDF0FB"), (18, "#FFF9E4"), (13, "#FFFFFF")):
        sp.fill(sp.ell(14, 14, r, r), c)
    for x, y, w in ((4, 118, 120), (430, 120, 112), (150, 196, 92), (330, 168, 84),
                    (-30, 330, 110), (468, 318, 96), (232, 250, 70)):
        cloud(sp, x, y, w)

    # ---- distant town (muted, low contrast) ----
    town = Sprite(W, H)
    far = dict(base="#B6CADC", sh="#A4BAD0", hi="#C6D7E6")
    mid = dict(base="#A9C0D6", sh="#97B0C8", hi="#BED1E2")
    win = "#CCDCEA"
    towers = [(120, 300, 26), (150, 262, 30), (184, 286, 22), (210, 244, 28), (240, 296, 24),
              (24, 330, 30), (60, 300, 24), (500, 336, 30)]
    for i, (x, ty, w) in enumerate(towers):
        pal = far if i % 2 else mid
        town.part(town.rect(x, ty, x + w, 446), pal["base"], pal["hi"], pal["sh"], None, shw=3, bottom=False)
        for yy in range(ty + 6, 440, 7):
            for xx in range(x + 4, x + w - 4, 6):
                town.fill(town.rect(xx, yy, xx + 2, yy + 3), win)
        town.fill(town.rect(x + w // 2 - 1, ty - 8, x + w // 2, ty - 1), pal["sh"])
    # shopping street: low buildings with awnings
    for i, x in enumerate(range(262, 352, 22)):
        hgt = 398 + (i % 3) * 8
        pal = far if i % 2 else mid
        town.part(town.rect(x, hgt, x + 20, 446), pal["base"], pal["hi"], pal["sh"], None, bottom=False)
        aw = "#BCD6BE" if i % 2 else "#D7E3EC"
        town.fill(town.rect(x, hgt + 12, x + 20, hgt + 16), aw)
        for xx in range(x, x + 20, 4):
            town.fill(town.rect(xx, hgt + 12, xx + 1, hgt + 16), "#C9DDD0" if i % 2 else "#C6D6E3")
        town.fill(town.rect(x + 4, hgt + 22, x + 15, hgt + 34), win)
    # factory: saw-tooth roof and chimneys
    for i in range(5):
        x = 352 + i * 22
        town.part(town.poly([(x, 420), (x + 22, 404), (x + 22, 446), (x, 446)]), far["base"], far["hi"], far["sh"], None, bottom=False)
        town.fill(town.rect(x + 18, 406, x + 21, 420), win)
    for x, ty in ((376, 330), (400, 350)):
        town.part(town.rect(x, ty, x + 8, 420), mid["base"], mid["hi"], mid["sh"], None, bottom=False)
        town.fill(town.rect(x, ty + 6, x + 8, ty + 8), "#D9E3EC")
    town.part(town.ell(386, 318, 10, 6) | town.ell(398, 308, 8, 5), "#E6EFF6", None, "#D6E2EC", None)
    sp.over(town)

    # haze at horizon
    for y in range(392, 446):
        a = (y - 392) / 54.0
        for x in range(W):
            if BAYER[y % 4, x % 4] < a * 0.55:
                sp.a[y, x] = C("#DCEEF8")

    # ---- tree line and meadow ----
    trees = Sprite(W, H)
    m = trees.rect(0, 440, W, 460)
    for x in range(-6, W + 12, 13):
        r = 9 + (x * 7 % 5)
        m |= trees.ell(x, 440 - (x * 3 % 4), r, r - 2)
    trees.part(m, "#9FCB98", "#B6D9AE", "#8CBC88", None, shw=3)
    sp.over(trees)
    dither_gradient(sp.a, 452, H, ["#B3DE93", "#A7D987", "#9BD27A", "#8FCB6E", "#86C566"])
    # a few soft grass tufts on the meadow edges
    rng = np.random.default_rng(7)
    for _ in range(140):
        x, y = int(rng.integers(0, W)), int(rng.integers(458, H))
        sp.fill(sp.rect(x, y, x, y + 1), "#7DBE5E")
        sp.dot(x + 1, y - 1, "#C7E8AE")
    # pale plaza under the characters
    sp.fill(sp.ell(273, 488, 150, 22), "#CBE7B6")
    sp.fill(sp.ell(273, 488, 132, 17), "#D7EEC6")
    sp.image().save(os.path.join(OUT, "background.png"))


# --------------------------------------------------------------------------
# Title emblem plate (gold, pixel-stepped edges)
# --------------------------------------------------------------------------
def build_title_plate():
    sp = Sprite(W, H)
    x0, x1, y0, y1, step = 50, 496, 16, 112, 4
    mid = (y0 + y1) // 2

    def plate(inset):
        top, bot = y0 + inset, y1 - inset
        left, right = x0 + inset, x1 - inset
        m = sp.rect(left, top, right, bot)
        # pointed ends built from 4-dot stairs
        n = 6
        dv = (mid - top) / (n + 1)
        for k in range(n):
            ya, yb = int(top + (k + 1) * dv), int(bot - (k + 1) * dv)
            m |= sp.rect(left - (k + 1) * step, ya, left - k * step - 1, yb)
            m |= sp.rect(right + k * step + 1, ya, right + (k + 1) * step, yb)
        # stepped corners
        for (cx, cy, dx, dy) in ((left, top, 1, 1), (right, top, -1, 1), (left, bot, 1, -1), (right, bot, -1, -1)):
            for k in range(3):
                w_ = (3 - k) * step
                ys = cy + dy * k * step
                xa, xb = sorted((cx, cx + dx * (w_ - 1)))
                ya, yb = sorted((ys, ys + dy * (step - 1)))
                m &= ~sp.rect(xa, ya, xb, yb)
        return m

    outer = plate(0)
    sp.fill(dilate4(dilate4(outer)) & ~outer, "#1B2A4F")
    sp.fill(outer, GOLD["sh"])
    inner = plate(3)
    # banded vertical gradient with dither
    bands = ["#FFF0A8", "#FBE27E", "#F5D05A", "#EEC342", "#E9B92F", "#DDA826", "#CF9A20"]
    tmp = np.zeros_like(sp.a)
    dither_gradient(tmp, y0, y1 + 1, bands, x0 - 30, x1 + 30)
    sp.a[inner] = tmp[inner]
    sp.fill(inner & ~shift(inner, 0, 2), "#FFF6CC")
    sp.fill(inner & ~shift(inner, 0, -2), "#B98A1C")
    ring = plate(7)
    sp.fill(ring & ~shift(ring, 0, 1) | ring & ~shift(ring, 0, -1) | ring & ~shift(ring, 1, 0) | ring & ~shift(ring, -1, 0), "#C9961F")
    # pixel stars at the tips
    for cx in (x0 + 8, x1 - 8):
        for dx, dy in ((0, -3), (0, -2), (0, -1), (0, 0), (0, 1), (0, 2), (0, 3), (-3, 0), (-2, 0), (-1, 0), (1, 0), (2, 0), (3, 0)):
            sp.dot(cx + dx, mid + dy, "#FFFFFF")
        sp.dot(cx, mid, "#FFF6CC")
    # little sparkles on the gold
    for x, y in ((92, 26), (448, 98), (470, 30)):
        for dx, dy in ((0, -2), (0, -1), (0, 0), (0, 1), (0, 2), (-2, 0), (-1, 0), (1, 0), (2, 0)):
            sp.dot(x + dx, y + dy, "#FFFFFF")
    sp.image().save(os.path.join(OUT, "title_plate.png"))


# --------------------------------------------------------------------------
# Drifting cherry petals (kept clear of every text zone)
# --------------------------------------------------------------------------
PETALS = [(16, 150), (530, 104), (522, 160), (160, 168), (392, 166), (204, 232), (336, 214),
          (276, 196), (150, 290), (398, 270), (10, 326), (534, 332), (452, 488), (96, 488),
          (8, 470), (538, 452), (268, 160)]


def build_petals():
    sp = Sprite(W, H)
    shapes = [
        [(0, 0, "#F8C9D8"), (1, 0, "#F8C9D8"), (1, 1, "#F3AFC6"), (2, 1, "#F8C9D8"), (0, 1, "#FDE4EC")],
        [(1, 0, "#FDE4EC"), (0, 1, "#F8C9D8"), (1, 1, "#F8C9D8"), (2, 1, "#F3AFC6"), (1, 2, "#F3AFC6")],
        [(0, 0, "#F8C9D8"), (1, 1, "#F8C9D8"), (2, 1, "#F3AFC6"), (1, 0, "#FDE4EC")],
    ]
    for i, (x, y) in enumerate(PETALS):
        for dx, dy, c in shapes[i % 3]:
            sp.dot(x + dx, y + dy, c)
    sp.image().save(os.path.join(OUT, "petals.png"))


# --------------------------------------------------------------------------
# Layer 2: scene panels (118 x 136 dots each)
# --------------------------------------------------------------------------
PW, PH = 118, 136


def panel_listen():
    sp = Sprite(PW, PH)
    dither_gradient(sp.a, 0, 26, ["#8ACAF0", "#B3DDF6", "#D3ECFA"], 0, PW)
    # shop facade and awning
    sp.part(sp.rect(0, 14, PW, 30), "#F3F6F8", None, "#D8E2EA", None)
    aw = sp.poly([(0, 24), (PW, 24), (PW, 38), (0, 38)])
    for x in range(-2, PW + 8, 8):
        aw |= sp.ell(x + 4, 38, 4, 3)
    sp.fill(aw, "#FFFFFF")
    for x in range(0, PW, 16):
        sp.fill(aw & sp.rect(x, 0, x + 7, PH), "#5FB548")
    sp.fill(aw & ~shift(aw, 0, -2), "#3E8E34")
    # interior wall and shelves
    sp.fill(sp.rect(0, 42, PW, 98), "#EEF3EC")
    for sy in (58, 78):
        sp.part(sp.rect(52, sy, PW, sy + 3), "#C7A776", "#DCC096", "#A88A5E", None)
        for i, x in enumerate(range(56, PW - 4, 9)):
            c = ["#6CBDE8", "#E9B92F", "#86CF6B", "#FFFFFF", "#F08C7A"][i % 5]
            hh = 8 + (i % 3) * 2
            sp.part(sp.rect(x, sy - hh, x + 6, sy - 1), c, None, "#9AA9BA", None)
    # floor
    sp.fill(sp.rect(0, 98, PW, PH), "#E3E8EC")
    sp.fill(sp.rect(0, 98, PW, 99), "#CBD5DE")
    # owner behind the counter (towel band, apron, gray hair)
    owner = person_sprite(PW, PH, cx=86, by=134, H=74, gender="m", hair="gray", style="gray",
                          outfit="apron", fx=-1, mouth="grin", towel=True,
                          arms={-1: [(-21, 62), (-28, 84), (-24, 74)]})
    sp.over(owner)
    # counter
    sp.part(sp.rect(54, 100, PW, PH), "#D9BB8A", "#E8D1A8", "#B89763", "#8C6E44", shw=2)
    sp.part(sp.rect(52, 96, PW, 101), "#F1E2C6", "#FFF3DE", "#CDB48A", "#8C6E44")
    # basket of greens on the counter
    sp.part(sp.ell(100, 92, 8, 5), "#86CF6B", "#B7E6A0", "#5FB548", None)
    sp.part(sp.rect(91, 92, 109, 98), "#C7A776", None, "#A88A5E", None)
    # staff member listening with notepad
    staff = person_sprite(PW, PH, cx=30, by=132, H=74, gender="f", hair="brown", style="bob",
                          fx=1, mouth="smile",
                          arms={1: [(21, 62), (26, 84), (14, 82)], -1: [(-21, 62), (-24, 88), (-6, 90)]},
                          prop=prop_small_notepad(1))
    sp.over(staff)
    return sp


def panel_investigate():
    sp = Sprite(PW, PH)
    sp.fill(sp.rect(0, 0, PW, PH), "#DCE6EE")
    # high windows with daylight
    for x in range(6, PW, 28):
        sp.part(sp.rect(x, 8, x + 20, 26), "#BFE3F8", "#E2F3FC", "#9CCFEE", "#7E93A8")
        sp.fill(sp.rect(x + 10, 8, x + 10, 26), "#7E93A8")
    sp.fill(sp.rect(0, 30, PW, 32), "#9AABBE")
    # machine with pipes and round gauges
    sp.part(sp.rect(6, 40, 60, 100), "#8FB3C9", "#B3CEDF", "#6E93AC", "#4E6E86", shw=2)
    sp.part(sp.rect(12, 48, 34, 66), "#E6EEF4", None, "#C2D0DC", "#4E6E86")
    for gx in (44, 52):
        sp.part(sp.ell(gx, 54, 3, 3), "#FFFFFF", None, "#C2D0DC", "#4E6E86")
    sp.fill(sp.rect(14, 74, 18, 77), "#5FB548")
    sp.fill(sp.rect(22, 74, 26, 77), "#E9B92F")
    sp.part(sp.rect(60, 50, PW, 55), "#A8BCCC", "#C8D6E2", "#8299AC", None)
    sp.part(sp.rect(96, 32, 101, 50), "#A8BCCC", "#C8D6E2", "#8299AC", None)
    # conveyor with boxes
    sp.part(sp.rect(56, 80, PW, 86), "#5C6E86", "#7A8DA4", "#46566C", None)
    for x in (66, 92):
        sp.part(sp.rect(x, 68, x + 14, 80), "#E2C690", "#F0DAB0", "#C3A56C", "#8C6E44")
    # floor with gold safety line
    sp.fill(sp.rect(0, 100, PW, PH), "#C9D3DC")
    sp.fill(sp.rect(0, 100, PW, 101), "#AEBBC8")
    sp.fill(sp.rect(0, 126, PW, 127), "#E9B92F")
    worker = person_sprite(PW, PH, cx=84, by=133, H=72, gender="m", hair="dark", style="short",
                           outfit="work", helmet=True, fx=-1, mouth="grin",
                           arms={-1: [(-21, 62), (-34, 70), (-46, 58)]})
    sp.over(worker)
    staff = person_sprite(PW, PH, cx=36, by=133, H=72, gender="m", hair="black", style="short",
                          helmet=True, fx=1, mouth="smile",
                          arms={1: [(21, 62), (26, 88), (14, 96)], -1: [(-21, 62), (-26, 88), (-4, 96)]},
                          prop=prop_tablet_small)
    sp.over(staff)
    return sp


def panel_consult():
    sp = Sprite(PW, PH)
    sp.fill(sp.rect(0, 0, PW, PH), "#EEF3F8")
    sp.fill(sp.rect(0, 0, PW, 3), "#D8E2EC")
    # wall screen with a data chart (no text)
    sp.part(sp.rect(24, 8, 94, 50), "#2B3A5C", None, None, None)
    scr = sp.rect(27, 11, 91, 47)
    sp.fill(scr, "#A9DDF7")
    sp.fill(scr & sp.rect(0, 30, PW, PH), "#94D3F4")
    for i, hgt in enumerate((10, 16, 13, 22, 28)):
        c = GOLD["base"] if i == 4 else ("#5FB548" if i % 2 else "#FFFFFF")
        sp.fill(sp.rect(33 + i * 11, 44 - hgt, 39 + i * 11, 44), c)
    sp.fill(sp.line([(33, 34), (47, 28), (58, 30), (70, 22), (86, 14)], 1), "#2E6F9A")
    # plant
    sp.part(sp.rect(102, 70, 112, 90), "#E9EFF6", None, "#B9C7D6", "#6B7B8E")
    sp.part(sp.ell(107, 62, 9, 11), "#86CF6B", "#B7E6A0", "#5FB548", "#3E8E34")
    # three colleagues
    for cx, kw in ((26, dict(gender="f", hair="dark", style="pony", fx=0.6, mouth="open")),
                   (92, dict(gender="m", hair="chestnut", style="part", fx=-0.6, mouth="smile", glasses=True)),
                   (59, dict(gender="m", hair="black", style="short", fx=0, mouth="grin",
                             arms={1: [(21, 62), (30, 78), (34, 66)]}))):
        sp.over(person_sprite(PW, PH, cx=cx, by=150, H=78, legs=False, **kw))
    # table
    sp.part(sp.rect(0, 108, PW, 113), "#F5EBD9", "#FFF7EA", "#D7C4A2", "#9C8460")
    sp.part(sp.rect(0, 114, PW, PH), "#D9BB8A", "#E8D1A8", "#B89763", "#8C6E44", shw=2)
    # laptop (open, lid towards the viewer) and papers on the table
    sp.part(sp.rect(44, 92, 74, 109), "#CBD5E0", "#EEF3F8", "#9AA9BA", OUTLINE)
    sp.fill(sp.rect(57, 98, 61, 102), "#EEF3F8")
    for x, y in ((8, 102), (88, 101)):
        sp.part(sp.rect(x, y, x + 20, y + 7), "#FFFFFF", None, "#C9D7E5", "#8C9FB4")
        sp.fill(sp.rect(x + 3, y + 3, x + 14, y + 3), "#A9C9E6")
    return sp


def panel_answer():
    sp = Sprite(PW, PH)
    sp.fill(sp.rect(0, 0, PW, PH), "#F2F6FA")
    # big bright window with sky
    sp.part(sp.rect(8, 8, 110, 70), "#FFFFFF", None, "#D6E0EA", "#9AAAC0")
    dither_gradient(sp.a, 11, 67, ["#7CC4EE", "#9AD3F4", "#BCE2F8"], 11, 108)
    cloud(sp, 20, 26, 40)
    cloud(sp, 70, 40, 30)
    sp.fill(sp.rect(58, 11, 59, 67), "#FFFFFF")
    sp.fill(sp.rect(11, 38, 107, 39), "#FFFFFF")
    # floor
    sp.fill(sp.rect(0, 100, PW, PH), "#E1E7EE")
    sp.fill(sp.rect(0, 100, PW, 101), "#C9D3DE")
    # plant
    sp.part(sp.rect(100, 84, 112, 104), "#E9EFF6", None, "#B9C7D6", "#6B7B8E")
    sp.part(sp.ell(106, 76, 10, 12), "#86CF6B", "#B7E6A0", "#5FB548", "#3E8E34")
    manager = person_sprite(PW, PH, cx=80, by=134, H=74, gender="m", hair="gray", style="gray",
                            outfit="suit_gray", tie="#6CBDE8", fx=-1, mouth="grin")
    sp.over(manager)
    staff = person_sprite(PW, PH, cx=32, by=134, H=74, gender="f", hair="brown", style="bob",
                          fx=1, mouth="open",
                          arms={1: [(21, 62), (28, 86), (22, 92)], -1: [(-21, 62), (-26, 88), (-14, 94)]},
                          prop=prop_doc_check)
    sp.over(staff)
    return sp


# --------------------------------------------------------------------------
# Status icons (book, calculator, speech bubble, light bulb)
# --------------------------------------------------------------------------
ICON_COLOURS = {"K": "#0B1226", "W": "#FFFFFF", "S": "#6CBDE8", "G": "#E9B92F", "Y": "#FFD84A",
                "B": "#4A9BCB", "L": "#C9D3DE", "P": "#D8F5C8"}
ICONS = {
    "book": [
        ".KKKK..KKKK.",
        "KWWWWKKWWWWK",
        "KWSSWKKWSSWK",
        "KWWWWKKWWWWK",
        "KWSSWKKWSSWK",
        "KWWWWKKWWWWK",
        "KWSSWKKWSSWK",
        "KWWWWWWWWWWK",
        "KGGGGGGGGGGK",
        ".KKKKKKKKKK.",
    ],
    "calc": [
        "KKKKKKKKKK",
        "KBBBBBBBBK",
        "KBPPPPPPBK",
        "KBPPPPPPBK",
        "KBBBBBBBBK",
        "KBWBWBWBBK",
        "KBBBBBBBBK",
        "KBWBWBWBBK",
        "KBBBBBBBBK",
        "KBWBWBGGBK",
        "KBBBBBBBBK",
        "KKKKKKKKKK",
    ],
    "talk": [
        ".KKKKKKKKKK.",
        "KWWWWWWWWWWK",
        "KWWWWWWWWWWK",
        "KWWSWWSWWSWK",
        "KWWWWWWWWWWK",
        "KWWWWWWWWWWK",
        ".KKKWWKKKKK.",
        "...KWK......",
        "...KK.......",
    ],
    "bulb": [
        "...KKKK...",
        "..KYYYYK..",
        ".KYWYYYYK.",
        ".KYWYYYYK.",
        ".KYYYYYYK.",
        ".KYYYYYYK.",
        "..KYYYYK..",
        "...KYYK...",
        "..KLLLLK..",
        "..KGGGGK..",
        "..KLLLLK..",
        "...KKKK...",
    ],
}


def build_icons():
    for name, rows in ICONS.items():
        h, w = len(rows), max(len(r) for r in rows)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch != ".":
                    im.putpixel((x, y), C(ICON_COLOURS[ch]))
        im.save(os.path.join(OUT, f"icon_{name}.png"))


def main():
    os.makedirs(OUT, exist_ok=True)
    build_background()
    build_title_plate()
    build_characters()
    build_petals()
    build_icons()
    for name, fn in (("listen", panel_listen), ("investigate", panel_investigate),
                     ("consult", panel_consult), ("answer", panel_answer)):
        fn().image().save(os.path.join(OUT, f"panel_{name}.png"))


if __name__ == "__main__":
    main()
