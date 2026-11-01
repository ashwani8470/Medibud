from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import (
    Hospital,
    HospitalBed,
    BedType,
    Doctor,
    DoctorStatus,
    Booking,
    BookingType,
    BookingStatus,
    BedAuditLog,
)
from app.schemas.hospital import BedAdjustmentRequest, DoctorStatusUpdateRequest
from app.schemas.booking import BookingResponse
from app.core.websocket_manager import ws_manager
from app.routers.bookings import format_booking_response
from app.seed.simulator import simulator
from app.routers.auth import require_admin

router = APIRouter(prefix="/admin", tags=["Hospital Staff & Admin"], dependencies=[Depends(require_admin)])


@router.get("/simulator/status")
def get_simulator_status():
    """Returns current active status of the live demo fluctuation simulator."""
    return {"is_running": simulator.is_running}


@router.post("/simulator/toggle")
def toggle_simulator(enable: bool = Query(..., description="True to start, False to stop")):
    """Toggle the demo simulator on/off."""
    if enable:
        simulator.start()
    else:
        simulator.stop()
    return {"status": "ok", "is_running": simulator.is_running}


@router.post("/beds/adjust")
async def adjust_bed_inventory(
    payload: BedAdjustmentRequest,
    db: Session = Depends(get_db),
):
    """
    ⚡ ZERO-FRICTION 1-TAP BED ADJUSTMENT FOR HOSPITAL STAFF:
    - delta: +1 adds a free bed (e.g. patient discharged: occupied_beds -= 1)
    - delta: -1 removes a free bed (e.g. walk-in triage admission: occupied_beds += 1)
    Automatically updates hospital freshness timestamp and broadcasts live via WebSocket.
    """
    bed = (
        db.query(HospitalBed)
        .filter(
            HospitalBed.hospital_id == payload.hospital_id,
            HospitalBed.bed_type == payload.bed_type,
        )
        .with_for_update()
        .first()
    )

    if not bed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bed inventory record not found")

    old_free = bed.free_beds

    if payload.delta == -1:
        # One less free bed -> occupy a bed
        if old_free <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No free beds remaining to occupy")
        bed.occupied_beds += 1
    elif payload.delta == 1:
        # One more free bed -> discharge an occupied bed
        if bed.occupied_beds <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Occupied bed count is already 0")
        bed.occupied_beds = max(0, bed.occupied_beds - 1)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Delta must be +1 or -1")

    now = datetime.now(timezone.utc)
    bed.updated_at = now

    hospital = db.query(Hospital).filter(Hospital.id == payload.hospital_id).first()
    if hospital:
        hospital.last_updated_at = now

    # Audit log
    audit = BedAuditLog(
        hospital_id=payload.hospital_id,
        bed_type=payload.bed_type,
        delta=payload.delta,
        previous_count=old_free,
        new_count=bed.free_beds,
        reason="STAFF_ONE_TAP_ADJUST",
    )
    db.add(audit)
    db.commit()

    # Real-time WebSocket broadcast to all connected patients & staff
    await ws_manager.broadcast({
        "event": "bed_update",
        "hospital_id": payload.hospital_id,
        "bed_type": payload.bed_type.value,
        "free": bed.free_beds,
        "total": bed.total_beds,
        "occupied": bed.occupied_beds,
        "held": bed.held_beds,
        "last_updated_minutes_ago": 0,
    })

    return {
        "status": "success",
        "hospital_id": payload.hospital_id,
        "bed_type": payload.bed_type.value,
        "free": bed.free_beds,
        "total": bed.total_beds,
        "occupied": bed.occupied_beds,
        "held": bed.held_beds,
    }


@router.post("/doctors/{doctor_id}/status")
async def update_doctor_status(
    doctor_id: int,
    payload: DoctorStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    ⚡ ZERO-FRICTION 1-TAP DOCTOR STATUS TOGGLE:
    Switches between: Available, In Surgery, Off Duty.
    Broadcasts live to all clients.
    """
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    now = datetime.now(timezone.utc)
    doctor.status = payload.status
    doctor.status_updated_at = now

    hospital = db.query(Hospital).filter(Hospital.id == doctor.hospital_id).first()
    if hospital:
        hospital.last_updated_at = now

    db.commit()

    # Broadcast live status update
    await ws_manager.broadcast({
        "event": "doctor_update",
        "hospital_id": doctor.hospital_id,
        "doctor_id": doctor.id,
        "doctor_name": doctor.name,
        "status": doctor.status.value,
    })

    return {
        "status": "success",
        "doctor_id": doctor.id,
        "doctor_status": doctor.status.value,
    }


@router.get("/hospitals/{hospital_id}/bookings", response_model=List[BookingResponse])
def list_hospital_bookings(
    hospital_id: int,
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Staff view of incoming patient queue, active holds, and check-ins."""
    query = db.query(Booking).filter(Booking.hospital_id == hospital_id)
    if status_filter:
        query = query.filter(Booking.status == status_filter)

    bookings = query.order_by(Booking.created_at.desc()).all()
    return [format_booking_response(b) for b in bookings]


@router.post("/bookings/{booking_id}/admit", response_model=BookingResponse)
async def admit_held_patient(
    booking_id: int,
    db: Session = Depends(get_db),
):
    """
    When patient arrives at the emergency gate, staff clicks 'Admit':
    Converts 30-min hold to official hospital admission (held_beds - 1, occupied_beds + 1).
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot admit a booking in '{booking.status.value}' state",
        )

    now = datetime.now(timezone.utc)

    # Shift bed from held to occupied
    if booking.booking_type == BookingType.BED_HOLD and booking.bed_type:
        bed = (
            db.query(HospitalBed)
            .filter(
                HospitalBed.hospital_id == booking.hospital_id,
                HospitalBed.bed_type == booking.bed_type,
            )
            .first()
        )
        if bed:
            if bed.held_beds > 0:
                bed.held_beds -= 1
            bed.occupied_beds += 1
            bed.updated_at = now

    booking.status = BookingStatus.ADMITTED
    booking.admitted_at = now
    db.commit()
    db.refresh(booking)

    # Broadcast update
    if booking.booking_type == BookingType.BED_HOLD and booking.bed_type:
        bed = (
            db.query(HospitalBed)
            .filter(
                HospitalBed.hospital_id == booking.hospital_id,
                HospitalBed.bed_type == booking.bed_type,
            )
            .first()
        )
        if bed:
            await ws_manager.broadcast({
                "event": "bed_update",
                "hospital_id": booking.hospital_id,
                "bed_type": booking.bed_type.value,
                "free": bed.free_beds,
                "total": bed.total_beds,
                "occupied": bed.occupied_beds,
                "held": bed.held_beds,
            })

    return format_booking_response(booking)
