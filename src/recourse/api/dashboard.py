"""Dashboard HTML template — single dark-theme page.

Renders the AR worker state, invoice table, lifecycle traces, and
Failure Lab one-click attack buttons.
"""
from __future__ import annotations

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>RECOURSE — Autonomous AR Worker</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0a0a0f;--fg:#c8d6e5;--accent:#00e676;--warn:#ffab00;
       --err:#ff1744;--dim:#3a3a4a;--card:#12121a;--border:#222233}
body{background:var(--bg);color:var(--fg);font-family:'SF Mono','Fira Code',monospace;
     padding:1.5rem;line-height:1.5}
h1{color:var(--accent);font-size:1.1rem;letter-spacing:.05em;margin-bottom:.25rem}
h2{color:var(--fg);font-size:.9rem;margin:1rem 0 .5rem;opacity:.8}
.badge{display:inline-block;padding:2px 8px;border-radius:3px;font-size:.7rem;
        font-weight:700;text-transform:uppercase}
.b-done{background:#004d1a;color:#00e676}.b-rec{background:#1a2200;color:#b2ff59}
.b-esc{background:#3d2200;color:#ffab00}.b-frozen{background:#1a0033;color:#d500f9}
.b-pend{background:#1a1a22;color:#78909c}.b-fail{background:#3d0000;color:#ff1744}
.b-proc{background:#002233;color:#40c4ff}
.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:.75rem;margin:1rem 0}
.card{background:var(--card);border:1px solid var(--border);border-radius:6px;
       padding:.75rem 1rem;text-align:center}
.card .val{font-size:1.6rem;font-weight:800;color:var(--accent)}
.card .lbl{font-size:.65rem;text-transform:uppercase;opacity:.6;margin-top:.25rem}
table{width:100%;border-collapse:collapse;font-size:.75rem;margin:.5rem 0}
th{text-align:left;padding:6px 10px;border-bottom:1px solid var(--dim);
    color:var(--accent);font-size:.65rem;text-transform:uppercase;opacity:.8}
td{padding:5px 10px;border-bottom:1px solid #18181f}
tr:hover{background:#14141c}
tr.sel{background:#1a1a2a;border-left:2px solid var(--accent)}
button{background:var(--card);color:var(--fg);border:1px solid var(--dim);
       border-radius:4px;padding:6px 14px;font-family:inherit;font-size:.7rem;
       cursor:pointer;transition:border-color .15s}
button:hover{border-color:var(--accent)}
button:active{background:#1a1a22}
button.danger{border-color:var(--err);color:var(--err)}
.lab-row{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0}
.lifecycle{background:var(--card);border:1px solid var(--border);border-radius:6px;
           padding:1rem;margin:1rem 0;font-size:.72rem;min-height:100px}
.lifecycle .step{display:inline-block;padding:3px 8px;margin:2px;
                 border-radius:3px;background:#1a1a22;border:1px solid var(--border)}
.lifecycle .step.fail{border-color:var(--err);color:var(--err)}
.lifecycle .step.ok{border-color:var(--accent);color:var(--accent)}
.lifecycle .step.rec{border-color:#b2ff59;color:#b2ff59}
.lifecycle .step.esc{border-color:var(--warn);color:var(--warn)}
.lifecycle .step.frozen{border-color:#d500f9;color:#d500f9}
.arrow{color:var(--dim);margin:0 2px}
h2 .sub{font-size:.7rem;opacity:.5;font-weight:400}
.controls{display:flex;gap:.5rem;align-items:center;margin:1rem 0}
.controls .status-msg{font-size:.7rem;opacity:.6}
#selected-label{font-size:.75rem;color:var(--accent);margin-top:.5rem}
</style>
</head>
<body>
<h1>RECOURSE <span style="opacity:.4">|</span> Autonomous AR Worker</h1>
<p style="font-size:.7rem;opacity:.5">50 invoices <span style="opacity:.3">·</span>
   Recovery is not retry <span style="opacity:.3">·</span>
   The agent owns the job — it does not own the definition of success</p>

<div class="controls">
  <button id="btn-run" onclick="runWorker()">▶ RUN 50</button>
  <button id="btn-reset" onclick="resetWorker()" class="danger">⟳ RESET</button>
  <span class="status-msg" id="run-msg"></span>
</div>

<div class="grid">
  <div class="card"><div class="val" id="v-pending">50</div><div class="lbl">Remaining</div></div>
  <div class="card"><div class="val" id="v-completed">0</div><div class="lbl">Completed</div></div>
  <div class="card"><div class="val" id="v-recovered">0</div><div class="lbl">Recovered</div></div>
  <div class="card"><div class="val" id="v-escalated">0</div><div class="lbl">Escalated</div></div>
  <div class="card"><div class="val" id="v-frozen">0</div><div class="lbl">Frozen</div></div>
  <div class="card"><div class="val" id="v-rate">0%</div><div class="lbl">No-Human Rate</div></div>
</div>

<h2>Failure Lab <span class="sub">— one click breaks it, RecoveryRuntime recovers it</span></h2>
<div class="lab-row">
  <button onclick="inject('inv_007','http_503')">503</button>
  <button onclick="inject('inv_007','http_401')">401</button>
  <button onclick="inject('inv_007','malformed_amount')">MALFORMED</button>
  <button onclick="inject('inv_007','stale')">STALE</button>
  <button onclick="inject('inv_007','conflict')">CONFLICT</button>
  <button onclick="inject('inv_007','partial')">PARTIAL</button>
  <button onclick="inject('inv_007','inflated')">INFLATED</button>
  <button onclick="authorityAttack()">AUTH WIDENING</button>
  <button onclick="falseCompletion()">FALSE COMPLETION</button>
  <button onclick="oscillation()">OSCILLATION</button>
</div>
<div id="lab-msg" style="font-size:.7rem;opacity:.5;margin-bottom:1rem"></div>

<h2>Invoices</h2>
<table>
  <thead><tr><th>ID</th><th>Status</th><th>Attempts</th><th>Recovery</th><th></th></tr></thead>
  <tbody id="inv-body"></tbody>
</table>

<div id="selected-label"></div>
<div class="lifecycle" id="lifecycle-pane">
  <span style="opacity:.3">Select an invoice to view its lifecycle trace</span>
</div>

<script>
let selected = null;
const badge = s => {
  const m = {COMPLETED:'b-done',RECOVERED:'b-rec',ESCALATED:'b-esc',
             FROZEN:'b-frozen',PENDING:'b-pend',FAILED:'b-fail',PROCESSING:'b-proc'};
  return `<span class="badge ${m[s]||'b-pend'}">${s}</span>`;
};

const refresh = async () => {
  try {
    const r = await fetch('/api/worker/status');
    if (!r.ok) return;
    const d = await r.json();
    const c = d.counts || {};
    document.getElementById('v-pending').textContent = c.pending ?? 50;
    document.getElementById('v-completed').textContent = (c.completed||0) + (c.recovered||0);
    document.getElementById('v-recovered').textContent = c.recovered ?? 0;
    document.getElementById('v-escalated').textContent = c.escalated ?? 0;
    document.getElementById('v-frozen').textContent = c.frozen ?? 0;
    const done = (c.completed||0) + (c.recovered||0);
    const total = 50;
    document.getElementById('v-rate').textContent =
      total > 0 ? Math.round(((total - (c.escalated||0)) / total) * 100) + '%' : '0%';
    const body = document.getElementById('inv-body');
    body.innerHTML = '';
    const invs = d.invoices || {};
    for (const [iid, info] of Object.entries(invs)) {
      const st = info.status || 'PENDING';
      const sel = selected === iid ? ' class="sel"' : '';
      body.innerHTML += `<tr${sel}><td>${iid}</td><td>${badge(st)}</td>` +
        `<td>${info.attempts || 0}</td><td>${info.recovery_mode || '—'}</td>` +
        `<td><button onclick="selectInv('${iid}')">trace</button></td></tr>`;
    }
    if (selected && invs[selected]) renderLifecycle(invs[selected].trace || []);
  } catch(e) {}
};

const renderLifecycle = trace => {
  const pane = document.getElementById('lifecycle-pane');
  if (!trace.length) { pane.innerHTML = '<span style="opacity:.3">No events yet</span>'; return; }
  const classFor = e => {
    if (e.includes('FAIL') || e.includes('BLOCKED') || e.includes('REJECT')) return 'fail';
    if (e.includes('COMPLETED') || e.includes('VERIFIED')) return 'ok';
    if (e.includes('RECOVER') || e.includes('policy:')) return 'rec';
    if (e.includes('ESCALAT')) return 'esc';
    if (e.includes('FROZEN') || e.includes('FREEZE')) return 'frozen';
    return '';
  };
  let html = '';
  trace.forEach((t, i) => {
    const cls = classFor(t.event);
    if (i > 0) html += '<span class="arrow">→</span>';
    html += `<span class="step ${cls}">${t.state}:${t.event}</span>`;
  });
  pane.innerHTML = html;
};

const selectInv = iid => { selected = iid; document.getElementById('selected-label').textContent =
  `Selected: ${iid}`; refresh(); };

const runWorker = async () => {
  document.getElementById('run-msg').textContent = 'Running...';
  await fetch('/api/worker/run', {method:'POST'});
  document.getElementById('run-msg').textContent = '';
  refresh();
};

const resetWorker = async () => {
  await fetch('/api/worker/reset', {method:'POST'});
  selected = null;
  document.getElementById('selected-label').textContent = '';
  refresh();
};

const inject = async (iid, mode) => {
  document.getElementById('lab-msg').textContent = `Injecting ${mode} into ${iid}...`;
  await fetch('/api/worker/attack', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({invoice_id:iid, mode})});
  document.getElementById('lab-msg').textContent = `Injected ${mode}. Run worker to see recovery.`;
};

const authorityAttack = async () => {
  document.getElementById('lab-msg').textContent = 'Authority widening attack sent (see API logs).';
  await fetch('/api/worker/authority-attack', {method:'POST'});
};

const falseCompletion = async () => {
  document.getElementById('lab-msg').textContent =
    'False completion: agent says DONE, verifier says NOT. ROLLBACK.';
  await fetch('/api/worker/false-completion', {method:'POST'});
};

const oscillation = async () => {
  document.getElementById('lab-msg').textContent =
    'Oscillation attack: alternating failures. Bounded retry → FREEZE.';
  await fetch('/api/worker/oscillation', {method:'POST'});
};

setInterval(refresh, 1000);
refresh();
</script>
</body>
</html>"""


def render_dashboard() -> str:
    return DASHBOARD_HTML
