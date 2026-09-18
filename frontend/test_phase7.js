// test_phase7.js - Automated frontend integration tests for Phase 7: Historical Knowledge Base Lookup
import assert from 'node:assert';

const API_BASE = 'http://127.0.0.1:8000';

async function runPhase7FrontendTests() {
  console.log('========================================');
  console.log('RUNNING PHASE 7 FRONTEND INTEGRATION TESTS');
  console.log('========================================');

  // Test 1: Historical connections for FIR-002
  console.log('\n[TEST 1] Querying Historical Connections for FIR-002...');
  const res2 = await fetch(`${API_BASE}/api/graph/firs/FIR-002/historical-connections`);
  assert.strictEqual(res2.status, 200, 'Expected 200 OK from historical-connections for FIR-002');
  const data2 = await res2.json();
  assert.strictEqual(data2.current_fir_id, 'FIR-002');
  assert.strictEqual(data2.total_matches, 2, `Expected 2 matches for FIR-002, got ${data2.total_matches}`);
  assert.strictEqual(data2.shared_entity_count, 2);

  // Verify matched entities
  const keys2 = data2.matches.map(m => m.entity_key);
  assert(keys2.includes('PHONE:9876543210'), 'Phone 9876543210 must be in historical matches');
  assert(keys2.includes('VEHICLE:KL-11-AB-1234'), 'Vehicle KL-11-AB-1234 must be in historical matches');
  console.log(`[OK] Detected ${data2.total_matches} historical connections for FIR-002: ${keys2.join(', ')}`);

  // Test 2: Historical connections for FIR-001
  console.log('\n[TEST 2] Querying Historical Connections for FIR-001...');
  const res1 = await fetch(`${API_BASE}/api/graph/firs/FIR-001/historical-connections`);
  assert.strictEqual(res1.status, 200);
  const data1 = await res1.json();
  assert.strictEqual(data1.current_fir_id, 'FIR-001');
  assert.strictEqual(data1.total_matches, 2);
  const keys1 = data1.matches.map(m => m.entity_key);
  assert(keys1.includes('PHONE:9876543210'));
  assert(keys1.includes('VEHICLE:KL-11-AB-1234'));
  console.log(`[OK] Detected ${data1.total_matches} historical connections for FIR-001: ${keys1.join(', ')}`);

  // Test 3: Provenance fields verification on historical matches
  console.log('\n[TEST 3] Verifying Provenance Fields on Matches...');
  for (const m of data2.matches) {
    assert.strictEqual(m.historical_fir_id, 'FIR-001', 'Historical FIR must be FIR-001');
    assert.strictEqual(m.historical_filename, 'FIR-001.pdf');
    assert(typeof m.page === 'number' && m.page >= 1, `Page must be a valid number, got ${m.page}`);
    assert(typeof m.evidence === 'string' && m.evidence.length > 10, 'Evidence text must be populated');
    assert(typeof m.confidence === 'number' && m.confidence > 0, 'Confidence must be positive');
    console.log(`  - Match: [${m.entity_type}] ${m.canonical_value} in ${m.historical_fir_id} (Page ${m.page}, Conf ${m.confidence})`);
    console.log(`    Evidence: "${m.evidence.substring(0, 75)}..."`);
  }
  console.log('[OK] All historical matches have valid provenance fields for UI display');

  // Test 4: Exclusion of current FIR from results
  console.log('\n[TEST 4] Verifying Exclusion of Current FIR from Results...');
  for (const m of data2.matches) {
    assert.notStrictEqual(m.historical_fir_id, 'FIR-002', 'Current FIR-002 must not appear in its own historical matches');
  }
  for (const m of data1.matches) {
    assert.notStrictEqual(m.historical_fir_id, 'FIR-001', 'Current FIR-001 must not appear in its own historical matches');
  }
  console.log('[OK] Current FIR is strictly excluded from historical connections');

  // Test 5: Error handling for nonexistent FIR
  console.log('\n[TEST 5] Verifying 404 Error on Nonexistent FIR...');
  const resNone = await fetch(`${API_BASE}/api/graph/firs/NONEXISTENT-999/historical-connections`);
  assert.strictEqual(resNone.status, 404);
  const errNone = await resNone.json();
  assert(errNone.detail && errNone.detail.includes('NONEXISTENT-999'));
  console.log(`[OK] 404 cleanly returned for nonexistent FIR: "${errNone.detail}"`);

  console.log('\n========================================');
  console.log('ALL PHASE 7 FRONTEND TESTS PASSED WITH 100% SUCCESS!');
  console.log('========================================');
}

runPhase7FrontendTests().catch(err => {
  console.error('[FAIL] Test failed:', err);
  process.exit(1);
});
