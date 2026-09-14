/* ── Work field canvas — 50 invoice nodes flowing through KEEPR pipeline ── */
const COLORS = {
  COMPLETED: '#0E8A3E', RECOVERED: '#0E8A3E', PENDING: '#b0ad9f',
  ESCALATED: '#D99E00', FROZEN: '#7B2FD6', FAILED: '#E03E4A', PROCESSING: '#FF4D00'
};

export class WorkField {
  constructor(container, opts = {}) {
    this.onSelect = opts.onSelect || (() => {});
    this.onHover = opts.onHover || (() => {});
    this.large = opts.large || false;
    this.wrap = container;
    this.canvas = document.createElement('canvas');
    this.wrap.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');
    this.nodes = [];
    this.selectedIid = null;
    this._resize();
    this._boundResize = () => this._resize();
    window.addEventListener('resize', this._boundResize);
    this.canvas.addEventListener('mousemove', e => this._onMouseMove(e));
    this.canvas.addEventListener('mouseleave', () => this.onHover(null));
    this.canvas.addEventListener('click', e => this._onClick(e));
  }

  _resize() {
    const dpr = Math.min(devicePixelRatio, 2);
    const w = this.wrap.clientWidth;
    const h = this.large ? Math.min(380, Math.max(260, w * 0.4)) : Math.min(280, Math.max(180, w * 0.45));
    this.wrap.style.height = h + 'px';
    this.W = w; this.H = h;
    this.canvas.width = w * dpr; this.canvas.height = h * dpr;
    this.canvas.style.width = w + 'px'; this.canvas.style.height = h + 'px';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this._layoutNodes();
  }

  _layoutNodes() {
    const W = this.W, H = this.H;
    const zones = this.large
      ? [{ x1: 0, x2: .16, label: 'QUEUE' }, { x1: .16, x2: .34, label: 'ACTION' },
         { x1: .34, x2: .58, label: 'KEEPR' }, { x1: .58, x2: .76, label: 'VERIFY' },
         { x1: .76, x2: .92, label: 'VERIFIED' }]
      : [{ x1: 0, x2: .18, label: 'QUEUE' }, { x1: .18, x2: .38, label: 'ACTION' },
         { x1: .38, x2: .62, label: 'KEEPR' }, { x1: .62, x2: .82, label: 'VERIFY' },
         { x1: .82, x2: 1, label: 'VERIFIED' }];
    this.zones = zones;
    const escZone = { x1: .82, y1: .02, x2: .98, y2: .2, label: 'ESCALATED' };
    const fzZone = { x1: .02, y1: .78, x2: .18, y2: .98, label: 'FROZEN' };
    this.escZone = escZone; this.fzZone = fzZone;

    for (const n of this.nodes) {
      const pos = this._targetPos(n);
      if (!n._initialized) { n.x = pos.x; n.y = pos.y; n._initialized = true; }
      n.tx = pos.x; n.ty = pos.y;
    }
  }

  _targetPos(n) {
    const W = this.W, H = this.H, pad = this.large ? 32 : 24;
    const status = n.status || 'PENDING';
    const idx = n.idx || 0;

    if (status === 'ESCALATED') {
      const z = this.escZone;
      const col = idx % 6, row = Math.floor(idx / 6);
      return { x: (z.x1 + .02 + col * .025) * W, y: (z.y1 + .08 + row * .06) * H };
    }
    if (status === 'FROZEN') {
      const z = this.fzZone;
      const col = idx % 6, row = Math.floor(idx / 6);
      return { x: (z.x1 + .02 + col * .025) * W, y: (z.y1 + .08 + row * .06) * H };
    }
    // Zone-based target for other states
    let zone;
    if (status === 'COMPLETED' || status === 'RECOVERED') zone = this.zones[4];
    else if (status === 'PENDING') zone = this.zones[0];
    else zone = this.zones[2]; // active/recovering → center

    const x1 = zone.x1 * W + pad, x2 = zone.x2 * W - pad;
    const y1 = pad + 10, y2 = H - pad - 10;
    const cols = Math.ceil(Math.sqrt(50 * (x2 - x1) / (y2 - y1)));
    const rows = Math.ceil(50 / cols);
    const col = idx % cols, row = Math.floor(idx / cols);
    return {
      x: x1 + (col + .5) * ((x2 - x1) / cols),
      y: y1 + (row + .5) * ((y2 - y1) / Math.min(rows, 12))
    };
  }

  update(statuses) {
    const invs = statuses || {};
    this.nodes = Object.entries(invs).map(([iid, info], i) => {
      const existing = this.nodes.find(n => n.iid === iid);
      const prevAttempts = existing ? existing.attempts : 0;
      const prevStatus = existing ? existing.status : '';
      const newAttempts = info.attempts || 0;
      const flash = newAttempts > prevAttempts || (prevStatus !== info.status && info.status !== 'PENDING');
      return {
        iid, idx: i, status: info.status || 'PENDING', attempts: newAttempts,
        amount: info.amount || 0, recovery_mode: info.recovery_mode,
        x: existing ? existing.x : 0, y: existing ? existing.y : 0,
        tx: 0, ty: 0, flash: flash ? 1 : (existing ? existing.flash * .94 : 0),
        _initialized: existing ? existing._initialized : false
      };
    });
    this._layoutNodes();
    this._draw();
  }

  _draw() {
    const ctx = this.ctx, W = this.W, H = this.H;
    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = '#faf9f6';
    ctx.fillRect(0, 0, W, H);

    // Zone backgrounds
    for (const z of this.zones) {
      ctx.fillStyle = 'rgba(0,0,0,.015)';
      ctx.fillRect(z.x1 * W, 0, (z.x2 - z.x1) * W, H);
      ctx.fillStyle = 'rgba(0,0,0,.25)';
      ctx.font = `600 ${this.large ? 9 : 7}px 'JetBrains Mono',monospace`;
      ctx.textAlign = 'center';
      ctx.fillText(z.label, ((z.x1 + z.x2) / 2) * W, H - 8);
    }

    // Escalated zone
    ctx.fillStyle = 'rgba(217,158,0,.04)';
    ctx.fillRect(this.escZone.x1 * W, this.escZone.y1 * H,
      (this.escZone.x2 - this.escZone.x1) * W, (this.escZone.y2 - this.escZone.y1) * H);
    ctx.strokeStyle = 'rgba(217,158,0,.15)';
    ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
    ctx.strokeRect(this.escZone.x1 * W, this.escZone.y1 * H,
      (this.escZone.x2 - this.escZone.x1) * W, (this.escZone.y2 - this.escZone.y1) * H);
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(217,158,0,.4)';
    ctx.font = `600 ${this.large ? 9 : 7}px 'JetBrains Mono',monospace`;
    ctx.textAlign = 'center';
    ctx.fillText(this.escZone.label, ((this.escZone.x1 + this.escZone.x2) / 2) * W,
      this.escZone.y1 * H + 14);

    // Frozen zone
    ctx.fillStyle = 'rgba(123,47,214,.04)';
    ctx.fillRect(this.fzZone.x1 * W, this.fzZone.y1 * H,
      (this.fzZone.x2 - this.fzZone.x1) * W, (this.fzZone.y2 - this.fzZone.y1) * H);
    ctx.strokeStyle = 'rgba(123,47,214,.15)';
    ctx.setLineDash([3, 3]);
    ctx.strokeRect(this.fzZone.x1 * W, this.fzZone.y1 * H,
      (this.fzZone.x2 - this.fzZone.x1) * W, (this.fzZone.y2 - this.fzZone.y1) * H);
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(123,47,214,.4)';
    ctx.fillText(this.fzZone.label, ((this.fzZone.x1 + this.fzZone.x2) / 2) * W,
      this.fzZone.y1 * H + 14);

    // Pipeline arrows (faint)
    ctx.strokeStyle = 'rgba(0,0,0,.06)';
    ctx.lineWidth = 1;
    for (let i = 0; i < this.zones.length - 1; i++) {
      const x = this.zones[i].x2 * W;
      ctx.beginPath(); ctx.moveTo(x, H / 2 - 6); ctx.lineTo(x + 12, H / 2); ctx.lineTo(x, H / 2 + 6); ctx.stroke();
    }

    // Nodes
    const r = this.large ? 6 : 5;
    for (const n of this.nodes) {
      // Animate toward target
      n.x += (n.tx - n.x) * .1;
      n.y += (n.ty - n.y) * .1;

      const color = COLORS[n.status] || COLORS.PENDING;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();

      // Flash ring
      if (n.flash > .05) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, r + 4 * n.flash, 0, Math.PI * 2);
        ctx.strokeStyle = color;
        ctx.globalAlpha = n.flash * .5;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.globalAlpha = 1;
        n.flash *= .94;
      }

      // Selected ring
      if (n.iid === this.selectedIid) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, r + 3, 0, Math.PI * 2);
        ctx.strokeStyle = '#FF4D00';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Frozen lock icon
      if (n.status === 'FROZEN') {
        ctx.fillStyle = '#fff';
        ctx.font = `bold ${r + 2}px 'JetBrains Mono',monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('⊘', n.x, n.y);
      }
    }
  }

  _onMouseMove(e) {
    const rect = this.canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const r = this.large ? 8 : 6;
    let hit = null;
    for (const n of this.nodes) {
      if (Math.hypot(n.x - mx, n.y - my) < r + 4) { hit = n; break; }
    }
    this.onHover(hit ? {
      iid: hit.iid, x: e.clientX, y: e.clientY,
      status: hit.status, amount: hit.amount, attempts: hit.attempts,
      recovery_mode: hit.recovery_mode
    } : null);
  }

  _onClick(e) {
    const rect = this.canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const r = this.large ? 8 : 6;
    for (const n of this.nodes) {
      if (Math.hypot(n.x - mx, n.y - my) < r + 4) {
        this.selectedIid = n.iid;
        this.onSelect(n.iid);
        this._draw();
        return;
      }
    }
  }

  destroy() {
    window.removeEventListener('resize', this._boundResize);
    this.canvas.remove();
  }
}
