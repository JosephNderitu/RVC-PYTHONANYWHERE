<div align="center">

# 🚚 RVC Geospatial Logistics Platform

**An Intelligent, Resilience-Optimized Logistics Platform for Real-Time Dynamic Dispatch**

<br/>

<img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11"/>
<img src="https://img.shields.io/badge/Django-4.2-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django 4.2"/>
<img src="https://img.shields.io/badge/PostGIS-3.4-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostGIS 3.4"/>
<img src="https://img.shields.io/badge/OSRM-5.27-F4A100?style=for-the-badge&logo=openstreetmap&logoColor=white" alt="OSRM 5.27"/>
<img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
<img src="https://img.shields.io/badge/License-MIT-red?style=for-the-badge" alt="MIT License"/>

</div>

<br/>

## 📖 Overview

**Rift Valley Carriers (RVC)** is a full-stack geospatial logistics and courier dispatch platform designed for trucking operations across Georgia and surrounding U.S. states. The platform unifies courier coordination, delivery routing, and fleet management into an intelligent, web-based system.

This repository contains the **Geospatial Computing** component, powering road routing, automated dispatch, geofencing, service-area enforcement, and real-time fleet visualization — built entirely on self-hosted, open-source infrastructure.

<br/>

## 📊 Performance Metrics

<div align="center">

| ⚡ 20ms | 📍 47ms | ✅ 99.8% | 🚀 218x | 🗺️ 156ms | 💰 $24/mo |
|:---:|:---:|:---:|:---:|:---:|:---:|
| Dispatch Latency | Geofencing (p95) | Route Success Rate | Faster than Python Baseline | Map Refresh Interval | Infrastructure Cost |

</div>

> Note: Replace the emoji markers above with `<img>` badges if you'd like a fully icon-driven look — GitHub renders both natively, so emoji here is a lightweight, zero-dependency option.

<br/>

## ✨ Key Features

| Feature | Description |
|---|---|
| **🧭 Customer Portal** | 4-step job wizard, AI classification, live tracking with ETA, weather adjustments |
| **🌙 Courier Portal** | Dark-theme dashboard, live GPS tracking, job acceptance, delivery proof |
| **🔷 Geofencing Engine** | Winding Number point-in-polygon, 3-point jitter dampening, ENTER/EXIT detection |
| **📐 Distance Cascade** | Haversine → Karney Geodesic → OSRM, with automatic fallback |
| **📍 Service Area** | `ST_Contains` validation, snap-to-road via OSRM nearest endpoint |
| **🗺️ Visualization** | Self-hosted vector tiles (PostGIS MVT + Martin + MapLibre GL JS) |

<br/>

## 🧱 Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|:---:|---|
| Backend | Django + GeoDjango | 4.2 | REST API, spatial ORM |
| Spatial DB | PostgreSQL + PostGIS | 16 / 3.4 | GiST indexing, spatial queries |
| Routing | OSRM (Docker) | 5.27.1 | MLD algorithm, road network |
| Tasks | Celery + Redis | 5.3 / 7.0 | Background geofence evaluation |
| Maps | Leaflet.js + MapLibre GL JS | 1.9 / 3.0 | Interactive mapping, vector tiles |
| Payments | Stripe API | 2025-02 | Payment processing |
| Notifications | Twilio API | — | WhatsApp messaging |
| Orchestration | Docker + Docker Compose | 20.10 / 2.20 | Container management |

<br/>

## 🖼️ Screenshots

<div align="center">

| Customer Step 1 | Customer Step 2 | Customer Step 3 |
|:---:|:---:|:---:|
| <img src="readme_images/customer-step1.png" width="260"/> | <img src="readme_images/customer-step2.png" width="260"/> | <img src="readme_images/customer-step3.png" width="260"/> |
| Item Details & AI Classification | Pickup Location | OSRM Route & Price |

| Tracking Page | Courier Dashboard | Geofencing |
|:---:|:---:|:---:|
| <img src="readme_images/tracking.png" width="260"/> | <img src="readme_images/courier-dashboard.png" width="260"/> | <img src="readme_images/geofencing.png" width="260"/> |
| Live Courier & ETA | Live GPS Tracking | Zone Entry/Exit Detection |

</div>

> Screenshots are stored in `readme_images/`. Add your actual PNGs there — GitHub renders these `<img>` tags directly, unlike CSS placeholder boxes.

<br/>

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/JosephNderitu/RVC-PYTHONANYWHERE.git
cd RVC-PYTHONANYWHERE

# Build and start containers
docker compose up -d

# Apply migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser
```

### Access the Application

| Service | URL |
|---|---|
| Customer Portal | `http://localhost:8000/customer/` |
| Courier Portal | `http://localhost:8000/courier/` |
| Admin Dashboard | `http://localhost:8000/admin/` |
| OSRM API | `http://localhost:5000/` |

<br/>

## 🛰️ GPS Simulation

Test US operations from Kenya without physical couriers:

```bash
# Extract route from OSRM
python extract_route.py --pickup "33.749,-84.388" --delivery "32.083,-81.099"

# Run simulation
python gps_replay.py --route atlanta_savannah --speed 5
```

### Demo Scenarios

| Scenario | Route | Duration | Purpose |
|---|---|:---:|---|
| Quick Demo | Atlanta → Marietta (~20 mi) | 90s @ 10x | Full job lifecycle |
| Full Route | Atlanta → Savannah (~250 mi) | 3min @ 60x | OSRM network scale |
| Geofence Focus | Short route with zone | 60s @ 1x | Zone entry/exit detection |

<br/>

## 🔌 API Endpoints

| Method | Endpoint | Description |
|:---:|---|---|
| `POST` | `/courier/api/update-location/` | Update courier GPS position |
| `GET` | `/courier/api/courier-location/{job_id}/` | Get courier location for tracking |
| `GET` | `/courier/api/available-jobs/` | List available jobs |
| `POST` | `/courier/api/accept-job/` | Accept assigned job |
| `GET` | `/api/validate-location/` | Validate pin within service area |
| `GET` | `/api/osrm-route/` | Get OSRM route between points |

<br/>

## 👥 Contributors

| Name | Role | Contribution |
|---|---|---|
| **Joseph Gikuru Nderitu** | Geospatial Computing Specialist | Geofencing, Distance Engine, Dispatch, Visualization |
| Boniface Mwangi | PWA Resilience Specialist | Progressive Web Application, Service Worker |
| Loren Odhiambo | Machine Learning Specialist | AI Goods Classification, Prohibited Item Detection |

<br/>

## 🙏 Acknowledgments

- Dr. Isaiah Mulang' and Mr. Stephen Kun'gu for supervision and guidance
- Jomo Kenyatta University of Agriculture and Technology
- PostGIS, OSRM, Django, and Leaflet.js open-source communities
- Geofabrik for OpenStreetMap data extracts

<br/>

<div align="center">

[![GitHub](https://img.shields.io/badge/GitHub-JosephNderitu-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/JosephNderitu/RVC-PYTHONANYWHERE)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Joseph%20Nderitu-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/joseph-nderitu)
[![Email](https://img.shields.io/badge/Email-gikurujoseph53%40gmail.com-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:gikurujoseph53@gmail.com)

**MIT License** • 2026 Rift Valley Carriers latest update

</div>