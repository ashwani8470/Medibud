from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.models.models import BedType, BookingType, BookingStatus


class BedHoldRequest(BaseModel):
    hospital_id: int
    bed_type: BedType
    patient_name: str = Field(..., min_length=2, max_length=100)
    patient_phone: str = Field(..., pattern=r"^\+?[0-9]{10,15}$")
    emergency_notes: Optional[str] = None


class DoctorAppointmentRequest(BaseModel):
    hospital_id: int
    doctor_id: int
    slot_id: int
    patient_name: str = Field(..., min_length=2, max_length=100)
    patient_phone: str = Field(..., pattern=r"^\+?[0-9]{10,15}$")
    emergency_notes: Optional[str] = None


class FacilityCheckupRequest(BaseModel):
    hospital_id: int
    service_name: str = Field(..., min_length=2, max_length=150)
    patient_name: str = Field(..., min_length=2, max_length=100)
    patient_phone: str = Field(..., pattern=r"^\+?[0-9]{10,15}$")
    doctor_id: Optional[int] = None
    slot_id: Optional[int] = None
    preferred_time_window: Optional[str] = None
    notes: Optional[str] = None


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_code: str
    booking_type: BookingType
    status: BookingStatus
    hospital_id: int
    hospital_name: str
    hospital_phone: str
    hospital_address: str
    
    bed_type: Optional[BedType] = None
    hold_expires_at: Optional[datetime] = None
    seconds_remaining: Optional[int] = None
    
    doctor_name: Optional[str] = None
    doctor_specialty: Optional[str] = None
    slot_time: Optional[str] = None

    service_name: Optional[str] = None
    preferred_time_window: Optional[str] = None
    
    patient_name: str
    patient_phone: str
    emergency_notes: Optional[str] = None
    created_at: datetime


class BookingStatusUpdateRequest(BaseModel):
    status: BookingStatus
