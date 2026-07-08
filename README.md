<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>RVC Geospatial Logistics Platform</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" />
</head>
<body class="bg-white text-slate-800 font-sans antialiased py-10 px-4 max-w-4xl mx-auto">

  <!-- ===== HEADER ===== -->
  <div class="flex items-start gap-4 mb-6">
    <div>
      <h1 class="text-3xl font-bold text-slate-900">
        <i class="fas fa-truck text-blue-700 mr-3"></i>RVC Geospatial Logistics Platform
      </h1>
      <p class="text-base text-slate-500 mt-1">An Intelligent, Resilience-Optimized Logistics Platform for Real-Time Dynamic Dispatch</p>
    </div>
  </div>

  <!-- ===== BADGES ===== -->
  <div class="flex flex-wrap gap-2 mb-6">
    <span class="bg-blue-50 text-blue-700 text-xs font-semibold px-3 py-1 rounded-full"><i class="fab fa-python mr-1"></i>Python 3.11</span>
    <span class="bg-green-50 text-green-700 text-xs font-semibold px-3 py-1 rounded-full"><i class="fab fa-django mr-1"></i>Django 4.2</span>
    <span class="bg-blue-50 text-blue-700 text-xs font-semibold px-3 py-1 rounded-full"><i class="fas fa-database mr-1"></i>PostGIS 3.4</span>
    <span class="bg-amber-50 text-amber-700 text-xs font-semibold px-3 py-1 rounded-full"><i class="fas fa-route mr-1"></i>OSRM 5.27</span>
    <span class="bg-purple-50 text-purple-700 text-xs font-semibold px-3 py-1 rounded-full"><i class="fab fa-docker mr-1"></i>Docker</span>
    <span class="bg-red-50 text-red-700 text-xs font-semibold px-3 py-1 rounded-full"><i class="fas fa-code mr-1"></i>MIT</span>
  </div>

  <hr class="border-slate-200 my-6" />

  <!-- ===== OVERVIEW ===== -->
  <h2 class="text-xl font-semibold text-slate-900 mt-8 mb-3 pb-2 border-b border-slate-200">
    <i class="fas fa-info-circle text-blue-700 mr-2"></i>Overview
  </h2>
  <p class="text-slate-600 mb-3"><strong>Rift Valley Carriers (RVC)</strong> is a full-stack geospatial logistics and courier dispatch platform designed for trucking operations across Georgia and surrounding U.S. states. The platform unifies courier coordination, delivery routing, and fleet management into an intelligent web-based system.</p>
  <p class="text-slate-600">This repository contains the <strong>Geospatial Computing</strong> component, powering road routing, automated dispatch, geofencing, service area enforcement, and real-time fleet visualization using self-hosted open-source infrastructure.</p>

  <!-- ===== METRICS ===== -->
  <div class="grid grid-cols-2 md:grid-cols-3 gap-4 my-6">
    <div class="bg-slate-50 rounded-lg p-4 text-center border border-slate-200">
      <div class="text-2xl font-bold text-slate-900">20ms</div>
      <div class="text-xs text-slate-500 uppercase tracking-wide">Dispatch Latency</div>
    </div>
    <div class="bg-slate-50 rounded-lg p-4 text-center border border-slate-200">
      <div class="text-2xl font-bold text-slate-900">47ms</div>
      <div class="text-xs text-slate-500 uppercase tracking-wide">Geofencing (95th %ile)</div>
    </div>
    <div class="bg-slate-50 rounded-lg p-4 text-center border border-slate-200">
      <div class="text-2xl font-bold text-slate-900">99.8%</div>
      <div class="text-xs text-slate-500 uppercase tracking-wide">Route Success Rate</div>
    </div>
    <div class="bg-slate-50 rounded-lg p-4 text-center border border-slate-200">
      <div class="text-2xl font-bold text-slate-900">218x</div>
      <div class="text-xs text-slate-500 uppercase tracking-wide">Faster than Python Baseline</div>
    </div>
    <div class="bg-slate-50 rounded-lg p-4 text-center border border-slate-200">
      <div class="text-2xl font-bold text-slate-900">156ms</div>
      <div class="text-xs text-slate-500 uppercase tracking-wide">Map Refresh Interval</div>
    </div>
    <div class="bg-slate-50 rounded-lg p-4 text-center border border-slate-200">
      <div class="text-2xl font-bold text-slate-900">$24/mo</div>
      <div class="text-xs text-slate-500 uppercase tracking-wide">Infrastructure Cost</div>
    </div>
  </div>

  <!-- ===== FEATURES ===== -->
  <h2 class="text-xl font-semibold text-slate-900 mt-8 mb-3 pb-2 border-b border-slate-200">
    <i class="fas fa-star text-blue-700 mr-2"></i>Key Features
  </h2>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
    <div class="bg-slate-50 border border-slate-200 rounded-lg p-4"><i class="fas fa-wand-magic-sparkles text-blue-700 w-6 mr-2"></i><strong>Customer Portal</strong><br class="block sm:hidden" /><span class="text-slate-600">4-step job wizard, AI classification, live tracking with ETA, weather adjustments</span></div>
    <div class="bg-slate-50 border border-slate-200 rounded-lg p-4"><i class="fas fa-moon text-blue-700 w-6 mr-2"></i><strong>Courier Portal</strong><br class="block sm:hidden" /><span class="text-slate-600">Dark theme dashboard, live GPS tracking, job acceptance, delivery proof</span></div>
    <div class="bg-slate-50 border border-slate-200 rounded-lg p-4"><i class="fas fa-draw-polygon text-blue-700 w-6 mr-2"></i><strong>Geofencing Engine</strong><br class="block sm:hidden" /><span class="text-slate-600">Winding Number PiP, 3-point jitter dampening, ENTER/EXIT detection</span></div>
    <div class="bg-slate-50 border border-slate-200 rounded-lg p-4"><i class="fas fa-arrows-spin text-blue-700 w-6 mr-2"></i><strong>Distance Cascade</strong><br class="block sm:hidden" /><span class="text-slate-600">Haversine → Karney Geodesic → OSRM with auto fallback</span></div>
    <div class="bg-slate-50 border border-slate-200 rounded-lg p-4"><i class="fas fa-location-dot text-blue-700 w-6 mr-2"></i><strong>Service Area</strong><br class="block sm:hidden" /><span class="text-slate-600">ST_Contains validation, snap-to-road via OSRM nearest endpoint</span></div>
    <div class="bg-slate-50 border border-slate-200 rounded-lg p-4"><i class="fas fa-map text-blue-700 w-6 mr-2"></i><strong>Visualization</strong><br class="block sm:hidden" /><span class="text-slate-600">Self-hosted vector tiles (PostGIS MVT + Martin + MapLibre GL JS)</span></div>
  </div>

  <!-- ===== TECH STACK ===== -->
  <h2 class="text-xl font-semibold text-slate-900 mt-8 mb-3 pb-2 border-b border-slate-200">
    <i class="fas fa-cubes text-blue-700 mr-2"></i>Technology Stack
  </h2>
  <div class="overflow-x-auto">
    <table class="w-full text-sm border-collapse">
      <thead><tr class="bg-slate-50 text-left"><th class="p-3 font-semibold border-b-2 border-slate-200">Layer</th><th class="p-3 font-semibold border-b-2 border-slate-200">Technology</th><th class="p-3 font-semibold border-b-2 border-slate-200">Version</th><th class="p-3 font-semibold border-b-2 border-slate-200">Purpose</th></tr></thead>
      <tbody>
        <tr><td class="p-3 border-b border-slate-200">Backend</td><td class="p-3 border-b border-slate-200">Django with GeoDjango</td><td class="p-3 border-b border-slate-200">4.2</td><td class="p-3 border-b border-slate-200">REST API, spatial ORM</td></tr>
        <tr><td class="p-3 border-b border-slate-200">Spatial DB</td><td class="p-3 border-b border-slate-200">PostgreSQL with PostGIS</td><td class="p-3 border-b border-slate-200">16 / 3.4</td><td class="p-3 border-b border-slate-200">GiST indexing, spatial queries</td></tr>
        <tr><td class="p-3 border-b border-slate-200">Routing</td><td class="p-3 border-b border-slate-200">OSRM (Docker)</td><td class="p-3 border-b border-slate-200">5.27.1</td><td class="p-3 border-b border-slate-200">MLD algorithm, road network</td></tr>
        <tr><td class="p-3 border-b border-slate-200">Tasks</td><td class="p-3 border-b border-slate-200">Celery + Redis</td><td class="p-3 border-b border-slate-200">5.3 / 7.0</td><td class="p-3 border-b border-slate-200">Background geofence evaluation</td></tr>
        <tr><td class="p-3 border-b border-slate-200">Maps</td><td class="p-3 border-b border-slate-200">Leaflet.js + MapLibre GL JS</td><td class="p-3 border-b border-slate-200">1.9 / 3.0</td><td class="p-3 border-b border-slate-200">Interactive mapping, vector tiles</td></tr>
        <tr><td class="p-3 border-b border-slate-200">Payments</td><td class="p-3 border-b border-slate-200">Stripe API</td><td class="p-3 border-b border-slate-200">2025-02</td><td class="p-3 border-b border-slate-200">Payment processing</td></tr>
        <tr><td class="p-3 border-b border-slate-200">Notifications</td><td class="p-3 border-b border-slate-200">Twilio API</td><td class="p-3 border-b border-slate-200">-</td><td class="p-3 border-b border-slate-200">WhatsApp messaging</td></tr>
        <tr><td class="p-3">Orchestration</td><td class="p-3">Docker + Docker Compose</td><td class="p-3">20.10 / 2.20</td><td class="p-3">Container management</td></tr>
      </tbody>
    </table>
  </div>

  <!-- ===== GALLERY ===== -->
  <h2 class="text-xl font-semibold text-slate-900 mt-8 mb-3 pb-2 border-b border-slate-200">
    <i class="fas fa-images text-blue-700 mr-2"></i>Screenshots
  </h2>
  <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
    <div class="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden text-center">
      <div class="bg-slate-200 h-36 flex items-center justify-center text-slate-400 text-sm"><i class="fas fa-image text-3xl mr-2"></i> Customer Step 1</div>
      <div class="p-2 text-sm font-medium text-slate-700">Item Details &amp; AI Classification</div>
    </div>
    <div class="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden text-center">
      <div class="bg-slate-200 h-36 flex items-center justify-center text-slate-400 text-sm"><i class="fas fa-image text-3xl mr-2"></i> Customer Step 2</div>
      <div class="p-2 text-sm font-medium text-slate-700">Pickup Location</div>
    </div>
    <div class="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden text-center">
      <div class="bg-slate-200 h-36 flex items-center justify-center text-slate-400 text-sm"><i class="fas fa-image text-3xl mr-2"></i> Customer Step 3</div>
      <div class="p-2 text-sm font-medium text-slate-700">OSRM Route &amp; Price</div>
    </div>
    <div class="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden text-center">
      <div class="bg-slate-200 h-36 flex items-center justify-center text-slate-400 text-sm"><i class="fas fa-image text-3xl mr-2"></i> Tracking Page</div>
      <div class="p-2 text-sm font-medium text-slate-700">Live Courier &amp; ETA</div>
    </div>
    <div class="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden text-center">
      <div class="bg-slate-200 h-36 flex items-center justify-center text-slate-400 text-sm"><i class="fas fa-image text-3xl mr-2"></i> Courier Dashboard</div>
      <div class="p-2 text-sm font-medium text-slate-700">Live GPS Tracking</div>
    </div>
    <div class="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden text-center">
      <div class="bg-slate-200 h-36 flex items-center justify-center text-slate-400 text-sm"><i class="fas fa-image text-3xl mr-2"></i> Geofencing</div>
      <div class="p-2 text-sm font-medium text-slate-700">Zone Entry/Exit Detection</div>
    </div>
  </div>
  <p class="text-xs text-slate-400 mt-2"><i class="fas fa-folder mr-1"></i>Screenshots stored in <code class="bg-slate-100 px-1 rounded">readme_images/</code></p>

  <!-- ===== QUICK START ===== -->
  <h2 class="text-xl font-semibold text-slate-900 mt-8 mb-3 pb-2 border-b border-slate-200">
    <i class="fas fa-rocket text-blue-700 mr-2"></i>Quick Start
  </h2>
  <div class="bg-slate-900 text-slate-200 rounded-lg p-4 font-mono text-sm overflow-x-auto">
    <span class="text-slate-500"># Clone the repository</span><br />
    git clone https://github.com/JosephNderitu/RVC-PYTHONANYWHERE.git<br />
    cd RVC-PYTHONANYWHERE<br /><br />
    <span class="text-slate-500"># Build and start containers</span><br />
    docker compose up -d<br /><br />
    <span class="text-slate-500"># Apply migrations</span><br />
    docker compose exec web python manage.py migrate<br /><br />
    <span class="text-slate-500"># Create superuser</span><br />
    docker compose exec web python manage.py createsuperuser
  </div>

  <h3 class="text-base font-semibold text-slate-800 mt-4">Access the Application</h3>
  <div class="overflow-x-auto">
    <table class="w-full text-sm border-collapse">
      <tbody>
        <tr><td class="p-2 border-b border-slate-200 font-medium">Customer Portal</td><td class="p-2 border-b border-slate-200"><code class="bg-slate-100 px-2 py-0.5 rounded">http://localhost:8000/customer/</code></td></tr>
        <tr><td class="p-2 border-b border-slate-200 font-medium">Courier Portal</td><td class="p-2 border-b border-slate-200"><code class="bg-slate-100 px-2 py-0.5 rounded">http://localhost:8000/courier/</code></td></tr>
        <tr><td class="p-2 border-b border-slate-200 font-medium">Admin Dashboard</td><td class="p-2 border-b border-slate-200"><code class="bg-slate-100 px-2 py-0.5 rounded">http://localhost:8000/admin/</code></td></tr>
        <tr><td class="p-2 font-medium">OSRM API</td><td class="p-2"><code class="bg-slate-100 px-2 py-0.5 rounded">http://localhost:5000/</code></td></tr>
      </tbody>
    </table>
  </div>

  <!-- ===== GPS SIMULATION ===== -->
  <h2 class="text-xl font-semibold text-slate-900 mt-8 mb-3 pb-2 border-b border-slate-200">
    <i class="fas fa-play text-blue-700 mr-2"></i>GPS Simulation
  </h2>
  <p class="text-slate-600 mb-2">Test US operations from Kenya without physical couriers:</p>
  <div class="bg-slate-900 text-slate-200 rounded-lg p-4 font-mono text-sm overflow-x-auto">
    <span class="text-slate-500"># Extract route from OSRM</span><br />
    python extract_route.py --pickup "33.749,-84.388" --delivery "32.083,-81.099"<br /><br />
    <span class="text-slate-500"># Run simulation</span><br />
    python gps_replay.py --route atlanta_savannah --speed 5
  </div>

  <h3 class="text-base font-semibold text-slate-800 mt-4">Demo Scenarios</h3>
  <div class="overflow-x-auto">
    <table class="w-full text-sm border-collapse">
      <thead><tr class="bg-slate-50 text-left"><th class="p-3 font-semibold border-b-2 border-slate-200">Scenario</th><th class="p-3 font-semibold border-b-2 border-slate-200">Route</th><th class="p-3 font-semibold border-b-2 border-slate-200">Duration</th><th class="p-3 font-semibold border-b-2 border-slate-200">Purpose</th></tr></thead>
      <tbody>
        <tr><td class="p-3 border-b border-slate-200">Quick Demo</td><td class="p-3 border-b border-slate-200">Atlanta → Marietta (~20 mi)</td><td class="p-3 border-b border-slate-200">90s at 10x</td><td class="p-3 border-b border-slate-200">Full job lifecycle</td></tr>
        <tr><td class="p-3 border-b border-slate-200">Full Route</td><td class="p-3 border-b border-slate-200">Atlanta → Savannah (~250 mi)</td><td class="p-3 border-b border-slate-200">3min at 60x</td><td class="p-3 border-b border-slate-200">OSRM network scale</td></tr>
        <tr><td class="p-3">Geofence Focus</td><td class="p-3">Short route with zone</td><td class="p-3">60s at 1x</td><td class="p-3">Zone entry/exit detection</td></tr>
      </tbody>
    </table>
  </div>

  <!-- ===== API ENDPOINTS ===== -->
  <h2 class="text-xl font-semibold text-slate-900 mt-8 mb-3 pb-2 border-b border-slate-200">
    <i class="fas fa-code text-blue-700 mr-2"></i>API Endpoints
  </h2>
  <div class="overflow-x-auto">
    <table class="w-full text-sm border-collapse">
      <thead><tr class="bg-slate-50 text-left"><th class="p-3 font-semibold border-b-2 border-slate-200">Method</th><th class="p-3 font-semibold border-b-2 border-slate-200">Endpoint</th><th class="p-3 font-semibold border-b-2 border-slate-200">Description</th></tr></thead>
      <tbody>
        <tr><td class="p-3 border-b border-slate-200 font-mono text-xs bg-slate-50">POST</td><td class="p-3 border-b border-slate-200"><code>/courier/api/update-location/</code></td><td class="p-3 border-b border-slate-200">Update courier GPS position</td></tr>
        <tr><td class="p-3 border-b border-slate-200 font-mono text-xs bg-slate-50">GET</td><td class="p-3 border-b border-slate-200"><code>/courier/api/courier-location/{job_id}/</code></td><td class="p-3 border-b border-slate-200">Get courier location for tracking</td></tr>
        <tr><td class="p-3 border-b border-slate-200 font-mono text-xs bg-slate-50">GET</td><td class="p-3 border-b border-slate-200"><code>/courier/api/available-jobs/</code></td><td class="p-3 border-b border-slate-200">List available jobs</td></tr>
        <tr><td class="p-3 border-b border-slate-200 font-mono text-xs bg-slate-50">POST</td><td class="p-3 border-b border-slate-200"><code>/courier/api/accept-job/</code></td><td class="p-3 border-b border-slate-200">Accept assigned job</td></tr>
        <tr><td class="p-3 border-b border-slate-200 font-mono text-xs bg-slate-50">GET</td><td class="p-3 border-b border-slate-200"><code>/api/validate-location/</code></td><td class="p-3 border-b border-slate-200">Validate pin within service area</td></tr>
        <tr><td class="p-3 font-mono text-xs bg-slate-50">GET</td><td class="p-3"><code>/api/osrm-route/</code></td><td class="p-3">Get OSRM route between points</td></tr>
      </tbody>
    </table>
  </div>

  <!-- ===== CONTRIBUTORS ===== -->
  <h2 class="text-xl font-semibold text-slate-900 mt-8 mb-3 pb-2 border-b border-slate-200">
    <i class="fas fa-users text-blue-700 mr-2"></i>Contributors
  </h2>
  <div class="overflow-x-auto">
    <table class="w-full text-sm border-collapse">
      <thead><tr class="bg-slate-50 text-left"><th class="p-3 font-semibold border-b-2 border-slate-200">Name</th><th class="p-3 font-semibold border-b-2 border-slate-200">Role</th><th class="p-3 font-semibold border-b-2 border-slate-200">Contribution</th></tr></thead>
      <tbody>
        <tr><td class="p-3 border-b border-slate-200 font-medium">Joseph Gikuru Nderitu</td><td class="p-3 border-b border-slate-200">Geospatial Computing Specialist</td><td class="p-3 border-b border-slate-200">Geofencing, Distance Engine, Dispatch, Visualization</td></tr>
        <tr><td class="p-3 border-b border-slate-200">Boniface Mwangi</td><td class="p-3 border-b border-slate-200">PWA Resilience Specialist</td><td class="p-3 border-b border-slate-200">Progressive Web Application, Service Worker</td></tr>
        <tr><td class="p-3">Loren Odhiambo</td><td class="p-3">Machine Learning Specialist</td><td class="p-3">AI Goods Classification, Prohibited Item Detection</td></tr>
      </tbody>
    </table>
  </div>

  <!-- ===== ACKNOWLEDGMENTS ===== -->
  <h2 class="text-xl font-semibold text-slate-900 mt-8 mb-3 pb-2 border-b border-slate-200">
    <i class="fas fa-heart text-blue-700 mr-2"></i>Acknowledgments
  </h2>
  <ul class="list-disc pl-6 text-slate-600 space-y-1">
    <li>Dr. Isaiah Mulang' and Mr. Stephen Kun'gu for supervision and guidance</li>
    <li>Jomo Kenyatta University of Agriculture and Technology</li>
    <li>PostGIS, OSRM, Django, and Leaflet.js open-source communities</li>
    <li>Geofabrik for OpenStreetMap data extracts</li>
  </ul>

  <!-- ===== FOOTER ===== -->
  <div class="mt-12 pt-6 border-t border-slate-200 text-sm text-slate-400 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
    <div>
      <i class="fab fa-github mr-1"></i><a href="https://github.com/JosephNderitu/RVC-PYTHONANYWHERE" class="text-blue-600 hover:underline">GitHub</a>
      <span class="mx-2">|</span>
      <i class="fab fa-linkedin mr-1"></i><a href="https://linkedin.com/in/joseph-nderitu" class="text-blue-600 hover:underline">LinkedIn</a>
    </div>
    <div>
      <i class="fas fa-envelope mr-1"></i><a href="mailto:gikurujoseph53@gmail.com" class="text-blue-600 hover:underline">gikurujoseph53@gmail.com</a>
      <span class="mx-2">|</span>
      <i class="fas fa-phone mr-1"></i><span class="text-slate-500">0715369835 / 0110423886</span>
    </div>
  </div>
  <p class="text-xs text-slate-400 mt-4">MIT License &bull; 2026 Rift Valley Carriers</p>

</body>
</html>
