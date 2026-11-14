#!/usr/bin/env python3
"""Unduh sound effect dari myinstants.com ke assets/sfx/ + catat di assets/sfx/index.json.
Pakai: python3 tools/ambil_myinstants.py <url_halaman> [halaman_awal] [halaman_akhir]
Contoh: python3 tools/ambil_myinstants.py https://www.myinstants.com/en/index/id/ 1 1"""
import sys, os, re, json, time, html, urllib.request, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "assets", "sfx"); IDX = os.path.join(DIR, "index.json")
UA = {"User-Agent": "Mozilla/5.0"}
os.makedirs(DIR, exist_ok=True)

def get(url, binary=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        d = r.read(); return d if binary else d.decode("utf-8", "replace")

def parse(page):
    out = []
    for m in re.finditer(r"play\('(/media/sounds/[^']+\.mp3)'[^)]*'([^']+)'\)", page):
        path, slug = m.group(1), m.group(2)
        t = re.search(r'href="(/en/instant/' + re.escape(slug) + r'/)"[^>]*>([^<]+)<', page)
        out.append(dict(path=path, slug=slug, title=html.unescape(t.group(2)).strip() if t else slug,
                        page_url="https://www.myinstants.com" + (t.group(1) if t else f"/en/instant/{slug}/")))
    return out

def main():
    base = sys.argv[1]; p0 = int(sys.argv[2]) if len(sys.argv) > 2 else 1; p1 = int(sys.argv[3]) if len(sys.argv) > 3 else p0
    idx = json.load(open(IDX)) if os.path.exists(IDX) else {}
    baru = 0
    for p in range(p0, p1 + 1):
        url = base if p == 1 else f"{base}?page={p}"
        items = parse(get(url)); print(f"halaman {p}: {len(items)} suara", flush=True)
        for it in items:
            name = re.sub(r"[^a-z0-9_-]+", "-", os.path.splitext(os.path.basename(it["path"]))[0].lower()).strip("-")[:60] or it["slug"]
            fn = f"{name}.mp3"; dst = os.path.join(DIR, fn)
            if name in idx and os.path.exists(dst): continue
            try:
                data = get("https://www.myinstants.com" + urllib.parse.quote(it["path"]), True)
                if len(data) < 500: raise ValueError("file terlalu kecil")
                open(dst, "wb").write(data)
                idx[name] = dict(file=fn, title=it["title"], source=it["page_url"], bytes=len(data)); baru += 1
                print("  ok", fn, len(data), flush=True)
            except Exception as e:
                print("  GAGAL", it["slug"], e, flush=True)
            time.sleep(0.4)
    json.dump(idx, open(IDX, "w"), ensure_ascii=False, indent=1)
    print(f"selesai: {baru} baru, total {len(idx)}")

main()
