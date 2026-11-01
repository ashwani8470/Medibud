# MediBud

Real-time hospital availability and emergency booking. In an emergency, families lose time calling hospitals to ask about beds and doctors. MediBud shows nearby hospitals sorted by distance, with live bed counts, doctor status and booking.

Hackathon prototype running on dummy data (`DATA_MODE=dummy`).

## Features

- Distance-sorted hospital list with bed counts (General, ICU, etc.) and doctor status
- Emergency mode: nearest hospitals with a free bed
- Bed hold for 30 minutes, released automatically when it expires
- Pre-arrival requests after a bed hold: ventilator, oxygen, trauma team at the gate, ambulance pickup, blood group check, medicine kit. Hospital staff mark each one ready and the patient sees the status live
- Appointment and checkup booking
- Live updates over WebSocket (`/ws/live`)
- Separate logins for patients, hospital staff and admins
- Staff sign-ups need approval: a hospital admin approves staff of their own hospital, and a super admin approves admins
- Data freshness indicator ("updated X min ago", stale after 2 hours)
- Installable PWA frontend
- Demo simulator that fluctuates bed counts for live demos

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, SQLite, JWT (PyJWT) and bcrypt, APScheduler
- **Frontend:** single-file PWA (`app/frontend/index.html`), served by the backend
- **Tests:** pytest

## Run it

You need Python 3.11 or newer.

```bat
cd app
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
start.bat
```

After the first setup, running `app\start.bat` is enough.

- App: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health

The database is created and seeded with dummy hospitals on first start. To reset it, stop the server and delete `app/backend/medibud.db`.

## Demo accounts

| Role | Email | Password |
|------|-------|----------|
| Patient | patient@medibud.com | password123 |
| Hospital admin | admin@lifeline.com | admin123 |
| Super admin | superadmin@medibud.com | superadmin123 |

These are for local demos only.

## Configuration

Settings live in `app/backend/app/core/config.py` and can be overridden with environment variables or a `.env` file.

| Setting | Default | Notes |
|---------|---------|-------|
| `SECRET_KEY` | dev-only key | Change it for any real deployment |
| `ADMIN_AUTH_REQUIRED` | `False` | When `True`, `/api/admin/*` needs a logged-in admin |
| `DATA_MODE` | `dummy` | `dummy` or `real` |
| `BED_HOLD_DURATION_MINUTES` | `30` | |
| `STALE_THRESHOLD_MINUTES` | `120` | |
| `CORS_ORIGINS` | `["*"]` | Restrict before deploying |

## Main API endpoints

All under `/api`.

- **Auth:** `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `GET /auth/staff-requests`, `POST /auth/staff-requests/{id}/approve|reject`
- **Hospitals:** `GET /hospitals`, `GET /hospitals/emergency`, `GET /hospitals/{id}`, `GET /hospitals/{id}/emergency-details`
- **Bookings:** `POST /bookings/bed-hold`, `/bookings/appointment`, `/bookings/checkup`, `GET /bookings/{code}`, `POST /bookings/{code}/cancel`
- **Pre-arrival:** `GET|POST /bookings/{code}/prearrival`, `POST /bookings/{code}/prearrival/{type}/cancel`
- **Admin:** `POST /admin/prearrival/{id}/status?status=ready`, `POST /admin/beds/adjust`, `POST /admin/doctors/{id}/status`, `GET /admin/hospitals/{id}/bookings`, `POST /admin/bookings/{id}/admit`, `/admin/simulator/toggle`

## Run the tests

```bat
cd app\backend
..\.venv\Scripts\python -m pytest
```

## Project layout

```
app/
  backend/app/   core/ models/ routers/ schemas/ seed/ services/ tests/
  frontend/      index.html, manifest.json, sw.js, icons
  start.bat
backend/         experimental Spring Boot port (hospital search only)
PLAN.md          original hackathon plan
```

## Spring Boot port (experimental)

`backend/` is an early port of the API to Java Spring Boot with H2. It only covers hospital search and seeding so far, and it is not used by the app. See `backend/src/main/resources/application.yml` for its settings. Run it with `mvnw.cmd spring-boot:run` (Java 17+), on port 8080.

## Roadmap

Payments, real OTP/SMS, surgery booking with uploads, analytics, multi-language, ratings and ambulance tracking.
