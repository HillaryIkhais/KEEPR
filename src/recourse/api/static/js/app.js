/* ── Workspace shell: router, polling, init ── */
import { refreshStatus, mountOverview, mountWork, mountLab,
         mountAuthority, mountVerification, mountEscalations } from './views.js';

const views = { overview: mountOverview, work: mountWork, lab: mountLab,
                authority: mountAuthority, verification: mountVerification, escalations: mountEscalations };
const mounted = new Set();
let activeView = 'overview';

function navigate(view) {
  if (!views[view]) return;
  activeView = view;
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const el = document.getElementById(`view-${view}`);
  if (el) el.classList.add('active');
  if (!mounted.has(view)) { views[view](); mounted.add(view); }
  document.querySelectorAll('.sidenav .nav-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.view === view));
}

document.querySelectorAll('.sidenav .nav-btn').forEach(btn => {
  btn.addEventListener('click', () => navigate(btn.dataset.view));
});

async function poll() {
  try { await refreshStatus(); } catch (e) {}
}

(async () => {
  await poll();
  navigate('overview');
  setInterval(poll, 900);
})();
