<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RVC Geospatial Logistics Platform</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      background: #ffffff;
      color: #1e293b;
      line-height: 1.7;
      padding: 40px 20px;
      max-width: 1000px;
      margin: 0 auto;
    }
    .badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      margin-right: 6px;
    }
    .badge-blue { background: #e0f2fe; color: #0369a1; }
    .badge-green { background: #dcfce7; color: #15803d; }
    .badge-orange { background: #fef3c7; color: #b45309; }
    .badge-purple { background: #f3e8ff; color: #7c3aed; }
    .badge-red { background: #fee2e2; color: #b91c1c; }
    h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; color: #0f172a; }
    h2 { font-size: 20px; font-weight: 600; margin: 32px 0 16px 0; padding-bottom: 8px; border-bottom: 2px solid #e2e8f0; color: #0f172a; }
    h3 { font-size: 16px; font-weight: 600; margin: 20px 0 10px 0; color: #1e293b; }
    p { margin-bottom: 12px; color: #334155; }
    .subtitle { font-size: 16px; color: #64748b; margin-bottom: 24px; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 16px 0; }
    .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin: 16px 0; }
    .card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 20px; }
    .card i { color: #1e40af; width: 24px; margin-right: 8px; }
    .metric { background: #f1f5f9; border-radius: 8px; padding: 12px 16px; text-align: center; }
    .metric .value { font-size: 24px; font-weight: 700; color: #0f172a; }
    .metric .label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
    table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }
    th { background: #f1f5f9; text-align: left; padding: 10px 14px; font-weight: 600; color: #0f172a; border-bottom: 2px solid #e2e8f0; }
    td { padding: 10px 14px; border-bottom: 1px solid #e2e8f0; }
    .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; margin: 16px 0; }
    .gallery-item { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; text-align: center; }
    .gallery-item .placeholder { background: #e2e8f0; height: 140px; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 13px; }
    .gallery-item .caption { padding: 8px 12px; font-size: 13px; font-weight: 500; color: #1e293b; }
    .code-block { background: #0f172a; color: #e2e8f0; padding: 14px 18px; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 13px; overflow-x: auto; margin: 12px 0; }
    .code-block .comment { color: #94a3b8; }
    .footer { margin-top: 48px; padding-top: 24px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 14px; }
    .footer a { color: #1e40af; text-decoration: none; }
    .footer a:hover { text-decoration: underline; }
    .tech-icons i { font-size: 28px; margin-right: 12px; color: #334155; }
    @media (max-width: 768px) { .grid-2, .grid-3 { grid-template-columns: 1fr; } }
  </style>
</head>
<body>

<!-- ========== HEADER ========== -->
<h1><i class="fas fa-truck" style="color: #1e40af; margin-right: 12px;"></i> RVC Geospatial Logistics Platform</h1>
<p class="subtitle">An Intelligent, Resilience-Optimized Logistics Platform for Real-Time Dynamic Dispatch</p>

<p>
  <span class="badge badge-blue"><i class="fab fa-python"></i> Python 3.11</span>
  <span class="badge badge-green"><i class="fab fa-django"></i> Django 4.2</span>
  <span class="badge badge-blue"><i class="fas fa-database"></i> PostGIS 3.4</span>
  <span class="badge badge-orange"><i class="fas fa-route"></i> OSRM 5.27</span>
  <span class="badge badge-purple"><i class="fab fa-docker"></i> Docker</span>
  <span class="badge badge-red"><i class="fas fa-code"></i> MIT</span>
</p>

<hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">

<!-- ========== OVERVIEW ========== -->
<h2><i class="fas fa-info-circle" style="color: #1e40af; margin-right: 10px;"></i> Overview</h2>

<p><strong>Rift Valley Carriers (RVC)</strong> is a full-stack geospatial logistics and courier dispatch platform designed for trucking operations across Georgia and surrounding U.S. states. The platform unifies courier coordination, delivery routing, and fleet management into an intelligent web-based system.</p>

<p>This repository contains the <strong>Geospatial Computing</strong> component, powering road routing, automated dispatch, geofencing, service area enforcement, and real-time fleet visualization using self-hosted open-source infrastructure.</p>

<!-- ========== KEY METRICS ========== -->
<div class="grid-3">
  <div class="metric"><div class="value">20ms</div><div class="label">Dispatch Latency</div></div>
  <div class="metric"><div class="value">47ms</div><div class="label">Geofencing (95th %ile)</div></div>
  <div class="metric"><div class="value">99.8%</div><div class="label">Route Success Rate</div></div>
  <div class="metric"><div class="value">218x</div><div class="label">Faster than Python Baseline</div></div>
  <div class="metric"><div class="value">156ms</div><div class="label">Map Refresh Interval</div></div>
  <div class="metric"><div class="value">$24/mo</div><div class="label">Infrastructure Cost</div></div>
</div>

<!-- ========== FEATURES ========== -->
<h2><i class="fas fa-star" style="color: #1e40af; margin-right: 10px;"></i> Key Features</h2>

<div class="grid-2">
  <div class="card"><i class="fas fa-wand-magic-sparkles"></i> <strong>Customer Portal</strong><br>4-step job wizard, AI goods classification, live tracking with ETA, weather-aware adjustments</div>
  <div class="card"><i class="fas fa-moon"></i> <strong>Courier Portal</strong><br>Dark theme dashboard, live GPS tracking, job acceptance, delivery proof capture</div>
  <div class="card"><i class="fas fa-draw-polygon"></i> <strong>Geofencing Engine</strong><br>Winding Number PiP algorithm, 3-point jitter dampening, ENTER/EXIT event detection</div>
  <div class="card"><i class="fas fa-arrows-spin"></i> <strong>Distance Cascade</strong><br>Haversine (&#60;1mi) &#8594; Karney Geodesic (1-10mi) &#8594; OSRM (&#62;10mi)</div>
  <div class="card"><i class="fas fa-location-dot"></i> <strong>Service Area</strong><br>ST_Contains boundary validation, snap-to-road using OSRM nearest endpoint</div>
  <div class="card"><i class="fas fa-map"></i> <strong>Visualization</strong><br>Self-hosted vector tiles (PostGIS MVT + Martin + MapLibre GL JS), WebSocket streaming</div>
</div>

<!-- ========== TECHNOLOGY STACK ========== -->
<h2><i class="fas fa-cubes" style="color: #1e40af; margin-right: 10px;"></i> Technology Stack</h2>

<table>
  <tr><th>Layer</th><th>Technology</th><th>Version</th><th>Purpose</th></tr>
  <tr><td>Backend</td><td>Django with GeoDjango</td><td>4.2</td><td>REST API, spatial ORM</td></tr>
  <tr><td>Spatial DB</td><td>PostgreSQL with PostGIS</td><td>16 / 3.4</td><td>GiST indexing, spatial queries</td></tr>
  <tr><td>Routing</td><td>OSRM (Docker)</td><td>5.27.1</td><td>Road network, MLD algorithm</td></tr>
  <tr><td>Tasks</td><td>Celery + Redis</td><td>5.3 / 7.0</td><td>Background geofence evaluation</td></tr>
  <tr><td>Maps</td><td>Leaflet.js + MapLibre GL JS</td><td>1.9 / 3.0</td><td>Interactive mapping, vector tiles</td></tr>
  <tr><td>Payments</td><td>Stripe API</td><td>2025-02</td><td>Payment processing</td></tr>
  <tr><td>Notifications</td><td>Twilio API</td><td>-</td><td>WhatsApp messaging</td></tr>
  <tr><td>Orchestration</td><td>Docker + Docker Compose</td><td>20.10 / 2.20</td><td>Container management</td></tr>
</table>

<!-- ========== SYSTEM ARCHITECTURE ========== -->
<h2><i class="fas fa-sitemap" style="color: #1e40af; margin-right: 10px;"></i> System Architecture</h2>

<div class="code-block" style="color: #94a3b8; background: #0f172a; padding: 20px; border-radius: 8px; font-size: 13px; line-height: 1.8;">
<pre style="margin:0; color:#e2e8f0;">
┌────────────────────────────────────────────────────────────────────┐
│ <span style="color:#60a5fa;">PRESENTATION LAYER</span>                                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────────┐ │
│  │  Customer  │  │   Courier  │  │        Admin               │ │
│  │   Portal   │  │   Portal   │  │       Dashboard             │ │
│  │ (Leaflet)  │  │ (Dark Map) │  │    (Django Admin)           │ │
│  └────────────┘  └────────────┘  └────────────────────────────┘ │
└───────────────────────────────────┬────────────────────────────────┘
                                    │ REST API + WebSocket
┌───────────────────────────────────▼────────────────────────────────┐
│ <span style="color:#60a5fa;">APPLICATION LAYER</span>                                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────────┐ │
│  │  Django    │  │  GeoDjango │  │         Celery             │ │
│  │  REST API  │  │    ORM     │  │         Workers            │ │
│  └────────────┘  └────────────┘  └────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                       Redis (Cache)                          │ │
│  └──────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────┬────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────┐
│ <span style="color:#60a5fa;">ROUTING INTEGRATION LAYER</span>                                           │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │           OSRM Container (MLD Algorithm)                     │ │
│  │           Fallback: ORS → Haversine                         │ │
│  └──────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────┬────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────┐
│ <span style="color:#60a5fa;">DATA LAYER</span>                                                        │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │           PostgreSQL 16 + PostGIS 3.4                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐ │ │
│  │  │ Service  │ │  GeoZone │ │ Courier  │ │  GeofenceEvent  │ │ │
│  │  │  Area    │ │          │ │ Location │ │                 │ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └─────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
</pre>
</div>

<!-- ========== GALLERY ========== -->
<h2><i class="fas fa-images" style="color: #1e40af; margin-right: 10px;"></i> Screenshots</h2>

<div class="gallery">
  <div class="gallery-item">
    <div class="placeholder"><i class="fas fa-image" style="font-size: 32px;"></i><br>Customer Step 1</div>
    <div class="caption">Item Details &amp; AI Classification</div>
  </div>
  <div class="gallery-item">
    <div class="placeholder"><i class="fas fa-image" style="font-size: 32px;"></i><br>Customer Step 2</div>
    <div class="caption">Pickup Location with Service Area</div>
  </div>
  <div class="gallery-item">
    <div class="placeholder"><i class="fas fa-image" style="font-size: 32px;"></i><br>Customer Step 3</div>
    <div class="caption">OSRM Route &amp; Price Breakdown</div>
  </div>
  <div class="gallery-item">
    <div class="placeholder"><i class="fas fa-image" style="font-size: 32px;"></i><br>Tracking Page</div>
    <div class="caption">Live Courier with ETA Countdown</div>
  </div>
  <div class="gallery-item">
    <div class="placeholder"><i class="fas fa-image" style="font-size: 32px;"></i><br>Courier Dashboard</div>
    <div class="caption">Current Job with Live GPS</div>
  </div>
  <div class="gallery-item">
    <div class="placeholder"><i class="fas fa-image" style="font-size: 32px;"></i><br>Geofencing</div>
    <div class="caption">Zone Entry/Exit Event Detection</div>
  </div>
</div>

<p style="font-size: 13px; color: #94a3b8;"><i class="fas fa-folder"></i> All screenshots are stored in the <code>readme_images/</code> folder.</p>

<!-- ========== QUICK START ========== -->
<h2><i class="fas fa-rocket" style="color: #1e40af; margin-right: 10px;"></i> Quick Start</h2>

<div class="code-block">
<span class="comment"># Clone the repository</span>
git clone https://github.com/JosephNderitu/RVC-PYTHONANYWHERE.git
cd RVC-PYTHONANYWHERE

<span class="comment"># Build and start containers</span>
docker compose up -d

<span class="comment"># Apply migrations</span>
docker compose exec web python manage.py migrate

<span class="comment"># Create superuser</span>
docker compose exec web python manage.py createsuperuser
</div>

<h3>Access the Application</h3>
<table>
  <tr><th>Service</th><th>URL</th></tr>
  <tr><td>Customer Portal</td><td>http://localhost:8000/customer/</td></tr>
  <tr><td>Courier Portal</td><td>http://localhost:8000/courier/</td></tr>
  <tr><td>Admin Dashboard</td><td>http://localhost:8000/admin/</td></tr>
  <tr><td>OSRM API</td><td>http://localhost:5000/</td></tr>
</table>

<!-- ========== GPS SIMULATION ========== -->
<h2><i class="fas fa-play" style="color: #1e40af; margin-right: 10px;"></i> GPS Simulation</h2>

<p>Test US operations from Kenya without physical couriers:</p>

<div class="code-block">
<span class="comment"># Extract route from OSRM</span>
python extract_route.py --pickup "33.749,-84.388" --delivery "32.083,-81.099"

<span class="comment"># Run simulation</span>
python gps_replay.py --route atlanta_savannah --speed 5
</div>

<h3>Demo Scenarios</h3>
<table>
  <tr><th>Scenario</th><th>Route</th><th>Duration</th><th>Purpose</th></tr>
  <tr><td>Quick Demo</td><td>Atlanta → Marietta (~20 mi)</td><td>90s at 10x</td><td>Full job lifecycle</td></tr>
  <tr><td>Full Route</td><td>Atlanta → Savannah (~250 mi)</td><td>3min at 60x</td><td>OSRM network scale</td></tr>
  <tr><td>Geofence Focus</td><td>Short route with zone</td><td>60s at 1x</td><td>Zone entry/exit detection</td></tr>
</table>

<!-- ========== API ENDPOINTS ========== -->
<h2><i class="fas fa-code" style="color: #1e40af; margin-right: 10px;"></i> API Endpoints</h2>

<table>
  <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
  <tr><td>POST</td><td><code>/courier/api/update-location/</code></td><td>Update courier GPS position</td></tr>
  <tr><td>GET</td><td><code>/courier/api/courier-location/{job_id}/</code></td><td>Get courier location for tracking</td></tr>
  <tr><td>GET</td><td><code>/courier/api/available-jobs/</code></td><td>List available jobs</td></tr>
  <tr><td>POST</td><td><code>/courier/api/accept-job/</code></td><td>Accept assigned job</td></tr>
  <tr><td>GET</td><td><code>/api/validate-location/</code></td><td>Validate pin within service area</td></tr>
  <tr><td>GET</td><td><code>/api/osrm-route/</code></td><td>Get OSRM route between points</td></tr>
</table>

<!-- ========== CONTRIBUTORS ========== -->
<h2><i class="fas fa-users" style="color: #1e40af; margin-right: 10px;"></i> Contributors</h2>

<table>
  <tr><th>Name</th><th>Role</th><th>Contribution</th></tr>
  <tr><td><strong>Joseph Gikuru Nderitu</strong></td><td>Geospatial Computing Specialist</td><td>Geofencing, Distance Engine, Dispatch Algorithm, Visualization</td></tr>
  <tr><td>Boniface Mwangi</td><td>PWA Resilience Specialist</td><td>Progressive Web Application, Service Worker</td></tr>
  <tr><td>Loren Odhiambo</td><td>Machine Learning Specialist</td><td>AI Goods Classification, Prohibited Item Detection</td></tr>
</table>

<!-- ========== ACKNOWLEDGMENTS ========== -->
<h2><i class="fas fa-heart" style="color: #1e40af; margin-right: 10px;"></i> Acknowledgments</h2>

<ul style="padding-left: 20px; color: #334155;">
  <li>Dr. Isaiah Mulang' and Mr. Stephen Kun'gu for supervision and guidance</li>
  <li>Jomo Kenyatta University of Agriculture and Technology</li>
  <li>PostGIS, OSRM, Django, and Leaflet.js open-source communities</li>
  <li>Geofabrik for OpenStreetMap data extracts</li>
</ul>

<!-- ========== FOOTER ========== -->
<div class="footer">
  <p>
    <i class="fab fa-github"></i> <a href="https://github.com/JosephNderitu/RVC-PYTHONANYWHERE">GitHub Repository</a> &nbsp;|&nbsp;
    <i class="fab fa-linkedin"></i> <a href="https://linkedin.com/in/joseph-nderitu">Joseph Gikuru Nderitu</a> &nbsp;|&nbsp;
    <i class="fas fa-envelope"></i> jndr.ke@gmail.com
  </p>
  <p style="font-size: 13px; color: #94a3b8;">MIT License &bull; 2026 Rift Valley Carriers</p>
</div>

</body>
</html>
