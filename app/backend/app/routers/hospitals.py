from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Hospital, HospitalBed, Doctor, DoctorSlot, DoctorStatus, BedType
from app.schemas.hospital import (
    HospitalBase,
    HospitalDetailResponse,
    BedStatusResponse,
    DoctorResponse,
    DoctorSlotResponse,
)
from app.services.geo import haversine_distance, estimate_travel_time_minutes

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])


IST = timezone(timedelta(hours=5, minutes=30))  # clinic slot times are stored as local "HH:MM"


def _slot_datetime(slot_time: str, now_local: datetime) -> Optional[datetime]:
    """Turn a stored "HH:MM" slot into today's datetime in IST (None if malformed)."""
    try:
        hh, mm = slot_time.split(":")
        return now_local.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    except (ValueError, AttributeError):
        return None


def format_hospital_summary(h: Hospital, user_lat: Optional[float] = None, user_lon: Optional[float] = None) -> dict:
    """Helper to convert Hospital ORM model to dictionary with calculated distance and bed breakdown."""
    dist_km = None
    time_min = None
    if user_lat is not None and user_lon is not None:
        dist_km = haversine_distance(user_lat, user_lon, h.latitude, h.longitude)
        time_min = estimate_travel_time_minutes(dist_km)

    beds_map: Dict[str, dict] = {}
    emergency_beds = 0
    for b in h.beds:
        free = max(0, b.total_beds - b.occupied_beds - b.held_beds)
        beds_map[b.bed_type.value] = {
            "bed_type": b.bed_type.value,
            "total": b.total_beds,
            "occupied": b.occupied_beds,
            "held": b.held_beds,
            "free": free,
        }
        if b.bed_type in [BedType.GENERAL, BedType.ICU]:
            emergency_beds += free

    # Ensure all 4 bed types exist in dict even if 0
    for bt in BedType:
        if bt.value not in beds_map:
            beds_map[bt.value] = {
                "bed_type": bt.value,
                "total": 0,
                "occupied": 0,
                "held": 0,
                "free": 0,
            }

    return {
        "id": h.id,
        "name": h.name,
        "slug": h.slug,
        "phone": h.phone,
        "emergency_phone": h.emergency_phone,
        "address": h.address,
        "city": h.city,
        "latitude": h.latitude,
        "longitude": h.longitude,
        "is_verified": h.is_verified,
        "is_stale": h.is_stale,
        "last_updated_minutes_ago": h.minutes_since_update(),
        "facilities": h.facilities or [],
        "distance_km": dist_km,
        "estimated_time_min": time_min,
        "emergency_free_beds": emergency_beds,
        "beds": beds_map,
    }


@router.get("", response_model=List[HospitalBase])
def list_hospitals(
    lat: Optional[float] = Query(None, description="Patient GPS latitude"),
    lon: Optional[float] = Query(None, description="Patient GPS longitude"),
    specialty: Optional[str] = Query(None, description="Filter by doctor specialty"),
    q: Optional[str] = Query(None, description="Search keyword in hospital name or city"),
    db: Session = Depends(get_db),
):
    """
    Returns list of hospitals, dynamically sorted by proximity (distance in km).
    Includes live bed telemetry and data freshness indicator.
    """
    query = db.query(Hospital).filter(Hospital.is_active == True)

    if q:
        query = query.filter(
            or_(
                Hospital.name.ilike(f"%{q}%"),
                Hospital.city.ilike(f"%{q}%"),
                Hospital.address.ilike(f"%{q}%"),
            )
        )

    if specialty:
        query = query.join(Hospital.doctors).filter(Doctor.specialty.ilike(f"%{specialty}%"))

    hospitals = query.all()
    results = [format_hospital_summary(h, lat, lon) for h in hospitals]

    # Sort by distance if coordinates provided
    if lat is not None and lon is not None:
        results.sort(key=lambda x: (x["distance_km"] if x["distance_km"] is not None else 9999))
    else:
        results.sort(key=lambda x: x["name"])

    return results


@router.get("/emergency", response_model=List[dict])
def emergency_hospitals(
    lat: float = Query(..., description="Patient GPS latitude"),
    lon: float = Query(..., description="Patient GPS longitude"),
    max_results: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """
    🚨 EMERGENCY MODE:
    Instantly returns the nearest hospitals that have immediate free General or ICU beds.
    Includes direct emergency phone numbers and coordinates for GPS navigation.
    """
    hospitals = db.query(Hospital).filter(Hospital.is_active == True).all()

    filtered = []
    for h in hospitals:
        summary = format_hospital_summary(h, lat, lon)
        # Check if hospital has at least 1 free emergency bed (General or ICU)
        if summary["emergency_free_beds"] > 0:
            filtered.append(summary)

    # Sort strictly by shortest distance
    filtered.sort(key=lambda x: x["distance_km"])
    return filtered[:max_results]


@router.get("/{hospital_id}/emergency-details", response_model=dict)
def get_emergency_details(
    hospital_id: int,
    db: Session = Depends(get_db),
    now: datetime = Depends(lambda: datetime.now(timezone.utc)),
):
    """Return facilities and doctors with free slots for the next hour.
    Used by the emergency flow to show which doctors are actually available.
    """
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")

    # Facilities – already stored as JSON list
    facilities = hospital.facilities or []

    # Doctors that are Available and have at least one free slot within next hour
    now_local = now.astimezone(IST)
    upcoming = now_local + timedelta(hours=1)
    doctors_list = []
    for d in hospital.doctors:
        if d.status != DoctorStatus.AVAILABLE:
            continue
        slots = [
            {"id": s.id, "slot_time": s.slot_time}
            for s in d.slots
            if not s.is_booked and (t := _slot_datetime(s.slot_time, now_local)) and now_local <= t <= upcoming
        ]
        if slots:
            doctors_list.append({
                "id": d.id,
                "name": d.name,
                "specialty": d.specialty,
                "qualification": d.qualification,
                "experience_years": d.experience_years,
                "slots": slots,
            })

    return {
        "hospital_id": hospital.id,
        "name": hospital.name,
        "facilities": facilities,
        "doctors": doctors_list,
    }


@router.get("/{hospital_id}", response_model=HospitalDetailResponse)
def get_hospital_details(
    hospital_id: int,
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    db: Session = Depends(get_db),
):
    """Returns detailed hospital information, bed breakdowns, and active doctors with slot schedule."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")

    summary = format_hospital_summary(hospital, lat, lon)

    # Format doctors and bookable slots
    doctors_list = []
    for d in hospital.doctors:
        slots = [
            {"id": s.id, "slot_time": s.slot_time, "is_booked": s.is_booked}
            for s in d.slots
            if not s.is_booked
        ]
        doctors_list.append(
            {
                "id": d.id,
                "name": d.name,
                "specialty": d.specialty,
                "qualification": d.qualification,
                "experience_years": d.experience_years,
                "status": d.status,
                "status_updated_at": d.status_updated_at,
                "available_slots": slots,
            }
        )

    summary["doctors"] = doctors_list
    return summary
