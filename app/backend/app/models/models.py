from __future__ import annotations
import enum
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Text,
    CheckConstraint,
    Index,
    JSON,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from app.core.database import Base


# -------------------------------------------------------------------------
# Enums
# -------------------------------------------------------------------------
class UserRole(str, enum.Enum):
    PATIENT = "patient"
    HOSPITAL_ADMIN = "hospital_admin"
    HOSPITAL_STAFF = "hospital_staff"
    DOCTOR = "doctor"
    SUPER_ADMIN = "super_admin"


class BedType(str, enum.Enum):
    GENERAL = "general"
    ICU = "icu"
    VENTILATOR = "ventilator"
    OXYGEN = "oxygen"


class DoctorStatus(str, enum.Enum):
    AVAILABLE = "available"
    IN_SURGERY = "in_surgery"
    OFF_DUTY = "off_duty"
    ON_LEAVE = "on_leave"


class BookingType(str, enum.Enum):
    BED_HOLD = "bed_hold"
    DOCTOR_APPOINTMENT = "doctor_appointment"
    FACILITY_CHECKUP = "facility_checkup"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"          # Active hold / slot booked awaiting arrival
    CONFIRMED = "confirmed"      # Verified by hospital staff
    ADMITTED = "admitted"        # Patient arrived and admitted to bed
    COMPLETED = "completed"      # Consultation or discharge finished
    CANCELLED = "cancelled"      # Cancelled by user or hospital
    EXPIRED = "expired"          # Bed hold auto-released after timeout (e.g. 30 min)


# -------------------------------------------------------------------------
# 1. User Model
# -------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.PATIENT, nullable=False)
    # For staff users, reference the hospital they belong to (nullable for patients)
    hospital_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Staff self-sign-ups start as "pending" until a super admin approves them.
    # Values: "approved" | "pending" | "rejected"
    approval_status: Mapped[str] = mapped_column(String(10), default="approved", server_default="approved", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    staff_memberships: Mapped[List[HospitalStaff]] = relationship(back_populates="user", cascade="all, delete-orphan")
    doctor_profile: Mapped[Optional[Doctor]] = relationship(back_populates="user", uselist=False)
    bookings: Mapped[List[Booking]] = relationship(back_populates="user")


# -------------------------------------------------------------------------
# 2. Hospital Model
# -------------------------------------------------------------------------
class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    emergency_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    
    # Coordinates for Haversine distance calculations
    latitude: Mapped[float] = mapped_column(Float, index=True, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, index=True, nullable=False)

    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Freshness indicator
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False
    )

    # Facilities e.g. ["24x7 Emergency", "Ambulance", "Pharmacy", "Blood Bank", "Lab"]
    facilities: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    # Services offered (e.g., "General Checkup", "MRI", "CT Scan", "Blood Test")
    services: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)


    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    staff: Mapped[List[HospitalStaff]] = relationship(back_populates="hospital", cascade="all, delete-orphan")
    beds: Mapped[List[HospitalBed]] = relationship(back_populates="hospital", cascade="all, delete-orphan")
    doctors: Mapped[List[Doctor]] = relationship(back_populates="hospital", cascade="all, delete-orphan")
    bookings: Mapped[List[Booking]] = relationship(back_populates="hospital")
    audit_logs: Mapped[List[BedAuditLog]] = relationship(back_populates="hospital", cascade="all, delete-orphan")

    def minutes_since_update(self) -> int:
        delta = datetime.now(timezone.utc) - self.last_updated_at.replace(tzinfo=timezone.utc)
        return max(0, int(delta.total_seconds() / 60))

    @property
    def is_stale(self) -> bool:
        """Data unconfirmed > 120 minutes is considered stale."""
        return self.minutes_since_update() > 120


# -------------------------------------------------------------------------
# 3. Hospital Staff Junction Model
# -------------------------------------------------------------------------
class HospitalStaff(Base):
    __tablename__ = "hospital_staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_title: Mapped[str] = mapped_column(String(100), default="Staff Member", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    hospital: Mapped[Hospital] = relationship(back_populates="staff")
    user: Mapped[User] = relationship(back_populates="staff_memberships")


# -------------------------------------------------------------------------
# 4. Hospital Bed Inventory Model (Atomic Safety & Zero-Double Booking)
# -------------------------------------------------------------------------
class HospitalBed(Base):
    __tablename__ = "hospital_beds"
    __table_args__ = (
        CheckConstraint("total_beds >= 0", name="chk_total_beds_positive"),
        CheckConstraint("occupied_beds >= 0", name="chk_occupied_beds_positive"),
        CheckConstraint("held_beds >= 0", name="chk_held_beds_positive"),
        CheckConstraint("(occupied_beds + held_beds) <= total_beds", name="chk_bed_capacity_limits"),
        Index("idx_hospital_bed_type", "hospital_id", "bed_type", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    bed_type: Mapped[BedType] = mapped_column(SQLEnum(BedType), nullable=False)
    
    total_beds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    occupied_beds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    held_beds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    hospital: Mapped[Hospital] = relationship(back_populates="beds")

    @property
    def free_beds(self) -> int:
        """Immediately bookable beds."""
        return max(0, self.total_beds - self.occupied_beds - self.held_beds)


# -------------------------------------------------------------------------
# 5. Doctor Model
# -------------------------------------------------------------------------
class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    qualification: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    experience_years: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    status: Mapped[DoctorStatus] = mapped_column(
        SQLEnum(DoctorStatus), default=DoctorStatus.AVAILABLE, nullable=False
    )
    status_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    hospital: Mapped[Hospital] = relationship(back_populates="doctors")
    user: Mapped[Optional[User]] = relationship(back_populates="doctor_profile")
    slots: Mapped[List[DoctorSlot]] = relationship(back_populates="doctor", cascade="all, delete-orphan")
    bookings: Mapped[List[Booking]] = relationship(back_populates="doctor")


# -------------------------------------------------------------------------
# 6. Doctor Slot Model
# -------------------------------------------------------------------------
class DoctorSlot(Base):
    __tablename__ = "doctor_slots"
    __table_args__ = (
        Index("idx_doctor_slot_time", "doctor_id", "slot_time", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False)
    slot_time: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "10:00", "11:30", "14:00"
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    doctor: Mapped[Doctor] = relationship(back_populates="slots")
    booking: Mapped[Optional[Booking]] = relationship(back_populates="slot", uselist=False)


# -------------------------------------------------------------------------
# 7. Unified Booking Model (Bed Hold & Doctor Appointment)
# -------------------------------------------------------------------------
class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        Index("idx_booking_code", "booking_code", unique=True),
        Index("idx_booking_status_expires", "status", "hold_expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    
    booking_type: Mapped[BookingType] = mapped_column(SQLEnum(BookingType), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus), default=BookingStatus.PENDING, nullable=False
    )

    # Bed Hold fields
    bed_type: Mapped[Optional[BedType]] = mapped_column(SQLEnum(BedType), nullable=True)
    hold_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    admitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Doctor Appointment fields
    doctor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True)
    slot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("doctor_slots.id", ondelete="SET NULL"), nullable=True)

    # Facility Checkup fields
    service_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    preferred_time_window: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # Patient info snapshot
    patient_name: Mapped[str] = mapped_column(String(100), nullable=False)
    patient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    emergency_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped[Optional[User]] = relationship(back_populates="bookings")
    hospital: Mapped[Hospital] = relationship(back_populates="bookings")
    doctor: Mapped[Optional[Doctor]] = relationship(back_populates="bookings")
    slot: Mapped[Optional[DoctorSlot]] = relationship(back_populates="booking")
    prearrival_requests: Mapped[List[PreArrivalRequest]] = relationship(
        back_populates="booking", cascade="all, delete-orphan", order_by="PreArrivalRequest.id"
    )


# -------------------------------------------------------------------------
# 7b. Pre-arrival requests (things the patient asks the hospital to prepare)
# -------------------------------------------------------------------------
PREARRIVAL_TYPES = (
    "ventilator",
    "oxygen",
    "trauma_team",
    "ambulance",
    "blood_check",
    "medicine_kit",
)


class PreArrivalRequest(Base):
    __tablename__ = "prearrival_requests"
    __table_args__ = (
        Index("idx_prearrival_booking_type", "booking_id", "request_type", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    request_type: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # blood group / medicines
    # requested -> ready (set by hospital staff) | cancelled (by patient)
    status: Mapped[str] = mapped_column(String(20), default="requested", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    booking: Mapped[Booking] = relationship(back_populates="prearrival_requests")


# -------------------------------------------------------------------------
# 8. Bed Audit Log
# -------------------------------------------------------------------------
class BedAuditLog(Base):
    __tablename__ = "bed_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    bed_type: Mapped[BedType] = mapped_column(SQLEnum(BedType), nullable=False)
    
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_count: Mapped[int] = mapped_column(Integer, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, nullable=False)
    
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    hospital: Mapped[Hospital] = relationship(back_populates="audit_logs")
