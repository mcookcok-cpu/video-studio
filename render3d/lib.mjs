import { chromium } from "playwright-core";
import fs from "node:fs";
export const BASE = process.env.MODEL_BASE || "http://100.80.57.51:8689";
const EXE = fs.readdirSync(process.env.HOME + "/.cache/ms-playwright").filter(x => x.startsWith("chromium_headless_shell"))
  .map(x => `${process.env.HOME}/.cache/ms-playwright/${x}/chrome-headless-shell-linux64/chrome-headless-shell`)[0];
export async function openPage(w, h) {
  const browser = await chromium.launch({ executablePath: EXE, args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox", "--disable-features=BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights,PrivateNetworkAccessRespectPreflightResults,LocalNetworkAccessChecks", "--disable-web-security"] });
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  const html = fs.readFileSync(new URL("./page.html", import.meta.url), "utf8");
  await page.route(BASE + "/__r.html", r => r.fulfill({ contentType: "text/html", body: html }));
  page.on("pageerror", e => console.error("pageerror:", e.message));
  await page.goto(BASE + "/__r.html"); await page.waitForFunction(() => window.R, null, { timeout: 20000 });
  const gpu = await page.evaluate(([w, h]) => window.R.init(w, h), [w, h]);
  return { browser, page, gpu };
}
