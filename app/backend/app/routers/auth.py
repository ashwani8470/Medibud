from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.models.models import User, UserRole, Hospital, HospitalStaff
from app.schemas.auth import UserRegister, UserLogin, Token, UserResponse, StaffRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token", auto_error=False)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Retrieves current authenticated user from JWT token, if provided."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing subject identity",
        )
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active or user.approval_status != "approved":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")
    return user


def require_user(current_user: Optional[User] = Depends(get_current_user)) -> User:
    """Enforces that a valid user is logged in."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for this operation",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_admin(current_user: Optional[User] = Depends(get_current_user)) -> Optional[User]:
    """Guards /admin/* routes. Enforced only when settings.ADMIN_AUTH_REQUIRED is True."""
    if not settings.ADMIN_AUTH_REQUIRED:
        return current_user
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user.role not in (UserRole.HOSPITAL_ADMIN, UserRole.HOSPITAL_STAFF, UserRole.DOCTOR, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_super_admin(current_user: Optional[User] = Depends(get_current_user)) -> User:
    """Always enforced: approving staff must never depend on the ADMIN_AUTH_REQUIRED demo switch."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")
    return current_user


def _staff_hospital_id(user: User) -> Optional[int]:
    """Hospital a staff user belongs to (direct link, else first staff membership)."""
    if user.hospital_id:
        return user.hospital_id
    if user.role != UserRole.PATIENT and user.staff_memberships:
        return user.staff_memberships[0].hospital_id
    return None


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserRegister,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Registers a new patient or staff user.

    - Patients are active immediately.
    - Staff (hospital_admin / hospital_staff / doctor) who sign up themselves are created as
      "pending" and cannot log in until approved (see approval rules below).
    - Only a logged-in super admin can create a super_admin, or pre-approved staff.
    """
    is_super = bool(current_user and current_user.role == UserRole.SUPER_ADMIN)
    if user_in.role == UserRole.SUPER_ADMIN and not is_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin accounts cannot be self-registered",
        )

    existing = db.query(User).filter(
        or_(User.email == user_in.email, User.phone == user_in.phone)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email or phone number already exists",
        )

    # Validate hospital_id for staff roles
    hospital_id = None
    if user_in.role != UserRole.PATIENT:
        if not user_in.hospital_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="hospital_id is required for staff registrations",
            )
        # Ensure the hospital exists
        hospital = db.query(Hospital).filter(Hospital.id == user_in.hospital_id).first()
        if not hospital:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified hospital does not exist",
            )
        hospital_id = user_in.hospital_id

    user = User(
        email=user_in.email,
        phone=user_in.phone,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        hospital_id=hospital_id,
        is_active=True,
        approval_status=(
            "approved" if (user_in.role == UserRole.PATIENT or is_super) else "pending"
        ),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(login_in: UserLogin, db: Session = Depends(get_db)):
    """Logs in using email or phone and returns access JWT token."""
    user = db.query(User).filter(
        or_(User.email == login_in.username, User.phone == login_in.username)
    ).first()

    if not user or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if user.approval_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your staff account is awaiting approval. Please try again later.",
        )
    if user.approval_status == "rejected" or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your staff request was not approved. Please contact the MediBud admin.",
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "name": user.full_name, "hospital_id": _staff_hospital_id(user)}
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
        hospital_id=_staff_hospital_id(user),
    )


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Standard OAuth2 form login for Swagger UI interactive testing."""
    user = db.query(User).filter(
        or_(User.email == form_data.username, User.phone == form_data.username)
    ).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if user.approval_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your staff account is awaiting approval. Please try again later.",
        )
    if user.approval_status == "rejected" or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your staff request was not approved. Please contact the MediBud admin.",
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "name": user.full_name, "hospital_id": _staff_hospital_id(user)}
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
        hospital_id=_staff_hospital_id(user),
    )


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(require_user)):
    """Returns the authenticated user's profile."""
    return current_user


# ------------------------------------------------------------------
# Staff approval workflow
#   - hospital_admin sign-ups  -> approved by a super admin only
#   - hospital_staff / doctor  -> approved by the admin of the SAME hospital, or a super admin
# ------------------------------------------------------------------
REVIEWABLE_ROLES = [UserRole.HOSPITAL_ADMIN, UserRole.HOSPITAL_STAFF, UserRole.DOCTOR]
ROLE_TITLES = {
    UserRole.HOSPITAL_ADMIN: "Hospital Admin",
    UserRole.HOSPITAL_STAFF: "Hospital Staff",
    UserRole.DOCTOR: "Doctor",
}


def require_approver(current_user: Optional[User] = Depends(get_current_user)) -> User:
    """Super admins and (approved) hospital admins may review staff requests. Always enforced."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def _can_review(approver: User, target: User) -> bool:
    if approver.role == UserRole.SUPER_ADMIN:
        return True
    # a hospital admin: only staff/doctors of their own hospital (never other admins)
    mine = _staff_hospital_id(approver)
    return (
        approver.role == UserRole.HOSPITAL_ADMIN
        and target.role in (UserRole.HOSPITAL_STAFF, UserRole.DOCTOR)
        and mine is not None
        and target.hospital_id == mine
    )


def _to_request(u: User, db: Session) -> StaffRequest:
    h = db.query(Hospital).filter(Hospital.id == u.hospital_id).first() if u.hospital_id else None
    return StaffRequest(
        id=u.id, full_name=u.full_name, email=u.email, phone=u.phone, role=u.role,
        hospital_id=u.hospital_id, hospital_name=h.name if h else None,
        approval_status=u.approval_status, created_at=u.created_at,
    )


@router.get("/staff-requests", response_model=list[StaffRequest])
def list_staff_requests(
    status_filter: str = "pending",
    db: Session = Depends(get_db),
    approver: User = Depends(require_approver),
):
    """Lists staff sign-ups the caller is allowed to review (default: pending), newest first."""
    q = db.query(User).filter(User.role.in_(REVIEWABLE_ROLES))
    if status_filter != "all":
        q = q.filter(User.approval_status == status_filter)
    return [_to_request(u, db) for u in q.order_by(User.created_at.desc()).all() if _can_review(approver, u)]


def _get_reviewable(user_id: int, approver: User, db: Session) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    # same 404 whether it doesn't exist or isn't yours to review (don't leak other hospitals)
    if not user or user.role not in REVIEWABLE_ROLES or not _can_review(approver, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff request not found")
    if user.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This request is already {user.approval_status}",
        )
    return user


@router.post("/staff-requests/{user_id}/approve", response_model=StaffRequest)
def approve_staff(user_id: int, db: Session = Depends(get_db), approver: User = Depends(require_approver)):
    user = _get_reviewable(user_id, approver, db)
    user.approval_status = "approved"
    user.is_verified = True
    user.is_active = True
    if user.hospital_id and not db.query(HospitalStaff).filter_by(user_id=user.id, hospital_id=user.hospital_id).first():
        db.add(HospitalStaff(
            hospital_id=user.hospital_id, user_id=user.id,
            role_title=ROLE_TITLES.get(user.role, "Staff Member"),
        ))
    db.commit()
    db.refresh(user)
    return _to_request(user, db)


@router.post("/staff-requests/{user_id}/reject", response_model=StaffRequest)
def reject_staff(user_id: int, db: Session = Depends(get_db), approver: User = Depends(require_approver)):
    user = _get_reviewable(user_id, approver, db)
    user.approval_status = "rejected"
    db.commit()
    db.refresh(user)
    return _to_request(user, db)
