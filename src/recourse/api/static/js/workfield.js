/* ── Living Workflow — animated invoice nodes ── */
export class WorkField {
  constructor(container) {
    this.container = container;
    this.nodes = [];
    this.canvas = document.createElement('canvas');
    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');
    this.W = 0; this.H = 0;
    this.time = 0;
    this.lastStatus = {};
    this.recoveryTimes = {};
    
    this._resize();
    window.addEventListener('resize', () => this._resize());
    this._animate();
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

  _animate() {
    this.time += 0.04;
    this._draw();
    requestAnimationFrame(() => this._animate());
  }

  update(invoices) {
    const invs = invoices || {};
    const now = Date.now();
    const newNodes = [];
    
    for (const [iid, info] of Object.entries(invs)) {
      const status = this._normalizeStatus(info.status, info.attempts);
      const prev = this.lastStatus[iid];
      const existing = this.nodes.find(n => n.iid === iid);
      
      // Track recovery start
      if (info.attempts > 0 && prev && prev.status !== status && status === 'VERIFIED') {
        this.recoveryTimes[iid] = now;
      }
      
      // Show KEEPR for 2 seconds after recovery
      let displayStatus = status;
      if (status === 'VERIFIED' && info.attempts > 0 && this.recoveryTimes[iid]) {
        const timeSinceRecovery = now - this.recoveryTimes[iid];
        if (timeSinceRecovery < 2000) {
          displayStatus = 'KEEPR';
        } else {
          delete this.recoveryTimes[iid];
        }
      }
      
      const idx = this.nodes.indexOf(existing) !== -1 ? 
                  this.nodes.indexOf(existing) : Object.keys(invs).indexOf(iid);
      
      newNodes.push({
        iid,
        idx,
        status: displayStatus,
        attempts: info.attempts || 0,
        x: existing ? existing.x : this._targetX(idx, displayStatus),
        y: existing ? existing.y : this._targetY(displayStatus, idx),
        justChanged: prev && prev.status !== status
      });
    }
    
    this.nodes = newNodes;
    this.lastStatus = Object.fromEntries(
      Object.entries(invs).map(([iid, info]) => [
        iid, { status: this._normalizeStatus(info.status, info.attempts) }
      ])
    );
  }

  _normalizeStatus(st, attempts) {
    if (st === 'COMPLETED' && attempts > 0) return 'VERIFIED';
    if (st === 'COMPLETED') return 'VERIFIED';
    if (st === 'PENDING') return 'PENDING';
    if (st === 'ESCALATED') return 'ESCALATED';
    if (st === 'FROZEN') return 'FROZEN';
    return 'PROCESSING';
  }

  _targetX(idx, status) {
    const zones = {
      PENDING: 0.12,
      PROCESSING: 0.28,
      KEEPR: 0.56,
      VERIFIED: 0.84,
      RECOVERED: 0.84,
      ESCALATED: 0.02,
      FROZEN: 0.92
    };
    const baseX = this.W * (zones[status] || zones.PENDING);
    const jiggle = Math.sin(this.time * 0.5 + idx) * 6;
    return baseX + jiggle;
  }

  _targetY(status, idx) {
    if (status === 'ESCALATED' || status === 'FROZEN') {
      return this.H * 0.75 + (idx % 10) * 22;
    }
    return 120 + (idx % 15) * 24;
  }

  _draw() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.W, this.H);
    
    ctx.fillStyle = '#0A0A0A';
    ctx.fillRect(0, 0, this.W, this.H);

    ctx.fillStyle = '#888888';
    ctx.font = 'bold 13px JetBrains Mono';
    ctx.fillText('QUEUE', 40, 45);
    ctx.fillText('FETCHING', this.W * 0.28, 45);
    ctx.fillText('KEEPING', this.W * 0.56, 45);
    ctx.fillText('VERIFY', this.W * 0.82, 45);
    ctx.fillText('VERIFIED', this.W - 90, 45);

    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 1;
    for (let i = 1; i < 5; i++) {
      const x = this.W * (0.15 + i * 0.17);
      ctx.beginPath();
      ctx.moveTo(x, 60);
      ctx.lineTo(x, this.H - 40);
      ctx.stroke();
    }

    for (const n of this.nodes) {
      const targetX = this._targetX(n.idx, n.status);
      const targetY = this._targetY(n.status, n.idx);
      
      n.x += (targetX - n.x) * 0.25;
      n.y += (targetY - n.y) * 0.25;

      const colors = {
        PENDING: '#7A7A7A',
        PROCESSING: '#FF4D00',
        KEEPR: '#7B2FD6',
        VERIFIED: '#00B050',
        RECOVERED: '#00FF88',
        ESCALATED: '#FFB000',
        FROZEN: '#FF003C'
      };
      const color = colors[n.status] || colors.PENDING;

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.roundRect(n.x - 8, n.y - 8, 16, 16, 3);
      ctx.fill();

      if (n.status === 'KEEPR' || n.status === 'PROCESSING') {
        ctx.shadowColor = color;
        ctx.shadowBlur = 15;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.roundRect(n.x - 10, n.y - 10, 20, 20, 3);
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    }
  }
}
