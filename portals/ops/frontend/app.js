/* ====================================================================
   TAP — Live Ops Portal  |  app.js
   Plain HTML + vanilla JS. No build step. No bundler.

   Three screens:
     1. Tickets table (default)
     2. Ticket detail panel (slide-in)
     3. Bot audit dock (right-side toggle)

   TODO: replace MOCK_* constants with live API calls once
         GET /api/tickets/ and GET /api/audit/recent are deployed.
         Tracked in THE-17304 (Backend sibling).
   ==================================================================== */

'use strict';

/* ===================================================================
   CONFIG
   =================================================================== */

const API_BASE        = '';           // relative to origin — FastAPI serves at same host
const REFRESH_MS      = 60_000;       // 60s auto-refresh
const TOAST_DURATION  = 3_000;        // 3s auto-dismiss
const USE_MOCK        = true;         // TODO: set false once THE-17304 backend is live

/* ===================================================================
   MOCK DATA
   TODO: remove when backend is deployed (THE-17304)
   =================================================================== */

const MOCK_TICKETS = [
  {
    id: 'T-0001', tenant: 'Lee Wei Ming',  property: '18 Jln Jintan',
    category: 'Plumbing', service: 'Maintenance', area: 'Room 3A',
    priority: 'high', status: 'open',
    age_hours: 36, last_update: ago(36), last_action_by: 'bot',
    bot_pending: true, assignee: 'Faisal',
  },
  {
    id: 'T-0002', tenant: 'Sarah Tan',     property: '18 Penhas Rd',
    category: 'Electrical', service: 'Maintenance', area: 'Common Area',
    priority: 'mid', status: 'in_progress',
    age_hours: 4, last_update: ago(4), last_action_by: 'Erwan',
    bot_pending: false, assignee: 'Erwan',
  },
  {
    id: 'T-0003', tenant: 'Ravi Kumar',    property: 'TLKR Block A',
    category: 'Noise complaint', service: 'Operations', area: 'Floor 2',
    priority: 'low', status: 'new',
    age_hours: 2, last_update: ago(2), last_action_by: 'system',
    bot_pending: false, assignee: '',
  },
  {
    id: 'T-0004', tenant: 'Aisha Ibrahim', property: '51 Middle Rd',
    category: 'Air-con', service: 'Maintenance', area: 'Room 7B',
    priority: 'high', status: 'open',
    age_hours: 200, last_update: ago(200), last_action_by: 'bot',
    bot_pending: true, assignee: 'Thomas',
  },
  {
    id: 'T-0005', tenant: 'James Lim',     property: 'TLKR Block B',
    category: 'Internet', service: 'Technical', area: 'Room 12C',
    priority: 'mid', status: 'resolved',
    age_hours: 20, last_update: ago(20), last_action_by: 'Muhammad',
    bot_pending: false, assignee: 'Muhammad',
  },
  {
    id: 'T-0006', tenant: 'Priya Nair',    property: '18 Jln Jintan',
    category: 'Lease query', service: 'Admin', area: 'Room 5A',
    priority: 'low', status: 'closed',
    age_hours: 800, last_update: ago(800), last_action_by: 'Faisal',
    bot_pending: false, assignee: 'Faisal',
  },
];

const MOCK_DETAIL = {
  'T-0001': {
    id: 'T-0001', tenant: 'Lee Wei Ming', property: '18 Jln Jintan',
    category: 'Plumbing', priority: 'high', status: 'open',
    history: [
      { id: 'h1', type: 'message',     author: 'Lee Wei Ming', ts: ago(36),
        content: 'Hi, there is water leaking from the sink pipe in my bathroom. The floor is wet.' },
      { id: 'h2', type: 'status',      author: 'system',       ts: ago(35),
        from: 'new', to: 'open' },
      { id: 'h3', type: 'bot_sent',    author: 'TAP Bot',      ts: ago(35),
        content: 'Hi Lee Wei Ming, thank you for letting us know. We have logged your request and will arrange for a technician to inspect as soon as possible.' },
      { id: 'h4', type: 'note',        author: 'Faisal',       ts: ago(10),
        content: 'Called tenant — leaking is manageable but gets worse in mornings. Scheduling Thomas for tomorrow AM.' },
      { id: 'h5', type: 'bot_draft',   author: 'TAP Bot',      ts: ago(1),
        content: 'Hi Lee Wei Ming, our technician Thomas will visit tomorrow between 9 AM and 12 PM to fix the leaking pipe. Please ensure the bathroom is accessible. Let us know if you have any questions.',
        status: 'pending' },
    ],
    bot_draft: 'Hi Lee Wei Ming, our technician Thomas will visit tomorrow between 9 AM and 12 PM to fix the leaking pipe. Please ensure the bathroom is accessible. Let us know if you have any questions.',
  },
  'T-0002': {
    id: 'T-0002', tenant: 'Sarah Tan', property: '18 Penhas Rd',
    category: 'Electrical', priority: 'mid', status: 'in_progress',
    history: [
      { id: 'h1', type: 'message',  author: 'Sarah Tan', ts: ago(4),
        content: 'The power socket in the common area near the kitchen is sparking. It looks dangerous.' },
      { id: 'h2', type: 'status',   author: 'system',    ts: ago(4),
        from: 'new', to: 'in_progress' },
      { id: 'h3', type: 'comment',  author: 'Erwan',     ts: ago(3),
        content: 'Isolating the socket now. Will replace the outlet today. Tenants informed not to use until fixed.' },
    ],
    bot_draft: null,
  },
};

const MOCK_AUDIT = Array.from({ length: 20 }, (_, i) => ({
  id: `A-${String(i + 1).padStart(3, '0')}`,
  ticket_id: MOCK_TICKETS[i % MOCK_TICKETS.length].id,
  rule: ['auto-acknowledge', 'sentiment-high', 'sla-breach-warn', 'draft-followup', 'escalation-detect'][i % 5],
  tier: (i % 3) + 1,
  action: [
    'Sent acknowledgement to tenant within SLA window.',
    'Flagged high-sentiment message for priority escalation.',
    'Sent SLA breach warning to assignee.',
    'Generated follow-up draft for approval.',
    'Detected escalation keywords — routed to Faisal.',
  ][i % 5],
  ts: ago(i * 2 + 1),
}));

/* ===================================================================
   STATE
   =================================================================== */

const state = {
  tickets:          [],
  filteredTickets:  [],
  selectedTicketId: null,
  selectedDetail:   null,
  auditActions:     [],
  filteredAudit:    [],
  isLoading:        true,
  loadError:        null,
  detailOpen:       false,
  auditOpen:        false,
  refreshTimer:     null,
  countdownTimer:   null,
  nextRefreshAt:    null,
  sortCol:          'age_hours',
  sortAsc:          false,
  filters: {
    service:  '',
    priority: '',
    status:   '',
    property: '',
    area:     '',
    assignee: '',
    search:   '',
  },
  auditFilters: { ticket: '', rule: '', tier: '' },
};

/* ===================================================================
   HELPERS
   =================================================================== */

function ago(hours) {
  return new Date(Date.now() - hours * 3_600_000).toISOString();
}

function fmtAge(hours) {
  if (hours < 1)        return `${Math.round(hours * 60)}m`;
  if (hours < 24)       return `${Math.round(hours)}h`;
  const days = Math.floor(hours / 24);
  return days === 1 ? '1d' : `${days}d`;
}

function ageClass(hours) {
  if (hours < 24)  return 'age-fresh';
  if (hours < 168) return 'age-normal';
  if (hours < 720) return 'age-warn';
  return 'age-crit';
}

function fmtRelTime(iso) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60)    return 'just now';
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function qs(sel, root = document) { return root.querySelector(sel); }
function qsa(sel, root = document) { return [...root.querySelectorAll(sel)]; }

function show(el) { el?.classList.remove('hidden'); }
function hide(el) { el?.classList.add('hidden'); }

function getCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/* ===================================================================
   API LAYER
   =================================================================== */

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (res.status === 401) {
    showAuthPage();
    throw new Error('Session expired — please sign in again.');
  }
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}${body ? `: ${body}` : ''}`);
  }
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : res.text();
}

async function fetchTickets() {
  if (USE_MOCK) {
    await new Promise(r => setTimeout(r, 400));
    return { tickets: MOCK_TICKETS };
  }
  const params = new URLSearchParams();
  const f = state.filters;
  if (f.service)  params.set('service',  f.service);
  if (f.priority) params.set('priority', f.priority);
  if (f.status)   params.set('status',   f.status);
  if (f.property) params.set('property', f.property);
  if (f.area)     params.set('area',     f.area);
  if (f.assignee) params.set('assignee', f.assignee);
  if (f.search)   params.set('q',        f.search);
  return apiFetch(`/api/tickets/?${params}`);
}

async function fetchTicketDetail(id) {
  if (USE_MOCK) {
    await new Promise(r => setTimeout(r, 200));
    return MOCK_DETAIL[id] ?? { id, tenant: id, property: '', category: '',
      priority: 'low', status: 'open', history: [], bot_draft: null };
  }
  return apiFetch(`/api/tickets/${encodeURIComponent(id)}`);
}

async function fetchAudit() {
  if (USE_MOCK) {
    await new Promise(r => setTimeout(r, 150));
    return { actions: MOCK_AUDIT };
  }
  return apiFetch('/api/audit/recent');
}

async function postComment(id, text) {
  if (USE_MOCK) { await new Promise(r => setTimeout(r, 300)); return { ok: true }; }
  return apiFetch(`/api/tickets/${encodeURIComponent(id)}/comment`,
    { method: 'POST', body: JSON.stringify({ content: text }) });
}

async function postNote(id, text) {
  if (USE_MOCK) { await new Promise(r => setTimeout(r, 300)); return { ok: true }; }
  return apiFetch(`/api/tickets/${encodeURIComponent(id)}/comment_internal`,
    { method: 'POST', body: JSON.stringify({ content: text }) });
}

async function postStatus(id, newStatus) {
  if (USE_MOCK) { await new Promise(r => setTimeout(r, 300)); return { ok: true }; }
  return apiFetch(`/api/tickets/${encodeURIComponent(id)}/status`,
    { method: 'POST', body: JSON.stringify({ status: newStatus }) });
}

async function postApproveDraft(id) {
  if (USE_MOCK) { await new Promise(r => setTimeout(r, 300)); return { ok: true }; }
  return apiFetch(`/api/tickets/${encodeURIComponent(id)}/approve_draft`, { method: 'POST' });
}

async function postEditAndSend(id, editedText) {
  if (USE_MOCK) { await new Promise(r => setTimeout(r, 300)); return { ok: true }; }
  return apiFetch(`/api/tickets/${encodeURIComponent(id)}/edit_and_send`,
    { method: 'POST', body: JSON.stringify({ content: editedText }) });
}

async function requestMagicLink(email) {
  if (USE_MOCK) { await new Promise(r => setTimeout(r, 600)); return { ok: true }; }
  return apiFetch(`/auth/magic-link?email=${encodeURIComponent(email)}`);
}

/* ===================================================================
   TOAST
   =================================================================== */

function toast(msg, type = 'info') {
  const container = qs('#toast-container');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.setAttribute('role', 'status');
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add('out');
    el.addEventListener('animationend', () => el.remove(), { once: true });
  }, TOAST_DURATION);
}

/* ===================================================================
   AUTH PAGE
   =================================================================== */

function showAuthPage() {
  hide(qs('#app'));
  show(qs('#auth-page'));
  qs('#auth-email')?.focus();
}

function showApp() {
  hide(qs('#auth-page'));
  show(qs('#app'));
}

function isAuthenticated() {
  if (USE_MOCK) return true;
  return Boolean(getCookie('tap_session'));
}

function initAuth() {
  const sendBtn = qs('#btn-send-magic-link');
  const emailIn = qs('#auth-email');

  sendBtn.addEventListener('click', async () => {
    const email = emailIn.value.trim();
    if (!email) { emailIn.focus(); return; }
    hide(qs('#auth-error'));
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sending…';
    try {
      await requestMagicLink(email);
      show(qs('#auth-sent'));
      emailIn.disabled = true;
    } catch (err) {
      const errEl = qs('#auth-error');
      errEl.textContent = err.message || 'Failed to send magic link. Try again.';
      show(errEl);
    } finally {
      sendBtn.disabled = false;
      sendBtn.textContent = 'Send magic link';
    }
  });

  emailIn.addEventListener('keydown', e => {
    if (e.key === 'Enter') sendBtn.click();
  });
}

/* ===================================================================
   FILTER HELPERS
   =================================================================== */

function applyFilters() {
  const f = state.filters;
  const q = f.search.toLowerCase();

  state.filteredTickets = state.tickets.filter(t => {
    if (f.service  && t.service  !== f.service)  return false;
    if (f.priority && t.priority !== f.priority)  return false;
    if (f.status   && t.status   !== f.status)    return false;
    if (f.property && t.property !== f.property)  return false;
    if (f.area     && t.area     !== f.area)       return false;
    if (f.assignee && t.assignee !== f.assignee)   return false;
    if (q && !`${t.id} ${t.tenant} ${t.category} ${t.property} ${t.area}`.toLowerCase().includes(q)) return false;
    return true;
  });

  sortTickets();
}

function sortTickets() {
  const col = state.sortCol;
  const asc = state.sortAsc;
  state.filteredTickets.sort((a, b) => {
    let av = a[col] ?? '', bv = b[col] ?? '';
    if (typeof av === 'string') av = av.toLowerCase();
    if (typeof bv === 'string') bv = bv.toLowerCase();
    if (av < bv) return asc ? -1 : 1;
    if (av > bv) return asc ? 1 : -1;
    return 0;
  });
}

function populateFilterOptions() {
  const unique = (key) => [...new Set(state.tickets.map(t => t[key]).filter(Boolean))].sort();

  const fill = (selId, values) => {
    const sel = qs(`#${selId}`);
    if (!sel) return;
    const current = sel.value;
    const first = sel.options[0];
    sel.innerHTML = '';
    sel.appendChild(first.cloneNode(true));
    values.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v; opt.textContent = v;
      sel.appendChild(opt);
    });
    if (current) sel.value = current;
  };

  fill('filter-service',  unique('service'));
  fill('filter-property', unique('property'));
  fill('filter-area',     unique('area'));
  fill('filter-assignee', unique('assignee'));
}

/* ===================================================================
   TICKETS TABLE RENDER
   =================================================================== */

function renderSkeletons() {
  const container = qs('#skeleton-rows');
  container.innerHTML = Array.from({ length: 8 }, () =>
    `<div class="skeleton-row">
      ${[80, 120, 100, 80, 60, 70, 50, 90].map(w =>
        `<div class="skeleton-cell" style="width:${w}px"></div>`
      ).join('')}
    </div>`
  ).join('');
}

function renderTicketsTable() {
  const tbody = qs('#tickets-tbody');
  const tickets = state.filteredTickets;
  const count   = qs('#tickets-count');

  if (count) count.textContent = `${tickets.length} ticket${tickets.length !== 1 ? 's' : ''}`;

  if (tickets.length === 0) {
    tbody.innerHTML = '';
    return;
  }

  /* Smart re-render: only update rows that changed, don't repaint the whole table */
  const existingRows = {};
  qsa('tr[data-id]', tbody).forEach(tr => { existingRows[tr.dataset.id] = tr; });

  const seen = new Set();
  tickets.forEach((t, idx) => {
    seen.add(t.id);
    const html = ticketRowHtml(t);

    if (existingRows[t.id]) {
      /* row exists — update if content changed */
      const existing = existingRows[t.id];
      const newHtml = html;
      if (existing.innerHTML !== newHtml) {
        const tmp = document.createElement('tr');
        tmp.innerHTML = newHtml;
        existing.replaceWith(tmp);
        tmp.dataset.id = t.id;
        if (state.selectedTicketId === t.id) tmp.classList.add('selected');
        attachRowListeners(tmp, t);
      }
    } else {
      /* new row */
      const tr = document.createElement('tr');
      tr.dataset.id = t.id;
      tr.innerHTML = html;
      if (state.selectedTicketId === t.id) tr.classList.add('selected');
      attachRowListeners(tr, t);
      tbody.appendChild(tr);
    }
  });

  /* Remove stale rows */
  qsa('tr[data-id]', tbody).forEach(tr => {
    if (!seen.has(tr.dataset.id)) tr.remove();
  });
}

function ticketRowHtml(t) {
  const ageCls  = ageClass(t.age_hours);
  const prioCls = `prio-${t.priority}`;
  const stCls   = `status-${t.status}`;
  const botCls  = t.bot_pending ? 'bot-yes' : 'bot-no';

  return `
    <td><code>${escHtml(t.id)}</code></td>
    <td class="td-wrap">${escHtml(t.tenant)}</td>
    <td class="td-wrap">${escHtml(t.property)}</td>
    <td>${escHtml(t.category)}</td>
    <td><span class="prio-badge ${prioCls}">${escHtml(t.priority)}</span></td>
    <td><span class="status-badge ${stCls}">${escHtml(t.status.replace('_', ' '))}</span></td>
    <td><span class="age-chip ${ageCls}">${fmtAge(t.age_hours)}</span></td>
    <td>${fmtRelTime(t.last_update)}</td>
    <td class="col-last-action">${escHtml(t.last_action_by || '—')}</td>
    <td><span class="bot-dot ${botCls}">${t.bot_pending ? 'Yes' : 'No'}</span></td>
    <td class="td-actions">
      <button class="btn-action-sm" data-action="open" aria-label="Open ticket ${escHtml(t.id)}">Open</button>
    </td>
  `;
}

function attachRowListeners(tr, t) {
  tr.addEventListener('click', (e) => {
    if (e.target.closest('[data-action]')) return; /* let button handle it */
    openDetailPanel(t.id);
  });
  tr.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDetailPanel(t.id); }
  });
  tr.setAttribute('tabindex', '0');
  tr.setAttribute('role', 'row');

  const openBtn = tr.querySelector('[data-action="open"]');
  if (openBtn) openBtn.addEventListener('click', () => openDetailPanel(t.id));
}

function updateSortHeaders() {
  qsa('.th-sortable').forEach(th => {
    const col = th.dataset.col;
    th.classList.toggle('sorted', col === state.sortCol);
    if (col === state.sortCol) {
      th.setAttribute('aria-sort', state.sortAsc ? 'ascending' : 'descending');
    } else {
      th.setAttribute('aria-sort', 'none');
    }
  });
}

/* ===================================================================
   LOAD / REFRESH CYCLE
   =================================================================== */

async function loadTickets(isRefresh = false) {
  if (!isRefresh) {
    state.isLoading = true;
    state.loadError = null;
    renderLoadingState();
  }

  try {
    const data = await fetchTickets();
    state.tickets = data.tickets ?? [];
    state.isLoading = false;
    state.loadError = null;
    populateFilterOptions();
    applyFilters();
    renderTicketTable_managed();
  } catch (err) {
    state.isLoading = false;
    state.loadError = err.message;
    renderErrorState();
    if (isRefresh) toast(`Auto-refresh failed: ${err.message}`, 'error');
  }
}

function renderLoadingState() {
  hide(qs('#tickets-table'));
  hide(qs('#state-empty'));
  hide(qs('#state-error'));
  show(qs('#state-loading'));
  renderSkeletons();
}

function renderErrorState() {
  hide(qs('#tickets-table'));
  hide(qs('#state-empty'));
  hide(qs('#state-loading'));
  const errEl = qs('#state-error');
  show(errEl);
  qs('#state-error-msg').textContent = state.loadError;
}

function renderTicketTable_managed() {
  hide(qs('#state-loading'));
  hide(qs('#state-error'));

  if (state.filteredTickets.length === 0) {
    hide(qs('#tickets-table'));
    show(qs('#state-empty'));
  } else {
    hide(qs('#state-empty'));
    show(qs('#tickets-table'));
    renderTicketsTable();
    updateSortHeaders();
  }
}

function scheduleRefresh() {
  clearInterval(state.refreshTimer);
  clearInterval(state.countdownTimer);

  state.nextRefreshAt = Date.now() + REFRESH_MS;

  state.refreshTimer = setInterval(async () => {
    await loadTickets(true);
    state.nextRefreshAt = Date.now() + REFRESH_MS;
  }, REFRESH_MS);

  state.countdownTimer = setInterval(() => {
    const el = qs('#refresh-countdown');
    if (!el) return;
    const secs = Math.max(0, Math.round((state.nextRefreshAt - Date.now()) / 1000));
    el.textContent = `Refresh in ${secs}s`;
  }, 1000);
}

/* ===================================================================
   DETAIL PANEL
   =================================================================== */

function openDetailPanel(ticketId) {
  state.selectedTicketId = ticketId;
  const panel = qs('#detail-panel');

  /* Update selected row highlight */
  qsa('tr[data-id]').forEach(tr => tr.classList.toggle('selected', tr.dataset.id === ticketId));

  /* Show panel loading state */
  panel.classList.add('open');
  panel.setAttribute('aria-hidden', 'false');
  state.detailOpen = true;
  qs('#detail-ticket-id').textContent = ticketId;
  qs('#detail-title').textContent = 'Loading…';
  qs('#detail-meta').innerHTML = '';
  qs('#detail-history').innerHTML = renderHistorySkeleton();
  hide(qs('#bot-draft-block'));

  loadDetail(ticketId);
}

async function loadDetail(ticketId) {
  try {
    const detail = await fetchTicketDetail(ticketId);
    state.selectedDetail = detail;
    renderDetailPanel(detail);
  } catch (err) {
    qs('#detail-history').innerHTML =
      `<div class="state-container"><div class="state-icon">⚠️</div>
       <div class="state-title">Failed to load detail</div>
       <div class="state-sub">${escHtml(err.message)}</div></div>`;
  }
}

function renderDetailPanel(detail) {
  qs('#detail-ticket-id').textContent = detail.id;
  qs('#detail-title').textContent = `${detail.tenant} — ${detail.category}`;
  qs('#detail-meta').innerHTML = `
    <span class="prio-badge prio-${detail.priority}">${detail.priority}</span>
    <span class="status-badge status-${detail.status}">${detail.status.replace('_', ' ')}</span>
    <span style="color:var(--text-2);font-size:12px">${escHtml(detail.property)}</span>
  `;

  /* History */
  qs('#detail-history').innerHTML = (detail.history || []).map(renderHistoryEntry).join('');

  /* Bot draft block */
  if (detail.bot_draft) {
    qs('#bot-draft-text').textContent = detail.bot_draft;
    show(qs('#bot-draft-block'));
    hide(qs('#edit-draft-area'));
  } else {
    hide(qs('#bot-draft-block'));
  }

  /* Pre-select current status in the status dropdown */
  const sel = qs('#status-select');
  if (sel && detail.status) sel.value = detail.status;
}

function renderHistoryEntry(h) {
  const typeMap = {
    message:    ['chip-message',   'Tenant'],
    comment:    ['chip-comment',   'Comment'],
    note:       ['chip-note',      'Internal'],
    status:     ['chip-status',    'Status'],
    bot_draft:  ['chip-bot_draft', 'Bot draft'],
    bot_sent:   ['chip-bot_sent',  'Bot sent'],
  };
  const [chipClass, chipLabel] = typeMap[h.type] || ['chip-status', h.type];

  if (h.type === 'status') {
    return `<div class="hist-entry">
      <div class="hist-status-change">
        <span class="hist-type-chip ${chipClass}">${chipLabel}</span>
        <span>${escHtml(h.from)} → ${escHtml(h.to)}</span>
        <span style="margin-left:auto;color:var(--text-3)">${fmtRelTime(h.ts)}</span>
      </div>
    </div>`;
  }

  const isDraft = h.type === 'bot_draft';
  return `<div class="hist-entry">
    <div class="hist-header">
      <span class="hist-author">${escHtml(h.author)}</span>
      <span class="hist-type-chip ${chipClass}">${chipLabel}</span>
      <span class="hist-time">${fmtRelTime(h.ts)}</span>
    </div>
    <div class="hist-body${isDraft ? ' bot-draft' : ''}">${escHtml(h.content)}</div>
  </div>`;
}

function renderHistorySkeleton() {
  return Array.from({ length: 3 }, () =>
    `<div class="hist-entry">
      <div class="skeleton-cell" style="width:200px;height:10px;margin-bottom:6px"></div>
      <div class="skeleton-cell" style="width:100%;height:48px"></div>
    </div>`
  ).join('');
}

function closeDetailPanel() {
  const panel = qs('#detail-panel');
  panel.classList.remove('open');
  panel.setAttribute('aria-hidden', 'true');
  state.detailOpen = false;
  state.selectedTicketId = null;
  state.selectedDetail = null;
  qsa('tr.selected').forEach(tr => tr.classList.remove('selected'));
}

/* Detail panel tab switching */
function initDetailTabs() {
  qsa('.action-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      qsa('.action-tab').forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      qsa('.action-pane').forEach(p => hide(p));
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      show(qs(`#tab-${tab.dataset.tab}`));
    });
  });
}

/* ===================================================================
   DETAIL WRITE ACTIONS (optimistic UI)
   =================================================================== */

async function withOptimistic(btnEl, asyncFn, successMsg) {
  const originalText = btnEl.textContent;
  btnEl.disabled = true;
  btnEl.textContent = 'Sending…';

  const detail = state.selectedDetail;
  /* Snapshot for rollback */
  const snapshotHistory = detail ? [...(detail.history || [])] : null;

  try {
    await asyncFn();
    toast(successMsg, 'success');
    /* Refresh detail panel silently */
    if (state.selectedTicketId) await loadDetail(state.selectedTicketId);
  } catch (err) {
    toast(`Error: ${err.message}`, 'error');
    /* Rollback: restore previous history render */
    if (snapshotHistory && detail) {
      detail.history = snapshotHistory;
      renderDetailPanel(detail);
    }
  } finally {
    btnEl.disabled = false;
    btnEl.textContent = originalText;
  }
}

function initDetailActions() {
  const id = () => state.selectedTicketId;

  /* Post public comment */
  qs('#btn-post-comment').addEventListener('click', async () => {
    const ta   = qs('#comment-textarea');
    const text = ta.value.trim();
    if (!text) { ta.focus(); return; }

    /* Optimistic: add to history immediately */
    const optimisticEntry = {
      id: `opt-${Date.now()}`, type: 'comment',
      author: 'You (sending…)', ts: new Date().toISOString(), content: text,
    };
    if (state.selectedDetail) {
      state.selectedDetail.history.push(optimisticEntry);
      qs('#detail-history').innerHTML = state.selectedDetail.history.map(renderHistoryEntry).join('');
      qs('#detail-history').scrollTop = qs('#detail-history').scrollHeight;
    }
    ta.value = '';

    await withOptimistic(qs('#btn-post-comment'), () => postComment(id(), text), 'Comment posted.');
  });

  /* Post internal note */
  qs('#btn-post-note').addEventListener('click', async () => {
    const ta   = qs('#note-textarea');
    const text = ta.value.trim();
    if (!text) { ta.focus(); return; }
    ta.value = '';
    await withOptimistic(qs('#btn-post-note'), () => postNote(id(), text), 'Internal note posted.');
  });

  /* Change status */
  qs('#btn-change-status').addEventListener('click', async () => {
    const newStatus = qs('#status-select').value;
    await withOptimistic(qs('#btn-change-status'), () => postStatus(id(), newStatus), `Status updated to ${newStatus}.`);
  });

  /* Approve draft */
  qs('#btn-approve-draft').addEventListener('click', async () => {
    await withOptimistic(qs('#btn-approve-draft'), () => postApproveDraft(id()), 'Draft approved and sent.');
  });

  /* Edit draft — show edit area */
  qs('#btn-edit-draft').addEventListener('click', () => {
    const ta = qs('#edit-draft-textarea');
    ta.value = state.selectedDetail?.bot_draft || '';
    show(qs('#edit-draft-area'));
    ta.focus();
  });

  /* Cancel edit */
  qs('#btn-cancel-edit-draft').addEventListener('click', () => {
    hide(qs('#edit-draft-area'));
  });

  /* Send edited draft */
  qs('#btn-send-edited-draft').addEventListener('click', async () => {
    const ta   = qs('#edit-draft-textarea');
    const text = ta.value.trim();
    if (!text) { ta.focus(); return; }
    await withOptimistic(
      qs('#btn-send-edited-draft'),
      () => postEditAndSend(id(), text),
      'Edited draft sent.'
    );
    hide(qs('#edit-draft-area'));
  });
}

/* ===================================================================
   BOT AUDIT DOCK
   =================================================================== */

function applyAuditFilters() {
  const f = state.auditFilters;
  state.filteredAudit = state.auditActions.filter(a => {
    if (f.ticket && !a.ticket_id.toLowerCase().includes(f.ticket.toLowerCase())) return false;
    if (f.rule   && !a.rule.toLowerCase().includes(f.rule.toLowerCase()))        return false;
    if (f.tier   && String(a.tier) !== f.tier)                                   return false;
    return true;
  });
}

function renderAuditList() {
  const list = qs('#audit-list');
  const entries = state.filteredAudit;

  if (!entries.length) {
    list.innerHTML = '<div class="state-container"><div class="state-sub">No audit entries match filters.</div></div>';
    return;
  }

  list.innerHTML = entries.map(a => {
    const hl = state.selectedTicketId === a.ticket_id ? ' highlighted' : '';
    return `<div class="audit-entry${hl}" data-ticket="${escHtml(a.ticket_id)}" tabindex="0" role="button"
                 aria-label="Audit entry for ${escHtml(a.ticket_id)}">
      <div class="audit-entry-header">
        <span class="audit-ticket-id">${escHtml(a.ticket_id)}</span>
        <span class="audit-rule">${escHtml(a.rule)}</span>
        <span class="audit-tier">Tier ${escHtml(String(a.tier))}</span>
      </div>
      <div class="audit-action-text">${escHtml(a.action)}</div>
      <div class="audit-time">${fmtRelTime(a.ts)}</div>
    </div>`;
  }).join('');

  list.querySelectorAll('.audit-entry').forEach(el => {
    const handler = () => {
      const tid = el.dataset.ticket;
      openDetailPanel(tid);
      /* on mobile: close audit dock when opening detail */
      if (window.innerWidth < 768) toggleAuditDock(false);
    };
    el.addEventListener('click', handler);
    el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); } });
  });
}

async function loadAudit() {
  try {
    const data = await fetchAudit();
    state.auditActions = data.actions ?? [];
    applyAuditFilters();
    renderAuditList();
  } catch (err) {
    qs('#audit-list').innerHTML =
      `<div class="state-container"><div class="state-sub">${escHtml(err.message)}</div></div>`;
  }
}

function toggleAuditDock(forceOpen) {
  const dock    = qs('#audit-dock');
  const toggleB = qs('#btn-audit-toggle');
  const isOpen  = typeof forceOpen === 'boolean' ? !forceOpen : dock.classList.contains('open');

  if (isOpen) {
    dock.classList.remove('open');
    dock.setAttribute('aria-hidden', 'true');
    toggleB.classList.remove('active');
    toggleB.setAttribute('aria-pressed', 'false');
    state.auditOpen = false;
  } else {
    dock.classList.add('open');
    dock.setAttribute('aria-hidden', 'false');
    toggleB.classList.add('active');
    toggleB.setAttribute('aria-pressed', 'true');
    state.auditOpen = true;
    loadAudit();
  }
}

function initAuditDock() {
  qs('#btn-audit-toggle').addEventListener('click', () => toggleAuditDock());
  qs('#btn-close-audit').addEventListener('click',  () => toggleAuditDock(false));

  ['#audit-filter-ticket', '#audit-filter-rule'].forEach(sel => {
    qs(sel).addEventListener('input', e => {
      const key = sel.includes('ticket') ? 'ticket' : 'rule';
      state.auditFilters[key] = e.target.value;
      applyAuditFilters();
      renderAuditList();
    });
  });

  qs('#audit-filter-tier').addEventListener('change', e => {
    state.auditFilters.tier = e.target.value;
    applyAuditFilters();
    renderAuditList();
  });
}

/* ===================================================================
   FILTER BAR WIRING
   =================================================================== */

function initFilters() {
  const filterMap = {
    '#filter-service':  'service',
    '#filter-priority': 'priority',
    '#filter-status':   'status',
    '#filter-property': 'property',
    '#filter-area':     'area',
    '#filter-assignee': 'assignee',
  };

  Object.entries(filterMap).forEach(([sel, key]) => {
    qs(sel)?.addEventListener('change', e => {
      state.filters[key] = e.target.value;
      applyFilters();
      renderTicketTable_managed();
    });
  });

  /* Search with 250ms debounce */
  let searchTimer;
  qs('#filter-search').addEventListener('input', e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.filters.search = e.target.value;
      applyFilters();
      renderTicketTable_managed();
    }, 250);
  });

  qs('#btn-clear-filters').addEventListener('click', () => {
    state.filters = { service: '', priority: '', status: '', property: '', area: '', assignee: '', search: '' };
    qsa('#filter-service, #filter-priority, #filter-status, #filter-property, #filter-area, #filter-assignee')
      .forEach(s => s.value = '');
    qs('#filter-search').value = '';
    applyFilters();
    renderTicketTable_managed();
  });

  /* Retry on error */
  qs('#btn-retry').addEventListener('click', () => loadTickets());
}

/* ===================================================================
   SORT HEADER WIRING
   =================================================================== */

function initSortHeaders() {
  qsa('.th-sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (state.sortCol === col) {
        state.sortAsc = !state.sortAsc;
      } else {
        state.sortCol = col;
        state.sortAsc = true;
      }
      sortTickets();
      renderTicketTable_managed();
    });
    th.setAttribute('tabindex', '0');
    th.addEventListener('keydown', e => { if (e.key === 'Enter') th.click(); });
  });
}

/* ===================================================================
   CLOSE PANEL WIRING
   =================================================================== */

function initCloseHandlers() {
  qs('#btn-close-detail').addEventListener('click', closeDetailPanel);

  /* Escape key: close detail first, then audit dock */
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      if (state.detailOpen) { closeDetailPanel(); return; }
      if (state.auditOpen)  { toggleAuditDock(false); }
    }
  });
}

/* ===================================================================
   BOOTSTRAP
   =================================================================== */

async function init() {
  initAuth();

  if (!isAuthenticated()) {
    showAuthPage();
    return;
  }

  showApp();
  initFilters();
  initSortHeaders();
  initDetailTabs();
  initDetailActions();
  initAuditDock();
  initCloseHandlers();

  await loadTickets();
  scheduleRefresh();
}

document.addEventListener('DOMContentLoaded', init);
