"""Schema translation between SWS and department systems.

Each department has its own field names, date formats, and value conventions.
This module handles the translation in both directions.
"""

import logging

logger = logging.getLogger(__name__)

# Field mapping: SWS field → department field (per department)
SWS_TO_DEPT_MAPPINGS = {
    "labour": {
        "business_name": "establishment_name",
        "owner_name": "proprietor_name",
        "registered_address": "premises_address",
        "pincode": "pin_code",
        "business_type": "entity_type",
        "application_status": "registration_status",
    },
    "kspcb": {
        "business_name": "unit_name",
        "owner_name": "contact_person",
        "registered_address": "plant_address",
        "pincode": "pin_code",
        "sector": "industry_category",
        "application_status": "consent_status",
    },
    "commercial_tax": {
        "business_name": "dealer_name",
        "owner_name": "authorized_signatory",
        "registered_address": "business_address",
        "pincode": "pin_code",
        "pan": "pan_number",
        "gstin": "gstin",
        "application_status": "registration_status",
    },
    "factories": {
        "business_name": "factory_name",
        "owner_name": "occupier_name",
        "registered_address": "factory_address",
        "pincode": "pin_code",
        "sector": "manufacturing_process",
        "application_status": "license_status",
    },
    "fire_safety": {
        "business_name": "building_name",
        "owner_name": "owner_occupant",
        "registered_address": "building_address",
        "pincode": "pin_code",
        "application_status": "noc_status",
    },
}

# Reverse mapping (computed from SWS_TO_DEPT_MAPPINGS)
DEPT_TO_SWS_MAPPINGS = {}
for dept, mapping in SWS_TO_DEPT_MAPPINGS.items():
    DEPT_TO_SWS_MAPPINGS[dept] = {v: k for k, v in mapping.items()}

# Value transformations per department
STATUS_TRANSLATIONS = {
    "labour": {
        "submitted": "Application Received",
        "approved": "Registered",
        "rejected": "Registration Denied",
        "pending_dept": "Under Review",
    },
    "kspcb": {
        "submitted": "CTE Application Filed",
        "approved": "CTO Granted",
        "rejected": "Consent Refused",
        "pending_dept": "Under Inspection",
    },
    "commercial_tax": {
        "submitted": "Application Received",
        "approved": "Active",
        "rejected": "Cancelled",
        "pending_dept": "Verification Pending",
    },
    "factories": {
        "submitted": "License Application Filed",
        "approved": "License Issued",
        "rejected": "License Denied",
        "pending_dept": "Inspection Pending",
    },
    "fire_safety": {
        "submitted": "NOC Application Filed",
        "approved": "NOC Issued",
        "rejected": "NOC Denied",
        "pending_dept": "Inspection Scheduled",
    },
}


def translate_sws_to_dept(sws_payload: dict, department_name: str) -> dict:
    """Translate SWS fields to department-specific schema."""
    mapping = SWS_TO_DEPT_MAPPINGS.get(department_name, {})
    status_map = STATUS_TRANSLATIONS.get(department_name, {})

    translated = {}
    for sws_field, value in sws_payload.items():
        dept_field = mapping.get(sws_field)
        if dept_field:
            # Apply value transformation for status fields
            if sws_field == "application_status" and value in status_map:
                translated[dept_field] = status_map[value]
            else:
                translated[dept_field] = _transform_value(value, sws_field, department_name)
        # Keep unmapped fields with a prefix
        else:
            translated[f"sws_{sws_field}"] = value

    return translated


def translate_dept_to_sws(dept_payload: dict, department_name: str) -> dict:
    """Translate department fields to SWS schema."""
    mapping = DEPT_TO_SWS_MAPPINGS.get(department_name, {})
    status_map = STATUS_TRANSLATIONS.get(department_name, {})
    reverse_status = {v: k for k, v in status_map.items()}

    translated = {}
    for dept_field, value in dept_payload.items():
        sws_field = mapping.get(dept_field)
        if sws_field:
            # Reverse status translation
            if sws_field == "application_status" and value in reverse_status:
                translated[sws_field] = reverse_status[value]
            else:
                translated[sws_field] = value
        else:
            translated[f"dept_{dept_field}"] = value

    return translated


def _transform_value(value: str, field: str, department: str) -> str:
    """Apply department-specific value transformations."""
    if not value:
        return value

    # Some departments want uppercase
    if department in ("kspcb", "factories") and field in ("business_name", "owner_name"):
        return value.upper()

    return value
