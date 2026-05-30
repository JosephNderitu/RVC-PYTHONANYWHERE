{% load static %}
/*
 * RiftValley Carriers — Service Worker
 * =====================================================
 * Scope: /  (covers /courier/ and /customer/)
 * Strategy matrix:
 *   - Static assets  → Cache First  (CSS, JS, fonts, images)
 *   - Courier pages  → Network First with offline fallback
 *   - API calls      → Network First, queue offline POSTs
 *   - Maps/tiles     → Cache First (Leaflet tiles)
 * =====================================================
 */

const SW_VERSION  = 'rvc-sw-v1.0.0';
const STATIC_CACHE  = `${SW_VERSION}-static`;
const PAGES_CACHE   = `${SW_VERSION}-pages`;
const API_CACHE     = `${SW_VERSION}-api`;
const TILE_CACHE    = `${SW_VERSION}-tiles`;

/* ── Assets to pre-cache on install ─────────────────────── */
const STATIC_ASSETS = [
  '{% static "css/styles.css" %}',
  '{% static "images/logo.png" %}',
  '{% static "images/couriconbg.png" %}',
  '{% static "images/avatar.png" %}',
  '/courier/',
  '/courier/jobs/current/',
  '/courier/jobs/available/',
  '/offline/',           /* offline fallback page (we'll create this) */
];

/* ── Courier pages to cache on first visit ───────────────── */
const COURIER_PAGES = [
  '/courier/',
  '/courier/jobs/current/',
  '/courier/jobs/available/',
  '/courier/profile/',
];

/* ── URL patterns that should NEVER be cached ────────────── */
const NEVER_CACHE = [
  '/admin/',
  '/sign_out/',
  '/api/get-quote/',
];

/* ── Tile hosts (Leaflet map tiles) ─────────────────────── */
const TILE_HOSTS = [
  'tile.openstreetmap.org',
  'tiles.stadiamaps.com',
];

/* ── Max tile cache entries ──────────────────────────────── */
const MAX_TILE_ENTRIES = 500;


/* ═══════════════════════════════════════════════════════════
   INSTALL — pre-cache static assets
══════════════════════════════════════════════════════════ */
self.addEventListener('install', event => {
  console.log('[RVC SW] Installing', SW_VERSION);
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        /* Cache what we can — don't fail install if one asset is missing */
        return Promise.allSettled(
          STATIC_ASSETS.map(url =>
            cache.add(url).catch(err =>
              console.warn('[RVC SW] Pre-cache failed for', url, err)
            )
          )
        );
      })
      .then(() => self.skipWaiting())
  );
});


/* ═══════════════════════════════════════════════════════════
   ACTIVATE — clean up old caches
══════════════════════════════════════════════════════════ */
self.addEventListener('activate', event => {
  console.log('[RVC SW] Activating', SW_VERSION);
  const validCaches = [STATIC_CACHE, PAGES_CACHE, API_CACHE, TILE_CACHE];
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => !validCaches.includes(key))
          .map(key => {
            console.log('[RVC SW] Deleting old cache:', key);
            return caches.delete(key);
          })
      ))
      .then(() => self.clients.claim())
  );
});


/* ═══════════════════════════════════════════════════════════
   FETCH — route requests through correct strategy
══════════════════════════════════════════════════════════ */
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  /* Skip non-GET requests (POST handled by background sync) */
  if (request.method !== 'GET') return;

  /* Skip never-cache paths */
  if (NEVER_CACHE.some(p => url.pathname.startsWith(p))) return;

  /* Skip chrome-extension and non-http(s) */
  if (!url.protocol.startsWith('http')) return;

  /* ── Map tiles → Cache First with size limit ─── */
  if (TILE_HOSTS.some(h => url.hostname.includes(h))) {
    event.respondWith(tileStrategy(request));
    return;
  }

  /* ── Static assets → Cache First ─────────────── */
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  /* ── Courier API GETs → Network First ────────── */
  if (url.pathname.startsWith('/courier/api/') ||
      url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request, API_CACHE));
    return;
  }

  /* ── Courier HTML pages → Network First with fallback ── */
  if (url.pathname.startsWith('/courier/') &&
      request.headers.get('Accept')?.includes('text/html')) {
    event.respondWith(courierPageStrategy(request));
    return;
  }
});


/* ═══════════════════════════════════════════════════════════
   BACKGROUND SYNC — flush offline job status updates
══════════════════════════════════════════════════════════ */
self.addEventListener('sync', event => {
  console.log('[RVC SW] Sync event:', event.tag);
  if (event.tag === 'rvc-job-status-sync') {
    event.waitUntil(flushOfflineStatusUpdates());
  }
});


/* ═══════════════════════════════════════════════════════════
   PUSH NOTIFICATIONS (FCM fallback)
══════════════════════════════════════════════════════════ */
self.addEventListener('push', event => {
  if (!event.data) return;
  try {
    const data = event.data.json();
    event.waitUntil(
      self.registration.showNotification(data.title || 'RVC Courier', {
        body:    data.body || 'You have a new update.',
        icon:    '{% static "images/logo.png" %}',
        badge:   '{% static "images/logo.png" %}',
        tag:     'rvc-notification',
        renotify: true,
        data:    { url: data.url || '/courier/' },
      })
    );
  } catch (e) {
    console.warn('[RVC SW] Push parse error:', e);
  }
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const target = event.notification.data?.url || '/courier/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(list => {
        const existing = list.find(c => c.url.includes('/courier/'));
        if (existing) return existing.focus();
        return clients.openWindow(target);
      })
  );
});


/* ═══════════════════════════════════════════════════════════
   STRATEGY HELPERS
══════════════════════════════════════════════════════════ */

/** Cache First — serve from cache, fall back to network, cache the response */
async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Offline — asset unavailable', { status: 503 });
  }
}

/** Network First — try network, cache on success, fall back to cache */
async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request, { credentials: 'include' });
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify({ offline: true, error: 'No network' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

/** Courier page strategy — Network First, fall back to cached page or offline shell */
async function courierPageStrategy(request) {
  const cache = await caches.open(PAGES_CACHE);
  try {
    const response = await fetch(request, { credentials: 'include' });
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    /* Try exact cached page first */
    const cached = await cache.match(request);
    if (cached) return cached;
    /* Fall back to offline page */
    const offline = await caches.match('/offline/');
    if (offline) return offline;
    return new Response('<h1>You are offline</h1><p>Please reconnect to continue.</p>', {
      headers: { 'Content-Type': 'text/html' },
      status: 503,
    });
  }
}

/** Tile strategy — Cache First with entry limit to avoid filling storage */
async function tileStrategy(request) {
  const cache = await caches.open(TILE_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      /* Enforce tile cache size limit */
      const keys = await cache.keys();
      if (keys.length >= MAX_TILE_ENTRIES) {
        cache.delete(keys[0]); /* evict oldest */
      }
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('', { status: 503 });
  }
}

/** Flush queued offline job status updates via IndexedDB queue */
async function flushOfflineStatusUpdates() {
  /* Reads from the rvc-sync-queue IndexedDB store (written by courier-offline.js) */
  const db = await openSyncDB();
  const tx  = db.transaction('syncQueue', 'readwrite');
  const store = tx.objectStore('syncQueue');

  return new Promise((resolve, reject) => {
    const req = store.getAll();
    req.onsuccess = async () => {
      const items = req.result;
      const failed = [];
      for (const item of items) {
        try {
          const res = await fetch(item.url, {
            method:      'POST',
            headers:     { 'Content-Type': 'application/json', 'X-CSRFToken': item.csrf },
            body:        JSON.stringify(item.body),
            credentials: 'include',
          });
          if (res.ok) {
            store.delete(item.id);
            console.log('[RVC SW] Synced offline update:', item.id);
          } else {
            failed.push(item.id);
          }
        } catch {
          failed.push(item.id);
        }
      }
      await tx.done;
      if (failed.length) {
        console.warn('[RVC SW] Failed to sync', failed.length, 'item(s) — will retry next sync');
        reject(new Error('Partial sync failure'));
      } else {
        resolve();
      }
    };
    req.onerror = reject;
  });
}

/** Minimal IndexedDB open for the sync queue */
function openSyncDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('rvc-offline-db', 1);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('syncQueue')) {
        db.createObjectStore('syncQueue', { keyPath: 'id', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains('jobCache')) {
        db.createObjectStore('jobCache', { keyPath: 'id' });
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

/** Detect static asset URLs */
function isStaticAsset(url) {
  return url.pathname.startsWith('/static/') ||
    /\.(css|js|woff2?|ttf|png|jpg|jpeg|gif|svg|ico|webp)$/i.test(url.pathname);
}