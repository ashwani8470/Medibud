from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Booking, BookingType, BookingStatus, User, HospitalBed
from app.schemas.booking import (
    BedHoldRequest,
    DoctorAppointmentRequest,
    FacilityCheckupRequest,
    BookingResponse,
)
from app.services.booking_service import (
    reserve_bed_hold,
    reserve_doctor_appointment,
    generate_booking_code,
)
from app.routers.auth import get_current_user
from app.core.websocket_manager import ws_manager

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def format_booking_response(b: Booking) -> dict:
    """Helper to format booking with live countdown."""
    seconds_remaining = None
    if b.booking_type == BookingType.BED_HOLD and b.status == BookingStatus.PENDING and b.hold_expires_at:
        now = datetime.now(timezone.utc)
        exp = b.hold_expires_at.replace(tzinfo=timezone.utc) if b.hold_expires_at.tzinfo is None else b.hold_expires_at
        diff = int((exp - now).total_seconds())
        seconds_remaining = max(0, diff)

    return {
        "id": b.id,
        "booking_code": b.booking_code,
        "booking_type": b.booking_type,
        "status": b.status,
        "hospital_id": b.hospital_id,
        "hospital_name": b.hospital.name if b.hospital else "Hospital",
        "hospital_phone": b.hospital.phone if b.hospital else "",
        "hospital_address": b.hospital.address if b.hospital else "",
        "bed_type": b.bed_type,
        "hold_expires_at": b.hold_expires_at,
        "seconds_remaining": seconds_remaining,
        "doctor_name": b.doctor.name if b.doctor else None,
        "doctor_specialty": b.doctor.specialty if b.doctor else None,
        "slot_time": b.slot.slot_time if b.slot else None,
        "service_name": b.service_name,
        "preferred_time_window": b.preferred_time_window,
        "patient_name": b.patient_name,
        "patient_phone": b.patient_phone,
        "emergency_notes": b.emergency_notes,
        "created_at": b.created_at,
    }


@router.post("/bed-hold", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_bed_hold(
    payload: BedHoldRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Reserve a bed with a 30-minute hold window.
    Protected against race-conditions and double-booking.
    """
    user_id = current_user.id if current_user else None
    success, booking, message = reserve_bed_hold(
        db=db,
        hospital_id=payload.hospital_id,
        bed_type=payload.bed_type,
        patient_name=payload.patient_name,
        patient_phone=payload.patient_phone,
        emergency_notes=payload.emergency_notes,
        user_id=user_id,
    )

    if not success or not booking:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)

    # Broadcast real-time bed inventory change to all connected clients
    bed = (
        db.query(HospitalBed)
        .filter(
            HospitalBed.hospital_id == payload.hospital_id,
            HospitalBed.bed_type == payload.bed_type,
        )
        .first()
    )
    if bed:
        await ws_manager.broadcast({
            "event": "bed_update",
            "hospital_id": payload.hospital_id,
            "bed_type": payload.bed_type.value,
            "free": bed.free_beds,
            "total": bed.total_beds,
            "occupied": bed.occupied_beds,
            "held": bed.held_beds,
        })

    return format_booking_response(booking)


@router.post("/appointment", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_doctor_appointment(
    payload: DoctorAppointmentRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Book a confirmed doctor consultation slot."""
    user_id = current_user.id if current_user else None
    success, booking, message = reserve_doctor_appointment(
        db=db,
        hospital_id=payload.hospital_id,
        doctor_id=payload.doctor_id,
        slot_id=payload.slot_id,
        patient_name=payload.patient_name,
        patient_phone=payload.patient_phone,
        emergency_notes=payload.emergency_notes,
        user_id=user_id,
    )

    if not success or not booking:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)

    return format_booking_response(booking)


@router.post("/checkup", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_facility_checkup_booking(
    payload: FacilityCheckupRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Guided Requirement-Based Booking:
    - If doctor_id is provided: books doctor slot for that consultation.
    - If doctor_id is None: books direct facility checkup (e.g. MRI, CT Scan, Lab tests).
    """
    user_id = current_user.id if current_user else None

    # If doctor consultation is needed for this service
    if payload.doctor_id and payload.slot_id:
        success, booking, message = reserve_doctor_appointment(
            db=db,
            hospital_id=payload.hospital_id,
            doctor_id=payload.doctor_id,
            slot_id=payload.slot_id,
            patient_name=payload.patient_name,
            patient_phone=payload.patient_phone,
            emergency_notes=f"Service: {payload.service_name}. Notes: {payload.notes or ''}".strip(),
            user_id=user_id,
        )
        if not success or not booking:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)

        # Set service name on booking
        booking.service_name = payload.service_name
        booking.preferred_time_window = payload.preferred_time_window
        db.commit()
        db.refresh(booking)
        return format_booking_response(booking)

    # Direct facility/lab checkup without doctor consultation
    code = generate_booking_code("MB-CHK")
    booking = Booking(
        booking_code=code,
        user_id=user_id,
        hospital_id=payload.hospital_id,
        booking_type=BookingType.FACILITY_CHECKUP,
        status=BookingStatus.CONFIRMED,
        service_name=payload.service_name,
        preferred_time_window=payload.preferred_time_window or "Morning 09:00 - 12:00",
        patient_name=payload.patient_name,
        patient_phone=payload.patient_phone,
        emergency_notes=payload.notes,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return format_booking_response(booking)


@router.get("/{booking_code}", response_model=BookingResponse)
def get_booking_by_code(booking_code: str, db: Session = Depends(get_db)):
    """Look up a booking by human-readable reference code."""
    booking = db.query(Booking).filter(Booking.booking_code == booking_code.upper()).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking code not found")
    return format_booking_response(booking)


@router.get("", response_model=List[BookingResponse])
def get_my_bookings(
    phone: Optional[str] = Query(None, description="Lookup by phone number if not logged in"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Returns booking history for the current user or phone."""
    query = db.query(Booking)
    if current_user:
        query = query.filter(Booking.user_id == current_user.id)
    elif phone:
        query = query.filter(Booking.patient_phone == phone)
    else:
        # Return recent public bookings for demo purposes
        query = query.order_by(Booking.created_at.desc()).limit(10)
        return [format_booking_response(b) for b in query.all()]

    bookings = query.order_by(Booking.created_at.desc()).all()
    return [format_booking_response(b) for b in bookings]


@router.post("/{booking_code}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_code: str,
    db: Session = Depends(get_db),
):
    """Cancel booking and immediately release bed or doctor slot."""
    booking = db.query(Booking).filter(Booking.booking_code == booking_code.upper()).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking code not found")

    if booking.status in [BookingStatus.CANCELLED, BookingStatus.COMPLETED, BookingStatus.EXPIRED]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Booking is already {booking.status.value}")

    # Release resource
    if booking.booking_type == BookingType.BED_HOLD and booking.bed_type:
        bed = (
            db.query(HospitalBed)
            .filter(HospitalBed.hospital_id == booking.hospital_id, HospitalBed.bed_type == booking.bed_type)
            .first()
        )
        if bed and bed.held_beds > 0:
            bed.held_beds -= 1
            bed.updated_at = datetime.now(timezone.utc)
            db.commit()
            
            # Broadcast release
            await ws_manager.broadcast({
                "event": "bed_update",
                "hospital_id": booking.hospital_id,
                "bed_type": booking.bed_type.value,
                "free": bed.free_beds,
                "total": bed.total_beds,
                "occupied": bed.occupied_beds,
                "held": bed.held_beds,
            })

    if booking.slot:
        booking.slot.is_booked = False

    booking.status = BookingStatus.CANCELLED
    booking.released_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(booking)

    return format_booking_response(booking)
