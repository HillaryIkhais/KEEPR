/* ── Trace event actor classification ── */
const PATTERNS = [
  { re: /^action:|OBSERVING|observed:/, actor: 'agent', label: 'AGENT' },
  { re: /^classified:|^policy:|^escalate:|^freeze:|^recovery-bound:|^recovery-blocked:|^RECOVERY_SELECTED:|^OBSERVATION_REJECTED|^REPLAN|^RECOVERY_FAILED/, actor: 'keeper', label: 'KEEPR' },
  { re: /^verify:|^verified:|^recovery-verified:|VERIFIED|VERIFYING/, actor: 'verify', label: 'VERIFY' },
  { re: /^ROLLED_BACK|^ROLLBACK_FAILED|rollback/, actor: 'recovery', label: 'RECOVERY' },
  { re: /^resume:|^continue-after-|^restored-pending:|^start:|^halted|^INCOMPLETE|^DONE_WITH|^done:/, actor: 'system', label: 'SYSTEM' },
  { re: /^failure:|^FAILURE/, actor: 'keeper', label: 'KEEPR' },
];

export function classifyEvent(event, detail) {
  const text = `${event} ${detail || ''}`;
  for (const p of PATTERNS) {
    if (p.re.test(text)) return p;
  }
  return { actor: 'system', label: 'SYSTEM' };
}

export function classifyState(state, event) {
  const text = `${state}:${event}`;
  if (/FAIL|BLOCKED|REJECT/.test(text)) return 'fail';
  if (/COMPLETED|VERIFIED/.test(text)) return 'ok';
  if (/RECOVER|policy:/.test(text)) return 'rec';
  if (/ESCALAT/.test(text)) return 'esc';
  if (/FROZEN|FREEZE/.test(text)) return 'frozen';
  if (/REPLAN|OBSERVATION_REJECTED/.test(text)) return 'fail';
  return '';
}
