"""Ilustrasi stiker vektor orisinal (PIL) untuk gaya video 'explainer'.
make_sticker(nama, t, ukuran, rot) -> RGBA: gambar + outline putih + bayangan lembut.
t = detik sejak scene mulai (untuk animasi)."""
import math
from PIL import Image, ImageDraw, ImageFilter

S = 640
INK = (96, 146, 196)
PALE = (236, 247, 255)


def _new():
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _poly(d, pts, fill, line, w=5):
    d.polygon(pts, fill=fill)
    d.line(list(pts) + [pts[0]], fill=line, width=w, joint="curve")


def i_fan(t):
    im, d = _new(); cx, cy = 320, 260
    d.rounded_rectangle([165, 556, 475, 604], 24, fill=PALE, outline=INK, width=6)
    d.rectangle([297, 440, 343, 566], fill=PALE, outline=INK, width=6)
    d.ellipse([cx-212, cy-212, cx+212, cy+212], fill=(244, 251, 255), outline=INK, width=8)
    a0 = t * 10.5
    for k in range(4):
        a = a0 + k * math.pi / 2; nx, ny = -math.sin(a), math.cos(a); L = []; R = []
        for j in range(13):
            u = j / 12; r = 26 + 150 * u; w = 4 + 38 * math.sin(math.pi * u) ** 0.8
            px, py = cx + r * math.cos(a), cy + r * math.sin(a)
            L.append((px + nx * w, py + ny * w)); R.append((px - nx * w, py - ny * w))
        _poly(d, L + R[::-1], (158, 206, 240), (96, 146, 196), 4)
    d.ellipse([cx-150, cy-150, cx+150, cy+150], outline=INK, width=5)
    for k in range(8):
        a = k * math.pi / 4 + 0.39
        d.line([(cx + 44 * math.cos(a), cy + 44 * math.sin(a)), (cx + 212 * math.cos(a), cy + 212 * math.sin(a))], fill=(150, 185, 215), width=3)
    d.ellipse([cx-212, cy-212, cx+212, cy+212], outline=INK, width=8)
    d.ellipse([cx-34, cy-34, cx+34, cy+34], fill=(120, 170, 212), outline=INK, width=5)
    return im


def i_wind(t):
    im, d = _new()
    rows = [(190, 26, 70, 560), (320, 32, 120, 585), (450, 26, 50, 520)]
    for k, (y0, amp, xa, xb) in enumerate(rows):
        ph = t * 3.2 + k * 1.4; pts = []
        for x in range(xa, xb + 1, 8):
            fade = min(1.0, (x - xa) / 60.0, (xb - x) / 60.0)
            pts.append((x, y0 + amp * math.sin(x / 105.0 - ph) * (0.35 + 0.65 * fade)))
        d.line(pts, fill=(168, 214, 250), width=24, joint="curve")
        for p in (pts[0], pts[-1]): d.ellipse([p[0]-12, p[1]-12, p[0]+12, p[1]+12], fill=(168, 214, 250))
    return im


def _drop_pts(cx, cy, r, h):
    th = math.acos(r / h); pts = []
    start = -math.pi / 2 + th; end = -math.pi / 2 - th + 2 * math.pi
    n = 28
    for i in range(n + 1):
        a = start + (end - start) * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append((cx, cy - h))
    return pts


def i_drop(t):
    im, d = _new(); s = 1 + 0.03 * math.sin(t * 4)
    _poly(d, _drop_pts(320, 400, 150 * s, 330 * s), (96, 192, 255), (40, 120, 220), 7)
    d.ellipse([228, 330, 280, 430], fill=(210, 238, 255))
    return im


def _skin(t, evap):
    im, d = _new(); x0, x1 = 60, 580
    top = lambda x: 268 + 9 * math.sin(x / 36.0)
    d.rounded_rectangle([x0, 250, x1, 556], 34, fill=(250, 208, 125), outline=(190, 140, 70), width=5)
    d.rectangle([x0 + 2, 316, x1 - 2, 436], fill=(236, 120, 132))
    d.line([(x0 + 2, 436), (x1 - 2, 436)], fill=(190, 140, 70), width=4)
    pts = [(x, top(x)) for x in range(x0, x1 + 1, 6)]
    d.polygon(pts + [(x1, 322), (x0, 322)], fill=(248, 178, 170))
    d.line(pts, fill=(190, 100, 100), width=5, joint="curve")
    d.line([(x0, 322), (x1, 322)], fill=(205, 95, 105), width=4)
    for (px, py) in [(110, 365), (210, 400), (270, 350), (380, 395), (440, 355), (530, 395), (160, 345)]:
        d.ellipse([px-9, py-6, px+9, py+6], fill=(214, 92, 106))
    for (px, py) in [(130, 500), (240, 480), (340, 505), (450, 485), (520, 510)]:
        d.ellipse([px-18, py-12, px+18, py+12], fill=(255, 226, 160), outline=(215, 170, 90), width=3)
    for gx in (170, 320, 470):
        d.line([(gx, 405), (gx + 8, 360), (gx - 4, 330), (gx, top(gx) + 6)], fill=(190, 60, 80), width=9, joint="curve")
        d.ellipse([gx-22, 395, gx+22, 439], outline=(190, 60, 80), width=7)
    if not evap:
        for k, gx in enumerate((170, 320, 470)):
            r = 25 + 6 * math.sin(t * 3 + k * 1.7); cy = top(gx) - r * 0.9
            _poly(d, _drop_pts(gx, cy, r, r * 2.2), (96, 192, 255), (40, 120, 220), 4)
    else:
        lay = Image.new("RGBA", (S, S), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
        for k, gx in enumerate((170, 320, 470)):
            u = (t * 0.55 + k / 3.0) % 1.0
            y = 250 - u * 200; a = int(255 * min(1.0, u * 6) * (1 - u) ** 0.6)
            col = (60, 150, 255, a)
            ld.polygon([(gx-38, y + 6), (gx + 38, y + 6), (gx, y - 48)], fill=col)
            ld.rectangle([gx-13, y + 4, gx + 13, y + 52], fill=col)
        im.alpha_composite(lay)
    return im


def i_skin(t): return _skin(t, False)
def i_skin_evap(t): return _skin(t, True)


def i_thermo(t):
    im, d = _new(); f = 0.82 - 0.5 * _ease(t / 1.8); ym = 440 - f * 330
    d.rounded_rectangle([272, 50, 368, 470], 48, fill=(246, 249, 253), outline=(150, 165, 192), width=6)
    d.ellipse([228, 420, 412, 604], fill=(246, 249, 253), outline=(150, 165, 192), width=6)
    d.rounded_rectangle([280, 58, 360, 470], 40, fill=(246, 249, 253))
    for i in range(7):
        y = 110 + i * 48; d.line([(384, y), (384 + (36 if i % 2 == 0 else 22), y)], fill=(150, 165, 192), width=6)
    d.ellipse([254, 446, 386, 578], fill=(232, 68, 84))
    d.rounded_rectangle([302, ym, 338, 510], 18, fill=(232, 68, 84))
    d.ellipse([276, 432, 300, 456], fill=(246, 249, 253)); d.rectangle([276, 440, 300, 470], fill=(246, 249, 253))
    d.ellipse([268, 470, 296, 498], fill=(255, 150, 160))
    d.line([(560, 150), (560, 300)], fill=(70, 150, 255), width=26)
    d.polygon([(520, 290), (600, 290), (560, 350)], fill=(70, 150, 255))
    return im


def i_bolt(t):
    im, d = _new(); s = 1 + 0.04 * math.sin(t * 6)
    pts = [(380, 30), (180, 350), (300, 350), (240, 610), (470, 240), (345, 240), (430, 30)]
    pts = [(320 + (x - 320) * s, 320 + (y - 320) * s) for x, y in pts]
    _poly(d, pts, (255, 214, 64), (236, 150, 24), 8)
    return im


def i_sun(t):
    im, d = _new(); a0 = t * 0.8
    for k in range(12):
        a = a0 + k * math.pi / 6
        d.line([(320 + 190 * math.cos(a), 320 + 190 * math.sin(a)), (320 + 262 * math.cos(a), 320 + 262 * math.sin(a))], fill=(255, 190, 40), width=26)
        for r in (190, 262): d.ellipse([320 + r * math.cos(a) - 13, 320 + r * math.sin(a) - 13, 320 + r * math.cos(a) + 13, 320 + r * math.sin(a) + 13], fill=(255, 190, 40))
    d.ellipse([170, 170, 470, 470], fill=(255, 218, 80), outline=(240, 160, 30), width=7)
    return im


def i_check(t):
    im, d = _new(); s = 0.94 + 0.06 * _ease(t / 0.4)
    d.ellipse([320 - 250*s, 320 - 250*s, 320 + 250*s, 320 + 250*s], fill=(70, 200, 120), outline=(30, 140, 80), width=8)
    d.line([(190, 330), (280, 420), (455, 230)], fill=(255, 255, 255), width=56, joint="curve")
    for p in ((190, 330), (455, 230)): d.ellipse([p[0]-28, p[1]-28, p[0]+28, p[1]+28], fill=(255, 255, 255))
    return im


def i_cross(t):
    im, d = _new(); s = 0.94 + 0.06 * _ease(t / 0.4)
    d.ellipse([320 - 250*s, 320 - 250*s, 320 + 250*s, 320 + 250*s], fill=(240, 84, 94), outline=(170, 40, 56), width=8)
    d.line([(220, 220), (420, 420)], fill=(255, 255, 255), width=56); d.line([(420, 220), (220, 420)], fill=(255, 255, 255), width=56)
    for p in ((220, 220), (420, 420), (420, 220), (220, 420)): d.ellipse([p[0]-28, p[1]-28, p[0]+28, p[1]+28], fill=(255, 255, 255))
    return im


ICONS = dict(fan=i_fan, wind=i_wind, drop=i_drop, skin=i_skin, skin_evap=i_skin_evap, thermometer=i_thermo,
             bolt=i_bolt, sun=i_sun, check=i_check, cross=i_cross)



def i_heart(t):
    im, d = _new(); s = 1 + 0.09 * abs(math.sin(t * 5.5)) ** 4
    def P(x, y): return (320 + (x - 320) * s, 360 + (y - 360) * s)
    r = 122 * s; c1 = P(232, 260); c2 = P(408, 260)
    for c in (c1, c2): d.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=(240, 70, 92))
    d.polygon([P(120, 318), P(520, 318), P(320, 585)], fill=(240, 70, 92))
    d.polygon([P(125, 300), P(515, 300), P(320, 570)], fill=(240, 70, 92))
    d.ellipse([c1[0]-r*0.55, c1[1]-r*0.62, c1[0]-r*0.05, c1[1]-r*0.2], fill=(255, 160, 175))
    return im


def i_lungs(t):
    im, d = _new(); s = 1 + 0.05 * math.sin(t * 3.2)
    def X(x): return 320 + (x - 320) * s
    def Y(y): return 400 + (y - 400) * (1 + 0.03 * math.sin(t * 3.2))
    for sgn in (-1, 1):
        x0, x1 = (X(75), X(300)) if sgn < 0 else (X(340), X(565))
        d.ellipse([x0, Y(190), x1, Y(570)], fill=(255, 150, 165), outline=(205, 85, 110), width=6)
        d.ellipse([x0 + (60 if sgn < 0 else 20), Y(225), x1 - (20 if sgn < 0 else 60), Y(380)], fill=(255, 175, 188))
    d.rounded_rectangle([302, 70, 338, 290], 16, fill=(250, 214, 220), outline=(205, 85, 110), width=5)
    for sgn in (-1, 1):
        d.line([(320, 270), (320 + sgn * 70, 330), (320 + sgn * 130, 380)], fill=(250, 214, 220), width=20, joint="curve")
        d.line([(320 + sgn * 70, 330), (320 + sgn * 100, 300)], fill=(250, 214, 220), width=14)
        d.line([(320 + sgn * 100, 355), (320 + sgn * 150, 440)], fill=(250, 214, 220), width=12)
    return im


def _blob(d, circles, fill, line, w=7):
    for (x, y, r) in circles: d.ellipse([x-r-w, y-r-w, x+r+w, y+r+w], fill=line)
    for (x, y, r) in circles: d.ellipse([x-r, y-r, x+r, y+r], fill=fill)


def i_brain(t):
    im, d = _new(); s = 1 + 0.025 * math.sin(t * 3); cx, cy = 320, 280
    cs = [(cx + 175*s*math.cos(math.radians(a)), cy + 125*s*math.sin(math.radians(a)), 68) for a in range(0, 360, 30)]
    cs += [(cx, cy, 150)]
    d.rounded_rectangle([285, 400, 355, 580], 26, fill=(240, 150, 175), outline=(205, 95, 125), width=6)
    d.ellipse([360, 390, 520, 500], fill=(240, 150, 175), outline=(205, 95, 125), width=6)
    _blob(d, cs, (255, 175, 195), (205, 95, 125))
    fold = (205, 95, 125)
    d.line([(320, 150), (305, 215), (335, 280), (315, 345), (322, 410)], fill=fold, width=7, joint="curve")
    for (x, y, a0, a1) in [(190, 230, 200, 20), (215, 335, 180, 10), (450, 230, 170, 340), (430, 335, 160, 350), (250, 160, 190, 350), (400, 165, 190, 350)]:
        d.arc([x-48, y-34, x+48, y+34], a0 % 360, a1 % 360, fill=fold, width=7)
    return im


def i_glass(t):
    im, d = _new(); f = 0.72 + 0.04 * math.sin(t * 2.4); yt = 150 + (1 - f) * 380
    d.polygon([(130, 110), (510, 110), (450, 590), (190, 590)], fill=(236, 247, 255))
    w = [(x, yt + 7 * math.sin(x / 38.0 + t * 3)) for x in range(130, 511, 10)]
    lx = lambda y: 130 + (y - 110) / 480 * 60; rx = lambda y: 510 - (y - 110) / 480 * 60
    d.polygon([(lx(yt), yt)] + [(min(max(x, lx(y)), rx(y)), y) for x, y in w] + [(rx(yt), yt), (450, 590), (190, 590)], fill=(96, 192, 255))
    d.line([(130, 110), (190, 590), (450, 590), (510, 110)], fill=(96, 146, 196), width=9, joint="curve")
    d.line([(140, 110), (500, 110)], fill=(96, 146, 196), width=9)
    d.line([(210, 170), (240, 500)], fill=(255, 255, 255), width=14)
    return im


def i_moon(t):
    im, d = _new(); d.ellipse([110, 110, 530, 530], fill=(255, 224, 110), outline=(240, 170, 40), width=7)
    d.ellipse([210, 70, 600, 460], fill=(0, 0, 0, 0))
    for (x, y, r) in [(210, 340, 24), (270, 440, 16), (180, 250, 14)]: d.ellipse([x-r, y-r, x+r, y+r], fill=(255, 200, 80))
    for k, (x, y) in enumerate([(470, 150), (540, 290), (420, 420)]):
        z = 16 + 6 * math.sin(t * 4 + k * 2); d.polygon([(x, y-z), (x+z*0.35, y-z*0.35), (x+z, y), (x+z*0.35, y+z*0.35), (x, y+z), (x-z*0.35, y+z*0.35), (x-z, y), (x-z*0.35, y-z*0.35)], fill=(255, 245, 190))
    return im


def i_apple(t):
    im, d = _new(); s = 1 + 0.02 * math.sin(t * 3)
    box = [320 - 205*s, 175, 320 + 205*s, 600]
    d.ellipse([box[0]-8, box[1]-8, box[2]+8, box[3]+8], fill=(170, 30, 45))
    d.ellipse(box, fill=(238, 64, 70))
    d.ellipse([282, 160, 358, 240], fill=(170, 30, 45)); d.ellipse([290, 172, 350, 236], fill=(0, 0, 0, 0))
    d.line([(322, 230), (330, 130), (372, 78)], fill=(120, 80, 40), width=20, joint="curve")
    d.polygon([(348, 140), (470, 86), (505, 176), (395, 190)], fill=(96, 196, 96), outline=(40, 130, 60))
    d.line([(352, 150), (470, 120)], fill=(40, 130, 60), width=4)
    d.ellipse([160, 290, 214, 400], fill=(255, 150, 150))
    return im


ICONS.update(heart=i_heart, lungs=i_lungs, brain=i_brain, glass=i_glass, moon=i_moon, apple=i_apple)


def make_sticker(name, t, size, rot=0.0):
    im = ICONS[name](t)
    a = im.split()[3]
    halo = a.filter(ImageFilter.GaussianBlur(7)).point(lambda v: 255 if v > 4 else 0)
    shadow = halo.filter(ImageFilter.GaussianBlur(11)).point(lambda v: int(v * 0.38))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste((16, 26, 120, 255), (0, 12), shadow)
    out.paste((255, 255, 255, 255), (0, 0), halo)
    out.alpha_composite(im)
    out = out.resize((size, size), Image.LANCZOS)
    if rot: out = out.rotate(rot, resample=Image.BICUBIC)
    return out


def stickerize(im, size, rot=0.0):
    """Beri outline putih + bayangan pada RGBA berukuran bebas (mis. frame render 3D)."""
    a = im.split()[3]
    halo = a.filter(ImageFilter.GaussianBlur(7)).point(lambda v: 255 if v > 4 else 0)
    shadow = halo.filter(ImageFilter.GaussianBlur(11)).point(lambda v: int(v * 0.38))
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste((16, 26, 120, 255), (0, 12), shadow)
    out.paste((255, 255, 255, 255), (0, 0), halo)
    out.alpha_composite(im)
    out = out.resize((size, size), Image.LANCZOS)
    if rot: out = out.rotate(rot, resample=Image.BICUBIC)
    return out
