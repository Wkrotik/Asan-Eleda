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
        --bg: #f8fafc;
        --panel: #ffffff;
        --text: #1e293b;
        --muted: #64748b;
        --border: #e2e8f0;
        --accent: #7c3aed;
        --accent-light: #ede9fe;
        --warn: #f59e0b;
        --warn-light: #fef3c7;
        --err: #ef4444;
        --ok: #10b981;
        --demo-banner: #fbbf24;
        --shadow: 0 1px 3px rgba(0,0,0,0.1);
        --radius: 8px;
      }

      * { box-sizing: border-box; margin: 0; padding: 0; }
      
      body {
        min-height: 100vh;
        color: var(--text);
        background: var(--bg);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 14px;
        line-height: 1.5;
      }

      /* Demo Banner */
      .demo-banner {
        background: linear-gradient(90deg, var(--demo-banner), #f97316);
        color: #000;
        text-align: center;
        padding: 10px 16px;
        font-weight: 600;
        font-size: 13px;
        letter-spacing: 0.5px;
      }
      .demo-banner span {
        background: rgba(0,0,0,0.15);
        padding: 2px 8px;
        border-radius: 4px;
        margin-left: 8px;
        font-size: 11px;
        text-transform: uppercase;
      }

      /* Header */
      header {
        background: var(--panel);
        border-bottom: 1px solid var(--border);
        padding: 16px 24px;
      }
      .header-content {
        max-width: 900px;
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
        gap: 10px;
      }
      .logo-icon {
        width: 32px;
        height: 32px;
        background: var(--accent);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 700;
        font-size: 14px;
      }
      h1 {
        font-size: 18px;
        font-weight: 600;
      }
      .api-info {
        font-size: 12px;
        color: var(--muted);
      }
      .api-info code {
        background: var(--accent-light);
        color: var(--accent);
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 11px;
      }

      /* Main */
      main {
        max-width: 900px;
        margin: 24px auto;
        padding: 0 24px;
      }

      /* Tabs */
      .tabs {
        display: flex;
        gap: 4px;
        margin-bottom: 16px;
      }
      .tab {
        appearance: none;
        border: none;
        background: transparent;
        color: var(--muted);
        padding: 10px 20px;
        cursor: pointer;
        font-weight: 500;
        font-size: 14px;
        border-radius: var(--radius) var(--radius) 0 0;
        transition: all 0.15s;
      }
      .tab:hover {
        background: var(--panel);
        color: var(--text);
      }
      .tab[aria-selected="true"] {
        background: var(--panel);
        color: var(--accent);
        box-shadow: var(--shadow);
      }

      /* Card */
      .card {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        overflow: hidden;
      }
      .card + .card {
        margin-top: 16px;
      }
      .card-header {
        padding: 12px 16px;
        border-bottom: 1px solid var(--border);
        background: #fafafa;
        font-weight: 600;
        font-size: 13px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .card-body {
        padding: 16px;
      }

      /* Form */
      .form-group {
        margin-bottom: 16px;
      }
      .form-group:last-child {
        margin-bottom: 0;
      }
      .form-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
      }
      @media (max-width: 600px) {
        .form-row { grid-template-columns: 1fr; }
      }
      label {
        display: block;
        font-weight: 500;
        margin-bottom: 6px;
        font-size: 13px;
      }
      input[type="file"] {
        width: 100%;
        padding: 12px;
        border: 2px dashed var(--border);
        border-radius: var(--radius);
        background: #fafafa;
        cursor: pointer;
        transition: border-color 0.15s;
      }
      input[type="file"]:hover {
        border-color: var(--accent);
      }

      /* Buttons */
      .btn-row {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 16px;
      }
      .btn {
        appearance: none;
        border: none;
        padding: 10px 20px;
        border-radius: var(--radius);
        font-weight: 600;
        font-size: 14px;
        cursor: pointer;
        transition: all 0.15s;
      }
      .btn-primary {
        background: var(--accent);
        color: white;
      }
      .btn-primary:hover {
        background: #6d28d9;
      }
      .btn-primary:disabled {
        background: #a78bfa;
        cursor: not-allowed;
      }
      .btn-secondary {
        background: var(--border);
        color: var(--text);
      }
      .btn-secondary:hover {
        background: #cbd5e1;
      }

      /* Status */
      .status {
        font-size: 13px;
        font-weight: 500;
      }
      .status.ok { color: var(--ok); }
      .status.err { color: var(--err); }
      .status.warn { color: var(--warn); }
      .status.loading { color: var(--accent); }

      /* Output */
      .output-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
      }
      pre {
        margin: 0;
        padding: 16px;
        overflow: auto;
        max-height: 500px;
        border-radius: var(--radius);
        background: #1e293b;
        color: #e2e8f0;
        font-family: "SF Mono", Monaco, Consolas, monospace;
        font-size: 12px;
        line-height: 1.5;
      }

      /* Result Summary */
      .result-summary {
        background: var(--accent-light);
        border: 1px solid #c4b5fd;
        border-radius: var(--radius);
        padding: 16px;
        margin-bottom: 16px;
      }
      .result-summary h3 {
        font-size: 14px;
        margin-bottom: 12px;
        color: var(--accent);
      }
      .result-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px;
      }
      .result-item {
        background: white;
        padding: 10px 12px;
        border-radius: 6px;
      }
      .result-item .label {
        font-size: 11px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .result-item .value {
        font-size: 15px;
        font-weight: 600;
        color: var(--text);
        margin-top: 2px;
      }
      .result-item .value.match { color: var(--ok); }
      .result-item .value.no-match { color: var(--err); }
      .result-item .value.review { color: var(--warn); }

      /* Helper text */
      .helper {
        margin-top: 12px;
        padding: 10px 12px;
        background: #f1f5f9;
        border-radius: 6px;
        font-size: 12px;
        color: var(--muted);
      }

      /* Footer */
      footer {
        text-align: center;
        padding: 24px;
        color: var(--muted);
        font-size: 12px;
      }
    </style>
  </head>
  <body>
    <div class="demo-banner">
      This is a demonstration interface for testing purposes only
      <span>Not for Production</span>
    </div>

    <header>
      <div class="header-content">
        <div class="logo">
          <div class="logo-icon">AI</div>
          <div>
            <h1>ASAN Appeal AI</h1>
            <div class="api-info">Citizen Appeal Analysis System</div>
          </div>
        </div>
        <div class="api-info">
          API: <code id="baseUrl"></code>
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
              <label for="fileAnalyze">Select Image or Video</label>
              <input id="fileAnalyze" type="file" accept="image/*,video/*" />
            </div>
            <div class="btn-row">
              <button class="btn btn-primary" id="btnAnalyze">Analyze</button>
              <button class="btn btn-secondary" id="btnClearA">Clear</button>
              <span class="status" id="statusA"></span>
            </div>
            <div class="helper">
              Upload a photo or video of a civic issue. The AI will generate a title, description, 
              category suggestion, and priority level.
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
                <label for="fileBefore">Before (Original Issue)</label>
                <input id="fileBefore" type="file" accept="image/*,video/*" />
              </div>
              <div class="form-group">
                <label for="fileAfter">After (Resolution Evidence)</label>
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
              The AI checks location consistency and evidence of resolution.
            </div>
          </div>
        </div>
      </div>

      <!-- Results -->
      <div class="card" id="resultsCard" style="display:none">
        <div class="card-header">Results</div>
        <div class="card-body">
          <div class="result-summary" id="resultSummary" style="display:none"></div>
          <div class="output-header">
            <span style="font-weight:500; color: var(--muted);">Raw JSON Response</span>
            <button class="btn btn-secondary" id="btnCopy" style="padding: 6px 12px; font-size: 12px;">
              Copy JSON
            </button>
          </div>
          <pre id="out"></pre>
        </div>
      </div>
    </main>

    <footer>
      ASAN Appeal AI Demo &middot; Offline Processing &middot; No Data Sent to External Servers
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
        `;
        resultSummary.style.display = '';
      }

      function showVerifySummary(data) {
        if (!data || data.error) {
          resultSummary.style.display = 'none';
          return;
        }
        
        const sameLoc = data.same_location?.decision || 'unknown';
        const sameConf = data.same_location?.confidence;
        const resolved = data.resolved?.decision || 'unknown';
        const resConf = data.resolved?.confidence;
        
        const sameClass = sameLoc === 'match' ? 'match' : sameLoc === 'no_match' ? 'no-match' : 'review';
        const resClass = resolved === 'match' ? 'match' : resolved === 'no_match' ? 'no-match' : 'review';
        
        resultSummary.innerHTML = `
          <h3>Verification Results</h3>
          <div class="result-grid">
            <div class="result-item">
              <div class="label">Same Location</div>
              <div class="value ${sameClass}">${sameLoc === 'match' ? 'Yes' : sameLoc === 'no_match' ? 'No' : 'Review Needed'}</div>
            </div>
            <div class="result-item">
              <div class="label">Location Confidence</div>
              <div class="value">${sameConf ? (sameConf * 100).toFixed(0) + '%' : 'N/A'}</div>
            </div>
            <div class="result-item">
              <div class="label">Issue Resolved</div>
              <div class="value ${resClass}">${resolved === 'match' ? 'Yes' : resolved === 'no_match' ? 'No' : 'Review Needed'}</div>
            </div>
            <div class="result-item">
              <div class="label">Resolution Confidence</div>
              <div class="value">${resConf ? (resConf * 100).toFixed(0) + '%' : 'N/A'}</div>
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
          btn.textContent = 'Copied!';
          setTimeout(() => { btn.textContent = 'Copy JSON'; }, 1500);
        } catch (e) {
          console.error('Copy failed:', e);
        }
      });
    </script>
  </body>
</html>
"""
