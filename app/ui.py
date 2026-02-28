from __future__ import annotations


def render_index_html() -> str:
    # Single-file UI (no build step) for demo/testing.
    # Keep dependencies at zero; use fetch() to call the API.
    return """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <link rel=\"icon\" href=\"/favicon.ico\" />
    <title>Asan Eleda</title>
    <style>
      :root {
        --bg: #0b0f17;
        --panel: #0f1522;
        --panel2: #0c111c;
        --text: #e6edf6;
        --muted: rgba(230, 237, 246, 0.70);
        --line: rgba(230, 237, 246, 0.14);
        --accent: #8be9fd;
        --warn: #fbbf24;
        --err: #fb7185;
        --ok: #34d399;
        --shadow: 0 10px 30px rgba(0, 0, 0, 0.40);
        --radius: 14px;
      }

      * { box-sizing: border-box; }
      body {
        margin: 0;
        min-height: 100vh;
        color: var(--text);
        background: var(--bg);
        font-family: "DejaVu Sans", "Noto Sans", "Liberation Sans", Arial, sans-serif;
      }

      header {
        padding: 24px 18px 10px;
        max-width: 1100px;
        margin: 0 auto;
      }

      .brand {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
      }

      h1 {
        margin: 0;
        font-weight: 750;
        letter-spacing: -0.02em;
        font-size: 22px;
      }

      .subtitle {
        color: var(--muted);
        font-size: 13px;
      }

      main {
        max-width: 1100px;
        margin: 0 auto;
        padding: 12px 18px 28px;
      }

      .grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 14px;
      }

      @media (min-width: 960px) {
        .grid {
          grid-template-columns: 420px 1fr;
          align-items: start;
        }
      }

      .card {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        overflow: hidden;
      }

      .card .hd {
        padding: 14px 14px 12px;
        border-bottom: 1px solid var(--line);
        background: var(--panel2);
      }

      .card .hd .k {
        font-size: 12px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: rgba(232, 238, 252, 0.75);
      }

      .card .bd { padding: 14px; }

      .tabs {
        display: flex;
        gap: 8px;
        padding: 10px 14px 0;
      }

      .tab {
        appearance: none;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.02);
        color: var(--text);
        border-radius: 999px;
        padding: 8px 12px;
        cursor: pointer;
        font-weight: 650;
        font-size: 13px;
      }
      .tab[aria-selected=\"true\"] {
        border-color: rgba(139, 233, 253, 0.55);
        background: rgba(139, 233, 253, 0.10);
      }

      .row {
        display: grid;
        grid-template-columns: 1fr;
        gap: 10px;
        margin: 12px 0 0;
      }

      label {
        display: block;
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(232, 238, 252, 0.70);
        margin-bottom: 6px;
      }

      input[type=file] {
        width: 100%;
        padding: 10px;
        border-radius: 12px;
        border: 1px dashed rgba(232, 238, 252, 0.26);
        background: rgba(255, 255, 255, 0.02);
        color: var(--muted);
      }

      .btnbar {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 12px;
      }

      .btn {
        appearance: none;
        border: 1px solid rgba(139, 233, 253, 0.50);
        background: rgba(139, 233, 253, 0.10);
        color: var(--text);
        border-radius: 12px;
        padding: 10px 12px;
        cursor: pointer;
        font-weight: 700;
        font-size: 13px;
      }
      .btn:hover { background: rgba(139, 233, 253, 0.15); }
      .btn:disabled { opacity: 0.55; cursor: not-allowed; }

      .btn.secondary {
        border-color: rgba(232, 238, 252, 0.22);
        background: rgba(255, 255, 255, 0.03);
      }

      .status {
        font-size: 13px;
        color: var(--muted);
      }
      .status .ok { color: var(--ok); }
      .status .err { color: var(--err); }
      .status .warn { color: var(--warn); }

      pre {
        margin: 0;
        padding: 14px;
        overflow: auto;
        max-height: 70vh;
        border-radius: var(--radius);
        border: 1px solid var(--line);
        background: rgba(0, 0, 0, 0.22);
        font-family: "DejaVu Sans Mono", "Noto Sans Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
        font-size: 12px;
        line-height: 1.45;
      }

      .hint {
        margin-top: 10px;
        color: rgba(232, 238, 252, 0.62);
        font-size: 12px;
        line-height: 1.35;
      }
      code { font-family: inherit; color: rgba(139, 233, 253, 0.95); }
    </style>
  </head>
  <body>
    <header>
      <div class=\"brand\">
        <div>
          <h1>Asan Eleda</h1>
          <div class=\"subtitle\">Single-page demo UI for <code>/analyze</code> and <code>/verify</code> (offline, local).</div>
        </div>
        <div class=\"subtitle\">API: <code id=\"baseUrl\"></code></div>
      </div>
    </header>
    <main>
      <div class=\"grid\">
        <section class=\"card\" aria-label=\"Controls\">
          <div class=\"tabs\" role=\"tablist\" aria-label=\"Mode\">
            <button class=\"tab\" id=\"tabAnalyze\" role=\"tab\" aria-selected=\"true\">Analyze</button>
            <button class=\"tab\" id=\"tabVerify\" role=\"tab\" aria-selected=\"false\">Verify</button>
          </div>

          <div class=\"hd\"><div class=\"k\" id=\"panelTitle\">Analyze</div></div>
          <div class=\"bd\">
            <div id=\"panelAnalyze\">
              <div class=\"row\">
                <div>
                  <label for=\"fileAnalyze\">Media (image/video)</label>
                  <input id=\"fileAnalyze\" type=\"file\" accept=\"image/*,video/*\" />
                </div>
              </div>
              <div class=\"btnbar\">
                <button class=\"btn\" id=\"btnAnalyze\">Run /analyze</button>
                <button class=\"btn secondary\" id=\"btnClearA\">Clear</button>
                <span class=\"status\" id=\"statusA\"></span>
              </div>
              <div class=\"hint\">Tip: the response includes <code>category_top_k</code>, <code>priority</code>, and <code>evidence</code> (GPS metadata when available).</div>
            </div>

            <div id=\"panelVerify\" style=\"display:none\">
              <div class=\"row\">
                <div>
                  <label for=\"fileBefore\">Before</label>
                  <input id=\"fileBefore\" type=\"file\" accept=\"image/*,video/*\" />
                </div>
                <div>
                  <label for=\"fileAfter\">After</label>
                  <input id=\"fileAfter\" type=\"file\" accept=\"image/*,video/*\" />
                </div>
              </div>
              <div class=\"btnbar\">
                <button class=\"btn\" id=\"btnVerify\">Run /verify</button>
                <button class=\"btn secondary\" id=\"btnClearV\">Clear</button>
                <span class=\"status\" id=\"statusV\"></span>
              </div>
              <div class=\"hint\">Tip: if GPS metadata differs, you should see a <code>gps_mismatch</code> warning (warning-only).</div>
            </div>
          </div>
        </section>

        <section class=\"card\" aria-label=\"Output\">
          <div class=\"hd\"><div class=\"k\">Response JSON</div></div>
          <div class=\"bd\">
            <div class=\"btnbar\" style=\"margin-top:0\">
              <button class=\"btn secondary\" id=\"btnCopy\">Copy JSON</button>
              <span class=\"status\" id=\"statusO\"></span>
            </div>
            <div style=\"margin-top:10px\">
              <pre id=\"out\">{\n  \"ready\": true\n}</pre>
            </div>
          </div>
        </section>
      </div>
    </main>

    <script>
      const baseUrl = window.location.origin;
      document.getElementById('baseUrl').textContent = baseUrl;

      const out = document.getElementById('out');
      const statusO = document.getElementById('statusO');
      let lastJson = null;

      function setOut(obj) {
        lastJson = obj;
        out.textContent = JSON.stringify(obj, null, 2);
      }

      function setStatus(el, kind, msg) {
        el.innerHTML = '';
        if (!msg) return;
        const span = document.createElement('span');
        span.className = kind;
        span.textContent = msg;
        el.appendChild(span);
      }

      function tab(mode) {
        const a = (mode === 'analyze');
        document.getElementById('tabAnalyze').setAttribute('aria-selected', a ? 'true' : 'false');
        document.getElementById('tabVerify').setAttribute('aria-selected', a ? 'false' : 'true');
        document.getElementById('panelAnalyze').style.display = a ? '' : 'none';
        document.getElementById('panelVerify').style.display = a ? 'none' : '';
        document.getElementById('panelTitle').textContent = a ? 'Analyze' : 'Verify';
      }

      document.getElementById('tabAnalyze').addEventListener('click', () => tab('analyze'));
      document.getElementById('tabVerify').addEventListener('click', () => tab('verify'));

      async function postMultipart(path, formData) {
        const t0 = performance.now();
        const r = await fetch(baseUrl + path, { method: 'POST', body: formData });
        const dt = Math.round(performance.now() - t0);
        const text = await r.text();
        let js = null;
        try { js = JSON.parse(text); } catch (_) { js = { raw: text }; }
        return { ok: r.ok, status: r.status, json: js, ms: dt };
      }

      document.getElementById('btnAnalyze').addEventListener('click', async () => {
        const file = document.getElementById('fileAnalyze').files[0];
        const s = document.getElementById('statusA');
        if (!file) { setStatus(s, 'warn', 'Pick a file.'); return; }
        setStatus(s, '', '');
        setStatus(statusO, '', '');
        document.getElementById('btnAnalyze').disabled = true;

        const fd = new FormData();
        fd.append('file', file, file.name);
        try {
          const res = await postMultipart('/analyze', fd);
          setOut({ _meta: { status: res.status, latency_ms: res.ms }, ...res.json });
          setStatus(s, res.ok ? 'ok' : 'err', (res.ok ? 'OK' : 'Error') + ' (' + res.status + ', ' + res.ms + 'ms)');
        } catch (e) {
          setOut({ error: String(e) });
          setStatus(s, 'err', 'Request failed.');
        } finally {
          document.getElementById('btnAnalyze').disabled = false;
        }
      });

      document.getElementById('btnVerify').addEventListener('click', async () => {
        const before = document.getElementById('fileBefore').files[0];
        const after = document.getElementById('fileAfter').files[0];
        const s = document.getElementById('statusV');
        if (!before || !after) { setStatus(s, 'warn', 'Pick both files.'); return; }
        setStatus(s, '', '');
        setStatus(statusO, '', '');
        document.getElementById('btnVerify').disabled = true;

        const fd = new FormData();
        fd.append('before', before, before.name);
        fd.append('after', after, after.name);
        try {
          const res = await postMultipart('/verify', fd);
          setOut({ _meta: { status: res.status, latency_ms: res.ms }, ...res.json });
          setStatus(s, res.ok ? 'ok' : 'err', (res.ok ? 'OK' : 'Error') + ' (' + res.status + ', ' + res.ms + 'ms)');
        } catch (e) {
          setOut({ error: String(e) });
          setStatus(s, 'err', 'Request failed.');
        } finally {
          document.getElementById('btnVerify').disabled = false;
        }
      });

      document.getElementById('btnClearA').addEventListener('click', () => {
        document.getElementById('fileAnalyze').value = '';
        setStatus(document.getElementById('statusA'), '', '');
      });
      document.getElementById('btnClearV').addEventListener('click', () => {
        document.getElementById('fileBefore').value = '';
        document.getElementById('fileAfter').value = '';
        setStatus(document.getElementById('statusV'), '', '');
      });

      document.getElementById('btnCopy').addEventListener('click', async () => {
        if (!lastJson) { setStatus(statusO, 'warn', 'Nothing to copy.'); return; }
        try {
          await navigator.clipboard.writeText(JSON.stringify(lastJson, null, 2));
          setStatus(statusO, 'ok', 'Copied.');
          setTimeout(() => setStatus(statusO, '', ''), 900);
        } catch (e) {
          setStatus(statusO, 'err', 'Copy failed.');
        }
      });
    </script>
  </body>
</html>
"""
