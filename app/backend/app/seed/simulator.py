import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Optional

from app.core.database import SessionLocal
from app.models.models import Hospital, HospitalBed, Doctor, DoctorStatus, BedType, BedAuditLog
from app.core.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


class LiveUpdateSimulator:
    """
    Simulates real-world hospital activity during live demos by randomly:
    1. Incrementing/decrementing bed counts (patient admissions/discharges)
    2. Toggling doctor statuses (doctor entering surgery or coming back on duty)
    Broadcasts real-time events through WebSockets to all connected browsers.
    """

    def __init__(self, interval_seconds: float = 4.0):
        self.interval_seconds = interval_seconds
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._simulation_loop())
            logger.info("⚡ Live demo simulator started.")

    def stop(self):
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("🛑 Live demo simulator stopped.")

    async def _simulation_loop(self):
        while self.is_running:
            try:
                await asyncio.sleep(self.interval_seconds)
                await self._execute_random_event()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in simulator loop: {e}")

    async def _execute_random_event(self):
        db = SessionLocal()
        try:
            hospitals = db.query(Hospital).all()
            if not hospitals:
                return

            chosen_hospital = random.choice(hospitals)
            now = datetime.now(timezone.utc)
            chosen_hospital.last_updated_at = now

            # 70% chance of bed fluctuation, 30% chance of doctor status change
            if random.random() < 0.7:
                beds = db.query(HospitalBed).filter(HospitalBed.hospital_id == chosen_hospital.id).all()
                if not beds:
                    return
                bed = random.choice(beds)
                delta = 1 if random.random() < 0.5 else -1

                old_free = bed.free_beds
                if delta == -1 and old_free > 0:
                    bed.occupied_beds += 1
                elif delta == 1 and bed.occupied_beds > 0:
                    bed.occupied_beds -= 1
                else:
                    return

                bed.updated_at = now
                audit = BedAuditLog(
                    hospital_id=chosen_hospital.id,
                    bed_type=bed.bed_type,
                    delta=delta,
                    previous_count=old_free,
                    new_count=bed.free_beds,
                    reason="DEMO_SIMULATOR_FLUCTUATION",
                )
                db.add(audit)
                db.commit()

                # Broadcast live update
                await ws_manager.broadcast({
                    "event": "bed_update",
                    "hospital_id": chosen_hospital.id,
                    "hospital_name": chosen_hospital.name,
                    "bed_type": bed.bed_type.value,
                    "free": bed.free_beds,
                    "total": bed.total_beds,
                    "occupied": bed.occupied_beds,
                    "held": bed.held_beds,
                    "last_updated_minutes_ago": 0,
                })
            else:
                doctors = db.query(Doctor).filter(Doctor.hospital_id == chosen_hospital.id).all()
                if not doctors:
                    return
                doc = random.choice(doctors)
                cycle = [DoctorStatus.AVAILABLE, DoctorStatus.IN_SURGERY, DoctorStatus.OFF_DUTY]
                current_idx = cycle.index(doc.status) if doc.status in cycle else 0
                doc.status = cycle[(current_idx + 1) % len(cycle)]
                doc.status_updated_at = now
                db.commit()

                await ws_manager.broadcast({
                    "event": "doctor_update",
                    "hospital_id": chosen_hospital.id,
                    "doctor_id": doc.id,
                    "doctor_name": doc.name,
                    "status": doc.status.value,
                })
        except Exception as e:
            db.rollback()
            logger.error(f"Simulator event error: {e}")
        finally:
            db.close()


simulator = LiveUpdateSimulator()
