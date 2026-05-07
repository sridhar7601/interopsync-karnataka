"""Dashboard rollup + AI briefing for the Interop Layer."""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    ConflictRecord,
    ConflictResolution,
    SyncDirection,
    SyncEvent,
    SyncStatus,
    SWSApplication,
    DepartmentRecord,
)
from app.services.llm_narration import generate_dashboard_briefing

router = APIRouter()


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    """KPI snapshot + AI briefing for the home page."""

    total_apps = db.query(SWSApplication).count()
    total_dept_records = db.query(DepartmentRecord).count()

    total_syncs = db.query(SyncEvent).count()
    completed = db.query(SyncEvent).filter(SyncEvent.status == SyncStatus.COMPLETED).count()
    failed = db.query(SyncEvent).filter(SyncEvent.status == SyncStatus.FAILED).count()
    pending = db.query(SyncEvent).filter(SyncEvent.status == SyncStatus.PENDING).count()
    conflict_status_count = (
        db.query(SyncEvent).filter(SyncEvent.status == SyncStatus.CONFLICT).count()
    )

    sws_to_dept = (
        db.query(SyncEvent).filter(SyncEvent.direction == SyncDirection.SWS_TO_DEPT).count()
    )
    dept_to_sws = (
        db.query(SyncEvent).filter(SyncEvent.direction == SyncDirection.DEPT_TO_SWS).count()
    )

    by_department = dict(
        db.query(SyncEvent.department_name, func.count(SyncEvent.id))
        .filter(SyncEvent.direction == SyncDirection.SWS_TO_DEPT)
        .group_by(SyncEvent.department_name)
        .all()
    )

    total_conflicts = db.query(ConflictRecord).count()
    unresolved = (
        db.query(ConflictRecord)
        .filter(ConflictRecord.resolution == ConflictResolution.UNRESOLVED)
        .count()
    )
    critical = (
        db.query(ConflictRecord)
        .filter(
            ConflictRecord.severity == "critical",
            ConflictRecord.resolution == ConflictResolution.UNRESOLVED,
        )
        .count()
    )

    success_rate = round((completed / total_syncs) * 100, 1) if total_syncs else 0.0

    stats = {
        "total_applications": total_apps,
        "total_department_records": total_dept_records,
        "total_syncs": total_syncs,
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "conflict_count": conflict_status_count,
        "success_rate_pct": success_rate,
        "sws_to_dept": sws_to_dept,
        "dept_to_sws": dept_to_sws,
        "by_department": by_department,
        "unresolved_conflicts": unresolved,
        "critical_conflicts": critical,
        "pending_review": unresolved,
    }

    briefing = generate_dashboard_briefing(stats)

    return {
        **stats,
        "briefing": briefing,
    }
