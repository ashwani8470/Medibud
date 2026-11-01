import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.routers import auth_router, hospitals_router, bookings_router, admin_router, ws_router
from app.services.booking_service import release_expired_bed_holds
from app.seed.seed_data import seed_database

# Scheduler for periodic auto-release of expired 30-min bed holds
scheduler = BackgroundScheduler()


def auto_release_job():
    db = SessionLocal()
    try:
        released = release_expired_bed_holds(db)
        if released > 0:
            print(f"[Scheduler] Auto-released {released} expired bed hold(s).")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database tables are created & initial seed data exists
    Base.metadata.create_all(bind=engine)
    seed_database()

    # Start hold auto-release job every 20 seconds
    scheduler.add_job(auto_release_job, "interval", seconds=20, id="bed_hold_autorelease", replace_existing=True)
    scheduler.start()
    print("[MediBud Backend] Lifespan initialized, background scheduler active.")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    print("[MediBud Backend] Lifespan shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Real-time Hospital Availability & Emergency Booking Platform API",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials="*" not in settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(hospitals_router, prefix=settings.API_V1_STR)
app.include_router(bookings_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(ws_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "data_mode": settings.DATA_MODE,
    }


# Frontend static file serving & PWA support
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/manifest.json", include_in_schema=False)
    async def serve_manifest():
        manifest_file = os.path.join(frontend_dir, "manifest.json")
        if os.path.exists(manifest_file):
            return FileResponse(manifest_file, media_type="application/manifest+json")
        return {"error": "manifest not found"}

    @app.get("/sw.js", include_in_schema=False)
    async def serve_sw():
        sw_file = os.path.join(frontend_dir, "sw.js")
        if os.path.exists(sw_file):
            return FileResponse(
                sw_file,
                media_type="application/javascript",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        return {"error": "service worker not found"}

    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(
                index_file,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        return {"message": "Welcome to MediBud API. Frontend index not found, visit /docs for API documentation."}
