# Referensi Spec Video

Spec adalah objek JSON yang dikirim ke tool `create_video` (atau disimpan sebagai `jobs/<id>/spec.json` untuk `engine.py`).

## 1. Level video

| Field          | Tipe    | Wajib | Default              | Keterangan |
|----------------|---------|-------|----------------------|------------|
| `title`        | string  | ya    | –                    | Judul video (2–80 karakter). Dipakai untuk nama file. |
| `scenes`       | array   | ya    | –                    | 1–12 scene berurutan. |
| `voice`        | string  | tidak | `id-ID-ArdiNeural`   | Nama suara Edge TTS (lihat bagian 5). |
| `rate`         | string  | tidak | `+4%`                | Kecepatan bicara, format `+N%` / `-N%` (mis. `-10%`). |
| `channel`      | string  | tidak | kosong               | Teks kecil di header video (maks 30 karakter), mis. `FAKTA ANGKASA`. Kosong = tanpa header. |
| `music`        | boolean | tidak | `true`               | Musik latar ambient sintetis. |
| `music_volume` | number  | tidak | `0.16`               | 0–0.4. |
| `out_name`     | string  | –     | `video`              | **Hanya untuk `engine.py` manual.** Lewat MCP diisi otomatis `<slug-judul>-<job_id>`. |

## 2. Level scene

| Field       | Tipe   | Wajib | Keterangan |
|-------------|--------|-------|------------|
| `narration` | string | ya    | Teks yang diucapkan (maks 500 karakter). Tulis angka dengan digit (`243 hari`); TTS membacanya dengan benar dan subtitle jadi ringkas. |
| `line1`     | string | tidak | Judul baris 1, putih (maks 24 karakter). Huruf kapital paling serasi. |
| `line2`     | string | tidak | Judul baris 2, emas (maks 24 karakter). |
| `badge`     | string | tidak | Lencana bulat emas di atas grafik (maks 3 karakter), mis. nomor `"1"`. |
| `graphic`   | enum   | tidak | `statement` (default) · `planet` · `rings` · `bars` · `counter` · `list` · `galaxy` · `cta`. Nilai tak dikenal → `statement`. |
| `theme`     | enum   | tidak | `orange` `blue` `purple` `teal` `pink` `green` `red` `gold`. Kosong → bergilir otomatis per scene. |
| `params`    | object | tidak | Parameter khusus grafik (bagian 3). |

Durasi scene = durasi suara + 0,3 dtk (jeda awal) + 0,7 dtk (jeda akhir). Perkiraan: ±13 karakter narasi per detik.

## 3. Grafik dan `params`

Semua teks `params` ditampilkan apa adanya; teks panjang dibungkus otomatis dan ukuran font mengecil bila perlu.

### `statement` — kalimat besar
Pernyataan/kutipan di tengah layar dengan orb mengambang.
| Param  | Keterangan |
|--------|------------|
| `text` | Kalimat (disarankan ≤ 120 karakter; maks 6 baris). |

### `planet` — planet berputar + bulan
| Param   | Default | Keterangan |
|---------|---------|------------|
| `label` | –       | Teks di bawah planet (maks 2 baris), muncul perlahan. |
| `bands` | `5`     | Jumlah pita tekstur planet (2–9). |
| `moon`  | `true`  | Tampilkan bulan yang mengorbit. |

### `rings` — gelombang memancar
Cocok untuk sinyal, suara, energi, pengaruh. Param: `label`.

### `bars` — bar perbandingan
| Param   | Keterangan |
|---------|------------|
| `items` | Array 1–5 objek `{"label": "Tidur", "value": 8}`; bar muncul bergiliran, panjang proporsional terhadap nilai terbesar. |
| `unit`  | Akhiran angka, mis. `" jam"`, `"%"`. |

### `counter` — angka menghitung naik
| Param      | Default | Keterangan |
|------------|---------|------------|
| `from`     | `0`     | Nilai awal. |
| `to`       | `100`   | Nilai akhir. |
| `decimals` | `0`     | Angka desimal (0–4). |
| `prefix` / `suffix` | kosong | Mis. `"Rp "` / `" km"`. |
| `label`    | –       | Keterangan di bawah angka (maks 2 baris). |
| `locale`   | `id`    | `id` → `1.234,5`; `en` → `1,234.5`. |

### `list` — daftar poin
| Param   | Keterangan |
|---------|------------|
| `items` | Array 1–6 string (maks 60 karakter); muncul bergiliran sepanjang scene. |

### `galaxy` — galaksi spiral berputar
Param: `label1` (muncul ±2 dtk), `label2` (muncul ±3,6 dtk). Tiap teks maks 2 baris.

### `cta` — ajakan follow/komentar
Tombol "+" berdenyut. Param: `text` (teks di bawah tombol).

## 4. Tema warna

| Tema     | Kesan            | Tema    | Kesan          |
|----------|------------------|---------|----------------|
| `orange` | hangat, energi   | `pink`  | ceria, hangat  |
| `blue`   | tenang, teknologi| `green` | alam, uang     |
| `purple` | misteri, kosmik  | `red`   | tegas, peringatan |
| `teal`   | segar, air       | `gold`  | prestise, juara |

## 5. Suara (Edge TTS)

Panggil `list_voices` untuk daftar saran. Nama lain yang valid di Edge TTS juga bisa dipakai di `voice`.

| Voice                 | Bahasa            | Gender |
|-----------------------|-------------------|--------|
| `id-ID-ArdiNeural`    | Indonesia         | pria   |
| `id-ID-GadisNeural`   | Indonesia         | wanita |
| `en-US-GuyNeural` / `en-US-JennyNeural` / `en-US-AriaNeural` | Inggris (AS) | pria / wanita / wanita |
| `en-GB-RyanNeural` / `en-GB-SoniaNeural` | Inggris (UK) | pria / wanita |
| `ms-MY-OsmanNeural` / `ms-MY-YasminNeural` | Melayu | pria / wanita |
| `es-ES-AlvaroNeural`, `fr-FR-HenriNeural`, `de-DE-ConradNeural`, `pt-BR-AntonioNeural` | Spanyol, Prancis, Jerman, Portugis | pria |

Teks (judul/subtitle) hanya mendukung aksara Latin, Yunani, dan Sirilik.

## 6. Resep struktur video yang efektif

1. **Scene 1 – hook**: pertanyaan/klaim mengejutkan dalam ≤ 8 detik (`statement`).
2. **Scene 2…N – isi**: satu gagasan per scene, selang-seling jenis grafik (`list`, `bars`, `counter`, `planet`…).
3. **Scene terakhir – ajakan**: `cta` untuk komentar/follow.
4. Total 45–75 detik (≈ 600–1000 karakter narasi) paling aman untuk Shorts/TikTok.
5. Hindari narasi yang diawali kata sambung panjang; kalimat pendek membuat subtitle lebih rapi.

## 7. Struktur `status.json`

```json
{ "state": "queued|running|done|failed", "stage": "render frame 300/900", "progress": 0.43,
  "error": null, "output": "judul-1a2b3c4d.mp4", "thumbnail": "judul-1a2b3c4d.png",
  "duration": 61.4, "size": 9120334, "updated": 1793581803.6 }
```
Tahap `progress`: 0–0,12 pembuatan suara · 0,12–0,94 render frame · 0,96 mixing audio · 1,0 selesai.
