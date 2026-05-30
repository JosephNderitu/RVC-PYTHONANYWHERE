/**
 * RiftValley Carriers — Courier Offline Manager v2
 * =================================================
 * File: Truck/static/js/pwa/courier-offline.js
 *
 * Responsibilities:
 *  1. ONLINE  — fetch current job from API, cache to IndexedDB silently
 *  2. OFFLINE — read job from IndexedDB, show blurred bottom-sheet card
 *  3. Card is dismissible (backdrop tap or chevron button)
 *  4. Persistent bottom banner on all courier pages when offline
 *  5. Background sync trigger on reconnect (Phase 4 hook)
 *
 * Depends on: idb.js (must be loaded before this file)
 */

(function () {
  'use strict';

  /* ── Config ───────────────────────────────────────────────── */
  const API_URL  = '/courier/api/jobs/current/json/';
  const STALE_MS = 5 * 60 * 1000;   /* 5 min — warn if cache older than this */

  /* ── Page detection ───────────────────────────────────────── */
  const PAGE = window.location.pathname;
  const isCurrentJob = PAGE.includes('/jobs/current');

  /* ── Inject keyframe animations once ─────────────────────── */
  (function injectStyles() {
    if (document.getElementById('rvc-offline-styles')) return;
    const s = document.createElement('style');
    s.id = 'rvc-offline-styles';
    s.textContent = `
      @keyframes rvc-fade-in {
        from { opacity: 0; }
        to   { opacity: 1; }
      }
      @keyframes rvc-slide-up {
        from { transform: translateY(48px); opacity: 0; }
        to   { transform: translateY(0);    opacity: 1; }
      }
      @keyframes rvc-fade-out {
        from { opacity: 1; }
        to   { opacity: 0; }
      }
      @keyframes rvc-slide-down {
        from { transform: translateY(0);    opacity: 1; }
        to   { transform: translateY(48px); opacity: 0; }
      }
      #rvc-offline-overlay {
        position: fixed; inset: 0; z-index: 8000;
        display: flex; align-items: flex-end; justify-content: center;
        padding-bottom: 80px;
        backdrop-filter: blur(7px);
        -webkit-backdrop-filter: blur(7px);
        background: rgba(11, 15, 26, 0.6);
        animation: rvc-fade-in 0.25s ease forwards;
      }
      #rvc-offline-overlay.dismissing {
        animation: rvc-fade-out 0.2s ease forwards;
      }
      #rvc-offline-card {
        width: calc(100% - 32px);
        max-width: 440px;
        background: var(--rvc-card, #111827);
        border: 1px solid var(--rvc-border-l, #2E3A55);
        border-radius: 22px;
        overflow: hidden;
        box-shadow: 0 28px 70px rgba(0, 0, 0, 0.65);
        animation: rvc-slide-up 0.3s cubic-bezier(0.4, 0, 0.2, 1) forwards;
      }
      #rvc-offline-overlay.dismissing #rvc-offline-card {
        animation: rvc-slide-down 0.2s cubic-bezier(0.4, 0, 0.2, 1) forwards;
      }
      #rvc-offline-body {
        max-height: 58vh;
        overflow-y: auto;
        padding: 0 16px 20px;
        scrollbar-width: thin;
        scrollbar-color: var(--rvc-border-l, #2E3A55) transparent;
      }
      #rvc-offline-body::-webkit-scrollbar { width: 3px; }
      #rvc-offline-body::-webkit-scrollbar-thumb {
        background: var(--rvc-border-l, #2E3A55);
        border-radius: 3px;
      }
      #rvc-offline-banner {
        position: fixed;
        bottom: 68px; left: 12px; right: 12px;
        z-index: 7999;
        border-radius: 10px;
        padding: 10px 14px;
        background: rgba(239, 68, 68, 0.14);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #EF4444;
        font-size: .8rem; font-weight: 600;
        font-family: 'Sora', sans-serif;
        display: none;
        align-items: center;
        gap: 8px;
        animation: rvc-fade-in 0.3s ease;
        cursor: pointer;
      }
      .rvc-addr-card {
        background: var(--rvc-card-l, #1F2937);
        border: 1px solid var(--rvc-border, #1E2840);
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 8px;
      }
      .rvc-addr-row {
        display: flex; gap: 10px; align-items: flex-start;
      }
      .rvc-addr-icon {
        width: 28px; height: 28px; border-radius: 8px;
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0;
      }
      .rvc-stat-grid {
        display: grid; grid-template-columns: repeat(3, 1fr);
        gap: 8px; margin-bottom: 12px;
      }
      .rvc-stat-pill {
        background: var(--rvc-card-l, #1F2937);
        border: 1px solid var(--rvc-border, #1E2840);
        border-radius: 10px; padding: 10px 8px;
        text-align: center;
      }
    `;
    document.head.appendChild(s);
  })();


  /* ══════════════════════════════════════════════════════════
     INIT
  ══════════════════════════════════════════════════════════ */
  document.addEventListener('DOMContentLoaded', function () {
    if (navigator.onLine) {
      refreshJobCache();
    } else {
      showOfflineBanner();
      if (isCurrentJob) injectOfflineCard();
    }

    window.addEventListener('online',  onCameOnline);
    window.addEventListener('offline', onWentOffline);
  });


  /* ══════════════════════════════════════════════════════════
     CACHE REFRESH
  ══════════════════════════════════════════════════════════ */
  async function refreshJobCache() {
    try {
      const res = await fetch(API_URL, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });
      if (!res.ok) {
        if (res.status === 404) {
          await RvcDB.clearJobs();
          console.log('[RVC Offline] No active job — cache cleared');
        }
        return;
      }
      const data = await res.json();
      if (data.success && data.job) {
        await RvcDB.saveJob(data.job);
        console.log('[RVC Offline] Job cached:', data.job.id);
        updateSyncBadge();
      }
    } catch (err) {
      console.log('[RVC Offline] Cache refresh skipped:', err.message);
    }
  }


  /* ══════════════════════════════════════════════════════════
     OFFLINE CARD — bottom sheet with blur backdrop
  ══════════════════════════════════════════════════════════ */
  async function injectOfflineCard() {
    /* Remove stale overlay if already present */
    document.getElementById('rvc-offline-overlay')?.remove();

    const job = await RvcDB.getJob();
    if (!job) { showNoDataBanner(); return; }

    const stale     = (Date.now() - (job._cached_at || 0)) > STALE_MS;
    const cachedStr = job._cached_at
      ? new Date(job._cached_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : '';

    const isDelivering   = job.status === 'delivering';
    const statusLabel    = isDelivering ? 'Delivering' : 'Picking Up';
    const statusColour   = isDelivering
      ? 'var(--rvc-orange, #F97316)'
      : 'var(--rvc-green,  #10B981)';

    /* ── Overlay ────────────────────────────────────────────── */
    const overlay = document.createElement('div');
    overlay.id    = 'rvc-offline-overlay';

    /* ── Card ───────────────────────────────────────────────── */
    const card = document.createElement('div');
    card.id    = 'rvc-offline-card';

    card.innerHTML = `

      <!-- Drag handle -->
      <div style="display:flex;justify-content:center;padding:10px 0 2px;">
        <div style="width:36px;height:4px;border-radius:2px;
          background:var(--rvc-border-l,#2E3A55);"></div>
      </div>

      <!-- Header row -->
      <div style="display:flex;align-items:center;
        justify-content:space-between;padding:10px 16px 12px;">

        <div style="display:flex;align-items:center;gap:8px;">
          <div style="width:8px;height:8px;border-radius:50%;
            background:var(--rvc-red,#EF4444);
            box-shadow:0 0 0 3px rgba(239,68,68,.2);
            flex-shrink:0;"></div>
          <span style="font-size:.72rem;font-weight:700;
            color:var(--rvc-red,#EF4444);
            text-transform:uppercase;letter-spacing:.07em;">
            Offline — Cached Data
          </span>
        </div>

        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-size:.68rem;
            color:${stale ? '#D97706' : 'var(--rvc-muted,#64748B)'};">
            ${stale
              ? '<i class="fas fa-exclamation-triangle"></i> May be outdated'
              : 'Cached ' + cachedStr}
          </span>
          <!-- Dismiss button -->
          <button id="rvc-card-dismiss"
            title="Dismiss"
            style="width:30px;height:30px;border-radius:9px;
              background:var(--rvc-card-l,#1F2937);
              border:1px solid var(--rvc-border-l,#2E3A55);
              color:var(--rvc-muted-l,#94A3B8);
              font-size:.78rem;cursor:pointer;
              display:flex;align-items:center;justify-content:center;
              flex-shrink:0;transition:background .15s,color .15s;">
            <i class="fas fa-chevron-down"></i>
          </button>
        </div>
      </div>

      <!-- Scrollable body -->
      <div id="rvc-offline-body">

        <!-- Status pill -->
        <div style="margin-bottom:12px;">
          <span style="
            display:inline-flex;align-items:center;gap:6px;
            padding:5px 14px;border-radius:20px;
            background:rgba(249,115,22,.1);
            border:1px solid rgba(249,115,22,.2);
            font-size:.75rem;font-weight:700;
            color:${statusColour};">
            <i class="fas fa-circle" style="font-size:.38rem;"></i>
            ${statusLabel}
          </span>
        </div>

        <!-- Pickup -->
        <div class="rvc-addr-card">
          <div class="rvc-addr-row">
            <div class="rvc-addr-icon"
              style="background:rgba(16,185,129,.15);">
              <i class="fas fa-map-marker-alt"
                style="color:var(--rvc-green,#10B981);font-size:.75rem;"></i>
            </div>
            <div style="flex:1;min-width:0;">
              <div style="font-size:.65rem;font-weight:700;
                color:var(--rvc-muted,#64748B);
                text-transform:uppercase;letter-spacing:.06em;
                margin-bottom:3px;">Pickup</div>
              <div style="font-size:.85rem;font-weight:600;
                color:var(--rvc-text,#F8FAFC);line-height:1.4;">
                ${e(job.pickup_address)}</div>
              <div style="font-size:.78rem;
                color:var(--rvc-muted-l,#94A3B8);margin-top:3px;">
                ${e(job.pickup_name)}
                &nbsp;·&nbsp;
                <a href="tel:${e(job.pickup_phone)}"
                  style="color:var(--rvc-orange,#F97316);text-decoration:none;">
                  ${e(job.pickup_phone)}</a>
              </div>
            </div>
          </div>
        </div>

        <!-- Delivery -->
        <div class="rvc-addr-card">
          <div class="rvc-addr-row">
            <div class="rvc-addr-icon"
              style="background:rgba(249,115,22,.15);">
              <i class="fas fa-flag-checkered"
                style="color:var(--rvc-orange,#F97316);font-size:.75rem;"></i>
            </div>
            <div style="flex:1;min-width:0;">
              <div style="font-size:.65rem;font-weight:700;
                color:var(--rvc-muted,#64748B);
                text-transform:uppercase;letter-spacing:.06em;
                margin-bottom:3px;">Delivery</div>
              <div style="font-size:.85rem;font-weight:600;
                color:var(--rvc-text,#F8FAFC);line-height:1.4;">
                ${e(job.delivery_address)}</div>
              <div style="font-size:.78rem;
                color:var(--rvc-muted-l,#94A3B8);margin-top:3px;">
                ${e(job.delivery_name)}
                &nbsp;·&nbsp;
                <a href="tel:${e(job.delivery_phone)}"
                  style="color:var(--rvc-orange,#F97316);text-decoration:none;">
                  ${e(job.delivery_phone)}</a>
              </div>
            </div>
          </div>
        </div>

        <!-- Stats grid -->
        <div class="rvc-stat-grid">
          ${stat('fa-road',        e(String(job.distance)) + ' mi', 'Distance')}
          ${stat('fa-clock',       e(String(job.duration)) + ' min', 'ETA')}
          ${stat('fa-dollar-sign', '$' + e(String(job.earnings || '—')), 'Earnings')}
        </div>

        <!-- Offline note -->
        <div style="padding:10px 12px;
          background:rgba(239,68,68,.07);
          border:1px solid rgba(239,68,68,.14);
          border-radius:10px;
          font-size:.75rem;
          color:var(--rvc-muted-l,#94A3B8);
          line-height:1.6;">
          <i class="fas fa-info-circle"
            style="color:var(--rvc-red,#EF4444);margin-right:5px;"></i>
          You're offline. Status updates will sync automatically
          when you reconnect.
        </div>

      </div><!-- /#rvc-offline-body -->
    `;

    overlay.appendChild(card);
    document.body.appendChild(overlay);

    /* ── Event listeners ──────────────────────────────────── */

    /* Tap backdrop → dismiss */
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) dismissCard();
    });

    /* Chevron button → dismiss */
    document.getElementById('rvc-card-dismiss')
      ?.addEventListener('click', dismissCard);

    console.log('[RVC Offline] Card shown for job:', job.id,
      stale ? '(STALE)' : '(fresh)');
  }


  /* ── Animated dismiss ─────────────────────────────────────── */
  function dismissCard() {
    const overlay = document.getElementById('rvc-offline-overlay');
    if (!overlay) return;
    overlay.classList.add('dismissing');
    setTimeout(() => {
      overlay.remove();
      /* Bottom banner stays so courier knows they're still offline */
    }, 210);
  }


  /* ══════════════════════════════════════════════════════════
     ONLINE / OFFLINE TRANSITIONS
  ══════════════════════════════════════════════════════════ */
  function onCameOnline() {
    console.log('[RVC Offline] Back online');
    dismissCard();
    hideOfflineBanner();
    refreshJobCache();

    /* Trigger background sync (Phase 4) */
    if ('serviceWorker' in navigator && 'SyncManager' in window) {
      navigator.serviceWorker.ready
        .then(reg => reg.sync.register('rvc-job-status-sync'))
        .then(() => console.log('[RVC Offline] Sync registered'))
        .catch(err => console.warn('[RVC Offline] Sync failed:', err));
    }
  }

  function onWentOffline() {
    console.log('[RVC Offline] Went offline');
    showOfflineBanner();
    if (isCurrentJob) injectOfflineCard();
  }


  /* ══════════════════════════════════════════════════════════
     OFFLINE BANNER (slim — persists after card dismissed)
  ══════════════════════════════════════════════════════════ */
  function showOfflineBanner() {
    let b = document.getElementById('rvc-offline-banner');
    if (!b) {
      b = document.createElement('div');
      b.id = 'rvc-offline-banner';
      /* Tap banner → re-open card */
      b.title = 'Tap to view cached job';
      b.addEventListener('click', function () {
        if (isCurrentJob) injectOfflineCard();
      });
      document.body.appendChild(b);
    }
    b.innerHTML = `
      <i class="fas fa-wifi-slash"></i>
      Offline — cached data active
      ${isCurrentJob
        ? '<span style="margin-left:auto;font-size:.7rem;opacity:.7;">tap to view</span>'
        : ''}
    `;
    b.style.display = 'flex';
  }

  function hideOfflineBanner() {
    const b = document.getElementById('rvc-offline-banner');
    if (b) b.style.display = 'none';
  }


  /* ── No cache available ───────────────────────────────────── */
  function showNoDataBanner() {
    const b = document.createElement('div');
    b.style.cssText = [
      'margin:12px 16px', 'padding:14px',
      'background:rgba(239,68,68,.08)',
      'border:1px solid rgba(239,68,68,.2)',
      'border-radius:12px',
      'color:var(--rvc-muted-l,#94A3B8)',
      'font-size:.85rem',
      'font-family:Sora,sans-serif',
      'text-align:center',
      'line-height:1.6',
    ].join(';');
    b.innerHTML = `
      <i class="fas fa-exclamation-triangle"
        style="color:var(--rvc-red,#EF4444);margin-right:6px;"></i>
      No cached job data. Please reconnect to view your active job.
    `;
    document.getElementById('content')?.appendChild(b);
  }


  /* ══════════════════════════════════════════════════════════
     SYNC BADGE
  ══════════════════════════════════════════════════════════ */
  async function updateSyncBadge() {
    try {
      const count = await RvcDB.countQueued();
      const badge = document.getElementById('rvc-sync-badge');
      if (!badge) return;
      badge.textContent   = count;
      badge.style.display = count > 0 ? 'inline-flex' : 'none';
    } catch (_) { /* non-critical */ }
  }


  /* ══════════════════════════════════════════════════════════
     HELPERS
  ══════════════════════════════════════════════════════════ */

  /* HTML-escape shorthand */
  function e(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* Stat pill HTML */
  function stat(icon, value, label) {
    return `
      <div class="rvc-stat-pill">
        <i class="fas ${icon}"
          style="color:var(--rvc-orange,#F97316);font-size:.75rem;"></i>
        <div style="font-size:.85rem;font-weight:700;
          color:var(--rvc-text,#F8FAFC);margin-top:4px;">
          ${value}
        </div>
        <div style="font-size:.65rem;
          color:var(--rvc-muted,#64748B);
          text-transform:uppercase;letter-spacing:.04em;">
          ${label}
        </div>
      </div>`;
  }


  /* ── Public API (used by Phase 4) ─────────────────────────── */
  window.RvcOffline = { refreshJobCache, updateSyncBadge, dismissCard };

})();