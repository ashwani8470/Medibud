import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.core.config import settings
from app.models.models import (
    Booking,
    BookingType,
    BookingStatus,
    HospitalBed,
    BedType,
    Doctor,
    DoctorSlot,
    Hospital,
    BedAuditLog,
)
from app.core.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


def generate_booking_code(prefix: str = "MB") -> str:
    """Generates a memorable 8-character unique booking code e.g. MB-784219."""
    token = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{token}"


def reserve_bed_hold(
    db: Session,
    hospital_id: int,
    bed_type: BedType,
    patient_name: str,
    patient_phone: str,
    emergency_notes: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Tuple[bool, Optional[Booking], str]:
    """
    Reserves a bed with a 30-minute hold window.
    Guarantees no double-booking via atomic check and transaction.
    """
    try:
        # Atomic selection of bed row with update intent
        bed = (
            db.query(HospitalBed)
            .filter(
                HospitalBed.hospital_id == hospital_id,
                HospitalBed.bed_type == bed_type,
            )
            .with_for_update()
            .first()
        )

        if not bed:
            return False, None, f"Bed type '{bed_type.value}' not configured for this hospital."

        free_count = bed.total_beds - (bed.occupied_beds + bed.held_beds)
        if free_count <= 0:
            return False, None, f"No free {bed_type.value} beds currently available at this hospital."

        # Increment held count
        bed.held_beds += 1
        bed.updated_at = datetime.now(timezone.utc)

        # Update hospital freshness timestamp
        hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if hospital:
            hospital.last_updated_at = datetime.now(timezone.utc)

        # Create booking record
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.BED_HOLD_DURATION_MINUTES)
        booking = Booking(
            booking_code=generate_booking_code("MB-BED"),
            user_id=user_id,
            hospital_id=hospital_id,
            booking_type=BookingType.BED_HOLD,
            status=BookingStatus.PENDING,
            bed_type=bed_type,
            hold_expires_at=expires_at,
            patient_name=patient_name,
            patient_phone=patient_phone,
            emergency_notes=emergency_notes,
        )
        db.add(booking)

        # Audit log entry
        audit = BedAuditLog(
            hospital_id=hospital_id,
            bed_type=bed_type,
            delta=-1,
            previous_count=free_count,
            new_count=free_count - 1,
            reason="BED_HOLD_RESERVATION",
            changed_by_user_id=user_id,
        )
        db.add(audit)

        db.commit()
        db.refresh(booking)

        logger.info(f"Bed hold granted: {booking.booking_code} for {patient_name} at Hospital #{hospital_id}")
        return True, booking, "Bed hold successfully reserved."

    except Exception as e:
        db.rollback()
        logger.error(f"Error in reserve_bed_hold: {e}")
        return False, None, f"Failed to hold bed: {str(e)}"


def reserve_doctor_appointment(
    db: Session,
    hospital_id: int,
    doctor_id: int,
    slot_id: int,
    patient_name: str,
    patient_phone: str,
    emergency_notes: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Tuple[bool, Optional[Booking], str]:
    """
    Books an appointment slot with double-booking prevention.
    """
    try:
        slot = (
            db.query(DoctorSlot)
            .filter(
                DoctorSlot.id == slot_id,
                DoctorSlot.doctor_id == doctor_id,
            )
            .with_for_update()
            .first()
        )

        if not slot:
            return False, None, "Slot not found."

        if slot.is_booked:
            return False, None, "This slot has already been booked by another patient."

        # Mark slot as booked
        slot.is_booked = True

        booking = Booking(
            booking_code=generate_booking_code("MB-DOC"),
            user_id=user_id,
            hospital_id=hospital_id,
            doctor_id=doctor_id,
            slot_id=slot_id,
            booking_type=BookingType.DOCTOR_APPOINTMENT,
            status=BookingStatus.CONFIRMED,
            patient_name=patient_name,
            patient_phone=patient_phone,
            emergency_notes=emergency_notes,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        return True, booking, "Appointment confirmed."

    except Exception as e:
        db.rollback()
        logger.error(f"Error in reserve_doctor_appointment: {e}")
        return False, None, f"Failed to book slot: {str(e)}"


def release_expired_bed_holds(db: Session) -> int:
    """
    Background worker job: Auto-releases bed holds whose 30-minute window has lapsed.
    Returns the count of released reservations.
    """
    now = datetime.now(timezone.utc)
    expired_bookings = (
        db.query(Booking)
        .filter(
            Booking.booking_type == BookingType.BED_HOLD,
            Booking.status == BookingStatus.PENDING,
            Booking.hold_expires_at <= now,
        )
        .all()
    )

    if not expired_bookings:
        return 0

    released_count = 0
    for booking in expired_bookings:
        try:
            # Revert held bed
            bed = (
                db.query(HospitalBed)
                .filter(
                    HospitalBed.hospital_id == booking.hospital_id,
                    HospitalBed.bed_type == booking.bed_type,
                )
                .first()
            )
            if bed and bed.held_beds > 0:
                bed.held_beds -= 1
                bed.updated_at = now

            booking.status = BookingStatus.EXPIRED
            booking.released_at = now

            audit = BedAuditLog(
                hospital_id=booking.hospital_id,
                bed_type=booking.bed_type,
                delta=+1,
                previous_count=bed.free_beds - 1 if bed else 0,
                new_count=bed.free_beds if bed else 0,
                reason="HOLD_EXPIRED_AUTORELEASE",
            )
            db.add(audit)
            released_count += 1
            logger.info(f"Released expired bed hold: {booking.booking_code}")
        except Exception as e:
            logger.error(f"Error releasing booking {booking.id}: {e}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to commit expired hold releases: {e}")

    return released_count
