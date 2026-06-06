/**
 * RiftValley Carriers — Courier Offline Manager v4
 * =================================================
 * File: Truck/static/js/pwa/courier-offline.js
 *
 * Phase 3 — Offline job card (blurred backdrop sheet)    ✅ complete
 * Phase 4 — Inline camera + photo queue + sync           ✅ complete
 * Phase 5 — Offline map route from cached GeoJSON        ✅ complete
 *
 * Depends on: idb.js (must load before this file)
 */

(function () {
  'use strict';

  /* ── Config ───────────────────────────────────────────────── */
  const API_URL  = '/courier/api/jobs/current/json/';
  const ORS_URL  = '/courier/api/ors-route/';
  const STALE_MS = 5 * 60 * 1000;

  /* ── Page detection ───────────────────────────────────────── */
  const PAGE         = window.location.pathname;
  const isCurrentJob = PAGE.includes('/jobs/current') && !PAGE.includes('take_photo');
  const isTakePhoto  = PAGE.includes('take_photo');

  /* ── Inject styles once ───────────────────────────────────── */
  (function injectStyles() {
    if (document.getElementById('rvc-offline-styles')) return;
    const s = document.createElement('style');
    s.id = 'rvc-offline-styles';
    s.textContent = `
      @keyframes rvc-fade-in    { from{opacity:0} to{opacity:1} }
      @keyframes rvc-slide-up   { from{transform:translateY(48px);opacity:0} to{transform:translateY(0);opacity:1} }
      @keyframes rvc-fade-out   { from{opacity:1} to{opacity:0} }
      @keyframes rvc-slide-down { from{transform:translateY(0);opacity:1} to{transform:translateY(48px);opacity:0} }

      #rvc-offline-overlay {
        position:fixed; inset:0; z-index:8000;
        display:flex; align-items:flex-end; justify-content:center;
        padding-bottom:80px;
        backdrop-filter:blur(7px); -webkit-backdrop-filter:blur(7px);
        background:rgba(11,15,26,.6);
        animation:rvc-fade-in .25s ease forwards;
      }
      #rvc-offline-overlay.dismissing { animation:rvc-fade-out .2s ease forwards; }

      #rvc-offline-card {
        width:calc(100% - 32px); max-width:440px;
        background:var(--rvc-card,#111827);
        border:1px solid var(--rvc-border-l,#2E3A55);
        border-radius:22px; overflow:hidden;
        box-shadow:0 28px 70px rgba(0,0,0,.65);
        animation:rvc-slide-up .3s cubic-bezier(.4,0,.2,1) forwards;
      }
      #rvc-offline-overlay.dismissing #rvc-offline-card {
        animation:rvc-slide-down .2s cubic-bezier(.4,0,.2,1) forwards;
      }
      #rvc-offline-body {
        max-height:58vh; overflow-y:auto; padding:0 16px 20px;
        scrollbar-width:thin;
        scrollbar-color:var(--rvc-border-l,#2E3A55) transparent;
      }
      #rvc-offline-body::-webkit-scrollbar { width:3px; }
      #rvc-offline-body::-webkit-scrollbar-thumb {
        background:var(--rvc-border-l,#2E3A55); border-radius:3px;
      }

      /* Persistent bottom banner */
      #rvc-offline-banner {
        position:fixed; bottom:68px; left:12px; right:12px;
        z-index:7999; border-radius:10px; padding:10px 14px;
        background:rgba(239,68,68,.14); border:1px solid rgba(239,68,68,.3);
        color:#EF4444; font-size:.8rem; font-weight:600;
        font-family:'Sora',sans-serif;
        display:none; align-items:center; gap:8px;
        animation:rvc-fade-in .3s ease; cursor:pointer;
      }

      /* Photo sync banner */
      #rvc-photo-banner {
        position:fixed; bottom:68px; left:12px; right:12px;
        z-index:7998; border-radius:10px; padding:10px 14px;
        background:rgba(249,115,22,.14); border:1px solid rgba(249,115,22,.3);
        color:#F97316; font-size:.8rem; font-weight:600;
        font-family:'Sora',sans-serif;
        display:none; align-items:center; gap:8px;
      }

      /* Offline map banner */
      #rvc-map-offline-banner {
        background:rgba(239,68,68,.1); border:1px solid rgba(239,68,68,.2);
        border-radius:0 0 14px 14px; padding:8px 14px;
        font-size:.75rem; color:var(--rvc-muted-l,#94A3B8);
        display:none; align-items:center; gap:7px;
        font-family:'Sora',sans-serif;
      }

      /* Camera overlay */
      #rvc-camera-overlay {
        position:fixed; inset:0; z-index:9000;
        background:#000;
        display:flex; flex-direction:column;
        align-items:center; justify-content:center;
      }

      /* Shared card elements */
      .rvc-addr-card {
        background:var(--rvc-card-l,#1F2937);
        border:1px solid var(--rvc-border,#1E2840);
        border-radius:12px; padding:12px; margin-bottom:8px;
      }
      .rvc-addr-row { display:flex; gap:10px; align-items:flex-start; }
      .rvc-addr-icon {
        width:28px; height:28px; border-radius:8px;
        display:flex; align-items:center; justify-content:center; flex-shrink:0;
      }
      .rvc-stat-grid {
        display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-bottom:12px;
      }
      .rvc-stat-pill {
        background:var(--rvc-card-l,#1F2937);
        border:1px solid var(--rvc-border,#1E2840);
        border-radius:10px; padding:10px 8px; text-align:center;
      }
      .rvc-action-row {
        display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:12px;
      }
      .rvc-action-btn {
        display:flex; align-items:center; justify-content:center; gap:7px;
        padding:12px 8px; border-radius:12px; border:none;
        font-size:.8rem; font-weight:700; font-family:'Sora',sans-serif;
        cursor:pointer; text-decoration:none; transition:opacity .15s;
      }
      .rvc-action-btn:active { opacity:.8; }
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
      if (isCurrentJob) {
        injectOfflineCard();
        drawOfflineRoute();
      }
    }
    window.addEventListener('online',  onCameOnline);
    window.addEventListener('offline', onWentOffline);
    updatePhotoSyncBadge();
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
        if (isCurrentJob) cacheRouteData(data.job);
        updatePhotoSyncBadge();
      }
    } catch (err) {
      console.log('[RVC Offline] Cache refresh skipped:', err.message);
    }
  }


  /* ══════════════════════════════════════════════════════════
     PHASE 5 — CACHE ROUTE GEOJSON
  ══════════════════════════════════════════════════════════ */
  async function cacheRouteData(job) {
    if (!job.pickup_lat || !job.pickup_lng || !job.delivery_lat || !job.delivery_lng) return;
    try {
      const url = `${ORS_URL}?plat=${job.pickup_lat}&plng=${job.pickup_lng}`
                + `&dlat=${job.delivery_lat}&dlng=${job.delivery_lng}`;
      const res  = await fetch(url, { credentials: 'include' });
      if (!res.ok) return;
      const data = await res.json();
      if (data.geometry) {
        await RvcDB.saveRoute(job.id, data);
        console.log('[RVC Offline] Route cached for job:', job.id);
      }
    } catch (err) {
      console.log('[RVC Offline] Route cache skipped:', err.message);
    }
  }


  /* ══════════════════════════════════════════════════════════
     PHASE 5 — DRAW OFFLINE ROUTE
  ══════════════════════════════════════════════════════════ */
  async function drawOfflineRoute() {
    if (!isCurrentJob) return;
    const job = await RvcDB.getJob();
    if (!job) return;
    const route = await RvcDB.getRoute(job.id);
    if (!route || !route.geometry) {
      console.log('[RVC Offline] No cached route found');
      return;
    }

    /* Wait for window.rvcMap (set by current_job.html) */
    const map = await new Promise(resolve => {
      const wait = (attempts) => {
        if (window.rvcMap) { resolve(window.rvcMap); return; }
        if (attempts <= 0) { resolve(null); return; }
        setTimeout(() => wait(attempts - 1), 300);
      };
      wait(20);
    });

    if (!map) {
      console.warn('[RVC Offline] Leaflet map not ready');
      return;
    }

    /* GeoJSON coords are [lng, lat] — Leaflet wants [lat, lng] */
    const coords = route.geometry.coordinates.map(c => [c[1], c[0]]);

    L.polyline(coords, {
      color: '#F97316', weight: 4, opacity: 0.75, dashArray: '8, 6',
    }).addTo(map).bindPopup(
      `<b style="font-family:Sora,sans-serif;font-size:.8rem;">📍 Cached Route</b>
       <br><span style="font-size:.75rem;color:#6B7280;">
         ${route.distance} mi · ${route.duration} min<br>
         Source: ${(route.source || 'ors').toUpperCase()}<br>
         Cached ${new Date(route.cached_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}
       </span>`
    );

    showMapOfflineBanner(route);
    console.log('[RVC Offline] Offline route drawn for job:', job.id);
  }

  function showMapOfflineBanner(route) {
    const mapBox = document.querySelector('.map-box');
    if (!mapBox) return;
    let b = document.getElementById('rvc-map-offline-banner');
    if (!b) {
      b = document.createElement('div');
      b.id = 'rvc-map-offline-banner';
      mapBox.parentNode.insertBefore(b, mapBox.nextSibling);
    }
    const cachedStr = route?.cached_at
      ? new Date(route.cached_at).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })
      : '';
    b.innerHTML = `
      <i class="fas fa-map-marked-alt" style="color:var(--rvc-orange,#F97316);"></i>
      Offline — showing cached route · Last updated ${cachedStr}
    `;
    b.style.display = 'flex';
  }


  /* ══════════════════════════════════════════════════════════
     PHASE 4 — OFFLINE CARD
  ══════════════════════════════════════════════════════════ */
  async function injectOfflineCard() {
    document.getElementById('rvc-offline-overlay')?.remove();

    const job = await RvcDB.getJob();
    if (!job) { showNoDataBanner(); return; }

    const stale        = (Date.now() - (job._cached_at || 0)) > STALE_MS;
    const cachedStr    = job._cached_at
      ? new Date(job._cached_at).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })
      : '';
    const isDelivering = job.status === 'delivering';
    const statusLabel  = isDelivering ? 'Delivering' : 'Picking Up';
    const statusColour = isDelivering ? 'var(--rvc-orange,#F97316)' : 'var(--rvc-green,#10B981)';
    const navDest      = isDelivering
      ? `${job.delivery_lat},${job.delivery_lng}`
      : `${job.pickup_lat},${job.pickup_lng}`;
    const mapsUrl      = `https://www.google.com/maps/dir/?api=1&destination=${navDest}&travelmode=driving`;

    /* Store job reference for the inline camera button */
    window._rvcOfflineJob = job;

    const overlay = document.createElement('div');
    overlay.id    = 'rvc-offline-overlay';

    const card = document.createElement('div');
    card.id    = 'rvc-offline-card';

    card.innerHTML = `
      <!-- Drag handle -->
      <div style="display:flex;justify-content:center;padding:10px 0 2px;">
        <div style="width:36px;height:4px;border-radius:2px;
          background:var(--rvc-border-l,#2E3A55);"></div>
      </div>

      <!-- Header -->
      <div style="display:flex;align-items:center;
        justify-content:space-between;padding:10px 16px 12px;">
        <div style="display:flex;align-items:center;gap:8px;">
          <div style="width:8px;height:8px;border-radius:50%;
            background:var(--rvc-red,#EF4444);
            box-shadow:0 0 0 3px rgba(239,68,68,.2);flex-shrink:0;"></div>
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
          <button id="rvc-card-dismiss" title="Dismiss"
            style="width:30px;height:30px;border-radius:9px;
              background:var(--rvc-card-l,#1F2937);
              border:1px solid var(--rvc-border-l,#2E3A55);
              color:var(--rvc-muted-l,#94A3B8);font-size:.78rem;
              cursor:pointer;display:flex;align-items:center;
              justify-content:center;flex-shrink:0;">
            <i class="fas fa-chevron-down"></i>
          </button>
        </div>
      </div>

      <!-- Scrollable body -->
      <div id="rvc-offline-body">

        <!-- Status pill -->
        <div style="margin-bottom:12px;">
          <span style="display:inline-flex;align-items:center;gap:6px;
            padding:5px 14px;border-radius:20px;
            background:rgba(249,115,22,.1);
            border:1px solid rgba(249,115,22,.2);
            font-size:.75rem;font-weight:700;color:${statusColour};">
            <i class="fas fa-circle" style="font-size:.38rem;"></i>
            ${statusLabel}
          </span>
        </div>

        <!-- Pickup -->
        <div class="rvc-addr-card">
          <div class="rvc-addr-row">
            <div class="rvc-addr-icon" style="background:rgba(16,185,129,.15);">
              <i class="fas fa-map-marker-alt"
                style="color:var(--rvc-green,#10B981);font-size:.75rem;"></i>
            </div>
            <div style="flex:1;min-width:0;">
              <div style="font-size:.65rem;font-weight:700;
                color:var(--rvc-muted,#64748B);
                text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;">
                Pickup</div>
              <div style="font-size:.85rem;font-weight:600;
                color:var(--rvc-text,#F8FAFC);line-height:1.4;">
                ${e(job.pickup_address)}</div>
              <div style="font-size:.78rem;
                color:var(--rvc-muted-l,#94A3B8);margin-top:3px;">
                ${e(job.pickup_name)} &nbsp;·&nbsp;
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
            <div class="rvc-addr-icon" style="background:rgba(249,115,22,.15);">
              <i class="fas fa-flag-checkered"
                style="color:var(--rvc-orange,#F97316);font-size:.75rem;"></i>
            </div>
            <div style="flex:1;min-width:0;">
              <div style="font-size:.65rem;font-weight:700;
                color:var(--rvc-muted,#64748B);
                text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;">
                Delivery</div>
              <div style="font-size:.85rem;font-weight:600;
                color:var(--rvc-text,#F8FAFC);line-height:1.4;">
                ${e(job.delivery_address)}</div>
              <div style="font-size:.78rem;
                color:var(--rvc-muted-l,#94A3B8);margin-top:3px;">
                ${e(job.delivery_name)} &nbsp;·&nbsp;
                <a href="tel:${e(job.delivery_phone)}"
                  style="color:var(--rvc-orange,#F97316);text-decoration:none;">
                  ${e(job.delivery_phone)}</a>
              </div>
            </div>
          </div>
        </div>

        <!-- Stats -->
        <div class="rvc-stat-grid">
          ${stat('fa-road',        e(String(job.distance)) + ' mi', 'Distance')}
          ${stat('fa-clock',       e(String(job.duration)) + ' min', 'ETA')}
          ${stat('fa-dollar-sign', '$' + e(String(job.earnings || '—')), 'Earnings')}
        </div>

        <!-- Action buttons -->
        <div class="rvc-action-row">
          <!-- Navigate — works offline via Google Maps cache -->
          <a href="${mapsUrl}" target="_blank" rel="noopener"
            class="rvc-action-btn"
            style="background:rgba(59,130,246,.12);
              border:1px solid rgba(59,130,246,.25);color:#60A5FA;">
            <i class="fas fa-directions"></i>
            Navigate
          </a>

          <!-- Take photo — opens inline camera (no navigation needed) -->
          <button id="rvc-open-camera-btn"
            class="rvc-action-btn"
            style="background:var(--rvc-orange,#F97316);color:#fff;
              border:none;cursor:pointer;">
            <i class="fas fa-camera"></i>
            Take Photo
          </button>
        </div>

        <!-- Offline note -->
        <div style="padding:10px 12px;
          background:rgba(239,68,68,.07);
          border:1px solid rgba(239,68,68,.14);
          border-radius:10px;font-size:.75rem;
          color:var(--rvc-muted-l,#94A3B8);line-height:1.6;">
          <i class="fas fa-info-circle"
            style="color:var(--rvc-red,#EF4444);margin-right:5px;"></i>
          You're offline. Tap <strong>Take Photo</strong> to confirm pickup or
          delivery — the upload queues automatically and syncs when you reconnect.
        </div>

      </div><!-- /#rvc-offline-body -->
    `;

    overlay.appendChild(card);
    document.body.appendChild(overlay);

    overlay.addEventListener('click', ev => { if (ev.target === overlay) dismissCard(); });
    document.getElementById('rvc-card-dismiss')?.addEventListener('click', dismissCard);

    /* Wire inline camera button */
    document.getElementById('rvc-open-camera-btn')
      ?.addEventListener('click', () => openInlineCamera(window._rvcOfflineJob));

    console.log('[RVC Offline] Card shown for job:', job.id, stale ? '(STALE)' : '(fresh)');
  }

  function dismissCard() {
    const overlay = document.getElementById('rvc-offline-overlay');
    if (!overlay) return;
    overlay.classList.add('dismissing');
    setTimeout(() => overlay.remove(), 210);
  }


  /* ══════════════════════════════════════════════════════════
     PHASE 4 — INLINE CAMERA (fully offline photo capture)
  ══════════════════════════════════════════════════════════ */
  async function openInlineCamera(job) {
    if (!job) return;

    const isDelivering = job.status === 'delivering';
    const photoType    = isDelivering ? 'delivery' : 'pickup';
    const updateUrl    = `/courier/api/jobs/current/${job.id}/update/`;
    const csrf         = getCsrf();

    /* ── Build camera overlay ─────────────────────────────── */
    const camOverlay = document.createElement('div');
    camOverlay.id    = 'rvc-camera-overlay';

    camOverlay.innerHTML = `
      <!-- Top bar -->
      <div style="position:absolute;top:0;left:0;right:0;
        padding:16px 20px;z-index:10;
        display:flex;align-items:center;justify-content:space-between;
        background:linear-gradient(180deg,rgba(0,0,0,.7) 0%,transparent 100%);">
        <button id="rvc-cam-close"
          style="background:rgba(255,255,255,.15);
            border:1px solid rgba(255,255,255,.2);
            color:#fff;border-radius:10px;
            padding:8px 14px;font-size:.82rem;font-weight:600;
            font-family:Sora,sans-serif;cursor:pointer;">
          <i class="fas fa-chevron-left"></i> Back
        </button>
        <span style="font-size:.8rem;font-weight:700;color:#fff;
          font-family:Sora,sans-serif;
          background:rgba(0,0,0,.4);padding:6px 14px;
          border-radius:20px;border:1px solid rgba(255,255,255,.15);">
          ${isDelivering
            ? '<i class="fas fa-flag-checkered" style="color:#F97316;margin-right:5px;"></i>Delivery Photo'
            : '<i class="fas fa-box" style="color:#10B981;margin-right:5px;"></i>Pickup Photo'}
        </span>
        <div style="width:80px;"></div>
      </div>

      <!-- Video stream -->
      <video id="rvc-cam-video" autoplay playsinline
        style="width:100%;height:100%;object-fit:cover;"></video>

      <!-- Hidden capture canvas -->
      <canvas id="rvc-cam-canvas" style="display:none;"></canvas>

      <!-- Preview image (shown after capture) -->
      <img id="rvc-cam-preview"
        style="display:none;width:100%;height:100%;object-fit:cover;" />

      <!-- Shutter bar -->
      <div id="rvc-cam-shutter-bar"
        style="position:absolute;bottom:0;left:0;right:0;
          padding:24px 24px 44px;z-index:10;
          display:flex;align-items:center;justify-content:center;
          background:linear-gradient(0deg,rgba(0,0,0,.75) 0%,transparent 100%);">
        <button id="rvc-cam-shutter"
          style="width:74px;height:74px;border-radius:50%;
            background:#fff;border:4px solid rgba(255,255,255,.35);
            display:flex;align-items:center;justify-content:center;
            cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,.5);
            transition:transform .1s;">
          <div style="width:54px;height:54px;border-radius:50%;
            background:#fff;border:2px solid #ddd;"></div>
        </button>
      </div>

      <!-- Confirm bar (shown after capture) -->
      <div id="rvc-cam-confirm-bar"
        style="position:absolute;bottom:0;left:0;right:0;
          padding:20px 24px 44px;z-index:10;
          display:none;align-items:center;justify-content:center;gap:16px;
          background:linear-gradient(0deg,rgba(0,0,0,.75) 0%,transparent 100%);">
        <button id="rvc-cam-retake"
          style="padding:13px 24px;border-radius:13px;
            background:rgba(255,255,255,.15);
            border:1px solid rgba(255,255,255,.25);
            color:#fff;font-size:.88rem;font-weight:700;
            font-family:Sora,sans-serif;cursor:pointer;">
          <i class="fas fa-redo"></i> Retake
        </button>
        <button id="rvc-cam-use"
          style="padding:13px 28px;border-radius:13px;
            background:#F97316;border:none;
            color:#fff;font-size:.88rem;font-weight:700;
            font-family:Sora,sans-serif;cursor:pointer;
            box-shadow:0 4px 16px rgba(249,115,22,.4);">
          <i class="fas fa-check"></i> Use Photo
        </button>
      </div>

      <!-- Error toast -->
      <div id="rvc-cam-error"
        style="display:none;position:absolute;top:80px;
          left:50%;transform:translateX(-50%);
          background:rgba(239,68,68,.9);color:#fff;
          padding:10px 20px;border-radius:12px;
          font-size:.84rem;font-family:Sora,sans-serif;
          white-space:nowrap;z-index:20;"></div>
    `;

    document.body.appendChild(camOverlay);

    /* ── Refs ─────────────────────────────────────────────── */
    const video   = document.getElementById('rvc-cam-video');
    const canvas  = document.getElementById('rvc-cam-canvas');
    const preview = document.getElementById('rvc-cam-preview');
    const errEl   = document.getElementById('rvc-cam-error');
    let   stream  = null;

    function showCamError(msg) {
      errEl.textContent   = msg;
      errEl.style.display = 'block';
      setTimeout(() => { errEl.style.display = 'none'; }, 5000);
    }

    function stopStream() {
      if (stream) stream.getTracks().forEach(t => t.stop());
    }

    /* ── Start camera ─────────────────────────────────────── */
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      });
      video.srcObject = stream;
    } catch (err) {
      showCamError('Camera access denied: ' + err.message);
    }

    /* ── Close / back ─────────────────────────────────────── */
    document.getElementById('rvc-cam-close')
      .addEventListener('click', () => { stopStream(); camOverlay.remove(); });

    /* ── Shutter ──────────────────────────────────────────── */
    document.getElementById('rvc-cam-shutter')
      .addEventListener('click', () => {
        canvas.width  = video.videoWidth  || 1280;
        canvas.height = video.videoHeight || 720;
        canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);

        preview.src           = canvas.toDataURL('image/png');
        video.style.display   = 'none';
        preview.style.display = 'block';
        document.getElementById('rvc-cam-shutter-bar').style.display  = 'none';
        document.getElementById('rvc-cam-confirm-bar').style.display  = 'flex';
      });

    /* ── Retake ───────────────────────────────────────────── */
    document.getElementById('rvc-cam-retake')
      .addEventListener('click', () => {
        preview.style.display = 'none';
        video.style.display   = 'block';
        document.getElementById('rvc-cam-confirm-bar').style.display  = 'none';
        document.getElementById('rvc-cam-shutter-bar').style.display  = 'flex';
      });

    /* ── Use Photo — save to IDB queue ───────────────────── */
    document.getElementById('rvc-cam-use')
      .addEventListener('click', async () => {
        const btn     = document.getElementById('rvc-cam-use');
        btn.disabled  = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving…';

        try {
          await RvcDB.savePhoto(job.id, photoType, preview.src, updateUrl, csrf);

          stopStream();
          camOverlay.remove();
          dismissCard();

          if (window.Swal) {
            Swal.fire({
              toast:             true,
              position:          'bottom',
              icon:              'warning',
              title:             'You\'re offline — photo queued',
              text:              'It will upload automatically when you reconnect.',
              showConfirmButton: false,
              timer:             5000,
              timerProgressBar:  true,
            });
          }

          /* Update badge directly — do NOT call updatePhotoSyncBadge()
             here because it may trigger flushPhotoQueue → fetch() → fail
             when DevTools offline intercepts but navigator.onLine is true */
          try {
            const count = await RvcDB.countPhotos();
            const badge = document.getElementById('rvc-sync-badge');
            if (badge) {
              badge.textContent   = count;
              badge.style.display = count > 0 ? 'inline-flex' : 'none';
            }
            if (count > 0) {
              showPhotoBanner(
                `${count} photo${count > 1 ? 's' : ''} queued — will sync when online`
              );
            }
          } catch (_) { /* non-critical */ }

        } catch (err) {
          showCamError('Failed to save: ' + err.message);
          btn.disabled  = false;
          btn.innerHTML = '<i class="fas fa-check"></i> Use Photo';
        }
      });
  }


  /* ══════════════════════════════════════════════════════════
     ONLINE / OFFLINE TRANSITIONS
  ══════════════════════════════════════════════════════════ */
  function onCameOnline() {
    console.log('[RVC Offline] Back online');
    dismissCard();
    hideOfflineBanner();
    refreshJobCache();
    flushPhotoQueue();

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
    if (isCurrentJob) {
      injectOfflineCard();
      drawOfflineRoute();
    }
  }


  /* ══════════════════════════════════════════════════════════
     PHASE 4 — FLUSH PHOTO QUEUE on reconnect
  ══════════════════════════════════════════════════════════ */
  async function flushPhotoQueue() {
    const photos = await RvcDB.getPhotos();
    if (photos.length === 0) return;

    console.log('[RVC Offline] Flushing', photos.length, 'queued photo(s)');
    showPhotoBanner(`Syncing ${photos.length} queued photo(s)…`);

    let synced = 0;
    for (const p of photos) {
      try {
        const blob     = b64ToBlob(p.photo_b64, 'image/png');
        const formData = new FormData();
        formData.append(p.photo_type + '_photo', blob, p.photo_type + '_photo.png');

        const res = await fetch(p.update_url, {
          method:      'POST',
          headers:     { 'X-CSRFToken': p.csrf },
          credentials: 'include',
          body:        formData,
        });

        if (res.ok) {
          await RvcDB.removePhoto(p.id);
          synced++;
          console.log('[RVC Offline] Photo synced:', p.photo_type, 'job:', p.job_id);
        } else {
          console.warn('[RVC Offline] Photo sync failed:', res.status);
        }
      } catch (err) {
        console.warn('[RVC Offline] Photo sync error:', err.message);
      }
    }

    await updatePhotoSyncBadge();

    if (synced > 0) {
      hidePhotoBanner();
      if (window.Swal) {
        Swal.fire({
          toast: true, position: 'bottom', icon: 'success',
          title: `${synced} photo${synced > 1 ? 's' : ''} synced successfully`,
          showConfirmButton: false,
          timer: 4000, timerProgressBar: true,
        });
      }
      const deliverySynced = photos.some(p => p.photo_type === 'delivery');
      if (deliverySynced) {
        setTimeout(() => window.location.href = '/courier/jobs/complete/', 1500);
      } else {
        setTimeout(() => window.location.reload(), 1000);
      }
    }
  }

  /* base64 data URL → Blob */
  function b64ToBlob(dataUrl, mimeType) {
    const base64 = dataUrl.split(',')[1];
    const bytes  = atob(base64);
    const buf    = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i);
    return new Blob([buf], { type: mimeType });
  }


  /* ══════════════════════════════════════════════════════════
     BANNERS
  ══════════════════════════════════════════════════════════ */
  function showOfflineBanner() {
    let b = document.getElementById('rvc-offline-banner');
    if (!b) {
      b = document.createElement('div');
      b.id = 'rvc-offline-banner';
      b.title = 'Tap to view cached job';
      b.addEventListener('click', () => { if (isCurrentJob) injectOfflineCard(); });
      document.body.appendChild(b);
    }
    b.innerHTML = `
      <i class="fas fa-wifi-slash"></i>
      Offline — cached data active
      ${isCurrentJob ? '<span style="margin-left:auto;font-size:.7rem;opacity:.7;">tap to view</span>' : ''}
    `;
    b.style.display = 'flex';
  }

  function hideOfflineBanner() {
    const b = document.getElementById('rvc-offline-banner');
    if (b) b.style.display = 'none';
  }

  function showPhotoBanner(msg) {
    let b = document.getElementById('rvc-photo-banner');
    if (!b) {
      b = document.createElement('div');
      b.id = 'rvc-photo-banner';
      document.body.appendChild(b);
    }
    b.innerHTML     = `<i class="fas fa-camera"></i> ${msg}`;
    b.style.display = 'flex';
  }

  function hidePhotoBanner() {
    const b = document.getElementById('rvc-photo-banner');
    if (b) b.style.display = 'none';
  }

  function showNoDataBanner() {
    const b = document.createElement('div');
    b.style.cssText = [
      'margin:12px 16px', 'padding:14px',
      'background:rgba(239,68,68,.08)',
      'border:1px solid rgba(239,68,68,.2)',
      'border-radius:12px',
      'color:var(--rvc-muted-l,#94A3B8)',
      'font-size:.85rem', 'font-family:Sora,sans-serif',
      'text-align:center', 'line-height:1.6',
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
  async function updatePhotoSyncBadge() {
    try {
      const count = await RvcDB.countPhotos();
      const badge = document.getElementById('rvc-sync-badge');
      if (!badge) return;
      badge.textContent   = count;
      badge.style.display = count > 0 ? 'inline-flex' : 'none';
      if (count > 0 && navigator.onLine) {
        flushPhotoQueue();
      } else if (count > 0) {
        showPhotoBanner(`${count} photo${count > 1 ? 's' : ''} queued — will sync when online`);
      }
    } catch (_) { /* non-critical */ }
  }

  async function updateSyncBadge() { return updatePhotoSyncBadge(); }


  /* ══════════════════════════════════════════════════════════
     HELPERS
  ══════════════════════════════════════════════════════════ */
  function e(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function stat(icon, value, label) {
    return `
      <div class="rvc-stat-pill">
        <i class="fas ${icon}" style="color:var(--rvc-orange,#F97316);font-size:.75rem;"></i>
        <div style="font-size:.85rem;font-weight:700;
          color:var(--rvc-text,#F8FAFC);margin-top:4px;">${value}</div>
        <div style="font-size:.65rem;color:var(--rvc-muted,#64748B);
          text-transform:uppercase;letter-spacing:.04em;">${label}</div>
      </div>`;
  }

  function getCsrf() {
    const c = document.cookie.split(';')
      .find(x => x.trim().startsWith('csrftoken='));
    return c ? c.trim().split('=')[1] : '';
  }


  /* ── Public API ───────────────────────────────────────────── */
  window.RvcOffline = {
    refreshJobCache,
    updateSyncBadge,
    updatePhotoSyncBadge,
    flushPhotoQueue,
    dismissCard,
    drawOfflineRoute,
    openInlineCamera,
  };

})();