// pm2 ecosystem — jalankan: pm2 start ecosystem.config.cjs && pm2 save
const ROOT = "/home/Claude/video-studio";
const TS_IP = "100.106.213.94"; // IP Tailscale server (dipakai untuk membentuk URL di balasan MCP)
module.exports = {
  apps: [
    {
      name: "video-mcp",            // MCP server (SSE + Streamable HTTP) + file hasil
      script: "server.mjs",
      cwd: `${ROOT}/mcp-server`,
      env: { PORT: 2500, PUBLIC_BASE: `http://${TS_IP}:2500`, VIDEO_STUDIO_ROOT: ROOT /*, MCP_TOKEN: "isi-bila-perlu" */ },
      max_restarts: 10,
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
