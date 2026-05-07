"""Conflict detection between SWS and department data.

Compares normalized field values and flags mismatches by severity:
- critical: status/registration mismatch (e.g., SWS says approved, dept says rejected)
- warning: address or name mismatch (could be a legitimate change propagating)
- info: minor formatting differences
"""

import logging
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Fields that map between SWS and departments (for comparison)
COMPARABLE_FIELDS = {
    ("business_name", "establishment_name"): {"severity": "warning", "threshold": 80},
    ("owner_name", "proprietor_name"): {"severity": "warning", "threshold": 80},
    ("registered_address", "premises_address"): {"severity": "warning", "threshold": 70},
    ("pincode", "pin_code"): {"severity": "info", "threshold": 100},
    ("application_status", "registration_status"): {"severity": "critical", "threshold": 100},
}


def detect_conflicts(
    sws_payload: dict,
    dept_payload: dict,
    department_name: str,
    ubid: str,
) -> list[dict]:
    """Compare SWS and department data, return list of detected conflicts.

    Returns list of dicts: {field, sws_value, dept_value, severity}
    """
    conflicts = []

    for (sws_field, dept_field), config in COMPARABLE_FIELDS.items():
        sws_value = (sws_payload.get(sws_field) or "").strip()
        dept_value = (dept_payload.get(dept_field) or "").strip()

        # Skip if either side is empty (not a conflict, just missing data)
        if not sws_value or not dept_value:
            continue

        # Exact match required for critical fields
        if config["threshold"] == 100:
            if _normalize(sws_value) != _normalize(dept_value):
                conflicts.append({
                    "field": sws_field,
                    "sws_value": sws_value,
                    "dept_value": dept_value,
                    "severity": config["severity"],
                })
        else:
            # Fuzzy match for name/address fields
            similarity = fuzz.token_sort_ratio(
                _normalize(sws_value), _normalize(dept_value)
            )
            if similarity < config["threshold"]:
                conflicts.append({
                    "field": sws_field,
                    "sws_value": sws_value,
                    "dept_value": dept_value,
                    "severity": config["severity"],
                })

    return conflicts


def _normalize(value: str) -> str:
    """Normalize a value for comparison."""
    return value.upper().strip()
