import express from "express";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

const PORT = Number(process.env.PORT || 2500);
const BASE = (process.env.PUBLIC_BASE || `http://100.106.213.94:${PORT}`).replace(/\/$/, "");
const TOKEN = process.env.MCP_TOKEN || "";
const JOB_RETENTION_DAYS = Number(process.env.JOB_RETENTION_DAYS || 14); // folder job selesai/gagal lebih tua dari ini dihapus (video di output/ tidak disentuh)
const ROOT = process.env.VIDEO_STUDIO_ROOT || "/home/Claude/video-studio";
const JOBS = path.join(ROOT, "jobs");
const OUT = path.join(ROOT, "output");
const ENGINE = path.join(ROOT, "engine.py");
const PY = "/usr/bin/python3";
fs.mkdirSync(JOBS, { recursive: true });
fs.mkdirSync(OUT, { recursive: true });

const GRAPHICS = ["statement", "planet", "rings", "bars", "counter", "list", "galaxy", "cta", "sticker", "clip3d"];
const ICONS = ["fan", "wind", "drop", "skin", "skin_evap", "thermometer", "bolt", "sun", "check", "cross", "heart", "lungs", "brain", "glass", "moon", "apple"];
const THEMES = ["orange", "blue", "purple", "teal", "pink", "green", "red", "gold"];
const ID_RE = /^[a-f0-9]{8}$/;

// ---------------------------------------------------------------- job store
const jdir = (id) => path.join(JOBS, id);
const readJson = (p, d = null) => { try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return d; } };
function writeStatus(id, patch) {
  const p = path.join(jdir(id), "status.json");
  const s = Object.assign(readJson(p, {}), patch, { updated: Date.now() / 1000 });
  fs.writeFileSync(p + ".tmp", JSON.stringify(s)); fs.renameSync(p + ".tmp", p);
}
function jobView(id) {
  const info = readJson(path.join(jdir(id), "job.json"));
  if (!info) return null;
  const st = readJson(path.join(jdir(id), "status.json"), { state: "queued", progress: 0 });
  const v = { job_id: id, title: info.title, state: st.state, progress_percent: Math.round((st.progress || 0) * 100), stage: st.stage || "", created_at: info.created_at };
  const qi = queue.indexOf(id);
  if (qi >= 0) v.queue_position = qi + 1;
  if (st.state === "done" && st.output) {
    v.video_url = `${BASE}/files/${st.output}`;
    v.thumbnail_url = `${BASE}/files/${st.thumbnail}`;
    v.duration_seconds = st.duration; v.size_bytes = st.size;
    v.local_path = path.join(OUT, st.output);
  }
  if (st.state === "failed") v.error = st.error;
  return v;
}

const queue = []; let running = null; let runningProc = null;
// Matikan satu pohon proses (python + ffmpeg + worker Pool) lewat process group
function killTree(p, sig = "SIGKILL") {
  if (!p || !p.pid) return;
  try { process.kill(-p.pid, sig); } catch { try { p.kill(sig); } catch {} }
}
function runNext() {
  if (running || queue.length === 0) return;
  const id = queue.shift(); running = id;
  writeStatus(id, { state: "running", stage: "mulai", progress: 0.01 });
  const log = fs.openSync(path.join(jdir(id), "engine.log"), "a");
  let finished = false, killer = null;
  const finish = (code, err) => {           // idempotent: 'error' dan 'close' bisa datang keduanya
    if (finished) return; finished = true;
    clearTimeout(killer); try { fs.closeSync(log); } catch {}
    const st = readJson(path.join(jdir(id), "status.json"), {});
    if (err) writeStatus(id, { state: "failed", error: String(err) });
    else if (st.state !== "done") writeStatus(id, { state: "failed", error: st.error || `engine berhenti (kode ${code})` });
    if (running === id) { running = null; runningProc = null; }   // jangan menimpa job lain yang sudah mulai
    runNext();
  };
  const p = spawn(PY, [ENGINE, jdir(id)], { stdio: ["ignore", log, log], detached: true });  // detached = process group baru
  runningProc = p;
  killer = setTimeout(() => killTree(p), 25 * 60 * 1000);
  p.on("close", (code) => finish(code));
  p.on("error", (e) => finish(null, e));
}
// sapu engine sisa dari proses server sebelumnya (mis. server di-SIGKILL), supaya job tidak dirender ganda
try { spawnSync("pkill", ["-9", "-f", `${ENGINE} ${JOBS}/[a-f0-9]{8}$`]); } catch {}
// pulihkan antrian saat restart
for (const id of fs.readdirSync(JOBS).filter((x) => ID_RE.test(x)).sort()) {
  const st = readJson(path.join(jdir(id), "status.json"), null);
  if (st && (st.state === "queued" || st.state === "running")) { writeStatus(id, { state: "queued", stage: "antri ulang", progress: 0 }); queue.push(id); }
}
setTimeout(runNext, 500);

const slugify = (s) => s.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "video";
const text = (obj) => ({ content: [{ type: "text", text: typeof obj === "string" ? obj : JSON.stringify(obj, null, 2) }] });
const fail = (msg) => ({ isError: true, content: [{ type: "text", text: msg }] });

// ---------------------------------------------------------------- panduan
const GUIDE = `PANDUAN create_video (video vertikal 9:16, 1080x1920, 30fps, cocok TikTok / YouTube Shorts / Reels)

ALUR: create_video -> dapat job_id -> get_video_status(job_id, wait_seconds=40) diulang sampai state "done" -> pakai video_url.
Estimasi waktu: sekitar 2,5 detik render per 1 detik video (video 60 detik ~ 3 menit). Antrian diproses satu per satu.

STRUKTUR: video = daftar scene. Tiap scene = satu narasi suara + satu grafik animasi + judul 2 baris + subtitle otomatis (kata yang diucapkan disorot).
Durasi scene mengikuti panjang narasi (sekitar 13 karakter per detik). Total narasi maks 3000 karakter (~3 menit), maks 12 scene.

FIELD TIAP SCENE
- narration (wajib, maks 500 karakter): teks yang diucapkan. Tulis angka dengan digit ("243 hari"), bukan huruf.
- line1, line2 (opsional, maks 24 karakter, HURUF KAPITAL lebih bagus): judul besar di bawah grafik. line2 berwarna emas.
- badge (opsional, maks 3 karakter): lingkaran bernomor di atas, mis. "1".
- graphic (default "statement"): salah satu dari
    statement : kalimat besar di tengah.      params: {text}
    planet    : planet berputar + bulan.       params: {label, bands(2-9), moon(true/false)}
    rings     : cincin gelombang memancar.     params: {label}
    bars      : bar perbandingan beranimasi.   params: {items:[{label,value}] (maks 5), unit}
    counter   : angka besar menghitung naik.   params: {from, to, decimals, prefix, suffix, label, locale("id"=1.234,5 | "en"=1,234.5)}
    list      : daftar poin muncul bergiliran. params: {items:[string] (maks 6, maks 60 karakter)}
    galaxy    : galaksi spiral berputar.       params: {label1, label2}
    cta       : tombol "+" follow berdenyut.   params: {text}
    sticker   : (untuk style "explainer") 1-3 stiker ilustrasi beranimasi dengan outline putih.   params: {icons:[nama,...] (maks 3)}
                nama ikon: ${ICONS.join(" | ")}
    clip3d    : (untuk style "explainer") klip animasi 3D hasil render (assets/clips/<nama>), tampil sebagai stiker.   params: {clip:"nama_klip"}
- theme (opsional): ${THEMES.join(" | ")}. Kalau kosong, warna berganti otomatis tiap scene.

STYLE VIDEO (opsional): "cosmic" (default: latar gelap berbintang, judul + grafik) atau "explainer" (latar polos berwarna, stiker ilustrasi, subtitle miring tebal kata per kata, tanpa judul/header/progress; cocok untuk penjelasan singkat ala TikTok). Untuk explainer pakai graphic "sticker" di tiap scene, narasi pendek 1-2 kalimat per scene; line1/line2/badge/theme diabaikan. Warna latar: field bg (hex, default #4664FA).

OPSI VIDEO: title (wajib), voice (default id-ID-ArdiNeural, lihat list_voices), rate (mis. "+4%", "-10%"), channel (teks kecil di header, mis. "FAKTA ANGKASA"),
music (true/false, musik latar ambient sintetis bebas hak cipta), music_volume (0-0.4, default 0.16).

CATATAN: font mendukung aksara Latin/Yunani/Sirilik. Bahasa dengan aksara lain (Mandarin, Jepang, Arab, dll) tidak akan tampil di subtitle/judul.
RESEP: hook di scene 1 -> 3-5 scene isi (bergantian jenis grafik) -> scene terakhir graphic "cta" ajak komen/follow.

CONTOH:
{
  "title": "3 Kebiasaan Pagi Orang Produktif",
  "channel": "TIPS HARIAN",
  "scenes": [
    {"graphic":"statement","line1":"RAHASIA PAGI","line2":"ORANG PRODUKTIF","narration":"Mau hari-harimu lebih produktif? Coba 3 kebiasaan pagi ini.","params":{"text":"3 Kebiasaan Pagi yang Mengubah Harimu"}},
    {"graphic":"list","badge":"1","line1":"MULAI RINGAN","line2":"3 LANGKAH","theme":"teal","narration":"Pertama, bangun lebih awal. Kedua, tulis tiga prioritas. Ketiga, kerjakan yang tersulit lebih dulu.","params":{"items":["Bangun lebih awal","Tulis 3 prioritas","Kerjakan yang tersulit dulu"]}},
    {"graphic":"counter","badge":"2","line1":"EFEKNYA NYATA","line2":"SETIAP HARI","theme":"gold","narration":"Dalam 30 hari, kamu bisa menghemat lebih dari 20 jam waktu terbuang.","params":{"from":0,"to":20,"suffix":" jam+","label":"waktu terhemat dalam 30 hari"}},
    {"graphic":"cta","line1":"FOLLOW UNTUK","line2":"TIPS LAINNYA","theme":"pink","narration":"Kebiasaan mana yang mau kamu coba duluan? Tulis di komentar dan follow ya!","params":{"text":"Follow untuk tips lainnya"}}
  ]
}`;

const VOICES = [
  { voice: "id-ID-ArdiNeural", language: "Indonesia", gender: "pria" },
  { voice: "id-ID-GadisNeural", language: "Indonesia", gender: "wanita" },
  { voice: "en-US-GuyNeural", language: "Inggris (AS)", gender: "pria" },
  { voice: "en-US-JennyNeural", language: "Inggris (AS)", gender: "wanita" },
  { voice: "en-US-AriaNeural", language: "Inggris (AS)", gender: "wanita" },
  { voice: "en-GB-RyanNeural", language: "Inggris (UK)", gender: "pria" },
  { voice: "en-GB-SoniaNeural", language: "Inggris (UK)", gender: "wanita" },
  { voice: "ms-MY-OsmanNeural", language: "Melayu", gender: "pria" },
  { voice: "ms-MY-YasminNeural", language: "Melayu", gender: "wanita" },
  { voice: "es-ES-AlvaroNeural", language: "Spanyol", gender: "pria" },
  { voice: "fr-FR-HenriNeural", language: "Prancis", gender: "pria" },
  { voice: "de-DE-ConradNeural", language: "Jerman", gender: "pria" },
  { voice: "pt-BR-AntonioNeural", language: "Portugis (Brasil)", gender: "pria" },
];

// ---------------------------------------------------------------- MCP server
const SceneSchema = z.object({
  narration: z.string().min(5).max(500).describe("Teks yang diucapkan di scene ini (maks 500 karakter)"),
  line1: z.string().max(24).optional().describe("Judul baris 1 (maks 24 karakter, putih)"),
  line2: z.string().max(24).optional().describe("Judul baris 2 (maks 24 karakter, emas)"),
  badge: z.string().max(3).optional().describe("Teks lencana bulat di atas, mis. nomor '1'"),
  graphic: z.enum(GRAPHICS).optional().describe("Jenis grafik animasi (default statement). Lihat get_video_guide"),
  theme: z.enum(THEMES).optional().describe("Tema warna scene"),
  params: z.record(z.string(), z.any()).optional().describe("Parameter grafik, tergantung 'graphic' (lihat get_video_guide)"),
});

function buildServer() {
  const server = new McpServer({ name: "video-studio", version: "1.0.0" });

  server.tool("get_video_guide",
    "Baca panduan lengkap membuat video: jenis grafik, parameter, batasan, dan contoh spec JSON. Panggil ini dulu sebelum create_video.",
    {}, async () => text(GUIDE));

  server.tool("list_voices", "Daftar suara narator (Microsoft Edge TTS) yang bisa dipakai di create_video.", {}, async () => text(VOICES));

  server.tool("create_video",
    "Buat video pendek vertikal 9:16 (TikTok/YouTube Shorts/Reels) lengkap dengan narasi suara, subtitle animasi, grafik, dan musik latar dari daftar scene. Berjalan di latar belakang: balasan berisi job_id, lalu pantau dengan get_video_status. Baca get_video_guide dulu.",
    {
      title: z.string().min(2).max(80).describe("Judul video"),
      scenes: z.array(SceneSchema).min(1).max(12).describe("Daftar scene berurutan (1-12)"),
      voice: z.string().regex(/^[A-Za-z0-9-]{5,60}$/).optional().describe("Nama suara, default id-ID-ArdiNeural"),
      rate: z.string().regex(/^[+-]\d{1,2}%$/).optional().describe("Kecepatan bicara, mis. '+4%' atau '-10%'"),
      style: z.enum(["cosmic", "explainer"]).optional().describe("Gaya video: cosmic (default) atau explainer (latar polos + stiker + subtitle kata per kata)"),
      bg: z.string().regex(/^#?[0-9A-Fa-f]{6}$/).optional().describe("Warna latar hex untuk style explainer, mis. #4664FA"),
      channel: z.string().max(30).optional().describe("Teks kecil di header video, mis. 'FAKTA ANGKASA'"),
      music: z.boolean().optional().describe("Musik latar (default true)"),
      music_volume: z.number().min(0).max(0.4).optional().describe("Volume musik 0-0.4 (default 0.16)"),
    },
    async (a) => {
      const total = a.scenes.reduce((n, s) => n + s.narration.length, 0);
      if (total > 3000) return fail(`Total narasi ${total} karakter melebihi batas 3000. Persingkat atau kurangi scene.`);
      let id; do { id = crypto.randomBytes(4).toString("hex"); } while (fs.existsSync(jdir(id)));
      const name = `${slugify(a.title)}-${id}`;
      fs.mkdirSync(jdir(id), { recursive: true });
      const spec = { title: a.title, scenes: a.scenes, voice: a.voice, rate: a.rate, channel: a.channel || "", style: a.style, bg: a.bg, music: a.music !== false, music_volume: a.music_volume, out_name: name };
      fs.writeFileSync(path.join(jdir(id), "spec.json"), JSON.stringify(spec, null, 1));
      fs.writeFileSync(path.join(jdir(id), "job.json"), JSON.stringify({ id, title: a.title, created_at: new Date().toISOString() }));
      writeStatus(id, { state: "queued", stage: "antri", progress: 0 });
      queue.push(id); runNext();
      const estSec = Math.round((total / 13 + a.scenes.length) * 2.6 + 15);
      const cur = jobView(id); return text({ job_id: id, state: cur.state, queue_position: cur.queue_position || 0, perkiraan_selesai_detik: estSec * (queue.length + (running ? 1 : 0) || 1),
        langkah_berikut: `Panggil get_video_status dengan job_id "${id}" dan wait_seconds=40 berulang sampai state = done.`, video_url_nanti: `${BASE}/files/${name}.mp4` });
    });

  server.tool("get_video_status",
    "Cek status pembuatan video (queued/running/done/failed). Jika wait_seconds diisi, menunggu sampai selesai atau waktu habis (maks 45 detik). Saat done, balasan berisi video_url dan thumbnail_url.",
    { job_id: z.string().regex(ID_RE).describe("job_id dari create_video"), wait_seconds: z.number().min(0).max(45).optional() },
    async ({ job_id, wait_seconds }) => {
      if (!jobView(job_id)) return fail("job_id tidak ditemukan");
      const until = Date.now() + (wait_seconds || 0) * 1000;
      let v = jobView(job_id);
      while (wait_seconds && v.state !== "done" && v.state !== "failed" && Date.now() < until) {
        await new Promise((r) => setTimeout(r, 1000)); v = jobView(job_id);
      }
      return text(v);
    });

  server.tool("list_videos", "Daftar video/job terbaru beserta statusnya dan URL-nya.",
    { limit: z.number().int().min(1).max(50).optional() },
    async ({ limit }) => {
      const ids = fs.readdirSync(JOBS).filter((x) => ID_RE.test(x));
      const jobs = ids.map(jobView).filter(Boolean).sort((a, b) => (a.created_at < b.created_at ? 1 : -1)).slice(0, limit || 10);
      return text(jobs);
    });

  server.tool("delete_video", "Hapus video dan job tertentu (file MP4, thumbnail, dan folder job). Tidak bisa menghapus job yang sedang berjalan.",
    { job_id: z.string().regex(ID_RE) },
    async ({ job_id }) => {
      const v = jobView(job_id);
      if (!v) return fail("job_id tidak ditemukan");
      if (v.state === "running") return fail("job sedang berjalan, tunggu selesai dulu");
      const qi = queue.indexOf(job_id); if (qi >= 0) queue.splice(qi, 1);
      const st = readJson(path.join(jdir(job_id), "status.json"), {});
      for (const f of [st.output, st.thumbnail]) if (f && /^[a-z0-9-]+\.(mp4|png)$/.test(f)) fs.rmSync(path.join(OUT, f), { force: true });
      fs.rmSync(jdir(job_id), { recursive: true, force: true });
      return text({ deleted: job_id });
    });

  return server;
}

// ---------------------------------------------------------------- HTTP
const app = express();
app.disable("x-powered-by");
const tokenOk = (given) => {
  if (typeof given !== "string" || !given) return false;
  const a = crypto.createHash("sha256").update(given).digest();
  const b = crypto.createHash("sha256").update(TOKEN).digest();
  return crypto.timingSafeEqual(a, b);
};
const auth = (req, res, next) => {
  if (!TOKEN) return next();
  const h = req.headers.authorization || "";
  const bearer = h.startsWith("Bearer ") ? h.slice(7) : "";
  if (tokenOk(bearer) || tokenOk(typeof req.query.token === "string" ? req.query.token : "")) return next();
  res.status(401).json({ error: "unauthorized" });
};

app.use("/files", express.static(OUT, { acceptRanges: true }));
app.get("/health", (req, res) => res.json({ ok: true, running, queued: queue.length }));
app.get("/", (req, res) => res.type("text/plain").send(
  `Video Studio MCP\n\nSSE (legacy)    : ${BASE}/sse\nStreamable HTTP: ${BASE}/mcp\nFile hasil      : ${BASE}/files/<nama>.mp4\nHealth          : ${BASE}/health\n`));

const transports = {};
app.get("/sse", auth, async (req, res) => {
  const transport = new SSEServerTransport("/messages", res);
  transports[transport.sessionId] = transport;
  res.on("close", () => { delete transports[transport.sessionId]; });
  await buildServer().connect(transport);
});
app.post("/messages", auth, async (req, res) => {
  const t = transports[String(req.query.sessionId)];
  if (!t) return res.status(400).send("sessionId tidak ditemukan");
  await t.handlePostMessage(req, res);
});

app.post("/mcp", auth, express.json({ limit: "2mb" }), async (req, res) => {
  const server = buildServer();
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  res.on("close", () => { transport.close(); server.close(); });
  try { await server.connect(transport); await transport.handleRequest(req, res, req.body); }
  catch (e) { if (!res.headersSent) res.status(500).json({ jsonrpc: "2.0", error: { code: -32603, message: String(e) }, id: null }); }
});
const noGet = (req, res) => res.status(405).json({ jsonrpc: "2.0", error: { code: -32000, message: "Method not allowed" }, id: null });
app.get("/mcp", noGet); app.delete("/mcp", noGet);

// ---------------------------------------------------------------- retensi & shutdown
function pruneJobs() {
  if (!(JOB_RETENTION_DAYS > 0)) return;
  const limit = Date.now() - JOB_RETENTION_DAYS * 86400 * 1000; let n = 0;
  for (const id of fs.readdirSync(JOBS).filter((x) => ID_RE.test(x))) {
    if (id === running || queue.includes(id)) continue;
    const st = readJson(path.join(jdir(id), "status.json"), null);
    if (st && (st.state === "queued" || st.state === "running")) continue;
    try { if (fs.statSync(jdir(id)).mtimeMs < limit) { fs.rmSync(jdir(id), { recursive: true, force: true }); n++; } } catch {}
  }
  if (n) console.log(`pruneJobs: ${n} folder job lama dihapus`);
}
pruneJobs(); setInterval(pruneJobs, 6 * 3600 * 1000).unref();

function shutdown(sig) {                     // pm2 restart/stop: matikan render yang berjalan supaya tidak jadi yatim
  console.log(`${sig}: berhenti, mematikan render yang berjalan`);
  killTree(runningProc);
  process.exit(0);
}
process.on("SIGINT", () => shutdown("SIGINT")); process.on("SIGTERM", () => shutdown("SIGTERM"));

app.listen(PORT, "0.0.0.0", () => console.log(`video-mcp jalan di port ${PORT} | base ${BASE}`));
