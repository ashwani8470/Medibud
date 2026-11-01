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
