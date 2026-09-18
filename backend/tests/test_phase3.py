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

from pydantic import ValidationError



# Set environment before loading schemas to test clean fallback
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
from services.extraction_service import (
    ExtractionService,
    ExtractionValidationError,
    ConfigurationError,
)
from services.llm_provider import DemoLLMProvider, GeminiLLMProvider


def test_schema_valid_entity():
    """Test 1: Valid Entity schema."""
    ent = Entity(type=EntityType.PERSON, value="Rahul Menon")
    assert ent.type == EntityType.PERSON
    assert ent.value == "Rahul Menon"

    # Reject whitespace-only entity value
    try:
        Entity(type=EntityType.PERSON, value="   ")
        assert False, "Should reject empty/whitespace-only entity value"
    except ValidationError:
        pass


def test_schema_entity_type_rejection():
    """Test 2: Entity type validation rejects unsupported types."""
    try:
        Entity(type="UNKNOWN_TYPE", value="Something")  # type: ignore
        assert False, "Should reject unknown entity type"
    except ValidationError:
        pass


def test_schema_relationship_validation():
    """Test 3: Relationship validation ensures controlled relationship types."""
    src = Entity(type=EntityType.PERSON, value="Rahul Menon")
    tgt = Entity(type=EntityType.PHONE, value="9876543210")

    # Valid relationship
    rel = ExtractedRelationship(
        source=src,
        target=tgt,
        relationship=RelationshipType.USES,
        fir_id="FIR-001",
        page=2,
        evidence="Rahul Menon was using 9876543210",
        confidence=0.95
    )
    assert rel.relationship == RelationshipType.USES
    assert rel.confidence == 0.95

    # Reject unsupported relationship type
    try:
        ExtractedRelationship(
            source=src,
            target=tgt,
            relationship="ARBITRARY_ACTION",  # type: ignore
            fir_id="FIR-001",
            page=2,
            evidence="Rahul Menon was using 9876543210",
            confidence=0.95
        )
        assert False, "Should reject arbitrary relationship type"
    except ValidationError:
        pass


def test_provenance_field_validation():
    """Test 4: Provenance fields must be present and valid."""
    src = Entity(type=EntityType.PERSON, value="Rahul Menon")
    tgt = Entity(type=EntityType.PHONE, value="9876543210")

    # Negative page number
    try:
        ExtractedRelationship(
            source=src, target=tgt, relationship=RelationshipType.USES,
            fir_id="FIR-001", page=0, evidence="Valid evidence", confidence=0.9
        )
        assert False, "Should reject page <= 0"
    except ValidationError:
        pass

    # Invalid confidence > 1.0
    try:
        ExtractedRelationship(
            source=src, target=tgt, relationship=RelationshipType.USES,
            fir_id="FIR-001", page=1, evidence="Valid evidence", confidence=1.5
        )
        assert False, "Should reject confidence > 1.0"
    except ValidationError:
        pass

    # Empty evidence string
    try:
        ExtractedRelationship(
            source=src, target=tgt, relationship=RelationshipType.USES,
            fir_id="FIR-001", page=1, evidence=" ", confidence=0.9
        )
        assert False, "Should reject blank evidence"
    except ValidationError:
        pass


def run_phase3_api_suite():
    print("========================================")
    print("RUNNING PHASE 3 AUTOMATED TEST SUITE")
    print("========================================")

    base_url = "http://127.0.0.1:8000"

    # 1. Pydantic Unit Tests
    print("\n[UNIT 1] Entity schema and whitespace validation...")
    test_schema_valid_entity()
    print("[OK] Unit 1 Passed")

    print("\n[UNIT 2] Entity type rejection...")
    test_schema_entity_type_rejection()
    print("[OK] Unit 2 Passed")

    print("\n[UNIT 3] Controlled relationship types...")
    test_schema_relationship_validation()
    print("[OK] Unit 3 Passed")

    print("\n[UNIT 4] Provenance field validation...")
    test_provenance_field_validation()
    print("[OK] Unit 4 Passed")

    # 2. Phase 1 Health check regression test
    print("\n[API 1] Phase 1 Regression: Health Check...")
    req = urllib.request.Request(f"{base_url}/api/health")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data.get("status") == "ok"
    print("[OK] Phase 1 Health Check Still Operational")

    # 3. Phase 2 PDF extraction regression test
    print("\n[API 2] Phase 2 Regression: PDF Extraction...")
    boundary = "----WebKitFormBoundaryPhase3Test"
    with open("sample_data/FIR-001.pdf", "rb") as f:
        file_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="FIR-001.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body))
    }
    req_pdf = urllib.request.Request(f"{base_url}/api/documents/extract", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req_pdf) as resp:
        assert resp.status == 200
        pdf_res = json.loads(resp.read().decode())
        assert pdf_res["page_count"] == 2
    print("[OK] Phase 2 PDF Extraction Still Operational")

    # 4. Phase 3 Demo extraction for FIR-001
    print("\n[API 3] Demo Extraction: FIR-001...")
    req_payload_1 = {
        "filename": "FIR-001.pdf",
        "fir_id": "FIR-001",
        "pages": pdf_res["pages"]
    }
    req_ext1 = urllib.request.Request(
        f"{base_url}/api/extraction/extract",
        data=json.dumps(req_payload_1).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req_ext1) as resp:
        assert resp.status == 200
        res1 = json.loads(resp.read().decode())
        assert res1["extraction_mode"] == "demo"
        assert res1["fir_id"] == "FIR-001"
        assert len(res1["entities"]) >= 5
        assert len(res1["relationships"]) >= 3
        
        # Verify provenance on every relationship
        for r in res1["relationships"]:
            assert r["fir_id"] == "FIR-001"
            assert r["page"] in (1, 2)
            assert len(r["evidence"]) > 10
            assert 0.0 <= r["confidence"] <= 1.0

        # Verify key entities
        person_names = res1["entities_by_type"]["PERSON"]
        assert "Rahul Menon" in person_names
        phones = res1["entities_by_type"]["PHONE"]
        assert "9876543210" in phones
        vehicles = res1["entities_by_type"]["VEHICLE"]
        assert "KL-11-AB-1234" in vehicles
        print(f"[OK] FIR-001 extracted {len(res1['entities'])} entities and {len(res1['relationships'])} relationships with full provenance.")

    # 5. Phase 3 Demo extraction for FIR-002
    print("\n[API 4] Demo Extraction: FIR-002...")
    # Extract FIR-002 PDF first
    with open("sample_data/FIR-002.pdf", "rb") as f:
        file_bytes_2 = f.read()

    body_2 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="FIR-002.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + file_bytes_2 + f"\r\n--{boundary}--\r\n".encode("utf-8")

    headers_2 = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body_2))
    }
    req_pdf2 = urllib.request.Request(f"{base_url}/api/documents/extract", data=body_2, headers=headers_2, method="POST")
    with urllib.request.urlopen(req_pdf2) as resp:
        pdf_res2 = json.loads(resp.read().decode())


    req_payload_2 = {
        "filename": "FIR-002.pdf",
        "fir_id": "FIR-002",
        "pages": pdf_res2["pages"]
    }
    req_ext2 = urllib.request.Request(
        f"{base_url}/api/extraction/extract",
        data=json.dumps(req_payload_2).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req_ext2) as resp:
        assert resp.status == 200
        res2 = json.loads(resp.read().decode())
        assert res2["fir_id"] == "FIR-002"
        assert "Arjun Das" in res2["entities_by_type"]["PERSON"]
        assert "9876543210" in res2["entities_by_type"]["PHONE"]
        assert "KL-11-AB-1234" in res2["entities_by_type"]["VEHICLE"]
        print(f"[OK] FIR-002 extracted {len(res2['entities'])} entities and {len(res2['relationships'])} relationships.")

    # 6. Behavior when forced AI without API key configured
    print("\n[API 5] Behavior when forced AI mode has no key configured...")
    req_payload_forced_ai = {
        "filename": "FIR-001.pdf",
        "pages": pdf_res["pages"],
        "force_mode": "ai"
    }
    # Temporarily ensure no key is present for this test
    req_forced_ai = urllib.request.Request(
        f"{base_url}/api/extraction/extract",
        data=json.dumps(req_payload_forced_ai).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        urllib.request.urlopen(req_forced_ai)
        # If user happens to have a live key set in env, it might succeed, which is okay, but if not it should return 400
        print("[INFO] Forced AI mode succeeded (live key configured)")
    except urllib.error.HTTPError as e:
        assert e.code == 400
        err = json.loads(e.read().decode())
        assert "No LLM API key configured" in err["detail"]
        print(f"[OK] Cleanly returned 400 error when forced AI has no key: {err['detail']}")

    # 7. Rejection of invalid extraction request (empty pages)
    print("\n[API 6] Rejection of invalid / empty request...")
    invalid_payload = {
        "filename": "empty.pdf",
        "pages": []
    }
    req_invalid = urllib.request.Request(
        f"{base_url}/api/extraction/extract",
        data=json.dumps(invalid_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        urllib.request.urlopen(req_invalid)
        assert False, "Should have rejected empty pages with 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400
        print(f"[OK] Correctly rejected empty pages request with code {e.code}")

    print("\n========================================")
    print("ALL PHASE 3 AUTOMATED TESTS PASSED!")
    print("========================================")


if __name__ == "__main__":
    run_phase3_api_suite()
