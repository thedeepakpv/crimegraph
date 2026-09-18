from fastapi import APIRouter, HTTPException, status
from models.schemas import (
    ExtractionResult,
    IngestionSummary,
    GraphStatusResponse,
    GraphDataResponse,
    FIRListResponse,
    HistoricalLookupResponse,
    GraphAnalysisResponse,
)
from services.neo4j_service import (
    Neo4jService,
    Neo4jConnectionError,
    Neo4jServiceError,
    FIRNotFoundError,
)

router = APIRouter(prefix="/api/graph", tags=["graph"])
neo4j_service = Neo4jService()


@router.get("/status", response_model=GraphStatusResponse)
def get_graph_status():
    """Reports whether the Neo4j knowledge graph connection is available."""
    return neo4j_service.check_connection()


@router.get("/firs", response_model=FIRListResponse)
def get_available_firs():
    """Retrieves all available FIRs recorded in the knowledge graph."""
    try:
        return neo4j_service.get_firs()
    except Neo4jConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Neo4j database connection unavailable: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve FIR list: {str(e)}",
        )


@router.get("/analytics", response_model=GraphAnalysisResponse)
def get_global_graph_analytics():
    """
    Computes explainable, read-only graph analysis signals across all FIRs in the knowledge base:
    1. Highly connected entities (degree excluding FIR nodes and CONTAINS edges)
    2. Repeated entities across FIRs
    3. 2-hop candidate relationships
    4. Potential bridge / connecting entities
    """
    try:
        return neo4j_service.get_graph_analytics(fir_id=None)
    except Neo4jConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Neo4j database connection unavailable: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute graph analytics: {str(e)}",
        )


@router.get("/firs/{fir_id}/analytics", response_model=GraphAnalysisResponse)
def get_graph_analytics_for_fir(fir_id: str):
    """
    Computes explainable, read-only graph analysis signals scoped to a specific FIR:
    1. Highly connected entities in this FIR's network
    2. Repeated entities in this FIR that also appear in other FIRs
    3. 2-hop candidate relationships involving this FIR's entities
    4. Potential bridge / connecting entities linking this FIR to the wider graph
    """
    try:
        return neo4j_service.get_graph_analytics(fir_id=fir_id)
    except FIRNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Neo4jConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Neo4j database connection unavailable: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute graph analytics for '{fir_id}': {str(e)}",
        )


@router.get("/firs/{fir_id}", response_model=GraphDataResponse)
@router.get("/{fir_id}", response_model=GraphDataResponse)
def get_graph_by_fir(fir_id: str):
    """
    Retrieves the complete graph (nodes and relationships with provenance)
    for a specific FIR document.
    """
    try:
        return neo4j_service.get_graph_for_fir(fir_id)
    except FIRNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Neo4jConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Neo4j database connection unavailable: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve graph for '{fir_id}': {str(e)}",
        )


@router.get("/firs/{fir_id}/historical-connections", response_model=HistoricalLookupResponse)
def get_historical_connections_for_fir(fir_id: str):
    """
    Searches for candidate historical connections where canonical entities in this FIR
    were previously observed in other historical FIR records.
    """
    try:
        return neo4j_service.get_historical_connections(fir_id)
    except FIRNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Neo4jConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Neo4j database connection unavailable: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve historical connections for '{fir_id}': {str(e)}",
        )


@router.post("/ingest", response_model=IngestionSummary)
def ingest_into_knowledge_graph(result: ExtractionResult):
    """
    Ingests normalized entities, relationships, and FIR nodes into Neo4j
    using parameterized Cypher MERGE queries with strict evidence provenance.
    """
    try:
        summary = neo4j_service.ingest_extraction_result(result)
        return summary
    except Neo4jConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Neo4j database connection unavailable: {str(e)}",
        )
    except Neo4jServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to ingest graph data: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during graph ingestion: {str(e)}",
        )

