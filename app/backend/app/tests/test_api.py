import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Base, engine
from app.seed.seed_data import seed_database


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    seed_database()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "MediBud"


def test_auth_and_profile(client):
    # Register a new patient
    random_num = "9876500001"
    reg_payload = {
        "email": f"test_{random_num}@example.com",
        "phone": f"+91{random_num}",
        "password": "securepassword123",
        "full_name": "Test Patient",
        "role": "patient",
    }
    response = client.post("/api/auth/register", json=reg_payload)
    if response.status_code == 400:
        # Already registered, continue to login
        pass
    else:
        assert response.status_code == 201

    # Login
    login_payload = {
        "username": f"test_{random_num}@example.com",
        "password": "securepassword123",
    }
    login_res = client.post("/api/auth/login", json=login_payload)
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data

    # Profile lookup with token
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    profile_res = client.get("/api/auth/me", headers=headers)
    assert profile_res.status_code == 200
    assert profile_res.json()["email"] == f"test_{random_num}@example.com"


def test_list_hospitals_and_emergency(client):
    # List all hospitals near Civil Lines Kanpur
    response = client.get("/api/hospitals?lat=26.4695&lon=80.3512")
    assert response.status_code == 200
    hospitals = response.json()
    assert len(hospitals) > 0
    # First hospital should have distance near 0.0 km
    assert hospitals[0]["distance_km"] is not None
    assert hospitals[0]["distance_km"] <= hospitals[-1]["distance_km"]

    # Emergency mode query
    emergency_res = client.get("/api/hospitals/emergency?lat=26.4695&lon=80.3512&max_results=3")
    assert emergency_res.status_code == 200
    em_hospitals = emergency_res.json()
    assert len(em_hospitals) <= 3
    for h in em_hospitals:
        assert h["emergency_free_beds"] > 0


def test_bed_hold_booking_flow(client):
    # Find hospital #1
    res = client.get("/api/hospitals/1")
    assert res.status_code == 200
    hospital = res.json()

    # Reserve a General bed hold
    booking_payload = {
        "hospital_id": 1,
        "bed_type": "general",
        "patient_name": "Urgent Triage Patient",
        "patient_phone": "+919876543210",
        "emergency_notes": "Chest pain and shortness of breath",
    }
    book_res = client.post("/api/bookings/bed-hold", json=booking_payload)
    assert book_res.status_code in [201, 409]
    if book_res.status_code == 201:
        booking = book_res.json()
        assert "MB-BED-" in booking["booking_code"]
        assert booking["status"] == "pending"
        assert booking["seconds_remaining"] is not None
        assert booking["seconds_remaining"] > 0

        # Query by code
        code_res = client.get(f"/api/bookings/{booking['booking_code']}")
        assert code_res.status_code == 200
        assert code_res.json()["booking_code"] == booking["booking_code"]

        # Cancel hold
        cancel_res = client.post(f"/api/bookings/{booking['booking_code']}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"


def test_emergency_route_not_shadowed_by_hospital_id(client):
    res = client.get("/api/hospitals/emergency?lat=26.4695&lon=80.3512&max_results=3")
    assert res.status_code == 200
    assert len(res.json()) <= 3


def test_emergency_details_endpoint(client):
    res = client.get("/api/hospitals/1/emergency-details")
    assert res.status_code == 200
    body = res.json()
    assert body["hospital_id"] == 1 and "doctors" in body and "facilities" in body


def test_admin_requires_login_when_enforced(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ADMIN_AUTH_REQUIRED", True)
    res = client.post("/api/admin/beds/adjust", json={"hospital_id": 1, "bed_type": "icu", "delta": 1})
    assert res.status_code == 401
    res = client.post("/api/auth/register", json={
        "full_name": "Eve", "email": "eve@x.com", "phone": "9999999999",
        "password": "secret123", "role": "super_admin", "hospital_id": 1})
    assert res.status_code == 403


# ---------------- Staff approval workflow ----------------
def _login(client, user, pw):
    r = client.post("/api/auth/login", json={"username": user, "password": pw})
    return r


def _super_headers(client):
    tok = _login(client, "superadmin@medibud.com", "superadmin123").json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _staff_signup(client, n, role="hospital_admin", hospital_id=1):
    payload = {
        "email": f"staff{n}@example.com", "phone": f"+9188000{n:05d}", "password": "secret123",
        "full_name": f"Staff {n}", "role": role, "hospital_id": hospital_id,
    }
    r = client.post("/api/auth/register", json=payload)
    return r, payload


def test_staff_signup_is_pending_and_cannot_login(client):
    r, p = _staff_signup(client, 1)
    assert r.status_code == 201
    assert r.json()["approval_status"] == "pending"
    login = _login(client, p["email"], p["password"])
    assert login.status_code == 403
    assert "awaiting approval" in login.json()["detail"]


def test_wrong_password_does_not_reveal_pending(client):
    _, p = _staff_signup(client, 2)
    assert _login(client, p["email"], "wrong-password").status_code == 401


def test_approval_endpoints_need_admin(client):
    assert client.get("/api/auth/staff-requests").status_code == 401
    patient = _login(client, "patient@medibud.com", "password123").json()["access_token"]
    r = client.get("/api/auth/staff-requests", headers={"Authorization": f"Bearer {patient}"})
    assert r.status_code == 403
    r = client.post("/api/auth/staff-requests/1/approve", headers={"Authorization": f"Bearer {patient}"})
    assert r.status_code == 403


def test_super_admin_can_approve_then_staff_logs_in(client):
    r, p = _staff_signup(client, 3, role="doctor")
    uid = r.json()["id"]
    h = _super_headers(client)
    pending = client.get("/api/auth/staff-requests", headers=h).json()
    assert any(x["id"] == uid and x["hospital_name"] for x in pending)
    ok = client.post(f"/api/auth/staff-requests/{uid}/approve", headers=h)
    assert ok.status_code == 200 and ok.json()["approval_status"] == "approved"
    login = _login(client, p["email"], p["password"])
    assert login.status_code == 200
    assert login.json()["hospital_id"] == 1
    # already handled
    assert client.post(f"/api/auth/staff-requests/{uid}/approve", headers=h).status_code == 400


def test_rejected_staff_cannot_login(client):
    r, p = _staff_signup(client, 4)
    uid = r.json()["id"]
    h = _super_headers(client)
    assert client.post(f"/api/auth/staff-requests/{uid}/reject", headers=h).status_code == 200
    login = _login(client, p["email"], p["password"])
    assert login.status_code == 403
    assert "not approved" in login.json()["detail"]


def test_cannot_self_register_super_admin(client):
    r = client.post("/api/auth/register", json={
        "email": "evil@example.com", "phone": "+918800099999", "password": "secret123",
        "full_name": "Evil Admin", "role": "super_admin", "hospital_id": 1,
    })
    assert r.status_code == 403


def test_patient_signup_still_instant(client):
    r = client.post("/api/auth/register", json={
        "email": "newpatient@example.com", "phone": "+918800011111", "password": "secret123",
        "full_name": "New Patient", "role": "patient",
    })
    assert r.status_code == 201 and r.json()["approval_status"] == "approved"
    assert _login(client, "newpatient@example.com", "secret123").status_code == 200


# ---------------- Hospital Staff vs Admin (separate roles, hierarchical approval) ----------------
def _hosp_admin_headers(client):
    tok = _login(client, "admin@lifeline.com", "admin123").json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_hospital_staff_is_its_own_role_and_starts_pending(client):
    r, p = _staff_signup(client, 10, role="hospital_staff")
    assert r.status_code == 201
    assert r.json()["role"] == "hospital_staff" and r.json()["approval_status"] == "pending"
    assert _login(client, p["email"], p["password"]).status_code == 403


def test_hospital_admin_approves_staff_of_own_hospital(client):
    r, p = _staff_signup(client, 11, role="hospital_staff", hospital_id=1)
    uid = r.json()["id"]
    h = _hosp_admin_headers(client)
    assert any(x["id"] == uid for x in client.get("/api/auth/staff-requests", headers=h).json())
    ok = client.post(f"/api/auth/staff-requests/{uid}/approve", headers=h)
    assert ok.status_code == 200
    login = _login(client, p["email"], p["password"])
    assert login.status_code == 200 and login.json()["role"] == "hospital_staff"
    assert login.json()["hospital_id"] == 1


def test_hospital_admin_cannot_review_other_hospital_or_admin_requests(client):
    other, _ = _staff_signup(client, 12, role="hospital_staff", hospital_id=2)
    new_admin, _ = _staff_signup(client, 13, role="hospital_admin", hospital_id=1)
    h = _hosp_admin_headers(client)
    listed = {x["id"] for x in client.get("/api/auth/staff-requests", headers=h).json()}
    assert other.json()["id"] not in listed          # different hospital
    assert new_admin.json()["id"] not in listed      # admins need a super admin
    assert client.post(f"/api/auth/staff-requests/{other.json()['id']}/approve", headers=h).status_code == 404
    assert client.post(f"/api/auth/staff-requests/{new_admin.json()['id']}/approve", headers=h).status_code == 404


def test_admin_requests_need_super_admin_then_new_admin_can_approve(client):
    r, p = _staff_signup(client, 14, role="hospital_admin", hospital_id=1)
    sup = _super_headers(client)
    assert client.post(f"/api/auth/staff-requests/{r.json()['id']}/approve", headers=sup).status_code == 200
    tok = _login(client, p["email"], p["password"]).json()["access_token"]
    new_admin = {"Authorization": f"Bearer {tok}"}
    s, _ = _staff_signup(client, 15, role="hospital_staff", hospital_id=1)
    assert client.post(f"/api/auth/staff-requests/{s.json()['id']}/approve", headers=new_admin).status_code == 200


def test_pending_admin_cannot_approve_anything(client):
    r, p = _staff_signup(client, 16, role="hospital_admin", hospital_id=1)
    assert _login(client, p["email"], p["password"]).status_code == 403   # no token => no approval power
