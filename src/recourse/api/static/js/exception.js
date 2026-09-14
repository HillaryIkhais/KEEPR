/* ── Active Exception Panel — focused failure lifecycle ── */

export class ExceptionPanel {
  constructor(container) {
    this.container = container;
    this.active = null;
    this.lifecycle = [];
    this.phaseIndex = 0;
    this.lastUpdate = 0;
  }

  show(exception) {
    if (!exception || (this.active && this.active.iid === exception.iid && this.active.state === exception.state)) {
      return;
    }
    
    this.active = exception;
    this.lifecycle = this._buildLifecycle(exception.state);
    this.phaseIndex = 0;
    this.lastUpdate = Date.now();
    this._render();
  }

  hide() {
    this.active = null;
    this.lifecycle = [];
    this.container.innerHTML = '';
  }

  _buildLifecycle(state) {
    const phases = [
      { label: 'FAILURE', color: '#FF0044', icon: '!' },
      { label: 'ISOLATING', color: '#FF2D78', icon: '~' },
      { label: 'CLASSIFYING', color: '#9B30FF', icon: '?' },
      { label: 'RECOVERY', color: '#9B30FF', icon: '>' },
      { label: 'VERIFYING', color: '#D4A843', icon: '.' },
      { label: 'VERIFIED', color: '#1A8C3E', icon: '+' }
    ];

    const stateMap = {
      'FAILED': 0,
      'CLASSIFYING': 2,
      'RECOVERY_SELECTED': 3,
      'RECOVERY_ACTIVE': 3,
      'VERIFYING_RECOVERY': 4,
      'VERIFIED': 5
    };

    const activeIdx = stateMap[state] || 0;
    return phases.map((p, i) => ({
      ...p,
      active: i === activeIdx,
      completed: i < activeIdx,
      pending: i > activeIdx
    }));
  }

  _render() {
    if (!this.active) return;

    const ex = this.active;
    const html = `
      <div class="exception-panel">
        <div class="exception-header">
          <span class="exception-label">ACTIVE EXCEPTION</span>
          <span class="exception-iid">${ex.iid.toUpperCase()}</span>
        </div>
        <div class="exception-mode">${ex.mode || 'SERVICE FAILURE'}</div>
        <div class="exception-lifecycle">
          ${this.lifecycle.map((phase, i) => `
            <div class="lifecycle-phase ${phase.active ? 'active' : ''} ${phase.completed ? 'completed' : ''} ${phase.pending ? 'pending' : ''}">
              <div class="phase-indicator" style="background: ${phase.completed ? phase.color : phase.active ? phase.color : '#333'}">
                ${phase.completed ? phase.icon : phase.active ? phase.icon : ''}
              </div>
              <div class="phase-label">${phase.label}</div>
              ${i < this.lifecycle.length - 1 ? '<div class="phase-connector"></div>' : ''}
            </div>
          `).join('')}
        </div>
        <div class="exception-status">
          ${this._statusText(ex.state)}
        </div>
      </div>
    `;

    this.container.innerHTML = html;
  }

  _statusText(state) {
    const texts = {
      'FAILED': 'ISOLATING TRANSACTION',
      'CLASSIFYING': 'ANALYZING FAILURE',
      'RECOVERY_SELECTED': 'EXECUTING RECOVERY',
      'RECOVERY_ACTIVE': 'RECOVERY IN PROGRESS',
      'VERIFYING_RECOVERY': 'VERIFYING AUTHORITATIVE STATE',
      'VERIFIED': 'TRANSACTION VERIFIED'
    };
    return texts[state] || 'PROCESSING';
  }
}
