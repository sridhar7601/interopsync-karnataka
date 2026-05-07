"""Bidirectional sync engine — propagates changes between SWS and departments.

Key principles:
- Every propagation is idempotent (payload_hash prevents duplicates)
- Every propagation is fully auditable (SyncEvent for each operation)
- Conflicts are detected and queued for resolution, never silently overwritten
"""

import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    SWSApplication, DepartmentRecord, SyncEvent,
    SyncDirection, SyncStatus, ConflictRecord, ConflictResolution,
)
from app.services.schema_translator import translate_sws_to_dept, translate_dept_to_sws
from app.services.conflict_detector import detect_conflicts

logger = logging.getLogger(__name__)

# Departments that the middleware integrates with
SUPPORTED_DEPARTMENTS = ["labour", "kspcb", "commercial_tax", "factories", "fire_safety"]


def sync_sws_to_departments(
    sws_app: SWSApplication,
    db: Session,
    department_names: list[str] | None = None,
) -> dict:
    """Direction 1: Push an SWS change to matching department systems.

    For each target department:
    1. Translate SWS schema → department schema
    2. Check for conflicts with existing department data
    3. Create SyncEvent with full audit trail
    """
    targets = department_names or SUPPORTED_DEPARTMENTS
    sync_event_ids = []
    conflicts_detected = 0
    departments_synced = []

    for dept_name in targets:
        # Find existing department record for this UBID
        dept_record = db.query(DepartmentRecord).filter(
            DepartmentRecord.ubid == sws_app.ubid,
            DepartmentRecord.department_name == dept_name,
        ).first()

        # Translate SWS schema to department schema
        sws_payload = _extract_sws_payload(sws_app)
        translated = translate_sws_to_dept(sws_payload, dept_name)

        # Compute payload hash for idempotency
        payload_hash = _compute_hash(translated)

        # Check if this exact change was already synced
        existing = db.query(SyncEvent).filter(
            SyncEvent.payload_hash == payload_hash,
            SyncEvent.department_name == dept_name,
            SyncEvent.status == SyncStatus.COMPLETED,
        ).first()

        if existing:
            logger.info(f"Idempotent skip: SWS→{dept_name} for UBID {sws_app.ubid}")
            continue

        # Detect conflicts
        conflict_records = []
        if dept_record:
            conflict_records = detect_conflicts(
                sws_payload, _extract_dept_payload(dept_record), dept_name, sws_app.ubid
            )
            conflicts_detected += len(conflict_records)

        # Create sync event
        sync_event = SyncEvent(
            direction=SyncDirection.SWS_TO_DEPT,
            sws_application_id=sws_app.id,
            department_record_id=dept_record.id if dept_record else None,
            department_name=dept_name,
            ubid=sws_app.ubid,
            event_type=sws_app.service_type or "update",
            payload=translated,
            payload_hash=payload_hash,
            source_schema=sws_payload,
            translated_schema=translated,
            has_conflict=len(conflict_records) > 0,
            attempt_count=1,
        )

        if conflict_records:
            sync_event.status = SyncStatus.CONFLICT
            for cr in conflict_records:
                conflict = ConflictRecord(
                    ubid=sws_app.ubid,
                    field_name=cr["field"],
                    sws_value=cr["sws_value"],
                    dept_value=cr["dept_value"],
                    department_name=dept_name,
                    severity=cr["severity"],
                )
                db.add(conflict)
        else:
            sync_event.status = SyncStatus.COMPLETED
            sync_event.completed_at = datetime.now(timezone.utc)

            # Apply changes to department record (simulated write)
            if dept_record:
                _apply_to_dept_record(dept_record, translated)
                dept_record.last_synced_at = datetime.now(timezone.utc)
            else:
                # Create new department record
                dept_record = DepartmentRecord(
                    department_name=dept_name,
                    ubid=sws_app.ubid,
                    establishment_name=translated.get("establishment_name", sws_app.business_name),
                    proprietor_name=translated.get("proprietor_name", sws_app.owner_name),
                    premises_address=translated.get("premises_address", sws_app.registered_address),
                    pin_code=translated.get("pin_code", sws_app.pincode),
                    registration_status="Pending",
                    last_synced_at=datetime.now(timezone.utc),
                    data=translated,
                )
                db.add(dept_record)

            departments_synced.append(dept_name)

        db.add(sync_event)
        db.flush()
        sync_event_ids.append(sync_event.id)

    # Update SWS last synced timestamp
    sws_app.last_synced_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "departments_synced": departments_synced,
        "conflicts_detected": conflicts_detected,
        "sync_event_ids": sync_event_ids,
    }


def sync_department_to_sws(
    db: Session,
    department_name: str,
    dept_record_id: str | None = None,
) -> dict:
    """Direction 2: Pull changes from a department system into SWS.

    For departments that don't emit events, this simulates polling/snapshot comparison.
    """
    query = db.query(DepartmentRecord).filter(
        DepartmentRecord.department_name == department_name
    )
    if dept_record_id:
        query = query.filter(DepartmentRecord.dept_record_id == dept_record_id)

    dept_records = query.all()
    sync_event_ids = []
    records_synced = 0
    conflicts_detected = 0

    for dept_record in dept_records:
        # Find matching SWS application by UBID
        sws_app = db.query(SWSApplication).filter(
            SWSApplication.ubid == dept_record.ubid
        ).first()

        if not sws_app:
            logger.info(f"No SWS application for UBID {dept_record.ubid} — skipping")
            continue

        # Translate department schema to SWS schema
        dept_payload = _extract_dept_payload(dept_record)
        translated = translate_dept_to_sws(dept_payload, department_name)

        payload_hash = _compute_hash(translated)

        # Idempotency check
        existing = db.query(SyncEvent).filter(
            SyncEvent.payload_hash == payload_hash,
            SyncEvent.direction == SyncDirection.DEPT_TO_SWS,
            SyncEvent.status == SyncStatus.COMPLETED,
        ).first()

        if existing:
            continue

        # Detect conflicts
        sws_payload = _extract_sws_payload(sws_app)
        conflict_records = detect_conflicts(
            sws_payload, dept_payload, department_name, dept_record.ubid
        )
        conflicts_detected += len(conflict_records)

        sync_event = SyncEvent(
            direction=SyncDirection.DEPT_TO_SWS,
            sws_application_id=sws_app.id,
            department_record_id=dept_record.id,
            department_name=department_name,
            ubid=dept_record.ubid,
            event_type="dept_update",
            payload=translated,
            payload_hash=payload_hash,
            source_schema=dept_payload,
            translated_schema=translated,
            has_conflict=len(conflict_records) > 0,
            attempt_count=1,
        )

        if conflict_records:
            sync_event.status = SyncStatus.CONFLICT
            for cr in conflict_records:
                conflict = ConflictRecord(
                    ubid=dept_record.ubid,
                    field_name=cr["field"],
                    sws_value=cr["sws_value"],
                    dept_value=cr["dept_value"],
                    department_name=department_name,
                    severity=cr["severity"],
                )
                db.add(conflict)
        else:
            sync_event.status = SyncStatus.COMPLETED
            sync_event.completed_at = datetime.now(timezone.utc)
            _apply_to_sws(sws_app, translated)
            sws_app.last_synced_at = datetime.now(timezone.utc)
            records_synced += 1

        db.add(sync_event)
        db.flush()
        sync_event_ids.append(sync_event.id)

    db.commit()

    return {
        "records_synced": records_synced,
        "conflicts_detected": conflicts_detected,
        "sync_event_ids": sync_event_ids,
    }


def _extract_sws_payload(app: SWSApplication) -> dict:
    """Extract a normalized payload from an SWS application."""
    return {
        "business_name": app.business_name or "",
        "owner_name": app.owner_name or "",
        "registered_address": app.registered_address or "",
        "pincode": app.pincode or "",
        "business_type": app.business_type or "",
        "sector": app.sector or "",
        "pan": app.pan or "",
        "gstin": app.gstin or "",
        "application_status": app.application_status or "",
    }


def _extract_dept_payload(record: DepartmentRecord) -> dict:
    """Extract a normalized payload from a department record."""
    return {
        "establishment_name": record.establishment_name or "",
        "proprietor_name": record.proprietor_name or "",
        "premises_address": record.premises_address or "",
        "pin_code": record.pin_code or "",
        "entity_type": record.entity_type or "",
        "registration_number": record.registration_number or "",
        "registration_status": record.registration_status or "",
    }


def _compute_hash(payload: dict) -> str:
    """Compute a deterministic hash for idempotency."""
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _apply_to_dept_record(record: DepartmentRecord, translated: dict):
    """Apply translated SWS values to a department record."""
    if translated.get("establishment_name"):
        record.establishment_name = translated["establishment_name"]
    if translated.get("premises_address"):
        record.premises_address = translated["premises_address"]
    if translated.get("pin_code"):
        record.pin_code = translated["pin_code"]
    if translated.get("proprietor_name"):
        record.proprietor_name = translated["proprietor_name"]
    record.data = {**(record.data or {}), **translated}


def _apply_to_sws(app: SWSApplication, translated: dict):
    """Apply translated department values to an SWS application."""
    if translated.get("business_name"):
        app.business_name = translated["business_name"]
    if translated.get("owner_name"):
        app.owner_name = translated["owner_name"]
    if translated.get("registered_address"):
        app.registered_address = translated["registered_address"]
    if translated.get("pincode"):
        app.pincode = translated["pincode"]
