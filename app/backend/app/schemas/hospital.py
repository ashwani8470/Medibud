from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.models import BedType, DoctorStatus


class BedStatusResponse(BaseModel):
    bed_type: BedType
    total: int
    occupied: int
    held: int
    free: int


class DoctorSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slot_time: str
    is_booked: bool


class DoctorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    specialty: str
    qualification: Optional[str] = None
    experience_years: int
    status: DoctorStatus
    status_updated_at: datetime
    available_slots: List[DoctorSlotResponse] = []


class HospitalBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    phone: str
    emergency_phone: str
    address: str
    city: str
    latitude: float
    longitude: float
    is_verified: bool
    is_stale: bool
    last_updated_minutes_ago: int
    services: List[str] = []

    
    # Distance calculated dynamically per user location
    distance_km: Optional[float] = None
    estimated_time_min: Optional[int] = None
    
    # Emergency bed count (General + ICU with immediate availability)
    emergency_free_beds: int = 0
    beds: Dict[str, BedStatusResponse] = {}


class HospitalDetailResponse(HospitalBase):
    doctors: List[DoctorResponse] = []


class BedAdjustmentRequest(BaseModel):
    hospital_id: int
    bed_type: BedType
    delta: int  # +1 to increase free beds, -1 to decrease free beds


class DoctorStatusUpdateRequest(BaseModel):
    status: DoctorStatus
