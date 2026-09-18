import os
from typing import Dict, Any, List, Optional
from models.schemas import (
    PageText,
    Entity,
    EntityType,
    ExtractedRelationship,
    RelationshipType,
    ExtractionResult,
)
from services.llm_provider import (
    BaseLLMProvider,
    DemoLLMProvider,
    GeminiLLMProvider,
    ConfigurationError,
    LLMProviderError,
)
from services.normalization_service import NormalizationService


class ExtractionValidationError(Exception):
    """Raised when extracted data fails validation."""
    pass


class ExtractionService:
    def __init__(
        self,
        demo_provider: Optional[BaseLLMProvider] = None,
        ai_provider: Optional[BaseLLMProvider] = None,
        normalization_service: Optional[NormalizationService] = None,
    ):
        self.demo_provider = demo_provider or DemoLLMProvider()
        self.ai_provider = ai_provider or GeminiLLMProvider()
        self.normalization_service = normalization_service or NormalizationService()


    def get_provider(self, force_mode: Optional[str] = None) -> BaseLLMProvider:
        """Determines whether to use AI or Demo provider based on configuration."""
        if force_mode:
            mode = force_mode.strip().lower()
            if mode == "demo":
                return self.demo_provider
            elif mode == "ai":
                return self.ai_provider
            else:
                raise ValueError(f"Invalid force_mode: '{force_mode}'. Must be 'demo' or 'ai'.")

        # Global env fallback: default to demo if DEMO_MODE=true or no API key
        demo_mode_env = os.getenv("DEMO_MODE", "true").strip().lower() in ("true", "1", "yes")
        has_api_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY"))

        if demo_mode_env or not has_api_key:
            return self.demo_provider
        return self.ai_provider

    async def extract_from_pages(
        self,
        filename: str,
        pages: List[PageText],
        fir_id: Optional[str] = None,
        force_mode: Optional[str] = None,
    ) -> ExtractionResult:
        if not pages:
            raise ExtractionValidationError("Cannot extract from empty pages list.")

        # Determine FIR ID from filename if not provided
        derived_fir_id = fir_id or filename.rsplit(".", 1)[0].strip()

        provider = self.get_provider(force_mode)

        # Execute extraction
        raw_result = await provider.extract(
            fir_id=derived_fir_id,
            filename=filename,
            pages=pages,
        )

        # Validate and structure response
        return self._validate_and_build_result(
            raw_result=raw_result,
            derived_fir_id=derived_fir_id,
            filename=filename,
        )

    def _validate_and_build_result(
        self,
        raw_result: Dict[str, Any],
        derived_fir_id: str,
        filename: str,
    ) -> ExtractionResult:
        raw_entities = raw_result.get("entities", [])
        raw_relationships = raw_result.get("relationships", [])
        extraction_mode = raw_result.get("extraction_mode", "demo")
        provider_name = raw_result.get("provider", "unknown")

        # 1. Validate Entities
        validated_entities: List[Entity] = []
        for item in raw_entities:
            try:
                entity = Entity.model_validate(item)
                validated_entities.append(entity)
            except Exception as e:
                raise ExtractionValidationError(f"Invalid entity format: {item}. Details: {e}")

        # 2. Validate Relationships
        validated_relationships: List[ExtractedRelationship] = []
        for rel in raw_relationships:
            try:
                # Ensure relationship fir_id is populated
                if "fir_id" not in rel or not rel["fir_id"]:
                    rel["fir_id"] = derived_fir_id

                extracted_rel = ExtractedRelationship.model_validate(rel)
                validated_relationships.append(extracted_rel)
            except Exception as e:
                raise ExtractionValidationError(f"Invalid relationship format: {rel}. Details: {e}")

        # 3. Apply Conservative Normalization
        try:
            normalized_entities, normalized_relationships = self.normalization_service.normalize_extraction(
                validated_entities, validated_relationships
            )
        except Exception as e:
            raise ExtractionValidationError(f"Normalization failed: {e}")

        # 4. Group canonical entities by type for API response
        entities_by_type: Dict[str, List[str]] = {
            t.value: [] for t in EntityType
        }
        for ent in normalized_entities:
            canonical_val = ent.normalized_value or ent.value
            if canonical_val not in entities_by_type[ent.type.value]:
                entities_by_type[ent.type.value].append(canonical_val)

        return ExtractionResult(
            fir_id=derived_fir_id,
            filename=filename,
            entities=normalized_entities,
            entities_by_type=entities_by_type,
            relationships=normalized_relationships,
            extraction_mode=extraction_mode,
            provider=provider_name,
            status="success",
        )

