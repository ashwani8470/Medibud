from app.routers.auth import router as auth_router
from app.routers.hospitals import router as hospitals_router
from app.routers.bookings import router as bookings_router
from app.routers.admin import router as admin_router
from app.routers.ws import router as ws_router

__all__ = [
    "auth_router",
    "hospitals_router",
    "bookings_router",
    "admin_router",
    "ws_router",
]
