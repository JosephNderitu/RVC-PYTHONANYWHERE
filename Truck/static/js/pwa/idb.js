/**
 * RiftValley Carriers — IndexedDB Wrapper v2
 * ============================================
 * File: Truck/static/js/pwa/idb.js
 *
 * Database:  rvc-offline-db  (version 2)
 *
 * Stores:
 *   jobCache    — current active job JSON (Phase 3)
 *   syncQueue   — generic offline status updates (Phase 4, legacy)
 *   photoQueue  — offline photo uploads (base64 + metadata) (Phase 4)
 *   routeCache  — cached route GeoJSON for offline map (Phase 5)
 *
 * Version bumped 1 → 2 to add photoQueue + routeCache stores.
 * Existing data in jobCache and syncQueue is preserved on upgrade.
 */

const RvcDB = (function () {
  'use strict';

  const DB_NAME    = 'rvc-offline-db';
  const DB_VERSION = 2;            /* ← bumped from 1 */

  /* ── Open / upgrade ───────────────────────────────────────── */
  function open() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);

      req.onupgradeneeded = function (e) {
        const db      = e.target.result;
        const oldVer  = e.oldVersion;

        /* Version 1 stores — create only if not present */
        if (!db.objectStoreNames.contains('jobCache')) {
          db.createObjectStore('jobCache', { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('syncQueue')) {
          const sq = db.createObjectStore('syncQueue', {
            keyPath: 'id', autoIncrement: true,
          });
          sq.createIndex('by_url', 'url', { unique: false });
        }

        /* Version 2 stores — added for Phase 4 + Phase 5 */
        if (!db.objectStoreNames.contains('photoQueue')) {
          /*
           * photoQueue record shape:
           * {
           *   id          — autoincrement PK
           *   job_id      — UUID string
           *   photo_type  — 'pickup' | 'delivery'
           *   photo_b64   — base64-encoded PNG (data:image/png;base64,...)
           *   update_url  — /courier/api/jobs/current/<id>/update/
           *   csrf        — CSRF token at time of capture
           *   queued_at   — Date.now()
           * }
           */
          const pq = db.createObjectStore('photoQueue', {
            keyPath: 'id', autoIncrement: true,
          });
          pq.createIndex('by_job', 'job_id', { unique: false });
        }

        if (!db.objectStoreNames.contains('routeCache')) {
          /*
           * routeCache record shape:
           * {
           *   id         — job_id used as PK
           *   geometry   — GeoJSON LineString {type, coordinates}
           *   distance   — miles
           *   duration   — minutes
           *   source     — 'ors' | 'osrm'
           *   cached_at  — Date.now()
           * }
           */
          db.createObjectStore('routeCache', { keyPath: 'id' });
        }
      };

      req.onsuccess = e  => resolve(e.target.result);
      req.onerror   = e  => reject(e.target.error);
    });
  }

  /* ══════════════════════════════════════════════════════════
     JOB CACHE  (Phase 3)
  ══════════════════════════════════════════════════════════ */

  async function saveJob(jobData) {
    const db    = await open();
    const tx    = db.transaction('jobCache', 'readwrite');
    const store = tx.objectStore('jobCache');
    return new Promise((resolve, reject) => {
      const record = Object.assign({}, jobData, { _cached_at: Date.now() });
      const req    = store.put(record);
      req.onsuccess = () => {
        console.log('[RVC IDB] Job cached:', jobData.id);
        resolve(record);
      };
      req.onerror = e => reject(e.target.error);
    });
  }

  async function getJob() {
    const db    = await open();
    const tx    = db.transaction('jobCache', 'readonly');
    const store = tx.objectStore('jobCache');
    return new Promise((resolve, reject) => {
      const req = store.getAll();
      req.onsuccess = () => {
        const records = req.result;
        if (!records || records.length === 0) { resolve(null); return; }
        records.sort((a, b) => (b._cached_at || 0) - (a._cached_at || 0));
        resolve(records[0]);
      };
      req.onerror = e => reject(e.target.error);
    });
  }

  async function clearJobs() {
    const db    = await open();
    const tx    = db.transaction('jobCache', 'readwrite');
    const store = tx.objectStore('jobCache');
    return new Promise((resolve, reject) => {
      const req = store.clear();
      req.onsuccess = () => resolve();
      req.onerror   = e  => reject(e.target.error);
    });
  }


  /* ══════════════════════════════════════════════════════════
     SYNC QUEUE  (Phase 4 — generic, kept for compatibility)
  ══════════════════════════════════════════════════════════ */

  async function queueStatusUpdate(url, body, csrf) {
    const db    = await open();
    const tx    = db.transaction('syncQueue', 'readwrite');
    const store = tx.objectStore('syncQueue');
    return new Promise((resolve, reject) => {
      const req = store.add({ url, body, csrf, queued_at: Date.now() });
      req.onsuccess = () => {
        console.log('[RVC IDB] Status update queued:', url);
        resolve(req.result);
      };
      req.onerror = e => reject(e.target.error);
    });
  }

  async function getQueuedUpdates() {
    const db    = await open();
    const tx    = db.transaction('syncQueue', 'readonly');
    const store = tx.objectStore('syncQueue');
    return new Promise((resolve, reject) => {
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror   = e  => reject(e.target.error);
    });
  }

  async function removeQueuedUpdate(id) {
    const db    = await open();
    const tx    = db.transaction('syncQueue', 'readwrite');
    const store = tx.objectStore('syncQueue');
    return new Promise((resolve, reject) => {
      const req = store.delete(id);
      req.onsuccess = () => resolve();
      req.onerror   = e  => reject(e.target.error);
    });
  }

  async function countQueued() {
    const db    = await open();
    const tx    = db.transaction('syncQueue', 'readonly');
    const store = tx.objectStore('syncQueue');
    return new Promise((resolve, reject) => {
      const req = store.count();
      req.onsuccess = () => resolve(req.result);
      req.onerror   = e  => reject(e.target.error);
    });
  }


  /* ══════════════════════════════════════════════════════════
     PHOTO QUEUE  (Phase 4 — offline photo upload storage)
  ══════════════════════════════════════════════════════════ */

  /**
   * Save a photo to the offline queue.
   * @param {string} jobId      — job UUID
   * @param {string} photoType  — 'pickup' or 'delivery'
   * @param {string} photoB64   — full data URL (data:image/png;base64,...)
   * @param {string} updateUrl  — /courier/api/jobs/current/<id>/update/
   * @param {string} csrf       — CSRF token value
   */
  async function savePhoto(jobId, photoType, photoB64, updateUrl, csrf) {
    const db    = await open();
    const tx    = db.transaction('photoQueue', 'readwrite');
    const store = tx.objectStore('photoQueue');
    return new Promise((resolve, reject) => {
      const req = store.add({
        job_id:     jobId,
        photo_type: photoType,
        photo_b64:  photoB64,
        update_url: updateUrl,
        csrf:       csrf,
        queued_at:  Date.now(),
      });
      req.onsuccess = () => {
        console.log('[RVC IDB] Photo queued:', photoType, 'for job', jobId);
        resolve(req.result);
      };
      req.onerror = e => reject(e.target.error);
    });
  }

  /**
   * Get all queued photos.
   * @returns {Array}
   */
  async function getPhotos() {
    const db    = await open();
    const tx    = db.transaction('photoQueue', 'readonly');
    const store = tx.objectStore('photoQueue');
    return new Promise((resolve, reject) => {
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror   = e  => reject(e.target.error);
    });
  }

  /**
   * Remove a successfully uploaded photo from the queue.
   * @param {number} id — autoincrement key
   */
  async function removePhoto(id) {
    const db    = await open();
    const tx    = db.transaction('photoQueue', 'readwrite');
    const store = tx.objectStore('photoQueue');
    return new Promise((resolve, reject) => {
      const req = store.delete(id);
      req.onsuccess = () => resolve();
      req.onerror   = e  => reject(e.target.error);
    });
  }

  /**
   * Count pending photos in the queue.
   * @returns {number}
   */
  async function countPhotos() {
    const db    = await open();
    const tx    = db.transaction('photoQueue', 'readonly');
    const store = tx.objectStore('photoQueue');
    return new Promise((resolve, reject) => {
      const req = store.count();
      req.onsuccess = () => resolve(req.result);
      req.onerror   = e  => reject(e.target.error);
    });
  }


  /* ══════════════════════════════════════════════════════════
     ROUTE CACHE  (Phase 5 — offline map route)
  ══════════════════════════════════════════════════════════ */

  /**
   * Save route GeoJSON for a job.
   * @param {string} jobId     — job UUID (used as PK)
   * @param {Object} routeData — { geometry, distance_miles, duration_min, source }
   */
  async function saveRoute(jobId, routeData) {
    const db    = await open();
    const tx    = db.transaction('routeCache', 'readwrite');
    const store = tx.objectStore('routeCache');
    return new Promise((resolve, reject) => {
      const record = {
        id:        jobId,
        geometry:  routeData.geometry,
        distance:  routeData.distance_miles,
        duration:  routeData.duration_min,
        source:    routeData.source || 'ors',
        cached_at: Date.now(),
      };
      const req = store.put(record);
      req.onsuccess = () => {
        console.log('[RVC IDB] Route cached for job:', jobId);
        resolve(record);
      };
      req.onerror = e => reject(e.target.error);
    });
  }

  /**
   * Get the cached route for a job.
   * @param {string} jobId
   * @returns {Object|null}
   */
  async function getRoute(jobId) {
    const db    = await open();
    const tx    = db.transaction('routeCache', 'readonly');
    const store = tx.objectStore('routeCache');
    return new Promise((resolve, reject) => {
      const req = store.get(jobId);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror   = e  => reject(e.target.error);
    });
  }


  /* ── Public API ───────────────────────────────────────────── */
  return {
    /* Job cache */
    saveJob,
    getJob,
    clearJobs,
    /* Sync queue */
    queueStatusUpdate,
    getQueuedUpdates,
    removeQueuedUpdate,
    countQueued,
    /* Photo queue */
    savePhoto,
    getPhotos,
    removePhoto,
    countPhotos,
    /* Route cache */
    saveRoute,
    getRoute,
  };

})();