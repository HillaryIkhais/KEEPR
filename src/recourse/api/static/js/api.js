/* ── API client ── */
export async function getStatus() {
  const r = await fetch('/api/worker/status');
  if (!r.ok) throw new Error('status');
  return r.json();
}
export async function runWorker(max) {
  const url = max != null ? `/api/worker/run?max=${max}` : '/api/worker/run';
  const r = await fetch(url, { method: 'POST' });
  if (!r.ok) throw new Error('run');
  return r.json();
}
export async function resetWorker() {
  const r = await fetch('/api/worker/reset', { method: 'POST' });
  return r.json();
}
export async function pauseWorker() {
  const r = await fetch('/api/worker/pause', { method: 'POST' });
  return r.json();
}
export async function resumeWorker() {
  const r = await fetch('/api/worker/resume', { method: 'POST' });
  return r.json();
}
export async function injectFault(invoice_id, mode) {
  const r = await fetch('/api/worker/attack', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ invoice_id, mode })
  });
  return r.json();
}
export async function authorityAttack() {
  const r = await fetch('/api/worker/authority-attack', { method: 'POST' });
  return r.json();
}
export async function falseCompletion() {
  const r = await fetch('/api/worker/false-completion', { method: 'POST' });
  return r.json();
}
export async function oscillation() {
  const r = await fetch('/api/worker/oscillation', { method: 'POST' });
  return r.json();
}
export async function checkHealth() {
  try {
    const r = await fetch('/health');
    return r.ok;
  } catch { return false; }
}
export async function checkLedgerHealth() {
  try {
    const r = await fetch('http://127.0.0.1:8001/ledger/health');
    return r.ok;
  } catch { return false; }
}
