#!/usr/bin/env python3
# Video generator: "5 Fakta Gila Luar Angkasa" (vertikal 1080x1920, 30fps)
import os, sys, math, json, subprocess, asyncio, random, bisect
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from multiprocessing import Pool

W, H, FPS = 1080, 1920, 30
BASE = os.environ.get("VIDEO_STUDIO_ROOT", "/home/Claude/video-studio")
WORK, OUT = f"{BASE}/work", f"{BASE}/output"
VOICE = "id-ID-ArdiNeural"
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
LEAD, TAIL = 0.3, 0.7

SCENES = [
 dict(kind="intro", num=None, t1="5 FAKTA GILA", t2="LUAR ANGKASA", tint=(60, 25, 120),
  text="Kamu merasa sudah tahu banyak soal luar angkasa? Coba dengarkan 5 fakta ini. Nomor 3 bikin merinding!"),
 dict(kind="venus", num=1, t1="HARI > TAHUN", t2="DI PLANET VENUS", tint=(120, 55, 15),
  text="Nomor 1. Di Venus, satu hari lebih lama dari satu tahun! Planet ini butuh 243 hari Bumi untuk berputar sekali, tapi hanya 225 hari untuk mengelilingi Matahari."),
 dict(kind="silence", num=2, t1="DI ANGKASA", t2="TIDAK ADA SUARA", tint=(15, 70, 110),
  text="Nomor 2. Di luar angkasa, tidak ada suara sama sekali. Ruang hampa tidak punya udara untuk merambatkan gelombang suara, jadi ledakan sebesar apa pun tetap sunyi."),
 dict(kind="neutron", num=3, t1="BINTANG NEUTRON", t2="SUPER PADAT", tint=(30, 50, 140),
  text="Nomor 3. Satu sendok teh materi bintang neutron beratnya bisa miliaran ton. Bayangkan massa Matahari diperas menjadi bola seukuran kota."),
 dict(kind="sunlight", num=4, t1="CAHAYA MATAHARI", t2="DARI 8 MENIT LALU", tint=(130, 70, 10),
  text="Nomor 4. Cahaya Matahari yang kamu lihat sekarang adalah cahaya dari 8 menit lalu. Cahaya butuh sekitar 8 menit 20 detik untuk menempuh 150 juta kilometer ke Bumi."),
 dict(kind="stars", num=5, t1="BINTANG LEBIH BANYAK", t2="DARI BUTIR PASIR", tint=(70, 30, 130),
  text="Nomor 5. Jumlah bintang di alam semesta yang teramati diperkirakan lebih banyak daripada seluruh butir pasir di semua pantai Bumi."),
 dict(kind="outro", num=None, t1="FOLLOW UNTUK", t2="FAKTA LAINNYA", tint=(110, 30, 90),
  text="Itu tadi 5 fakta luar angkasa. Mana yang paling bikin kamu kaget? Tulis di komentar, dan follow untuk fakta seru lainnya!"),
]

# ------------------------------------------------------------------ PREP
def probe(path):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",path],capture_output=True,text=True)
    return float(r.stdout.strip())

async def tts(text, path):
    import edge_tts
    comm = edge_tts.Communicate(text, VOICE, rate="+4%", boundary="WordBoundary")
    words, sents = [], []
    with open(path, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio": f.write(ch["data"])
            elif ch["type"] == "WordBoundary": words.append((ch["offset"]/1e7, ch["duration"]/1e7, ch["text"]))
            elif ch["type"] == "SentenceBoundary": sents.append((ch["offset"]/1e7, ch["duration"]/1e7, ch["text"]))
    return words, sents

def fallback_words(text, adur):
    toks = text.split(); wts = [len(t)+2 for t in toks]; tot = sum(wts); cur = 0.05; out = []
    for t, w in zip(toks, wts):
        d = (adur-0.1)*w/tot; out.append((cur, d, t)); cur += d
    return out

def make_groups(words):
    groups, cur = [], []
    for w in words:
        cur.append(w)
        end = w["text"][-1:] in ".,!?"
        if len(cur) >= 4 or (end and len(cur) >= 2):
            groups.append(cur); cur = []
    if cur: groups.append(cur)
    return groups

def prep():
    meta = {"scenes": []}; t0 = 0.0
    for i, sc in enumerate(SCENES):
        mp3 = f"{WORK}/s{i}.mp3"
        words, sents = asyncio.run(tts(sc["text"], mp3))
        adur = probe(mp3)
        mode = "word"
        if not words:
            mode = "fallback"; words = fallback_words(sc["text"], adur)
        else:
            # pakai teks tampilan asli (tanda baca) jika jumlah kata sama
            toks = sc["text"].split()
            if len(toks) == len(words):
                words = [(w[0], w[1], toks[j]) for j, w in enumerate(words)]
                mode = "word+punct"
        dur = LEAD + adur + TAIL
        wl = [{"s": w[0]+LEAD, "d": w[1], "text": w[2]} for w in words]
        s = dict(sc); s.update(start=t0, dur=dur, adur=adur, words=wl, mode=mode)
        meta["scenes"].append(s); t0 += dur
        print(f"scene {i} {sc['kind']}: audio {adur:.2f}s dur {dur:.2f}s words={len(words)} mode={mode}", flush=True)
    meta["total"] = t0
    json.dump(meta, open(f"{WORK}/meta.json", "w"), ensure_ascii=False, indent=1)
    # narasi: tiap scene di-pad ke durasinya lalu digabung
    lst = []
    for i, s in enumerate(meta["scenes"]):
        wav = f"{WORK}/s{i}.wav"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-i",f"{WORK}/s{i}.mp3","-af",
            f"adelay={int(LEAD*1000)}|{int(LEAD*1000)},apad=whole_dur={s['dur']:.3f}","-ar","44100","-ac","2",wav],check=True)
        lst.append(f"file '{wav}'")
    open(f"{WORK}/list.txt","w").write("\n".join(lst))
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",f"{WORK}/list.txt","-c","copy",f"{WORK}/narration.wav"],check=True)
    # musik latar ambient (sintesis)
    T = meta["total"] + 1
    expr = ("0.35*sin(2*PI*110*t)+0.25*sin(2*PI*164.81*t)*(0.7+0.3*sin(2*PI*0.13*t))"
            "+0.2*sin(2*PI*220*t)+0.12*sin(2*PI*329.63*t)*(0.5+0.5*sin(2*PI*0.07*t))"
            "+0.08*sin(2*PI*440*t)*(0.5+0.5*sin(2*PI*0.21*t))")
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","lavfi","-i",f"aevalsrc='{expr}':s=44100:d={T:.2f}",
        "-af","lowpass=f=1100,volume=0.6","-ac","2",f"{WORK}/music.wav"],check=True)
    print("prep selesai, total", round(meta["total"],2), "detik", flush=True)

# ------------------------------------------------------------------ RENDER
M = None; BG = []; STARS = None; FC = {}; SPR = {}; GAL = None

def font(path, size):
    k = (path, size)
    if k not in FC: FC[k] = ImageFont.truetype(path, size)
    return FC[k]

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x*x*(3-2*x)
def col(c, a=1.0): return (int(c[0]), int(c[1]), int(c[2]), int(255*clamp(a)))

def make_bg(tint):
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    x = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
    top = np.array([4, 5, 16], np.float32); bot = np.array(tint, np.float32)*0.42
    base = top[None, None, :]*(1-y[..., None]) + bot[None, None, :]*y[..., None]
    base = np.broadcast_to(base, (H, W, 3)).copy()
    yy = (np.linspace(0, 1, H, dtype=np.float32)[:, None] - 0.34)
    rad = np.exp(-((x*0.9)**2 + (yy*1.1)**2)*5.0)
    base += rad[..., None]*np.array(tint, np.float32)[None, None, :]*0.55
    return np.clip(base, 0, 255).astype(np.uint8)

def sphere(r, base, accent, rot=0.0, light=(-0.5, -0.55), bands=6.0):
    ys, xs = np.mgrid[-r:r, -r:r].astype(np.float32); ys += .5; xs += .5
    nx, ny = xs/r, ys/r; rr = nx*nx+ny*ny
    nz = np.sqrt(np.clip(1-rr, 0, 1))
    lat = np.arcsin(np.clip(ny, -1, 1)); lon = np.arctan2(nx, nz)+rot
    tex = 0.5+0.5*np.sin(bands*lat+1.6*np.sin(2*lon+1.3*np.sin(lat*3)))
    c = np.array(base, np.float32)[None, None, :]*(1-tex[..., None]) + np.array(accent, np.float32)[None, None, :]*tex[..., None]
    lx, ly = light; lz = math.sqrt(max(1e-4, 1-lx*lx-ly*ly))
    diff = np.clip(nx*lx+ny*ly+nz*lz, 0, 1)
    shade = 0.14+0.95*diff
    rim = ((1-nz)**3*0.5)[..., None]*np.array(accent, np.float32)[None, None, :]
    out = np.clip(c*shade[..., None]+rim, 0, 255).astype(np.uint8)
    alpha = (np.clip((1.0-np.sqrt(rr))*r, 0, 1)*255).astype(np.uint8)
    return Image.fromarray(np.dstack([out, alpha]), "RGBA")

def glow(r, color, power=2.2):
    k = (r, color, power)
    if k not in SPR:
        ys, xs = np.mgrid[-r:r, -r:r].astype(np.float32)
        a = np.clip(1-np.sqrt(xs**2+ys**2)/r, 0, 1)**power
        arr = np.zeros((2*r, 2*r, 4), np.uint8); arr[..., 0], arr[..., 1], arr[..., 2] = color
        arr[..., 3] = (a*255).astype(np.uint8)
        SPR[k] = Image.fromarray(arr, "RGBA")
    return SPR[k]

def paste_c(img, spr, cx, cy, alpha=1.0):
    x, y = int(cx-spr.width/2), int(cy-spr.height/2)
    if alpha >= 0.999: img.paste(spr, (x, y), spr)
    elif alpha > 0.01:
        m = spr.getchannel("A").point(lambda v: int(v*alpha)); img.paste(spr, (x, y), m)

def disc(img, cx, cy, r, color, a=1.0):
    n = int(r+3); ys, xs = np.mgrid[-n:n+1, -n:n+1].astype(np.float32)
    al = np.clip(r+0.5-np.sqrt(xs**2+ys**2), 0, 1)*a
    arr = np.zeros((2*n+1, 2*n+1, 4), np.uint8); arr[..., 0], arr[..., 1], arr[..., 2] = color[:3]
    arr[..., 3] = (al*255).astype(np.uint8)
    spr = Image.fromarray(arr, "RGBA"); img.paste(spr, (int(cx-n), int(cy-n)), spr)

def ring(img, cx, cy, r, w, color, a=1.0):
    if a <= 0.01: return
    n = int(r+w+3); ys, xs = np.mgrid[-n:n+1, -n:n+1].astype(np.float32)
    al = np.clip(w/2+0.5-np.abs(np.sqrt(xs**2+ys**2)-r), 0, 1)*a
    arr = np.zeros((2*n+1, 2*n+1, 4), np.uint8); arr[..., 0], arr[..., 1], arr[..., 2] = color[:3]
    arr[..., 3] = (al*255).astype(np.uint8)
    spr = Image.fromarray(arr, "RGBA"); img.paste(spr, (int(cx-n), int(cy-n)), spr)

def txt(d, xy, s, f, fill, stroke=0, anchor="mm"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0, fill[3]) if len(fill) > 3 else (0, 0, 0))

# ---------- grafik per scene
def g_intro(img, od, lt, D, p, ga):
    cx, cy = 540, 640
    paste_c(img, glow(380, (130, 80, 255)), cx, cy, 0.8*ga)
    ang = lt*0.9
    mx, my, behind = cx+360*math.cos(ang), cy+90*math.sin(ang), math.sin(ang) < 0
    if behind: disc(img, mx, my, 28, (230, 230, 255), ga)
    paste_c(img, sphere(220, (70, 30, 140), (255, 130, 210), rot=lt*0.5, bands=5), cx, cy, ga)
    if not behind: disc(img, mx, my, 28, (230, 230, 255), ga)
    ring(img, cx, cy, 300+8*math.sin(lt*2), 3, (200, 170, 255), 0.35*ga)

def g_venus(img, od, lt, D, p, ga):
    cx, cy = 540, 560
    paste_c(img, glow(310, (255, 150, 40)), cx, cy, 0.75*ga)
    paste_c(img, sphere(185, (150, 70, 20), (255, 195, 95), rot=-lt*0.18, bands=5), cx, cy, ga)
    for (y, label, w, c, t0) in ((850, "1 HARI = 243 hari Bumi", 900, (235, 80, 50), 1.5), (950, "1 TAHUN = 225 hari Bumi", 900*225/243, (255, 200, 70), 3.2)):
        k = ease((lt-t0)/1.3)
        if k > 0:
            x0 = 90
            od.rounded_rectangle([x0, y-36, x0+max(44, w*k), y+36], 18, fill=col(c, 0.92))
            txt(od, (x0+24, y), label, font(FB, 36), col((255, 255, 255), clamp(k*1.5)), 2, "lm")

def g_silence(img, od, lt, D, p, ga):
    cx, cy = 540, 620; earth = p < 0.45
    c = (90, 220, 255) if earth else (255, 90, 90)
    lim = 340 if earth else 95
    for k in range(4):
        ph = (lt*0.55+k/4.0) % 1.0
        ring(img, cx, cy, 50+ph*(lim-50), 6, c, (1-ph)*0.9*ga)
    disc(img, cx, cy, 46+4*math.sin(lt*6), (255, 255, 255), ga)
    if not earth:
        k = ease((p-0.45)/0.08)
        od.line([(cx-80, cy-80), (cx+80, cy+80)], fill=col((255, 70, 70), k), width=14)
    lab = "DI BUMI: ADA SUARA" if earth else "DI ANGKASA: HENING"
    txt(od, (540, 930), lab, font(FB, 52), col(c, ga), 3)

def g_neutron(img, od, lt, D, p, ga):
    cx, cy = 540, 580
    pulse = 0.55+0.25*math.sin(lt*6)
    paste_c(img, glow(340, (120, 170, 255), 2.0), cx, cy, pulse*ga)
    bl = Image.new("RGBA", (W//2, H//2), (0, 0, 0, 0)); bd = ImageDraw.Draw(bl)
    a0 = lt*2.2
    for a in (a0, a0+math.pi):
        L, wd = 520, 0.075
        pts = [(cx/2, cy/2), ((cx+L*math.cos(a-wd))/2, (cy+L*math.sin(a-wd))/2), ((cx+L*math.cos(a+wd))/2, (cy+L*math.sin(a+wd))/2)]
        bd.polygon(pts, fill=(170, 210, 255, int(95*ga)))
    bl = bl.resize((W, H), Image.BILINEAR); img.paste(bl, (0, 0), bl)
    paste_c(img, sphere(62, (190, 220, 255), (255, 255, 255), rot=lt*3, bands=3), cx, cy, ga)
    k = ease((lt-1.8)/0.8)
    txt(od, (540, 930), "1 sendok teh =", font(FB, 48), col((220, 230, 255), k), 3)
    txt(od, (540, 1005), "MILIARAN TON", font(FB, 80), col((255, 214, 90), k), 4)

def g_sunlight(img, od, lt, D, p, ga):
    sx, ex, y = 190, 890, 640
    paste_c(img, glow(270, (255, 170, 40)), sx, y, 0.8*ga)
    paste_c(img, sphere(120, (255, 140, 20), (255, 235, 100), rot=lt*0.2, bands=4), sx, y, ga)
    paste_c(img, glow(110, (80, 150, 255), 2.5), ex, y, 0.6*ga)
    paste_c(img, sphere(54, (20, 70, 170), (80, 170, 100), rot=lt*0.6, bands=7), ex, y, ga)
    q = clamp((lt-0.6)/(D-2.0)); x0, x1 = sx+130, ex-60
    for i in range(0, 22):
        xx = x0+(x1-x0)*i/21
        od.rectangle([xx-7, y-2, xx+7, y+2], fill=col((255, 255, 255), 0.18*ga))
    px = x0+(x1-x0)*q
    for i in range(1, 9): disc(img, px-i*18, y, 11-i, (255, 235, 140), (1-i/9)*0.7*ga)
    disc(img, px, y, 14, (255, 250, 200), ga)
    secs = int(q*500); txt(od, (540, 400), f"{secs//60:02d}:{secs%60:02d}", font(FM, 160), col((255, 214, 90), ga), 5)
    txt(od, (540, 505), "menit : detik", font(FB, 34), col((200, 210, 255), 0.8*ga), 2)
    txt(od, (540, 780), "150 juta km", font(FB, 48), col((255, 255, 255), ga), 3)

def g_stars(img, od, lt, D, p, ga):
    cx, cy = 540, 600
    paste_c(img, glow(150, (255, 220, 170), 1.6), cx, cy, 0.8*ga)
    ang = lt*0.25
    r, th, cc, sz = GAL
    a = th+ang; x = cx+r*np.cos(a); y = cy+r*np.sin(a)*0.62
    d = ImageDraw.Draw(img)
    for i in range(len(r)):
        tw = 0.6+0.4*math.sin(lt*3+i); s = sz[i]; c = tuple(int(v*tw*ga) for v in cc[i])
        d.ellipse([x[i]-s, y[i]-s, x[i]+s, y[i]+s], fill=c)
    k1, k2 = ease((lt-2.0)/0.8), ease((lt-3.6)/0.8)
    txt(od, (540, 930), "BINTANG  ≈ 10²²", font(FB, 60), col((120, 220, 255), k1), 3)
    txt(od, (540, 1015), "BUTIR PASIR  ≈ 10¹⁹", font(FB, 60), col((255, 205, 120), k2), 3)

def g_outro(img, od, lt, D, p, ga):
    cx, cy = 540, 640
    paste_c(img, glow(330, (255, 120, 190)), cx, cy, 0.7*ga)
    rr = 150*(1+0.06*math.sin(lt*5))
    for k in range(3):
        ph = (lt*0.6+k/3.0) % 1.0
        ring(img, cx, cy, rr+ph*170, 5, (255, 220, 120), (1-ph)*0.7*ga)
    disc(img, cx, cy, rr, (255, 200, 70), ga)
    od.rounded_rectangle([cx-70, cy-14, cx+70, cy+14], 12, fill=col((60, 25, 90), ga))
    od.rounded_rectangle([cx-14, cy-70, cx+14, cy+70], 12, fill=col((60, 25, 90), ga))
    k = ease((lt-1.0)/0.8)
    txt(od, (540, 940), "Fakta mana yang paling", font(FB, 48), col((255, 255, 255), k), 3)
    txt(od, (540, 1005), "bikin kamu kaget?", font(FB, 48), col((255, 255, 255), k), 3)

GRAPHICS = dict(intro=g_intro, venus=g_venus, silence=g_silence, neutron=g_neutron, sunlight=g_sunlight, stars=g_stars, outro=g_outro)

# ---------- teks UI
def fit(lines, maxw=980, hi=92, lo=50):
    for s in range(hi, lo-1, -2):
        f = font(FB, s)
        if max(f.getlength(l) for l in lines) <= maxw: return f
    return font(FB, lo)

def draw_title(od, sc, lt):
    k = ease(lt/0.5); off = (1-k)*50
    lines = [sc["t1"], sc["t2"]]; f = fit(lines); lh = int(f.size*1.18); y0 = 1215-lh/2+off
    txt(od, (540, y0), lines[0], f, col((255, 255, 255), k), 7)
    txt(od, (540, y0+lh), lines[1], f, col((255, 214, 90), k), 7)

def draw_header(od, sc, lt):
    txt(od, (540, 96), "FAKTA ANGKASA", font(FB, 38), col((200, 210, 255), 0.85), 2)
    od.line([(390, 140), (690, 140)], fill=col((200, 210, 255), 0.4), width=3)

def draw_badge(img, od, sc, lt):
    if sc["num"] is None: return
    k = ease(lt/0.4); disc(img, 540, 230, 62*(0.6+0.4*k), (255, 200, 70), k)
    txt(od, (540, 234), str(sc["num"]), font(FB, 78), col((40, 20, 70), k))

def draw_caption(od, sc, lt):
    ws = sc["words"]
    if not ws or lt < ws[0]["s"]-0.15: return
    idx = 0
    for i, w in enumerate(ws):
        if w["s"] <= lt: idx = i
    # grup
    gi, groups, cur = 0, [], []
    for i, w in enumerate(ws):
        cur.append(i)
        if len(cur) >= 4 or (w["text"][-1:] in ".,!?" and len(cur) >= 2): groups.append(cur); cur = []
    if cur: groups.append(cur)
    g = next((x for x in groups if idx in x), groups[-1])
    f = font(FB, 66); sp = f.getlength(" ")
    lines, cur, curw = [], [], 0
    for i in g:
        wl = f.getlength(ws[i]["text"])
        if cur and curw+sp+wl > 940: lines.append((cur, curw)); cur, curw = [], 0
        curw = curw+(sp if cur else 0)+wl; cur.append(i)
    lines.append((cur, curw))
    lh = 92; bh = lh*len(lines)+44; bw = max(l[1] for l in lines)+70; cy = 1560
    od.rounded_rectangle([540-bw/2, cy-bh/2, 540+bw/2, cy+bh/2], 34, fill=(0, 0, 0, 150))
    for li, (idxs, lw) in enumerate(lines):
        x = 540-lw/2; y = cy-bh/2+22+lh*li+lh/2
        for i in idxs:
            on = (i == idx)
            od.text((x, y), ws[i]["text"], font=f, fill=(255, 224, 80, 255) if on else (255, 255, 255, 255), anchor="lm", stroke_width=4, stroke_fill=(0, 0, 0, 255))
            x += f.getlength(ws[i]["text"])+sp

def draw_progress(od, t):
    q = clamp(t/M["total"])
    od.rounded_rectangle([120, 165, 960, 175], 5, fill=(255, 255, 255, 50))
    if 840*q >= 14: od.rounded_rectangle([120, 165, 120+840*q, 175], 5, fill=(255, 214, 90, 230))

# ---------- bintang latar
def init_globals():
    global M, BG, STARS, GAL
    M = json.load(open(f"{WORK}/meta.json"))
    BG = [make_bg(s["tint"]) for s in M["scenes"]]
    rng = np.random.default_rng(7)
    n = 260
    STARS = dict(x=rng.uniform(0, W, n), y=rng.uniform(0, H, n), sp=rng.uniform(14, 120, n), sz=rng.uniform(0.8, 3.2, n),
                 ph=rng.uniform(0, 6.28, n), tw=rng.uniform(1.5, 4.5, n), c=rng.integers(0, 3, n))
    m = 650; r = rng.random(m)**0.7*340; arm = rng.integers(0, 2, m)
    th = arm*math.pi + r*0.018 + rng.normal(0, 0.28, m)
    pal = np.array([(255, 255, 255), (150, 190, 255), (255, 220, 150)])
    GAL = (r, th, pal[rng.integers(0, 3, m)], rng.uniform(1.2, 3.0, m))
    starts = [s["start"] for s in M["scenes"]]
    M["_starts"] = starts

def scene_index(t):
    return max(0, bisect.bisect_right(M["_starts"], t)-1)

def draw_stars(d, t):
    S = STARS
    pal = [(255, 255, 255), (170, 200, 255), (255, 230, 170)]
    for i in range(len(S["x"])):
        y = (S["y"][i]-S["sp"][i]*t) % H
        b = 0.55+0.45*math.sin(t*S["tw"][i]+S["ph"][i])
        c = pal[S["c"][i]]; s = S["sz"][i]
        d.ellipse([S["x"][i]-s, y-s, S["x"][i]+s, y+s], fill=(int(c[0]*b), int(c[1]*b), int(c[2]*b)))

def render(fi):
    t = fi/FPS; si = scene_index(t); sc = M["scenes"][si]; lt = t-sc["start"]; D = sc["dur"]; p = lt/D
    k = ease(lt/0.4) if si > 0 else 1.0
    if k < 1.0: arr = (BG[si-1].astype(np.float32)*(1-k)+BG[si].astype(np.float32)*k).astype(np.uint8)
    else: arr = BG[si]
    img = Image.fromarray(arr); d = ImageDraw.Draw(img)
    draw_stars(d, t)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    GRAPHICS[sc["kind"]](img, od, lt, D, p, ease(lt/0.5))
    draw_badge(img, od, sc, lt)
    draw_header(od, sc, lt); draw_title(od, sc, lt); draw_caption(od, sc, lt); draw_progress(od, t)
    img.paste(ov, (0, 0), ov)
    return img.convert("RGB").tobytes()

def still(t, path):
    fi = int(t*FPS); b = render(fi)
    Image.frombytes("RGB", (W, H), b).save(path)

def ascii_preview(path, cols=54):
    im = Image.open(path).convert("L").resize((cols, int(cols*H/W*0.5)))
    chars = " .:-=+*#%@"; a = np.array(im)
    return "\n".join("".join(chars[min(9, v*10//256)] for v in row) for row in a)

def full():
    total_frames = int(math.ceil(M["total"]*FPS))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", f"{WORK}/silent.mp4"]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(2) as pool:
        for n, b in enumerate(pool.imap(render, range(total_frames), chunksize=6)):
            pr.stdin.write(b)
            if n % 60 == 0: print(f"frame {n}/{total_frames}", flush=True)
    pr.stdin.close(); pr.wait()
    T = M["total"]
    fc = (f"[1:a]volume=1.0[a1];[2:a]volume=0.16,afade=t=in:d=2,afade=t=out:st={T-2.5:.2f}:d=2.5[a2];"
          f"[a1][a2]amix=inputs=2:duration=first,volume=2[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{WORK}/silent.mp4", "-i", f"{WORK}/narration.wav", "-i", f"{WORK}/music.wav",
        "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{T:.2f}",
        f"{OUT}/5-fakta-gila-luar-angkasa.mp4"], check=True)
    still(1.6, f"{OUT}/thumbnail.png")
    print("SELESAI", flush=True)

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "prep": prep()
    else:
        init_globals()
        if mode == "test":
            for i, s in enumerate(M["scenes"]):
                tt = s["start"]+min(s["dur"]-0.2, 4.5)
                pth = f"{WORK}/test{i}.png"; still(tt, pth); print("ok", i, s["kind"], pth, flush=True)
        elif mode == "ascii":
            print(ascii_preview(sys.argv[2]))
        elif mode == "full": full()
