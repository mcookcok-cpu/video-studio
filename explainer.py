"""Gaya video 'explainer': background polos, stiker ilustrasi, subtitle miring tebal kata per kata."""
import math, os, re, json
from functools import lru_cache
from PIL import ImageFont
import stickers as ST

FONTS = ["/usr/share/fonts/truetype/freefont/FreeSansBoldOblique.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf"]
_FC = {}


def font(size):
    if size not in _FC:
        for p in FONTS:
            if os.path.exists(p):
                _FC[size] = ImageFont.truetype(p, size); break
        else:
            _FC[size] = ImageFont.load_default()
    return _FC[size]


def pop(x):  # easeOutBack: muncul membesar sedikit lalu mengendap
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


LAYOUT = {1: [(540, 800, 840)],
          2: [(360, 640, 560), (740, 1060, 560)],
          3: [(320, 560, 460), (760, 840, 460), (380, 1120, 460)]}


def g_sticker(img, od, lt, D, p, ga, sc):
    P = sc["params"]; raw = P.get("icons") or [P.get("icon")]
    if not isinstance(raw, list): raw = [raw]
    names = [n for n in raw if isinstance(n, str) and n in ST.ICONS][:3] or ["drop"]
    for i, (nm, (cx, cy, sz)) in enumerate(zip(names, LAYOUT[len(names)])):
        k = pop((lt - 0.10 - 0.55 * i) / 0.42)
        if k <= 0: continue
        bob = 11 * math.sin(lt * 2.1 + i * 1.3)
        layer = ST.make_sticker(nm, max(0.0, lt - 0.10 - 0.55 * i), max(16, int(sz * k)), rot=3.0 * math.sin(lt * 1.6 + i))
        img.paste(layer, (int(cx - layer.width / 2), int(cy + bob - layer.height / 2)), layer)


def draw_caption(od, sc, lt):
    ws = sc["words"]
    if not ws or lt < ws[0]["s"]: return
    idx = max(i for i, w in enumerate(ws) if w["s"] <= lt)
    groups, cur = [], []
    for i, w in enumerate(ws):
        cur.append(i)
        if len(cur) >= 3 or w["text"][-1:] in ".,!?;:": groups.append(cur); cur = []
    if cur: groups.append(cur)
    g = next((x for x in groups if idx in x), groups[-1])
    size = 88
    while size > 48:
        f = font(size); sp = f.getlength(" ")
        total = sum(f.getlength(ws[i]["text"]) for i in g) + sp * (len(g) - 1)
        if total <= 960: break
        size -= 4
    x = 540 - total / 2; y = 1500
    for i in g:
        w = ws[i]; tw = f.getlength(w["text"])
        if w["s"] <= lt:
            dy = -int(14 * max(0.0, 1 - (lt - w["s"]) / 0.16)) if i == idx else 0
            fill = (255, 255, 255, 255) if i == idx else (206, 212, 255, 255)
            od.text((x, y + dy + 7), w["text"], font=f, fill=(20, 22, 110, 140), anchor="lm", stroke_width=11, stroke_fill=(20, 22, 110, 140))
            od.text((x, y + dy), w["text"], font=f, fill=fill, anchor="lm", stroke_width=9, stroke_fill=(42, 40, 160, 255))
        x += tw + sp


CLIPS = os.path.join(os.environ.get("VIDEO_STUDIO_ROOT", "/home/Claude/video-studio"), "assets", "clips")


@lru_cache(maxsize=None)
def _clip_meta(name):
    try: return json.load(open(f"{CLIPS}/{name}/clip.json"))
    except Exception: return None


@lru_cache(maxsize=40)
def _clip_frame(name, i):
    from PIL import Image
    return Image.open(f"{CLIPS}/{name}/f_{i + 1:04d}.png").convert("RGBA")


def g_clip3d(img, od, lt, D, p, ga, sc):
    """Klip hasil render 3D (assets/clips/<nama>/f_0001.png ...) sebagai stiker beranimasi."""
    name = str(sc["params"].get("clip", ""))
    if not re.fullmatch(r"[a-z0-9_-]{1,40}", name): return
    m = _clip_meta(name)
    if not m: return
    k = pop((lt - 0.05) / 0.40)
    if k <= 0: return
    i = max(0, min(m["n"] - 1, int(lt * m["fps"])))
    layer = ST.stickerize(_clip_frame(name, i), max(16, int(900 * k)))
    img.paste(layer, (540 - layer.width // 2, 790 - layer.height // 2), layer)
