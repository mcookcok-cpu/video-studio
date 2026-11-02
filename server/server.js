const express = require('express');
const fs = require('fs');
const path = require('path');
const app = express();
app.disable('x-powered-by');
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
  const vids = files.filter(f => f.endsWith('.mp4'))
    .map(f => ({ f, t: fs.statSync(path.join(OUT, f)).mtimeMs }))
    .sort((a, b) => b.t - a.t).map(x => x.f);
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const read = f => { try { return fs.readFileSync(path.join(OUT, f), 'utf8'); } catch { return ''; } };
  const cards = vids.map(v => {
    const base = v.replace(/\.mp4$/, '');
    // poster & metadata per video; video lama "5 fakta" memakai thumbnail.png / metadata.txt
    const poster = files.includes(base + '.png') ? base + '.png' : (files.includes('thumbnail.png') && base.startsWith('5-fakta') ? 'thumbnail.png' : '');
    const metaFile = files.includes(base + '.txt') ? base + '.txt' : (base.startsWith('5-fakta') && files.includes('metadata.txt') ? 'metadata.txt' : '');
    const meta = metaFile ? read(metaFile) : '';
    return `
    <div class="card">
      <video controls playsinline preload="metadata"${poster ? ` poster="/files/${encodeURIComponent(poster)}"` : ''} src="/files/${encodeURIComponent(v)}"></video>
      <a class="btn" href="/files/${encodeURIComponent(v)}" download>⬇ Download ${esc(v)}</a>
      ${meta ? `<pre>${esc(meta)}</pre>` : ''}
    </div>`;
  }).join('');
  res.send(`<!doctype html><html lang="id"><head><meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1"><title>Video Studio</title>
  <style>
    body{margin:0;background:#0b0b1a;color:#eef;font-family:system-ui,sans-serif;padding:24px}
    h1{margin:0 0 16px;font-size:22px}
    .grid{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start}
    .card{width:340px}
    video{width:100%;border-radius:16px;background:#000}
    .btn{display:block;margin-top:12px;text-align:center;background:#ffd65a;color:#201040;padding:12px;border-radius:12px;text-decoration:none;font-weight:700;word-break:break-all}
    pre{background:#15152b;padding:16px;border-radius:12px;white-space:pre-wrap;line-height:1.5;font-size:13px}
  </style></head><body>
  <h1>🎬 Video Studio</h1>
  <div class="grid">${cards || '<p>Belum ada video.</p>'}</div>
  </body></html>`);
});

app.listen(PORT, '0.0.0.0', () => console.log('video-studio jalan di port ' + PORT));
