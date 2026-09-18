import { useState, useEffect, useRef, useCallback } from 'react';
import cytoscape from 'cytoscape';
import { getAvailableFirs, getGraphForFir, getHistoricalConnections, getGraphAnalytics } from '../services/api';

const ENTITY_STYLES = {
  PERSON: { bg: '#3b82f6', border: '#60a5fa', shape: 'ellipse' },
  PHONE: { bg: '#10b981', border: '#34d399', shape: 'ellipse' },
  VEHICLE: { bg: '#f59e0b', border: '#fbbf24', shape: 'round-rectangle' },
  LOCATION: { bg: '#ef4444', border: '#f87171', shape: 'diamond' },
  ORGANIZATION: { bg: '#8b5cf6', border: '#a78bfa', shape: 'hexagon' },
  FIR: { bg: '#334155', border: '#94a3b8', shape: 'round-rectangle' },
  DEFAULT: { bg: '#64748b', border: '#94a3b8', shape: 'ellipse' },
};

export default function GraphVisualization({ activeFirId, onFirChanged }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  const [firs, setFirs] = useState([]);
  const [selectedFir, setSelectedFir] = useState(activeFirId || '');
  const [loadingFirs, setLoadingFirs] = useState(false);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [error, setError] = useState(null);
  const [graphData, setGraphData] = useState(null);

  // Historical Connections state (Phase 7)
  const [historicalData, setHistoricalData] = useState(null);
  const [loadingHistorical, setLoadingHistorical] = useState(false);

  // Graph Analytics state (Phase 8: P2 Signals)
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [analyticsScope, setAnalyticsScope] = useState('fir'); // 'fir' or 'all'
  const [analyticsTab, setAnalyticsTab] = useState('bridges'); // 'bridges', 'connected', 'repeated', 'twohop'

  // Inspector selection state
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedRelationship, setSelectedRelationship] = useState(null);

  // Load list of available FIRs
  const fetchFirs = useCallback(async () => {
    setLoadingFirs(true);
    try {
      const res = await getAvailableFirs();
      setFirs(res.firs || []);
      if (res.firs && res.firs.length > 0 && !selectedFir) {
        setSelectedFir(res.firs[0].fir_id);
      }
    } catch (err) {
      console.warn('Could not load FIR list:', err);
    } finally {
      setLoadingFirs(false);
    }
  }, [selectedFir]);

  useEffect(() => {
    fetchFirs();
  }, [fetchFirs]);

  // Sync if parent passes in a newly ingested FIR
  useEffect(() => {
    if (activeFirId) {
      setSelectedFir(activeFirId);
      fetchFirs();
    }
  }, [activeFirId, fetchFirs]);

  // Load analytics helper
  const loadAnalytics = useCallback(async (firId, scope = 'fir') => {
    setLoadingAnalytics(true);
    try {
      const data = await getGraphAnalytics(scope === 'fir' ? firId : null);
      setAnalyticsData(data);
    } catch (err) {
      console.warn('Could not load graph analytics:', err);
      setAnalyticsData(null);
    } finally {
      setLoadingAnalytics(false);
    }
  }, []);

  // Load graph data, historical connections, and analytics when selected FIR changes
  const loadGraph = useCallback(async (firId) => {
    if (!firId) return;
    setLoadingGraph(true);
    setLoadingHistorical(true);
    setError(null);
    setSelectedNode(null);
    setSelectedRelationship(null);
    try {
      const [data, histData] = await Promise.all([
        getGraphForFir(firId),
        getHistoricalConnections(firId).catch((err) => {
          console.warn('Could not fetch historical connections:', err);
          return { current_fir_id: firId, matches: [], total_matches: 0, shared_entity_count: 0 };
        }),
      ]);
      setGraphData(data);
      setHistoricalData(histData);
      loadAnalytics(firId, analyticsScope);
      if (onFirChanged) onFirChanged(firId);
    } catch (err) {
      setError(err.message || `Failed to load graph for ${firId}`);
      setGraphData(null);
      setHistoricalData(null);
    } finally {
      setLoadingGraph(false);
      setLoadingHistorical(false);
    }
  }, [onFirChanged, loadAnalytics, analyticsScope]);

  useEffect(() => {
    if (selectedFir) {
      loadGraph(selectedFir);
    }
  }, [selectedFir, loadGraph]);

  // Initialize and update Cytoscape instance
  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    // Build Cytoscape elements
    const elements = [];

    // Nodes
    (graphData.nodes || []).forEach((node) => {
      const style = ENTITY_STYLES[node.entity_type] || ENTITY_STYLES.DEFAULT;
      elements.push({
        group: 'nodes',
        data: {
          id: node.key,
          label: node.display_value || node.key,
          entityType: node.entity_type,
          canonicalValue: node.canonical_value,
          properties: node.properties || {},
          bgColor: style.bg,
          borderColor: style.border,
          shape: style.shape,
        },
      });
    });

    // Relationships / Edges
    (graphData.relationships || []).forEach((rel) => {
      const isContains = rel.relationship_type === 'CONTAINS';
      elements.push({
        group: 'edges',
        data: {
          id: rel.id,
          source: rel.source,
          target: rel.target,
          label: isContains ? '' : rel.relationship_type,
          relationshipType: rel.relationship_type,
          firId: rel.fir_id,
          page: rel.page,
          evidence: rel.evidence,
          confidence: rel.confidence,
          properties: rel.properties || {},
          isContains: isContains,
        },
      });
    });

    // Destroy existing cy instance if any
    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    // Create fresh instance
    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      boxSelectionEnabled: false,
      autounselectify: false,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(bgColor)',
            'border-color': 'data(borderColor)',
            'border-width': 2,
            'label': 'data(label)',
            'color': '#f8fafc',
            'font-size': '11px',
            'font-weight': '600',
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '90px',
            'shape': 'data(shape)',
            'width': '52px',
            'height': '45px',
            'transition-property': 'background-color, border-color, border-width',
            'transition-duration': '0.15s',
          },
        },
        {
          selector: 'node[entityType = "FIR"]',
          style: {
            'width': '75px',
            'height': '36px',
            'font-size': '12px',
            'border-width': 2,
            'background-color': '#1e293b',
            'border-color': '#94a3b8',
          },
        },
        {
          selector: 'node[entityType = "VEHICLE"]',
          style: {
            'width': '70px',
            'height': '38px',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#ffffff',
            'border-width': 3,
            'underlay-color': '#38bdf8',
            'underlay-padding': '4px',
            'underlay-opacity': 0.5,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#64748b',
            'target-arrow-color': '#64748b',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'color': '#cbd5e1',
            'font-size': '10px',
            'font-weight': '500',
            'text-background-opacity': 0.85,
            'text-background-color': '#0f172a',
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'arrow-scale': 1.1,
          },
        },
        {
          selector: 'edge[isContains]',
          style: {
            'line-style': 'dashed',
            'line-color': '#475569',
            'target-arrow-color': '#475569',
            'width': 1.5,
            'opacity': 0.6,
          },
        },
        {
          selector: 'edge:selected',
          style: {
            'width': 4,
            'line-color': '#38bdf8',
            'target-arrow-color': '#38bdf8',
            'color': '#38bdf8',
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: false,
        padding: 40,
        nodeRepulsion: () => 6000,
        idealEdgeLength: () => 90,
        edgeElasticity: () => 100,
      },
    });

    // Event listeners
    cy.on('tap', 'node', (evt) => {
      const nodeData = evt.target.data();
      setSelectedNode(nodeData);
      setSelectedRelationship(null);
    });

    cy.on('tap', 'edge', (evt) => {
      const edgeData = evt.target.data();
      setSelectedRelationship(edgeData);
      setSelectedNode(null);
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null);
        setSelectedRelationship(null);
      }
    });

    cyRef.current = cy;

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [graphData]);

  // Toolbar control handlers
  const handleZoomIn = () => {
    if (cyRef.current) {
      cyRef.current.zoom({
        level: cyRef.current.zoom() * 1.25,
        renderedPosition: { x: cyRef.current.width() / 2, y: cyRef.current.height() / 2 },
      });
    }
  };

  const handleZoomOut = () => {
    if (cyRef.current) {
      cyRef.current.zoom({
        level: cyRef.current.zoom() * 0.8,
        renderedPosition: { x: cyRef.current.width() / 2, y: cyRef.current.height() / 2 },
      });
    }
  };

  const handleFit = () => {
    if (cyRef.current) {
      cyRef.current.fit(undefined, 30);
    }
  };

  const handleFocusNode = (entityKey) => {
    if (!cyRef.current) return;
    const node = cyRef.current.getElementById(entityKey);
    if (node && node.length > 0) {
      cyRef.current.nodes().unselect();
      cyRef.current.edges().unselect();
      node.select();
      cyRef.current.animate(
        {
          center: { eles: node },
          zoom: 1.6,
        },
        { duration: 350 }
      );
      setSelectedNode(node.data());
      setSelectedRelationship(null);
      if (containerRef.current) {
        containerRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  };

  const handleFocusPath = (keys) => {
    if (!cyRef.current) return;
    cyRef.current.nodes().unselect();
    cyRef.current.edges().unselect();
    const targets = keys.map((k) => cyRef.current.getElementById(k)).filter((el) => el && el.length > 0);
    if (targets.length > 0) {
      let collection = cyRef.current.collection();
      targets.forEach((t) => {
        collection = collection.union(t);
        t.select();
      });
      cyRef.current.animate(
        {
          center: { eles: collection },
          zoom: 1.3,
        },
        { duration: 350 }
      );
      if (targets.length === 1) {
        setSelectedNode(targets[0].data());
        setSelectedRelationship(null);
      }
      if (containerRef.current) {
        containerRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  };


  return (
    <section className="card graph-viz-card" style={{ marginTop: '1.5rem' }}>
      <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1.1rem', fontWeight: 600 }}>Investigation Knowledge Graph</span>
          <span className="badge" style={{ backgroundColor: '#0284c7', color: '#fff', fontSize: '0.75rem' }}>Phase 6: Cytoscape.js</span>
        </div>

        {/* FIR Selection & Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <label htmlFor="fir-select" style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Select FIR:</label>
          <select
            id="fir-select"
            value={selectedFir}
            onChange={(e) => setSelectedFir(e.target.value)}
            disabled={loadingFirs || loadingGraph}
            style={{
              padding: '0.4rem 0.8rem',
              backgroundColor: '#1e293b',
              color: '#f8fafc',
              border: '1px solid #475569',
              borderRadius: '6px',
              fontSize: '0.85rem',
              outline: 'none',
              cursor: 'pointer',
            }}
          >
            {firs.length === 0 && <option value="">No FIRs in database</option>}
            {firs.map((f) => (
              <option key={f.fir_id} value={f.fir_id}>
                {f.fir_id} {f.filename ? `(${f.filename})` : ''} — {f.entity_count || 0} entities
              </option>
            ))}
          </select>

          <button
            onClick={() => { fetchFirs(); loadGraph(selectedFir); }}
            disabled={loadingGraph}
            className="btn btn-secondary"
            style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
            title="Reload available FIRs and re-render current graph"
          >
            {loadingGraph ? 'Loading...' : 'Reload Graph'}
          </button>
        </div>
      </div>

      {/* Graph Toolbar & Legend */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', padding: '0.5rem 0', borderBottom: '1px solid #1e293b', marginBottom: '0.75rem' }}>
        {/* Entity Legend */}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center', fontSize: '0.75rem', color: '#94a3b8' }}>
          <span style={{ fontWeight: 600, color: '#e2e8f0' }}>Legend:</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: ENTITY_STYLES.PERSON.bg }} /> Person
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: ENTITY_STYLES.PHONE.bg }} /> Phone
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: 10, height: 8, borderRadius: '2px', backgroundColor: ENTITY_STYLES.VEHICLE.bg }} /> Vehicle
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: 9, height: 9, transform: 'rotate(45deg)', backgroundColor: ENTITY_STYLES.LOCATION.bg }} /> Location
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: 10, height: 7, borderRadius: '2px', backgroundColor: ENTITY_STYLES.FIR.bg, border: '1px solid #94a3b8' }} /> FIR Root
          </span>
        </div>

        {/* Zoom & Fit Controls */}
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          <button onClick={handleZoomIn} className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}>+ Zoom</button>
          <button onClick={handleZoomOut} className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}>- Zoom</button>
          <button onClick={handleFit} className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}>Fit View</button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div style={{ padding: '1rem', backgroundColor: '#450a0a', border: '1px solid #ef4444', borderRadius: '6px', color: '#fca5a5', marginBottom: '1rem', fontSize: '0.85rem' }}>
          <strong>Graph Error:</strong> {error}
        </div>
      )}

      {/* Main Canvas & Inspector Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 320px', gap: '1rem', minHeight: '480px' }}>
        {/* Cytoscape Canvas Container */}
        <div style={{ position: 'relative', backgroundColor: '#090d16', border: '1px solid #1e293b', borderRadius: '8px', overflow: 'hidden' }}>
          {loadingGraph && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(9, 13, 22, 0.75)', zIndex: 10, color: '#38bdf8' }}>
              <span>Loading graph data for {selectedFir}...</span>
            </div>
          )}

          {!loadingGraph && graphData && graphData.nodes.length === 0 && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
              <p>No nodes found for FIR {selectedFir}.</p>
              <p style={{ fontSize: '0.8rem' }}>Please ingest this FIR using the pipeline above.</p>
            </div>
          )}

          <div
            ref={containerRef}
            id="cy-container"
            style={{ width: '100%', height: '500px' }}
          />
        </div>

        {/* Evidence & Provenance Inspector Panel */}
        <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <h4 style={{ margin: 0, fontSize: '0.95rem', color: '#e2e8f0', borderBottom: '1px solid #1e293b', paddingBottom: '0.5rem' }}>
            Evidence &amp; Provenance Panel
          </h4>

          {/* Relationship Selection Details */}
          {selectedRelationship && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="badge" style={{ backgroundColor: '#0284c7', color: '#fff', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  {selectedRelationship.relationshipType}
                </span>
                {selectedRelationship.confidence !== null && (
                  <span className="badge" style={{ backgroundColor: '#065f46', color: '#a7f3d0' }}>
                    {Math.round(selectedRelationship.confidence * 100)}% Confidence
                  </span>
                )}
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Source → Target</div>
                <div style={{ fontWeight: 600, color: '#f8fafc', marginTop: '2px' }}>
                  {selectedRelationship.source}
                </div>
                <div style={{ color: '#38bdf8', fontSize: '0.8rem' }}>↓ {selectedRelationship.relationshipType}</div>
                <div style={{ fontWeight: 600, color: '#f8fafc' }}>
                  {selectedRelationship.target}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', backgroundColor: '#1e293b', padding: '0.5rem', borderRadius: '6px' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>FIR ID</div>
                  <div style={{ fontWeight: 600, color: '#f8fafc' }}>{selectedRelationship.firId}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Page</div>
                  <div style={{ fontWeight: 600, color: '#f8fafc' }}>{selectedRelationship.page !== null ? `Page ${selectedRelationship.page}` : 'N/A'}</div>
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '4px' }}>Extracted Evidence Text:</div>
                <div style={{
                  padding: '0.6rem',
                  backgroundColor: '#1e293b',
                  borderLeft: '3px solid #38bdf8',
                  borderRadius: '4px',
                  color: '#e2e8f0',
                  fontSize: '0.8rem',
                  lineHeight: '1.4',
                  fontStyle: 'italic',
                }}>
                  &ldquo;{selectedRelationship.evidence || 'No explicit evidence string recorded.'}&rdquo;
                </div>
              </div>

              <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                <span style={{ color: '#f59e0b' }}>⚠️ Investigative Lead:</span> Requires human investigator verification before legal conclusion.
              </div>
            </div>
          )}

          {/* Node Selection Details */}
          {selectedNode && !selectedRelationship && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="badge" style={{ backgroundColor: selectedNode.bgColor || '#3b82f6', color: '#fff' }}>
                  {selectedNode.entityType}
                </span>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Canonical Entity</span>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Display Value</div>
                <div style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc' }}>
                  {selectedNode.label}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Canonical / Normalized Key</div>
                <div style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#38bdf8', wordBreak: 'break-all' }}>
                  {selectedNode.id}
                </div>
              </div>

              {selectedNode.canonicalValue && selectedNode.canonicalValue !== selectedNode.label && (
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Canonical Value</div>
                  <div style={{ color: '#e2e8f0' }}>{selectedNode.canonicalValue}</div>
                </div>
              )}

              {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '4px' }}>Properties</div>
                  <div style={{ backgroundColor: '#1e293b', padding: '0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>
                    {Object.entries(selectedNode.properties).map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', margin: '2px 0' }}>
                        <span style={{ color: '#94a3b8' }}>{k}:</span>
                        <span style={{ color: '#f8fafc' }}>{String(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Idle Prompt */}
          {!selectedNode && !selectedRelationship && (
            <div style={{ color: '#64748b', fontSize: '0.8rem', textAlign: 'center', marginTop: '2rem' }}>
              <p>🔍 Click on any node or relationship in the graph to view canonical details and extracted evidence provenance.</p>
            </div>
          )}
        </div>
      </div>

      {/* Historical Knowledge Base Connections (Phase 7: P1 Feature) */}
      <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid #1e293b' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
              Historical Knowledge Base Connections
            </span>
            <span className="badge" style={{ backgroundColor: '#854d0e', color: '#fef08a', fontSize: '0.75rem' }}>
              Phase 7: P1 Historical Lookup
            </span>
          </div>

          <div>
            {loadingHistorical ? (
              <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Checking historical FIRs...</span>
            ) : historicalData && historicalData.total_matches > 0 ? (
              <span className="badge" style={{ backgroundColor: '#065f46', color: '#a7f3d0' }}>
                {historicalData.total_matches} Candidate {historicalData.total_matches === 1 ? 'Connection' : 'Connections'} Detected
              </span>
            ) : (
              <span className="badge" style={{ backgroundColor: '#334155', color: '#94a3b8' }}>
                0 Historical Connections
              </span>
            )}
          </div>
        </div>

        {/* Warning / Investigative lead notice */}
        <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '0 0 0.75rem 0' }}>
          <span style={{ color: '#fbbf24', fontWeight: 600 }}>Investigative Lead Only:</span> Identifies canonical entities in {selectedFir} that previously appeared in other historical FIR records in the knowledge base. Requires human verification; does not prove identity, association, or criminal guilt.
        </p>

        {loadingHistorical ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
            Searching Neo4j historical knowledge base...
          </div>
        ) : historicalData && historicalData.matches.length > 0 ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '0.75rem' }}>
            {historicalData.matches.map((match, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: '#090d16',
                  border: '1px solid #1e293b',
                  borderLeft: `4px solid ${ENTITY_STYLES[match.entity_type]?.bg || '#f59e0b'}`,
                  borderRadius: '6px',
                  padding: '0.85rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.5rem',
                  fontSize: '0.85rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span
                      className="badge"
                      style={{
                        backgroundColor: ENTITY_STYLES[match.entity_type]?.bg || '#64748b',
                        color: '#fff',
                        fontSize: '0.7rem',
                      }}
                    >
                      {match.entity_type}
                    </span>
                    <span style={{ fontWeight: 600, color: '#f8fafc' }}>{match.canonical_value}</span>
                  </div>

                  <button
                    onClick={() => handleFocusNode(match.entity_key)}
                    className="btn btn-secondary"
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                    title="Focus entity node in graph"
                  >
                    Focus in Graph
                  </button>
                </div>

                <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                  Previously observed in: <strong style={{ color: '#38bdf8' }}>{match.historical_fir_id}</strong>
                  {match.historical_filename ? ` (${match.historical_filename})` : ''}
                  {match.page ? ` • Page ${match.page}` : ''}
                  {match.historical_relationship ? ` • Context: ${match.historical_relationship}` : ''}
                </div>

                {match.evidence && (
                  <div
                    style={{
                      padding: '0.5rem 0.65rem',
                      backgroundColor: '#1e293b',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      color: '#cbd5e1',
                      fontStyle: 'italic',
                      lineHeight: '1.4',
                    }}
                  >
                    &ldquo;{match.evidence}&rdquo;
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ padding: '0.85rem 1rem', backgroundColor: '#090d16', border: '1px solid #1e293b', borderRadius: '6px', color: '#94a3b8', fontSize: '0.85rem', lineHeight: '1.5' }}>
            No candidate historical connections detected for canonical entities in <strong>{selectedFir}</strong>.
            <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '0.35rem' }}>
              💡 <em>Demo Tip:</em> Ingest another FIR that shares entities (e.g. <strong>FIR-002</strong> which shares mobile <code>9876543210</code> and vehicle <code>KL-11-AB-1234</code> with <strong>FIR-001</strong>) to observe cross-FIR correlation and provenance.
            </div>
          </div>
        )}
      </div>

      {/* ================================================================ */}
      {/* Graph Analytics (Phase 8: P2 Signals)                            */}
      {/* ================================================================ */}
      <div style={{ marginTop: '1.5rem', paddingTop: '1.25rem', borderTop: '1px solid #1e293b' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc' }}>
              Graph Analytics
            </span>
            <span className="badge" style={{ backgroundColor: '#4338ca', color: '#e0e7ff', fontSize: '0.75rem' }}>
              Phase 8: P2 Signals
            </span>
            {analyticsData && (
              <span className="badge" style={{ backgroundColor: '#1e293b', color: '#38bdf8', fontSize: '0.75rem', border: '1px solid #334155' }}>
                {analyticsData.total_signals} Signals Detected
              </span>
            )}
          </div>

          {/* Analytics Scope Toggle: Selected FIR vs Entire Case */}
          <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8', marginRight: '0.25rem' }}>Scope:</span>
            <button
              onClick={() => {
                setAnalyticsScope('fir');
                loadAnalytics(selectedFir, 'fir');
              }}
              className="btn btn-secondary"
              style={{
                padding: '0.25rem 0.6rem',
                fontSize: '0.75rem',
                backgroundColor: analyticsScope === 'fir' ? '#0284c7' : '#1e293b',
                color: analyticsScope === 'fir' ? '#fff' : '#94a3b8',
                borderColor: analyticsScope === 'fir' ? '#38bdf8' : '#334155',
              }}
            >
              Current FIR ({selectedFir || 'N/A'})
            </button>
            <button
              onClick={() => {
                setAnalyticsScope('all');
                loadAnalytics(selectedFir, 'all');
              }}
              className="btn btn-secondary"
              style={{
                padding: '0.25rem 0.6rem',
                fontSize: '0.75rem',
                backgroundColor: analyticsScope === 'all' ? '#0284c7' : '#1e293b',
                color: analyticsScope === 'all' ? '#fff' : '#94a3b8',
                borderColor: analyticsScope === 'all' ? '#38bdf8' : '#334155',
              }}
            >
              Entire Knowledge Base (All FIRs)
            </button>
          </div>
        </div>

        {/* Prominent Investigative Disclaimer Banner */}
        <div style={{
          backgroundColor: '#1e1b4b',
          border: '1px solid #4338ca',
          borderRadius: '6px',
          padding: '0.65rem 0.85rem',
          marginBottom: '1rem',
          display: 'flex',
          gap: '0.5rem',
          alignItems: 'flex-start',
          fontSize: '0.78rem',
          color: '#c7d2fe',
          lineHeight: '1.45',
        }}>
          <span style={{ fontSize: '1rem' }}>🛡️</span>
          <div>
            <strong style={{ color: '#e0e7ff' }}>Investigative Signals Only:</strong> Structural graph metrics (connectivity degree, repeated normalized attributes, 2-hop linkage paths, and potential connecting entities) provide objective exploratory leads. They do <em>NOT</em> infer guilt, identity, criminality, or proven criminal association. All findings require human investigator verification against source FIR documents.
          </div>
        </div>

        {/* Signal Category Navigation Tabs */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', borderBottom: '1px solid #1e293b', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
          <button
            onClick={() => setAnalyticsTab('bridges')}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: '6px',
              border: analyticsTab === 'bridges' ? '1px solid #38bdf8' : '1px solid #334155',
              backgroundColor: analyticsTab === 'bridges' ? '#0f172a' : 'transparent',
              color: analyticsTab === 'bridges' ? '#38bdf8' : '#94a3b8',
              fontSize: '0.8rem',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Potential Bridges / Intermediaries ({analyticsData?.potential_bridges?.length || 0})
          </button>

          <button
            onClick={() => setAnalyticsTab('connected')}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: '6px',
              border: analyticsTab === 'connected' ? '1px solid #38bdf8' : '1px solid #334155',
              backgroundColor: analyticsTab === 'connected' ? '#0f172a' : 'transparent',
              color: analyticsTab === 'connected' ? '#38bdf8' : '#94a3b8',
              fontSize: '0.8rem',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Highly Connected Entities ({analyticsData?.highly_connected_entities?.length || 0})
          </button>

          <button
            onClick={() => setAnalyticsTab('repeated')}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: '6px',
              border: analyticsTab === 'repeated' ? '1px solid #38bdf8' : '1px solid #334155',
              backgroundColor: analyticsTab === 'repeated' ? '#0f172a' : 'transparent',
              color: analyticsTab === 'repeated' ? '#38bdf8' : '#94a3b8',
              fontSize: '0.8rem',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Repeated Entities ({analyticsData?.repeated_entities?.length || 0})
          </button>

          <button
            onClick={() => setAnalyticsTab('twohop')}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: '6px',
              border: analyticsTab === 'twohop' ? '1px solid #38bdf8' : '1px solid #334155',
              backgroundColor: analyticsTab === 'twohop' ? '#0f172a' : 'transparent',
              color: analyticsTab === 'twohop' ? '#38bdf8' : '#94a3b8',
              fontSize: '0.8rem',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            2-Hop Relationships ({analyticsData?.two_hop_relationships?.length || 0})
          </button>
        </div>

        {/* Content Display by Tab */}
        {loadingAnalytics ? (
          <div style={{ padding: '1.5rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
            Computing graph analytics signals...
          </div>
        ) : !analyticsData ? (
          <div style={{ padding: '1rem', color: '#64748b', fontSize: '0.85rem' }}>
            No analytics data available.
          </div>
        ) : (
          <div>
            {/* Tab 1: Potential Bridge / Intermediary Entities */}
            {analyticsTab === 'bridges' && (
              <div>
                <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '0.75rem' }}>
                  Identifies canonical entities that structurally connect pairs of entities or separate FIR clusters with no recorded direct domain relationship between the endpoints.
                </p>
                {analyticsData.potential_bridges.length === 0 ? (
                  <div style={{ padding: '1rem', backgroundColor: '#090d16', border: '1px solid #1e293b', borderRadius: '6px', color: '#94a3b8', fontSize: '0.85rem' }}>
                    No potential bridge / intermediary entities detected in this scope.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {analyticsData.potential_bridges.map((bridge) => (
                      <div
                        key={bridge.entity_key}
                        style={{
                          backgroundColor: '#090d16',
                          border: '1px solid #1e293b',
                          borderLeft: `4px solid ${ENTITY_STYLES[bridge.entity_type]?.bg || '#8b5cf6'}`,
                          borderRadius: '6px',
                          padding: '0.85rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.6rem',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span className="badge" style={{ backgroundColor: ENTITY_STYLES[bridge.entity_type]?.bg || '#64748b', color: '#fff', fontSize: '0.7rem' }}>
                              {bridge.entity_type}
                            </span>
                            <span style={{ fontWeight: 600, color: '#f8fafc', fontSize: '0.95rem' }}>
                              {bridge.canonical_value}
                            </span>
                            <span className="badge" style={{ backgroundColor: '#7c3aed', color: '#f5f3ff', fontSize: '0.7rem' }}>
                              {bridge.signal_label}
                            </span>
                            <span className="badge" style={{ backgroundColor: '#1e293b', color: '#a78bfa', fontSize: '0.7rem' }}>
                              {bridge.bridge_score} Bridged Pair{bridge.bridge_score === 1 ? '' : 's'}
                            </span>
                          </div>

                          <button
                            onClick={() => handleFocusNode(bridge.entity_key)}
                            className="btn btn-secondary"
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                            title="Center and select bridge node in graph"
                          >
                            Focus in Graph
                          </button>
                        </div>

                        <div style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>
                          {bridge.explanation}
                        </div>

                        {/* Bridged Pairs Breakdown */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginTop: '0.25rem' }}>
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8' }}>
                            Bridged Endpoint Pairs:
                          </span>
                          {bridge.bridged_pairs.map((pair, pIdx) => (
                            <div
                              key={pIdx}
                              style={{
                                backgroundColor: '#1e293b',
                                borderRadius: '4px',
                                padding: '0.5rem 0.65rem',
                                fontSize: '0.78rem',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '0.35rem',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.35rem' }}>
                                <div>
                                  <span style={{ color: '#38bdf8', fontWeight: 600 }}>{pair.entity_a_canonical}</span>
                                  <span style={{ color: '#94a3b8' }}> ({pair.entity_a_type})</span>
                                  <span style={{ color: '#f59e0b', margin: '0 0.35rem' }}>⇄ [{bridge.canonical_value}] ⇄</span>
                                  <span style={{ color: '#38bdf8', fontWeight: 600 }}>{pair.entity_b_canonical}</span>
                                  <span style={{ color: '#94a3b8' }}> ({pair.entity_b_type})</span>
                                </div>
                                {pair.is_cross_fir && (
                                  <span className="badge" style={{ backgroundColor: '#065f46', color: '#a7f3d0', fontSize: '0.68rem' }}>
                                    Cross-FIR ({pair.fir_a} ↔ {pair.fir_b})
                                  </span>
                                )}
                              </div>
                              <div style={{ color: '#94a3b8', fontSize: '0.73rem' }}>
                                {pair.explanation}
                              </div>
                              {pair.hop_a_provenance?.evidence && (
                                <div style={{ fontSize: '0.72rem', color: '#94a3b8', fontStyle: 'italic', borderLeft: '2px solid #38bdf8', paddingLeft: '0.4rem' }}>
                                  Evidence ({pair.hop_a_provenance.fir_id}): &ldquo;{pair.hop_a_provenance.evidence}&rdquo;
                                </div>
                              )}
                              {pair.hop_b_provenance?.evidence && (
                                <div style={{ fontSize: '0.72rem', color: '#94a3b8', fontStyle: 'italic', borderLeft: '2px solid #a78bfa', paddingLeft: '0.4rem' }}>
                                  Evidence ({pair.hop_b_provenance.fir_id}): &ldquo;{pair.hop_b_provenance.evidence}&rdquo;
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Highly Connected Entities */}
            {analyticsTab === 'connected' && (
              <div>
                <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '0.75rem' }}>
                  Ranks canonical entities by total non-provenance degree (excluding FIR root nodes and CONTAINS edges).
                </p>
                {analyticsData.highly_connected_entities.length === 0 ? (
                  <div style={{ padding: '1rem', backgroundColor: '#090d16', border: '1px solid #1e293b', borderRadius: '6px', color: '#94a3b8', fontSize: '0.85rem' }}>
                    No connected domain entities found in this scope.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '0.75rem' }}>
                    {analyticsData.highly_connected_entities.map((hce) => (
                      <div
                        key={hce.entity_key}
                        style={{
                          backgroundColor: '#090d16',
                          border: '1px solid #1e293b',
                          borderLeft: `4px solid ${ENTITY_STYLES[hce.entity_type]?.bg || '#3b82f6'}`,
                          borderRadius: '6px',
                          padding: '0.85rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.5rem',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span className="badge" style={{ backgroundColor: ENTITY_STYLES[hce.entity_type]?.bg || '#64748b', color: '#fff', fontSize: '0.7rem' }}>
                              {hce.entity_type}
                            </span>
                            <span style={{ fontWeight: 600, color: '#f8fafc' }}>{hce.canonical_value}</span>
                          </div>
                          <button
                            onClick={() => handleFocusNode(hce.entity_key)}
                            className="btn btn-secondary"
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                          >
                            Focus in Graph
                          </button>
                        </div>

                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.78rem' }}>
                          <span className="badge" style={{ backgroundColor: '#0284c7', color: '#fff' }}>
                            Degree: {hce.degree}
                          </span>
                          <span style={{ color: '#94a3b8' }}>
                            In: <strong>{hce.in_degree}</strong> • Out: <strong>{hce.out_degree}</strong>
                          </span>
                        </div>

                        <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                          <strong>Connected Entities ({hce.connected_entities.length}):</strong>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginTop: '0.25rem' }}>
                            {hce.connected_entities.map((ce, ceIdx) => (
                              <div key={ceIdx} style={{ backgroundColor: '#1e293b', padding: '0.25rem 0.5rem', borderRadius: '4px', display: 'flex', justifyContent: 'space-between' }}>
                                <span style={{ color: '#e2e8f0' }}>{ce.relationship_type} → {ce.canonical_value}</span>
                                <span style={{ color: '#64748b' }}>({ce.fir_id})</span>
                              </div>
                            ))}
                          </div>
                        </div>

                        {hce.provenance.length > 0 && hce.provenance[0].evidence && (
                          <div style={{ fontSize: '0.72rem', color: '#94a3b8', fontStyle: 'italic', backgroundColor: '#1e293b', padding: '0.4rem 0.5rem', borderRadius: '4px' }}>
                            Supporting quote ({hce.provenance[0].fir_id}): &ldquo;{hce.provenance[0].evidence}&rdquo;
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: Repeated Entities */}
            {analyticsTab === 'repeated' && (
              <div>
                <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '0.75rem' }}>
                  Canonical normalized entities (excluding Location and FIR) observed across multiple distinct FIR documents.
                </p>
                {analyticsData.repeated_entities.length === 0 ? (
                  <div style={{ padding: '1rem', backgroundColor: '#090d16', border: '1px solid #1e293b', borderRadius: '6px', color: '#94a3b8', fontSize: '0.85rem' }}>
                    No repeated cross-FIR entities detected in this scope.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '0.75rem' }}>
                    {analyticsData.repeated_entities.map((rep) => (
                      <div
                        key={rep.entity_key}
                        style={{
                          backgroundColor: '#090d16',
                          border: '1px solid #1e293b',
                          borderLeft: `4px solid ${ENTITY_STYLES[rep.entity_type]?.bg || '#10b981'}`,
                          borderRadius: '6px',
                          padding: '0.85rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.5rem',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span className="badge" style={{ backgroundColor: ENTITY_STYLES[rep.entity_type]?.bg || '#64748b', color: '#fff', fontSize: '0.7rem' }}>
                              {rep.entity_type}
                            </span>
                            <span style={{ fontWeight: 600, color: '#f8fafc' }}>{rep.canonical_value}</span>
                          </div>
                          <button
                            onClick={() => handleFocusNode(rep.entity_key)}
                            className="btn btn-secondary"
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                          >
                            Focus in Graph
                          </button>
                        </div>

                        <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                          Observed across <strong style={{ color: '#38bdf8' }}>{rep.fir_count} FIRs:</strong> {rep.fir_ids.join(', ')}
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '0.25rem' }}>
                          {rep.occurrences.map((occ, oIdx) => (
                            <div key={oIdx} style={{ backgroundColor: '#1e293b', padding: '0.4rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#e2e8f0' }}>
                                <strong>{occ.fir_id}</strong>
                                {occ.relationship_type && <span style={{ color: '#38bdf8' }}>{occ.relationship_type}</span>}
                              </div>
                              {occ.evidence && (
                                <div style={{ color: '#94a3b8', fontStyle: 'italic', marginTop: '2px', fontSize: '0.72rem' }}>
                                  &ldquo;{occ.evidence}&rdquo;
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tab 4: 2-Hop Relationships */}
            {analyticsTab === 'twohop' && (
              <div>
                <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '0.75rem' }}>
                  Candidate indirect relationships connecting two entities through an intermediate node with supporting evidence for both hops.
                </p>
                {analyticsData.two_hop_relationships.length === 0 ? (
                  <div style={{ padding: '1rem', backgroundColor: '#090d16', border: '1px solid #1e293b', borderRadius: '6px', color: '#94a3b8', fontSize: '0.85rem' }}>
                    No 2-hop relationships found in this scope.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                    {analyticsData.two_hop_relationships.map((path, pIdx) => (
                      <div
                        key={pIdx}
                        style={{
                          backgroundColor: '#090d16',
                          border: '1px solid #1e293b',
                          borderRadius: '6px',
                          padding: '0.75rem 0.85rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.45rem',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                          <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f8fafc' }}>
                            {path.path_description}
                          </div>
                          <button
                            onClick={() => handleFocusPath([path.source_key, path.intermediary_key, path.target_key])}
                            className="btn btn-secondary"
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                          >
                            Focus Path
                          </button>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.5rem' }}>
                          {path.hop1_provenance?.evidence && (
                            <div style={{ backgroundColor: '#1e293b', padding: '0.4rem 0.5rem', borderRadius: '4px', fontSize: '0.72rem', color: '#cbd5e1', borderLeft: '2px solid #38bdf8' }}>
                              <strong>Hop 1 ({path.hop1_provenance.fir_id}, Page {path.hop1_provenance.page || 'N/A'}):</strong> &ldquo;{path.hop1_provenance.evidence}&rdquo;
                            </div>
                          )}
                          {path.hop2_provenance?.evidence && (
                            <div style={{ backgroundColor: '#1e293b', padding: '0.4rem 0.5rem', borderRadius: '4px', fontSize: '0.72rem', color: '#cbd5e1', borderLeft: '2px solid #a78bfa' }}>
                              <strong>Hop 2 ({path.hop2_provenance.fir_id}, Page {path.hop2_provenance.page || 'N/A'}):</strong> &ldquo;{path.hop2_provenance.evidence}&rdquo;
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

