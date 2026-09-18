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
    GraphNode,
    GraphRelationship,
    GraphDataResponse,
    FIRItem,
    FIRListResponse,
)
from services.neo4j_service import (
    Neo4jService,
    FIRNotFoundError,
    Neo4jConnectionError,
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


def test_fir_list_endpoint():
    """Test 1: GET /api/graph/firs returns list of available FIRs."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs")
    assert status == 200, f"Expected 200, got {status}"
    
    # Validate against Pydantic schema
    fir_list = FIRListResponse.model_validate(data)
    assert fir_list.total_count >= 2, f"Expected at least 2 FIRs, found {fir_list.total_count}"
    
    fir_ids = [item.fir_id for item in fir_list.firs]
    assert "FIR-001" in fir_ids, "FIR-001 missing from FIR list"
    assert "FIR-002" in fir_ids, "FIR-002 missing from FIR list"
    
    # Check item structure
    fir1_item = next(item for item in fir_list.firs if item.fir_id == "FIR-001")
    assert fir1_item.filename == "FIR-001.pdf"
    assert fir1_item.entity_count is not None and fir1_item.entity_count > 0
    print(f"[OK] FIR list endpoint passed: found {fir_list.total_count} FIRs ({fir_ids})")


def test_graph_retrieval_fir_001():
    """Test 2: GET /api/graph/firs/FIR-001 returns nodes and relationships for FIR-001."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/FIR-001")
    assert status == 200, f"Expected 200, got {status}"

    # Validate against Pydantic schema
    graph = GraphDataResponse.model_validate(data)
    assert graph.fir_id == "FIR-001"
    assert graph.node_count >= 8, f"Expected >= 8 nodes for FIR-001, got {graph.node_count}"
    assert graph.relationship_count >= 11, f"Expected >= 11 relationships for FIR-001, got {graph.relationship_count}"

    # Verify expected key nodes
    node_keys = {n.key for n in graph.nodes}
    assert "FIR:FIR-001" in node_keys, "FIR root node missing"
    assert "PERSON:Rahul Menon" in node_keys, "Rahul Menon node missing"
    assert "PHONE:9876543210" in node_keys, "Canonical phone node missing"
    assert "VEHICLE:KL-11-AB-1234" in node_keys, "Canonical vehicle node missing"

    # Also test the route alias /api/graph/FIR-001
    status_alias, data_alias = http_get(f"{BASE_URL}/api/graph/FIR-001")
    assert status_alias == 200
    assert data_alias["fir_id"] == "FIR-001"
    print(f"[OK] Graph retrieval for FIR-001 passed: {graph.node_count} nodes, {graph.relationship_count} relationships")


def test_graph_retrieval_fir_002():
    """Test 3: GET /api/graph/firs/FIR-002 returns nodes and relationships for FIR-002."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/FIR-002")
    assert status == 200, f"Expected 200, got {status}"

    graph = GraphDataResponse.model_validate(data)
    assert graph.fir_id == "FIR-002"
    assert graph.node_count >= 5, f"Expected >= 5 nodes for FIR-002, got {graph.node_count}"
    assert graph.relationship_count >= 7, f"Expected >= 7 relationships for FIR-002, got {graph.relationship_count}"

    node_keys = {n.key for n in graph.nodes}
    assert "FIR:FIR-002" in node_keys
    assert "PERSON:Arjun Das" in node_keys
    assert "PHONE:9876543210" in node_keys
    assert "VEHICLE:KL-11-AB-1234" in node_keys
    print(f"[OK] Graph retrieval for FIR-002 passed: {graph.node_count} nodes, {graph.relationship_count} relationships")


def test_nonexistent_fir():
    """Test 4: Requesting a nonexistent FIR cleanly returns HTTP 404."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/NONEXISTENT-FIR-999")
    assert status == 404, f"Expected 404, got {status}"
    assert "detail" in data
    assert "NONEXISTENT-FIR-999" in data["detail"]
    print(f"[OK] Nonexistent FIR correctly rejected with 404: {data['detail']}")


def test_response_schema():
    """Test 5: Validates strict schema requirements for GraphNode and GraphRelationship."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/FIR-001")
    assert status == 200

    graph = GraphDataResponse.model_validate(data)
    for node in graph.nodes:
        assert isinstance(node.key, str) and len(node.key) > 0, "Node key must be a non-empty string"
        assert isinstance(node.entity_type, str) and len(node.entity_type) > 0, "Entity type must be non-empty"
        assert isinstance(node.display_value, str) and len(node.display_value) > 0, "Display value must be non-empty"
        assert node.canonical_value is not None, "Canonical value should be populated"
        assert isinstance(node.properties, dict), "Properties must be a dict"

    for rel in graph.relationships:
        assert isinstance(rel.id, str) and len(rel.id) > 0, "Relationship ID must be non-empty"
        assert isinstance(rel.source, str) and len(rel.source) > 0, "Relationship source must be non-empty"
        assert isinstance(rel.target, str) and len(rel.target) > 0, "Relationship target must be non-empty"
        assert isinstance(rel.relationship_type, str) and len(rel.relationship_type) > 0, "Type must be non-empty"
        assert rel.fir_id == "FIR-001", "fir_id must match requested FIR"
        assert isinstance(rel.properties, dict), "Properties must be a dict"

    print(f"[OK] Schema validation passed: {len(graph.nodes)} nodes and {len(graph.relationships)} relationships verified against schema")


def test_provenance_fields():
    """Test 6: Validates that provenance fields (page, evidence, confidence) are populated."""
    status, data = http_get(f"{BASE_URL}/api/graph/firs/FIR-001")
    assert status == 200

    graph = GraphDataResponse.model_validate(data)
    entity_rels = [r for r in graph.relationships if r.relationship_type != "CONTAINS"]
    assert len(entity_rels) >= 4, f"Expected at least 4 entity relationships, found {len(entity_rels)}"

    for rel in entity_rels:
        assert rel.fir_id == "FIR-001", f"Expected fir_id 'FIR-001', got '{rel.fir_id}'"
        assert rel.page is not None and rel.page >= 1, f"Missing or invalid page on {rel.relationship_type}: {rel.page}"
        assert rel.evidence is not None and len(rel.evidence.strip()) > 10, f"Missing evidence on {rel.relationship_type}"
        assert rel.confidence is not None and 0.0 <= rel.confidence <= 1.0, f"Invalid confidence on {rel.relationship_type}: {rel.confidence}"
        print(f"  - Verified Provenance: ({rel.source})-[:{rel.relationship_type}]->({rel.target}) | Page {rel.page} | Conf {rel.confidence}")

    print("[OK] All entity relationships have verified provenance fields (fir_id, page, evidence, confidence)")


def test_unit_service_mock():
    """Test 7: Unit tests for Neo4jService query construction and FIRNotFoundError."""
    class MockSession:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def run(self, query, **kwargs):
            class MockResult:
                def single(self):
                    return None
            return MockResult()

    class MockDriver:
        def verify_connectivity(self):
            return True
        def session(self, **kwargs):
            return MockSession()
        def close(self):
            pass

    svc = Neo4jService(uri="bolt://mock:7687", username="neo4j", password="dummy")
    svc._driver = MockDriver()
    from models.schemas import GraphStatusResponse
    svc.check_connection = lambda: GraphStatusResponse(status="connected", uri="bolt://mock:7687", database="neo4j")

    try:
        svc.get_graph_for_fir("UNKNOWN-FIR")
        assert False, "Should raise FIRNotFoundError"
    except FIRNotFoundError as e:
        assert "not found" in str(e)
    print("[OK] Unit test passed: FIRNotFoundError raised correctly on unknown FIR")


def run_phase6a_suite():
    print("========================================")
    print("RUNNING PHASE 6A AUTOMATED TEST SUITE")
    print("========================================")

    print("\n[TEST 1] FIR List Endpoint (/api/graph/firs)...")
    test_fir_list_endpoint()

    print("\n[TEST 2] Graph Retrieval for FIR-001 (/api/graph/firs/FIR-001)...")
    test_graph_retrieval_fir_001()

    print("\n[TEST 3] Graph Retrieval for FIR-002 (/api/graph/firs/FIR-002)...")
    test_graph_retrieval_fir_002()

    print("\n[TEST 4] Nonexistent FIR Handling (404 Not Found)...")
    test_nonexistent_fir()

    print("\n[TEST 5] Response Schema Validation...")
    test_response_schema()

    print("\n[TEST 6] Provenance Fields Verification...")
    test_provenance_fields()

    print("\n[TEST 7] Unit Service Mock Validation...")
    test_unit_service_mock()

    print("\n========================================")
    print("ALL PHASE 6A AUTOMATED TESTS PASSED!")
    print("========================================")


if __name__ == "__main__":
    run_phase6a_suite()
