# AGENTS.md

# AI-Powered Criminal Network Analysis System
# Hackathon MVP — Catalyst Crew
# Problem Statement: SIH26189

## 1. PROJECT PURPOSE

Build a focused hackathon prototype that converts multiple FIR documents
from a single case into a unified, traceable investigation knowledge graph.

The core workflow is:

FIR PDF
    ↓
Text Extraction
    ↓
Structured AI Extraction
    ↓
Entity Normalization + Validation
    ↓
Neo4j Knowledge Graph
    ↓
Cross-FIR Correlation
    ↓
Graph Visualization
    ↓
Evidence / Provenance Inspection

The system is an INVESTIGATION SUPPORT TOOL.

It does NOT determine guilt, identify criminals automatically, or make
legal conclusions.

The system suggests relationships and investigative leads.
A human investigator must verify the underlying evidence.

---

# 2. PRIMARY MVP GOAL

The most important demonstration must work end-to-end:

1. Create a case.
2. Upload multiple FIR PDFs.
3. Extract text from each FIR.
4. Extract entities and relationships using structured LLM output.
5. Normalize entities across FIRs.
6. Store entities and relationships in Neo4j.
7. Display the unified graph in React using Cytoscape.js.
8. Allow the user to select a relationship.
9. Show the FIR, page, evidence text, and confidence associated with it.
10. Demonstrate at least one cross-FIR connection.

A working end-to-end pipeline is more important than advanced features.

---

# 3. TECHNOLOGY STACK

Use the following stack unless there is a strong technical reason not to.

## Frontend

- React
- Vite
- JavaScript or TypeScript
- Cytoscape.js for graph visualization

## Backend

- Python
- FastAPI
- PyMuPDF / fitz for PDF text extraction

## Database

- Neo4j

## AI

- LLM with structured JSON output

The LLM provider should be isolated behind a small service/module so
that it can be replaced easily.

## Development

- Git
- Environment variables for secrets
- Local development first

Do not introduce additional frameworks unless necessary.

---

# 4. IMPORTANT DEVELOPMENT PRINCIPLE

DO NOT BUILD THE ENTIRE APPLICATION AT ONCE.

Implement the project incrementally.

Recommended order:

Phase 1:
Project structure
→ FastAPI health check
→ React application

Phase 2:
PDF upload
→ PyMuPDF extraction

Phase 3:
Text
→ LLM
→ structured JSON

Phase 4:
Structured JSON
→ normalization
→ validation

Phase 5:
Structured data
→ Neo4j

Phase 6:
Neo4j
→ graph API

Phase 7:
Graph API
→ Cytoscape.js

Phase 8:
Relationship selection
→ evidence/provenance panel

Phase 9:
Cross-FIR correlation

Phase 10:
UI polish and demo preparation

Do not skip directly to later phases.

---

# 5. CODING STYLE

Prefer:

- simple code
- readable functions
- small modules
- explicit data structures
- straightforward API endpoints
- useful error messages
- minimal abstractions

Avoid:

- unnecessary design patterns
- excessive classes
- dependency injection frameworks
- microservices
- message queues
- Docker unless explicitly requested
- Kubernetes
- authentication
- authorization
- complicated state-management libraries
- unnecessary configuration systems
- premature optimization

This is a hackathon MVP.

Working and understandable code is more important than enterprise architecture.

---

# 6. PROJECT STRUCTURE

Use a structure approximately like:

criminal-network-analysis/
│
├── AGENTS.md
├── README.md
├── .env.example
├── .gitignore
│
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   │
│   ├── api/
│   │   ├── cases.py
│   │   ├── documents.py
│   │   ├── extraction.py
│   │   └── graph.py
│   │
│   ├── services/
│   │   ├── pdf_service.py
│   │   ├── llm_service.py
│   │   ├── normalization_service.py
│   │   └── neo4j_service.py
│   │
│   ├── models/
│   │   └── schemas.py
│   │
│   └── tests/
│
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.jsx
│
└── sample_data/
    ├── FIR-001.pdf
    ├── FIR-002.pdf
    └── FIR-003.pdf

The exact structure may be adjusted if required, but keep backend,
frontend, and sample data clearly separated.

---

# 7. DATA MODEL

Core entity types for P0:

- PERSON
- PHONE
- VEHICLE
- LOCATION
- FIR

ORGANIZATION can be supported if straightforward, but must not delay the core pipeline.

Potential future entity types (not required tonight):

- EMAIL
- WEAPON
- BANK_ACCOUNT
- CASE


---

# 8. STRUCTURED EXTRACTION SCHEMA

The LLM must return structured JSON.

Use a structure conceptually similar to:

{
  "persons": [
    {
      "name": "Rahul Menon"
    }
  ],

  "phones": [
    {
      "number": "9876543210"
    }
  ],

  "vehicles": [
    {
      "registration": "KL-11-AB-1234"
    }
  ],

  "locations": [
    {
      "name": "Kozhikode Railway Station"
    }
  ],

  "relationships": [
    {
      "source": "Rahul Menon",
      "source_type": "PERSON",
      "relationship_type": "USED_PHONE",
      "target": "9876543210",
      "target_type": "PHONE",

      "fir_id": "FIR-001",
      "page": 1,

      "evidence":
        "Rahul Menon was using mobile number 9876543210.",

      "confidence": 0.95
    }
  ]
}

The exact schema may be implemented using Pydantic models.

---

# 9. EVIDENCE PROVENANCE — CRITICAL

Every extracted relationship must preserve its source.

At minimum, store:

- FIR ID
- page number when available
- evidence text
- confidence

Example:

Rahul Menon
    |
    | USED_PHONE
    |
9876543210

Relationship properties:

fir_id = FIR-001
page = 1
evidence = "Rahul Menon was using..."
confidence = 0.95

NEVER create an AI-generated relationship without recording its evidence.

Do not invent evidence.

The evidence displayed to the user must originate from the uploaded FIR
text.

---

# 10. LLM RULES

The LLM is responsible for:

- extracting entities
- identifying relationships explicitly supported by the text
- returning structured JSON

The LLM is NOT responsible for:

- deciding guilt
- making legal conclusions
- inventing relationships
- inventing evidence
- creating unsupported facts
- determining that two ambiguous people are definitely the same person

If the evidence is ambiguous, preserve the uncertainty.

Prefer:

"candidate relationship"

over:

"confirmed relationship"

when the evidence does not establish certainty.

---

# 11. MOCK / DEMO MODE

A fallback/demo mode is REQUIRED.

The system must be capable of demonstrating the graph workflow without
depending entirely on an external LLM API.

Possible implementation:

DEMO_MODE=true

When enabled:

FIR → extracted text → predefined structured JSON

This allows the following to continue working even if the LLM API fails:

- Neo4j storage
- graph visualization
- cross-FIR correlation
- provenance display

Do not remove demo mode unless explicitly instructed.

---

# 12. PDF PROCESSING

Use PyMuPDF for normal text-based PDFs.

The initial pipeline is:

PDF
 ↓
PyMuPDF
 ↓
page-level text
 ↓
LLM

Preserve page boundaries where possible.

Example:

{
  "page": 1,
  "text": "..."
}

{
  "page": 2,
  "text": "..."
}

OCR is NOT part of the initial MVP.

Do not introduce PaddleOCR or another OCR framework unless explicitly
requested or unless the existing pipeline is already working.

---

# 13. ENTITY NORMALIZATION

Before inserting entities into Neo4j, normalize them.

Examples:

Phone:

"98765 43210"
"9876543210"
"+91 9876543210"

should be normalized where appropriate.

Vehicle:

"KL 11 AB 1234"
"KL-11-AB-1234"

should normalize to a consistent representation.

Names should receive conservative normalization such as:

- trimming whitespace
- consistent casing for comparison
- removing obvious formatting differences

Do NOT perform aggressive fuzzy matching in the first MVP.

False entity merges are worse than missed uncertain matches.

---

# 14. CROSS-FIR CORRELATION

One of the most important features is detecting entities that occur
across multiple FIRs.

Example:

FIR-001:
Rahul Menon → PHONE → 9876543210

FIR-002:
Arjun Das → PHONE → 9876543210

The shared phone should produce a graph connection through the same
normalized Phone node.

The system should be able to show:

FIR-001
   ↓
Rahul Menon
   ↓
9876543210
   ↑
Arjun Das
   ↑
FIR-002

Cross-FIR matches should be based on conservative normalization.

Do not claim an uncertain identity match is definitely the same person.

---

# 15. NEO4J MODEL

Use nodes approximately like:

(:Person)
(:Phone)
(:Vehicle)
(:Location)
(:FIR)

Relationships can include:

(:Person)-[:USED_PHONE]->(:Phone)

(:Person)-[:USED_VEHICLE]->(:Vehicle)

(:Person)-[:SEEN_AT]->(:Location)

(:Person)-[:MET]->(:Person)

(:Person)-[:ASSOCIATED_WITH]->(:Person)

Use MERGE where appropriate to avoid unnecessary duplicate normalized
entities.

Relationship properties should preserve provenance.

---

# 15A. HISTORICAL KNOWLEDGE BASE (P1 — STRONG EXTENSION IF P0 IS STABLE)

Neo4j also serves as the historical investigation knowledge base.

The database may contain FIRs from previous cases in addition to the
currently analyzed case.

When a new FIR is analyzed:

1. Extract and normalize entities.
2. Check whether normalized entities already exist in the SAME Neo4j database.
3. Identify historical FIRs containing matching entities.
4. Return:
   - matched entity
   - historical FIR
   - relationship
   - evidence / provenance where available
5. Display historical matches separately from newly extracted
   relationships when appropriate.

For the hackathon MVP, use a small set of fictional historical FIRs.

Do NOT create a separate historical database.

Do not implement complex recommendation or prediction algorithms.

The initial historical lookup should focus on exact normalized matches
for:
- phone numbers
- vehicle registrations
- person names where sufficiently reliable

Historical matches must be presented as candidate connections and must
not be treated as proof of identity, guilt, or criminal association.

---


# 16. GRAPH API

The backend should expose simple APIs.

Possible endpoints:

GET /api/health

POST /api/cases

GET /api/cases/{case_id}

POST /api/cases/{case_id}/documents

POST /api/cases/{case_id}/analyze

GET /api/cases/{case_id}/graph

GET /api/relationships/{relationship_id}

The exact endpoint names may be changed if a better consistent design
is required.

Do not create dozens of endpoints.

---

# 17. FRONTEND REQUIREMENTS

The frontend should focus on the investigation workflow.

Minimum UI:

1. Case selection / case creation
2. FIR upload
3. FIR document list
4. Analyze Case button
5. Investigation graph
6. Evidence/provenance panel

Recommended layout:

----------------------------------------------------
| Criminal Network Analysis                         |
----------------------------------------------------
| Case: Operation X                                 |
|                                                   |
| [Upload FIR] [Analyze Case]                       |
----------------------------------------------------
| FIR Documents       | Investigation Graph         |
|                     |                             |
| FIR-001 ✓           |          Rahul              |
| FIR-002 ✓           |          /  \               |
| FIR-003 ✓           |       PHONE  MET            |
|                     |        |      \             |
|                     |     98765   Arjun            |
----------------------------------------------------
| Evidence / Relationship Details                  |
| FIR: FIR-001                                      |
| Page: 2                                           |
| Evidence: "..."                                   |
----------------------------------------------------

The graph is the primary visual component.

---

# 18. CYTOSCAPE.JS

Use Cytoscape.js for interactive graph visualization.

The frontend should support:

- displaying nodes
- displaying relationships
- basic node labels
- relationship labels where useful
- selecting a relationship
- selecting a node
- showing associated evidence

Do not spend excessive time on advanced graph styling.

Functional interaction is more important than visual complexity.

---

# 19. GRAPH ANALYSIS (P2 — ONLY IF TIME REMAINS)

Simple explainable graph-analysis signals:

- highly connected entities
- repeated entities
- 2-hop relationships
- potential bridge/intermediary entities

These are analytical signals for investigator review, NOT conclusions of guilt or criminality.

Do NOT implement:

- Graph Neural Networks
- advanced graph embeddings
- complex community detection
- custom graph ML
- sophisticated criminal prediction models

These can be future extensions.


---

# 20. HUMAN-IN-THE-LOOP PRINCIPLE

The system should use language such as:

- "Potential connection"
- "Candidate relationship"
- "Shared entity detected"
- "Evidence source"
- "Requires verification"

Avoid language such as:

- "Confirmed criminal"
- "This person is guilty"
- "Criminal identified"
- "Proven association"

The system supports investigation; it does not make legal judgments.

---

# 21. ERROR HANDLING

Every external dependency may fail.

Handle at least:

- invalid PDF
- empty PDF
- PDF text extraction failure
- LLM API failure
- invalid LLM JSON
- Neo4j connection failure
- missing environment variables
- duplicate uploads
- empty extraction results

Errors should be understandable to the user.

Do not silently swallow exceptions.

---

# 22. SECURITY / SECRETS

Never hard-code:

- LLM API keys
- Neo4j passwords
- database credentials

Use environment variables.

Example:

NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
LLM_API_KEY=

Provide:

.env.example

Never commit:

.env

---

# 23. SAMPLE DATA

Use fictional FIR data for demonstration.

Do not require real sensitive criminal records for the MVP.

Sample FIRs should intentionally contain overlapping information so the
cross-FIR correlation can be demonstrated.

For example:

FIR-001:
Rahul Menon
Phone: 9876543210
Vehicle: KL-11-AB-1234

FIR-002:
Arjun Das
Phone: 9876543210
Vehicle: KL-11-AB-1234

FIR-003:
Rahul Menon
Location: Kozhikode Railway Station

This creates an understandable demonstration graph.

---

# 24. TESTING STRATEGY

After implementing each feature:

1. Run it.
2. Test it.
3. Fix errors.
4. Only then move to the next feature.

At minimum test:

PDF → text

text → JSON

JSON → Neo4j

Neo4j → graph API

graph API → Cytoscape

relationship click → evidence

Do not assume code works merely because it compiles.

---

# 25. ANTIGRAVITY WORKING RULES

When asked to implement a feature:

1. Inspect the existing code first.
2. Understand the current architecture.
3. Reuse existing modules where appropriate.
4. Make the smallest change necessary.
5. Do not rewrite working components unnecessarily.
6. Run relevant tests after changes.
7. Report what was changed.
8. Report any remaining errors.
9. Do not claim something works without testing it.

If a requirement is ambiguous, choose the simplest implementation
consistent with this document.

---

# 26. DO NOT OVERENGINEER

Do NOT automatically add:

- Docker
- Kubernetes
- Redis
- Celery
- RabbitMQ
- Kafka
- PostgreSQL
- MongoDB
- LangChain
- LangGraph
- vector databases
- authentication
- user accounts
- cloud deployment
- microservices

unless explicitly requested.

Neo4j is already the primary database.

FastAPI is already the backend.

React is already the frontend.

Keep the architecture focused.

---

# 27. AGENT BEHAVIOR

Act as a pragmatic senior full-stack developer helping build a hackathon
prototype.

Prioritize:

1. End-to-end functionality
2. Reliability
3. Simplicity
4. Demonstrability
5. Code clarity
6. UI polish

Do not prioritize:

- theoretical perfection
- enterprise-scale architecture
- unnecessary abstraction
- implementing every feature in the presentation

If time is limited, protect the core workflow.

---

# 28. FEATURE PRIORITY

## P0 — CORE DEMO THAT MUST WORK

- Case creation & multi-FIR upload
- FIR PDF text extraction
- AI / structured entity + relationship extraction
- Entity normalization and validation
- Neo4j knowledge graph storage
- Cytoscape graph visualization
- Evidence / provenance inspection (FIR, page, evidence text, confidence)
- Cross-FIR correlation (demonstrating shared entities across FIRs)
- Core entities: PERSON, PHONE, VEHICLE, LOCATION
  (ORGANIZATION can be supported if straightforward, but must not delay the core pipeline)

## P1 — STRONG EXTENSION IF P0 IS STABLE

- Historical FIR lookup using the SAME Neo4j database
- Small set of fictional historical FIRs
- When a new FIR contains a normalized entity already present in historical data, show:
  - matched entity
  - historical FIR
  - relationship
  - evidence / provenance where available
- Do NOT create a separate historical database

## P2 — ONLY IF TIME REMAINS

- Simple explainable graph-analysis signals:
  - highly connected entities
  - repeated entities
  - 2-hop relationships
  - potential bridge / intermediary entities
- Analytical signals for investigator review, NOT conclusions of guilt or criminality

## FUTURE SCOPE — DO NOT IMPLEMENT TONIGHT

- CDR integration
- Financial transaction integration
- Surveillance integration
- Social-media integration
- Real criminal-history databases
- Real intelligence-agency databases
- Advanced graph neural networks
- Sophisticated anomaly detection
- Predictive criminal behavior
- Real law-enforcement integrations

(The architecture can remain extensible for these later.)

## DEVELOPMENT PRIORITY RULES

- P0 must be completed and working before P1.
- P1 must be completed before P2.
- A stable working feature is more important than adding breadth.
- Do not modify working Phase 1 code unnecessarily.


---

# 29. DEMO SUCCESS CRITERIA

The project is considered successful if a judge can observe:

1. Multiple FIRs uploaded into one case.
2. Documents analyzed.
3. Entities automatically extracted.
4. Relationships automatically extracted.
5. A unified graph appears.
6. The same entity appearing in multiple FIRs is correlated.
7. A relationship can be selected.
8. The original FIR evidence is displayed.
9. The system communicates that findings require human verification.

The demo should communicate:

AI extracts evidence.
Graph analysis correlates evidence.
The investigator verifies the result.

---

# 30. FINAL RULE

DO NOT sacrifice the working end-to-end pipeline for additional features.

A simple system that reliably demonstrates:

FIR → AI → JSON → Neo4j → Graph → Evidence

is preferable to a sophisticated system with disconnected components.

When making implementation decisions, ask:

"Does this help us demonstrate the core investigation workflow?"

If NO:
do not implement it unless explicitly requested.

If YES:
implement the simplest reliable version.