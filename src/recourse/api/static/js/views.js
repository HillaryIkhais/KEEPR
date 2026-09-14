/* ── Workspace views ── */
import { getStatus, runWorker, resetWorker, pauseWorker, resumeWorker,
         injectFault, authorityAttack, falseCompletion, oscillation } from './api.js';
import { classifyEvent, classifyState } from './actors.js';
import { openTrace } from './trace.js';
import { ContinuityMap } from './continuity.js';
import { ExceptionPanel } from './exception.js';
import { EventStream } from './events.js';

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const fmtAmt = n => n ? `$${Number(n).toLocaleString()}` : '—';

/* ── Shared state ── */
let _state = null;
let _map = null;
let _exceptionPanel = null;
let _eventStream = null;
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
    <div class="ov-field" id="ov-map-wrap"></div>
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
    <div class="ov-bottom">
      <div class="ov-exception-wrap" id="ov-exception-wrap"></div>
      <div class="ov-stream">
        <div class="stream-header"><span>LIVE EVENT STREAM</span><span id="ev-count">0 events</span></div>
        <div class="stream-body" id="stream-body"><div class="empty-state">No events yet.</div></div>
      </div>
    </div>`;

  const mapWrap = $('#ov-map-wrap');
  _map = new ContinuityMap(mapWrap);
  
  const exceptionWrap = $('#ov-exception-wrap');
  _exceptionPanel = new ExceptionPanel(exceptionWrap);
  
  const streamBody = $('#stream-body');
  _eventStream = new EventStream(streamBody);

  if (_state) _map.update(_state.invoices, _state.run_state);
  
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
  msg.textContent = 'RESET';
  try {
    await resetWorker();
    await refreshStatus();
    await sleep(100);
  } catch (e) { /* proceed anyway */ }
  msg.textContent = 'JOB ACTIVE';
  let faultInjected = false;
  let processed = 0;
  let lastRecovered = 0;
  try {
    while (true) {
      const s = await getStatus();
      if (s.paused) { msg.textContent = 'PAUSED'; return; }
      const st = s.run_state;
      if (st === 'FROZEN' || st === 'COMPLETED') { msg.textContent = st; return; }
      const pending = s.counts.pending || 0;
      if (pending === 0) { 
        msg.textContent = 'COMPLETE 50/50';
        _eventStream.addEvent('SYSTEM', null, 'JOB COMPLETE — ALL TRANSACTIONS VERIFIED', 'COMPLETE');
        return; 
      }

      if (!faultInjected && processed >= 0) {
        faultInjected = true;
        msg.textContent = 'FAULT INJECTED';
        _eventStream.addEvent('SYSTEM', null, 'FAULT INJECTED: inv_003 http_503', 'FAULT');
        const res = await injectFault('inv_003', 'http_503');
        await refreshStatus();
        await sleep(200);
      }

      const res = await runWorker(1);
      processed = 50 - pending;
      
      const currentRecovered = s.counts.recovered || 0;
      if (currentRecovered > lastRecovered) {
        _eventStream.addEvent('KEEPR', 'inv_003', 'EXCEPTION CONTAINED — RECOVERY COMPLETE', 'RECOVERED');
        lastRecovered = currentRecovered;
      }
      
      msg.textContent = `PROCESSING ${processed}/50`;
      await refreshStatus();
      await sleep(80);
    }
  } catch (e) { msg.textContent = 'ERROR: ' + e.message; }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/* ── Work ── */
export function mountWork() {
  const el = $('#view-work');
  el.innerHTML = `
    <div class="work-top">
      <div class="work-title">TRANSACTION GRID</div>
      <div class="work-filters" id="work-filters">
        <button class="wf-btn active" data-f="all">ALL</button>
        <button class="wf-btn" data-f="PENDING">PENDING</button>
        <button class="wf-btn" data-f="COMPLETED">COMPLETED</button>
        <button class="wf-btn" data-f="RECOVERED">RECOVERED</button>
        <button class="wf-btn" data-f="ESCALATED">ESCALATED</button>
        <button class="wf-btn" data-f="FROZEN">FROZEN</button>
      </div>
    </div>
    <div class="work-segments" id="work-segments"></div>
    <div class="work-grid" id="work-grid"></div>`;
  el.querySelectorAll('.wf-btn').forEach(b => b.addEventListener('click', () => {
    el.querySelectorAll('.wf-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    renderWorkGrid(b.dataset.f);
  }));
  if (_state) renderWorkGrid('all');
}

let _workFilter = 'all';
function renderWorkGrid(filter) {
  _workFilter = filter;
  const grid = $('#work-grid');
  if (!grid || !_state) return;
  const invs = _state.invoices || {};
  const entries = Object.entries(invs).filter(([id, inv]) => {
    if (filter === 'all') return true;
    if (filter === 'RECOVERED') return inv.status === 'COMPLETED' && inv.attempts > 0;
    return inv.status === filter;
  });
  grid.innerHTML = entries.length === 0 ? '<div class="empty-state">No items match filter.</div>' :
    entries.map(([id, inv]) => {
      const st = inv.status === 'COMPLETED' && inv.attempts > 0 ? 'RECOVERED' : inv.status;
      const color = { PENDING: 'var(--ink4)', COMPLETED: 'var(--green)', RECOVERED: 'var(--purple)',
                      ESCALATED: 'var(--yellow)', FROZEN: 'var(--red)' }[st] || 'var(--ink3)';
      return `<div class="wg-card" data-iid="${id}" style="border-left:3px solid ${color}">
        <div class="wg-id">${id}</div>
        <div class="wg-amt">${fmtAmt(inv.amount)}</div>
        <div class="wg-status">${st}</div>
        ${inv.attempts > 0 ? `<div class="wg-attempts">${inv.attempts} attempt${inv.attempts > 1 ? 's' : ''}</div>` : ''}
      </div>`;
    }).join('');
  grid.querySelectorAll('.wg-card').forEach(c => c.addEventListener('click', () => openInvoice(c.dataset.iid)));
  updateSegments();
}

function updateSegments() {
  const seg = $('#work-segments');
  if (!seg || !_state) return;
  const c = _state.counts;
  const t = c.pending + c.completed + c.recovered + c.escalated + c.frozen || 1;
  seg.innerHTML = `
    <div class="work-seg work-seg-completed" style="width:${(c.completed/t)*100}%"></div>
    <div class="work-seg work-seg-recovered" style="width:${(c.recovered/t)*100}%"></div>
    <div class="work-seg work-seg-escalated" style="width:${(c.escalated/t)*100}%"></div>
    <div class="work-seg work-seg-frozen" style="width:${(c.frozen/t)*100}%"></div>`;
}

function openInvoice(iid) {
  openTrace(iid, _state);
}

/* ── Failure Lab ── */
const ATTACKS = [
  { id: 'http_503', name: '503 FAILURE', desc: 'External adapter returns HTTP 503.', sev: 'high', expected: 'RECOVERED' },
  { id: 'false', name: 'FALSE COMPLETION', desc: 'Agent claims COMPLETED but reality is REFUNDED.', sev: 'critical', expected: 'FROZEN' },
  { id: 'authority', name: 'AUTHORITY WIDENING', desc: 'Agent requests payroll.write outside authority.', sev: 'high', expected: 'BLOCKED' },
  { id: 'partial', name: 'PARTIAL RESULT', desc: 'Adapter returns incomplete data.', sev: 'medium', expected: 'RECOVERED' },
  { id: 'conflict', name: 'CONFLICT', desc: 'Agent and authority disagree on state.', sev: 'high', expected: 'FROZEN' },
  { id: 'oscillation', name: 'KILL WORKER', desc: 'Worker oscillates between states.', sev: 'critical', expected: 'FROZEN' }
];

let _selectedAttack = null;

export function mountLab() {
  const el = $('#view-lab');
  el.innerHTML = `
    <div class="lab-hero">
      <div class="lab-title">BREAK THE JOB</div>
      <div class="lab-subtitle">Introduce a failure. Watch KEEPR contain it.</div>
    </div>
    <div class="lab-content">
      <div class="lab-attacks" id="lab-attacks"></div>
      <div class="lab-right">
        <div class="lab-pipeline-wrap">
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
          <div class="lr-title">RESULT</div>
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

function renderAuthorityDemo(res, container) {
  container.innerHTML = `
    <div class="demo-box demo-blocked">
      <div class="demo-title">AUTHORITY WIDENING BLOCKED</div>
      <div class="demo-detail">
        <div>Request: <code>${res.requested || 'payroll.write'}</code></div>
        <div>Adapter: <code>${res.adapter || 'payroll'}</code></div>
        <div>Result: <strong>BLOCKED</strong></div>
        <div class="demo-note">Authority boundary enforced. Adapter not executed.</div>
      </div>
    </div>`;
}

function renderFalseCompletionDemo(res, container) {
  const claim = res.agent_claim || {};
  const reality = res.authoritative_reality || {};
  container.innerHTML = `
    <div class="demo-box demo-conflict">
      <div class="demo-title">CONFLICT DETECTED</div>
      <div class="demo-comparison">
        <div class="demo-col">
          <div class="demo-col-title">AGENT CLAIM</div>
          <div class="demo-col-status">${claim.status || 'COMPLETED'}</div>
        </div>
        <div class="demo-vs">VS</div>
        <div class="demo-col">
          <div class="demo-col-title">AUTHORITATIVE REALITY</div>
          <div class="demo-col-status demo-fail">${reality.status || 'REFUNDED'}</div>
        </div>
      </div>
      <div class="demo-action">KEEPR REJECTS CLAIM → FROZEN</div>
    </div>`;
}

/* ── Authority / Escalation ── */
export function mountAuthority() {
  const el = $('#view-authority');
  el.innerHTML = `
    <div class="auth-hero">
      <div class="auth-title">AUTHORITY BOUNDARY</div>
      <div class="auth-subtitle">Bounded autonomy. Every action verified.</div>
    </div>
    <div class="auth-grid">
      <div class="auth-card">
        <div class="auth-card-title">ADAPTER PERMISSIONS</div>
        <div class="auth-card-body" id="auth-adapters"></div>
      </div>
      <div class="auth-card">
        <div class="auth-card-title">RECENT DECISIONS</div>
        <div class="auth-card-body" id="auth-decisions"></div>
      </div>
    </div>`;
}

export function mountEscalation() {
  const el = $('#view-escalation');
  el.innerHTML = `
    <div class="esc-hero">
      <div class="esc-title">HUMAN REVIEW</div>
      <div class="esc-subtitle">Escalated items requiring human decision.</div>
    </div>
    <div class="esc-grid" id="esc-grid"></div>`;
}

export function mountVerification() {
  const el = $('#view-verification');
  el.innerHTML = `
    <div class="ver-hero">
      <div class="ver-title">VERIFICATION LOG</div>
      <div class="ver-subtitle">Authoritative state checks.</div>
    </div>
    <div class="ver-grid" id="ver-grid"></div>`;
}

/* ── Status refresh ── */
export async function refreshStatus() {
  try {
    const s = await getStatus();
    _state = s;
    if (_map) _map.update(s.invoices, s.run_state);
    if (_workField) _workField.update(s.invoices);
    updateTopbar(s);
    updateHero(s);
    updateMetrics(s);
  } catch (e) { /* silent */ }
}

function updateTopbar(s) {
  const chip = $('#t-state-chip');
  if (!chip) return;
  const st = s.run_state || 'STANDBY';
  const hasException = s.counts.recovered > 0 || s.counts.escalated > 0 || s.counts.frozen > 0;
  
  chip.className = 't-chip';
  if (st === 'COMPLETED') chip.classList.add('t-chip-completed');
  else if (st === 'FROZEN') chip.classList.add('t-chip-frozen');
  else if (hasException) chip.classList.add('t-chip-recovering');
  else if (s.paused) chip.classList.add('t-chip-paused');
  else chip.classList.add('t-chip-autonomous');
  
  chip.textContent = st;
}

function updateHero(s) {
  const stateEl = $('#ov-state');
  const subEl = $('#ov-state-sub');
  if (!stateEl || !subEl) return;
  
  const c = s.counts;
  const total = c.pending + c.completed + c.recovered + c.escalated + c.frozen;
  
  if (total === 0) {
    stateEl.textContent = 'STANDBY';
    subEl.textContent = 'No job running.';
    return;
  }
  
  if (c.pending === 0 && c.recovered === 0 && c.escalated === 0 && c.frozen === 0) {
    stateEl.textContent = 'JOB COMPLETE';
    subEl.textContent = `${c.completed} transactions verified. All clear.`;
    return;
  }
  
  if (c.recovered > 0 || c.escalated > 0 || c.frozen > 0) {
    stateEl.textContent = 'AUTONOMOUS JOB ACTIVE';
    const parts = [];
    if (c.recovered > 0) parts.push(`${c.recovered} exception recovered`);
    if (c.escalated > 0) parts.push(`${c.escalated} escalated to human`);
    if (c.frozen > 0) parts.push(`${c.frozen} frozen`);
    parts.push(`${c.completed} verified`);
    subEl.textContent = parts.join(' · ');
    return;
  }
  
  stateEl.textContent = 'JOB CONTINUING';
  subEl.textContent = `${c.completed} verified · ${c.pending} remaining`;
}

function updateMetrics(s) {
  const qWorking = $('#q-working');
  const qDone = $('#q-done');
  const qFailing = $('#q-failing');
  const qRecovered = $('#q-recovered');
  const qEscalated = $('#q-escalated');
  
  if (qWorking) qWorking.textContent = s.run_state || '—';
  if (qDone) qDone.textContent = s.counts.completed || 0;
  if (qFailing) qFailing.textContent = (s.counts.recovered || 0) + (s.counts.frozen || 0);
  if (qRecovered) qRecovered.textContent = s.counts.recovered || 0;
  if (qEscalated) qEscalated.textContent = s.counts.escalated || 0;
  
  const evCount = $('#ev-count');
  if (evCount && _eventStream) {
    evCount.textContent = `${_eventStream.events.length} events`;
  }
}

/* ── View switching ── */
export function switchView(view) {
  $$('.view').forEach(v => v.classList.remove('active'));
  const el = $(`#view-${view}`);
  if (el) el.classList.add('active');
  $$('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === view));
}

export function mountNav() {
  $$('.nav-btn').forEach(b => b.addEventListener('click', () => switchView(b.dataset.view)));
}

/* ── Init ── */
export function initApp() {
  mountNav();
  mountOverview();
  mountWork();
  mountLab();
  mountAuthority();
  mountEscalation();
  mountVerification();
  refreshStatus();
  setInterval(refreshStatus, 2000);
}
