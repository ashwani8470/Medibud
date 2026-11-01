# MediBud — Phase 1 (backend)

Hackathon prototype: nearby hospitals with dummy bed/doctor data.

## Run (Phase 1)

You need **Java 17+** (Java 21/26 is fine). Maven Wrapper is included — no Maven install required.

```bat
cd D:\medibud\backend
mvnw.cmd spring-boot:run
```

Then open:

- Health: http://localhost:8080/api/health
- Hospitals near Civil Lines: http://localhost:8080/api/hospitals?lat=26.467&lng=80.35
- Emergency (nearest 3 with General or ICU free): http://localhost:8080/api/hospitals?lat=26.467&lng=80.35&emergency=true
- One hospital: http://localhost:8080/api/hospitals/1?lat=26.467&lng=80.35
- H2 console: http://localhost:8080/h2-console  
  JDBC URL `jdbc:h2:file:./data/medibud`, user `sa`, password empty

Dummy data file (delete this later to drop demo hospitals): `backend/src/main/resources/data/seed-hospitals.json`

To re-seed: stop the app, delete `backend/data/`, start again.

Demo logins (auth API comes in the next step): `patient@demo` / `demo`, `admin@demo` / `demo`
