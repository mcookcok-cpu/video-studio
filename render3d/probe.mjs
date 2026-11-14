import { openPage, BASE } from "./lib.mjs";
const w = +process.argv[2] || 540, h = +process.argv[3] || 960;
const { browser, page, gpu } = await openPage(w, h); console.log("gpu:", gpu);
const models = await (await fetch(BASE + "/api/models")).json();
for (const m of models) {
  const t0 = Date.now(); const an = await page.evaluate(f => window.R.load(f), m.file);
  console.log(m.file, "load", Date.now() - t0, "ms |", an.length, "anim:", an.map(a => `${a.name}(${a.duration}s)`).join(", "));
}
await page.evaluate(f => window.R.load(f), models[1].file);
const t1 = Date.now(); let url;
for (let i = 0; i < 5; i++) url = await page.evaluate(() => window.R.frame("city_idle", 0.3 * Math.random(), 20, 3.6, 0.9));
console.log("rata-rata per frame:", (Date.now() - t1) / 5, "ms, ukuran png b64:", url.length);
await browser.close();
