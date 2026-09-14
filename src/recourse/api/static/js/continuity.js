/* ── Continuity Map — living transaction visualization ── */

const COLORS = {
  PENDING: '#555555',
  PROCESSING: '#E8700A',
  VERIFYING: '#D4A843',
  KEEPR: '#9B30FF',
  VERIFIED: '#1A8C3E',
  RECOVERING: '#FF2D78',
  FROZEN: '#CC0000',
  ESCALATED: '#FFB800',
  FAILED: '#FF0044',
  IDLE: '#333333'
};

const STATES = {
  PENDING: 'PENDING',
  FETCHING: 'FETCHING',
  PROCESSING: 'PROCESSING',
  VERIFYING: 'VERIFYING',
  KEEPR: 'KEEPR',
  CLASSIFYING: 'CLASSIFYING',
  RECOVERY_SELECTED: 'RECOVERY_SELECTED',
  RECOVERY_ACTIVE: 'RECOVERY_ACTIVE',
  VERIFYING_RECOVERY: 'VERIFYING_RECOVERY',
  VERIFIED: 'VERIFIED',
  FAILED: 'FAILED',
  FROZEN: 'FROZEN',
  ESCALATED: 'ESCALATED',
  IDLE: 'IDLE'
};

export class ContinuityMap {
  constructor(container) {
    this.container = container;
    this.canvas = document.createElement('canvas');
    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');
    this.W = 0;
    this.H = 0;
    this.time = 0;
    this.nodes = [];
    this.events = [];
    this.lastStatus = {};
    this.activeException = null;
    this.recoveryStartTime = {};
    
    this._resize();
    window.addEventListener('resize', () => this._resize());
    this._animate();
  }

  _resize() {
    const dpr = Math.min(devicePixelRatio, 2);
    const w = this.container.clientWidth;
    const h = Math.min(600, Math.max(400, w * 0.55));
    this.W = w;
    this.H = h;
    this.canvas.width = w * dpr;
    this.canvas.height = h * dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  _animate() {
    this.time += 0.02;
    this._draw();
    requestAnimationFrame(() => this._animate());
  }

  update(invoices, runState) {
    const invs = invoices || {};
    const now = Date.now();
    const newNodes = [];

    for (const [iid, info] of Object.entries(invs)) {
      const state = this._deriveState(info.status, info.attempts, runState);
      const prev = this.lastStatus[iid];
      const existing = this.nodes.find(n => n.iid === iid);
      
      const idx = this.nodes.indexOf(existing) !== -1
        ? this.nodes.indexOf(existing)
        : Object.keys(invs).indexOf(iid);

      if (existing) {
        const targetX = this._targetX(idx, state);
        const targetY = this._targetY(state, idx);
        
        const speed = state === STATES.KEEPR || state === STATES.FAILED ? 0.08 : 0.12;
        existing.x += (targetX - existing.x) * speed;
        existing.y += (targetY - existing.y) * speed;
        
        if (existing.state !== state) {
          existing.prevState = existing.state;
          existing.state = state;
          existing.stateChangedAt = now;
          existing.flash = true;
          
          if (state === STATES.FAILED || state === STATES.CLASSIFYING || state === STATES.RECOVERY_ACTIVE) {
            if (!this.recoveryStartTime[iid]) {
              this.recoveryStartTime[iid] = now;
            }
          }
          
          if (state === STATES.VERIFIED) {
            delete this.recoveryStartTime[iid];
          }
          
          if (state === STATES.FAILED || state === STATES.CLASSIFYING) {
            this.activeException = {
              iid,
              mode: info.recovery_mode || 'UNKNOWN',
              state,
              startedAt: now
            };
          }
          
          if (state === STATES.VERIFIED && this.activeException && this.activeException.iid === iid) {
            setTimeout(() => {
              if (this.activeException && this.activeException.iid === iid) {
                this.activeException = null;
              }
            }, 3000);
          }
        }
        
        existing.idx = idx;
        existing.attempts = info.attempts || 0;
        existing.state = state;
        existing.flash = existing.flash && (now - existing.stateChangedAt < 400);
      } else {
        newNodes.push({
          iid,
          idx,
          state,
          attempts: info.attempts || 0,
          x: this._targetX(idx, state),
          y: this._targetY(state, idx),
          flash: false,
          prevState: null,
          stateChangedAt: now
        });
      }
    }

    if (newNodes.length > 0) {
      this.nodes.push(...newNodes);
    }

    this.nodes = this.nodes.filter(n => invs[n.iid]);
    
    this.lastStatus = Object.fromEntries(
      Object.entries(invs).map(([iid, info]) => [
        iid, { status: info.status, attempts: info.attempts }
      ])
    );
  }

  addEvent(event) {
    this.events.unshift({
      ...event,
      ts: Date.now(),
      opacity: 1
    });
    if (this.events.length > 20) {
      this.events.pop();
    }
  }

  _deriveState(status, attempts, runState) {
    if (status === 'PENDING') return STATES.PENDING;
    if (status === 'ESCALATED') return STATES.ESCALATED;
    if (status === 'FROZEN') return STATES.FROZEN;
    if (status === 'COMPLETED' && attempts > 0) return STATES.VERIFIED;
    if (status === 'COMPLETED') return STATES.VERIFIED;
    if (status === 'PROCESSING') {
      if (runState === 'CLASSIFYING') return STATES.CLASSIFYING;
      if (runState === 'RECOVERY_SELECTED') return STATES.RECOVERY_SELECTED;
      if (runState === 'RECOVERY_ACTIVE') return STATES.RECOVERY_ACTIVE;
      if (runState === 'VERIFYING') return STATES.VERIFYING_RECOVERY;
      return STATES.PROCESSING;
    }
    return STATES.PENDING;
  }

  _targetX(idx, state) {
    const lanes = {
      [STATES.PENDING]: 0.06,
      [STATES.FETCHING]: 0.18,
      [STATES.PROCESSING]: 0.32,
      [STATES.VERIFYING]: 0.46,
      [STATES.KEEPR]: 0.50,
      [STATES.CLASSIFYING]: 0.50,
      [STATES.RECOVERY_SELECTED]: 0.54,
      [STATES.RECOVERY_ACTIVE]: 0.58,
      [STATES.VERIFYING_RECOVERY]: 0.66,
      [STATES.VERIFIED]: 0.88,
      [STATES.FAILED]: 0.50,
      [STATES.FROZEN]: 0.94,
      [STATES.ESCALATED]: 0.02,
      [STATES.IDLE]: 0.06
    };
    const baseX = this.W * (lanes[state] || 0.06);
    const jitter = Math.sin(this.time * 0.7 + idx * 0.3) * 3;
    return baseX + jitter;
  }

  _targetY(state, idx) {
    const mainFlow = this.H * 0.45;
    const recoveryZone = this.H * 0.78;
    const escalatedZone = this.H * 0.15;
    const frozenZone = this.H * 0.90;

    if (state === STATES.KEEPR || state === STATES.CLASSIFYING || 
        state === STATES.RECOVERY_SELECTED || state === STATES.RECOVERY_ACTIVE ||
        state === STATES.VERIFYING_RECOVERY || state === STATES.FAILED) {
      return recoveryZone + (idx % 8) * 18;
    }
    if (state === STATES.ESCALATED) return escalatedZone + (idx % 5) * 20;
    if (state === STATES.FROZEN) return frozenZone;
    return mainFlow + (idx % 12) * 16 - 90;
  }

  _draw() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.W, this.H);

    ctx.fillStyle = '#0D0D0D';
    ctx.fillRect(0, 0, this.W, this.H);

    this._drawZones(ctx);
    this._drawTransactions(ctx);
    this._drawEventPulses(ctx);
    this._drawActiveException(ctx);
  }

  _drawZones(ctx) {
    const mainY = this.H * 0.45;
    const recoveryY = this.H * 0.72;
    const h = 120;

    ctx.fillStyle = 'rgba(255,255,255,0.02)';
    ctx.fillRect(this.W * 0.04, mainY - h/2, this.W * 0.92, h);

    ctx.fillStyle = 'rgba(155,48,255,0.04)';
    ctx.fillRect(this.W * 0.44, recoveryY - 30, this.W * 0.24, 100);

    ctx.strokeStyle = '#222222';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    
    ctx.beginPath();
    ctx.moveTo(this.W * 0.14, mainY - h/2);
    ctx.lineTo(this.W * 0.14, mainY + h/2);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(this.W * 0.28, mainY - h/2);
    ctx.lineTo(this.W * 0.28, mainY + h/2);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(this.W * 0.42, mainY - h/2);
    ctx.lineTo(this.W * 0.42, mainY + h/2);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(this.W * 0.80, mainY - h/2);
    ctx.lineTo(this.W * 0.80, mainY + h/2);
    ctx.stroke();
    
    ctx.setLineDash([]);

    ctx.fillStyle = '#444444';
    ctx.font = '11px JetBrains Mono';
    ctx.fillText('QUEUE', this.W * 0.04, mainY - h/2 - 8);
    ctx.fillText('FETCH', this.W * 0.18, mainY - h/2 - 8);
    ctx.fillText('PROCESS', this.W * 0.32, mainY - h/2 - 8);
    ctx.fillText('VERIFY', this.W * 0.46, mainY - h/2 - 8);
    ctx.fillText('VERIFIED', this.W * 0.82, mainY - h/2 - 8);

    ctx.fillStyle = '#6B2FA0';
    ctx.fillText('KEEPR CONTROL PLANE', this.W * 0.46, recoveryY - 38);

    if (this.activeException) {
      ctx.strokeStyle = '#FF2D78';
      ctx.lineWidth = 2;
      ctx.strokeRect(this.W * 0.44 - 2, recoveryY - 32, this.W * 0.24 + 4, 104);
    }
  }

  _drawTransactions(ctx) {
    for (const n of this.nodes) {
      const color = COLORS[n.state] || COLORS.IDLE;
      const size = n.state === STATES.KEEPR || n.state === STATES.CLASSIFYING ||
                   n.state === STATES.RECOVERY_ACTIVE ? 10 : 7;

      ctx.fillStyle = color;
      ctx.fillRect(n.x - size/2, n.y - size/2, size, size);

      if (n.state === STATES.PROCESSING || n.state === STATES.FETCHING) {
        const pulse = 0.5 + Math.sin(this.time * 2 + n.idx * 0.5) * 0.5;
        ctx.fillStyle = `rgba(232, 112, 10, ${pulse * 0.3})`;
        ctx.fillRect(n.x - size/2 - 2, n.y - size/2 - 2, size + 4, size + 4);
      }

      if (n.state === STATES.KEEPR || n.state === STATES.CLASSIFYING ||
          n.state === STATES.RECOVERY_ACTIVE) {
        const pulse = 0.5 + Math.sin(this.time * 3 + n.idx) * 0.5;
        ctx.strokeStyle = `rgba(155, 48, 255, ${0.4 + pulse * 0.4})`;
        ctx.lineWidth = 2;
        ctx.strokeRect(n.x - size/2 - 3, n.y - size/2 - 3, size + 6, size + 6);
      }

      if (n.state === STATES.FAILED) {
        const pulse = 0.5 + Math.sin(this.time * 4) * 0.5;
        ctx.fillStyle = `rgba(255, 0, 68, ${0.2 + pulse * 0.3})`;
        ctx.fillRect(n.x - 16, n.y - 16, 32, 32);
      }

      if (n.flash) {
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2;
        ctx.strokeRect(n.x - size/2 - 1, n.y - size/2 - 1, size + 2, size + 2);
      }

      if (n.state === STATES.FROZEN) {
        ctx.strokeStyle = '#CC0000';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(n.x - 6, n.y - 6);
        ctx.lineTo(n.x + 6, n.y + 6);
        ctx.moveTo(n.x + 6, n.y - 6);
        ctx.lineTo(n.x - 6, n.y + 6);
        ctx.stroke();
      }

      if (n.state === STATES.ESCALATED) {
        ctx.strokeStyle = '#FFB800';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(n.x, n.y, size/2 + 4, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
  }

  _drawEventPulses(ctx) {
    const now = Date.now();
    for (let i = this.events.length - 1; i >= 0; i--) {
      const e = this.events[i];
      const age = now - e.ts;
      if (age > 5000) {
        this.events.splice(i, 1);
        continue;
      }
      e.opacity = Math.max(0, 1 - age / 5000);
    }
  }

  _drawActiveException(ctx) {
    if (!this.activeException) return;

    const ex = this.activeException;
    const age = Date.now() - ex.startedAt;
    const fadeIn = Math.min(1, age / 300);

    const x = this.W * 0.04;
    const y = this.H * 0.04;
    const w = this.W * 0.36;
    const h = 80;

    ctx.fillStyle = `rgba(255, 0, 68, ${0.08 * fadeIn})`;
    ctx.fillRect(x, y, w, h);

    ctx.strokeStyle = `rgba(255, 45, 120, ${0.6 * fadeIn})`;
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);

    ctx.fillStyle = `rgba(255, 255, 255, ${0.9 * fadeIn})`;
    ctx.font = 'bold 12px JetBrains Mono';
    ctx.fillText('ACTIVE EXCEPTION', x + 12, y + 20);

    ctx.fillStyle = `rgba(255, 45, 120, ${0.9 * fadeIn})`;
    ctx.font = 'bold 14px JetBrains Mono';
    ctx.fillText(ex.iid.toUpperCase(), x + 12, y + 40);

    ctx.fillStyle = `rgba(255, 255, 255, ${0.7 * fadeIn})`;
    ctx.font = '11px JetBrains Mono';
    ctx.fillText(ex.mode || 'SERVICE FAILURE', x + 12, y + 58);

    const stateText = this._stateLabel(ex.state);
    ctx.fillStyle = '#9B30FF';
    ctx.fillText(stateText, x + 12, y + 72);
  }

  _stateLabel(state) {
    const labels = {
      [STATES.FAILED]: 'FAILURE DETECTED',
      [STATES.CLASSIFYING]: 'CLASSIFYING',
      [STATES.RECOVERY_SELECTED]: 'RECOVERY SELECTED',
      [STATES.RECOVERY_ACTIVE]: 'RECOVERY IN PROGRESS',
      [STATES.VERIFYING_RECOVERY]: 'VERIFYING RECOVERY',
      [STATES.KEEPR]: 'KEEPR INTERVENING'
    };
    return labels[state] || state;
  }
}
