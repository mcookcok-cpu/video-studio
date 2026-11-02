// pm2 ecosystem — jalankan: pm2 start ecosystem.config.cjs && pm2 save
// Rahasia (MCP_TOKEN, dll.) dibaca dari .env di folder ini (chmod 600, tidak masuk git).
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = __dirname;

function loadEnv() {
  const out = {};
  try {
    for (const line of fs.readFileSync(path.join(ROOT, ".env"), "utf8").split("\n")) {
      const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
      if (m && !line.trim().startsWith("#")) out[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
    }
  } catch {}
  return out;
}
function tailscaleIp() {                       // IP Tailscale otomatis; fallback ke nilai lama bila perintah gagal
  try { return execFileSync("tailscale", ["ip", "-4"], { encoding: "utf8", timeout: 5000 }).trim().split("\n")[0]; }
  catch { return "100.106.213.94"; }
}

const E = loadEnv();
const PUBLIC_BASE = E.PUBLIC_BASE || `http://${tailscaleIp()}:2500`;

module.exports = {
  apps: [
    {
      name: "video-mcp",            // MCP server (SSE + Streamable HTTP) + file hasil
      script: "server.mjs",
      cwd: `${ROOT}/mcp-server`,
      env: { PORT: 2500, PUBLIC_BASE, VIDEO_STUDIO_ROOT: ROOT, MCP_TOKEN: E.MCP_TOKEN || "", JOB_RETENTION_DAYS: E.JOB_RETENTION_DAYS || "14" },
      max_restarts: 10,
      kill_timeout: 8000,            // beri waktu server mematikan render yang berjalan
    },
    {
      name: "video-studio",          // halaman web pemutar + download
      script: "server.js",
      cwd: `${ROOT}/server`,
      env: { PORT: 2400, VIDEO_STUDIO_ROOT: ROOT },
      max_restarts: 10,
    },
  ],
};
