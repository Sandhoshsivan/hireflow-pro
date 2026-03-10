// ── API Client ────────────────────────────────────────────────────────────────
const API = {
  async req(method, url, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error((await res.json()).error || 'Request failed');
    return res.json();
  },
  get:    url       => API.req('GET', url),
  post:   (url, d)  => API.req('POST', url, d),
  put:    (url, d)  => API.req('PUT', url, d),
  patch:  (url, d)  => API.req('PATCH', url, d),
  delete: url       => API.req('DELETE', url),
};

// ── Toast ─────────────────────────────────────────────────────────────────────
(function() {
  const wrap = document.createElement('div');
  wrap.className = 'toast-wrap';
  document.body.appendChild(wrap);

  window.toast = function(msg, type = 'success', duration = 3000) {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    const icons = { success: '✓', error: '✕', info: 'ℹ', warn: '⚠' };
    el.innerHTML = `<span>${icons[type] || '✓'}</span><span>${msg}</span>`;
    wrap.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 350);
    }, duration);
  };
})();

// ── Modal ─────────────────────────────────────────────────────────────────────
window.Modal = {
  open(id)  { document.getElementById(id)?.classList.add('open'); },
  close(id) { document.getElementById(id)?.classList.remove('open'); },
};
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
});

// ── Drawer ────────────────────────────────────────────────────────────────────
window.Drawer = {
  open(id)  {
    document.getElementById(id + '-overlay')?.classList.add('open');
    document.getElementById(id)?.classList.add('open');
  },
  close(id) {
    document.getElementById(id + '-overlay')?.classList.remove('open');
    document.getElementById(id)?.classList.remove('open');
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────
window.fmtDate = d => {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' });
};

window.daysAgo = d => {
  if (!d) return 99999;
  return Math.floor((Date.now() - new Date(d)) / 86400000);
};

window.badge = status => {
  return `<span class="badge badge-${status}">${status}</span>`;
};

window.pDot = priority => {
  const map = { high: 'p-high', medium: 'p-medium', low: 'p-low' };
  return `<span class="priority-dot ${map[priority] || 'p-medium'}"></span>`;
};

window.avatarColor = name => {
  const c = ['#2563EB','#059669','#D97706','#7C3AED','#DC2626','#0891B2','#EC4899'];
  let h = 0; for (let ch of (name||'X')) h = (h * 31 + ch.charCodeAt(0)) % c.length;
  return c[h];
};

// ── Active nav ────────────────────────────────────────────────────────────────
(function() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item[href]').forEach(a => {
    if (a.getAttribute('href') === path || (path.endsWith('/') && a.getAttribute('href') === '/dashboard')) {
      a.classList.add('active');
    }
  });
})();

// ── Stats loader (shared) ─────────────────────────────────────────────────────
window.loadNavCounts = async () => {
  try {
    const stats = await API.get('/api/stats');
    const map = { 'nav-cnt-all': stats.total, 'nav-cnt-interview': stats.interview,
                  'nav-cnt-offer': stats.offer, 'nav-cnt-applied': stats.applied };
    for (const [id, val] of Object.entries(map)) {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    }
    // Follow-up alert in sidebar
    const fuEl = document.getElementById('sidebar-followups');
    if (fuEl && stats.followups?.length) {
      fuEl.style.display = 'block';
      fuEl.innerHTML = `<div class="followup-card">
        <div class="followup-title">⏰ Follow-ups Due (${stats.followups.length})</div>
        ${stats.followups.map(f => `<div class="followup-item" onclick="window.location='/applications?open=${f.id}'">📌 ${f.company} — ${f.role}</div>`).join('')}
      </div>`;
    }
  } catch(e) {}
};
