/* ── Workspace views ── */
import { getStatus, runWorker, resetWorker, pauseWorker, resumeWorker,
         injectFault, authorityAttack, falseCompletion, oscillation } from './api.js';
import { classifyEvent, classifyState } from './actors.js';
import { openTrace } from './trace.js';
import { WorkField } from './workfield.js';

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const fmtAmt = n => n ? `$${Number(n).toLocaleString()}` : '—';

/* ── Shared state ── */
let _state = null;
let _field = null;
let _workField = null;

export function getState() { return _state; }

/* ── Overview ── */
export function mountOverview() {
  const el = $('#view-overview');
  el.innerHTML = `
    <div class="ov-hero">
      <div class="ov-state" id="ov-state">STANDBY</div>
      <div class="ov-state-sub" id="ov-state-sub">No job running. Click "Run Job" to begin.</div>
    </div>
    <div class="ov-field" id="ov-field-wrap"></div>
    <div class="ov-questions" id="ov-questions">
      <div class="ov-q ink"><div class="q-val" id="q-working">—</div><div class="q-lbl">What is the worker doing?</div></div>
      <div class="ov-q green"><div class="q-val" id="q-done">0</div><div class="q-lbl">Verified items</div></div>
      <div class="ov-q orange"><div class="q-val" id="q-failing">0</div><div class="q-lbl">Exceptions contained</div></div>
      <div class="ov-q green"><div class="q-val" id="q-recovered">0</div><div class="q-lbl">KEEPR recovered</div></div>
      <div class="ov-q yellow"><div class="q-val" id="q-escalated">0</div><div class="q-lbl">Human decisions required</div></div>
    </div>
    <div class="ov-controls">
      <button class="btn btn-primary" id="btn-run">Run Job</button>
      <button class="btn btn-outline btn-sm" id="btn-pause">Pause</button>
      <button class="btn btn-outline btn-sm" id="btn-resume">Resume</button>
      <button class="btn btn-ghost btn-sm" id="btn-reset">Reset</button>
      <span class="status-msg" id="run-msg"></span>
    </div>
    <div class="ov-stream">
      <div class="stream-header"><span>Live Event Stream</span><span id="ev-count">0 events</span></div>
      <div class="stream-body" id="stream-body"><div class="empty-state">No events yet — run the job to see KEEPR in action.</div></div>
    </div>`;
  const fieldWrap = $('#ov-field-wrap');
  _field = new WorkField(fieldWrap, { large: true, onSelect: iid => openInvoice(iid) });
  if (_state) _field.update(_state.invoices);
  $('#btn-run').addEventListener('click', handleRun);
  $('#btn-pause').addEventListener('click', handlePause);
  $('#btn-resume').addEventListener('click', handleResume);
  $('#btn-reset').addEventListener('click', handleReset);
}

function handleRun() { runChunked(); }
function handlePause() { pauseWorker().catch(()=>{}); }
function handleResume() { resumeWorker().catch(()=>{}); }
function handleReset() { resetWorker().then(() => refreshStatus()).catch(()=>{}); }

async function runChunked() {
  const msg = $('#run-msg');
  msg.textContent = 'Resetting...';
  try {
    await resetWorker();
    await refreshStatus();
    await sleep(100);
  } catch (e) { /* proceed anyway */ }
  msg.textContent = 'Processing...';
  let faultInjected = false;
  let processed = 0;
  try {
    while (true) {
      const s = await getStatus();
      if (s.paused) { msg.textContent = 'Paused.'; return; }
      const st = s.run_state;
      if (st === 'FROZEN' || st === 'COMPLETED') { msg.textContent = st + '.'; return; }
      const pending = s.counts.pending || 0;
      if (pending === 0) { msg.textContent = `Complete. 50/50`; return; }

      // Auto-inject fault on inv_007 after 5 invoices for demo drama
      if (!faultInjected && processed >= 5) {
        faultInjected = true;
        msg.textContent = 'FAULT: inv_007 503';
        const res = await injectFault('inv_007', 'http_503');
        await refreshStatus();
        await sleep(300);
      }

      const res = await runWorker(1);
      processed = 50 - pending;
      msg.textContent = faultInjected ? `Processing... ${processed}/50 (recovering...)` : `Processing... ${processed}/50`;
      await refreshStatus();
      await sleep(100);
    }
  } catch (e) { msg.textContent = 'Error: ' + e.message; }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/* ── Work ── */
let _workFilter = 'ALL';
export function mountWork() {
  const el = $('#view-work');
  el.innerHTML = `
    <div class="work-top">
      <h2 class="section-title">Invoices <span class="mirror" aria-hidden="true">INVOICES</span></h2>
      <div class="work-filters" id="work-filters">
        <button class="wf-btn active" data-filter="ALL">ALL</button>
        <button class="wf-btn" data-filter="COMPLETED">VERIFIED</button>
        <button class="wf-btn" data-filter="RECOVERED">RECOVERED</button>
        <button class="wf-btn" data-filter="ESCALATED">ESCALATED</button>
        <button class="wf-btn" data-filter="FROZEN">FROZEN</button>
        <button class="wf-btn" data-filter="PENDING">PENDING</button>
      </div>
    </div>
    <div class="work-segments" id="work-segments"></div>
    <div class="work-grid" id="work-grid"></div>`;
  $$('#work-filters .wf-btn').forEach(b => b.addEventListener('click', () => {
    _workFilter = b.dataset.filter;
    $$('#work-filters .wf-btn').forEach(bb => bb.classList.toggle('active', bb === b));
    renderWorkGrid();
  }));
  const gw = document.createElement('div');
  gw.style.cssText = 'background:var(--card);border:1px solid var(--card-border);border-radius:var(--r3);overflow:hidden;margin-bottom:1rem;';
  el.querySelector('.work-segments').after(gw);
  _workField = new WorkField(gw, { onSelect: iid => openInvoice(iid) });
  renderWorkGrid();
}

function renderWorkGrid() {
  if (!_state) return;
  const invs = _state.invoices || {};
  const counts = _state.counts || {};
  const total = 50;

  // Segments
  const segEl = $('#work-segments');
  if (segEl) {
    const segs = [
      ['completed', counts.completed || 0, 'work-seg-completed'],
      ['recovered', counts.recovered || 0, 'work-seg-recovered'],
      ['escalated', counts.escalated || 0, 'work-seg-escalated'],
      ['frozen', counts.frozen || 0, 'work-seg-frozen'],
      ['pending', counts.pending || 50, 'work-seg-pending']
    ];
    segEl.innerHTML = segs.map(([_, c, cls]) =>
      `<div class="work-seg ${cls}" style="width:${(c / total * 100)}%"></div>`
    ).join('');
  }

  // Grid
  const grid = $('#work-grid');
  if (!grid) return;
  grid.innerHTML = '';
  for (const [iid, info] of Object.entries(invs)) {
    const st = info.status || 'PENDING';
    if (_workFilter !== 'ALL' && st !== _workFilter) continue;
    const cell = document.createElement('div');
    cell.className = `inv-cell inv-cell-${st.toLowerCase()}`;
    cell.innerHTML = `<div class="inv-id">${iid.replace('inv_', '')}</div>
      <div class="inv-amt">${fmtAmt(info.amount)}</div>
      <div class="inv-state-bar"></div>`;
    cell.addEventListener('click', () => openInvoice(iid));
    cell.addEventListener('mouseenter', e => showTooltip(e, iid, info));
    cell.addEventListener('mouseleave', hideTooltip);
    grid.appendChild(cell);
  }
  if (_workField) _workField.update(invs);
}

/* ── Failure Lab ── */
const ATTACKS = [
  { id: 'http_503', name: 'Break One Transaction', desc: 'Transient service failure on a single invoice. Bounded retry, then substitute fallback.', sev: 'med', expected: 'retry → substitute → verify' },
  { id: 'http_401', name: 'Kill the Credentials', desc: 'Expired authentication. Never retried — immediate escalation with evidence.', sev: 'high', expected: 'escalate immediately' },
  { id: 'malformed_amount', name: 'Poison the Data', desc: 'Malformed response ($4,500) — schema validation rejects before content is trusted.', sev: 'med', expected: 'reject → substitute' },
  { id: 'stale', name: 'Return Stale Records', desc: 'Record older than freshness bound. Alternate source used, authoritative verified.', sev: 'low', expected: 'substitute → verify' },
  { id: 'conflict', name: 'Create Source Conflict', desc: 'Primary and authoritative disagree. Unresolvable contradiction.', sev: 'high', expected: 'freeze' },
  { id: 'partial', name: 'Return Partial Result', desc: 'Incomplete batch — remainder retried, rollback if recovery fails.', sev: 'med', expected: 'retry_remainder → rollback → escalate' },
  { id: 'inflated', name: 'Inflate the Amount', desc: 'Schema-valid but wrong value. Caught by verification against authoritative state.', sev: 'low', expected: 'substitute → verify' },
  { id: 'authority', name: 'Request Unauthorized Access', desc: 'Worker attempts out-of-scope capability. Blocked before any adapter executes.', sev: 'high', expected: 'blocked — adapter not executed' },
  { id: 'false', name: 'Lie About Completion', desc: 'Agent claims DONE. Authoritative ledger says otherwise. REJECT → ROLLBACK → FROZEN.', sev: 'high', expected: 'reject → rollback → freeze' },
  { id: 'oscillation', name: 'Create Oscillation', desc: 'Alternating failures exhaust bounded retries. Paranoia bound triggers escalation.', sev: 'high', expected: 'bounded retry → escalate' }
];

let _selectedAttack = null;
let _labResult = null;

export function mountLab() {
  const el = $('#view-lab');
  el.innerHTML = `
    <div style="margin-bottom:1.5rem">
      <h2 class="section-title">Break the Job <span class="mirror" aria-hidden="true">BREAK IT</span></h2>
      <p style="font-size:.85rem;color:var(--ink3);margin-top:.3rem">Introduce a failure. Watch KEEPR contain it. The rest of the job survives.</p>
    </div>
    <div class="lab-layout">
      <div class="lab-attacks" id="lab-attacks"></div>
      <div class="lab-right">
        <div class="lab-pipeline" id="lab-pipeline">
          <div class="pl-title">Recovery Pipeline</div>
          <div class="pl-stages" id="pl-stages">
            <div class="pl-stage" data-stage="failure">FAILURE</div><span class="pl-arrow">/</span>
            <div class="pl-stage" data-stage="classify">CLASSIFY</div><span class="pl-arrow">/</span>
            <div class="pl-stage" data-stage="policy">POLICY</div><span class="pl-arrow">/</span>
            <div class="pl-stage" data-stage="authority">AUTHORITY</div><span class="pl-arrow">/</span>
            <div class="pl-stage" data-stage="action">ACTION</div><span class="pl-arrow">/</span>
            <div class="pl-stage" data-stage="observe">OBSERVE</div><span class="pl-arrow">/</span>
            <div class="pl-stage" data-stage="verify">VERIFY</div><span class="pl-arrow">→</span>
            <div class="pl-stage" data-stage="final">FINAL</div>
          </div>
        </div>
        <div id="lab-special"></div>
        <div class="lab-result" id="lab-result">
          <div class="lr-title">Result</div>
          <div id="lab-result-content"><div class="empty-state">Select an attack and run to see the result.</div></div>
        </div>
      </div>
    </div>`;
  const list = $('#lab-attacks');
  ATTACKS.forEach(a => {
    const card = document.createElement('div');
    card.className = 'lab-attack';
    card.dataset.id = a.id;
    card.innerHTML = `<div class="la-name">${a.name}</div><div class="la-desc">${a.desc}</div>
      <div class="la-meta"><span class="la-sev ${a.sev}">${a.sev}</span><span class="tag">${a.expected}</span></div>
      <button class="btn btn-primary btn-sm" style="margin-top:.6rem;width:100%" data-run="${a.id}">Run Attack</button>`;
    card.addEventListener('click', () => { _selectedAttack = a.id; $$('.lab-attack').forEach(c => c.classList.toggle('selected', c.dataset.id === a.id)); });
    card.querySelector('[data-run]').addEventListener('click', e => { e.stopPropagation(); runLabAttack(a); });
    list.appendChild(card);
  });
}

async function runLabAttack(attack) {
  const resultEl = $('#lab-result-content');
  const specialEl = $('#lab-special');
  resultEl.innerHTML = '<div class="loading-full">Running attack...</div>';
  specialEl.innerHTML = '';

  // Reset pipeline
  $$('.pl-stage').forEach(s => { s.classList.remove('lit', 'pass', 'fail', 'freeze'); });

  try {
    if (attack.id === 'authority') {
      const res = await authorityAttack();
      await animatePipeline(['failure', 'classify', 'policy', 'authority'], 'fail');
      resultEl.innerHTML = `<pre>${JSON.stringify(res, null, 2)}</pre>`;
      renderAuthorityDemo(res, specialEl);
      return;
    }
    if (attack.id === 'false') {
      const res = await falseCompletion();
      await refreshStatus();
      await animatePipeline(['failure', 'classify', 'policy', 'authority', 'action', 'observe', 'verify', 'final'], 'freeze');
      resultEl.innerHTML = `<pre>${JSON.stringify(res, null, 2)}</pre>`;
      renderFalseCompletionDemo(res, specialEl);
      return;
    }
    if (attack.id === 'oscillation') {
      const res = await oscillation();
      await refreshStatus();
      await animatePipeline(['failure', 'classify', 'policy', 'action', 'observe', 'verify', 'final'], res.final_status === 'FROZEN' ? 'freeze' : 'fail');
      resultEl.innerHTML = `<pre>${JSON.stringify(res, null, 2)}</pre>`;
      return;
    }
    // Standard attack: inject + run
    await injectFault('inv_007', attack.id);
    await refreshStatus();
    await runWorker();
    await refreshStatus();
    const inv = (_state?.invoices || {})['inv_007'];
    const trace = inv?.trace || [];
    const stages = mapTraceToStages(trace);
    const finalClass = inv?.status === 'COMPLETED' || inv?.status === 'RECOVERED' ? 'pass'
      : inv?.status === 'FROZEN' ? 'freeze' : 'fail';
    await animatePipeline(stages, finalClass);
    resultEl.innerHTML = `<pre>Invoice: inv_007\nStatus: ${inv?.status || 'UNKNOWN'}\nAttempts: ${inv?.attempts || 0}\nRecovery: ${inv?.recovery_mode || '—'}\n\nTrace:\n${trace.map(e => `  ${e.state}:${e.event}`).join('\n')}</pre>`;
  } catch (e) { resultEl.innerHTML = `<div class="err-banner">${e.message}</div>`; }
}

function mapTraceToStages(trace) {
  const stages = ['failure'];
  for (const ev of trace) {
    const t = ev.event;
    if (t.startsWith('classified:')) stages.push('classify');
    if (t.startsWith('policy:')) stages.push('policy');
    if (/OBSERVING|observed:/.test(t)) stages.push('observe');
    if (/verify:|verified:|VERIFIED/.test(t)) stages.push('verify');
    if (/resume:|RESUMED|COMPLETED|restored-pending/.test(t)) stages.push('final');
    if (/ESCALAT|FROZEN/.test(t)) stages.push('final');
  }
  return [...new Set(stages)];
}

async function animatePipeline(stages, finalClass) {
  for (const s of stages) {
    const el = document.querySelector(`[data-stage="${s}"]`);
    if (el) { el.classList.add('lit', finalClass || ''); await sleep(180); }
  }
}

function renderFalseCompletionDemo(res, container) {
  container.innerHTML = `
    <div class="lab-split">
      <div class="lab-split-panel agent">
        <div class="sp-label">AI Worker Claim</div>
        <div class="sp-claim" style="color:var(--green)">COMPLETED</div>
        <div style="font-size:.75rem;color:var(--ink3)">Invoice ${res.invoice} marked as done by the agent.</div>
      </div>
      <div class="lab-split-panel ledger">
        <div class="sp-label">Authoritative Ledger</div>
        <div class="sp-claim" style="color:var(--red)">REFUNDED</div>
        <div style="font-size:.75rem;color:var(--ink3)">External state contradicts the agent's claim.</div>
      </div>
    </div>
    <div class="lab-split-vs">AGENT CLAIM ≠ AUTHORITATIVE STATE</div>
    <div class="lab-reject">
      <div class="lr-reject-title">KEEPR / REJECT / ROLLBACK / FROZEN</div>
      <div class="lr-reject-desc">${res.explanation}</div>
      <div style="margin-top:.8rem;font-size:.82rem;font-weight:600;color:var(--green);font-family:var(--mono)">
        THE OTHER 49 INVOICES CONTINUE.
      </div>
    </div>`;
}

function renderAuthorityDemo(res, container) {
  container.innerHTML = `
    <div class="lab-boundary" id="lab-boundary">
      <div class="lb-title">Authority Boundary</div>
      <div class="lb-flow">
        <div class="lb-node allowed">ar.read</div>
        <div class="lb-arrow">/</div>
        <div class="lb-node" id="lb-request" style="border-color:var(--yellow);color:var(--yellow)">payroll.write</div>
        <div class="lb-arrow">/</div>
        <div class="lb-node denied" id="lb-boundary">BOUNDARY</div>
      </div>
      <div class="lb-stamp" id="lb-stamp">AUTHORITY WIDENING — BLOCKED</div>
      <div style="margin-top:.6rem;font-size:.78rem;color:var(--green);font-weight:600;font-family:var(--mono);opacity:0;transition:opacity .3s" id="lb-continue">
        ADAPTER NOT EXECUTED. THE JOB CONTINUES.
      </div>
    </div>`;
  setTimeout(() => { const el = $('#lb-stamp'); if (el) el.classList.add('show'); }, 600);
  setTimeout(() => { const el = $('#lb-continue'); if (el) el.style.opacity = '1'; }, 1200);
}

/* ── Authority ── */
export function mountAuthority() {
  const el = $('#view-authority');
  const scope = _state?.scope || ['fetch_primary', 'fetch_alternate'];
  const forbidden = ['refund_payment', 'modify_payment', 'request_payroll_access', 'rewrite_transaction', 'modify_payment_amount'];
  el.innerHTML = `
    <div>
      <h2 class="section-title">Authority Map <span class="mirror" aria-hidden="true">SCOPE</span></h2>
      <p style="font-size:.85rem;color:var(--ink3);margin-top:.3rem">KEEPR recovers the work, but it cannot expand the agent's authority to do so. The original job scope is the ceiling.</p>
    </div>
    <div class="auth-map">
      <div class="auth-zone granted">
        <div class="az-title">Granted Capabilities</div>
        ${scope.map(c => `<div class="auth-cap"><div class="ac-check"></div><span>${c}</span></div>`).join('')}
      </div>
      <div class="auth-zone forbidden">
        <div class="az-title">Forbidden</div>
        ${forbidden.map(c => `<div class="auth-cap"><div class="ac-check ac-deny"></div><span>${c}</span></div>`).join('')}
      </div>
    </div>
    <div class="auth-demo">
      <button class="btn btn-outline" id="auth-demo-btn">Attempt payroll.write</button>
      <div class="auth-demo-result" id="auth-demo-result"></div>
    </div>`;
  $('#auth-demo-btn').addEventListener('click', async () => {
    const res = await authorityAttack();
    const el = $('#auth-demo-result');
    el.className = 'auth-demo-result show ' + (res.blocked ? 'blocked' : 'allowed');
    el.textContent = res.blocked ? `BLOCKED — ${res.reason}` : 'ALLOWED (unexpected)';
  });
}

/* ── Verification ── */
export function mountVerification() {
  const el = $('#view-verification');
  el.innerHTML = `
    <div>
      <h2 class="section-title">Verification Center <span class="mirror" aria-hidden="true">VERIFY</span></h2>
      <p style="font-size:.85rem;color:var(--ink3);margin-top:.3rem">What the agent said vs. what the system observed. No item becomes DONE on the agent's word alone.</p>
    </div>
    <div class="verify-checks">
      <div class="vc-card"><div class="vc-name">Schema Validation</div><div class="vc-desc">Record shape checked before any content is trusted. Malformed payloads rejected.</div></div>
      <div class="vc-card"><div class="vc-name">Source Identity</div><div class="vc-desc">Observation must come from a trusted source. Unknown sources flagged.</div></div>
      <div class="vc-card"><div class="vc-name">Freshness</div><div class="vc-desc">Record must be within the freshness bound. Stale data triggers substitution.</div></div>
      <div class="vc-card"><div class="vc-name">Amount Match</div><div class="vc-desc">Observed amount must match the expected ledger amount.</div></div>
      <div class="vc-card"><div class="vc-name">Cross-Source Consistency</div><div class="vc-desc">Two valid sources for the same invoice must agree. Conflict → freeze.</div></div>
      <div class="vc-card"><div class="vc-name">Terminal State</div><div class="vc-desc">Completion requires independent verification. Agent cannot declare success.</div></div>
    </div>
    <div class="verify-live" id="verify-live">
      <h3 style="font-size:.88rem;margin:1.5rem 0 .8rem;font-weight:600">Live Verification Events</h3>
      <div id="verify-events"><div class="empty-state">Run the job to see verification events.</div></div>
    </div>
    <div class="verify-claim" id="verify-claim">
      <h3 style="font-size:.88rem;margin-bottom:.8rem;font-weight:600">Claims vs Observed</h3>
      <div id="verify-claim-content"><div class="empty-state">Trigger "False Completion" in the Failure Lab to see this comparison.</div></div>
    </div>`;
  renderVerifyEvents();
}

function renderVerifyEvents() {
  if (!_state) return;
  const el = $('#verify-events');
  if (!el) return;
  const events = [];
  for (const [iid, inv] of Object.entries(_state.invoices || {})) {
    for (const ev of (inv.trace || [])) {
      if (/verified:|VERIFIED|VERIFYING|verify:/.test(ev.event)) {
        events.push({ iid, ...ev });
      }
    }
  }
  if (events.length === 0) { el.innerHTML = '<div class="empty-state">No verification events yet.</div>'; return; }
  el.innerHTML = events.slice(-12).map(e => {
    const passed = /verified:|VERIFIED|pass/.test(e.event);
    return `<div class="ev-item" data-actor="verify"><span class="ev-actor ev-actor-verify">VERIFY</span>
      <span class="ev-iid">${e.iid}</span><span class="ev-text">${e.state}:${e.event}</span>
      <span class="chip ${passed ? 'chip-green' : 'chip-red'}" style="margin-left:auto">${passed ? 'PASS' : 'FAIL'}</span></div>`;
  }).join('');
}

/* ── Escalations ── */
export function mountEscalations() {
  const el = $('#view-escalations');
  const invs = _state?.invoices || {};
  const escalated = Object.entries(invs).filter(([, i]) => i.status === 'ESCALATED');
  const total = 50, resolved = total - escalated.length;
  el.innerHTML = `
    <div class="esc-header">
      <h2>Escalation Queue</h2>
      <div class="esc-stat">KEEPR resolved <strong>${resolved}</strong> of ${total} invoices automatically. The job continues. <strong>${escalated.length}</strong> exceptions require human judgment.</div>
    </div>
    <div class="esc-queue" id="esc-queue"></div>`;
  const queue = $('#esc-queue');
  if (escalated.length === 0) {
    queue.innerHTML = '<div class="empty-state">Queue is empty — KEEPR resolved everything.</div>';
    return;
  }
  for (const [iid, inv] of escalated) {
    const trace = inv.trace || [];
    const failureEv = trace.find(e => e.event.startsWith('failure:') || e.event === 'FAILURE');
    const policyEvs = trace.filter(e => e.event.startsWith('policy:'));
    const why = failureEv ? failureEv.event.replace('failure:', '').replace('FAILURE', 'UNKNOWN') : 'Unknown';
    const tried = policyEvs.map(e => e.event.split(':')[1]).join(', ') || 'None';
    const card = document.createElement('div');
    card.className = 'esc-card';
    card.innerHTML = `
      <div class="ec-top"><div class="ec-iid">${iid}</div><span class="chip chip-yellow">ESCALATED</span></div>
      <div class="ec-section"><div class="ec-label">Why KEEPR stopped</div><div class="ec-value">${why}</div></div>
      <div class="ec-section"><div class="ec-label">What it tried</div><div class="ec-value">${tried || '—'}</div></div>
      <div class="ec-section"><div class="ec-label">Decision needed</div><div class="ec-value">${escDecision(why)}</div></div>`;
    card.addEventListener('click', () => openInvoice(iid));
    queue.appendChild(card);
  }
}

function escDecision(failureClass) {
  const map = {
    'AUTHENTICATION': 'Renew credentials for accounting_primary.',
    'AUTHORIZATION': 'Grant or deny expanded access.',
    'CONFLICTING_RESULT': 'Adjudicate conflicting records.',
    'UNKNOWN': 'Investigate and decide manual path.'
  };
  return map[failureClass] || 'Human decision required.';
}

/* ── Helpers ── */
function openInvoice(iid) {
  if (!_state) return;
  const inv = _state.invoices?.[iid];
  if (inv) openTrace(iid, inv);
}

const tooltip = document.getElementById('tooltip');
function showTooltip(e, iid, info) {
  tooltip.innerHTML = `<div class="tt-id">${iid}</div>
    <div class="tt-row"><span class="tt-label">Amount</span><span>${fmtAmt(info.amount)}</span></div>
    <div class="tt-row"><span class="tt-label">Status</span><span>${info.status || 'PENDING'}</span></div>
    <div class="tt-row"><span class="tt-label">Attempts</span><span>${info.attempts || 0}</span></div>
    <div class="tt-row"><span class="tt-label">Recovery</span><span>${info.recovery_mode || '—'}</span></div>`;
  tooltip.style.left = Math.min(e.clientX + 12, innerWidth - 240) + 'px';
  tooltip.style.top = (e.clientY + 12) + 'px';
  tooltip.classList.add('show');
}
function hideTooltip() { tooltip.classList.remove('show'); }

/* ── Topbar updates ── */
export function updateTopbar(state) {
  _state = state;
  const counts = state?.counts || {};
  const runState = state?.run_state;
  const paused = state?.paused;
  const total = 50, done = (counts.completed||0)+(counts.recovered||0);
  const rate = total > 0 ? Math.round(((total-(counts.escalated||0))/total)*100) : 0;

  // System state chip
  const chip = $('#t-state-chip');
  let chipText = 'STANDBY', chipClass = 't-chip-standby';
  if (paused) { chipText = 'PAUSED'; chipClass = 't-chip-paused'; }
  else if (runState === 'FROZEN') { chipText = 'FROZEN — HALTED'; chipClass = 't-chip-frozen'; }
  else if (runState === 'COMPLETED') { chipText = `COMPLETED — ${rate}% NO-HUMAN`; chipClass = 't-chip-completed'; }
  else if (runState === 'RUNNING' || runState === 'RESUMED') {
    if (counts.pending > 0) { chipText = 'AUTONOMOUS — WORKING'; chipClass = 't-chip-autonomous'; }
    else { chipText = `COMPLETED — ${rate}% NO-HUMAN`; chipClass = 't-chip-completed'; }
  }
  if (counts.escalated > 0 && runState !== 'RUNNING' && runState !== 'RESUMED') {
    chipText = `EXCEPTION REQUIRES REVIEW`; chipClass = 't-chip-escalated';
  }
  chip.textContent = chipText;
  chip.className = 't-chip ' + chipClass;

  // Escalation badge
  const esc = $('#t-esc');
  const escNum = $('#t-esc-num');
  if (counts.escalated > 0) { esc.style.display = ''; escNum.textContent = counts.escalated; }
  else { esc.style.display = 'none'; }

  // Overview questions
  const qWorking = $('#q-working');
  const qDone = $('#q-done');
  const qFailing = $('#q-failing');
  const qRecovered = $('#q-recovered');
  const qEscalated = $('#q-escalated');
  if (qWorking) qWorking.textContent = runState === 'RUNNING' || runState === 'RESUMED' ? 'Processing invoices' : runState || 'Standby';
  if (qDone) { qDone.textContent = done; qDone.closest('.ov-q')?.classList.toggle('green', done > 0); }
  if (qFailing) qFailing.textContent = (counts.frozen || 0) + (counts.escalated || 0);
  if (qRecovered) qRecovered.textContent = counts.recovered || 0;
  if (qEscalated) qEscalated.textContent = counts.escalated || 0;

  // Overview state
  const ovState = $('#ov-state');
  const ovSub = $('#ov-state-sub');
  if (ovState) ovState.textContent = chipText;
  if (ovSub) {
    if (runState === 'RUNNING' || runState === 'RESUMED') ovSub.textContent = `Processing invoices — ${done}/50 verified.`;
    else if (runState === 'COMPLETED') ovSub.textContent = `Job complete. ${rate}% no-human rate.`;
    else if (runState === 'FROZEN') ovSub.textContent = 'Workflow halted by unresolvable conflict.';
    else ovSub.textContent = 'No job running. Click "Run Job" to begin.';
  }

  // Event stream
  renderEventStream();
  renderWorkGrid();
  renderVerifyEvents();
  renderEscalationsInline();

  // Health dots
  checkHealthDots();
}

function renderEventStream() {
  const body = $('#stream-body');
  if (!body || !_state) return;
  const events = [];
  for (const [iid, inv] of Object.entries(_state.invoices || {})) {
    for (const ev of (inv.trace || [])) {
      events.push({ iid, seq: ev.seq || 0, ...ev });
    }
  }
  events.sort((a, b) => (b.seq || 0) - (a.seq || 0));
  const recent = events.slice(0, 20);
  if (recent.length === 0) { body.innerHTML = '<div class="empty-state">No events yet — run the job to see KEEPR in action.</div>'; return; }
  body.innerHTML = recent.map(e => {
    const info = classifyEvent(e.event, e.detail);
    return `<div class="ev-item" data-actor="${info.actor}"><span class="ev-actor ev-actor-${info.actor}">${info.label}</span>
      <span class="ev-iid">${e.iid}</span><span class="ev-text">${e.state}:${e.event}</span></div>`;
  }).join('');
  const countEl = $('#ev-count');
  if (countEl) countEl.textContent = `${events.length} events`;
}

function renderEscalationsInline() {
  // Update escalation view if mounted
  const el = $('#view-escalations');
  if (el && el.querySelector('.esc-queue')) mountEscalations();
}

let _healthTimer;
async function checkHealthDots() {
  const w = $('#dot-worker'), l = $('#dot-ledger');
  if (w) w.className = 't-dot ok';
  try {
    const r = await fetch('http://127.0.0.1:8001/ledger/health', { signal: AbortSignal.timeout(2000) });
    if (l) l.className = r.ok ? 't-dot ok' : 't-dot err';
  } catch { if (l) l.className = 't-dot err'; }
}

export async function refreshStatus() {
  try {
    const s = await getStatus();
    _state = s;
    if (_field) _field.update(s.invoices);
    if (_workField) _workField.update(s.invoices);
    updateTopbar(s);
  } catch (e) { /* silent */ }
}
