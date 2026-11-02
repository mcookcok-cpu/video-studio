# Operasi, Troubleshooting, Keamanan, dan Pengembangan

## 1. Perintah harian

```bash
cd /home/Claude/video-studio
pm2 ls                                   # status video-mcp & video-studio
pm2 logs video-mcp --lines 50            # log MCP server
pm2 restart video-mcp                    # setelah mengubah server.mjs atau engine.py
pm2 restart ecosystem.config.cjs         # restart semua layanan proyek
curl -s localhost:2500/health            # {"ok":true,"running":<job|null>,"queued":N}
tail -f jobs/<job_id>/engine.log         # log render satu job
cat jobs/<job_id>/status.json            # status mentah satu job
```

Setelah mengubah `ecosystem.config.cjs` (port, env): `pm2 delete video-mcp video-studio && pm2 start ecosystem.config.cjs && pm2 save`.

## 2. Konfigurasi (environment)

| Variabel            | Layanan        | Default                       | Fungsi |
|---------------------|----------------|-------------------------------|--------|
| `PORT`              | keduanya       | 2500 (MCP) / 2400 (web)       | Port HTTP. |
| `PUBLIC_BASE`       | video-mcp      | IP Tailscale terdeteksi otomatis (`tailscale ip -4`) | Awalan URL pada balasan tool (`video_url`, `thumbnail_url`). Isi di `.env` hanya bila ingin memaksa host lain (mis. nama MagicDNS). |
| `VIDEO_STUDIO_ROOT` | semua + Python | `/home/Claude/video-studio`   | Akar proyek (output, jobs, engine). |
| `MCP_TOKEN`         | video-mcp      | dari `.env` (aktif)           | `/sse`, `/messages`, `/mcp` butuh `Authorization: Bearer <token>` atau `?token=`. Kosongkan di `.env` untuk menonaktifkan. |
| `JOB_RETENTION_DAYS`| video-mcp      | 14                            | Umur maksimum folder `jobs/<id>` yang sudah `done`/`failed` sebelum dihapus otomatis (0 = nonaktif). |

Variabel `MCP_TOKEN`, `JOB_RETENTION_DAYS`, dan `PUBLIC_BASE` dibaca `ecosystem.config.cjs` dari file `.env` di akar proyek. Setelah mengubah `.env`: `pm2 delete video-mcp video-studio && pm2 start ecosystem.config.cjs && pm2 save`.
Ganti token: `printf 'MCP_TOKEN=%s\n' "$(openssl rand -hex 24)"` lalu edit `.env`, restart seperti di atas, dan bagikan token baru ke semua klien.

## 3. Siklus hidup job

```
queued ──▶ running ──▶ done
   │          └──────▶ failed (error ada di status.json & engine.log)
   └─ saat pm2 restart: render yang berjalan dimatikan bersih (seluruh process group), lalu job queued/running diantrikan ulang dari awal
```

- Satu render pada satu waktu (CPU hanya 2 core); sisanya FIFO.
- Watchdog: job yang berjalan > 25 menit dihentikan (SIGKILL ke seluruh process group: python, ffmpeg, worker) dan ditandai `failed`.
- Saat server start, sisa proses engine dari server sebelumnya (mis. setelah SIGKILL) disapu supaya job tidak dirender ganda.
- Setelah sukses, berkas sementara (`s*.mp3`, `s*.wav`, `silent.mp4`, `music.wav`, `narration.wav`) dihapus; yang tersisa di `jobs/<id>/`: `spec.json`, `job.json`, `status.json`, `meta.json`, `engine.log`.

## 4. Pembersihan & backup

```bash
# lihat pemakaian
du -sh output jobs

# hapus satu video lewat MCP: tool delete_video(job_id)
# atau manual: hapus jobs/<id>/ dan output/<slug>-<id>.{mp4,png}

# folder job lama (> 14 hari) dihapus otomatis oleh server (JOB_RETENTION_DAYS); file video di output/ tetap

# backup kode + dokumentasi (tanpa node_modules & hasil video)
tar czf /home/Claude/video-studio-backup-$(date +%Y%m%d).tar.gz \
  --exclude=node_modules --exclude=output --exclude=jobs --exclude=work -C /home/Claude video-studio
```

Ukuran kira-kira: video 77 detik ≈ 17 MB.

## 5. Troubleshooting

| Gejala | Penyebab umum | Solusi |
|--------|---------------|--------|
| `state: failed`, error `TTS gagal` | Server tak bisa menjangkau layanan Edge TTS, atau nama `voice` salah | `curl -sI https://speech.platform.bing.com` (balasan HTTP 400 = jaringan OK); cek nama voice di `list_voices`; coba ulang. Engine sudah mencoba 3 kali. |
| `failed`, `ffmpeg gagal` | Disk penuh / ffmpeg terhapus | `df -h /home`, `ffmpeg -version`; lihat `jobs/<id>/engine.log`. |
| Job lama `running` tanpa kemajuan | Proses engine mati mendadak | `pm2 restart video-mcp` (job diantrikan ulang) atau `delete_video` setelah `failed`. |
| Klien tak bisa tersambung | Perangkat bukan di tailnet / ufw | Pastikan Tailscale aktif; `sudo ufw status` harus ada aturan `Anywhere on tailscale0 ALLOW`. |
| `video_url` menunjuk host salah | `PUBLIC_BASE` usang | Ubah di `ecosystem.config.cjs`, lalu restart ulang proses (lihat bagian 1). |
| Teks Mandarin/Jepang/Arab jadi kotak kosong | Font DejaVu tak punya glyph tersebut | Pakai aksara Latin, atau ganti font di `build.py` (`FB`, `FM`). |
| Subtitle tidak sinkron sempurna | Layanan TTS tidak mengirim *word boundary* | Engine otomatis memakai pembagian proporsional per panjang kata (mode fallback). |
| Port bentrok (`EADDRINUSE`) | Port terpakai layanan lain | `ss -tlnp \| grep :2500`; ganti `PORT` di `ecosystem.config.cjs`. |
| Render sangat lambat | CPU dipakai proses lain | `top`; hindari render paralel di luar antrian MCP. |

Uji menyeluruh (membuat video uji 10 detik lewat SSE dan HTTP lalu memeriksa hasilnya):

```bash
cd /home/Claude/video-studio/tests && node mcp-client-test.mjs
# hapus hasil ujinya setelah itu dengan tool delete_video atau manual (judul "Uji MCP Video")
```

## 6. Keamanan

- **Jaringan**: layanan mendengarkan `0.0.0.0`, tetapi ufw aktif: port 2400/2500 hanya terjangkau lewat antarmuka `tailscale0` (dari internet publik hanya port 22 dan 80 yang terbuka). Anggap siapa pun di tailnet dapat memakai MCP ini.
- **Autentikasi**: aktif. `MCP_TOKEN` di `.env` (chmod 600, di-ignore git); dibandingkan dengan `timingSafeEqual`. Token lewat query `?token=` bisa tercatat di log proxy/klien, jadi pakai header `Authorization` bila klien mendukung. `/health`, `/files/*`, dan web 2400 sengaja terbuka (hanya-baca, hanya dari tailnet).
- **Dependensi**: `npm audit --omit=dev` bersih (zod 4.6.7, memperbaiki GHSA-mrhx-c7xc-m3w5). Jalankan audit berkala; Python dikunci di `requirements.txt`.
- **Validasi input**: skema zod membatasi panjang/jumlah field; `voice` & `rate` divalidasi regex; `job_id` wajib 8 heksadesimal (mencegah path traversal); nama file yang dihapus divalidasi regex.
- **Eksekusi proses**: engine dijalankan lewat `spawn` dengan argumen terpisah (tanpa shell); spec dibaca sebagai JSON, tidak pernah dieksekusi.
- **Layanan eksternal**: satu-satunya koneksi keluar adalah ke layanan Microsoft Edge TTS (teks narasi dikirim ke sana untuk disintesis).
- **Sumber daya**: batas 12 scene, 3000 karakter, dan watchdog 25 menit mencegah job tak terkendali. Disk tidak dibatasi otomatis — bersihkan berkala (bagian 4).
- **Hak akses**: `/home/Claude` mode `750`, dimiliki `agentuser` (user yang sama dengan pm2 dan MCP lain di server ini).

## 7. Pengembangan

### Menambah jenis grafik baru
1. Di `engine.py`, tulis fungsi `g_namabaru(img, od, lt, D, p, ga, sc)`  
   (`img`: kanvas RGB untuk sprite/glow; `od`: ImageDraw overlay RGBA untuk teks/bentuk; `lt`: detik sejak scene mulai; `D`: durasi scene; `p`: lt/D; `ga`: fade-in 0–1; `sc`: data scene — pakai `sc["params"]` dan `THEMES[sc["theme"]]`).
2. Daftarkan di kamus `GR` dan tambahkan namanya ke `GRAPHICS_OK`.
3. Di `mcp-server/server.mjs`, tambahkan ke array `GRAPHICS` dan jelaskan di teks `GUIDE`.
4. Pratinjau cepat tanpa render penuh: `python3 engine.py jobs/<id> stills` (gambar di `jobs/<id>/still*.png`).
5. `pm2 restart video-mcp`, lalu jalankan `tests/mcp-client-test.mjs`.

Fungsi bantu di `build.py` (diimpor sebagai `b`): `b.sphere`, `b.glow`, `b.disc`, `b.ring` (sprite anti-alias), `b.paste_c`, `b.txt`, `b.col`, `b.ease`, `b.font`.

### Menambah tema warna
Tambahkan entri di `THEMES` (`engine.py`) dengan `tint`, `base`, `accent`, `glow` (RGB), tambahkan ke `THEME_ORDER` bila ingin ikut giliran otomatis, dan ke array `THEMES` di `server.mjs`.

### Mengubah format video
Resolusi/fps ada di `build.py` (`W, H, FPS`). Tata letak (judul y≈1215, subtitle y≈1560, grafik pusat y≈640) di-hardcode untuk 9:16; ubah rasio berarti menyesuaikan koordinat di `build.py` dan `engine.py`.

## 8. Riwayat

| Tanggal    | Perubahan |
|------------|-----------|
| 2026-11-02 | Video pertama "5 Fakta Gila Luar Angkasa" (`build.py`), halaman web port 2400. |
| 2026-11-02 | Engine generik (`engine.py`) + MCP server port 2500 (6 tool, SSE & Streamable HTTP, antrian job). |
| 2026-11-02 | Proyek dipindah ke `/home/Claude/video-studio`; path dikontrol `VIDEO_STUDIO_ROOT`; ditambah `ecosystem.config.cjs` dan dokumentasi. |
| 2026-11-02 | Perbaikan hasil audit: token MCP aktif (timing-safe); render dijalankan di process group dan dimatikan bersih saat restart/timeout; perbaikan race `running`; ID job dicek tabrakan; zod 3 → 4 (0 kerentanan); retensi job otomatis; poster/metadata per video di web 2400; `bands` dan `out_name` divalidasi; git + `requirements.txt`; `PUBLIC_BASE` otomatis dari Tailscale. |
