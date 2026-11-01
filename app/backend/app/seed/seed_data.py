import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine, Base
from app.core.security import hash_password
from app.models.models import (
    User,
    UserRole,
    Hospital,
    HospitalStaff,
    HospitalBed,
    BedType,
    Doctor,
    DoctorStatus,
    DoctorSlot,
)


HOSPITAL_DATA = [
    {
        "name": "Lifeline Super Speciality Hospital",
        "slug": "lifeline-super-speciality",
        "phone": "+91 98390 12001",
        "emergency_phone": "+91 98390 11999",
        "address": "14/112 Civil Lines, Near Mall Road",
        "city": "Kanpur",
        "latitude": 26.4695,
        "longitude": 80.3512,
        "facilities": ["24x7 Emergency", "Ambulance", "ICU", "Blood Bank", "Pharmacy", "CT Scan"],
    },
    {
        "name": "Apex Heart & Trauma Centre",
        "slug": "apex-heart-trauma",
        "phone": "+91 98390 22002",
        "emergency_phone": "+91 98390 22999",
        "address": "Plot 8, Kakadeo Coaching Hub",
        "city": "Kanpur",
        "latitude": 26.4782,
        "longitude": 80.3025,
        "facilities": ["24x7 Emergency", "Ambulance", "Cath Lab", "Blood Bank", "Pharmacy"],
    },
    {
        "name": "City Care Multi-Speciality",
        "slug": "city-care-multi-speciality",
        "phone": "+91 98390 33003",
        "emergency_phone": "+91 98390 33999",
        "address": "Kalyanpur Main GT Road, Near Metro Pillar 42",
        "city": "Kanpur",
        "latitude": 26.5085,
        "longitude": 80.2440,
        "facilities": ["24x7 Emergency", "Ambulance", "Pediatrics ICU", "Pharmacy"],
    },
    {
        "name": "Sunrise Critical Care Hospital",
        "slug": "sunrise-critical-care",
        "phone": "+91 98390 44004",
        "emergency_phone": "+91 98390 44999",
        "address": "Swaroop Nagar, Near Phoolbagh Crossing",
        "city": "Kanpur",
        "latitude": 26.4810,
        "longitude": 80.3250,
        "facilities": ["24x7 Emergency", "Ventilators", "Blood Bank", "Diagnostics"],
    },
    {
        "name": "Metro Neuro & Orthopedic Hospital",
        "slug": "metro-neuro-ortho",
        "phone": "+91 98390 55005",
        "emergency_phone": "+91 98390 55999",
        "address": "Kidwai Nagar Block K, Near Market",
        "city": "Kanpur",
        "latitude": 26.4320,
        "longitude": 80.3340,
        "facilities": ["24x7 Emergency", "Ambulance", "MRI", "Physiotherapy"],
    },
    {
        "name": "Shanti Memorial Emergency Hospital",
        "slug": "shanti-memorial-emergency",
        "phone": "+91 98390 66006",
        "emergency_phone": "+91 98390 66999",
        "address": "Govind Nagar Crossing, Near Ratan Lal Nagar",
        "city": "Kanpur",
        "latitude": 26.4460,
        "longitude": 80.3010,
        "facilities": ["24x7 Emergency", "Dialysis", "Pharmacy", "Oxygen Plant"],
    },
    {
        "name": "Aarogya Health City",
        "slug": "aarogya-health-city",
        "phone": "+91 98390 77007",
        "emergency_phone": "+91 98390 77999",
        "address": "Rawatpur Station Road",
        "city": "Kanpur",
        "latitude": 26.4880,
        "longitude": 80.2920,
        "facilities": ["24x7 Emergency", "Blood Bank", "Trauma Unit", "Neonatal ICU"],
    },
    {
        "name": "Green Cross Surgical Institute",
        "slug": "green-cross-surgical",
        "phone": "+91 98390 88008",
        "emergency_phone": "+91 98390 88999",
        "address": "Chunniganj Bus Stand Road",
        "city": "Kanpur",
        "latitude": 26.4740,
        "longitude": 80.3420,
        "facilities": ["24x7 Emergency", "Modular OTs", "Burn Unit", "Pharmacy"],
    },
    {
        "name": "Care Plus Cantonment Hospital",
        "slug": "care-plus-cantt",
        "phone": "+91 98390 99009",
        "emergency_phone": "+91 98390 99999",
        "address": "The Mall, Cantt Area",
        "city": "Kanpur",
        "latitude": 26.4520,
        "longitude": 80.3680,
        "facilities": ["24x7 Emergency", "Ambulance Fleet", "Cardiology", "Pathology"],
    },
    {
        "name": "Noble Multi-Speciality Clinic & Hospital",
        "slug": "noble-multi-speciality",
        "phone": "+91 98391 10010",
        "emergency_phone": "+91 98391 10999",
        "address": "Fazalganj Industrial Area Road",
        "city": "Kanpur",
        "latitude": 26.4610,
        "longitude": 80.3090,
        "facilities": ["24x7 Emergency", "Pharmacy", "OPD Suites"],
    },
    {
        "name": "Prime Life Health & Trauma",
        "slug": "prime-life-health",
        "phone": "+91 98391 20020",
        "emergency_phone": "+91 98391 20999",
        "address": "Panki Kalyanpur Road",
        "city": "Kanpur",
        "latitude": 26.4950,
        "longitude": 80.2310,
        "facilities": ["24x7 Emergency", "Critical Care", "Ambulance"],
    },
    {
        "name": "Unity Emergency & Maternity Center",
        "slug": "unity-emergency-maternity",
        "phone": "+91 98391 30030",
        "emergency_phone": "+91 98391 30999",
        "address": "Barra Bypass, Sector 4",
        "city": "Kanpur",
        "latitude": 26.4250,
        "longitude": 80.2850,
        "facilities": ["24x7 Emergency", "Maternity ICU", "Blood Storage"],
    },
]

SPECIALTIES = [
    ("Cardiology", "MD, DM (Cardio)"),
    ("Orthopedics", "MS (Ortho), Fellowship"),
    ("Neurology", "MD, DM (Neuro)"),
    ("Emergency Medicine", "MD (Emergency), MEM"),
    ("General Surgery", "MS (Gen Surg), FIAGES"),
    ("Pediatrics", "MD (Pediatrics)"),
    ("Pulmonology", "MD (Chest & Respiratory)"),
]

DOCTOR_NAMES = [
    "Dr. Rajesh Sharma", "Dr. Anita Verma", "Dr. Vikram Singh", 
    "Dr. Priyanka Gupta", "Dr. Alok Mishra", "Dr. Farhan Khan",
    "Dr. Sunita Kapoor", "Dr. Rahul Agrawal", "Dr. Neha Pandey"
]

SLOT_TIMES = ["10:00", "11:30", "14:00", "15:30", "17:00", "18:30"]


def seed_database():
    """Drops (or creates) and seeds dummy hospitals, beds, doctors, and demo users."""
    print("Initializing MediBud database schema...")
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # Check if already seeded
        if db.query(Hospital).count() > 0:
            print("Database already contains hospitals. Skipping duplicate seed.")
            return

        print("Creating demo user accounts...")
        # Demo Patient
        patient_user = User(
            email="patient@medibud.com",
            phone="+919876543210",
            hashed_password=hash_password("password123"),
            full_name="Aman Gupta (Patient Demo)",
            role=UserRole.PATIENT,
            is_active=True,
            is_verified=True,
        )
        db.add(patient_user)

        # Demo Hospital Admin
        staff_user = User(
            email="admin@lifeline.com",
            phone="+919876543211",
            hashed_password=hash_password("admin123"),
            full_name="Dr. S. K. Verma (Chief Admin)",
            role=UserRole.HOSPITAL_ADMIN,
            is_active=True,
            is_verified=True,
        )
        db.add(staff_user)

        # Demo Super Admin
        super_admin = User(
            email="superadmin@medibud.com",
            phone="+919876543212",
            hashed_password=hash_password("superadmin123"),
            full_name="MediBud System Administrator",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
        )
        db.add(super_admin)
        db.commit()

        print(f"Seeding {len(HOSPITAL_DATA)} hospitals across the city...")
        for i, h_info in enumerate(HOSPITAL_DATA):
            # Give random update times (some fresh, 1 or 2 stale for demoing the freshness indicator)
            minutes_ago = random.choice([2, 5, 12, 25, 45, 140 if i == 4 else 8])
            last_updated = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)

            hospital = Hospital(
                name=h_info["name"],
                slug=h_info["slug"],
                phone=h_info["phone"],
                emergency_phone=h_info["emergency_phone"],
                address=h_info["address"],
                city=h_info["city"],
                latitude=h_info["latitude"],
                longitude=h_info["longitude"],
                facilities=h_info["facilities"],
                is_verified=True,
                is_demo=True,
                is_active=True,
                last_updated_at=last_updated,
            )
            db.add(hospital)
            db.flush()

            # Link staff user to the first hospital
            if i == 0:
                staff_rel = HospitalStaff(
                    hospital_id=hospital.id,
                    user_id=staff_user.id,
                    role_title="Senior Hospital Administrator",
                )
                db.add(staff_rel)

            # Seed Beds (General, ICU, Ventilator, Oxygen)
            bed_configs = [
                (BedType.GENERAL, random.randint(15, 35)),
                (BedType.ICU, random.randint(4, 12)),
                (BedType.VENTILATOR, random.randint(2, 6)),
                (BedType.OXYGEN, random.randint(8, 20)),
            ]
            for btype, total in bed_configs:
                # Ensure at least some beds free
                occupied = random.randint(0, total - 1)
                held = 1 if (random.random() > 0.7 and (total - occupied) > 1) else 0
                bed = HospitalBed(
                    hospital_id=hospital.id,
                    bed_type=btype,
                    total_beds=total,
                    occupied_beds=occupied,
                    held_beds=held,
                    updated_at=last_updated,
                )
                db.add(bed)

            # Seed 2-4 Doctors per hospital
            doc_count = random.randint(2, 4)
            for d_idx in range(doc_count):
                spec_name, qual = SPECIALTIES[(i + d_idx) % len(SPECIALTIES)]
                doc_name = DOCTOR_NAMES[(i * 2 + d_idx) % len(DOCTOR_NAMES)]
                status = random.choice([
                    DoctorStatus.AVAILABLE,
                    DoctorStatus.AVAILABLE,
                    DoctorStatus.IN_SURGERY,
                    DoctorStatus.OFF_DUTY,
                ])
                doc = Doctor(
                    hospital_id=hospital.id,
                    name=doc_name,
                    specialty=spec_name,
                    qualification=qual,
                    experience_years=random.randint(4, 22),
                    status=status,
                    status_updated_at=last_updated,
                )
                db.add(doc)
                db.flush()

                # Generate bookable slots for today
                for slot_t in random.sample(SLOT_TIMES, 4):
                    slot = DoctorSlot(
                        doctor_id=doc.id,
                        slot_time=slot_t,
                        is_booked=(random.random() > 0.8),
                    )
                    db.add(slot)

        db.commit()
        print("[MediBud Seed] Database seeding successfully completed.")

    except Exception as e:
        db.rollback()
        print(f"[MediBud Seed] Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
