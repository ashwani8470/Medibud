from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict
from app.models.models import UserRole


class UserRegister(BaseModel):
    """Schema for user registration.
    For staff roles (hospital_admin, hospital_staff, doctor) the ``hospital_id`` must be provided.
    """
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    phone: str = Field(..., pattern=r"^\+?[0-9]{10,15}$")
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = UserRole.PATIENT
    hospital_id: Optional[int] = None


class UserLogin(BaseModel):
    """Schema for login payload (email or phone + password)."""
    username: str  # Can be email or phone
    password: str


class Token(BaseModel):
    """JWT response payload.
    ``hospital_id`` is included for staff users.
    """
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    user_id: int
    full_name: str
    hospital_id: Optional[int] = None


class UserResponse(BaseModel):
    """Public representation of a user profile."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    phone: str
    full_name: str
    role: UserRole
    is_active: bool
    hospital_id: Optional[int] = None
    approval_status: str = "approved"


class StaffRequest(BaseModel):
    """A staff sign-up waiting for (or already given) super-admin review."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: str
    phone: str
    role: UserRole
    hospital_id: Optional[int] = None
    hospital_name: Optional[str] = None
    approval_status: str
    created_at: Optional[datetime] = None
