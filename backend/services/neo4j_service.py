import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver, Session
from models.schemas import (
    Entity,
    EntityType,
    ExtractedRelationship,
    RelationshipType,
    ExtractionResult,
    IngestionSummary,
    GraphStatusResponse,
    GraphNode,
    GraphRelationship,
    GraphDataResponse,
    FIRItem,
    FIRListResponse,
    HistoricalMatch,
    HistoricalLookupResponse,
    ConnectedEntityInfo,
    RelationshipProvenance,
    HighlyConnectedEntity,
    RepeatedEntityOccurrence,
    RepeatedEntity,
    TwoHopPath,
    BridgedEntityPair,
    BridgeEntity,
    GraphAnalysisResponse,
) 

load_dotenv()
logger = logging.getLogger("crimegraph.neo4j")


class Neo4jServiceError(Exception):
    """Base exception for Neo4j operations."""
    pass


class Neo4jConnectionError(Neo4jServiceError):
    """Raised when Neo4j is unreachable or credentials fail."""
    pass


class FIRNotFoundError(Neo4jServiceError):
    """Raised when a requested FIR does not exist in Neo4j."""
    pass


# Map schema EntityType to standard Neo4j Label
LABEL_MAP = {
    EntityType.PERSON: "Person",
    EntityType.PHONE: "Phone",
    EntityType.VEHICLE: "Vehicle",
    EntityType.LOCATION: "Location",
    EntityType.ORGANIZATION: "Organization",
}

# Whitelist allowed relationship types for Cypher query safety
ALLOWED_RELATIONSHIPS = {rel.value for rel in RelationshipType}


def get_entity_key(entity: Entity) -> str:
    """Generates the canonical unique identity key for a node."""
    canonical_val = entity.normalized_value or entity.value
    return f"{entity.type.value}:{canonical_val}"


class Neo4jService:
    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self.uri = uri if uri is not None else os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username if username is not None else os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = password if password is not None else os.getenv("NEO4J_PASSWORD", "")
        self.database = database if database is not None else os.getenv("NEO4J_DATABASE", "neo4j")
        self._driver: Optional[Driver] = None

    def get_driver(self) -> Driver:
        """Initializes and returns the Neo4j driver singleton."""
        if self._driver is None:
            if not self.password:
                raise Neo4jConnectionError(
                    "NEO4J_PASSWORD is not set in environment. Please configure .env."
                )
            try:
                self._driver = GraphDatabase.driver(
                    self.uri,
                    auth=(self.username, self.password),
                    max_connection_lifetime=30 * 60,
                )
            except Exception as e:
                raise Neo4jConnectionError(f"Failed to create Neo4j driver for '{self.uri}': {e}")
        return self._driver

    def check_connection(self) -> GraphStatusResponse:
        """Checks connectivity to the Neo4j database without throwing uncaught exceptions."""
        if not self.password:
            return GraphStatusResponse(
                status="unavailable",
                uri=self.uri,
                database=self.database,
                message="NEO4J_PASSWORD environment variable is not configured.",
            )

        try:
            driver = self.get_driver()
            driver.verify_connectivity()
            return GraphStatusResponse(
                status="connected",
                uri=self.uri,
                database=self.database,
                message="Successfully connected to Neo4j knowledge graph.",
            )
        except Exception as e:
            return GraphStatusResponse(
                status="unavailable",
                uri=self.uri,
                database=self.database,
                message=f"Cannot connect to Neo4j instance: {str(e)}",
            )

    def init_schema(self):
        """Initializes database constraints and indexes for canonical performance and integrity."""
        status = self.check_connection()
        if status.status != "connected":
            return

        driver = self.get_driver()
        with driver.session(database=self.database) as session:
            # FIR unique constraint
            session.run(
                "CREATE CONSTRAINT fir_id_unique IF NOT EXISTS "
                "FOR (f:FIR) REQUIRE f.fir_id IS UNIQUE"
            )
            # Entity key constraints
            for label in LABEL_MAP.values():
                session.run(
                    f"CREATE CONSTRAINT {label.lower()}_key_unique IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.key IS UNIQUE"
                )

    def ingest_extraction_result(self, result: ExtractionResult) -> IngestionSummary:
        """
        Persists a normalized ExtractionResult into Neo4j using parameterized Cypher MERGE queries:
        1. MERGE (:FIR {fir_id: ...})
        2. MERGE canonical entity nodes with normalized identity keys
        3. MERGE (:FIR)-[:CONTAINS]->(Entity) provenance relationships
        4. MERGE entity-to-entity relationships with full provenance (fir_id, page, evidence, confidence)
        """
        status = self.check_connection()
        if status.status != "connected":
            raise Neo4jConnectionError(
                f"Neo4j database is unavailable at {self.uri}. {status.message}"
            )

        driver = self.get_driver()
        fir_id = result.fir_id
        filename = result.filename

        entities_count = 0
        fir_rels_count = 0
        relationships_count = 0

        with driver.session(database=self.database) as session:
            # 1. MERGE FIR node
            session.run(
                """
                MERGE (f:FIR {fir_id: $fir_id})
                ON CREATE SET f.filename = $filename, f.created_at = datetime()
                ON MATCH SET f.last_analyzed = datetime()
                """,
                fir_id=fir_id,
                filename=filename,
            )

            # 2. MERGE canonical Entity nodes and (:FIR)-[:CONTAINS]->(Entity)
            for entity in result.entities:
                label = LABEL_MAP.get(entity.type)
                if not label:
                    continue

                canonical_val = entity.normalized_value or entity.value
                entity_key = get_entity_key(entity)

                # Parameterized MERGE on canonical key
                cypher_entity = f"""
                MERGE (e:{label} {{key: $key}})
                ON CREATE SET 
                    e.canonical_value = $canonical_val,
                    e.name = $canonical_val,
                    e.value = $canonical_val,
                    e.type = $type,
                    e.first_raw_value = $raw_val,
                    e.created_at = datetime()
                ON MATCH SET 
                    e.last_seen = datetime()
                WITH e
                MATCH (f:FIR {{fir_id: $fir_id}})
                MERGE (f)-[r:CONTAINS]->(e)
                ON CREATE SET r.raw_value = $raw_val, r.created_at = datetime()
                """
                session.run(
                    cypher_entity,
                    key=entity_key,
                    canonical_val=canonical_val,
                    raw_val=entity.value,
                    type=entity.type.value,
                    fir_id=fir_id,
                )
                entities_count += 1
                fir_rels_count += 1

            # 3. MERGE Entity-to-Entity Relationships with Provenance
            for rel in result.relationships:
                rel_type = rel.relationship.value
                if rel_type not in ALLOWED_RELATIONSHIPS:
                    continue

                src_label = LABEL_MAP.get(rel.source.type)
                tgt_label = LABEL_MAP.get(rel.target.type)
                if not src_label or not tgt_label:
                    continue

                src_key = get_entity_key(rel.source)
                tgt_key = get_entity_key(rel.target)

                # Parameterized Cypher with whitelisted relationship type
                # The relationship is keyed by source, target, fir_id, and page to preserve page-level evidence
                cypher_rel = f"""
                MATCH (source:{src_label} {{key: $src_key}})
                MATCH (target:{tgt_label} {{key: $tgt_key}})
                MERGE (source)-[r:{rel_type} {{fir_id: $fir_id, page: $page}}]->(target)
                SET 
                    r.evidence = $evidence,
                    r.confidence = $confidence,
                    r.source_raw = $src_raw,
                    r.target_raw = $tgt_raw,
                    r.relationship = $rel_type,
                    r.updated_at = datetime()
                """
                session.run(
                    cypher_rel,
                    src_key=src_key,
                    tgt_key=tgt_key,
                    fir_id=rel.fir_id or fir_id,
                    page=rel.page,
                    evidence=rel.evidence,
                    confidence=float(rel.confidence),
                    src_raw=rel.source.value,
                    tgt_raw=rel.target.value,
                    rel_type=rel_type,
                )
                relationships_count += 1

        return IngestionSummary(
            fir_id=fir_id,
            filename=filename,
            entities_created_or_matched=entities_count,
            relationships_created_or_matched=relationships_count,
            fir_relationships_created=fir_rels_count,
            status="success",
            message=f"Successfully ingested {entities_count} entities and {relationships_count} relationships into Neo4j for {fir_id}.",
        )

    def get_firs(self) -> FIRListResponse:
        """
        Retrieves all available FIR records from Neo4j along with metadata and entity counts.
        """
        status = self.check_connection()
        if status.status != "connected":
            raise Neo4jConnectionError(
                f"Neo4j database is unavailable at {self.uri}. {status.message}"
            )

        driver = self.get_driver()
        query = """
        MATCH (f:FIR)
        OPTIONAL MATCH (f)-[:CONTAINS]->(e)
        RETURN f.fir_id AS fir_id,
               f.filename AS filename,
               toString(f.created_at) AS created_at,
               toString(f.last_analyzed) AS last_analyzed,
               count(DISTINCT e) AS entity_count
        ORDER BY f.fir_id ASC
        """
        firs: List[FIRItem] = []
        with driver.session(database=self.database) as session:
            result = session.run(query)
            for record in result:
                firs.append(
                    FIRItem(
                        fir_id=record["fir_id"],
                        filename=record.get("filename"),
                        created_at=record.get("created_at"),
                        last_analyzed=record.get("last_analyzed"),
                        entity_count=record.get("entity_count", 0),
                    )
                )

        return FIRListResponse(firs=firs, total_count=len(firs))

    def get_graph_for_fir(self, fir_id: str) -> GraphDataResponse:
        """
        Retrieves nodes and relationships for a specific FIR.
        Raises FIRNotFoundError if the FIR does not exist.
        """
        status = self.check_connection()
        if status.status != "connected":
            raise Neo4jConnectionError(
                f"Neo4j database is unavailable at {self.uri}. {status.message}"
            )

        driver = self.get_driver()
        with driver.session(database=self.database) as session:
            # 1. Check if FIR exists
            fir_query = """
            MATCH (f:FIR {fir_id: $fir_id})
            RETURN f.fir_id AS fir_id, f.filename AS filename, toString(f.created_at) AS created_at
            """
            fir_record = session.run(fir_query, fir_id=fir_id).single()
            if not fir_record:
                raise FIRNotFoundError(f"FIR '{fir_id}' not found in knowledge graph.")

            nodes_dict: Dict[str, GraphNode] = {}
            relationships: List[GraphRelationship] = []

            # Add the FIR node itself
            fir_key = f"FIR:{fir_id}"
            nodes_dict[fir_key] = GraphNode(
                key=fir_key,
                entity_type="FIR",
                display_value=fir_id,
                canonical_value=fir_id,
                properties={"filename": fir_record.get("filename")},
            )

            # 2. Retrieve all entities contained in this FIR
            contains_query = """
            MATCH (f:FIR {fir_id: $fir_id})-[r:CONTAINS]->(e)
            RETURN e.key AS key,
                   labels(e) AS labels,
                   coalesce(e.name, e.canonical_value, e.value, e.key) AS display_value,
                   e.canonical_value AS canonical_value,
                   e.value AS value,
                   e.type AS entity_type,
                   e.first_raw_value AS first_raw_value,
                   r.raw_value AS raw_value,
                   elementId(r) AS rel_id
            ORDER BY key
            """
            contains_results = session.run(contains_query, fir_id=fir_id)
            for rec in contains_results:
                key = rec["key"]
                ent_type = rec.get("entity_type")
                if not ent_type:
                    labels = [l for l in rec.get("labels", []) if l != "FIR"]
                    ent_type = labels[0].upper() if labels else "UNKNOWN"

                display_val = rec.get("display_value") or key
                canonical_val = rec.get("canonical_value") or rec.get("value") or display_val

                if key not in nodes_dict:
                    nodes_dict[key] = GraphNode(
                        key=key,
                        entity_type=ent_type,
                        display_value=display_val,
                        canonical_value=canonical_val,
                        properties={
                            "first_raw_value": rec.get("first_raw_value"),
                            "raw_value": rec.get("raw_value"),
                        },
                    )

                # Add the CONTAINS relationship from FIR to Entity
                rel_id = rec.get("rel_id") or f"contains_{fir_id}_{key}"
                relationships.append(
                    GraphRelationship(
                        id=str(rel_id),
                        source=fir_key,
                        target=key,
                        relationship_type="CONTAINS",
                        fir_id=fir_id,
                        page=None,
                        evidence=f"Entity contained in {fir_id}",
                        confidence=1.0,
                        properties={"raw_value": rec.get("raw_value")},
                    )
                )

            # 3. Retrieve entity-to-entity relationships for this FIR
            rel_query = """
            MATCH (s)-[r]->(t)
            WHERE r.fir_id = $fir_id AND type(r) <> 'CONTAINS'
            RETURN elementId(r) AS rel_id,
                   s.key AS source,
                   labels(s) AS source_labels,
                   coalesce(s.name, s.canonical_value, s.value, s.key) AS source_display,
                   s.canonical_value AS source_canonical,
                   s.type AS source_type,
                   type(r) AS relationship_type,
                   t.key AS target,
                   labels(t) AS target_labels,
                   coalesce(t.name, t.canonical_value, t.value, t.key) AS target_display,
                   t.canonical_value AS target_canonical,
                   t.type AS target_type,
                   r.fir_id AS fir_id,
                   r.page AS page,
                   r.evidence AS evidence,
                   r.confidence AS confidence,
                   r.source_raw AS source_raw,
                   r.target_raw AS target_raw
            ORDER BY source, relationship_type, target
            """
            rel_results = session.run(rel_query, fir_id=fir_id)
            for rrec in rel_results:
                s_key = rrec["source"]
                t_key = rrec["target"]

                # Ensure source and target nodes exist in nodes_dict
                if s_key not in nodes_dict:
                    s_type = rrec.get("source_type") or (
                        [l for l in rrec.get("source_labels", []) if l != "FIR"][0].upper()
                        if rrec.get("source_labels")
                        else "UNKNOWN"
                    )
                    nodes_dict[s_key] = GraphNode(
                        key=s_key,
                        entity_type=s_type,
                        display_value=rrec.get("source_display") or s_key,
                        canonical_value=rrec.get("source_canonical") or rrec.get("source_display"),
                    )

                if t_key not in nodes_dict:
                    t_type = rrec.get("target_type") or (
                        [l for l in rrec.get("target_labels", []) if l != "FIR"][0].upper()
                        if rrec.get("target_labels")
                        else "UNKNOWN"
                    )
                    nodes_dict[t_key] = GraphNode(
                        key=t_key,
                        entity_type=t_type,
                        display_value=rrec.get("target_display") or t_key,
                        canonical_value=rrec.get("target_canonical") or rrec.get("target_display"),
                    )

                rel_id = rrec.get("rel_id") or f"{s_key}_{rrec['relationship_type']}_{t_key}_{fir_id}_{rrec.get('page')}"
                relationships.append(
                    GraphRelationship(
                        id=str(rel_id),
                        source=s_key,
                        target=t_key,
                        relationship_type=rrec["relationship_type"],
                        fir_id=rrec["fir_id"],
                        page=rrec.get("page"),
                        evidence=rrec.get("evidence"),
                        confidence=float(rrec["confidence"]) if rrec.get("confidence") is not None else None,
                        properties={
                            "source_raw": rrec.get("source_raw"),
                            "target_raw": rrec.get("target_raw"),
                        },
                    )
                )

        node_list = list(nodes_dict.values())
        return GraphDataResponse(
            fir_id=fir_id,
            nodes=node_list,
            relationships=relationships,
            node_count=len(node_list),
            relationship_count=len(relationships),
        )

    def get_historical_connections(self, fir_id: str) -> HistoricalLookupResponse:
        """
        Searches for candidate historical connections for a given FIR in the Neo4j database.
        Matches canonical entities (PHONE, VEHICLE, PERSON, ORGANIZATION) present in the current FIR
        against all other FIRs in the database, excluding LOCATION and the current FIR.
        """
        status = self.check_connection()
        if status.status != "connected":
            raise Neo4jConnectionError(
                f"Neo4j database is unavailable at {self.uri}. {status.message}"
            )

        driver = self.get_driver()
        with driver.session(database=self.database) as session:
            # 1. Verify current FIR exists
            check_query = "MATCH (f:FIR {fir_id: $fir_id}) RETURN f.fir_id AS fir_id"
            if not session.run(check_query, fir_id=fir_id).single():
                raise FIRNotFoundError(f"FIR '{fir_id}' not found in knowledge graph.")

            # 2. Query for historical matches
            # Conservative matching: PHONE, VEHICLE, PERSON, ORGANIZATION (excluding LOCATION and FIR)
            # Exclude current FIR ($fir_id)
            query = """
            MATCH (f1:FIR {fir_id: $fir_id})-[c1:CONTAINS]->(e)
            WHERE NOT e:Location AND NOT e:FIR
            MATCH (f2:FIR)-[c2:CONTAINS]->(e)
            WHERE f2.fir_id <> $fir_id
            OPTIONAL MATCH (s)-[r]->(t)
            WHERE r.fir_id = f2.fir_id AND (s.key = e.key OR t.key = e.key) AND type(r) <> 'CONTAINS'
            RETURN DISTINCT
                   e.key AS entity_key,
                   e.type AS entity_type,
                   coalesce(e.canonical_value, e.value, e.name, e.key) AS canonical_value,
                   f1.fir_id AS current_fir_id,
                   f2.fir_id AS historical_fir_id,
                   f2.filename AS historical_filename,
                   type(r) AS historical_relationship,
                   r.page AS page,
                   r.evidence AS evidence,
                   r.confidence AS confidence,
                   s.key AS source_key,
                   t.key AS target_key
            ORDER BY historical_fir_id, entity_type, canonical_value
            """
            results = session.run(query, fir_id=fir_id)
            matches: List[HistoricalMatch] = []
            seen_entities = set()

            for rec in results:
                ent_key = rec["entity_key"]
                seen_entities.add(ent_key)
                
                ent_type = rec.get("entity_type")
                if not ent_type:
                    ent_type = ent_key.split(":", 1)[0] if ":" in ent_key else "UNKNOWN"

                matches.append(
                    HistoricalMatch(
                        entity_key=ent_key,
                        entity_type=ent_type,
                        canonical_value=rec["canonical_value"],
                        current_fir_id=rec["current_fir_id"],
                        historical_fir_id=rec["historical_fir_id"],
                        historical_filename=rec.get("historical_filename"),
                        historical_relationship=rec.get("historical_relationship"),
                        source_key=rec.get("source_key"),
                        target_key=rec.get("target_key"),
                        page=rec.get("page"),
                        evidence=rec.get("evidence") or f"Entity {ent_key} previously recorded in {rec['historical_fir_id']}",
                        confidence=float(rec["confidence"]) if rec.get("confidence") is not None else 1.0,
                    )
                )

            return HistoricalLookupResponse(
                current_fir_id=fir_id,
                matches=matches,
                total_matches=len(matches),
                shared_entity_count=len(seen_entities),
            )

    def get_graph_analytics(self, fir_id: Optional[str] = None) -> GraphAnalysisResponse:
        """
        Computes explainable, read-only graph analysis signals (P2):
        1. Highly Connected Entities (degree excluding FIR nodes and CONTAINS provenance edges)
        2. Repeated Entities (canonical normalized entity keys present in >= 2 distinct FIRs)
        3. 2-Hop Candidate Relationships (indirect linkage paths with hop-level provenance)
        4. Potential Bridge / Intermediary Entities (nodes connecting otherwise disconnected entities / FIRs)

        Strictly read-only: does not modify Neo4j data.
        """
        status = self.check_connection()
        if status.status != "connected":
            raise Neo4jConnectionError(
                f"Neo4j database is unavailable at {self.uri}. {status.message}"
            )

        driver = self.get_driver()
        with driver.session(database=self.database) as session:
            # 1. Verify FIR exists if scoped to a specific FIR
            if fir_id:
                check_query = "MATCH (f:FIR {fir_id: $fir_id}) RETURN f.fir_id AS fir_id"
                if not session.run(check_query, fir_id=fir_id).single():
                    raise FIRNotFoundError(f"FIR '{fir_id}' not found in knowledge graph.")

            # ------------------------------------------------------------------
            # Signal 1: Highly Connected Entities
            # Degree strictly counts non-CONTAINS relationships to other non-FIR entities
            # ------------------------------------------------------------------
            hce_query = """
            MATCH (e)
            WHERE NOT e:FIR AND ($fir_id IS NULL OR EXISTS {
                MATCH (:FIR {fir_id: $fir_id})-[:CONTAINS]->(e)
            })
            MATCH (e)-[r]-(other)
            WHERE NOT other:FIR AND type(r) <> 'CONTAINS'
            WITH e, r, other,
                 CASE WHEN startNode(r) = e THEN 'outgoing' ELSE 'incoming' END AS direction
            WITH e,
                 count(DISTINCT r) AS degree,
                 count(DISTINCT CASE WHEN direction = 'incoming' THEN r END) AS in_degree,
                 count(DISTINCT CASE WHEN direction = 'outgoing' THEN r END) AS out_degree,
                 collect(DISTINCT {
                     entity_key: other.key,
                     entity_type: coalesce(other.type, [l IN labels(other) WHERE l <> 'FIR'][0], 'UNKNOWN'),
                     canonical_value: coalesce(other.canonical_value, other.value, other.name, other.key),
                     relationship_type: type(r),
                     direction: direction,
                     fir_id: r.fir_id
                 }) AS connected_entities,
                 collect(DISTINCT {
                     relationship_type: type(r),
                     source_key: startNode(r).key,
                     target_key: endNode(r).key,
                     fir_id: r.fir_id,
                     page: r.page,
                     evidence: r.evidence,
                     confidence: r.confidence
                 }) AS provenance_list
            WHERE degree > 0
            RETURN e.key AS entity_key,
                   coalesce(e.type, [l IN labels(e) WHERE l <> 'FIR'][0], 'UNKNOWN') AS entity_type,
                   coalesce(e.canonical_value, e.value, e.name, e.key) AS canonical_value,
                   degree,
                   in_degree,
                   out_degree,
                   connected_entities,
                   provenance_list
            ORDER BY degree DESC, entity_key ASC
            LIMIT 20
            """
            hce_results = session.run(hce_query, fir_id=fir_id)
            highly_connected: List[HighlyConnectedEntity] = []
            for rec in hce_results:
                conns = [
                    ConnectedEntityInfo(
                        entity_key=c["entity_key"],
                        entity_type=c["entity_type"],
                        canonical_value=c["canonical_value"],
                        relationship_type=c["relationship_type"],
                        direction=c["direction"],
                        fir_id=c.get("fir_id") or "UNKNOWN",
                    )
                    for c in rec["connected_entities"]
                ]
                provs = [
                    RelationshipProvenance(
                        relationship_type=p["relationship_type"],
                        source_key=p["source_key"],
                        target_key=p["target_key"],
                        fir_id=p.get("fir_id") or "UNKNOWN",
                        page=p.get("page"),
                        evidence=p.get("evidence"),
                        confidence=float(p["confidence"]) if p.get("confidence") is not None else None,
                    )
                    for p in rec["provenance_list"]
                ]
                highly_connected.append(
                    HighlyConnectedEntity(
                        entity_key=rec["entity_key"],
                        entity_type=rec["entity_type"],
                        canonical_value=rec["canonical_value"],
                        degree=rec["degree"],
                        in_degree=rec["in_degree"],
                        out_degree=rec["out_degree"],
                        connected_entities=conns,
                        provenance=provs,
                    )
                )

            # ------------------------------------------------------------------
            # Signal 2: Repeated Entities
            # Entities appearing across >= 2 distinct FIRs (excluding Location and FIR)
            # ------------------------------------------------------------------
            rep_query = """
            MATCH (f:FIR)-[:CONTAINS]->(e)
            WHERE NOT e:FIR AND NOT e:Location
              AND ($fir_id IS NULL OR EXISTS {
                  MATCH (:FIR {fir_id: $fir_id})-[:CONTAINS]->(e)
              })
            WITH e, collect(DISTINCT f) AS fir_nodes
            WHERE size(fir_nodes) >= 2
            OPTIONAL MATCH (s)-[r]->(t)
            WHERE (s.key = e.key OR t.key = e.key) AND type(r) <> 'CONTAINS'
            RETURN e.key AS entity_key,
                   coalesce(e.type, [l IN labels(e) WHERE l <> 'FIR'][0], 'UNKNOWN') AS entity_type,
                   coalesce(e.canonical_value, e.value, e.name, e.key) AS canonical_value,
                   [f IN fir_nodes | f.fir_id] AS fir_ids,
                   [f IN fir_nodes | {fir_id: f.fir_id, filename: f.filename}] AS fir_meta,
                   collect(DISTINCT {
                       rel_id: elementId(r),
                       rel_type: type(r),
                       fir_id: r.fir_id,
                       page: r.page,
                       evidence: r.evidence,
                       confidence: r.confidence,
                       source_key: s.key,
                       target_key: t.key
                   }) AS rels
            ORDER BY size(fir_ids) DESC, canonical_value ASC
            """
            rep_results = session.run(rep_query, fir_id=fir_id)
            repeated_entities: List[RepeatedEntity] = []
            for rec in rep_results:
                fir_ids = rec["fir_ids"]
                fir_meta_map = {m["fir_id"]: m.get("filename") for m in rec["fir_meta"]}
                occurrences: List[RepeatedEntityOccurrence] = []
                rels = [r for r in rec.get("rels", []) if r.get("rel_type")]
                
                # Build occurrences per FIR
                for fid in fir_ids:
                    matching_rels = [r for r in rels if r.get("fir_id") == fid]
                    if matching_rels:
                        for mr in matching_rels:
                            other_k = mr["target_key"] if mr["source_key"] == rec["entity_key"] else mr["source_key"]
                            occurrences.append(
                                RepeatedEntityOccurrence(
                                    fir_id=fid,
                                    filename=fir_meta_map.get(fid),
                                    relationship_type=mr.get("rel_type"),
                                    connected_key=other_k,
                                    page=mr.get("page"),
                                    evidence=mr.get("evidence"),
                                    confidence=float(mr["confidence"]) if mr.get("confidence") is not None else None,
                                )
                            )
                    else:
                        occurrences.append(
                            RepeatedEntityOccurrence(
                                fir_id=fid,
                                filename=fir_meta_map.get(fid),
                                relationship_type=None,
                                connected_key=None,
                                page=None,
                                evidence=f"Contained in FIR {fid}",
                                confidence=1.0,
                            )
                        )

                repeated_entities.append(
                    RepeatedEntity(
                        entity_key=rec["entity_key"],
                        entity_type=rec["entity_type"],
                        canonical_value=rec["canonical_value"],
                        fir_count=len(fir_ids),
                        fir_ids=fir_ids,
                        occurrences=occurrences,
                    )
                )

            # ------------------------------------------------------------------
            # Signal 3: 2-Hop Candidate Relationships
            # Indirect linkage paths: (s)-[r1]-(m)-[r2]-(t)
            # ------------------------------------------------------------------
            hop_query = """
            MATCH (s)-[r1]-(m)-[r2]-(t)
            WHERE NOT s:FIR AND NOT m:FIR AND NOT t:FIR
              AND type(r1) <> 'CONTAINS' AND type(r2) <> 'CONTAINS'
              AND elementId(s) < elementId(t)
              AND s.key <> t.key AND s.key <> m.key AND m.key <> t.key
              AND ($fir_id IS NULL OR r1.fir_id = $fir_id OR r2.fir_id = $fir_id)
            RETURN s.key AS source_key,
                   coalesce(s.type, [l IN labels(s) WHERE l <> 'FIR'][0], 'UNKNOWN') AS source_type,
                   coalesce(s.canonical_value, s.value, s.name, s.key) AS source_canonical,
                   m.key AS intermediary_key,
                   coalesce(m.type, [l IN labels(m) WHERE l <> 'FIR'][0], 'UNKNOWN') AS intermediary_type,
                   coalesce(m.canonical_value, m.value, m.name, m.key) AS intermediary_canonical,
                   t.key AS target_key,
                   coalesce(t.type, [l IN labels(t) WHERE l <> 'FIR'][0], 'UNKNOWN') AS target_type,
                   coalesce(t.canonical_value, t.value, t.name, t.key) AS target_canonical,
                   type(r1) AS hop1_type,
                   startNode(r1).key AS hop1_src,
                   endNode(r1).key AS hop1_tgt,
                   r1.fir_id AS hop1_fir,
                   r1.page AS hop1_page,
                   r1.evidence AS hop1_evidence,
                   r1.confidence AS hop1_confidence,
                   type(r2) AS hop2_type,
                   startNode(r2).key AS hop2_src,
                   endNode(r2).key AS hop2_tgt,
                   r2.fir_id AS hop2_fir,
                   r2.page AS hop2_page,
                   r2.evidence AS hop2_evidence,
                   r2.confidence AS hop2_confidence
            ORDER BY s.key, t.key
            LIMIT 50
            """
            hop_results = session.run(hop_query, fir_id=fir_id)
            two_hop_relationships: List[TwoHopPath] = []
            for rec in hop_results:
                s_can = rec["source_canonical"]
                m_can = rec["intermediary_canonical"]
                t_can = rec["target_canonical"]
                h1_type = rec["hop1_type"]
                h2_type = rec["hop2_type"]

                arrow1 = f"--[{h1_type}]-->" if rec["hop1_src"] == rec["source_key"] else f"<--[{h1_type}]--"
                arrow2 = f"--[{h2_type}]-->" if rec["hop2_src"] == rec["intermediary_key"] else f"<--[{h2_type}]--"
                desc = f"{s_can} ({rec['source_type']}) {arrow1} {m_can} ({rec['intermediary_type']}) {arrow2} {t_can} ({rec['target_type']})"

                p1 = RelationshipProvenance(
                    relationship_type=h1_type,
                    source_key=rec["hop1_src"],
                    target_key=rec["hop1_tgt"],
                    fir_id=rec.get("hop1_fir") or "UNKNOWN",
                    page=rec.get("hop1_page"),
                    evidence=rec.get("hop1_evidence"),
                    confidence=float(rec["hop1_confidence"]) if rec.get("hop1_confidence") is not None else None,
                )
                p2 = RelationshipProvenance(
                    relationship_type=h2_type,
                    source_key=rec["hop2_src"],
                    target_key=rec["hop2_tgt"],
                    fir_id=rec.get("hop2_fir") or "UNKNOWN",
                    page=rec.get("hop2_page"),
                    evidence=rec.get("hop2_evidence"),
                    confidence=float(rec["hop2_confidence"]) if rec.get("hop2_confidence") is not None else None,
                )

                two_hop_relationships.append(
                    TwoHopPath(
                        source_key=rec["source_key"],
                        source_canonical=s_can,
                        source_type=rec["source_type"],
                        intermediary_key=rec["intermediary_key"],
                        intermediary_canonical=m_can,
                        intermediary_type=rec["intermediary_type"],
                        target_key=rec["target_key"],
                        target_canonical=t_can,
                        target_type=rec["target_type"],
                        hop1_relationship=h1_type,
                        hop2_relationship=h2_type,
                        hop1_provenance=p1,
                        hop2_provenance=p2,
                        path_description=desc,
                    )
                )

            # ------------------------------------------------------------------
            # Signal 4: Potential Bridge / Intermediary Entities
            # Entities connecting pairs of neighbors with no direct domain relationship
            # ------------------------------------------------------------------
            bridge_query = """
            MATCH (u)-[r1]-(m)-[r2]-(w)
            WHERE NOT u:FIR AND NOT m:FIR AND NOT w:FIR
              AND type(r1) <> 'CONTAINS' AND type(r2) <> 'CONTAINS'
              AND elementId(u) < elementId(w)
              AND u.key <> w.key AND u.key <> m.key AND m.key <> w.key
              AND NOT EXISTS { MATCH (u)-[r_dir]-(w) WHERE type(r_dir) <> 'CONTAINS' }
              AND ($fir_id IS NULL OR r1.fir_id = $fir_id OR r2.fir_id = $fir_id)
            RETURN m.key AS intermediary_key,
                   coalesce(m.type, [l IN labels(m) WHERE l <> 'FIR'][0], 'UNKNOWN') AS intermediary_type,
                   coalesce(m.canonical_value, m.value, m.name, m.key) AS intermediary_canonical,
                   u.key AS u_key,
                   coalesce(u.type, [l IN labels(u) WHERE l <> 'FIR'][0], 'UNKNOWN') AS u_type,
                   coalesce(u.canonical_value, u.value, u.name, u.key) AS u_canonical,
                   r1.fir_id AS fir_u,
                   type(r1) AS r1_type,
                   r1.page AS r1_page,
                   r1.evidence AS r1_evidence,
                   r1.confidence AS r1_confidence,
                   startNode(r1).key AS r1_src,
                   endNode(r1).key AS r1_tgt,
                   w.key AS w_key,
                   coalesce(w.type, [l IN labels(w) WHERE l <> 'FIR'][0], 'UNKNOWN') AS w_type,
                   coalesce(w.canonical_value, w.value, w.name, w.key) AS w_canonical,
                   r2.fir_id AS fir_w,
                   type(r2) AS r2_type,
                   r2.page AS r2_page,
                   r2.evidence AS r2_evidence,
                   r2.confidence AS r2_confidence,
                   startNode(r2).key AS r2_src,
                   endNode(r2).key AS r2_tgt
            ORDER BY intermediary_key
            """
            bridge_results = session.run(bridge_query, fir_id=fir_id)
            bridge_map: Dict[str, Dict[str, Any]] = {}
            for rec in bridge_results:
                m_key = rec["intermediary_key"]
                if m_key not in bridge_map:
                    bridge_map[m_key] = {
                        "entity_key": m_key,
                        "entity_type": rec["intermediary_type"],
                        "canonical_value": rec["intermediary_canonical"],
                        "firs": set(),
                        "pairs": [],
                    }

                fir_u = rec["fir_u"]
                fir_w = rec["fir_w"]
                if fir_u:
                    bridge_map[m_key]["firs"].add(fir_u)
                if fir_w:
                    bridge_map[m_key]["firs"].add(fir_w)

                is_cross = bool(fir_u and fir_w and fir_u != fir_w)
                u_can = rec["u_canonical"]
                w_can = rec["w_canonical"]
                expl = (
                    f"Connects '{u_can}' ({rec['u_type']}) and '{w_can}' ({rec['w_type']}) "
                    f"{'across distinct FIRs (' + fir_u + ' and ' + fir_w + ')' if is_cross else 'within ' + str(fir_u)} "
                    f"without a direct relationship between them."
                )

                hop_a_prov = RelationshipProvenance(
                    relationship_type=rec["r1_type"],
                    source_key=rec["r1_src"],
                    target_key=rec["r1_tgt"],
                    fir_id=fir_u or "UNKNOWN",
                    page=rec.get("r1_page"),
                    evidence=rec.get("r1_evidence"),
                    confidence=float(rec["r1_confidence"]) if rec.get("r1_confidence") is not None else None,
                )
                hop_b_prov = RelationshipProvenance(
                    relationship_type=rec["r2_type"],
                    source_key=rec["r2_src"],
                    target_key=rec["r2_tgt"],
                    fir_id=fir_w or "UNKNOWN",
                    page=rec.get("r2_page"),
                    evidence=rec.get("r2_evidence"),
                    confidence=float(rec["r2_confidence"]) if rec.get("r2_confidence") is not None else None,
                )

                bridge_map[m_key]["pairs"].append(
                    BridgedEntityPair(
                        entity_a_key=rec["u_key"],
                        entity_a_canonical=u_can,
                        entity_a_type=rec["u_type"],
                        entity_b_key=rec["w_key"],
                        entity_b_canonical=w_can,
                        entity_b_type=rec["w_type"],
                        fir_a=fir_u,
                        fir_b=fir_w,
                        is_cross_fir=is_cross,
                        hop_a_provenance=hop_a_prov,
                        hop_b_provenance=hop_b_prov,
                        explanation=expl,
                    )
                )

            potential_bridges: List[BridgeEntity] = []
            for b in bridge_map.values():
                sorted_firs = sorted(list(b["firs"]))
                score = len(b["pairs"])
                expl_node = (
                    f"Potential Connecting Entity: Structurally links {score} entity pair(s) across "
                    f"{'multiple FIRs (' + ', '.join(sorted_firs) + ')' if len(sorted_firs) > 1 else (sorted_firs[0] if sorted_firs else 'knowledge base')} "
                    f"where no direct link exists between the paired entities."
                )
                potential_bridges.append(
                    BridgeEntity(
                        entity_key=b["entity_key"],
                        entity_type=b["entity_type"],
                        canonical_value=b["canonical_value"],
                        signal_label="Potential Bridge / Intermediary",
                        bridge_score=score,
                        connected_firs=sorted_firs,
                        bridged_pairs=b["pairs"],
                        explanation=expl_node,
                    )
                )

            # Sort bridges: cross-FIR bridges first, then by bridge score
            potential_bridges.sort(
                key=lambda b: (len([p for p in b.bridged_pairs if p.is_cross_fir]), b.bridge_score),
                reverse=True,
            )

            total_sig = (
                len(highly_connected)
                + len(repeated_entities)
                + len(two_hop_relationships)
                + len(potential_bridges)
            )

            return GraphAnalysisResponse(
                fir_id=fir_id,
                highly_connected_entities=highly_connected,
                repeated_entities=repeated_entities,
                two_hop_relationships=two_hop_relationships,
                potential_bridges=potential_bridges,
                total_signals=total_sig,
            )

    def close(self):
        """Closes the active Neo4j driver connection."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
