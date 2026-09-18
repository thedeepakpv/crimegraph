import os
from fastapi import APIRouter, HTTPException, status
from models.schemas import ExtractionRequest, ExtractionResult
from services.extraction_service import (
    ExtractionService,
    ExtractionValidationError,
    ConfigurationError,
    LLMProviderError,
)

router = APIRouter(prefix="/api/extraction", tags=["extraction"])
extraction_service = ExtractionService()


@router.get("/status")
def get_extraction_service_status():
    """Returns the current LLM configuration and available modes."""
    has_api_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY"))
    demo_mode_forced = os.getenv("DEMO_MODE", "true").strip().lower() in ("true", "1", "yes")

    default_mode = "demo" if (demo_mode_forced or not has_api_key) else "ai"

    return {
        "status": "ready",
        "default_mode": default_mode,
        "ai_available": has_api_key,
        "demo_available": True
    }


@router.post("/extract", response_model=ExtractionResult)
async def extract_entities_and_relationships(request: ExtractionRequest):
    """
    Accepts page-level text structure (from Phase 2 PDF extraction)
    and extracts validated entities, relationships, and provenance.
    """
    if not request.pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request must contain at least one page with text."
        )

    try:
        result = await extraction_service.extract_from_pages(
            filename=request.filename,
            pages=request.pages,
            fir_id=request.fir_id,
            force_mode=request.force_mode,
        )
        return result
    except ConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ExtractionValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Extraction validation failed: {str(e)}"
        )
    except LLMProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM Provider error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected extraction error: {str(e)}"
        )
