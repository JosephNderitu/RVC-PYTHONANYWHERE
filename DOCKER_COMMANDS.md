# RVC Docker Command Reference
**Rift Valley Carriers — Docker Compose Cheat Sheet**

---

## Quick Decision Guide

```
Did you change requirements.txt or Dockerfile?
  YES → docker compose down && docker compose up --build
  NO  → Did you change a Python file or template?
          YES → Just refresh the browser (auto-reload handles it)
          NO  → docker compose down && docker compose up
```

---

## Commands by Situation

### 1. Templates / Python / CSS / HTML changed
> Django's StatReloader watches your files automatically via the mounted volume.
> **No restart needed** — just save the file and refresh the browser.

```powershell
# Nothing to run — Django auto-reloads
# You will see this in the logs when it detects a change:
# Watching for file changes with StatReloader
```

---

### 2. Quick restart — keeps containers, just bounces them
```powershell
docker compose restart
```

---

### 3. Full stop and start — standard daily workflow
```powershell
docker compose down
docker compose up
```

Run in detached mode (terminal stays free):
```powershell
docker compose down
docker compose up -d
```

One-liner:
```powershell
docker compose down && docker compose up
```

---

### 4. New package added to `requirements.txt`
> Must rebuild the Docker image so pip installs the new package.

```powershell
docker compose down
docker compose up --build
```

---

### 5. `Dockerfile` or `docker-compose.yml` changed
```powershell
docker compose down
docker compose up --build
```

---

### 6. Run database migrations
```powershell
docker compose exec web python manage.py migrate
docker compose exec web python manage.py shell
```

---

### 7. Create a Django superuser
```powershell
docker compose exec web python manage.py createsuperuser
```

---

### 8. Collect static files
```powershell
docker compose exec web python manage.py collectstatic --noinput
```

---

### 9. Open Django shell
```powershell
docker compose exec web python manage.py shell
```

---

### 10. Test OSRM routing is working
```powershell
docker compose exec web python manage.py shell -c "
from Truck.distance_engine import compute_distance
r = compute_distance(33.7490, -84.3880, 32.0835, -81.0998)
print('Method  :', r['method'])
print('Distance:', r['distance_miles'], 'miles')
print('Price  : $', r['price_usd'])
"
```

---

### 11. View live logs
```powershell
# All containers
docker compose logs -f

# One specific container
docker compose logs rvc_web    -f
docker compose logs rvc_osrm   -f
docker compose logs rvc_celery -f
docker compose logs rvc_postgis -f
```

---

### 12. Check container health status
```powershell
docker compose ps
```

Expected output when everything is healthy:
```
NAME           STATUS
rvc_postgis    healthy
rvc_redis      running
rvc_osrm       running
rvc_web        running
rvc_celery     running
```

---

### 13. Nuclear reset — wipes database volume
> ⚠️ Destructive. All database data will be lost. Use only when you need a completely clean state.

```powershell
docker compose down -v
docker compose up --build
```

---

### 14. Rebuild only one service (faster than full rebuild)
```powershell
docker compose up --build web
docker compose up --build celery
```

---

## Container Names Reference

| Container | Purpose |
|---|---|
| `rvc_postgis` | PostgreSQL 16 + PostGIS 3.4 spatial database |
| `rvc_redis` | Redis 7 — Celery broker and result backend |
| `rvc_web` | Django 6 application server (port 8000) |
| `rvc_celery` | Celery worker for background tasks |
| `rvc_osrm` | OSRM routing engine on Georgia road network (port 5000) |

---

## URLs When Running

| Service | URL |
|---|---|
| Django app | http://localhost:8000 |
| Django admin | http://localhost:8000/admin/ |
| OSRM health check | http://localhost:5000/route/v1/driving/-84.388,33.749;-81.0998,32.0835?overview=false |
| Customer portal | http://localhost:8000/customer/ |
| Courier portal | http://localhost:8000/courier/ |

---

## Common Errors and Fixes

### `ERR_EMPTY_RESPONSE` on localhost:8000
Django crashed on startup. Check the web container logs:
```powershell
docker compose logs rvc_web
```
Most common cause: wrong `DATABASE_URL` hostname in `.env`.
Fix: ensure `.env` contains exactly:
```
DATABASE_URL=postgis://rvc_user:rvc_pass_2026@db:5432/rvc_spatial
```

---

### `could not translate host name "db"`
Your `.env` is overriding the database URL with `localhost` or another invalid hostname.
Fix: same as above — set `DATABASE_URL` to use `db` as the hostname.

---

### OSRM returns `InvalidUrl` at root
Normal — OSRM only responds to full route queries, not the root path.
Test with the full URL in the OSRM health check row above.

---

### Celery warning: `running with superuser privileges`
Harmless warning in development. Safe to ignore.

---

### `SyntaxWarning: invalid escape sequence '\$'`
Harmless — occurs only in PowerShell test commands where `\$` is used.
Your actual application code is unaffected.

---

## `.env` Required Variables

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=postgis://rvc_user:rvc_pass_2026@db:5432/rvc_spatial
REDIS_URL=redis://redis:6379/0
OSRM_BASE_URL=http://osrm:5000
GOOGLE_MAP_API_KEY=your-key
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=RiftValley Carriers <noreply@rvcarriers.com>
OWNER_EMAIL=your-email@gmail.com
```

---

*RVC Geospatial Logistics Platform — BCT 2406 Final Year Project*
*Joseph Gikuru Nderitu · SCT212-0574/2022*