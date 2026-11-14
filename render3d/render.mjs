// Pemakaian: node render.mjs <model.glb> <nama_klip> <anim[,anim2,...]> [detik=6] [ukuran=800]
// Hasil: ../assets/clips/<nama_klip>/f_0001.png ... + clip.json (PNG transparan, 24 fps)
import fs from "node:fs";
import { openPage } from "./lib.mjs";
const [model, out, seq, secs = "6", size = "800"] = process.argv.slice(2);
if (!model || !out || !seq || !/^[a-z0-9_-]{1,40}$/.test(out)) { console.error("argumen tidak valid"); process.exit(2); }
const FPS = 24, S = +size, T = +secs, N = Math.round(T * FPS);
const DIR = new URL(`../assets/clips/${out}/`, import.meta.url).pathname;
fs.mkdirSync(DIR, { recursive: true });
const { browser, page } = await openPage(S, S);
const anims = await page.evaluate(f => window.R.load(f), model);
const dur = Object.fromEntries(anims.map(a => [a.name, a.duration]));
const names = seq.split(",");
for (const n of names) if (!dur[n]) { console.error("animasi tidak ada:", n); process.exit(3); }
const total = names.reduce((s, n) => s + dur[n], 0); const t0 = Date.now();
for (let i = 0; i < N; i++) {
  const t = i / FPS; let tm = t % total, acc = 0, an = names[0], lt = 0;
  for (const n of names) { if (tm < acc + dur[n]) { an = n; lt = tm - acc; break; } acc += dur[n]; }
  const az = 22 * Math.sin(2 * Math.PI * t / T);
  const url = await page.evaluate(([a, l, z]) => window.R.frame(a, l, z, 4.0, 0.88), [an, lt, az]);
  fs.writeFileSync(`${DIR}/f_${String(i + 1).padStart(4, "0")}.png`, Buffer.from(url.split(",")[1], "base64"));
  if (i % 24 === 0) console.log(out, `${i}/${N}`, Math.round((Date.now() - t0) / 1000) + "s");
}
fs.writeFileSync(`${DIR}/clip.json`, JSON.stringify({ fps: FPS, n: N, size: S, model, seq }));
console.log("SELESAI", out, N, "frame", Math.round((Date.now() - t0) / 1000) + "s");
await browser.close();
