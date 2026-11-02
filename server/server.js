const express = require('express');
const fs = require('fs');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 2400;
const OUT = path.join(process.env.VIDEO_STUDIO_ROOT || '/home/Claude/video-studio', 'output');

app.use('/files', express.static(OUT, { acceptRanges: true }));

app.get('/api/list', (req, res) => {
  const files = fs.readdirSync(OUT).map(f => {
    const st = fs.statSync(path.join(OUT, f));
    return { name: f, size: st.size, mtime: st.mtime };
  });
  res.json(files);
});

app.get('/', (req, res) => {
  const files = fs.readdirSync(OUT);
  const vids = files.filter(f => f.endsWith('.mp4'));
  const meta = fs.existsSync(path.join(OUT, 'metadata.txt')) ? fs.readFileSync(path.join(OUT, 'metadata.txt'), 'utf8') : '';
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const cards = vids.map(v => `
    <div class="card">
      <video controls playsinline preload="metadata" poster="/files/thumbnail.png" src="/files/${encodeURIComponent(v)}"></video>
      <a class="btn" href="/files/${encodeURIComponent(v)}" download>⬇ Download ${esc(v)}</a>
    </div>`).join('');
  res.send(`<!doctype html><html lang="id"><head><meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1"><title>Video Studio</title>
  <style>
    body{margin:0;background:#0b0b1a;color:#eef;font-family:system-ui,sans-serif;padding:24px}
    h1{margin:0 0 16px;font-size:22px}
    .grid{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start}
    .card{width:340px}
    video{width:100%;border-radius:16px;background:#000}
    .btn{display:block;margin-top:12px;text-align:center;background:#ffd65a;color:#201040;padding:12px;border-radius:12px;text-decoration:none;font-weight:700}
    pre{background:#15152b;padding:16px;border-radius:12px;max-width:560px;white-space:pre-wrap;line-height:1.5}
  </style></head><body>
  <h1>🎬 Video Studio</h1>
  <div class="grid">${cards}<pre>${esc(meta)}</pre></div>
  </body></html>`);
});

app.listen(PORT, '0.0.0.0', () => console.log('video-studio jalan di port ' + PORT));
