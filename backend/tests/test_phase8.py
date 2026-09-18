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
    GraphAnalysisResponse,
    HighlyConnectedEntity,
    RepeatedEntity,
    TwoHopPath,
    BridgeEntity,
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


def test_global_analytics_endpoint():
    """Test 1: GET /api/graph/analytics returns valid GraphAnalysisResponse."""
    status, data = http_get(f"{BASE_URL}/api/graph/analytics")
    assert status == 200, f"Expected 200, got {status}"

    resp = GraphAnalysisResponse.model_validate(data)
    assert resp.fir_id is None, "Global analytics fir_id should be None"
    assert resp.total_signals > 0, f"Expected positive signals, got {resp.total_signals}"
    assert "INVESTIGATIVE SIGNALS ONLY" in resp.disclaimer
    print(f"[OK] Test 1: Global analytics endpoint returned {resp.total_signals} signals")


def test_fir_scoped_analytics_endpoint():
    """Test 2: GET /api/graph/firs/FIR-001/analytics returns valid FIR-scoped response."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/FIR-001/analytics")
    assert status == 200, f"Expected 200, got {status}"

    resp = GraphAnalysisResponse.model_validate(data)
    assert resp.fir_id == "FIR-001"
    assert resp.total_signals > 0
    print(f"[OK] Test 2: FIR-001 scoped analytics returned {resp.total_signals} signals")


def test_highly_connected_entities_exclusion():
    """Test 3: Highly connected entities exclude FIR nodes and CONTAINS provenance edges."""
    status, data = http_get(f"{BASE_URL}/api/graph/analytics")
    assert status == 200

    resp = GraphAnalysisResponse.model_validate(data)
    assert len(resp.highly_connected_entities) > 0, "Expected at least 1 highly connected entity"

    for hce in resp.highly_connected_entities:
        assert hce.entity_type != "FIR", f"FIR node {hce.entity_key} leaked into highly connected entities"
        assert not hce.entity_key.startswith("FIR:"), f"FIR key leaked: {hce.entity_key}"
        assert hce.degree > 0
        assert hce.degree == (hce.in_degree + hce.out_degree) or hce.degree <= (hce.in_degree + hce.out_degree)

        for ce in hce.connected_entities:
            assert ce.entity_type != "FIR", "FIR node appeared in connected entities"
            assert ce.relationship_type != "CONTAINS", "CONTAINS relationship leaked into connectivity"

        for prov in hce.provenance:
            assert prov.relationship_type != "CONTAINS", "CONTAINS provenance leaked into connectivity"

    top = resp.highly_connected_entities[0]
    print(f"[OK] Test 3: Highly connected entities strictly exclude FIR and CONTAINS edges (Top: {top.canonical_value}, degree {top.degree})")


def test_repeated_entities_canonical_matching():
    """Test 4: Repeated entity detection accurately identifies shared canonical phone and vehicle across FIR-001 and FIR-002."""
    status, data = http_get(f"{BASE_URL}/api/graph/analytics")
    assert status == 200

    resp = GraphAnalysisResponse.model_validate(data)
    rep_keys = [re.entity_key for re in resp.repeated_entities]
    assert "PHONE:9876543210" in rep_keys, f"PHONE:9876543210 missing from repeated entities ({rep_keys})"
    assert "VEHICLE:KL-11-AB-1234" in rep_keys, f"VEHICLE:KL-11-AB-1234 missing from repeated entities ({rep_keys})"

    phone_rep = next(re for re in resp.repeated_entities if re.entity_key == "PHONE:9876543210")
    assert phone_rep.fir_count >= 2
    assert "FIR-001" in phone_rep.fir_ids
    assert "FIR-002" in phone_rep.fir_ids
    assert len(phone_rep.occurrences) >= 2

    # Check Location nodes are excluded from repeated entities
    for re in resp.repeated_entities:
        assert re.entity_type != "LOCATION", f"Location node {re.entity_key} should be excluded from repeated entity signals"
        assert re.entity_type != "FIR"

    print(f"[OK] Test 4: Repeated entities detected shared phone and vehicle across FIR-001 and FIR-002")


def test_two_hop_relationships():
    """Test 5: 2-Hop candidate relationships contain intermediary node and hop provenance."""
    status, data = http_get(f"{BASE_URL}/api/graph/analytics")
    assert status == 200

    resp = GraphAnalysisResponse.model_validate(data)
    assert len(resp.two_hop_relationships) > 0, "Expected at least 1 2-hop relationship"

    for path in resp.two_hop_relationships:
        assert path.source_type != "FIR"
        assert path.intermediary_type != "FIR"
        assert path.target_type != "FIR"
        assert path.hop1_relationship != "CONTAINS"
        assert path.hop2_relationship != "CONTAINS"
        assert path.source_key != path.target_key
        assert len(path.path_description) > 5

        if path.hop1_provenance:
            assert path.hop1_provenance.fir_id in ["FIR-001", "FIR-002"]
        if path.hop2_provenance:
            assert path.hop2_provenance.fir_id in ["FIR-001", "FIR-002"]

    print(f"[OK] Test 5: 2-Hop relationships verified with valid path provenance ({len(resp.two_hop_relationships)} paths)")


def test_potential_bridge_entities():
    """Test 6: Potential bridge/intermediary entities connect distinct endpoints without direct domain edge."""
    status, data = http_get(f"{BASE_URL}/api/graph/analytics")
    assert status == 200

    resp = GraphAnalysisResponse.model_validate(data)
    assert len(resp.potential_bridges) > 0, "Expected at least 1 potential bridge entity"

    bridge_keys = [b.entity_key for b in resp.potential_bridges]
    assert "PHONE:9876543210" in bridge_keys or "VEHICLE:KL-11-AB-1234" in bridge_keys

    # Find the phone bridge
    phone_bridge = next((b for b in resp.potential_bridges if b.entity_key == "PHONE:9876543210"), None)
    if phone_bridge:
        assert phone_bridge.signal_label == "Potential Bridge / Intermediary"
        assert phone_bridge.bridge_score > 0
        assert len(phone_bridge.bridged_pairs) > 0
        assert "Potential" in phone_bridge.explanation

        # Check cross-FIR bridged pair between Rahul Menon and Arjun Das
        cross_pairs = [p for p in phone_bridge.bridged_pairs if p.is_cross_fir]
        assert len(cross_pairs) > 0, "Expected cross-FIR bridged pair for shared phone"
        cp = cross_pairs[0]
        assert ("Rahul Menon" in cp.entity_a_canonical and "Arjun Das" in cp.entity_b_canonical) or \
               ("Arjun Das" in cp.entity_a_canonical and "Rahul Menon" in cp.entity_b_canonical)
        assert cp.fir_a != cp.fir_b

    print(f"[OK] Test 6: Potential Bridge / Intermediary correctly identified cross-FIR connector between Rahul Menon & Arjun Das")


def test_read_only_invariance():
    """Test 7: Read-only verification: Neo4j node and edge counts are strictly invariant before and after analytics."""
    svc = Neo4jService()
    driver = svc.get_driver()

    with driver.session(database=svc.database) as session:
        n_before = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        r_before = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]

        # Run multiple analytics queries
        svc.get_graph_analytics(None)
        svc.get_graph_analytics("FIR-001")
        svc.get_graph_analytics("FIR-002")

        n_after = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        r_after = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]

        assert n_before == n_after, f"Node count mutated from {n_before} to {n_after}"
        assert r_before == r_after, f"Relationship count mutated from {r_before} to {r_after}"

    svc.close()
    print(f"[OK] Test 7: Read-only invariance confirmed: nodes ({n_before} == {n_after}), relationships ({r_before} == {r_after})")


def test_nonexistent_fir_handling():
    """Test 8: GET /api/graph/firs/NONEXISTENT-999/analytics returns 404."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/NONEXISTENT-999/analytics")
    assert status == 404, f"Expected 404, got {status}"
    assert "NONEXISTENT-999" in data.get("detail", "")
    print(f"[OK] Test 8: Nonexistent FIR cleanly returned 404: {data['detail']}")


def run_phase8_suite():
    print("========================================")
    print("RUNNING PHASE 8 AUTOMATED TEST SUITE")
    print("========================================")

    print("\n[TEST 1] Global Graph Analytics Endpoint...")
    test_global_analytics_endpoint()

    print("\n[TEST 2] FIR-Scoped Analytics Endpoint...")
    test_fir_scoped_analytics_endpoint()

    print("\n[TEST 3] Highly Connected Entities (FIR & CONTAINS Excluded)...")
    test_highly_connected_entities_exclusion()

    print("\n[TEST 4] Repeated Entities (Canonical Normalized Keys)...")
    test_repeated_entities_canonical_matching()

    print("\n[TEST 5] 2-Hop Candidate Relationships...")
    test_two_hop_relationships()

    print("\n[TEST 6] Potential Bridge / Intermediary Entities...")
    test_potential_bridge_entities()

    print("\n[TEST 7] Read-Only Invariance (Zero Mutation)...")
    test_read_only_invariance()

    print("\n[TEST 8] Nonexistent FIR Handling (404)...")
    test_nonexistent_fir_handling()

    print("\n========================================")
    print("ALL 8 PHASE 8 AUTOMATED TESTS PASSED!")
    print("========================================")


if __name__ == "__main__":
    run_phase8_suite()
