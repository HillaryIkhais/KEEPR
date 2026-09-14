/* ── Per-invoice forensic trace drawer ── */
import { classifyEvent } from './actors.js';

const overlay = document.getElementById('drawer-overlay');
const drawer = document.getElementById('drawer');
const title = document.getElementById('drawer-title');
const meta = document.getElementById('drawer-meta');
const timeline = document.getElementById('drawer-timeline');
const closeBtn = document.getElementById('drawer-close');

let isOpen = false;

export function openTrace(iid, invoice) {
  title.textContent = iid;
  meta.innerHTML = '';
  const fields = [
    ['Amount', invoice.amount ? `$${invoice.amount.toLocaleString()}` : '—'],
    ['Status', invoice.status || 'PENDING'],
    ['Attempts', String(invoice.attempts || 0)],
    ['Recovery', invoice.recovery_mode || '—'],
  ];
  for (const [label, value] of fields) {
    meta.innerHTML += `<div class="dm-item"><span class="dm-label">${label}</span><span>${value}</span></div>`;
  }

  const trace = invoice.trace || [];
  timeline.innerHTML = '';
  if (trace.length === 0) {
    timeline.innerHTML = '<div class="empty-state">No events recorded yet.</div>';
  } else {
    trace.forEach((ev, i) => {
      const info = classifyEvent(ev.event, ev.detail);
      const div = document.createElement('div');
      div.className = 'tl-event';
      div.style.animationDelay = `${i * 40}ms`;
      div.innerHTML = `
        <div class="tl-dot ${info.actor}"></div>
        <div class="tl-body">
          <div class="tl-actor ${info.actor}">${info.label}</div>
          <div class="tl-text">${ev.state}:${ev.event}</div>
        </div>`;
      timeline.appendChild(div);
    });
  }

  overlay.classList.add('open');
  drawer.classList.add('open');
  isOpen = true;
}

export function closeTrace() {
  overlay.classList.remove('open');
  drawer.classList.remove('open');
  isOpen = false;
}

closeBtn.addEventListener('click', closeTrace);
overlay.addEventListener('click', closeTrace);
document.addEventListener('keydown', e => { if (e.key === 'Escape' && isOpen) closeTrace(); });
