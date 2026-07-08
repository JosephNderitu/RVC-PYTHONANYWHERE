<p align="center">
  <img src="https://img.shields.io/badge/RVC_Geospatial-Logistics_Platform-1d4ed8?style=for-the-badge&logo=trusted-shops&logoColor=white" alt="RVC Banner" />
</p>

<h1 align="center">🚛 RVC Geospatial Logistics Platform</h1>

<p align="center">
  <strong>An Intelligent, Resilience-Optimized Logistics Platform for Real-Time Dynamic Dispatch</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Django-4.2-092E20?style=flat-square&logo=django&logoColor=white" alt="Django" />
  <img src="https://img.shields.io/badge/PostGIS-3.4-336791?style=flat-square&logo=postgresql&logoColor=white" alt="PostGIS" />
  <img src="https://img.shields.io/badge/OSRM-5.27-74c0fc?style=flat-square&logo=openstreetmap&logoColor=black" alt="OSRM" />
  <img src="https://img.shields.io/badge/Docker-20.10-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square" alt="License" />
</p>

---

## 📖 Overview

**Rift Valley Carriers (RVC)** is a full-stack geospatial logistics and courier dispatch platform designed for trucking operations across Georgia and surrounding U.S. states. The platform unifies courier coordination, delivery routing, and fleet management into an intelligent web-based system.

This repository contains the **Geospatial Computing** component, powering road routing, automated dispatch, geofencing, service area enforcement, and real-time fleet visualization using self-hosted open-source infrastructure.

---

## ⚡ Key Performance Metrics

GitHub doesn't run JavaScript grids, but we can leverage clean markdown tables to create highly distinct metric dashboards:

| Dispatch Latency | Geofencing (95th %ile) | Route Success Rate |
| :---: | :---: | :---: |
| 🚀 **20ms** | ⏱️ **47ms** | 📈 **99.8%** |

| Performance Gain | Map Refresh Interval | Infrastructure Cost |
| :---: | :---: | :---: |
| 🔥 **218x Faster** <br>*(vs Python Baseline)* | 🔄 **156ms** | 💰 **$24/mo** |

---

## ✨ Key Features

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <h4>🌐 Customer Portal</h4>
      <p>4-step job wizard, AI classification, live tracking with ETA, weather adjustments.</p>
    </td>
    <td width="50%" valign="top">
      <h4>🌙 Courier Portal</h4>
      <p>Dark theme dashboard, live GPS tracking, job acceptance, delivery proof.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>📐 Geofencing Engine</h4>
      <p>Winding Number PiP, 3-point jitter dampening, ENTER/EXIT detection.</p>
    </td>
    <td width="50%" valign="top">
      <h4>🔄 Distance Cascade</h4>
      <p>Haversine → Karney Geodesic → OSRM with auto fallback.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4>📍 Service Area</h4>
      <p>ST_Contains validation, snap-to-road via OSRM nearest endpoint.</p>
    </td>
    <td width="50%" valign="top">
      <h4>🗺️ Visualization</h4>
      <p>Self-hosted vector tiles (PostGIS MVT + Martin + MapLibre GL JS).</p>
    </td>
  </tr>
</table>

---

## 🛠️ Technology Stack

| Layer | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Backend** | Django with GeoDjango | `4.2` | REST API, spatial ORM |
| **Spatial DB** | PostgreSQL with PostGIS | `16 / 3.4` | GiST indexing, spatial queries |
| **Routing** | OSRM (Docker) | `5.27.1` | MLD algorithm, road network |
| **Tasks** | Celery + Redis | `5.3 / 7.0` | Background geofence evaluation |
| **Maps** | Leaflet.js + MapLibre GL JS | `1.9 / 3.0` | Interactive mapping, vector tiles |
| **Payments** | Stripe API | `2025-02` | Payment processing |
| **Notifications** | Twilio API | `-` | WhatsApp messaging |
| **Orchestration** | Docker + Docker Compose | `20.10 / 2.20` | Container management |

---

## 📸 Screenshots

<table width="100%">
  <tr>
    <td width="33.3%"><img src="readme_images/customer_step1.png" alt="Customer Step 1" onerror="this.src='https://placehold.co/600x400?text=Customer+Step+1'"/><br/><sub><b>Customer Step 1</b><br>Item Details & AI Classification</sub></td>
    <td width="33.3%"><img src="readme_images/customer_step2.png" alt="Customer Step 2" onerror="this.src='https://placehold.co/600x400?text=Customer+Step+2'"/><br/><sub><b>Customer Step 2</b><br>Pickup Location</sub></td>
    <td width="33.3%"><img src="readme_images/customer_step3.png" alt="Customer Step 3" onerror="this.src='https://placehold.co/600x400?text=Customer+Step+3'"/><br/><sub><b>Customer Step 3</b><br>OSRM Route & Price</sub></td>
  </tr>
  <tr>
    <td width="33.3%"><img src="readme_images/tracking.png" alt="Tracking Page" onerror="this.src='https://placehold.co/600x400?text=Tracking+Page'"/><br/><sub><b>Tracking Page</b><br>Live Courier & ETA</sub></td>
    <td width="33.3%"><img src="readme_images/courier_dashboard.png" alt="Courier Dashboard" onerror="this.src='https://placehold.co/600x400?text=Courier+Dashboard'"/><br/><sub><b>Courier Dashboard</b><br>Live GPS Tracking</sub></td>
    <td width="33.3%"><img src="readme_images/geofencing.png" alt="Geofencing" onerror="this.src='https://placehold.co/600x400?text=Geofencing'"/><br/><sub><b>Geofencing</b><br>Zone Entry/Exit Detection</sub></td>
  </tr>
</table>

> 📂 *All application screenshots are systematically managed inside the `readme_images/` directory.*

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone [https://github.com/JosephNderitu/RVC-PYTHONANYWHERE.git](https://github.com/JosephNderitu/RVC-PYTHONANYWHERE.git)
cd RVC-PYTHONANYWHERE

# Build and start containers
docker compose up -d

# Apply migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser
2. Port Mapping & Access LinksPortalURL Route🌐 Customer Portalhttp://localhost:8000/customer/🌙 Courier Portalhttp://localhost:8000/courier/⚙️ Admin Dashboardhttp://localhost:8000/admin/🗺️ OSRM APIhttp://localhost:5000/📡 GPS SimulationSimulate true-to-life US freight routes straight from local mock setups without dependencies on physical physical trackers moving down regional highways:Bash# Extract route metrics from OSRM engine
python extract_route.py --pickup "33.749,-84.388" --delivery "32.083,-81.099"

# Initialize streaming coordinate replayer
python gps_replay.py --route atlanta_savannah --speed 5
Supported Demo EnvironmentsScenarioSimulated PathTimeline TargetValidation PurposeQuick DemoAtlanta → Marietta (~20 mi)90s at 10x speedFull system job lifecycleFull RouteAtlanta → Savannah (~250 mi)3min at 60x speedOSRM routing mesh limitsGeofence EdgeSelected Zone Route60s at 1x speedBoundary crossing hooks🔌 Core API DocumentationMethodEndpointDescriptionPOST/courier/api/update-location/Post real-time courier coordinatesGET/courier/api/courier-location/{job_id}/Poll operational layout values for routing linesGET/courier/api/available-jobs/Expose pending queue elements to available fleetsPOST/courier/api/accept-job/Binds current user profile to explicit route payloadGET/api/validate-location/Spatial geofence check within operating zonesGET/api/osrm-route/Generates point-to-point road calculations👥 Engineering ContributorsDeveloper NameDomain ResponsibilityEngineering ContributionJoseph Gikuru NderituGeospatial Infrastructure SpecialistCore Geofencing, Distance Matrix Engine, Dispatch Optimization, Mapping LayersBoniface MwangiFrontend ArchitecturePWA Implementation, Resilient Edge Caching, Service WorkersLoren OdhiamboData Science & VisionAI Parcel Profile Classification, Prohibited Freight Pattern Detection🤝 AcknowledgmentsDr. Isaiah Mulang' & Mr. Stephen Kun'gu — Academic supervision, architecture feedback, and operational milestones guidance.Jomo Kenyatta University of Agriculture and Technology (JKUAT).Open-source core tools contributors across the PostGIS, OSRM, Django, and Leaflet.js ecosystems.Geofabrik for curated OpenStreetMap operational boundary raw files.📬 System Contacts & MaintainersMobile Support Lines: 0715369835 / 0110423886Licensing: Distributed under the MIT Open Source Framework standard. © 2026 Rift Valley Carriers.
