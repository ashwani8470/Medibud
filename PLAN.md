# MediBud - Hackathon Plan

## Goal
A WORKING DEMO APP with dummy hospitals for a smooth 3-minute live demo. Not the final product.
Problem: in an emergency, families waste time checking hospitals for beds, doctors, facilities.

## Current state
`app/index.html` is a working front-end demo (no install needed; open in a browser).
Data lives in localStorage; two browser tabs sync live (Patient tab + Admin tab).
Includes: distance-sorted list + map, bed counts, doctor status, appointment booking,
30-min bed hold, Emergency Mode, admin one-tap updates, demo simulator.

## Target stack (Cursor converts the app into this)
- Frontend: React + Vite + Tailwind, Leaflet + OpenStreetMap
- Backend: Java Spring Boot (REST + WebSocket)
- DB: H2 first, PostgreSQL later; distance via Haversine
- Deploy: Render/Railway (backend), Vercel (frontend)

## Phases (stop and test after each)
1. Backend skeleton: entities Hospital, Doctor, BedInventory, Booking (all with is_demo flag); DataSeeder; GET /api/hospitals?lat&lng
2. Booking APIs: POST /api/appointments, POST /api/beds/reserve (transactional, no double booking, 30-min hold, scheduled auto-release)
3. Admin APIs: PATCH /api/admin/hospitals/{id}/beds, PATCH /api/admin/doctors/{id}/status; broadcast over WebSocket (/ws)
4. React app: port screens from the app (list+map, detail, booking, Emergency Mode, admin) using the API
5. Demo simulator endpoint/scheduler, polish, deploy
6. Slides + 3-minute demo rehearsal

## Dummy to real data
- DATA_MODE=dummy|real in config; all data access behind a service/repository layer
- Every seeded row has is_demo=true; `DELETE ... WHERE is_demo=true` removes all dummy data
- A real hospital registers and uses the same admin dashboard to enter beds/doctors
- Data freshness: "updated X min ago", stale warning after 2h, auto-release of bed holds

## Out of scope (future-scope slide)
Payments, real OTP/SMS, surgery booking with uploads, analytics, super admin, multi-language, ratings, ambulance tracking.

## Demo script (3 min)
1. Problem (20s) 2. Patient: list, map, hospital detail (40s) 3. Split screen: admin taps -1 ICU, patient updates live (50s)
4. Emergency Mode + bed hold (40s) 5. Real-data plan + future scope (30s)
