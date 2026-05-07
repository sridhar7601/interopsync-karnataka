"""Seed demo data for Theme 2: InteropSync.

Creates SWS applications, department records, and deliberate conflicts.
Runs a sync to demonstrate bidirectional propagation and conflict detection.

Usage:
    cd backend
    python ../demo/seed_demo.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.database import init_db, SessionLocal
from app.models import (
    SWSApplication, DepartmentRecord, SyncEvent, ConflictRecord, SchemaMapping,
    SyncDirection, SyncStatus, ConflictResolution,
)
from datetime import datetime, timezone, timedelta
import uuid


def seed():
    init_db()
    db = SessionLocal()

    # Clear existing data
    db.query(SyncEvent).delete()
    db.query(ConflictRecord).delete()
    db.query(SchemaMapping).delete()
    db.query(DepartmentRecord).delete()
    db.query(SWSApplication).delete()
    db.commit()

    now = datetime.now(timezone.utc)

    # ── Create 10 SWS Applications ────────────────────────────────────────
    businesses = [
        ("UBID-KA-ABCDE1234A", "Sharma Enterprises", "Rajesh Sharma", "No. 45, MG Road, Bengaluru - 560001", "560001"),
        ("UBID-KA-FGHIJ5678B", "Kumar Technologies Pvt Ltd", "Suresh Kumar", "No. 12, Koramangala 4th Block, Bengaluru - 560034", "560034"),
        ("UBID-KA-KLMNO9012C", "Reddy Trading Co.", "Mahesh Reddy", "No. 78, Whitefield Main Road, Bengaluru - 560066", "560066"),
        ("UBID-KA-PQRST3456D", "Gowda Manufacturing", "Ramesh Gowda", "No. 23, Peenya Industrial Area, Bengaluru - 560058", "560058"),
        ("UBID-KA-UVWXY7890E", "Patel & Sons Agency", "Ganesh Patel", "No. 90, Jayanagar 9th Block, Bengaluru - 560041", "560041"),
        ("UBID-KA-ABCFG1111F", "Singh Constructions", "Arun Singh", "No. 56, Electronic City Phase 1, Bengaluru - 560100", "560100"),
        ("UBID-KA-HIJKL2222G", "Rao Solutions", "Varun Rao", "No. 34, HSR Layout Sector 2, Bengaluru - 560102", "560102"),
        ("UBID-KA-MNOPQ3333H", "Shetty Industries", "Kiran Shetty", "No. 67, Rajajinagar 1st Block, Bengaluru - 560010", "560010"),
        ("UBID-KA-RSTUV4444I", "Hegde Services", "Mohan Hegde", "No. 11, Malleshwaram 8th Cross, Bengaluru - 560003", "560003"),
        ("UBID-KA-WXYZA5555J", "Murthy Associates", "Vijay Murthy", "No. 89, BTM Layout 1st Stage, Bengaluru - 560029", "560029"),
    ]

    apps = []
    for ubid, name, owner, address, pincode in businesses:
        app = SWSApplication(
            sws_reference_no=f"SWS-{uuid.uuid4().hex[:8].upper()}",
            ubid=ubid,
            business_name=name,
            owner_name=owner,
            registered_address=address,
            pincode=pincode,
            business_type="pvt_ltd",
            sector="services",
            service_type="new_registration",
            application_status="approved",
            pan=f"{''.join([c for c in ubid if c.isalpha()])[:5]}{''.join([c for c in ubid if c.isdigit()])[:4]}A"[:10],
            submitted_at=now - timedelta(days=30),
        )
        db.add(app)
        apps.append(app)
    db.flush()

    # ── Create Department Records (some with conflicts) ───────────────────
    departments = ["labour", "kspcb", "commercial_tax"]

    for i, app in enumerate(apps):
        for dept in departments:
            # Deliberate conflicts for first 3 businesses
            if i < 3 and dept == "labour":
                # Address mismatch
                dept_address = f"No. {100 + i}, DIFFERENT Road, Bengaluru - {app.pincode}"
                dept_name = app.business_name.upper()  # Name variation
            elif i < 3 and dept == "commercial_tax":
                # Status mismatch
                dept_address = app.registered_address
                dept_name = app.business_name
            else:
                dept_address = app.registered_address
                dept_name = app.business_name

            field_map = {
                "labour": "establishment_name",
                "kspcb": "unit_name",
                "commercial_tax": "dealer_name",
            }

            dept_rec = DepartmentRecord(
                department_name=dept,
                dept_record_id=f"{dept.upper()[:3]}-{uuid.uuid4().hex[:6].upper()}",
                ubid=app.ubid,
                establishment_name=dept_name,
                proprietor_name=app.owner_name,
                premises_address=dept_address,
                pin_code=app.pincode,
                entity_type=app.business_type,
                registration_status="Registered" if i >= 3 else ("Pending" if dept == "commercial_tax" and i < 3 else "Registered"),
                last_updated=now - timedelta(days=15),
            )
            db.add(dept_rec)

    db.flush()

    # ── Create some completed sync events (audit trail) ───────────────────
    for i, app in enumerate(apps[3:], start=3):  # Non-conflicting ones
        for dept in departments:
            event = SyncEvent(
                direction=SyncDirection.SWS_TO_DEPT,
                status=SyncStatus.COMPLETED,
                sws_application_id=app.id,
                department_name=dept,
                ubid=app.ubid,
                event_type="new_registration",
                payload={"business_name": app.business_name, "address": app.registered_address},
                payload_hash=uuid.uuid4().hex,
                has_conflict=False,
                attempt_count=1,
                initiated_at=now - timedelta(days=10),
                completed_at=now - timedelta(days=10, hours=-1),
            )
            db.add(event)

    # ── Create conflict records for first 3 businesses ────────────────────
    conflict_scenarios = [
        (apps[0], "labour", "registered_address", apps[0].registered_address, f"No. 100, DIFFERENT Road, Bengaluru - {apps[0].pincode}", "warning"),
        (apps[0], "labour", "business_name", apps[0].business_name, apps[0].business_name.upper(), "info"),
        (apps[1], "labour", "registered_address", apps[1].registered_address, f"No. 101, DIFFERENT Road, Bengaluru - {apps[1].pincode}", "warning"),
        (apps[1], "commercial_tax", "application_status", "approved", "Pending", "critical"),
        (apps[2], "labour", "registered_address", apps[2].registered_address, f"No. 102, DIFFERENT Road, Bengaluru - {apps[2].pincode}", "warning"),
        (apps[2], "commercial_tax", "application_status", "approved", "Pending", "critical"),
    ]

    for app, dept, field, sws_val, dept_val, severity in conflict_scenarios:
        conflict = ConflictRecord(
            ubid=app.ubid,
            field_name=field,
            sws_value=sws_val,
            dept_value=dept_val,
            department_name=dept,
            severity=severity,
            resolution=ConflictResolution.UNRESOLVED,
        )
        db.add(conflict)

        # Create a conflict sync event
        event = SyncEvent(
            direction=SyncDirection.SWS_TO_DEPT,
            status=SyncStatus.CONFLICT,
            sws_application_id=app.id,
            department_name=dept,
            ubid=app.ubid,
            event_type="sync_check",
            payload={"field": field, "sws": sws_val, "dept": dept_val},
            payload_hash=uuid.uuid4().hex,
            has_conflict=True,
            attempt_count=1,
            initiated_at=now - timedelta(days=5),
        )
        db.add(event)

    db.commit()
    db.close()

    print("Demo data seeded successfully!")
    print(f"  Applications: {len(apps)}")
    print(f"  Department records: {len(apps) * len(departments)}")
    print(f"  Completed syncs: {len(apps[3:]) * len(departments)}")
    print(f"  Conflicts: {len(conflict_scenarios)}")
    print(f"\nStart the backend: uvicorn main:app --reload --port 8002")


if __name__ == "__main__":
    seed()
