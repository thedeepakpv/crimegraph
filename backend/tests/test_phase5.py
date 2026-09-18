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
    ExtractionResult,
    IngestionSummary,
    GraphStatusResponse,
)
from services.neo4j_service import (
    Neo4jService,
    Neo4jConnectionError,
    get_entity_key,
    LABEL_MAP,
    ALLOWED_RELATIONSHIPS,
)
from services.normalization_service import NormalizationService


def test_unit_key_generation():
    """Unit 1: Canonical identity key generation."""
    norm = NormalizationService()
    p1 = norm.normalize_entity(Entity(type=EntityType.PHONE, value="+91 98765 43210"))
    p2 = norm.normalize_entity(Entity(type=EntityType.PHONE, value="9876543210"))
    assert get_entity_key(p1) == get_entity_key(p2) == "PHONE:9876543210"

    v1 = norm.normalize_entity(Entity(type=EntityType.VEHICLE, value="KL 11 AB 1234"))
    v2 = norm.normalize_entity(Entity(type=EntityType.VEHICLE, value="kl11ab1234"))
    assert get_entity_key(v1) == get_entity_key(v2) == "VEHICLE:KL-11-AB-1234"

    # Distinct person names
    nm1 = norm.normalize_entity(Entity(type=EntityType.PERSON, value="Rahul Menon"))
    nm2 = norm.normalize_entity(Entity(type=EntityType.PERSON, value="Rahul K. Menon"))
    assert get_entity_key(nm1) != get_entity_key(nm2)


def test_unit_neo4j_config_handling():
    """Unit 2: Neo4j configuration and connection handling without credentials."""
    # Service with no password
    svc = Neo4jService(uri="bolt://localhost:7687", username="neo4j", password="")
    status = svc.check_connection()
    assert status.status == "unavailable"
    assert "not configured" in status.message

    # Attempting ingest without credentials raises Neo4jConnectionError
    dummy_result = ExtractionResult(
        fir_id="FIR-001",
        filename="FIR-001.pdf",
        entities=[],
        entities_by_type={},
        relationships=[],
        extraction_mode="demo",
        provider="test",
    )
    try:
        svc.ingest_extraction_result(dummy_result)
        assert False, "Should raise Neo4jConnectionError"
    except Neo4jConnectionError:
        pass


def test_unit_mock_driver_ingestion():
    """Unit 3: Query construction and parameterized execution via mock driver."""
    executed_queries = []
    executed_params = []

    class MockSession:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def run(self, query, **kwargs):
            executed_queries.append(query)
            executed_params.append(kwargs)
            return None

    class MockDriver:
        def verify_connectivity(self):
            return True
        def session(self, **kwargs):
            return MockSession()
        def close(self):
            pass

    svc = Neo4jService(uri="bolt://mock:7687", username="neo4j", password="dummy_password")
    svc._driver = MockDriver()
    # Mock check_connection to report connected
    svc.check_connection = lambda: GraphStatusResponse(status="connected", uri="bolt://mock:7687", database="neo4j")

    norm = NormalizationService()
    phone_ent = norm.normalize_entity(Entity(type=EntityType.PHONE, value="+91 9876543210"))
    veh_ent = norm.normalize_entity(Entity(type=EntityType.VEHICLE, value="KL-11-AB-1234"))
    person_ent = norm.normalize_entity(Entity(type=EntityType.PERSON, value="Rahul Menon"))

    rel = ExtractedRelationship(
        source=person_ent,
        target=phone_ent,
        relationship=RelationshipType.USES,
        fir_id="FIR-001",
        page=2,
        evidence="Rahul Menon was using 9876543210.",
        confidence=0.95
    )

    result = ExtractionResult(
        fir_id="FIR-001",
        filename="FIR-001.pdf",
        entities=[person_ent, phone_ent, veh_ent],
        entities_by_type={
            "PERSON": [person_ent.normalized_value],
            "PHONE": [phone_ent.normalized_value],
            "VEHICLE": [veh_ent.normalized_value],
        },
        relationships=[rel],
        extraction_mode="demo",
        provider="mock",
    )

    summary = svc.ingest_extraction_result(result)
    assert summary.status == "success"
    assert summary.fir_id == "FIR-001"
    assert summary.entities_created_or_matched == 3
    assert summary.relationships_created_or_matched == 1

    # Verify Cypher queries constructed
    # 1. FIR MERGE query
    assert any("MERGE (f:FIR {fir_id: $fir_id})" in q for q in executed_queries)
    # 2. Entity MERGE query
    assert any("MERGE (e:Person {key: $key})" in q for q in executed_queries)
    assert any("MERGE (e:Phone {key: $key})" in q for q in executed_queries)
    assert any("MERGE (e:Vehicle {key: $key})" in q for q in executed_queries)
    # 3. CONTAINS relationship
    assert any("MERGE (f)-[r:CONTAINS]->(e)" in q for q in executed_queries)
    # 4. Relationship query
    assert any("MERGE (source)-[r:USES {fir_id: $fir_id, page: $page}]->(target)" in q for q in executed_queries)

    # Verify parameter passing
    assert any(p.get("fir_id") == "FIR-001" for p in executed_params)
    assert any(p.get("key") == "PHONE:9876543210" for p in executed_params)
    assert any(p.get("evidence") == "Rahul Menon was using 9876543210." for p in executed_params)


def test_api_status_and_ingest_endpoints():
    """Unit 4: API Endpoint tests for /api/graph/status and error handling."""
    base_url = "http://127.0.0.1:8000"

    # GET /api/graph/status
    req_status = urllib.request.Request(f"{base_url}/api/graph/status")
    with urllib.request.urlopen(req_status) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "status" in data
        assert data["status"] in ("connected", "unavailable")

    # POST /api/graph/ingest when Neo4j is offline
    dummy_payload = {
        "fir_id": "FIR-001",
        "filename": "FIR-001.pdf",
        "entities": [
            {"type": "PERSON", "value": "Rahul Menon", "normalized_value": "Rahul Menon"}
        ],
        "entities_by_type": {"PERSON": ["Rahul Menon"]},
        "relationships": [],
        "extraction_mode": "demo",
        "provider": "test",
        "status": "success"
    }
    req_ingest = urllib.request.Request(
        f"{base_url}/api/graph/ingest",
        data=json.dumps(dummy_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req_ingest)
        print("[INFO] Live Neo4j instance detected on backend!")
    except urllib.error.HTTPError as e:
        # If offline, must return 503 Service Unavailable, not 500 or fake 200
        assert e.code == 503
        err = json.loads(e.read().decode())
        assert "Neo4j" in err["detail"]
        print(f"[OK] Backend cleanly returned 503 when Neo4j unavailable: {err['detail']}")


def run_live_integration_tests():
    """
    Runs integration tests against a live Neo4j instance if configured and reachable.
    """
    print("\n--- Live Neo4j Integration Check ---")
    svc = Neo4jService()
    status = svc.check_connection()

    if status.status != "connected":
        print(f"[NOTE] Live Neo4j instance is not currently connected ({status.message}).")
        print("[NOTE] Unit tests and query construction have passed 100%.")
        print("[NOTE] To connect live Neo4j: set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD in .env")
        return False

    print(f"[OK] Connected to live Neo4j at {svc.uri} (Database: {svc.database})")
    driver = svc.get_driver()

    # User Rule: Do not delete, reset, or clear any Neo4j data. MERGE statements ensure idempotency.

    base_url = "http://127.0.0.1:8000"

    # 1. Ingest FIR-001 via API
    with open("sample_data/FIR-001.pdf", "rb") as f:
        file_bytes = f.read()
    boundary = "----WebKitFormBoundaryPhase5Test"
    body1 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="FIR-001.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    h1 = {"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body1))}

    # Extract
    req_doc1 = urllib.request.Request(f"{base_url}/api/documents/extract", data=body1, headers=h1, method="POST")
    with urllib.request.urlopen(req_doc1) as r1:
        doc1 = json.loads(r1.read().decode())

    req_ext1 = urllib.request.Request(
        f"{base_url}/api/extraction/extract",
        data=json.dumps({"filename": doc1["filename"], "fir_id": "FIR-001", "pages": doc1["pages"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req_ext1) as r_ext1:
        res1 = json.loads(r_ext1.read().decode())

    # Ingest FIR-001
    summary1 = svc.ingest_extraction_result(ExtractionResult.model_validate(res1))
    assert summary1.status == "success"
    print(f"[OK] Ingested FIR-001: {summary1.entities_created_or_matched} entities, {summary1.relationships_created_or_matched} relationships")

    # 2. Ingest FIR-002
    with open("sample_data/FIR-002.pdf", "rb") as f:
        file_bytes_2 = f.read()
    body2 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="FIR-002.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + file_bytes_2 + f"\r\n--{boundary}--\r\n".encode("utf-8")
    h2 = {"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body2))}

    req_doc2 = urllib.request.Request(f"{base_url}/api/documents/extract", data=body2, headers=h2, method="POST")
    with urllib.request.urlopen(req_doc2) as r2:
        doc2 = json.loads(r2.read().decode())

    req_ext2 = urllib.request.Request(
        f"{base_url}/api/extraction/extract",
        data=json.dumps({"filename": doc2["filename"], "fir_id": "FIR-002", "pages": doc2["pages"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req_ext2) as r_ext2:
        res2 = json.loads(r_ext2.read().decode())

    summary2 = svc.ingest_extraction_result(ExtractionResult.model_validate(res2))
    assert summary2.status == "success"
    print(f"[OK] Ingested FIR-002: {summary2.entities_created_or_matched} entities, {summary2.relationships_created_or_matched} relationships")

    # 3. Query Neo4j to verify canonical single shared phone and vehicle
    with driver.session(database=svc.database) as session:
        # Check Phone count for 9876543210
        r_phone = session.run("MATCH (p:Phone {key: 'PHONE:9876543210'}) RETURN count(p) AS cnt").single()
        assert r_phone["cnt"] == 1, f"Expected 1 Phone node for 9876543210, got {r_phone['cnt']}"
        print("[OK] Verified exactly 1 canonical Phone node exists for 9876543210")

        # Check Vehicle count for KL-11-AB-1234
        r_veh = session.run("MATCH (v:Vehicle {key: 'VEHICLE:KL-11-AB-1234'}) RETURN count(v) AS cnt").single()
        assert r_veh["cnt"] == 1, f"Expected 1 Vehicle node for KL-11-AB-1234, got {r_veh['cnt']}"
        print("[OK] Verified exactly 1 canonical Vehicle node exists for KL-11-AB-1234")

        # Check FIR nodes count
        r_firs = session.run("MATCH (f:FIR) WHERE f.fir_id IN ['FIR-001', 'FIR-002'] RETURN count(f) AS cnt").single()
        assert r_firs["cnt"] == 2, f"Expected 2 separate FIR nodes, got {r_firs['cnt']}"
        print("[OK] Verified FIR-001 and FIR-002 remain separate FIR nodes")

        # Check both FIRs link to the shared phone via CONTAINS
        r_cross = session.run(
            """
            MATCH (f:FIR)-[:CONTAINS]->(p:Phone {key: 'PHONE:9876543210'})
            RETURN collect(f.fir_id) AS fir_ids
            """
        ).single()
        fir_ids = r_cross["fir_ids"]
        assert "FIR-001" in fir_ids and "FIR-002" in fir_ids
        print(f"[OK] Verified shared Phone node links to both FIRs: {fir_ids}")

        # Check provenance properties on relationship
        r_prov = session.run(
            """
            MATCH (a:Person {key: 'PERSON:Rahul Menon'})-[r:USES]->(p:Phone {key: 'PHONE:9876543210'})
            RETURN r.fir_id AS fir_id, r.page AS page, r.evidence AS evidence, r.confidence AS confidence
            """
        ).single()
        assert r_prov["fir_id"] == "FIR-001"
        assert r_prov["page"] == 2
        assert len(r_prov["evidence"]) > 10
        assert r_prov["confidence"] == 0.95
        print(f"[OK] Verified relationship provenance in graph: FIR {r_prov['fir_id']}, Page {r_prov['page']}")

        # 4. Re-ingestion idempotency test
        summary1_re = svc.ingest_extraction_result(ExtractionResult.model_validate(res1))
        r_phone_after = session.run("MATCH (p:Phone {key: 'PHONE:9876543210'}) RETURN count(p) AS cnt").single()
        assert r_phone_after["cnt"] == 1
        print("[OK] Verified re-ingesting the same FIR does not duplicate nodes")

    print("ALL LIVE INTEGRATION TESTS PASSED WITH 100% SUCCESS!")
    return True


def run_phase5_suite():
    print("========================================")
    print("RUNNING PHASE 5 AUTOMATED TEST SUITE")
    print("========================================")

    print("\n[TEST 1] Canonical Key Generation...")
    test_unit_key_generation()
    print("[OK] Unit 1 Passed")

    print("\n[TEST 2] Neo4j Config & Connection Handling...")
    test_unit_neo4j_config_handling()
    print("[OK] Unit 2 Passed")

    print("\n[TEST 3] Cypher Query Construction & Mock Ingestion...")
    test_unit_mock_driver_ingestion()
    print("[OK] Unit 3 Passed")

    print("\n[TEST 4] API Status & Ingestion Endpoints...")
    test_api_status_and_ingest_endpoints()
    print("[OK] Unit 4 Passed")

    # Live integration test (runs if real Neo4j is configured and reachable)
    run_live_integration_tests()

    print("\n========================================")
    print("PHASE 5 TEST SUITE COMPLETED SUCCESSFULLY")
    print("========================================")


if __name__ == "__main__":
    run_phase5_suite()
