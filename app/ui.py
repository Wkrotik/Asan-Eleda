from __future__ import annotations


def render_index_html() -> str:
    # Single-file UI (no build step) for demo/testing.
    # Keep dependencies at zero; use fetch() to call the API.
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="icon" href="/favicon.ico" />
    <title>ASAN Appeal AI - Demo</title>
    <style>
      :root {
        --bg: #f6f7f9;
        --panel: #ffffff;
        --text: #2d3748;
        --text-secondary: #5a6578;
        --muted: #8492a6;
        --border: #e8ecf1;
        --border-light: #f0f2f5;
        --accent: #4a6fa5;
        --accent-soft: #e8eef6;
        --accent-hover: #3d5d8a;
        --success: #4a9d7c;
        --success-soft: #e8f5ef;
        --warn: #c08c4a;
        --warn-soft: #faf4eb;
        --err: #b85c5c;
        --err-soft: #faf0f0;
        --shadow-sm: 0 1px 2px rgba(45,55,72,0.04);
        --shadow: 0 2px 8px rgba(45,55,72,0.06);
        --radius: 6px;
      }

      * { box-sizing: border-box; margin: 0; padding: 0; }
      
      body {
        min-height: 100vh;
        color: var(--text);
        background: var(--bg);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
        font-size: 14px;
        line-height: 1.6;
        -webkit-font-smoothing: antialiased;
      }

      /* Demo Notice - Subtle but clear */
      .demo-notice {
        background: var(--warn-soft);
        border-bottom: 1px solid #e8dfd0;
        color: #7a6340;
        text-align: center;
        padding: 8px 16px;
        font-size: 12px;
        letter-spacing: 0.02em;
      }
      .demo-notice strong {
        font-weight: 600;
      }

      /* Header */
      header {
        background: var(--panel);
        border-bottom: 1px solid var(--border);
        padding: 14px 24px;
      }
      .header-content {
        max-width: 840px;
        margin: 0 auto;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        flex-wrap: wrap;
      }
      .logo {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .logo-mark {
        width: 28px;
        height: 28px;
        background: var(--accent);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
        font-size: 11px;
        letter-spacing: -0.02em;
      }
      .logo-text h1 {
        font-size: 15px;
        font-weight: 600;
        color: var(--text);
        letter-spacing: -0.01em;
      }
      .logo-text p {
        font-size: 12px;
        color: var(--muted);
        margin-top: 1px;
      }
      .api-badge {
        font-size: 11px;
        color: var(--muted);
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .api-badge code {
        background: var(--border-light);
        color: var(--text-secondary);
        padding: 3px 8px;
        border-radius: 4px;
        font-family: "SF Mono", Monaco, Consolas, monospace;
        font-size: 11px;
      }

      /* Main */
      main {
        max-width: 840px;
        margin: 20px auto 40px;
        padding: 0 24px;
      }

      /* Tabs - Understated */
      .tabs {
        display: flex;
        gap: 2px;
        margin-bottom: 16px;
        border-bottom: 1px solid var(--border);
        padding-bottom: 0;
      }
      .tab {
        appearance: none;
        border: none;
        background: transparent;
        color: var(--muted);
        padding: 10px 16px;
        cursor: pointer;
        font-weight: 500;
        font-size: 13px;
        position: relative;
        transition: color 0.15s ease;
      }
      .tab:hover {
        color: var(--text-secondary);
      }
      .tab[aria-selected="true"] {
        color: var(--accent);
      }
      .tab[aria-selected="true"]::after {
        content: '';
        position: absolute;
        bottom: -1px;
        left: 0;
        right: 0;
        height: 2px;
        background: var(--accent);
        border-radius: 2px 2px 0 0;
      }

      /* Card - Refined */
      .card {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        box-shadow: var(--shadow-sm);
      }
      .card + .card {
        margin-top: 12px;
      }
      .card-header {
        padding: 12px 16px;
        border-bottom: 1px solid var(--border-light);
        font-weight: 500;
        font-size: 13px;
        color: var(--text-secondary);
      }
      .card-body {
        padding: 16px;
      }

      /* Form */
      .form-group {
        margin-bottom: 14px;
      }
      .form-group:last-child {
        margin-bottom: 0;
      }
      .form-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 14px;
      }
      @media (max-width: 560px) {
        .form-row { grid-template-columns: 1fr; }
      }
      label {
        display: block;
        font-weight: 500;
        margin-bottom: 6px;
        font-size: 13px;
        color: var(--text-secondary);
      }
      input[type="file"] {
        width: 100%;
        padding: 12px;
        border: 1px dashed var(--border);
        border-radius: var(--radius);
        background: var(--bg);
        cursor: pointer;
        font-size: 13px;
        color: var(--text-secondary);
        transition: border-color 0.15s ease, background 0.15s ease;
      }
      input[type="file"]:hover {
        border-color: var(--accent);
        background: var(--accent-soft);
      }

      /* Buttons - Refined */
      .btn-row {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 14px;
      }
      .btn {
        appearance: none;
        border: none;
        padding: 9px 18px;
        border-radius: var(--radius);
        font-weight: 500;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.15s ease;
      }
      .btn-primary {
        background: var(--accent);
        color: white;
      }
      .btn-primary:hover {
        background: var(--accent-hover);
      }
      .btn-primary:disabled {
        background: #a3b5cf;
        cursor: not-allowed;
      }
      .btn-secondary {
        background: var(--border-light);
        color: var(--text-secondary);
      }
      .btn-secondary:hover {
        background: var(--border);
      }

      /* Status - Subtle */
      .status {
        font-size: 12px;
        font-weight: 500;
      }
      .status.ok { color: var(--success); }
      .status.err { color: var(--err); }
      .status.warn { color: var(--warn); }
      .status.loading { color: var(--accent); }

      /* Output */
      .output-section {
        margin-top: 12px;
      }
      .output-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
      }
      .output-header span {
        font-size: 12px;
        font-weight: 500;
        color: var(--muted);
      }
      pre {
        margin: 0;
        padding: 14px 16px;
        overflow: auto;
        max-height: 400px;
        border-radius: var(--radius);
        background: #2a3441;
        color: #d4dae3;
        font-family: "SF Mono", Monaco, Consolas, monospace;
        font-size: 11px;
        line-height: 1.6;
      }

      /* Result Summary - Quieter */
      .result-summary {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 14px 16px;
        margin-bottom: 14px;
      }
      .result-summary h3 {
        font-size: 12px;
        font-weight: 500;
        margin-bottom: 12px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }
      .result-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 10px;
      }
      .result-item {
        background: var(--panel);
        padding: 10px 12px;
        border-radius: 4px;
        border: 1px solid var(--border-light);
      }
      .result-item .label {
        font-size: 10px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 3px;
      }
      .result-item .value {
        font-size: 14px;
        font-weight: 500;
        color: var(--text);
      }
      .result-item .value.match { color: var(--success); }
      .result-item .value.no-match { color: var(--err); }
      .result-item .value.review { color: var(--warn); }

      /* Description box - full width */
      .result-description {
        background: var(--panel);
        padding: 12px 14px;
        border-radius: 4px;
        border: 1px solid var(--border-light);
        margin-top: 10px;
      }
      .result-description .label {
        font-size: 10px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 6px;
      }
      .result-description .value {
        font-size: 13px;
        line-height: 1.6;
        color: var(--text);
      }

      /* Helper text */
      .helper {
        margin-top: 12px;
        padding: 10px 12px;
        background: var(--bg);
        border-radius: 4px;
        font-size: 12px;
        color: var(--muted);
        line-height: 1.5;
      }

      /* Footer */
      footer {
        text-align: center;
        padding: 20px 24px;
        color: var(--muted);
        font-size: 11px;
        border-top: 1px solid var(--border-light);
        margin-top: 32px;
      }
    </style>
  </head>
  <body>
    <div class="demo-notice">
      <strong>Demo Mode</strong> — This interface is for testing and evaluation purposes only
    </div>

    <header>
      <div class="header-content">
        <div class="logo">
          <div class="logo-mark">AI</div>
          <div class="logo-text">
            <h1>ASAN Appeal AI</h1>
            <p>Citizen Appeal Analysis System</p>
          </div>
        </div>
        <div class="api-badge">
          API <code id="baseUrl"></code>
        </div>
      </div>
    </header>

    <main>
      <div class="tabs" role="tablist">
        <button class="tab" id="tabAnalyze" role="tab" aria-selected="true">
          Analyze Media
        </button>
        <button class="tab" id="tabVerify" role="tab" aria-selected="false">
          Verify Resolution
        </button>
      </div>

      <!-- Analyze Panel -->
      <div id="panelAnalyze">
        <div class="card">
          <div class="card-header">Upload Media for Analysis</div>
          <div class="card-body">
            <div class="form-group">
              <label for="fileAnalyze">Select image or video</label>
              <input id="fileAnalyze" type="file" accept="image/*,video/*" />
            </div>
            <div class="btn-row">
              <button class="btn btn-primary" id="btnAnalyze">Analyze</button>
              <button class="btn btn-secondary" id="btnClearA">Clear</button>
              <span class="status" id="statusA"></span>
            </div>
            <div class="helper">
              Upload a photo or video of a civic issue. The system will generate a title, 
              description, category suggestion, and priority level.
            </div>
          </div>
        </div>
      </div>

      <!-- Verify Panel -->
      <div id="panelVerify" style="display:none">
        <div class="card">
          <div class="card-header">Compare Before & After</div>
          <div class="card-body">
            <div class="form-row">
              <div class="form-group">
                <label for="fileBefore">Before (original issue)</label>
                <input id="fileBefore" type="file" accept="image/*,video/*" />
              </div>
              <div class="form-group">
                <label for="fileAfter">After (resolution evidence)</label>
                <input id="fileAfter" type="file" accept="image/*,video/*" />
              </div>
            </div>
            <div class="btn-row">
              <button class="btn btn-primary" id="btnVerify">Verify</button>
              <button class="btn btn-secondary" id="btnClearV">Clear</button>
              <span class="status" id="statusV"></span>
            </div>
            <div class="helper">
              Upload before and after images to verify if an issue has been resolved.
              The system checks location consistency and evidence of resolution.
            </div>
          </div>
        </div>
      </div>

      <!-- Results -->
      <div class="card" id="resultsCard" style="display:none">
        <div class="card-header">Results</div>
        <div class="card-body">
          <div class="result-summary" id="resultSummary" style="display:none"></div>
          <div class="output-section">
            <div class="output-header">
              <span>JSON Response</span>
              <button class="btn btn-secondary" id="btnCopy" style="padding: 5px 10px; font-size: 11px;">
                Copy
              </button>
            </div>
            <pre id="out"></pre>
          </div>
        </div>
      </div>
    </main>

    <footer>
      ASAN Appeal AI Demo · Offline Processing · No Data Sent to External Servers
    </footer>

    <script>
      const baseUrl = window.location.origin;
      document.getElementById('baseUrl').textContent = baseUrl;

      const out = document.getElementById('out');
      const resultsCard = document.getElementById('resultsCard');
      const resultSummary = document.getElementById('resultSummary');
      let lastJson = null;
      let currentMode = 'analyze';

      function setOut(obj) {
        lastJson = obj;
        out.textContent = JSON.stringify(obj, null, 2);
        resultsCard.style.display = '';
      }

      function setStatus(el, kind, msg) {
        el.innerHTML = '';
        el.className = 'status ' + kind;
        el.textContent = msg || '';
      }

      function showAnalyzeSummary(data) {
        if (!data || data.error) {
          resultSummary.style.display = 'none';
          return;
        }
        
        const title = data.suggested_title || 'N/A';
        const category = data.category_top_k?.[0]?.label || 'Unknown';
        const confidence = data.category_top_k?.[0]?.confidence;
        const confStr = confidence ? (confidence * 100).toFixed(0) + '%' : 'N/A';
        const priority = data.priority?.level || 'N/A';
        const description = data.generated_description || 'No description generated';
        
        resultSummary.innerHTML = `
          <h3>Analysis Results</h3>
          <div class="result-grid">
            <div class="result-item">
              <div class="label">Suggested Title</div>
              <div class="value">${escapeHtml(title)}</div>
            </div>
            <div class="result-item">
              <div class="label">Category</div>
              <div class="value">${escapeHtml(category)}</div>
            </div>
            <div class="result-item">
              <div class="label">Confidence</div>
              <div class="value">${confStr}</div>
            </div>
            <div class="result-item">
              <div class="label">Priority</div>
              <div class="value">${escapeHtml(priority.charAt(0).toUpperCase() + priority.slice(1))}</div>
            </div>
          </div>
          <div class="result-description">
            <div class="label">Generated Description</div>
            <div class="value">${escapeHtml(description)}</div>
          </div>
        `;
        resultSummary.style.display = '';
      }

      function showVerifySummary(data) {
        if (!data || data.error) {
          resultSummary.style.display = 'none';
          return;
        }
        
        const sameLoc = data.same_location?.decision || 'unknown';
        const sameScore = data.same_location?.score;
        const resolved = data.resolved?.decision || 'unknown';
        const resScore = data.resolved?.score;
        
        const sameClass = sameLoc === 'match' ? 'match' : sameLoc === 'mismatch' ? 'no-match' : 'review';
        const resClass = resolved === 'match' ? 'match' : resolved === 'mismatch' ? 'no-match' : 'review';
        
        const formatDecision = (d) => d === 'match' ? 'Confirmed' : d === 'mismatch' ? 'No' : 'Review Needed';
        
        resultSummary.innerHTML = `
          <h3>Verification Results</h3>
          <div class="result-grid">
            <div class="result-item">
              <div class="label">Same Location</div>
              <div class="value ${sameClass}">${formatDecision(sameLoc)}</div>
            </div>
            <div class="result-item">
              <div class="label">Location Score</div>
              <div class="value">${sameScore != null ? (sameScore * 100).toFixed(0) + '%' : 'N/A'}</div>
            </div>
            <div class="result-item">
              <div class="label">Issue Resolved</div>
              <div class="value ${resClass}">${formatDecision(resolved)}</div>
            </div>
            <div class="result-item">
              <div class="label">Resolution Score</div>
              <div class="value">${resScore != null ? (resScore * 100).toFixed(0) + '%' : 'N/A'}</div>
            </div>
          </div>
        `;
        resultSummary.style.display = '';
      }

      function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
      }

      function tab(mode) {
        currentMode = mode;
        const isAnalyze = mode === 'analyze';
        document.getElementById('tabAnalyze').setAttribute('aria-selected', isAnalyze ? 'true' : 'false');
        document.getElementById('tabVerify').setAttribute('aria-selected', isAnalyze ? 'false' : 'true');
        document.getElementById('panelAnalyze').style.display = isAnalyze ? '' : 'none';
        document.getElementById('panelVerify').style.display = isAnalyze ? 'none' : '';
        resultSummary.style.display = 'none';
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
        if (!file) { setStatus(s, 'warn', 'Please select a file'); return; }
        
        setStatus(s, 'loading', 'Processing...');
        document.getElementById('btnAnalyze').disabled = true;

        const fd = new FormData();
        fd.append('file', file, file.name);
        try {
          const res = await postMultipart('/analyze', fd);
          setOut(res.json);
          showAnalyzeSummary(res.json);
          setStatus(s, res.ok ? 'ok' : 'err', 
            (res.ok ? 'Completed' : 'Error ' + res.status) + ' (' + res.ms + 'ms)');
        } catch (e) {
          setOut({ error: String(e) });
          setStatus(s, 'err', 'Request failed');
        } finally {
          document.getElementById('btnAnalyze').disabled = false;
        }
      });

      document.getElementById('btnVerify').addEventListener('click', async () => {
        const before = document.getElementById('fileBefore').files[0];
        const after = document.getElementById('fileAfter').files[0];
        const s = document.getElementById('statusV');
        if (!before || !after) { setStatus(s, 'warn', 'Please select both files'); return; }
        
        setStatus(s, 'loading', 'Processing...');
        document.getElementById('btnVerify').disabled = true;

        const fd = new FormData();
        fd.append('before', before, before.name);
        fd.append('after', after, after.name);
        try {
          const res = await postMultipart('/verify', fd);
          setOut(res.json);
          showVerifySummary(res.json);
          setStatus(s, res.ok ? 'ok' : 'err',
            (res.ok ? 'Completed' : 'Error ' + res.status) + ' (' + res.ms + 'ms)');
        } catch (e) {
          setOut({ error: String(e) });
          setStatus(s, 'err', 'Request failed');
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
        if (!lastJson) return;
        try {
          await navigator.clipboard.writeText(JSON.stringify(lastJson, null, 2));
          const btn = document.getElementById('btnCopy');
          btn.textContent = 'Copied';
          setTimeout(() => { btn.textContent = 'Copy'; }, 1200);
        } catch (e) {
          console.error('Copy failed:', e);
        }
      });
    </script>
  </body>
</html>
"""
