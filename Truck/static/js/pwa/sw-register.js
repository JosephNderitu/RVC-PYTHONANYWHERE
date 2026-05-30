/**
 * RiftValley Carriers — Service Worker Registration
 * =================================================
 * Place this file at: Truck/static/js/pwa/sw-register.js
 * Include it in courier/base.html {% block head %}
 *
 * Responsibilities:
 *  - Register /sw.js with root scope
 *  - Notify user when a new SW version is available
 *  - Track online/offline state for the UI
 *  - Show install prompt for PWA add-to-home-screen
 */

(function () {
  'use strict';

  /* ── 1. Register service worker ───────────────────────── */
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker
        .register('/sw.js', { scope: '/' })
        .then(function (registration) {
          console.log('[RVC PWA] SW registered. Scope:', registration.scope);

          /* ── Check for SW updates ─────────────────────── */
          registration.addEventListener('updatefound', function () {
            const newWorker = registration.installing;
            newWorker.addEventListener('statechange', function () {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                /* New version available — show non-intrusive toast */
                showUpdateToast();
              }
            });
          });
        })
        .catch(function (err) {
          console.warn('[RVC PWA] SW registration failed:', err);
        });

      /* ── Listen for controller change (after user clicks refresh) ── */
      let refreshing = false;
      navigator.serviceWorker.addEventListener('controllerchange', function () {
        if (!refreshing) {
          refreshing = true;
          window.location.reload();
        }
      });
    });
  }


  /* ── 2. Online / Offline status tracking ─────────────── */
  function updateNetworkBanner(isOnline) {
    let banner = document.getElementById('rvc-network-banner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'rvc-network-banner';
      banner.style.cssText = [
        'position:fixed', 'bottom:68px', 'left:12px', 'right:12px',
        'z-index:9999', 'border-radius:10px', 'padding:10px 16px',
        'font-size:.8rem', 'font-weight:600', 'font-family:Sora,sans-serif',
        'display:flex', 'align-items:center', 'gap:8px',
        'transition:all .35s cubic-bezier(.4,0,.2,1)',
        'transform:translateY(20px)', 'opacity:0',
        'pointer-events:none',
      ].join(';');
      document.body.appendChild(banner);
    }

    if (isOnline) {
      banner.style.background    = 'rgba(16,185,129,.15)';
      banner.style.border        = '1px solid rgba(16,185,129,.3)';
      banner.style.color         = '#10B981';
      banner.innerHTML           = '<i class="fas fa-wifi"></i> Back online';
      banner.style.opacity       = '1';
      banner.style.transform     = 'translateY(0)';
      setTimeout(function () {
        banner.style.opacity   = '0';
        banner.style.transform = 'translateY(20px)';
      }, 3000);
    } else {
      banner.style.background    = 'rgba(239,68,68,.15)';
      banner.style.border        = '1px solid rgba(239,68,68,.3)';
      banner.style.color         = '#EF4444';
      banner.innerHTML           = '<i class="fas fa-wifi-slash"></i> You\'re offline — saved data still available';
      banner.style.opacity       = '1';
      banner.style.transform     = 'translateY(0)';
    }
  }

  window.addEventListener('online',  function () { updateNetworkBanner(true);  });
  window.addEventListener('offline', function () { updateNetworkBanner(false); });

  /* Show offline banner immediately if already offline on load */
  if (!navigator.onLine) {
    document.addEventListener('DOMContentLoaded', function () {
      updateNetworkBanner(false);
    });
  }


  /* ── 3. PWA install prompt ───────────────────────────── */
  let deferredInstallPrompt = null;

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredInstallPrompt = e;
    /* Show install button if it exists on the page */
    const installBtn = document.getElementById('rvc-install-btn');
    if (installBtn) {
      installBtn.style.display = 'flex';
      installBtn.addEventListener('click', function () {
        deferredInstallPrompt.prompt();
        deferredInstallPrompt.userChoice.then(function (result) {
          console.log('[RVC PWA] Install prompt result:', result.outcome);
          deferredInstallPrompt = null;
          installBtn.style.display = 'none';
        });
      });
    }
  });

  window.addEventListener('appinstalled', function () {
    console.log('[RVC PWA] App installed successfully');
    deferredInstallPrompt = null;
  });


  /* ── 4. Update toast (non-blocking) ─────────────────── */
  function showUpdateToast() {
    /* Use SweetAlert2 if available (it is — loaded in courier/base.html) */
    if (window.Swal) {
      Swal.fire({
        toast:             true,
        position:          'bottom',
        icon:              'info',
        title:             'App updated',
        text:              'Tap to reload for the latest version.',
        showConfirmButton: true,
        confirmButtonText: 'Reload',
        confirmButtonColor: '#F97316',
        timer:             12000,
        timerProgressBar:  true,
      }).then(function (result) {
        if (result.isConfirmed) {
          navigator.serviceWorker.controller?.postMessage({ type: 'SKIP_WAITING' });
        }
      });
    }
  }

})();