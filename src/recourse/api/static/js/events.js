/* ── Live Event Stream — real-time events with visual emphasis ── */

export class EventStream {
  constructor(container) {
    this.container = container;
    this.events = [];
    this.maxEvents = 12;
  }

  addEvent(type, iid, detail, state) {
    const event = {
      id: Date.now() + Math.random(),
      type,
      iid: iid ? iid.toUpperCase() : null,
      detail,
      state,
      ts: new Date(),
      opacity: 1,
      isNew: true
    };

    this.events.unshift(event);
    if (this.events.length > this.maxEvents) {
      this.events.pop();
    }

    setTimeout(() => {
      event.isNew = false;
    }, 1500);

    this._render();
  }

  _render() {
    const html = `
      <div class="event-stream">
        <div class="stream-header">LIVE EVENT STREAM</div>
        <div class="stream-events">
          ${this.events.map(e => `
            <div class="stream-event ${e.isNew ? 'new' : ''} ${e.type}">
              <div class="event-time">${this._formatTime(e.ts)}</div>
              <div class="event-entity">${e.iid || 'KEEPR'}</div>
              <div class="event-detail">${e.detail}</div>
              ${e.state ? `<div class="event-state">${e.state}</div>` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    `;

    this.container.innerHTML = html;
  }

  _formatTime(date) {
    return date.toTimeString().slice(0, 8);
  }
}
