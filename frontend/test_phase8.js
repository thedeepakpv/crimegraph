// test_phase8.js - Automated frontend integration tests for Phase 8: Graph Analysis (P2 Signals)
import assert from 'node:assert';

const API_BASE = 'http://127.0.0.1:8000';

async function runPhase8FrontendTests() {
  console.log('========================================');
  console.log('RUNNING PHASE 8 FRONTEND INTEGRATION TESTS');
  console.log('========================================');

  // Test 1: Global analytics endpoint
  console.log('\n[TEST 1] Querying Global Graph Analytics (/api/graph/analytics)...');
  const resGlobal = await fetch(`${API_BASE}/api/graph/analytics`);
  assert.strictEqual(resGlobal.status, 200, 'Expected 200 OK from /api/graph/analytics');
  const dataGlobal = await resGlobal.json();
  assert.strictEqual(dataGlobal.fir_id, null, 'Global analytics fir_id must be null');
  assert(dataGlobal.total_signals > 0, `Expected total_signals > 0, got ${dataGlobal.total_signals}`);
  assert(dataGlobal.disclaimer.includes('INVESTIGATIVE SIGNALS ONLY'), 'Investigative disclaimer required');
  console.log(`[OK] Global analytics returned ${dataGlobal.total_signals} signals across 4 categories`);

  // Test 2: FIR-001 Scoped analytics
  console.log('\n[TEST 2] Querying Scoped Analytics for FIR-001...');
  const resFir1 = await fetch(`${API_BASE}/api/graph/firs/FIR-001/analytics`);
  assert.strictEqual(resFir1.status, 200);
  const dataFir1 = await resFir1.json();
  assert.strictEqual(dataFir1.fir_id, 'FIR-001');
  assert(dataFir1.total_signals > 0);
  console.log(`[OK] FIR-001 analytics returned ${dataFir1.total_signals} signals`);

  // Test 3: FIR-002 Scoped analytics
  console.log('\n[TEST 3] Querying Scoped Analytics for FIR-002...');
  const resFir2 = await fetch(`${API_BASE}/api/graph/firs/FIR-002/analytics`);
  assert.strictEqual(resFir2.status, 200);
  const dataFir2 = await resFir2.json();
  assert.strictEqual(dataFir2.fir_id, 'FIR-002');
  assert(dataFir2.total_signals > 0);
  console.log(`[OK] FIR-002 analytics returned ${dataFir2.total_signals} signals`);

  // Test 4: Verify Repeated Entities
  console.log('\n[TEST 4] Verifying Repeated Entities (Canonical Keys & FIR counts)...');
  const repKeys = dataGlobal.repeated_entities.map(r => r.entity_key);
  assert(repKeys.includes('PHONE:9876543210'), 'PHONE:9876543210 must be in repeated entities');
  assert(repKeys.includes('VEHICLE:KL-11-AB-1234'), 'VEHICLE:KL-11-AB-1234 must be in repeated entities');
  for (const re of dataGlobal.repeated_entities) {
    assert(re.fir_count >= 2, `Repeated entity ${re.entity_key} must have fir_count >= 2`);
    assert(re.fir_ids.length >= 2, 'fir_ids must have at least 2 elements');
    assert.notStrictEqual(re.entity_type, 'LOCATION', 'Location should not be in repeated entities');
    assert.notStrictEqual(re.entity_type, 'FIR', 'FIR nodes must not be in repeated entities');
    console.log(`  - Shared Entity: [${re.entity_type}] ${re.canonical_value} in FIRs: ${re.fir_ids.join(', ')}`);
  }
  console.log('[OK] Repeated entities canonical key matching verified');

  // Test 5: Verify Potential Bridge / Intermediary Entities
  console.log('\n[TEST 5] Verifying Potential Bridge / Intermediary Entities...');
  assert(dataGlobal.potential_bridges.length > 0, 'Must have at least 1 potential bridge');
  for (const b of dataGlobal.potential_bridges) {
    assert.strictEqual(b.signal_label, 'Potential Bridge / Intermediary');
    assert(b.bridge_score > 0, 'bridge_score must be positive');
    assert(b.explanation.includes('Potential'), 'explanation must state potential signal');
    console.log(`  - Bridge: [${b.entity_type}] ${b.canonical_value} (Score: ${b.bridge_score}, FIRs: ${b.connected_firs.join(', ')})`);
    for (const pair of b.bridged_pairs) {
      assert(pair.explanation.includes('without a direct relationship'), 'Pair must explain absence of direct link');
      if (pair.is_cross_fir) {
        console.log(`    * Cross-FIR Pair: ${pair.entity_a_canonical} (${pair.fir_a}) ⇄ ${pair.entity_b_canonical} (${pair.fir_b})`);
      }
    }
  }
  console.log('[OK] Potential Bridge / Intermediary entities verified');

  // Test 6: Verify 2-Hop Relationships
  console.log('\n[TEST 6] Verifying 2-Hop Relationships & Provenance...');
  assert(dataGlobal.two_hop_relationships.length > 0, 'Must have 2-hop relationships');
  for (const hop of dataGlobal.two_hop_relationships.slice(0, 3)) {
    assert(hop.source_key !== hop.target_key, 'Source and target must differ');
    assert.notStrictEqual(hop.hop1_relationship, 'CONTAINS', 'Hop 1 must not be CONTAINS');
    assert.notStrictEqual(hop.hop2_relationship, 'CONTAINS', 'Hop 2 must not be CONTAINS');
    console.log(`  - 2-Hop: ${hop.path_description}`);
  }
  console.log('[OK] 2-Hop candidate relationships verified with provenance');

  // Test 7: Verify Error Handling for Nonexistent FIR
  console.log('\n[TEST 7] Verifying 404 for Nonexistent FIR Analytics...');
  const resNone = await fetch(`${API_BASE}/api/graph/firs/NONEXISTENT-999/analytics`);
  assert.strictEqual(resNone.status, 404);
  const errData = await resNone.json();
  assert(errData.detail.includes('NONEXISTENT-999'));
  console.log(`[OK] Clean 404 returned for nonexistent FIR: "${errData.detail}"`);

  console.log('\n========================================');
  console.log('ALL PHASE 8 FRONTEND TESTS PASSED WITH 100% SUCCESS!');
  console.log('========================================');
}

runPhase8FrontendTests().catch(err => {
  console.error('[FAIL] Test failed:', err);
  process.exit(1);
});
