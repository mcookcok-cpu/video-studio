#!/usr/bin/env python3
"""Engine video generik (spec JSON -> MP4 9:16). Pemakaian: engine.py <job_dir> [stills]"""
import os, sys, json, math, subprocess, asyncio, re, time, shutil, traceback
ROOT = os.environ.get("VIDEO_STUDIO_ROOT", "/home/Claude/video-studio")
sys.path.insert(0, ROOT)
import numpy as np
import build as b
import explainer as X
from PIL import Image, ImageDraw
from multiprocessing import Pool

W, H, FPS = b.W, b.H, b.FPS
OUTDIR = os.path.join(ROOT, "output")
LEAD, TAIL = 0.3, 0.7
JOB = None
HEADER = ""

THEMES = {
 "orange": dict(tint=(120, 55, 15), base=(150, 70, 20), accent=(255, 195, 95), glow=(255, 150, 40)),
 "blue":   dict(tint=(30, 50, 140), base=(20, 60, 160), accent=(120, 200, 255), glow=(90, 150, 255)),
 "purple": dict(tint=(70, 30, 130), base=(70, 30, 140), accent=(255, 130, 210), glow=(130, 80, 255)),
 "teal":   dict(tint=(15, 70, 110), base=(10, 80, 110), accent=(90, 230, 220), glow=(60, 200, 230)),
 "pink":   dict(tint=(110, 30, 90), base=(150, 30, 100), accent=(255, 170, 200), glow=(255, 120, 190)),
 "green":  dict(tint=(20, 100, 60), base=(20, 90, 50), accent=(150, 240, 150), glow=(80, 220, 130)),
 "red":    dict(tint=(130, 30, 30), base=(140, 25, 25), accent=(255, 140, 100), glow=(255, 80, 70)),
 "gold":   dict(tint=(130, 70, 10), base=(160, 100, 10), accent=(255, 225, 110), glow=(255, 190, 50)),
}
THEME_ORDER = ["purple", "orange", "teal", "blue", "gold", "pink", "green", "red"]
GRAPHICS_OK = ["statement", "planet", "rings", "bars", "counter", "list", "galaxy", "cta", "sticker", "clip3d"]
STYLE = "cosmic"; BGX = (70, 100, 250)
GOLD = (255, 214, 90)

def status(**kw):
    p = os.path.join(JOB, "status.json"); s = {}
    try: s = json.load(open(p))
    except Exception: pass
    s.update(kw); s["updated"] = time.time()
    tmp = p + ".tmp"; json.dump(s, open(tmp, "w")); os.replace(tmp, p)

# ------------------------------------------------------------ PREP
async def tts(text, path, voice, rate):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(path, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio": f.write(ch["data"])
            elif ch["type"] == "WordBoundary": words.append((ch["offset"]/1e7, ch["duration"]/1e7, ch["text"]))
    return words

POCKET_URL = os.environ.get("POCKET_TTS_URL", "http://127.0.0.1:6001")

def tts_pocket(text, path, voice, style="percakapan", jeda_skala=1.0):
    """Narasi dari server Pocket TTS (port 6001, mode Eksperimental), disimpan sebagai mp3 di `path`.
    Server tidak memberi waktu per kata, jadi waktunya dihitung di sini: batas kalimat dicari dari
    jeda senyap di audio (n kalimat = n-1 jeda terpanjang), lalu kata dibagi sesuai panjangnya
    di dalam tiap kalimat. Mengembalikan [(mulai, durasi, teks)] atau None (pakai pembagian rata)."""
    import urllib.request
    body = json.dumps({"segmen": [{"teks": text.replace("!", ".")}], "voice": voice, "style": style,
                       "jeda_skala": jeda_skala, "pecah_koma": False}).encode()
    req = urllib.request.Request(POCKET_URL + "/tts/script-eksp", body, {"Content-Type": "application/json"})
    wav = path.rsplit(".", 1)[0] + "_pocket.wav"
    with urllib.request.urlopen(req, timeout=300) as r:
        open(wav, "wb").write(r.read())
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "192k", path])
    dur = b.probe(wav)
    err = subprocess.run(["ffmpeg", "-i", wav, "-af", "silencedetect=noise=-38dB:d=0.2", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    os.remove(wav)
    lead, speech_end, gaps = 0.0, dur, []
    for k, st in enumerate(starts):
        en = ends[k] if k < len(ends) else None
        if st < 0.05 and en is not None: lead = en
        elif en is None or en >= dur - 0.05: speech_end = max(st, lead + 0.1)
        else: gaps.append((st, en))
    sents = [x for x in re.split(r"(?<=[.?!])\s+", text.strip()) if x]
    if len(sents) > 1:
        if len(gaps) < len(sents) - 1: return None
        gaps = sorted(sorted(gaps, key=lambda g: g[1] - g[0], reverse=True)[:len(sents) - 1])
    else:
        gaps = []
    t_start = [lead] + [g[1] for g in gaps]
    t_end = [g[0] for g in gaps] + [speech_end]
    words = []
    for j, sent in enumerate(sents):
        toks = sent.split()
        wts = [len(t) + 2 + (3 if t[-1:] == "," else 0) for t in toks]
        tot = float(sum(wts)); cur = t_start[j]; span = max(0.2, t_end[j] - t_start[j])
        for t, w in zip(toks, wts):
            d = span * w / tot; words.append((cur, d, t)); cur += d
    return words

def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError("ffmpeg gagal: " + r.stderr[-400:])

SFX_DIR = os.path.join(os.environ.get("VIDEO_STUDIO_ROOT", os.path.dirname(os.path.abspath(__file__))), "assets", "sfx")

def sfx_list(scenes):
    """Daftar (file, waktu_mulai_detik, volume) dari field 'sfx' tiap scene.
    sfx: "nama" | {"name": "nama", "at": detik_setelah_scene_mulai (default 0.3), "volume": 0.1-2.0 (default 0.6)} | [daftar keduanya]"""
    out = []
    for sc in scenes:
        v = sc.get("sfx")
        if not v: continue
        for it in (v if isinstance(v, list) else [v])[:3]:
            if isinstance(it, str): it = {"name": it}
            if not isinstance(it, dict): continue
            name = str(it.get("name", ""))
            if not re.fullmatch(r"[a-z0-9_-]{1,60}", name): continue
            f = f"{SFX_DIR}/{name}.mp3"
            if not os.path.exists(f): print("sfx tidak ditemukan:", name, flush=True); continue
            at = max(0.0, min(num(it.get("at", 0.3), 0.3), sc["dur"] - 0.1))
            out.append((f, sc["start"] + at, max(0.1, min(2.0, num(it.get("volume", 0.6), 0.6)))))
    return out

def mix_sfx(scenes, total):
    L = sfx_list(scenes)
    if not L: return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", f"{JOB}/narration.wav"]
    for f, _, _ in L: cmd += ["-i", f]
    parts = [f"[{k+1}:a]aresample=44100,aformat=channel_layouts=stereo,volume={v:.2f},adelay={int(t*1000)}|{int(t*1000)}[x{k}]" for k, (f, t, v) in enumerate(L)]
    ins = "[0:a]" + "".join(f"[x{k}]" for k in range(len(L)))
    fc = ";".join(parts) + f";{ins}amix=inputs={len(L)+1}:duration=first:normalize=0:dropout_transition=0,alimiter=limit=0.95[a]"
    sh(cmd + ["-filter_complex", fc, "-map", "[a]", "-ar", "44100", "-ac", "2", f"{JOB}/narration_mix.wav"])
    os.replace(f"{JOB}/narration_mix.wav", f"{JOB}/narration.wav")

def prep(spec):
    scenes, t0, n = [], 0.0, len(spec["scenes"])
    for i, sc in enumerate(spec["scenes"]):
        mp3 = f"{JOB}/s{i}.mp3"
        words = None
        for attempt in range(3):
            try:
                if spec.get("pocket_voice"):
                    words = tts_pocket(sc["narration"], mp3, spec["pocket_voice"], spec.get("pocket_style") or "percakapan",
                                       num(spec.get("pocket_jeda", 1.0), 1.0))
                else:
                    words = asyncio.run(tts(sc["narration"], mp3, spec["voice"], spec["rate"]))
                break
            except Exception as e:
                if attempt == 2: raise RuntimeError(f"TTS gagal (voice {spec['voice']}): {e}")
                time.sleep(2)
        adur = b.probe(mp3)
        toks = sc["narration"].split()
        if not words: words = b.fallback_words(sc["narration"], adur)
        elif len(toks) == len(words): words = [(w[0], w[1], toks[j]) for j, w in enumerate(words)]
        theme = sc.get("theme") or THEME_ORDER[i % len(THEME_ORDER)]
        dur = LEAD+adur+TAIL
        wl = [{"s": w[0]+LEAD, "d": w[1], "text": w[2]} for w in words]
        scenes.append(dict(kind=sc.get("graphic") or "statement", num=sc.get("badge"), t1=sc.get("line1") or "", t2=sc.get("line2") or "",
                           tint=list(THEMES[theme]["tint"]), theme=theme, params=sc.get("params") or {}, text=sc["narration"],
                           start=t0, dur=dur, adur=adur, words=wl, sfx=sc.get("sfx")))
        t0 += dur
        status(stage=f"membuat suara {i+1}/{n}", progress=round(0.02+0.10*(i+1)/n, 3))
    meta = {"scenes": scenes, "total": t0}
    json.dump(meta, open(f"{JOB}/meta.json", "w"), ensure_ascii=False)
    lst = []
    for i, s in enumerate(scenes):
        wav = f"{JOB}/s{i}.wav"
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{JOB}/s{i}.mp3", "-af",
            f"adelay={int(LEAD*1000)}|{int(LEAD*1000)},apad=whole_dur={s['dur']:.3f}", "-ar", "44100", "-ac", "2", wav])
        lst.append(f"file '{wav}'")
    open(f"{JOB}/list.txt", "w").write("\n".join(lst))
    sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{JOB}/list.txt", "-c", "copy", f"{JOB}/narration.wav"])
    mix_sfx(scenes, t0)
    if spec.get("music", True):
        T = t0+1
        expr = ("0.35*sin(2*PI*110*t)+0.25*sin(2*PI*164.81*t)*(0.7+0.3*sin(2*PI*0.13*t))"
                "+0.2*sin(2*PI*220*t)+0.12*sin(2*PI*329.63*t)*(0.5+0.5*sin(2*PI*0.07*t))"
                "+0.08*sin(2*PI*440*t)*(0.5+0.5*sin(2*PI*0.21*t))")
        sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d={T:.2f}",
            "-af", "lowpass=f=1100,volume=0.6", "-ac", "2", f"{JOB}/music.wav"])
    return meta

# ------------------------------------------------------------ GRAFIK
def wrap(text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur+" "+w).strip()
        if f.getlength(t) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def num(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception: return default

def fmt(v):
    return str(int(v)) if float(v).is_integer() else f"{v:g}"

def label_at(od, P, key, y, ga, color=(255, 255, 255), size=52, lt=99):
    s = str(P.get(key, "")).strip()
    if not s: return
    f = b.font(b.FB, size)
    for i, l in enumerate(wrap(s, f, 940)[:2]):
        b.txt(od, (540, y+i*(size+12)), l, f, b.col(color, ga), 3)

def g_statement(img, od, lt, D, p, ga, sc):
    T = THEMES[sc["theme"]]; P = sc["params"]; text = str(P.get("text", "")).strip()
    b.paste_c(img, b.glow(360, T["glow"], 2.0), 540, 650, 0.55*ga)
    for i in range(7):
        a = lt*(0.25+0.07*i)+i*0.9
        b.disc(img, 540+(250+25*i)*math.cos(a), 650+(140+18*i)*math.sin(a*1.1), 7+2*(i % 3), T["accent"], 0.55*ga)
    if not text: return
    size = 84
    for size in range(84, 43, -4):
        f = b.font(b.FB, size); lines = wrap(text, f, 900)
        if len(lines) <= 6 and len(lines)*size*1.28 <= 560: break
    lines = lines[:6]; lh = size*1.28; y0 = 650-lh*(len(lines)-1)/2; k = b.ease((lt-0.2)/0.6)
    for i, l in enumerate(lines): b.txt(od, (540, y0+i*lh+(1-k)*30), l, f, b.col((255, 255, 255), k), 6)

def g_planet(img, od, lt, D, p, ga, sc):
    T = THEMES[sc["theme"]]; P = sc["params"]; cx, cy = 540, 640
    b.paste_c(img, b.glow(380, T["glow"]), cx, cy, 0.75*ga)
    ang = lt*0.9; mx, my = cx+350*math.cos(ang), cy+90*math.sin(ang); behind = math.sin(ang) < 0
    moon = P.get("moon", True)
    if moon and behind: b.disc(img, mx, my, 26, (235, 235, 255), ga)
    b.paste_c(img, b.sphere(215, T["base"], T["accent"], rot=lt*0.4, bands=max(2, min(9, int(num(P.get("bands", 5), 5))))), cx, cy, ga)
    if moon and not behind: b.disc(img, mx, my, 26, (235, 235, 255), ga)
    b.ring(img, cx, cy, 300+8*math.sin(lt*2), 3, T["accent"], 0.35*ga)
    label_at(od, P, "label", 960, b.ease((lt-1.0)/0.6), GOLD)

def g_rings(img, od, lt, D, p, ga, sc):
    T = THEMES[sc["theme"]]; P = sc["params"]; cx, cy = 540, 640
    b.paste_c(img, b.glow(300, T["glow"], 2.0), cx, cy, 0.6*ga)
    for k in range(4):
        ph = (lt*0.55+k/4.0) % 1.0
        b.ring(img, cx, cy, 50+ph*290, 6, T["accent"], (1-ph)*0.9*ga)
    b.disc(img, cx, cy, 52+5*math.sin(lt*6), (255, 255, 255), ga)
    label_at(od, P, "label", 960, b.ease((lt-0.8)/0.6), GOLD)

def g_bars(img, od, lt, D, p, ga, sc):
    T = THEMES[sc["theme"]]; P = sc["params"]; unit = str(P.get("unit", ""))
    items = []
    for it in (P.get("items") or [])[:5]:
        if isinstance(it, dict): items.append((str(it.get("label", ""))[:28], max(0.0, num(it.get("value", 0)))))
    if not items: return
    mx = max(v for _, v in items) or 1.0
    pal = [T["accent"], T["glow"], (255, 200, 70), (235, 90, 60), (120, 220, 255)]
    f = b.font(b.FB, 34)
    for i, (lab, v) in enumerate(items):
        k = b.ease((lt-(0.6+i*0.9))/1.2)
        if k <= 0: continue
        y = 470+i*120; w = max(44, 900*(v/mx)*k)
        od.rounded_rectangle([90, y-42, 90+w, y+42], 20, fill=b.col(pal[i % len(pal)], 0.92))
        b.txt(od, (114, y+2), f"{lab}: {fmt(v)}{unit}", f, b.col((255, 255, 255), min(1, k*1.6)), 3, "lm")

def g_counter(img, od, lt, D, p, ga, sc):
    T = THEMES[sc["theme"]]; P = sc["params"]; cx, cy = 540, 640
    frm, to = num(P.get("from", 0)), num(P.get("to", 100)); dec = max(0, min(4, int(num(P.get("decimals", 0)))))
    q = b.ease((lt-0.5)/max(1.0, D*0.6)); v = frm+(to-frm)*q
    s = f"{v:,.{dec}f}"
    if str(P.get("locale", "id")) == "id": s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    s = str(P.get("prefix", ""))+s+str(P.get("suffix", ""))
    b.paste_c(img, b.glow(330, T["glow"], 2.0), cx, cy, 0.5*ga)
    for k in range(3):
        ph = (lt*0.45+k/3.0) % 1.0
        b.ring(img, cx, cy, 120+ph*230, 5, T["accent"], (1-ph)*0.5*ga)
    size = 170
    while size > 56 and b.font(b.FB, size).getlength(s) > 960: size -= 6
    b.txt(od, (cx, cy), s, b.font(b.FB, size), b.col(GOLD, ga), 7)
    label_at(od, P, "label", 860, ga, (255, 255, 255), 46)

def g_list(img, od, lt, D, p, ga, sc):
    T = THEMES[sc["theme"]]; P = sc["params"]
    items = [str(x)[:60] for x in (P.get("items") or [])][:6]; n = len(items)
    b.paste_c(img, b.glow(330, T["glow"], 2.0), 540, 700, 0.35*ga)
    for i, it in enumerate(items):
        t0 = 0.5+i*max(0.5, (D*0.7)/max(n, 1)); k = b.ease((lt-t0)/0.5)
        if k <= 0: continue
        y = 430+i*120+(1-k)*40
        od.rounded_rectangle([90, y-45, 990, y+45], 28, fill=b.col(T["base"], 0.6*k), outline=b.col(T["accent"], 0.9*k), width=3)
        od.ellipse([110, y-30, 170, y+30], fill=b.col(T["accent"], k))
        b.txt(od, (140, y+2), str(i+1), b.font(b.FB, 36), b.col((30, 20, 50), k))
        size = 40; ff = b.font(b.FB, size)
        while ff.getlength(it) > 770 and size > 24: size -= 2; ff = b.font(b.FB, size)
        b.txt(od, (195, y+2), it, ff, b.col((255, 255, 255), k), 2, "lm")

def g_galaxy(img, od, lt, D, p, ga, sc):
    T = THEMES[sc["theme"]]; P = sc["params"]; cx, cy = 540, 600
    b.paste_c(img, b.glow(150, T["accent"], 1.6), cx, cy, 0.8*ga)
    r, th, cc, sz = b.GAL; a = th+lt*0.25; x = cx+r*np.cos(a); y = cy+r*np.sin(a)*0.62
    d = ImageDraw.Draw(img)
    for i in range(len(r)):
        tw = 0.6+0.4*math.sin(lt*3+i); s = sz[i]; c = tuple(int(v*tw*ga) for v in cc[i])
        d.ellipse([x[i]-s, y[i]-s, x[i]+s, y[i]+s], fill=c)
    label_at(od, P, "label1", 930, b.ease((lt-2.0)/0.8), T["accent"], 56)
    label_at(od, P, "label2", 1015, b.ease((lt-3.6)/0.8), GOLD, 56)

def g_cta(img, od, lt, D, p, ga, sc):
    T = THEMES[sc["theme"]]; P = sc["params"]; cx, cy = 540, 640
    b.paste_c(img, b.glow(330, T["glow"]), cx, cy, 0.7*ga)
    rr = 150*(1+0.06*math.sin(lt*5))
    for k in range(3):
        ph = (lt*0.6+k/3.0) % 1.0
        b.ring(img, cx, cy, rr+ph*170, 5, (255, 220, 120), (1-ph)*0.7*ga)
    b.disc(img, cx, cy, rr, (255, 200, 70), ga)
    od.rounded_rectangle([cx-70, cy-14, cx+70, cy+14], 12, fill=b.col((60, 25, 90), ga))
    od.rounded_rectangle([cx-14, cy-70, cx+14, cy+70], 12, fill=b.col((60, 25, 90), ga))
    label_at(od, P, "text", 940, b.ease((lt-1.0)/0.8), (255, 255, 255), 48)

GR = dict(statement=g_statement, planet=g_planet, rings=g_rings, bars=g_bars, counter=g_counter, list=g_list, galaxy=g_galaxy, cta=g_cta, sticker=X.g_sticker, clip3d=X.g_clip3d)

def draw_header(od):
    if not HEADER: return
    b.txt(od, (540, 96), HEADER, b.font(b.FB, 38), b.col((200, 210, 255), 0.85), 2)
    od.line([(390, 140), (690, 140)], fill=b.col((200, 210, 255), 0.4), width=3)

def draw_badge(img, od, sc, lt):
    n = sc.get("num")
    if not n: return
    n = str(n)[:3]; k = b.ease(lt/0.4)
    b.disc(img, 540, 230, 62*(0.6+0.4*k), (255, 200, 70), k)
    size = 78 if len(n) == 1 else (62 if len(n) == 2 else 48)
    b.txt(od, (540, 234), n, b.font(b.FB, size), b.col((40, 20, 70), k))

def render(fi):
    M = b.M; t = fi/FPS; si = b.scene_index(t); sc = M["scenes"][si]; lt = t-sc["start"]; D = sc["dur"]; p = lt/D
    if STYLE == "explainer":                      # background polos + stiker + subtitle miring kata per kata
        img = Image.new("RGB", (W, H), BGX); ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        GR.get(sc["kind"], g_statement)(img, od, lt, D, p, b.ease(lt/0.5), sc)
        X.draw_caption(od, sc, lt); img.paste(ov, (0, 0), ov)
        return img.convert("RGB").tobytes()
    k = b.ease(lt/0.4) if si > 0 else 1.0
    if k < 1.0: arr = (b.BG[si-1].astype(np.float32)*(1-k)+b.BG[si].astype(np.float32)*k).astype(np.uint8)
    else: arr = b.BG[si]
    img = Image.fromarray(arr); d = ImageDraw.Draw(img); b.draw_stars(d, t)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    GR.get(sc["kind"], g_statement)(img, od, lt, D, p, b.ease(lt/0.5), sc)
    draw_badge(img, od, sc, lt); draw_header(od)
    b.draw_title(od, sc, lt); b.draw_caption(od, sc, lt); b.draw_progress(od, t)
    img.paste(ov, (0, 0), ov)
    return img.convert("RGB").tobytes()

def still(t, path):
    Image.frombytes("RGB", (W, H), render(int(t*FPS))).save(path)

# ------------------------------------------------------------ MAIN
def clean_spec(spec):
    sc = spec.get("scenes") or []
    if not (1 <= len(sc) <= 12): raise ValueError("jumlah scene harus 1-12")
    spec.setdefault("voice", "id-ID-ArdiNeural"); spec.setdefault("rate", "+4%")
    if not re.fullmatch(r"[+-]\d{1,2}%", spec["rate"]): spec["rate"] = "+4%"
    if not re.fullmatch(r"[A-Za-z0-9-]{5,60}", spec["voice"]): raise ValueError("nama voice tidak valid")
    if spec.get("pocket_voice") and not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", str(spec["pocket_voice"])): raise ValueError("pocket_voice tidak valid")
    if spec.get("style") not in ("cosmic", "explainer"): spec["style"] = "cosmic"
    m = re.fullmatch(r"#?([0-9A-Fa-f]{6})", str(spec.get("bg") or ""))
    spec["bg"] = m.group(1) if m else "4664FA"
    for s in sc:
        s["narration"] = str(s.get("narration", "")).strip()[:500]
        if not s["narration"]: raise ValueError("narration tiap scene wajib diisi")
        if s.get("graphic") not in GRAPHICS_OK: s["graphic"] = "statement"
        if s.get("theme") not in THEMES: s["theme"] = None
        if "sfx" in s and not isinstance(s["sfx"], (str, dict, list)): s.pop("sfx")
    return spec

def main():
    global JOB, HEADER, STYLE, BGX
    JOB = os.path.abspath(sys.argv[1]); mode = sys.argv[2] if len(sys.argv) > 2 else "full"
    try:
        spec = clean_spec(json.load(open(f"{JOB}/spec.json")))
        HEADER = str(spec.get("channel", ""))[:30]
        STYLE = spec["style"]; BGX = tuple(int(spec["bg"][i:i+2], 16) for i in (0, 2, 4))
        status(state="running", stage="mulai", progress=0.01, error=None)
        meta = prep(spec)
        b.WORK = JOB; b.init_globals()
        if mode == "stills":
            for i, s in enumerate(b.M["scenes"]):
                still(s["start"]+min(s["dur"]-0.2, 4.0), f"{JOB}/still{i}.png"); print("still", i, s["kind"], flush=True)
            status(state="done", stage="stills", progress=1.0); return
        total = int(math.ceil(meta["total"]*FPS)); silent = f"{JOB}/silent.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", silent]
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        with Pool(2) as pool:
            for n, fr in enumerate(pool.imap(render, range(total), chunksize=6)):
                pr.stdin.write(fr)
                if n % 30 == 0: status(stage=f"render frame {n}/{total}", progress=round(0.12+0.82*n/total, 3))
        pr.stdin.close()
        if pr.wait() != 0: raise RuntimeError("encode video gagal")
        status(stage="mixing audio", progress=0.96)
        os.makedirs(OUTDIR, exist_ok=True); name = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(str(spec.get("out_name") or "video"))).strip(".-")[:80] or "video"; out = f"{OUTDIR}/{name}.mp4"; T = meta["total"]
        if spec.get("music", True):
            vol = max(0.0, min(0.4, num(spec.get("music_volume", 0.16), 0.16)))
            fc = (f"[2:a]volume={vol},afade=t=in:d=2,afade=t=out:st={max(0, T-2.5):.2f}:d=2.5[a2];[1:a][a2]amix=inputs=2:duration=first,volume=2,alimiter=limit=0.95[a]")
            sh(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", f"{JOB}/narration.wav", "-i", f"{JOB}/music.wav", "-filter_complex", fc,
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{T:.2f}", out])
        else:
            sh(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", f"{JOB}/narration.wav", "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{T:.2f}", out])
        still(min(1.6, meta["scenes"][0]["dur"]-0.3), f"{OUTDIR}/{name}.png")
        for f in os.listdir(JOB):
            if re.match(r"^s\d+\.(mp3|wav)$", f) or f in ("silent.mp4", "music.wav", "narration.wav", "list.txt"): os.remove(f"{JOB}/{f}")
        status(state="done", stage="selesai", progress=1.0, output=f"{name}.mp4", thumbnail=f"{name}.png", duration=round(T, 2), size=os.path.getsize(out))
    except Exception as e:
        traceback.print_exc()
        status(state="failed", stage="gagal", error=str(e)[:500]); sys.exit(1)

if __name__ == "__main__":
    main()
