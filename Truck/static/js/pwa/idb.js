/**
 * RiftValley Carriers — IndexedDB Wrapper
 * =========================================
 * File: Truck/static/js/pwa/idb.js
 *
 * Provides a clean Promise-based API over IndexedDB.
 * Used by courier-offline.js and sw.js (sync handler).
 *
 * Database:  rvc-offline-db  (version 1)
 * Stores:
 *   jobCache   — current active job data (keyed by job id)
 *   syncQueue  — offline status updates waiting to POST
 */

const RvcDB = (function () {
  'use strict';

  const DB_NAME    = 'rvc-offline-db';
  const DB_VERSION = 1;

  /* ── Open / upgrade ───────────────────────────────────────── */
  function open() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);

      req.onupgradeneeded = function (e) {
        const db = e.target.result;

        /* Job cache store — one record per job id */
        if (!db.objectStoreNames.contains('jobCache')) {
          db.createObjectStore('jobCache', { keyPath: 'id' });
        }

        /* Sync queue store — queued offline POSTs */
        if (!db.objectStoreNames.contains('syncQueue')) {
          const store = db.createObjectStore('syncQueue', {
            keyPath:       'id',
            autoIncrement: true,
          });
          store.createIndex('by_url', 'url', { unique: false });
        }
      };

      req.onsuccess = e  => resolve(e.target.result);
      req.onerror   = e  => reject(e.target.error);
    });
  }


  /* ══════════════════════════════════════════════════════════
     JOB CACHE API
  ══════════════════════════════════════════════════════════ */

  /**
   * Save job data to IndexedDB.
   * Overwrites any existing record with the same id.
   * @param {Object} jobData — plain object from /api/jobs/current/json/
   */
  async function saveJob(jobData) {
    const db    = await open();
    const tx    = db.transaction('jobCache', 'readwrite');
    const store = tx.objectStore('jobCache');
    return new Promise((resolve, reject) => {
      /* Add a timestamp so we know how stale the cache is */
      const record = Object.assign({}, jobData, { _cached_at: Date.now() });
      const req    = store.put(record);
      req.onsuccess = () => {
        console.log('[RVC IDB] Job cached:', jobData.id);
        resolve(record);
      };
      req.onerror = e => reject(e.target.error);
    });
  }

  /**
   * Get the most recently cached active job.
   * Returns null if nothing is cached.
   */
  async function getJob() {
    const db    = await open();
    const tx    = db.transaction('jobCache', 'readonly');
    const store = tx.objectStore('jobCache');
    return new Promise((resolve, reject) => {
      /* getAll then pick the newest by _cached_at */
      const req = store.getAll();
      req.onsuccess = () => {
        const records = req.result;
        if (!records || records.length === 0) {
          resolve(null);
          return;
        }
        /* Sort descending by cache time, return freshest */
        records.sort((a, b) => (b._cached_at || 0) - (a._cached_at || 0));
        resolve(records[0]);
      };
      req.onerror = e => reject(e.target.error);
    });
  }

  /**
   * Clear all cached jobs (call after job completes).
   */
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
     SYNC QUEUE API  (used by Phase 4 — Background Sync)
  ══════════════════════════════════════════════════════════ */

  /**
   * Queue a status update to be sent when connectivity returns.
   * @param {string} url    — e.g. /courier/api/jobs/current/<id>/update/
   * @param {Object} body   — POST body
   * @param {string} csrf   — CSRF token value
   */
  async function queueStatusUpdate(url, body, csrf) {
    const db    = await open();
    const tx    = db.transaction('syncQueue', 'readwrite');
    const store = tx.objectStore('syncQueue');
    return new Promise((resolve, reject) => {
      const req = store.add({
        url,
        body,
        csrf,
        queued_at: Date.now(),
      });
      req.onsuccess = () => {
        console.log('[RVC IDB] Status update queued for sync:', url);
        resolve(req.result);   /* returns the auto-increment id */
      };
      req.onerror = e => reject(e.target.error);
    });
  }

  /**
   * Get all queued updates waiting to sync.
   * @returns {Array}
   */
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

  /**
   * Remove a successfully synced update from the queue.
   * @param {number} id — the autoincrement key
   */
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

  /**
   * Count pending updates in the queue.
   * @returns {number}
   */
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


  /* ── Public API ───────────────────────────────────────────── */
  return {
    saveJob,
    getJob,
    clearJobs,
    queueStatusUpdate,
    getQueuedUpdates,
    removeQueuedUpdate,
    countQueued,
  };

})();