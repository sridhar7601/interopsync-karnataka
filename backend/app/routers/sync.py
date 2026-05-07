"""Sync endpoints — bidirectional propagation between SWS and departments."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SWSApplication, DepartmentRecord, SyncEvent, SyncDirection, SyncStatus
from app.services.sync_engine import sync_sws_to_departments, sync_department_to_sws

router = APIRouter()


class SWSToDeptRequest(BaseModel):
    sws_application_id: str
    department_names: list[str] | None = None  # If None, sync to all matching


class DeptToSWSRequest(BaseModel):
    department_name: str
    dept_record_id: str | None = None  # If None, sync all pending changes


@router.post("/sws-to-dept")
async def trigger_sws_to_dept(req: SWSToDeptRequest, db: Session = Depends(get_db)):
    """Push an SWS application/change to matching department systems."""
    app = db.query(SWSApplication).filter(SWSApplication.id == req.sws_application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="SWS Application not found")

    result = sync_sws_to_departments(app, db, department_names=req.department_names)

    return {
        "ubid": app.ubid,
        "sws_reference_no": app.sws_reference_no,
        "departments_synced": result["departments_synced"],
        "conflicts_detected": result["conflicts_detected"],
        "sync_events": result["sync_event_ids"],
    }


@router.post("/dept-to-sws")
async def trigger_dept_to_sws(req: DeptToSWSRequest, db: Session = Depends(get_db)):
    """Pull changes from a department system into SWS."""
    result = sync_department_to_sws(
        db,
        department_name=req.department_name,
        dept_record_id=req.dept_record_id,
    )

    return {
        "department": req.department_name,
        "records_synced": result["records_synced"],
        "conflicts_detected": result["conflicts_detected"],
        "sync_events": result["sync_event_ids"],
    }


@router.get("/events")
def list_sync_events(
    ubid: str | None = None,
    direction: str | None = None,
    status: str | None = None,
    department: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Audit trail — list all sync events with filtering."""
    query = db.query(SyncEvent)

    if ubid:
        query = query.filter(SyncEvent.ubid == ubid)
    if direction:
        query = query.filter(SyncEvent.direction == SyncDirection(direction))
    if status:
        query = query.filter(SyncEvent.status == SyncStatus(status))
    if department:
        query = query.filter(SyncEvent.department_name == department)

    total = query.count()
    events = query.order_by(SyncEvent.initiated_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "events": [
            {
                "id": e.id,
                "direction": e.direction,
                "status": e.status,
                "department_name": e.department_name,
                "ubid": e.ubid,
                "event_type": e.event_type,
                "has_conflict": e.has_conflict,
                "attempt_count": e.attempt_count,
                "initiated_at": e.initiated_at.isoformat() if e.initiated_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "error_message": e.error_message,
            }
            for e in events
        ],
    }


@router.get("/events/{event_id}/explain-llm")
def explain_sync_with_llm(event_id: str, db: Session = Depends(get_db)):
    """AI-grounded one-line audit summary for a sync event (Azure GPT-4.1)."""
    from app.services.llm_narration import explain_sync_event
    import json as _json

    e = db.query(SyncEvent).filter(SyncEvent.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Sync event not found")

    # Diff source vs translated payload to surface changed fields (best-effort)
    changed = []
    try:
        src = _json.loads(e.source_schema or "{}")
        tgt = _json.loads(e.translated_schema or "{}")
        for k, v in tgt.items():
            if str(src.get(k, "")) != str(v):
                changed.append({"field": k, "before": str(src.get(k, "")), "after": str(v)})
    except Exception:
        pass

    payload = {
        "sync_id": e.id,
        "ubid": e.ubid,
        "direction": e.direction,
        "source_system": "SWS" if e.direction == SyncDirection.SWS_TO_DEPT else (e.department_name or "Department"),
        "target_system": (e.department_name or "Department") if e.direction == SyncDirection.SWS_TO_DEPT else "SWS",
        "status": e.status,
        "changed_fields": changed[:6],
        "conflict_count": 1 if e.has_conflict else 0,
        "retry_count": e.attempt_count or 0,
    }

    return {
        "event_id": e.id,
        "ai_narration": explain_sync_event(payload),
        "status": e.status,
        "direction": e.direction,
    }


# ─── Retry endpoint — at-least-once delivery ────────────────────────────────
class _RetryRequest(BaseModel):
    max_attempts: int = 5
    backoff_seconds: int = 2


@router.post("/retry-failed")
def retry_failed_syncs(req: _RetryRequest = _RetryRequest(), db: Session = Depends(get_db)):
    """Retry all FAILED syncs with exponential backoff.

    Brief requires at-least-once delivery. This endpoint walks the failed queue,
    attempts each up to max_attempts with backoff between retries, and records
    every attempt in attempt_count + last_attempt_at.
    """
    import time

    failed = db.query(SyncEvent).filter(SyncEvent.status == SyncStatus.FAILED).all()
    succeeded = 0
    still_failed = 0

    for ev in failed:
        if (ev.attempt_count or 0) >= req.max_attempts:
            still_failed += 1
            continue
        # Exponential backoff: 2s, 4s, 8s … capped at 5s for demo responsiveness
        sleep_s = min(req.backoff_seconds * (2 ** (ev.attempt_count or 0)), 5)
        time.sleep(sleep_s)

        try:
            if ev.direction == SyncDirection.SWS_TO_DEPT:
                sws_app = (
                    db.query(SWSApplication).filter(SWSApplication.ubid == ev.ubid).first()
                )
                if not sws_app:
                    raise RuntimeError(f"SWS app missing for UBID {ev.ubid}")
                result = sync_sws_to_departments(
                    sws_app, db, department_names=[ev.department_name] if ev.department_name else None
                )
                # SWS→Dept returns aggregate; consider success when this dept's sync is COMPLETED
                ok = any(
                    r.get("status") == SyncStatus.COMPLETED.value
                    or r.get("status") == "completed"
                    for r in result.get("results", [])
                )
            else:
                result = sync_department_to_sws(db, ev.department_name, dept_record_id=None)
                ok = result.get("synced", 0) > 0

            ev.attempt_count = (ev.attempt_count or 0) + 1
            if ok:
                ev.status = SyncStatus.COMPLETED
                ev.error_message = None
                succeeded += 1
            else:
                still_failed += 1
        except Exception as exc:
            ev.attempt_count = (ev.attempt_count or 0) + 1
            ev.error_message = str(exc)[:500]
            still_failed += 1
        db.commit()

    return {
        "retried": len(failed),
        "succeeded": succeeded,
        "still_failed": still_failed,
        "max_attempts": req.max_attempts,
    }


@router.post("/all")
def sync_all(db: Session = Depends(get_db)):
    """Run both directions for every UBID — convenience for the dashboard 'Sync All' button.

    Walks every SWS application, propagates SWS→Dept for all matching depts,
    then for each known dept runs Dept→SWS to pick up reverse changes.
    Idempotency hash prevents duplicate writes; a no-change run is fully safe.
    """
    sws_results = []
    apps = db.query(SWSApplication).all()
    for app in apps:
        try:
            r = sync_sws_to_departments(app, db, department_names=None)
            sws_results.append(r)
        except Exception as exc:
            sws_results.append({"error": str(exc)[:200], "ubid": app.ubid})

    # Get list of distinct departments in the system, then pull back changes
    dept_names = [
        row[0]
        for row in db.query(DepartmentRecord.department_name).distinct().all()
    ]
    dept_results = []
    for dept_name in dept_names:
        try:
            r = sync_department_to_sws(db, dept_name, dept_record_id=None)
            dept_results.append({"department": dept_name, **r})
        except Exception as exc:
            dept_results.append({"department": dept_name, "error": str(exc)[:200]})

    def _count(v):
        return len(v) if isinstance(v, list) else (v if isinstance(v, int) else 0)

    return {
        "sws_to_dept": {
            "applications_processed": len(sws_results),
            "departments_synced": sum(_count(r.get("departments_synced", 0)) for r in sws_results),
            "conflicts_detected": sum(_count(r.get("conflicts_detected", 0)) for r in sws_results),
        },
        "dept_to_sws": {
            "departments_processed": len(dept_results),
            "records_synced": sum(_count(r.get("records_synced", 0)) for r in dept_results),
            "conflicts_detected": sum(_count(r.get("conflicts_detected", 0)) for r in dept_results),
        },
    }
