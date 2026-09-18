import { useState, useEffect } from 'react';
import {
  checkHealth,
  extractDocumentText,
  extractEntitiesAndRelationships,
  getExtractionStatus,
  getGraphStatus,
  ingestIntoGraph
} from './services/api';
import GraphVisualization from './components/GraphVisualization';
import './App.css';

function App() {
  // Connectivity state
  const [healthStatus, setHealthStatus] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState(null);
  const [lastChecked, setLastChecked] = useState(null);
  const [graphStatus, setGraphStatus] = useState({ status: 'unavailable', message: 'Checking...' });

  // Graph Visualization state (Phase 6B)
  const [activeGraphFirId, setActiveGraphFirId] = useState('FIR-001');

  // Document extraction state (Phase 2)
  const [selectedFile, setSelectedFile] = useState(null);
  const [extractingPdf, setExtractingPdf] = useState(false);
  const [pdfResult, setPdfResult] = useState(null);
  const [pdfError, setPdfError] = useState(null);
  const [activePageTab, setActivePageTab] = useState('combined');

  // AI / Demo Structured Extraction state (Phase 3 & 4)
  const [modeStatus, setModeStatus] = useState({ default_mode: 'demo', ai_available: false });
  const [selectedMode, setSelectedMode] = useState('demo');
  const [extractingEntities, setExtractingEntities] = useState(false);
  const [structuredData, setStructuredData] = useState(null);
  const [extractionError, setExtractionError] = useState(null);

  // Graph Ingestion state (Phase 5)
  const [ingesting, setIngesting] = useState(false);
  const [ingestionResult, setIngestionResult] = useState(null);
  const [ingestionError, setIngestionError] = useState(null);


  const fetchHealth = async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const data = await checkHealth();
      setHealthStatus(data);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (err) {
      setHealthError(err.message || 'Failed to connect to backend server');
      setHealthStatus(null);
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    getExtractionStatus().then(status => {
      setModeStatus(status);
      if (status.default_mode) {
        setSelectedMode(status.default_mode);
      }
    });
    getGraphStatus().then(setGraphStatus);
  }, []);

  const handleIngestIntoGraph = async () => {
    if (!structuredData) return;
    setIngesting(true);
    setIngestionError(null);
    setIngestionResult(null);
    try {
      const summary = await ingestIntoGraph(structuredData);
      setIngestionResult(summary);
      if (summary && summary.fir_id) {
        setActiveGraphFirId(summary.fir_id);
      }
    } catch (err) {
      setIngestionError(err.message || 'Graph ingestion failed.');
      setIngestionResult(null);
    } finally {
      setIngesting(false);
    }
  };


  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setPdfError(null);
      setPdfResult(null);
      setStructuredData(null);
      setIngestionResult(null);
    }
  };

  const loadSamplePdf = async (filename) => {
    try {
      setExtractingPdf(true);
      setPdfError(null);
      setPdfResult(null);
      setStructuredData(null);
      setIngestionResult(null);
      const res = await fetch(`/sample_data/${filename}`);
      if (!res.ok) throw new Error(`Could not fetch sample ${filename} (status ${res.status})`);
      const blob = await res.blob();
      const file = new File([blob], filename, { type: 'application/pdf' });
      setSelectedFile(file);
    } catch (err) {
      setPdfError(`Failed to load sample: ${err.message}`);
    } finally {
      setExtractingPdf(false);
    }
  };

  const handleUploadAndExtractPdf = async () => {
    if (!selectedFile) {
      setPdfError('Please select a PDF file first.');
      return;
    }

    setExtractingPdf(true);
    setPdfError(null);
    setStructuredData(null);
    setIngestionResult(null);
    try {
      const result = await extractDocumentText(selectedFile);
      setPdfResult(result);
      setActivePageTab('combined');
    } catch (err) {
      setPdfError(err.message || 'PDF text extraction failed.');
      setPdfResult(null);
    } finally {
      setExtractingPdf(false);
    }
  };

  const handleExtractEntitiesAndRelationships = async () => {
    if (!pdfResult || !pdfResult.pages || pdfResult.pages.length === 0) {
      setExtractionError('No page text available. Please extract PDF text first.');
      return;
    }

    setExtractingEntities(true);
    setExtractionError(null);
    setIngestionResult(null);
    try {
      const payload = {
        filename: pdfResult.filename,
        fir_id: pdfResult.filename.replace(/\.pdf$/i, ''),
        pages: pdfResult.pages,
        force_mode: selectedMode,
      };
      const result = await extractEntitiesAndRelationships(payload);
      setStructuredData(result);
    } catch (err) {
      setExtractionError(err.message || 'Entity extraction failed.');
      setStructuredData(null);
    } finally {
      setExtractingEntities(false);
    }
  };

  const isOnline = healthStatus && healthStatus.status === 'ok';

  return (
    <div className="app-container">
      <header className="header">
        <div className="badge-row">
          <span className="badge badge-cyan">Hackathon MVP</span>
          <span className="badge badge-amber">Problem: SIH26189</span>
          <span className="badge badge-cyan" style={{ backgroundColor: '#854d0e', color: '#fef08a' }}>Phase 7: P1 Historical FIR Lookup</span>
        </div>


        <h1 className="title">CrimeGraph</h1>
        <p className="subtitle">
          AI-Powered Criminal Network Analysis & Investigation Support System
        </p>
      </header>

      {/* Workflow Progress Stepper */}
      <div className="workflow-stepper">
        <div className={`step-badge ${pdfResult ? 'step-done' : 'step-current'}`}>
          <span className="step-circle">{pdfResult ? '✓' : '1'}</span>
          <span>1. Ingest FIR PDF</span>
        </div>
        <div className="step-arrow">→</div>
        <div className={`step-badge ${!pdfResult ? '' : structuredData ? 'step-done' : 'step-current'}`}>
          <span className="step-circle">{structuredData ? '✓' : '2'}</span>
          <span>2. AI / Structured Extraction</span>
        </div>
        <div className="step-arrow">→</div>
        <div className={`step-badge ${!structuredData ? '' : ingestionResult ? 'step-done' : 'step-current'}`}>
          <span className="step-circle">{ingestionResult ? '✓' : '3'}</span>
          <span>3. Ingest into Neo4j</span>
        </div>
        <div className="step-arrow">→</div>
        <div className={`step-badge ${ingestionResult || activeGraphFirId ? 'step-current' : ''}`}>
          <span className="step-circle">4</span>
          <span>4. Graph &amp; Historical Leads</span>
        </div>
      </div>

      {/* Main Grid */}
      <main className="grid">
        {/* Step 1: FIR PDF Ingestion (Phase 2) */}
        <section className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-title">
            <span>1. FIR PDF Ingestion &amp; Text Extraction (PyMuPDF)</span>
            {pdfResult && (
              <span className="badge badge-green">
                Extracted: {pdfResult.page_count} {pdfResult.page_count === 1 ? 'Page' : 'Pages'}
              </span>
            )}
          </div>

          <div className="upload-zone">
            <div className="file-input-wrapper">
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                <label className="btn btn-secondary custom-file-input">
                  Browse FIR PDF
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={handleFileChange}
                  />
                </label>

                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => loadSamplePdf('FIR-001.pdf')}
                  disabled={extractingPdf}
                  title="Load sample FIR-001 (Multi-page, Rahul Menon)"
                >
                  📄 Quick Load: FIR-001.pdf
                </button>

                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => loadSamplePdf('FIR-002.pdf')}
                  disabled={extractingPdf}
                  title="Load sample FIR-002 (Single-page, Arjun Das, shared phone & vehicle)"
                >
                  📄 Quick Load: FIR-002.pdf
                </button>
              </div>

              {selectedFile ? (
                <div className="selected-filename">
                  Selected: <strong>{selectedFile.name}</strong> ({(selectedFile.size / 1024).toFixed(1)} KB)
                </div>
              ) : (
                <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
                  Select an FIR PDF or click a Quick Load sample button above
                </span>
              )}

              <button
                className="btn"
                onClick={handleUploadAndExtractPdf}
                disabled={!selectedFile || extractingPdf}
                style={{ marginTop: '0.5rem' }}
              >
                {extractingPdf ? 'Extracting Text (PyMuPDF)...' : 'Extract Document Text'}
              </button>
            </div>
          </div>

          {pdfError && (
            <div className="error-banner">
              <strong>Error:</strong> {pdfError}
            </div>
          )}

          {pdfResult && (
            <div>
              <div className="doc-meta-row">
                <div className="meta-item">
                  <span className="meta-label">File:</span>
                  <span className="meta-val">{pdfResult.filename}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Pages:</span>
                  <span className="meta-val">{pdfResult.page_count}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Status:</span>
                  <span className="badge badge-green">{pdfResult.status}</span>
                </div>
              </div>

              {/* Page Tabs */}
              <div className="page-tabs">
                <button
                  className={`page-tab-btn ${activePageTab === 'combined' ? 'active' : ''}`}
                  onClick={() => setActivePageTab('combined')}
                >
                  Full Document ({pdfResult.combined_text.length} chars)
                </button>

                {pdfResult.pages.map((p, idx) => (
                  <button
                    key={p.page_number}
                    className={`page-tab-btn ${activePageTab === idx ? 'active' : ''}`}
                    onClick={() => setActivePageTab(idx)}
                  >
                    Page {p.page_number} ({p.character_count} chars)
                  </button>
                ))}
              </div>

              {/* Text Viewer */}
              <div className="text-viewer">
                {activePageTab === 'combined'
                  ? pdfResult.combined_text
                  : pdfResult.pages[activePageTab]?.text || '(No text on this page)'}
              </div>
            </div>
          )}
        </section>

        {/* Step 2: Structured Entity & Relationship Extraction (Phase 3) */}
        {pdfResult && (
          <section className="card" style={{ gridColumn: '1 / -1' }}>
            <div className="card-title">
              <span>2. AI / Structured Entity & Relationship Extraction</span>
              {structuredData && (
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <span className={`badge ${structuredData.extraction_mode === 'ai' ? 'badge-cyan' : 'badge-amber'}`}>
                    {structuredData.extraction_mode === 'ai' ? 'AI Extracted' : 'Demo Extraction'}
                  </span>
                  <span className="badge badge-purple">
                    Provider: {structuredData.provider}
                  </span>
                </div>
              )}
            </div>

            {/* Extraction Controls */}
            <div className="extraction-controls">
              <div className="mode-toggle-group">
                <span style={{ color: '#94a3b8' }}>Mode:</span>
                <button
                  className={`mode-btn ${selectedMode === 'demo' ? 'active' : ''}`}
                  onClick={() => setSelectedMode('demo')}
                >
                  Deterministic Demo Mode
                </button>
                <button
                  className={`mode-btn ${selectedMode === 'ai' ? 'active' : ''}`}
                  onClick={() => setSelectedMode('ai')}
                  title={!modeStatus.ai_available ? 'No LLM API key detected in .env' : 'Live Gemini AI Extraction'}
                >
                  Live AI Mode {modeStatus.ai_available ? '✓' : '(No Key)'}
                </button>
              </div>

              <button
                className="btn btn-accent"
                onClick={handleExtractEntitiesAndRelationships}
                disabled={extractingEntities}
              >
                {extractingEntities ? 'Extracting Entities & Relations...' : 'Extract Entities & Relationships'}
              </button>
            </div>

            {extractionError && (
              <div className="error-banner">
                <strong>Extraction Error:</strong> {extractionError}
              </div>
            )}

            {/* Structured Results Display */}
            {structuredData && (
              <div>
                {/* Entities by Type */}
                <h3 style={{ fontSize: '1rem', color: '#f1f5f9', marginBottom: '0.75rem' }}>
                  Extracted & Normalized Entities ({structuredData.entities.length} total)
                </h3>
                <div className="entity-grid">
                  {Object.entries(structuredData.entities_by_type).map(([type, values]) => (
                    values.length > 0 && (
                      <div key={type} className="entity-type-box">
                        <div className="entity-type-header">
                          <span>{type}</span>
                          <span style={{ color: '#64748b' }}>{values.length}</span>
                        </div>
                        <div className="entity-pills">
                          {structuredData.entities
                            .filter(e => e.type === type)
                            .map((ent, i) => (
                              <span
                                key={i}
                                className={`entity-pill ${type}`}
                                title={`Canonical: ${ent.normalized_value || ent.value}\nRaw: ${ent.value}`}
                              >
                                <strong>{ent.normalized_value || ent.value}</strong>
                                {ent.normalized_value && ent.value !== ent.normalized_value && (
                                  <span style={{ opacity: 0.6, fontSize: '0.7rem', marginLeft: '0.3rem' }}>
                                    (raw: "{ent.value}")
                                  </span>
                                )}
                              </span>
                            ))}
                        </div>
                      </div>
                    )
                  ))}
                </div>

                {/* Relationships with Provenance */}
                <h3 style={{ fontSize: '1rem', color: '#f1f5f9', marginBottom: '0.75rem' }}>
                  Extracted Relationships with Normalized Nodes ({structuredData.relationships.length} total)
                </h3>
                {structuredData.relationships.length === 0 ? (
                  <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>No relationships identified in this text.</p>
                ) : (
                  <div className="relationships-list">
                    {structuredData.relationships.map((rel, idx) => (
                      <div key={idx} className="relationship-card">
                        <div className="rel-header">
                          <div className="rel-triplet">
                            <span className="rel-node" title={`Raw: ${rel.source.value}`}>
                              <span className="node-type-label">{rel.source.type}</span>
                              {rel.source.normalized_value || rel.source.value}
                            </span>
                            <span className="rel-badge">{rel.relationship}</span>
                            <span className="rel-node" title={`Raw: ${rel.target.value}`}>
                              <span className="node-type-label">{rel.target.type}</span>
                              {rel.target.normalized_value || rel.target.value}
                            </span>
                          </div>

                          <div className="provenance-badges">
                            <span className="prov-pill">FIR: <strong>{rel.fir_id}</strong></span>
                            <span className="prov-pill">Page <strong>{rel.page}</strong></span>
                            <span className="confidence-pill">
                              {(rel.confidence * 100).toFixed(0)}% Conf.
                            </span>
                          </div>
                        </div>

                        <div className="evidence-quote">
                          <span className="evidence-label">Document Evidence (Page {rel.page}):</span>
                          "{rel.evidence}"
                        </div>
                      </div>
                    ))}
                  </div>
                )}

              </div>
            )}
          </section>
        )}

        {/* Step 3: Knowledge Graph Ingestion (Phase 5) */}
        {structuredData && (
          <section className="card" id="step3-card" style={{ gridColumn: '1 / -1' }}>
            <div className="card-title">
              <span>3. Knowledge Graph Ingestion (Neo4j Persistence)</span>
              <span className={`badge ${graphStatus.status === 'connected' ? 'badge-green' : 'badge-amber'}`}>
                Neo4j: {graphStatus.status}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', background: 'rgba(15, 23, 42, 0.6)', padding: '1.25rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
              <div>
                <h4 style={{ color: '#f8fafc', fontSize: '0.95rem', margin: 0 }}>
                  Ready to Persist Canonical Entities &amp; Provenance Relationships
                </h4>
                <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '0.25rem', marginBottom: 0 }}>
                  Extracted <strong>{structuredData.entities.length} canonical entities</strong> and <strong>{structuredData.relationships.length} relationships</strong> for <strong>{structuredData.fir_id}</strong>.
                </p>
              </div>

              <button
                className="btn"
                onClick={handleIngestIntoGraph}
                disabled={ingesting || graphStatus.status !== 'connected'}
                style={{ background: '#10b981', padding: '0.6rem 1.25rem', fontSize: '0.9rem' }}
              >
                {ingesting ? 'Ingesting into Neo4j...' : 'Store in Knowledge Graph'}
              </button>
            </div>

            {ingestionError && (
              <div className="error-banner" style={{ marginTop: '1rem' }}>
                <strong>Ingestion Error:</strong> {ingestionError}
              </div>
            )}

            {ingestionResult && (
              <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <h5 style={{ color: '#34d399', fontSize: '0.95rem', margin: 0 }}>
                    ✓ Knowledge Graph Ingestion Complete for {ingestionResult.fir_id}
                  </h5>
                  <button
                    className="btn btn-secondary"
                    style={{ padding: '0.3rem 0.65rem', fontSize: '0.75rem' }}
                    onClick={() => {
                      const el = document.querySelector('.graph-viz-card');
                      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }}
                  >
                    View in Graph ↓
                  </button>
                </div>
                <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.85rem', color: '#e2e8f0', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                  <span>FIR Node: <strong>{ingestionResult.fir_id}</strong></span>
                  <span>Entities Created or Matched: <strong>{ingestionResult.entities_created_or_matched}</strong></span>
                  <span>Relationships Created or Matched: <strong>{ingestionResult.relationships_created_or_matched}</strong></span>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.4rem', marginBottom: 0 }}>
                  {ingestionResult.message}
                </p>
              </div>
            )}
          </section>
        )}

        {/* Interactive Cytoscape Graph Visualization (Phase 6B) */}
        <GraphVisualization
          activeFirId={activeGraphFirId}
          onFirChanged={setActiveGraphFirId}
        />

        {/* Backend & Graph Status Card */}
        <section className="card">
          <div className="card-title">
            <span>System Connectivity</span>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                className="btn btn-secondary"
                onClick={() => { fetchHealth(); getGraphStatus().then(setGraphStatus); }}
                disabled={healthLoading}
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
              >
                {healthLoading ? 'Testing...' : 'Re-test Connectivity'}
              </button>
            </div>
          </div>

          <div
            className={`status-box ${healthLoading
                ? 'status-loading'
                : isOnline
                  ? 'status-online'
                  : 'status-offline'
              }`}
            style={{ marginBottom: '0.75rem' }}
          >
            <div
              className={`indicator-dot ${healthLoading
                  ? 'dot-loading'
                  : isOnline
                    ? 'dot-online'
                    : 'dot-offline'
                }`}
            />
            <div className="status-text">
              <h4>
                {healthLoading
                  ? 'Checking Backend Connectivity...'
                  : isOnline
                    ? 'FastAPI Backend Online'
                    : 'Backend Disconnected'}
              </h4>
              <p>
                {healthLoading
                  ? 'Connecting to /api/health...'
                  : isOnline
                    ? `Last verified at ${lastChecked}`
                    : `Error: ${healthError}`}
              </p>
            </div>
          </div>

          {/* Neo4j Status Box */}
          <div
            className={`status-box ${graphStatus.status === 'connected'
                ? 'status-online'
                : 'status-offline'
              }`}
          >
            <div
              className={`indicator-dot ${graphStatus.status === 'connected'
                  ? 'dot-online'
                  : 'dot-offline'
                }`}
            />
            <div className="status-text">
              <h4>
                {graphStatus.status === 'connected'
                  ? 'Neo4j Knowledge Graph Connected'
                  : 'Neo4j Database Unavailable'}
              </h4>
              <p>
                {graphStatus.status === 'connected'
                  ? `URI: ${graphStatus.uri} | DB: ${graphStatus.database}`
                  : (graphStatus.message || 'Configure NEO4J_PASSWORD in .env')}
              </p>
            </div>
          </div>
        </section>

        {/* Pipeline Checklist */}
        <section className="card">
          <div className="card-title">
            <span>Development Milestones</span>
            <span style={{ fontSize: '0.8rem', color: '#10b981' }}>Phase 7 / 10</span>
          </div>

          <ul className="pipeline-list">
            <li className="pipeline-step completed">
              <span className="step-num">✓</span>
              <span>Phase 1: Project Scaffolding & Health Check</span>
            </li>
            <li className="pipeline-step completed">
              <span className="step-num">✓</span>
              <span>Phase 2: FIR PDF Upload & PyMuPDF Extraction</span>
            </li>
            <li className="pipeline-step completed">
              <span className="step-num">✓</span>
              <span>Phase 3: AI / Structured Entity & Relationship Extraction</span>
            </li>
            <li className="pipeline-step completed">
              <span className="step-num">✓</span>
              <span>Phase 4: Entity Normalization & Validation</span>
            </li>
            <li className="pipeline-step completed">
              <span className="step-num">✓</span>
              <span>Phase 5: Neo4j Knowledge Graph Ingestion</span>
            </li>
            <li className="pipeline-step completed">
              <span className="step-num">✓</span>
              <span>Phase 6: Interactive Cytoscape.js Graph Visualization</span>
            </li>
            <li className="pipeline-step active">
              <span className="step-num">7</span>
              <span>Phase 7: Historical Knowledge Base Lookup (Active)</span>
            </li>
          </ul>
        </section>


      </main>

      <footer className="disclaimer">
        <strong>Human-in-the-Loop Investigation Tool:</strong> This system is designed solely to suggest candidate relationships and investigative leads based on FIR documents. All linkages require manual verification by an investigator.
      </footer>
    </div>
  );
}

export default App;
