from app.schemas.auth import UserRegister, UserLogin, Token, UserResponse
from app.schemas.hospital import (
    BedStatusResponse,
    DoctorSlotResponse,
    DoctorResponse,
    HospitalBase,
    HospitalDetailResponse,
    BedAdjustmentRequest,
    DoctorStatusUpdateRequest,
)
from app.schemas.booking import (
    BedHoldRequest,
    DoctorAppointmentRequest,
    FacilityCheckupRequest,
    BookingResponse,
    BookingStatusUpdateRequest,
)

__all__ = [
    "UserRegister",
    "UserLogin",
    "Token",
    "UserResponse",
    "BedStatusResponse",
    "DoctorSlotResponse",
    "DoctorResponse",
    "HospitalBase",
    "HospitalDetailResponse",
    "BedAdjustmentRequest",
    "DoctorStatusUpdateRequest",
    "BedHoldRequest",
    "DoctorAppointmentRequest",
    "FacilityCheckupRequest",
    "BookingResponse",
    "BookingStatusUpdateRequest",
]
