import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["DEMO_MODE"] = "true"

from models.schemas import (
    EntityType,
    RelationshipType,
    Entity,
    ExtractedRelationship,
    PageText,
    ExtractionRequest,
    ExtractionResult,
)
from services.normalization_service import (
    NormalizationService,
    NormalizationError,
    normalize_phone,
    normalize_vehicle,
    normalize_person,
    normalize_location,
    normalize_organization,
)


def run_phase4_tests():
    print("========================================")
    print("RUNNING PHASE 4 AUTOMATED TEST SUITE")
    print("========================================")

    service = NormalizationService()

    # 1. Phone formatting variants normalize consistently
    print("\n[TEST 1] Phone formatting variants normalize consistently...")
    phone_variants = [
        "9876543210",
        "98765 43210",
        "+91 9876543210",
        "+91-9876543210",
        "09876543210",
    ]
    expected_phone = "9876543210"
    for var in phone_variants:
        norm = normalize_phone(var)
        assert norm == expected_phone, f"Failed for '{var}': got '{norm}', expected '{expected_phone}'"
    print(f"[OK] All 5 phone variants normalized to canonical '{expected_phone}'")

    # 2. Vehicle formatting variants normalize consistently
    print("\n[TEST 2] Vehicle formatting variants normalize consistently...")
    vehicle_variants = [
        "KL-11-AB-1234",
        "KL 11 AB 1234",
        "KL11AB1234",
        "kl-11-ab-1234",
        "kl 11 ab 1234",
    ]
    expected_vehicle = "KL-11-AB-1234"
    for var in vehicle_variants:
        norm = normalize_vehicle(var)
        assert norm == expected_vehicle, f"Failed for '{var}': got '{norm}', expected '{expected_vehicle}'"
    print(f"[OK] All 5 vehicle variants normalized to canonical '{expected_vehicle}'")

    # 3. Person capitalization/whitespace normalizes consistently
    print("\n[TEST 3] Person capitalization and whitespace normalization...")
    person_variants = [
        "Rahul Menon",
        "rahul menon",
        "  Rahul   Menon  ",
        "RAHUL MENON",
    ]
    expected_person = "Rahul Menon"
    for var in person_variants:
        norm = normalize_person(var)
        assert norm == expected_person, f"Failed for '{var}': got '{norm}', expected '{expected_person}'"
    print(f"[OK] All person variants normalized to canonical '{expected_person}'")

    # 4. Original raw values are preserved
    print("\n[TEST 4] Original raw values are preserved alongside normalized_value...")
    raw_phone_ent = Entity(type=EntityType.PHONE, value="+91 98765 43210")
    norm_phone_ent = service.normalize_entity(raw_phone_ent)
    assert norm_phone_ent.value == "+91 98765 43210", "Original value must not be overwritten!"
    assert norm_phone_ent.normalized_value == "9876543210", "Normalized value must be canonical!"

    raw_veh_ent = Entity(type=EntityType.VEHICLE, value="kl 11 ab 1234")
    norm_veh_ent = service.normalize_entity(raw_veh_ent)
    assert norm_veh_ent.value == "kl 11 ab 1234"
    assert norm_veh_ent.normalized_value == "KL-11-AB-1234"
    print("[OK] Both .value and .normalized_value preserved correctly")

    # 5. Invalid/empty values are rejected appropriately
    print("\n[TEST 5] Invalid/empty values rejected...")
    try:
        normalize_phone("")
        assert False, "Should reject empty phone"
    except NormalizationError:
        pass

    try:
        normalize_phone("not-a-number")
        assert False, "Should reject non-digit phone"
    except NormalizationError:
        pass

    try:
        normalize_vehicle("")
        assert False, "Should reject empty vehicle"
    except NormalizationError:
        pass

    try:
        normalize_vehicle("!@#$")
        assert False, "Should reject non-alphanumeric vehicle"
    except NormalizationError:
        pass

    try:
        normalize_person("   ")
        assert False, "Should reject empty person name"
    except NormalizationError:
        pass
    print("[OK] All invalid and empty inputs correctly raised NormalizationError")

    # 6. Two equivalent values compare equal after normalization
    print("\n[TEST 6] Equivalent values compare equal after normalization...")
    e1 = service.normalize_entity(Entity(type=EntityType.PHONE, value="+91-9876543210"))
    e2 = service.normalize_entity(Entity(type=EntityType.PHONE, value="98765 43210"))
    assert e1.value != e2.value, "Raw values should be different"
    assert e1.normalized_value == e2.normalized_value, "Normalized values must be identical"

    v1 = service.normalize_entity(Entity(type=EntityType.VEHICLE, value="KL 11 AB 1234"))
    v2 = service.normalize_entity(Entity(type=EntityType.VEHICLE, value="kl11ab1234"))
    assert v1.normalized_value == v2.normalized_value
    print("[OK] Equivalent phone and vehicle variants evaluate equal on normalized_value")

    # 7. Similar-but-not-identical person names are NOT automatically merged
    print("\n[TEST 7] Similar-but-not-identical person names NOT merged...")
    p1 = service.normalize_entity(Entity(type=EntityType.PERSON, value="Rahul Menon"))
    p2 = service.normalize_entity(Entity(type=EntityType.PERSON, value="Rahul K. Menon"))
    assert p1.normalized_value != p2.normalized_value, "Should not merge distinct names without proof"
    assert p1.normalized_value == "Rahul Menon"
    assert p2.normalized_value == "Rahul K. Menon"
    print(f"[OK] Distinct names preserved: '{p1.normalized_value}' != '{p2.normalized_value}'")

    # 8. Shared entities across FIR-001 and FIR-002 produce identical normalized keys
    print("\n[TEST 8] Cross-FIR shared entities in FIR-001 and FIR-002...")
    base_url = "http://127.0.0.1:8000"

    # Ingest FIR-001
    with open("sample_data/FIR-001.pdf", "rb") as f:
        f1_bytes = f.read()
    boundary = "----WebKitFormBoundaryPhase4Test"
    body1 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="FIR-001.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + f1_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    h1 = {"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body1))}

    req1 = urllib.request.Request(f"{base_url}/api/documents/extract", data=body1, headers=h1, method="POST")
    with urllib.request.urlopen(req1) as r1:
        doc1 = json.loads(r1.read().decode())

    req_ext1 = urllib.request.Request(
        f"{base_url}/api/extraction/extract",
        data=json.dumps({"filename": doc1["filename"], "fir_id": "FIR-001", "pages": doc1["pages"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req_ext1) as r_ext1:
        res1 = json.loads(r_ext1.read().decode())

    # Ingest FIR-002
    with open("sample_data/FIR-002.pdf", "rb") as f:
        f2_bytes = f.read()
    body2 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="FIR-002.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + f2_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    h2 = {"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body2))}

    req2 = urllib.request.Request(f"{base_url}/api/documents/extract", data=body2, headers=h2, method="POST")
    with urllib.request.urlopen(req2) as r2:
        doc2 = json.loads(r2.read().decode())

    req_ext2 = urllib.request.Request(
        f"{base_url}/api/extraction/extract",
        data=json.dumps({"filename": doc2["filename"], "fir_id": "FIR-002", "pages": doc2["pages"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req_ext2) as r_ext2:
        res2 = json.loads(r_ext2.read().decode())

    # Find normalized phones and vehicles
    f1_phones = [e["normalized_value"] for e in res1["entities"] if e["type"] == "PHONE"]
    f2_phones = [e["normalized_value"] for e in res2["entities"] if e["type"] == "PHONE"]
    shared_phones = set(f1_phones).intersection(set(f2_phones))
    assert "9876543210" in shared_phones, f"Shared phone not matched! f1={f1_phones}, f2={f2_phones}"

    f1_vehicles = [e["normalized_value"] for e in res1["entities"] if e["type"] == "VEHICLE"]
    f2_vehicles = [e["normalized_value"] for e in res2["entities"] if e["type"] == "VEHICLE"]
    shared_vehicles = set(f1_vehicles).intersection(set(f2_vehicles))
    assert "KL-11-AB-1234" in shared_vehicles, f"Shared vehicle not matched! f1={f1_vehicles}, f2={f2_vehicles}"

    print(f"[OK] Cross-FIR shared phone matched: {shared_phones}")
    print(f"[OK] Cross-FIR shared vehicle matched: {shared_vehicles}")

    # 9. Verify relationship endpoints contain normalized entities & provenance
    print("\n[TEST 9] Relationship endpoints contain normalized entities & provenance...")
    for rel in res1["relationships"]:
        assert rel["source"]["normalized_value"] is not None
        assert rel["target"]["normalized_value"] is not None
        assert rel["fir_id"] == "FIR-001"
        assert rel["page"] in (1, 2)
        assert len(rel["evidence"]) > 5
        assert 0.0 <= rel["confidence"] <= 1.0
    print(f"[OK] All {len(res1['relationships'])} relationships have normalized source/target and full provenance")

    print("\n========================================")
    print("ALL PHASE 4 TESTS PASSED WITH 100% SUCCESS!")
    print("========================================")


if __name__ == "__main__":
    run_phase4_tests()
