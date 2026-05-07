"""Generate synthetic data for Theme 2: SWS-Department Interoperability.

Produces:
- SWS applications with UBIDs
- Department records with different schemas
- Deliberate conflicts for demo purposes

Usage:
    python generate_synthetic.py
"""

import csv
import json
import os
import random
import string
from datetime import datetime, timedelta

random.seed(42)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Reuse some names from Theme 1
BUSINESS_NAMES = [
    "Sharma Enterprises", "Kumar Technologies Pvt Ltd", "Reddy Trading Co.",
    "Gowda Manufacturing", "Patel & Sons Agency", "Singh Constructions",
    "Rao Solutions", "Shetty Industries", "Hegde Services",
    "Murthy Associates", "Swamy Engineers", "Prasad Exports",
    "Nair Brothers", "Gupta Traders", "Jain Manufacturing",
    "Agarwal Steel Works", "Mehta Chemicals Pvt Ltd", "Shah Textiles",
    "Verma Construction Co.", "Kulkarni IT Solutions",
]

OWNER_NAMES = [
    "Rajesh Sharma", "Suresh Kumar", "Mahesh Reddy", "Ramesh Gowda",
    "Ganesh Patel", "Arun Singh", "Varun Rao", "Kiran Shetty",
    "Mohan Hegde", "Vijay Murthy", "Deepa Swamy", "Priya Prasad",
    "Anita Nair", "Kavita Gupta", "Sunita Jain", "Rekha Agarwal",
    "Neha Mehta", "Pooja Shah", "Sanjay Verma", "Manoj Kulkarni",
]

AREAS = [
    "MG Road, Bengaluru", "Jayanagar, Bengaluru", "Koramangala, Bengaluru",
    "Whitefield, Bengaluru", "Electronic City, Bengaluru", "Peenya, Bengaluru",
    "Rajajinagar, Bengaluru", "Malleshwaram, Bengaluru", "HSR Layout, Bengaluru",
    "Marathahalli, Bengaluru",
]

PINCODES = ["560001", "560004", "560034", "560066", "560100", "560058", "560010", "560003", "560102", "560037"]

SERVICE_TYPES = ["new_registration", "address_change", "renewal", "signatory_change", "closure"]
STATUSES = ["submitted", "approved", "rejected", "pending_dept"]
SECTORS = ["manufacturing", "services", "trading", "construction", "technology"]
BUSINESS_TYPES = ["proprietorship", "partnership", "pvt_ltd", "llp"]

DEPARTMENTS = ["labour", "kspcb", "commercial_tax", "factories", "fire_safety"]


def _gen_ubid(i: int) -> str:
    return f"UBID-KA-{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}{random.randint(1000, 9999)}{random.choice(string.ascii_uppercase)}"


def _gen_pan() -> str:
    return "".join(random.choices(string.ascii_uppercase, k=5)) + "".join(random.choices(string.digits, k=4)) + random.choice(string.ascii_uppercase)


def _gen_gstin(pan: str) -> str:
    return f"29{pan}{random.choice(string.digits + string.ascii_uppercase)}Z{random.choice(string.digits + string.ascii_uppercase)}"


def _random_date(start_year: int = 2025, end_year: int = 2026) -> str:
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    dt = start + timedelta(days=random.randint(0, (end - start).days))
    return dt.strftime("%Y-%m-%d")


def generate():
    n = 20
    applications = []
    dept_records = []
    conflicts = []

    for i in range(n):
        ubid = _gen_ubid(i)
        name = BUSINESS_NAMES[i % len(BUSINESS_NAMES)]
        owner = OWNER_NAMES[i % len(OWNER_NAMES)]
        address = f"No. {random.randint(1, 200)}, {AREAS[i % len(AREAS)]}"
        pincode = PINCODES[i % len(PINCODES)]
        pan = _gen_pan()
        gstin = _gen_gstin(pan)

        # SWS Application
        app = {
            "sws_reference_no": f"SWS-{random.randint(10000, 99999)}",
            "ubid": ubid,
            "business_name": name,
            "owner_name": owner,
            "registered_address": address,
            "pincode": pincode,
            "business_type": random.choice(BUSINESS_TYPES),
            "sector": random.choice(SECTORS),
            "service_type": random.choice(SERVICE_TYPES),
            "application_status": random.choice(STATUSES),
            "pan": pan,
            "gstin": gstin,
            "submitted_at": _random_date(),
        }
        applications.append(app)

        # Department records (each business appears in 2-3 departments)
        n_depts = random.randint(2, 3)
        selected_depts = random.sample(DEPARTMENTS, n_depts)

        for dept in selected_depts:
            # Introduce realistic schema differences
            dept_name_field = {
                "labour": "establishment_name",
                "kspcb": "unit_name",
                "commercial_tax": "dealer_name",
                "factories": "factory_name",
                "fire_safety": "building_name",
            }

            # Some departments have slightly different data (the source of conflicts)
            dept_business_name = name
            dept_address = address
            dept_status = app["application_status"]

            # Introduce deliberate conflicts for ~30% of records
            if random.random() < 0.3:
                conflict_type = random.choice(["name", "address", "status"])
                if conflict_type == "name":
                    # Name variation
                    dept_business_name = name.replace("Pvt Ltd", "Private Limited") if "Pvt Ltd" in name else name.upper()
                elif conflict_type == "address":
                    # Address changed in department but not SWS
                    dept_address = f"No. {random.randint(200, 500)}, {random.choice(AREAS)}"
                elif conflict_type == "status":
                    # Status mismatch
                    dept_status = random.choice([s for s in STATUSES if s != app["application_status"]])

                conflicts.append({
                    "ubid": ubid,
                    "department": dept,
                    "conflict_type": conflict_type,
                    "sws_value": name if conflict_type == "name" else (address if conflict_type == "address" else app["application_status"]),
                    "dept_value": dept_business_name if conflict_type == "name" else (dept_address if conflict_type == "address" else dept_status),
                })

            dept_rec = {
                "department_name": dept,
                "dept_record_id": f"{dept.upper()[:3]}-{random.randint(10000, 99999)}",
                "ubid": ubid,
                dept_name_field[dept]: dept_business_name,
                "proprietor_name": owner,
                "premises_address": dept_address,
                "pin_code": pincode,
                "registration_status": dept_status,
                "last_updated": _random_date(),
            }
            dept_records.append(dept_rec)

    # Write files
    _write_csv(os.path.join(OUTPUT_DIR, "sample_sws_applications.csv"), applications)
    _write_csv(os.path.join(OUTPUT_DIR, "sample_department_records.csv"), dept_records)
    _write_csv(os.path.join(OUTPUT_DIR, "sample_conflicts_ground_truth.csv"), conflicts)

    print(f"Generated:")
    print(f"  SWS Applications:   {len(applications)}")
    print(f"  Department Records: {len(dept_records)}")
    print(f"  Known Conflicts:    {len(conflicts)}")
    print(f"\nFiles written to: {OUTPUT_DIR}")


def _write_csv(path: str, records: list[dict]):
    if not records:
        return
    # Get all unique keys
    all_keys = []
    for r in records:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    generate()
