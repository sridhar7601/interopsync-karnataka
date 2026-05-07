"""Database models for SWS-Department interoperability middleware."""

from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, DateTime, Enum, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid

from app.database import Base


def gen_id():
    return str(uuid.uuid4())


class SyncDirection(str, enum.Enum):
    SWS_TO_DEPT = "sws_to_dept"
    DEPT_TO_SWS = "dept_to_sws"


class SyncStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class ConflictResolution(str, enum.Enum):
    UNRESOLVED = "unresolved"
    SWS_WINS = "sws_wins"
    DEPT_WINS = "dept_wins"
    MANUAL = "manual"
    MERGED = "merged"


class SWSApplication(Base):
    """Application record in the Single Window System."""
    __tablename__ = "sws_applications"

    id = Column(String, primary_key=True, default=gen_id)
    sws_reference_no = Column(String, unique=True)
    ubid = Column(String, nullable=False, index=True)  # Links to Theme 1

    # Business details
    business_name = Column(String, nullable=False)
    owner_name = Column(String)
    registered_address = Column(Text)
    pincode = Column(String)
    business_type = Column(String)
    sector = Column(String)

    # Application details
    service_type = Column(String)  # new_registration, address_change, renewal, closure
    application_status = Column(String, default="submitted")  # submitted, approved, rejected, pending_dept
    pan = Column(String)
    gstin = Column(String)

    # Timestamps
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_synced_at = Column(DateTime)

    # Metadata
    data = Column(JSON)  # Full application payload

    sync_events = relationship("SyncEvent", back_populates="sws_application")


class DepartmentRecord(Base):
    """Record in a department system (Labour, KSPCB, Commercial Tax, etc.)."""
    __tablename__ = "department_records"

    id = Column(String, primary_key=True, default=gen_id)
    department_name = Column(String, nullable=False)  # labour, kspcb, commercial_tax, factories, fire_safety
    dept_record_id = Column(String)  # Department's own record identifier
    ubid = Column(String, nullable=False, index=True)

    # Business details (department's schema — may differ from SWS)
    establishment_name = Column(String)  # Different field name than SWS
    proprietor_name = Column(String)
    premises_address = Column(Text)
    pin_code = Column(String)
    entity_type = Column(String)
    registration_number = Column(String)
    registration_status = Column(String)

    # Timestamps
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_synced_at = Column(DateTime)

    # Metadata
    data = Column(JSON)  # Full department record payload
    schema_version = Column(String, default="1.0")

    sync_events = relationship("SyncEvent", back_populates="department_record")


class SyncEvent(Base):
    """Audit trail for every propagation between SWS and departments."""
    __tablename__ = "sync_events"

    id = Column(String, primary_key=True, default=gen_id)
    direction = Column(Enum(SyncDirection), nullable=False)
    status = Column(Enum(SyncStatus), default=SyncStatus.PENDING)

    # Source and target
    sws_application_id = Column(String, ForeignKey("sws_applications.id"), nullable=True)
    department_record_id = Column(String, ForeignKey("department_records.id"), nullable=True)
    department_name = Column(String)
    ubid = Column(String, nullable=False)

    # What changed
    event_type = Column(String, nullable=False)  # address_change, status_update, new_registration, signatory_change
    payload = Column(JSON)  # The actual data being synced
    payload_hash = Column(String)  # For idempotency

    # Translation
    source_schema = Column(JSON)  # Original field names/values
    translated_schema = Column(JSON)  # Translated field names/values

    # Conflict
    conflict_id = Column(String, ForeignKey("conflict_records.id"), nullable=True)
    has_conflict = Column(Boolean, default=False)

    # Retry tracking
    attempt_count = Column(Integer, default=0)
    error_message = Column(Text)

    # Timestamps
    initiated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)

    sws_application = relationship("SWSApplication", back_populates="sync_events")
    department_record = relationship("DepartmentRecord", back_populates="sync_events")
    conflict = relationship("ConflictRecord", back_populates="sync_events")


class SchemaMapping(Base):
    """Schema translation rules between SWS and department systems."""
    __tablename__ = "schema_mappings"

    id = Column(String, primary_key=True, default=gen_id)
    department_name = Column(String, nullable=False)

    sws_field = Column(String, nullable=False)  # SWS field name
    dept_field = Column(String, nullable=False)  # Department field name
    transform_rule = Column(String)  # none, uppercase, date_format, split, concat
    transform_config = Column(JSON)  # Parameters for the transform

    # Examples
    sws_example = Column(String)
    dept_example = Column(String)


class ConflictRecord(Base):
    """Conflicting updates detected during sync."""
    __tablename__ = "conflict_records"

    id = Column(String, primary_key=True, default=gen_id)
    ubid = Column(String, nullable=False)

    # The conflicting values
    field_name = Column(String, nullable=False)
    sws_value = Column(Text)
    dept_value = Column(Text)
    department_name = Column(String)

    # Resolution
    resolution = Column(Enum(ConflictResolution), default=ConflictResolution.UNRESOLVED)
    resolved_value = Column(Text)
    resolver_notes = Column(Text)
    severity = Column(String, default="warning")  # critical, warning, info

    # Timestamps
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime)

    sync_events = relationship("SyncEvent", back_populates="conflict")
