/* ── Living Workflow — animated invoice nodes with KEEPR intervention ── */

export class WorkField {
  constructor(container, opts = {}) {
    this.container = container;
    this.onSelect = opts.onSelect || (() => {});
    this.nodes = [];
    this.canvas = null;
    this.ctx = null;
    this._running = false;
    this._particles = [];
    this._time = 0;
    this._lastStatus = {};
    this._init();
    this._render();
  }

  _init() {
    this.canvas = document.createElement('canvas');
    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');
    this._resize();
    window.addEventListener('resize', () => this._resize());
    this.canvas.addEventListener('click', e => this._onClick(e));
  }

  _resize() {
    const dpr = Math.min(devicePixelRatio, 2);
    const w = this.container.clientWidth;
    const h = Math.min(520, Math.max(360, w * 0.5));
    this.W = w; this.H = h;
    this.canvas.width = w * dpr;
    this.canvas.height = h * dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  _render() {
    if (this._running) return;
    this._running = true;
    const loop = () => {
      this._time += 0.016;
      this._draw();
      requestAnimationFrame(loop);
    };
    loop();
  }

  _draw() {
    const ctx = this.ctx, W = this.W, H = this.H;
    ctx.clearRect(0, 0, W, H);
    
    const t = this._time;
    
    /* Background */
    const bg = ctx.createLinearGradient(0, 0, 0, H);
    bg.addColorStop(0, '#0A0A0A');
    bg.addColorStop(1, '#000000');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    /* Zone labels */
    ctx.fillStyle = 'rgba(255,255,255,0.6)';
    ctx.font = '12px JetBrains Mono';
    ctx.fillText('QUEUE', 40, 40);
    ctx.fillText('FETCHING', W * 0.28, 40);
    ctx.fillText('KEEPING', W * 0.56, 40);
    ctx.fillText('VERIFY', W * 0.82, 40);
    ctx.fillText('VERIFIED', W - 70, 40);

    /* Particles */
    for (let i = 0; i < 8; i++) {
      const py = 60 + Math.sin(t * 0.5 + i) * 10;
      ctx.strokeStyle = `rgba(255,255,255,${0.03 + Math.sin(t + i) * 0.02})`;
      ctx.beginPath();
      ctx.moveTo(i * W / 8, py);
      ctx.lineTo(i * W / 8, H - 40);
      ctx.stroke();
    }

    /* Nodes */
    for (const n of this.nodes) {
      this._drawNode(n, t);
    }

    /* Connection flow lines */
    this._drawFlow();
  }

  _drawNode(n, t) {
    const ctx = this.ctx;
    const { x, y, status, iid, attempts } = n;
    
    const targetY = this._targetY(status);
    const targetX = this._targetX(n.idx, status);
    
    n.x += (targetX - n.x) * 0.12;
    n.y += (targetY - n.y) * 0.12;

    /* State colors */
    const colors = {
      PENDING: '#7A7A7A',
      PROCESSING: '#FF4D00',
      KEEPR: '#7B2FD6',
      VERIFIED: '#00B050',
      RECOVERED: '#00B050',
      ESCALATED: '#FFB000',
      FROZEN: '#FF003C'
    };
    const color = colors[status] || colors.PENDING;

    /* Glow */
    if (status === 'KEEPR' || status === 'PROCESSING') {
      const glow = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, 30);
      glow.addColorStop(0, `${color}40`);
      glow.addColorStop(1, 'transparent');
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(n.x, n.y, 30, 0, Math.PI * 2);
      ctx.fill();
    }

    /* Node */
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.roundRect(n.x - 7, n.y - 7, 14, 14, 3);
    ctx.fill();

    /* Border */
    ctx.strokeStyle = status === 'FROZEN' ? '#FF003C' : 
                      status === 'ESCALATED' ? '#FFB000' : color;
    ctx.lineWidth = status === 'KEEPR' || status === 'FROZEN' ? 2 : 1;
    ctx.beginPath();
    ctx.roundRect(n.x - 7, n.y - 7, 14, 14, 3);
    ctx.stroke();

    /* Invoice ID */
    if (status !== 'PENDING') {
      ctx.fillStyle = 'rgba(255,255,255,0.8)';
      ctx.font = '9px JetBrains Mono';
      ctx.textAlign = 'center';
      ctx.fillText(iid.split('_')[1], n.x, n.y + 22);
    }
  }

  _drawFlow() {
    const ctx = this.ctx;
    const W = this.W;
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    for (let i = 0; i < 5; i++) {
      const x = W * (0.15 + i * 0.18);
      ctx.beginPath();
      ctx.moveTo(x, 50);
      ctx.lineTo(x, this.H - 50);
      ctx.stroke();
    }
  }

  _targetX(idx, status) {
    const zones = {
      PENDING: 0.08,
      PROCESSING: 0.28,
      KEEPR: 0.56,
      VERIFIED: 0.88,
      RECOVERED: 0.88,
      ESCALATED: 0.02,
      FROZEN: 0.02
    };
    const baseX = this.W * (zones[status] || zones.PENDING);
    const jiggle = Math.sin(this._time * 0.5 + idx) * 8;
    return baseX + jiggle;
  }

  _targetY(status, idx) {
    if (status === 'ESCALATED' || status === 'FROZEN') {
      return this.H * 0.78 + (idx % 8) * 25;
    }
    const baseY = 140 + (idx % 12) * 28;
    return baseY;
  }

  update(statuses) {
    const invs = statuses || {};
    const now = Array.from(Object.values(invs));
    
    this.nodes = Object.entries(invs).map(([iid, info], i) => {
      const prev = this._lastStatus[iid];
      const status = this._normalizeStatus(info.status, info.attempts);
      const existing = this.nodes?.find(n => n.iid === iid);
      
      const prevStatus = prev?.status;
      const changed = prevStatus && prevStatus !== status;
      
      return {
        iid, idx: i, status, attempts: info.attempts || 0,
        x: existing ? existing.x : this._targetX(i, status),
        y: existing ? existing.y : this._targetY(status, i),
        justChanged: changed,
        changedAt: changed ? this._time : 0
      };
    });

    this._lastStatus = Object.fromEntries(
      Object.entries(invs).map(([iid, info]) => [
        iid, { status: this._normalizeStatus(info.status, info.attempts) }
      ])
    );
  }

  _normalizeStatus(st, attempts) {
    if (st === 'COMPLETED' && attempts > 0) return 'RECOVERED';
    if (st === 'COMPLETED') return 'VERIFIED';
    if (st === 'PENDING') return 'PENDING';
    if (st === 'ESCALATED') return 'ESCALATED';
    if (st === 'FROZEN') return 'FROZEN';
    return 'PROCESSING';
  }

  _onClick(e) {
    // placeholder
  }

  destroy() {}
}
