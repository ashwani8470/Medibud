from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "MediBud"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str = "sqlite:///./medibud.db"
    
    # JWT Authentication
    # Override via .env / environment in any real deployment (SECRET_KEY=...)
    SECRET_KEY: str = "dev-only-insecure-key-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    
    # Operation Rules
    BED_HOLD_DURATION_MINUTES: int = 30
    STALE_THRESHOLD_MINUTES: int = 120  # 2 hours before hospital flagged stale
    
    # Demo & Simulator
    DATA_MODE: str = "dummy"  # "dummy" | "real"
    IS_DEMO: bool = True

    # When True, /admin/* endpoints require a logged-in hospital_admin/super_admin.
    # Default False so the no-login demo UI keeps working; set True for real use.
    ADMIN_AUTH_REQUIRED: bool = False
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
