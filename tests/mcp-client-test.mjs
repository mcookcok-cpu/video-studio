import { Client } from "../mcp-server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js";
import { SSEClientTransport } from "../mcp-server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/sse.js";
import { StreamableHTTPClientTransport } from "../mcp-server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/streamableHttp.js";
import fs from "node:fs";
const j = (r) => JSON.parse(r.content[0].text);
// token: dari env MCP_TOKEN, atau dari ../.env
let TOKEN = process.env.MCP_TOKEN || "";
if (!TOKEN) { try { TOKEN = (fs.readFileSync(new URL("../.env", import.meta.url), "utf8").match(/^MCP_TOKEN=(.*)$/m) || [])[1] || ""; } catch {} }
const reqInit = TOKEN ? { headers: { Authorization: `Bearer ${TOKEN}` } } : undefined;
const BASE = process.env.MCP_URL || "http://localhost:2500";

// 1) SSE
const c = new Client({ name: "uji-sse", version: "1.0.0" });
await c.connect(new SSEClientTransport(new URL(`${BASE}/sse`), { requestInit: reqInit, eventSourceInit: { fetch: (u, i) => fetch(u, { ...i, headers: { ...(i && i.headers), ...(reqInit ? reqInit.headers : {}) } }) } }));
const tools = (await c.listTools()).tools.map((t) => t.name);
console.log("[SSE] tools:", tools.join(", "));
const guide = (await c.callTool({ name: "get_video_guide", arguments: {} })).content[0].text;
console.log("[SSE] panduan:", guide.length, "karakter");
const created = j(await c.callTool({ name: "create_video", arguments: {
  title: "Uji MCP Video", channel: "UJI MCP", music: true,
  scenes: [
    { graphic: "statement", line1: "HALO DUNIA", line2: "DARI MCP", narration: "Halo! Video ini dibuat otomatis oleh agent lain lewat MCP.", params: { text: "Dibuat oleh AI Agent" } },
    { graphic: "counter", badge: "2", line1: "BERHASIL", line2: "100 PERSEN", theme: "green", narration: "Pengujian berhasil seratus persen.", params: { from: 0, to: 100, suffix: "%", label: "tingkat keberhasilan" } },
  ] } }));
console.log("[SSE] create:", JSON.stringify(created));
let v;
for (let i = 0; i < 30; i++) {
  v = j(await c.callTool({ name: "get_video_status", arguments: { job_id: created.job_id, wait_seconds: 40 } }));
  console.log("[SSE] status:", v.state, v.progress_percent + "%", v.stage);
  if (v.state === "done" || v.state === "failed") break;
}
console.log("[SSE] hasil:", JSON.stringify(v));
// validasi error
const bad = await c.callTool({ name: "get_video_status", arguments: { job_id: "zzzzzzzz" } }).catch((e) => ({ err: String(e).slice(0, 120) }));
console.log("[SSE] id salah ->", JSON.stringify(bad).slice(0, 160));
await c.close();

// 2) Streamable HTTP
const c2 = new Client({ name: "uji-http", version: "1.0.0" });
await c2.connect(new StreamableHTTPClientTransport(new URL(`${BASE}/mcp`), { requestInit: reqInit }));
console.log("[HTTP] tools:", (await c2.listTools()).tools.length);
console.log("[HTTP] list_videos:", JSON.stringify(j(await c2.callTool({ name: "list_videos", arguments: { limit: 3 } })).map((x) => [x.job_id, x.state])));
await c2.close();
if (created && created.job_id && v && v.state === "done") {
  const c3 = new Client({ name: "uji-hapus", version: "1.0.0" });
  await c3.connect(new StreamableHTTPClientTransport(new URL(`${BASE}/mcp`), { requestInit: reqInit }));
  console.log("[HTTP] delete_video:", JSON.stringify(j(await c3.callTool({ name: "delete_video", arguments: { job_id: created.job_id } }))));
  await c3.close();
}
console.log(v && v.state === "done" ? "SELESAI: LULUS" : "SELESAI: GAGAL"); process.exit(v && v.state === "done" ? 0 : 1);
