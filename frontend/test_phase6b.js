// test_phase6b.js - Automated test suite for Phase 6B Cytoscape.js integration
import assert from 'node:assert';
import cytoscape from 'cytoscape';

const API_BASE = 'http://127.0.0.1:8000';

async function runPhase6BTests() {
  console.log('========================================');
  console.log('RUNNING PHASE 6B FRONTEND INTEGRATION TESTS');
  console.log('========================================');

  // Test 1: Verify FIR list endpoint loading
  console.log('\n[TEST 1] Loading FIR List from API...');
  const firListRes = await fetch(`${API_BASE}/api/graph/firs`);
  assert.strictEqual(firListRes.status, 200, 'Expected 200 OK from /api/graph/firs');
  const firListData = await firListRes.json();
  assert(Array.isArray(firListData.firs), 'firs must be an array');
  assert(firListData.total_count >= 2, 'Expected at least 2 FIRs');
  const firIds = firListData.firs.map(f => f.fir_id);
  assert(firIds.includes('FIR-001'), 'FIR-001 must be in list');
  assert(firIds.includes('FIR-002'), 'FIR-002 must be in list');
  console.log(`[OK] FIR List loaded: found ${firListData.total_count} FIRs (${firIds.join(', ')})`);

  // Test 2: Selecting FIR-001 requests the correct endpoint and returns graph data
  console.log('\n[TEST 2] Selecting FIR-001 & Retrieving Graph Data...');
  const fir1Res = await fetch(`${API_BASE}/api/graph/firs/FIR-001`);
  assert.strictEqual(fir1Res.status, 200, 'Expected 200 OK for FIR-001');
  const graph1 = await fir1Res.json();
  assert.strictEqual(graph1.fir_id, 'FIR-001');
  assert(graph1.nodes.length >= 8, `Expected >= 8 nodes, got ${graph1.nodes.length}`);
  assert(graph1.relationships.length >= 11, `Expected >= 11 relationships, got ${graph1.relationships.length}`);
  console.log(`[OK] FIR-001 Graph retrieved: ${graph1.nodes.length} nodes, ${graph1.relationships.length} relationships`);

  // Test 3: Selecting FIR-002 requests the correct endpoint and returns graph data
  console.log('\n[TEST 3] Selecting FIR-002 & Retrieving Graph Data...');
  const fir2Res = await fetch(`${API_BASE}/api/graph/firs/FIR-002`);
  assert.strictEqual(fir2Res.status, 200, 'Expected 200 OK for FIR-002');
  const graph2 = await fir2Res.json();
  assert.strictEqual(graph2.fir_id, 'FIR-002');
  assert(graph2.nodes.length >= 5, `Expected >= 5 nodes, got ${graph2.nodes.length}`);
  assert(graph2.relationships.length >= 7, `Expected >= 7 relationships, got ${graph2.relationships.length}`);
  console.log(`[OK] FIR-002 Graph retrieved: ${graph2.nodes.length} nodes, ${graph2.relationships.length} relationships`);

  // Test 4: API Error handling for nonexistent FIR
  console.log('\n[TEST 4] Handling Nonexistent FIR Request (404)...');
  const nonExistentRes = await fetch(`${API_BASE}/api/graph/firs/NONEXISTENT-999`);
  assert.strictEqual(nonExistentRes.status, 404, 'Expected 404 for nonexistent FIR');
  const errorJson = await nonExistentRes.json();
  assert(errorJson.detail && errorJson.detail.includes('NONEXISTENT-999'));
  console.log(`[OK] Nonexistent FIR cleanly handled with 404: "${errorJson.detail}"`);

  // Test 5: Cytoscape headless element generation & graph rendering
  console.log('\n[TEST 5] Headless Cytoscape Element Construction & Graph Model...');
  const elements = [
    ...graph1.nodes.map(n => ({
      group: 'nodes',
      data: {
        id: n.key,
        label: n.display_value,
        entityType: n.entity_type,
        canonicalValue: n.canonical_value,
        properties: n.properties,
      }
    })),
    ...graph1.relationships.map(r => ({
      group: 'edges',
      data: {
        id: r.id,
        source: r.source,
        target: r.target,
        label: r.relationship_type === 'CONTAINS' ? '' : r.relationship_type,
        relationshipType: r.relationship_type,
        firId: r.fir_id,
        page: r.page,
        evidence: r.evidence,
        confidence: r.confidence,
      }
    }))
  ];

  // Initialize headless Cytoscape instance
  const cy = cytoscape({
    headless: true,
    elements: elements,
  });

  assert.strictEqual(cy.nodes().length, graph1.nodes.length, 'Cytoscape nodes count mismatch');
  assert.strictEqual(cy.edges().length, graph1.relationships.length, 'Cytoscape edges count mismatch');

  // Verify node types present in Cytoscape model
  const personNode = cy.$('node[entityType = "PERSON"]');
  const phoneNode = cy.$('node[entityType = "PHONE"]');
  const vehicleNode = cy.$('node[entityType = "VEHICLE"]');
  const firNode = cy.$('node[entityType = "FIR"]');

  assert(personNode.length > 0, 'Person node must exist in Cytoscape');
  assert(phoneNode.length > 0, 'Phone node must exist in Cytoscape');
  assert(vehicleNode.length > 0, 'Vehicle node must exist in Cytoscape');
  assert(firNode.length > 0, 'FIR node must exist in Cytoscape');
  console.log(`[OK] Cytoscape model verified: ${cy.nodes().length} nodes, ${cy.edges().length} edges`);

  // Test 6: Provenance inspection on entity relationships
  console.log('\n[TEST 6] Relationship Provenance Data Verification...');
  const entityEdges = cy.edges('[relationshipType != "CONTAINS"]');
  assert(entityEdges.length >= 4, 'Expected at least 4 entity edges');

  for (let i = 0; i < entityEdges.length; i++) {
    const edge = entityEdges[i];
    const data = edge.data();
    assert.strictEqual(data.firId, 'FIR-001', 'Provenance firId must match');
    assert(typeof data.page === 'number' && data.page >= 1, `Page number must be >= 1, got ${data.page}`);
    assert(typeof data.evidence === 'string' && data.evidence.length > 10, 'Evidence text must be populated');
    assert(typeof data.confidence === 'number' && data.confidence > 0, 'Confidence must be a positive number');
    console.log(`  - Provenance verified: (${data.source})-[:${data.relationshipType}]->(${data.target})`);
    console.log(`    FIR: ${data.firId}, Page: ${data.page}, Confidence: ${data.confidence}`);
    console.log(`    Evidence: "${data.evidence.substring(0, 75)}..."`);
  }
  console.log('[OK] All entity relationships have valid evidence provenance for UI panel display');

  cy.destroy();

  console.log('\n========================================');
  console.log('ALL PHASE 6B FRONTEND TESTS PASSED WITH 100% SUCCESS!');
  console.log('========================================');
}

runPhase6BTests().catch(err => {
  console.error('[FAIL] Test failed:', err);
  process.exit(1);
});
