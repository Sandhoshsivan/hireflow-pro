// ── API Client ────────────────────────────────────────────────────────────────
const API = {
  async req(method, url, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (!res.ok) {
      const data = await res.json();
      // Handle upgrade_required globally
      if (data.error === 'upgrade_required') {
        showUpgradeModal(data.message, data.feature);
        throw new Error('upgrade_required');
      }
      throw new Error(data.error || data.message || 'Request failed');
    }
    return res.json();
  },
  get:    url       => API.req('GET', url),
  post:   (url, d)  => API.req('POST', url, d),
  put:    (url, d)  => API.req('PUT', url, d),
  patch:  (url, d)  => API.req('PATCH', url, d),
  delete: url       => API.req('DELETE', url),
};

// ── Upgrade Modal ────────────────────────────────────────────────────────────
window.showUpgradeModal = function(message, feature) {
  // Remove existing modal if any
  document.getElementById('upgrade-modal-overlay')?.remove();

  const featureLabels = {
    app_limit: 'Unlimited Applications',
    ai_assistant: 'AI Career Assistant',
    advanced_analytics: 'Advanced Analytics',
    csv_export: 'CSV Export',
    pipeline_view: 'Pipeline View',
    contacts: 'Contact Tracking',
  };

  const overlay = document.createElement('div');
  overlay.id = 'upgrade-modal-overlay';
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `
    <div class="modal" style="max-width:440px">
      <div class="modal-header">
        <div class="modal-title">Upgrade Required</div>
        <button class="btn btn-ghost btn-icon btn-sm" onclick="this.closest('.modal-overlay').remove()">&#10005;</button>
      </div>
      <div class="modal-body" style="text-align:center;padding:28px 24px">
        <div style="font-size:48px;margin-bottom:12px">🔒</div>
        <div style="font-size:15px;font-weight:600;margin-bottom:8px">${featureLabels[feature] || 'Premium Feature'}</div>
        <div style="font-size:13px;color:var(--text2);line-height:1.6;margin-bottom:20px">${message || 'This feature requires a paid plan.'}</div>
        <div style="display:flex;gap:8px;justify-content:center">
          <a href="/pricing" class="btn btn-primary" style="min-width:140px;justify-content:center">View Plans</a>
          <button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">Maybe Later</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
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
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
    document.getElementById('upgrade-modal-overlay')?.remove();
  }
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
    window._userPlan = stats.plan || 'free';
    window._planLimits = stats.plan_limits || {};

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

    // Show pro badge for gated nav items
    updateNavGating(stats.plan);
  } catch(e) {}
};

// ── Nav gating: show lock icons for premium features ─────────────────────────
function updateNavGating(plan) {
  if (plan !== 'free') return;
  const gatedLinks = {
    '/ai-assistant': 'ai_assistant',
    '/pipeline': 'pipeline_view',
    '/api/export/csv': 'csv_export',
  };
  document.querySelectorAll('.nav-item[href]').forEach(a => {
    const href = a.getAttribute('href');
    if (gatedLinks[href]) {
      // Add PRO badge
      if (!a.querySelector('.nav-pro-badge')) {
        const badge = document.createElement('span');
        badge.className = 'nav-pro-badge';
        badge.textContent = 'PRO';
        a.appendChild(badge);
      }
    }
  });
}
