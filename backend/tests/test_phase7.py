import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.schemas import (
    HistoricalMatch,
    HistoricalLookupResponse,
)
from services.neo4j_service import (
    Neo4jService,
    FIRNotFoundError,
)

BASE_URL = "http://127.0.0.1:8000"


def http_get(url: str):
    """Helper to perform HTTP GET returning status code and parsed JSON."""
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        data = json.loads(e.read().decode("utf-8"))
        return e.code, data


def test_historical_lookup_endpoint():
    """Test 1: GET /api/graph/firs/{fir_id}/historical-connections returns valid response."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/FIR-002/historical-connections")
    assert status == 200, f"Expected 200, got {status}"

    resp = HistoricalLookupResponse.model_validate(data)
    assert resp.current_fir_id == "FIR-002"
    assert resp.total_matches >= 2, f"Expected at least 2 historical matches, got {resp.total_matches}"
    assert resp.shared_entity_count >= 2, f"Expected at least 2 shared entities, got {resp.shared_entity_count}"
    print(f"[OK] Test 1: Historical lookup endpoint returned {resp.total_matches} candidate connections")


def test_shared_phone_detection():
    """Test 2: Shared normalized phone '9876543210' is detected in historical FIR-001."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/FIR-002/historical-connections")
    assert status == 200

    resp = HistoricalLookupResponse.model_validate(data)
    phone_matches = [m for m in resp.matches if m.entity_type == "PHONE"]
    assert len(phone_matches) >= 1, "Expected at least 1 phone historical match"

    match = phone_matches[0]
    assert match.canonical_value == "9876543210", f"Expected canonical 9876543210, got {match.canonical_value}"
    assert match.historical_fir_id == "FIR-001", f"Expected historical FIR-001, got {match.historical_fir_id}"
    assert match.historical_filename == "FIR-001.pdf"
    assert "9876543210" in match.evidence
    print(f"[OK] Test 2: Shared phone 9876543210 correctly detected linking FIR-002 to historical FIR-001")


def test_shared_vehicle_detection():
    """Test 3: Shared normalized vehicle 'KL-11-AB-1234' is detected in historical FIR-001."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/FIR-002/historical-connections")
    assert status == 200

    resp = HistoricalLookupResponse.model_validate(data)
    veh_matches = [m for m in resp.matches if m.entity_type == "VEHICLE"]
    assert len(veh_matches) >= 1, "Expected at least 1 vehicle historical match"

    match = veh_matches[0]
    assert match.canonical_value == "KL-11-AB-1234"
    assert match.historical_fir_id == "FIR-001"
    assert match.historical_relationship == "OPERATES"
    assert "KL-11-AB-1234" in match.evidence
    print(f"[OK] Test 3: Shared vehicle KL-11-AB-1234 correctly detected linking FIR-002 to historical FIR-001")


def test_current_fir_excluded():
    """Test 4: Current FIR is strictly excluded from its own historical results."""
    # Test for FIR-002
    status2, data2 = http_get(f"{BASE_URL}/api/graph/firs/FIR-002/historical-connections")
    assert status2 == 200
    resp2 = HistoricalLookupResponse.model_validate(data2)
    for m in resp2.matches:
        assert m.historical_fir_id != "FIR-002", "Current FIR-002 must not appear as historical FIR"

    # Test for FIR-001
    status1, data1 = http_get(f"{BASE_URL}/api/graph/firs/FIR-001/historical-connections")
    assert status1 == 200
    resp1 = HistoricalLookupResponse.model_validate(data1)
    for m in resp1.matches:
        assert m.historical_fir_id != "FIR-001", "Current FIR-001 must not appear as historical FIR"

    print("[OK] Test 4: Current FIR is strictly excluded from historical connections results")


def test_no_match_and_nonexistent():
    """Test 5: Clean handling for no-match cases and nonexistent FIR (404)."""
    # Nonexistent FIR
    status, data = http_get(f"{BASE_URL}/api/graph/firs/NONEXISTENT-FIR-999/historical-connections")
    assert status == 404
    assert "not found" in data["detail"]

    # Unit check for FIR with no shared entities
    svc = Neo4jService()
    driver = svc.get_driver()
    with driver.session(database=svc.database) as session:
        # Create a temporary isolated FIR node that shares no entities with others
        session.run("MERGE (f:FIR {fir_id: 'TEST-ISOLATED-001', filename: 'isolated.pdf'})")
        try:
            res = svc.get_historical_connections("TEST-ISOLATED-001")
            assert res.total_matches == 0, f"Expected 0 matches for isolated FIR, got {res.total_matches}"
            assert res.matches == []
            assert res.shared_entity_count == 0
            print("[OK] Test 5: Clean empty result (0 matches) returned for FIR with no shared entities, 404 for unknown FIR")
        finally:
            session.run("MATCH (f:FIR {fir_id: 'TEST-ISOLATED-001'}) DETACH DELETE f")
    svc.close()


def test_provenance_fields():
    """Test 6: Validates that provenance fields are properly populated on historical matches."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/FIR-002/historical-connections")
    assert status == 200

    resp = HistoricalLookupResponse.model_validate(data)
    for m in resp.matches:
        assert isinstance(m.entity_key, str) and len(m.entity_key) > 0
        assert isinstance(m.canonical_value, str) and len(m.canonical_value) > 0
        assert m.current_fir_id == "FIR-002"
        assert m.historical_fir_id == "FIR-001"
        assert m.historical_filename == "FIR-001.pdf"
        assert m.page is not None and m.page >= 1
        assert m.evidence is not None and len(m.evidence.strip()) > 10
        assert m.confidence is not None and 0.0 <= m.confidence <= 1.0
        print(f"  - Verified Provenance: {m.entity_type} {m.canonical_value} | Hist FIR: {m.historical_fir_id} | Page: {m.page} | Conf: {m.confidence}")

    print("[OK] Test 6: All historical matches contain verified provenance fields (page, evidence, confidence)")


def test_exact_canonical_matching_and_location_exclusion():
    """Test 7: Conservative exact matching: Location entities are NOT matched as connections."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/FIR-002/historical-connections")
    assert status == 200

    resp = HistoricalLookupResponse.model_validate(data)
    for m in resp.matches:
        # Rule: LOCATION must not be treated as a person/criminal connection
        assert m.entity_type != "LOCATION", f"Location entity {m.entity_key} must NOT be returned as a connection"
        assert m.entity_type in {"PHONE", "VEHICLE", "PERSON", "ORGANIZATION"}

    # Confirm person names Rahul Menon and Arjun Das are NOT merged
    person_keys = {m.canonical_value for m in resp.matches if m.entity_type == "PERSON"}
    assert "Rahul Menon" not in person_keys, "Rahul Menon should not match Arjun Das"
    assert "Arjun Das" not in person_keys

    print("[OK] Test 7: Exact canonical matching verified; Location entities excluded from connections")


def test_no_duplicate_nodes():
    """Test 8: Read-only historical lookup does not create or duplicate any Neo4j nodes."""
    svc = Neo4jService()
    driver = svc.get_driver()

    with driver.session(database=svc.database) as session:
        count_query = "MATCH (n) RETURN count(n) AS cnt"
        nodes_before = session.run(count_query).single()["cnt"]

        # Run historical queries
        svc.get_historical_connections("FIR-001")
        svc.get_historical_connections("FIR-002")

        nodes_after = session.run(count_query).single()["cnt"]
        assert nodes_before == nodes_after, f"Node count changed from {nodes_before} to {nodes_after}"

    svc.close()
    print(f"[OK] Test 8: Read-only verification confirmed: Node count invariant ({nodes_before} == {nodes_after})")


def run_phase7_suite():
    print("========================================")
    print("RUNNING PHASE 7 AUTOMATED TEST SUITE")
    print("========================================")

    print("\n[TEST 1] Historical Lookup Endpoint...")
    test_historical_lookup_endpoint()

    print("\n[TEST 2] Shared Phone Detection...")
    test_shared_phone_detection()

    print("\n[TEST 3] Shared Vehicle Detection...")
    test_shared_vehicle_detection()

    print("\n[TEST 4] Current FIR Excluded from Results...")
    test_current_fir_excluded()

    print("\n[TEST 5] No-Match and Nonexistent FIR Handling...")
    test_no_match_and_nonexistent()

    print("\n[TEST 6] Provenance Fields Verification...")
    test_provenance_fields()

    print("\n[TEST 7] Exact Matching & Location Exclusion...")
    test_exact_canonical_matching_and_location_exclusion()

    print("\n[TEST 8] Read-Only Invariance (Zero Duplicates)...")
    test_no_duplicate_nodes()

    print("\n========================================")
    print("ALL PHASE 7 AUTOMATED TESTS PASSED!")
    print("========================================")


if __name__ == "__main__":
    run_phase7_suite()
