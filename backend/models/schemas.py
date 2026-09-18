from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator


class PageText(BaseModel):
    page_number: int = Field(ge=1, description="1-indexed page number")
    text: str = Field(description="Extracted page text")
    character_count: int = Field(ge=0, description="Character count on page")


class PDFExtractionResponse(BaseModel):
    filename: str
    page_count: int = Field(ge=1)
    pages: List[PageText]
    combined_text: str
    status: str = "success"


class EntityType(str, Enum):
    PERSON = "PERSON"
    PHONE = "PHONE"
    VEHICLE = "VEHICLE"
    LOCATION = "LOCATION"
    ORGANIZATION = "ORGANIZATION"


class RelationshipType(str, Enum):
    USES = "USES"
    OPERATES = "OPERATES"
    SEEN_AT = "SEEN_AT"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    COMMUNICATED_WITH = "COMMUNICATED_WITH"
    COORDINATED_WITH = "COORDINATED_WITH"
    REGISTERED_TO = "REGISTERED_TO"
    MEMBER_OF = "MEMBER_OF"


class Entity(BaseModel):
    type: EntityType
    value: str = Field(min_length=1, description="Original extracted entity value")
    normalized_value: Optional[str] = Field(default=None, description="Canonical normalized representation")

    @field_validator("value")
    @classmethod
    def clean_value(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Entity value cannot be empty or whitespace only")
        return cleaned



class ExtractedRelationship(BaseModel):
    source: Entity
    target: Entity
    relationship: RelationshipType
    fir_id: str = Field(min_length=1)
    page: int = Field(ge=1, description="Supporting FIR page number")
    evidence: str = Field(min_length=3, description="Exact quote from supporting page")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 3:
            raise ValueError("Evidence text must be at least 3 characters long")
        return cleaned


class ExtractionRequest(BaseModel):
    filename: str
    fir_id: Optional[str] = None
    pages: List[PageText]
    force_mode: Optional[str] = None  # None, "demo", or "ai"


class ExtractionResult(BaseModel):
    fir_id: str
    filename: str
    entities: List[Entity]
    entities_by_type: Dict[str, List[str]]
    relationships: List[ExtractedRelationship]
    extraction_mode: str  # "ai" or "demo"
    provider: str
    status: str = "success"


class IngestionSummary(BaseModel):
    fir_id: str
    filename: str
    entities_created_or_matched: int
    relationships_created_or_matched: int
    fir_relationships_created: int
    status: str = "success"
    message: Optional[str] = None


class GraphStatusResponse(BaseModel):
    status: str  # "connected" or "unavailable"
    uri: Optional[str] = None
    database: Optional[str] = None
    message: Optional[str] = None


class GraphNode(BaseModel):
    key: str
    entity_type: str
    display_value: str
    canonical_value: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphRelationship(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    fir_id: str
    page: Optional[int] = None
    evidence: Optional[str] = None
    confidence: Optional[float] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphDataResponse(BaseModel):
    fir_id: str
    nodes: List[GraphNode]
    relationships: List[GraphRelationship]
    node_count: int
    relationship_count: int


class FIRItem(BaseModel):
    fir_id: str
    filename: Optional[str] = None
    created_at: Optional[str] = None
    last_analyzed: Optional[str] = None
    entity_count: Optional[int] = None


class FIRListResponse(BaseModel):
    firs: List[FIRItem]
    total_count: int


class HistoricalMatch(BaseModel):
    entity_key: str
    entity_type: str
    canonical_value: str
    current_fir_id: str
    historical_fir_id: str
    historical_filename: Optional[str] = None
    historical_relationship: Optional[str] = None
    source_key: Optional[str] = None
    target_key: Optional[str] = None
    page: Optional[int] = None
    evidence: Optional[str] = None
    confidence: Optional[float] = None


class HistoricalLookupResponse(BaseModel):
    current_fir_id: str
    matches: List[HistoricalMatch]
    total_matches: int
    shared_entity_count: int


# ==============================================================================
# Phase 8: Graph Analysis Schemas (P2 Signals)
# ==============================================================================

class ConnectedEntityInfo(BaseModel):
    entity_key: str
    entity_type: str
    canonical_value: str
    relationship_type: str
    direction: str  # "outgoing" or "incoming"
    fir_id: str


class RelationshipProvenance(BaseModel):
    relationship_type: str
    source_key: str
    target_key: str
    fir_id: str
    page: Optional[int] = None
    evidence: Optional[str] = None
    confidence: Optional[float] = None


class HighlyConnectedEntity(BaseModel):
    entity_key: str
    entity_type: str
    canonical_value: str
    degree: int = Field(ge=0, description="Total non-CONTAINS connections to non-FIR entities")
    in_degree: int = Field(ge=0)
    out_degree: int = Field(ge=0)
    connected_entities: List[ConnectedEntityInfo] = Field(default_factory=list)
    provenance: List[RelationshipProvenance] = Field(default_factory=list)


class RepeatedEntityOccurrence(BaseModel):
    fir_id: str
    filename: Optional[str] = None
    relationship_type: Optional[str] = None
    connected_key: Optional[str] = None
    page: Optional[int] = None
    evidence: Optional[str] = None
    confidence: Optional[float] = None


class RepeatedEntity(BaseModel):
    entity_key: str
    entity_type: str
    canonical_value: str
    fir_count: int = Field(ge=2, description="Count of distinct FIRs containing this entity")
    fir_ids: List[str]
    occurrences: List[RepeatedEntityOccurrence] = Field(default_factory=list)


class TwoHopPath(BaseModel):
    source_key: str
    source_canonical: str
    source_type: str
    intermediary_key: str
    intermediary_canonical: str
    intermediary_type: str
    target_key: str
    target_canonical: str
    target_type: str
    hop1_relationship: str
    hop2_relationship: str
    hop1_provenance: Optional[RelationshipProvenance] = None
    hop2_provenance: Optional[RelationshipProvenance] = None
    path_description: str


class BridgedEntityPair(BaseModel):
    entity_a_key: str
    entity_a_canonical: str
    entity_a_type: str
    entity_b_key: str
    entity_b_canonical: str
    entity_b_type: str
    fir_a: Optional[str] = None
    fir_b: Optional[str] = None
    is_cross_fir: bool = False
    hop_a_provenance: Optional[RelationshipProvenance] = None
    hop_b_provenance: Optional[RelationshipProvenance] = None
    explanation: str


class BridgeEntity(BaseModel):
    entity_key: str
    entity_type: str
    canonical_value: str
    signal_label: str = "Potential Bridge / Intermediary"
    bridge_score: int = Field(ge=0, description="Count of distinct entity pairs connected via this intermediary")
    connected_firs: List[str] = Field(default_factory=list)
    bridged_pairs: List[BridgedEntityPair] = Field(default_factory=list)
    explanation: str


class GraphAnalysisResponse(BaseModel):
    fir_id: Optional[str] = None  # None indicates full knowledge base analysis
    disclaimer: str = (
        "INVESTIGATIVE SIGNALS ONLY: These graph signals indicate structural network patterns "
        "(degrees, shared canonical attributes, 2-hop linkages, and potential connecting entities). "
        "They do NOT infer guilt, criminality, identity, or legal conclusions. All leads require "
        "independent human investigator verification."
    )
    highly_connected_entities: List[HighlyConnectedEntity] = Field(default_factory=list)
    repeated_entities: List[RepeatedEntity] = Field(default_factory=list)
    two_hop_relationships: List[TwoHopPath] = Field(default_factory=list)
    potential_bridges: List[BridgeEntity] = Field(default_factory=list)
    total_signals: int = 0


