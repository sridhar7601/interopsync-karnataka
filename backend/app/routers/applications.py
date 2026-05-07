"""SWS Application management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SWSApplication, DepartmentRecord

router = APIRouter()


class CreateApplicationRequest(BaseModel):
    ubid: str
    business_name: str
    owner_name: str = ""
    registered_address: str = ""
    pincode: str = ""
    business_type: str = ""
    sector: str = ""
    service_type: str = "new_registration"
    pan: str = ""
    gstin: str = ""


@router.post("/")
def create_application(req: CreateApplicationRequest, db: Session = Depends(get_db)):
    """Create a new SWS application."""
    import uuid

    app = SWSApplication(
        sws_reference_no=f"SWS-{uuid.uuid4().hex[:8].upper()}",
        ubid=req.ubid,
        business_name=req.business_name,
        owner_name=req.owner_name,
        registered_address=req.registered_address,
        pincode=req.pincode,
        business_type=req.business_type,
        sector=req.sector,
        service_type=req.service_type,
        pan=req.pan,
        gstin=req.gstin,
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    return {
        "id": app.id,
        "sws_reference_no": app.sws_reference_no,
        "ubid": app.ubid,
        "business_name": app.business_name,
        "application_status": app.application_status,
    }


@router.get("/")
def list_applications(
    ubid: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List SWS applications with optional UBID filter."""
    query = db.query(SWSApplication)
    if ubid:
        query = query.filter(SWSApplication.ubid == ubid)

    total = query.count()
    apps = query.order_by(SWSApplication.submitted_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "applications": [
            {
                "id": a.id,
                "sws_reference_no": a.sws_reference_no,
                "ubid": a.ubid,
                "business_name": a.business_name,
                "service_type": a.service_type,
                "application_status": a.application_status,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
            }
            for a in apps
        ],
    }


@router.get("/{app_id}")
def get_application(app_id: str, db: Session = Depends(get_db)):
    """Get an SWS application with its department sync status."""
    app = db.query(SWSApplication).filter(SWSApplication.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Find matching department records by UBID
    dept_records = db.query(DepartmentRecord).filter(
        DepartmentRecord.ubid == app.ubid
    ).all()

    return {
        "id": app.id,
        "sws_reference_no": app.sws_reference_no,
        "ubid": app.ubid,
        "business_name": app.business_name,
        "owner_name": app.owner_name,
        "registered_address": app.registered_address,
        "pincode": app.pincode,
        "service_type": app.service_type,
        "application_status": app.application_status,
        "pan": app.pan,
        "gstin": app.gstin,
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "department_records": [
            {
                "id": d.id,
                "department_name": d.department_name,
                "dept_record_id": d.dept_record_id,
                "establishment_name": d.establishment_name,
                "registration_status": d.registration_status,
                "last_synced_at": d.last_synced_at.isoformat() if d.last_synced_at else None,
            }
            for d in dept_records
        ],
        "sync_events_count": len(app.sync_events),
    }
