/* ── Pipeline counter — replaces canvas dots with stage counters ── */

export class WorkField {
  constructor(container, opts = {}) {
    this.onSelect = opts.onSelect || (() => {});
    this.el = container;
    this._prev = {};
    this._render();
  }

  _render() {
    this.el.innerHTML = `
      <div class="pl">
        <div class="pl-stages">
          <div class="pl-stage" data-stage="queue">
            <div class="pl-count" id="pl-queue">50</div>
            <div class="pl-label">QUEUE</div>
            <div class="pl-dots" id="pl-queue-dots"></div>
          </div>
          <div class="pl-arrow">→</div>
          <div class="pl-stage" data-stage="process">
            <div class="pl-count" id="pl-process">0</div>
            <div class="pl-label">PROCESS</div>
            <div class="pl-dots" id="pl-process-dots"></div>
          </div>
          <div class="pl-arrow">→</div>
          <div class="pl-stage pl-keeper" data-stage="keeper">
            <div class="pl-count" id="pl-keeper">0</div>
            <div class="pl-label">KEEPR</div>
            <div class="pl-dots" id="pl-keeper-dots"></div>
          </div>
          <div class="pl-arrow">→</div>
          <div class="pl-stage" data-stage="done">
            <div class="pl-count" id="pl-done">0</div>
            <div class="pl-label">DONE</div>
            <div class="pl-dots" id="pl-done-dots"></div>
          </div>
        </div>
        <div class="pl-extras" id="pl-extras"></div>
      </div>`;
  }

  update(statuses) {
    const invs = statuses || {};
    let queue = 0, done = 0, recovered = 0, escalated = 0, frozen = 0, processing = 0;

    for (const [, info] of Object.entries(invs)) {
      const s = info.status || 'PENDING';
      if (s === 'PENDING') queue++;
      else if (s === 'COMPLETED') {
        if (info.attempts > 0) recovered++;
        else done++;
      }
      else if (s === 'ESCALATED') escalated++;
      else if (s === 'FROZEN') frozen++;
    }

    const keeperCount = recovered + escalated + frozen;
    const total = queue + done + recovered + escalated + frozen;
    const processed = done + recovered + escalated + frozen;
    processing = Math.min(1, queue);

    this._setCount('pl-queue', queue, this._prev.queue);
    this._setCount('pl-process', processing, this._prev.processing);
    this._setCount('pl-keeper', keeperCount, this._prev.keeper);
    this._setCount('pl-done', done + recovered, this._prev.done);

    this._setDots('pl-queue-dots', queue, 50);
    this._setDots('pl-process-dots', processing, 1);
    this._setDots('pl-keeper-dots', keeperCount, 50);
    this._setDots('pl-done-dots', done + recovered, 50);

    this._prev = { queue, processing, keeper: keeperCount, done: done + recovered };

    const extras = $('#pl-extras');
    if (extras) {
      let html = '';
      if (escalated > 0) html += `<div class="pl-extra pl-esc">${escalated} ESCALATED</div>`;
      if (frozen > 0) html += `<div class="pl-extra pl-fz">${frozen} FROZEN</div>`;
      if (keeperCount === 0 && processed === 0) html += `<div class="pl-extra pl-idle">No exceptions yet</div>`;
      extras.innerHTML = html;
    }

    const keeper = this.el.querySelector('.pl-keeper');
    if (keeper) {
      keeper.classList.toggle('pl-pulse', keeperCount > this._prev.keeper);
    }
  }

  _setCount(id, val, prev) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = val;
    if (prev !== undefined && val !== prev) {
      el.classList.remove('pl-bump');
      void el.offsetWidth;
      el.classList.add('pl-bump');
    }
  }

  _setDots(id, count, max) {
    const el = document.getElementById(id);
    if (!el) return;
    const show = Math.min(count, 20);
    const dots = [];
    for (let i = 0; i < show; i++) dots.push('<span class="pl-dot"></span>');
    if (count > 20) dots.push(`<span class="pl-dot-more">+${count - 20}</span>`);
    el.innerHTML = dots.join('');
  }

  destroy() {}
}

function $(sel, ctx) { return (ctx || document).querySelector(sel); }
