from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.models.models import User, UserRole
from app.schemas.auth import UserRegister, UserLogin, Token, UserResponse

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
    if not user or not user.is_active:
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
    if current_user.role not in (UserRole.HOSPITAL_ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserRegister,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Registers a new patient or staff user.

    When ADMIN_AUTH_REQUIRED is on, only a super_admin may create staff accounts,
    so nobody can self-register as an admin.
    """
    if (
        user_in.role != UserRole.PATIENT
        and settings.ADMIN_AUTH_REQUIRED
        and (not current_user or current_user.role != UserRole.SUPER_ADMIN)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a super admin can create staff accounts",
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
        from app.models.models import Hospital
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

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "name": user.full_name, "hospital_id": user.hospital_id}
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
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

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value, "name": user.full_name, "hospital_id": user.hospital_id}
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(require_user)):
    """Returns the authenticated user's profile."""
    return current_user
