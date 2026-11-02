# Video Studio — generator video pendek + MCP server

Sistem otomatis pembuatan video vertikal **9:16 (1080×1920, 30 fps)** untuk TikTok, YouTube Shorts, dan Reels.
Dari daftar scene (teks narasi + jenis grafik), sistem menghasilkan MP4 lengkap: **suara narator, subtitle animasi
(kata yang diucapkan disorot), grafik animasi, judul, progress bar, dan musik latar**. Seluruh visual digambar lewat kode
(tanpa stock footage), sehingga bebas hak cipta.

Ada dua cara memakainya:

1. **Lewat MCP** — agent AI lain memanggil tool `create_video` (disarankan).
2. **Lewat skrip** — jalankan `engine.py` / `build.py` langsung dari terminal.

- Lokasi proyek : `/home/Claude/video-studio`
- Server        : `VM-4-222-ubuntu` (Ubuntu, 2 vCPU, 7,4 GB RAM), akses lewat Tailscale
- Dokumen lain  : [`docs/SPEC.md`](docs/SPEC.md) (referensi spec video) · [`docs/OPERASI.md`](docs/OPERASI.md) (operasi, troubleshooting, keamanan, pengembangan) · [`docs/contoh-spec.json`](docs/contoh-spec.json)

---

## 1. Layanan yang berjalan (pm2)

| Nama pm2        | Port | Fungsi                                                                 |
|-----------------|------|------------------------------------------------------------------------|
| `video-mcp`     | 2500 | MCP server (SSE + Streamable HTTP), antrian render, dan penyaji file `/files` |
| `video-studio`  | 2400 | Halaman web pemutar video + tombol download + metadata (judul/hashtag)  |

Konfigurasi ada di `ecosystem.config.cjs`.

```bash
cd /home/Claude/video-studio
pm2 start ecosystem.config.cjs && pm2 save   # jalankan / daftarkan
pm2 ls                                       # status
pm2 logs video-mcp                           # log MCP
pm2 restart video-mcp                        # restart setelah ubah kode
```

## 2. Menyambungkan agent ke MCP

Semua agent harus berada di **tailnet Tailscale** yang sama dengan server.

| Transport                 | URL                                  |
|---------------------------|--------------------------------------|
| SSE (legacy)              | `http://100.106.213.94:2500/sse`     |
| Streamable HTTP           | `http://100.106.213.94:2500/mcp`     |
| Nama MagicDNS (alternatif)| `http://vm-4-222-ubuntu.kiko-arcturus.ts.net:2500/...` |
| Health check              | `http://100.106.213.94:2500/health`  |

Contoh konfigurasi klien:

```jsonc
// Klien yang mendukung URL MCP langsung (mis. Claude Desktop via config / klien generik)
{ "mcpServers": { "video-studio": { "url": "http://100.106.213.94:2500/sse?token=<token>" } } }
```

```bash
# Claude Code
claude mcp add --transport sse  video-studio http://100.106.213.94:2500/sse
claude mcp add --transport http video-studio http://100.106.213.94:2500/mcp
```

**Autentikasi aktif.** Token ada di `.env` (`MCP_TOKEN`, chmod 600, tidak masuk git). `/sse`, `/messages`, dan `/mcp` menolak (401) permintaan tanpa token.
Kirim header `Authorization: Bearer <token>` (disarankan), atau `?token=<token>` pada URL bila klien tidak bisa mengirim header.
`/health` dan `/files/*` tetap terbuka (hanya bisa dijangkau dari tailnet) supaya `video_url` bisa dibuka langsung.

```bash
claude mcp add --transport http video-studio http://100.106.213.94:2500/mcp --header "Authorization: Bearer <token>"
claude mcp add --transport sse  video-studio "http://100.106.213.94:2500/sse?token=<token>"
```

## 3. Tool MCP

| Tool               | Fungsi                                                                                      |
|--------------------|---------------------------------------------------------------------------------------------|
| `get_video_guide`  | Panduan lengkap (jenis grafik, parameter, batasan, contoh). **Baca dulu sebelum membuat video.** |
| `list_voices`      | Daftar suara narator yang disarankan.                                                       |
| `create_video`     | Membuat video dari spec; berjalan di latar belakang, mengembalikan `job_id`.                |
| `get_video_status` | Status job. Dengan `wait_seconds` (maks 45) ia menunggu sampai `done`/`failed`.             |
| `list_videos`      | Daftar job terbaru + URL hasil (`limit` 1–50, default 10).                                  |
| `delete_video`     | Menghapus MP4, thumbnail, dan folder job (tidak bisa saat job sedang `running`).            |

### Alur penggunaan

```
get_video_guide  →  create_video(spec)  →  job_id
                      │
                      └─ get_video_status(job_id, wait_seconds=40)  ← ulangi sampai state = "done"
                                                 │
                                                 └─ video_url, thumbnail_url, duration_seconds
```

Contoh panggilan `create_video` (ringkas):

```json
{
  "title": "3 Kebiasaan Pagi Orang Produktif",
  "channel": "TIPS HARIAN",
  "scenes": [
    { "graphic": "statement", "line1": "RAHASIA PAGI", "line2": "ORANG PRODUKTIF",
      "narration": "Mau hari-harimu lebih produktif? Coba 3 kebiasaan pagi ini.",
      "params": { "text": "3 Kebiasaan Pagi yang Mengubah Harimu" } },
    { "graphic": "cta", "line1": "FOLLOW UNTUK", "line2": "TIPS LAINNYA", "theme": "pink",
      "narration": "Tulis di komentar kebiasaan mana yang mau kamu coba, dan follow ya!",
      "params": { "text": "Follow untuk tips lainnya" } }
  ]
}
```

Balasan `get_video_status` saat selesai:

```json
{
  "job_id": "636a125c", "title": "…", "state": "done", "progress_percent": 100, "stage": "selesai",
  "video_url": "http://100.106.213.94:2500/files/judul-video-636a125c.mp4",
  "thumbnail_url": "http://100.106.213.94:2500/files/judul-video-636a125c.png",
  "duration_seconds": 10.18, "size_bytes": 2112102,
  "local_path": "/home/Claude/video-studio/output/judul-video-636a125c.mp4"
}
```

Spesifikasi lengkap field scene dan parameter tiap grafik ada di **[docs/SPEC.md](docs/SPEC.md)**.

## 4. Batasan

| Hal                      | Batas                                                                    |
|--------------------------|--------------------------------------------------------------------------|
| Jumlah scene             | 1–12                                                                     |
| Narasi per scene         | maks 500 karakter                                                        |
| Total narasi             | maks 3000 karakter (≈ 3 menit video)                                     |
| Judul `line1`/`line2`    | maks 24 karakter                                                         |
| Kecepatan render         | ≈ 2,5 detik per 1 detik video (video 60 dtk ≈ 3 menit)                   |
| Antrian                  | 1 render pada satu waktu; job lain mengantri (FIFO)                      |
| Retensi job              | folder `jobs/<id>` selesai/gagal dihapus otomatis setelah 14 hari (`JOB_RETENTION_DAYS`); video di `output/` tidak disentuh |
| Batas waktu per job      | 25 menit (lalu dihentikan paksa dan berstatus `failed`)                  |
| Aksara teks              | Latin, Yunani, Sirilik (font DejaVu). Mandarin/Jepang/Arab tidak tampil  |

## 5. Struktur folder

```
/home/Claude/video-studio
├── README.md                 dokumen ini
├── ecosystem.config.cjs      konfigurasi pm2 (2 layanan); membaca rahasia dari .env
├── .env                      MCP_TOKEN, JOB_RETENTION_DAYS (chmod 600, tidak di-commit)
├── requirements.txt          dependensi Python (edge-tts, Pillow, numpy)
├── engine.py                 engine generik: spec.json → MP4 (dipanggil oleh MCP)
├── build.py                  pustaka render (font, sphere, glow, caption, dll) + generator video "5 Fakta Gila Luar Angkasa"
├── mcp-server/
│   ├── server.mjs            MCP server (tools, antrian job, SSE + Streamable HTTP, /files)
│   └── node_modules/         @modelcontextprotocol/sdk 1.32.2, zod 3, express 4
├── server/
│   └── server.js             halaman web pemutar/download (port 2400)
├── jobs/<job_id>/            satu folder per job: spec.json, job.json, status.json, meta.json, engine.log
├── output/                   hasil akhir: <slug>-<job_id>.mp4 + .png (juga video "5 Fakta…", thumbnail, metadata.txt)
├── work/                     area kerja skrip manual build.py
├── tests/mcp-client-test.mjs uji end-to-end lewat klien MCP asli (SSE + HTTP)
└── docs/                     SPEC.md, OPERASI.md, contoh-spec.json
```

## 6. Cara kerja (singkat)

```
agent ──MCP──▶ server.mjs ──tulis spec.json──▶ antrian ──spawn──▶ engine.py <job_dir>
                                                                   │
        1. edge-tts: narasi → mp3 per scene + timestamp tiap kata  │
        2. ffmpeg: gabung narasi (pad per scene) + musik ambient   │
        3. PIL + numpy: gambar tiap frame (2 proses paralel)       │
        4. ffmpeg: encode H.264 + mix audio (AAC 192k) → output/   │
        5. status.json diperbarui → agent membaca via get_video_status
```

- Durasi tiap scene = lama suara narasi + 0,3 dtk jeda awal + 0,7 dtk jeda akhir.
- Subtitle dikelompokkan 2–4 kata; kata yang sedang diucapkan berwarna kuning (berdasarkan *word boundary* dari TTS).
- Musik latar disintesis oleh ffmpeg (`aevalsrc`), jadi tanpa file audio berhak cipta.

## 7. Dependensi

| Komponen        | Versi / lokasi                                                         |
|-----------------|-------------------------------------------------------------------------|
| ffmpeg          | 6.1.1 (`/usr/bin/ffmpeg`)                                               |
| Python          | **`/usr/bin/python3` (3.12)** — bukan python3 milik venv hermes        |
| Pillow / numpy  | 10.2.0 / 1.26.4                                                         |
| edge-tts        | 7.3.1 (terpasang di `~/.local/lib/python3.12`); butuh internet ke layanan Microsoft Edge TTS |
| Font            | DejaVu Sans Bold & Mono Bold (`/usr/share/fonts/truetype/dejavu`)       |
| Node.js         | 22.x; pm2 terpasang global                                              |

## 8. Pembuatan manual tanpa MCP

```bash
cd /home/Claude/video-studio

# a) dari spec JSON (sama seperti yang dipakai MCP)
mkdir -p jobs/manual && cp docs/contoh-spec.json jobs/manual/spec.json
/usr/bin/python3 engine.py jobs/manual            # hasil: output/<out_name>.mp4
/usr/bin/python3 engine.py jobs/manual stills     # hanya render 1 gambar per scene (cek tata letak cepat)

# b) video "5 Fakta Gila Luar Angkasa" (skrip asli)
/usr/bin/python3 build.py prep    # TTS + audio
/usr/bin/python3 build.py test    # contoh frame per scene ke work/test*.png
/usr/bin/python3 build.py full    # render lengkap → output/5-fakta-gila-luar-angkasa.mp4
```

> Nama file hasil `engine.py` diambil dari `out_name` di `spec.json` (tanpa ekstensi). Bila kosong, dipakai `video`.
