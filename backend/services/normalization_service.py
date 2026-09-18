import re
from typing import Tuple, List, Optional
from models.schemas import (
    Entity,
    EntityType,
    ExtractedRelationship,
    RelationshipType,
)


class NormalizationError(Exception):
    """Raised when an entity value is invalid or cannot be normalized."""
    pass


def normalize_phone(raw: str) -> str:
    """
    Conservative normalization for phone numbers:
    - Strips whitespace, hyphens, dots, parentheses.
    - Strips '+91' or leading '0' prefix when followed by 10 digits.
    - Preserves exact digits without guessing missing numbers.
    """
    if not raw or not raw.strip():
        raise NormalizationError("Phone number cannot be empty.")

    cleaned = re.sub(r"[\s\-\(\)\.]+", "", raw.strip())

    # Standard Indian phone format handling
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]

    if not cleaned.isdigit():
        raise NormalizationError(f"Phone number contains invalid non-digit characters: '{raw}'")

    if len(cleaned) < 7 or len(cleaned) > 15:
        raise NormalizationError(f"Phone number '{raw}' has invalid length ({len(cleaned)} digits).")

    return cleaned


def normalize_vehicle(raw: str) -> str:
    """
    Conservative normalization for vehicle registration plates:
    - Strips whitespace, hyphens, dots.
    - Converts to standard canonical representation (e.g. 'KL-11-AB-1234').
    - Does NOT use fuzzy matching.
    """
    if not raw or not raw.strip():
        raise NormalizationError("Vehicle registration cannot be empty.")

    cleaned = re.sub(r"[\s\-\.]+", "", raw.strip()).upper()

    if len(cleaned) < 4 or len(cleaned) > 15 or not cleaned.isalnum():
        raise NormalizationError(f"Invalid vehicle registration format: '{raw}'")

    # Match standard Indian registration: 2 letters state, 1-2 digits district, 1-3 letters series, 1-4 digits number
    m = re.match(r"^([A-Z]{2})([0-9]{1,2})([A-Z]{1,3})([0-9]{1,4})$", cleaned)
    if m:
        state, dist, series, num = m.groups()
        return f"{state}-{int(dist):02d}-{series}-{int(num):04d}"

    return cleaned



def normalize_person(raw: str) -> str:
    """
    Conservative normalization for person names:
    - Trims leading/trailing whitespace.
    - Collapses repeated internal whitespace.
    - Applies consistent casing (Title Case) for uniform comparison.
    - Does NOT automatically merge similar-but-different names (e.g. 'Rahul Menon' != 'Rahul K. Menon').
    """
    if not raw or not raw.strip():
        raise NormalizationError("Person name cannot be empty.")

    tokens = raw.strip().split()
    normalized_tokens = []
    for t in tokens:
        # Preserve abbreviations/initials (e.g., 'K.', 'M.')
        if len(t) <= 2 and t.endswith("."):
            normalized_tokens.append(t.upper())
        elif len(t) == 1:
            normalized_tokens.append(t.upper())
        else:
            normalized_tokens.append(t.capitalize())

    return " ".join(normalized_tokens)


def normalize_location(raw: str) -> str:
    """
    Basic whitespace and comma normalization for locations.
    Does not attempt geocoding or spatial resolution.
    """
    if not raw or not raw.strip():
        raise NormalizationError("Location cannot be empty.")

    cleaned = re.sub(r"\s+", " ", raw.strip())
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    tokens = cleaned.split(" ")
    return " ".join(t.capitalize() if not t.isupper() else t for t in tokens)


def normalize_organization(raw: str) -> str:
    """
    Basic whitespace and casing normalization for organizations.
    """
    if not raw or not raw.strip():
        raise NormalizationError("Organization cannot be empty.")

    cleaned = re.sub(r"\s+", " ", raw.strip())
    tokens = cleaned.split(" ")
    return " ".join(t.capitalize() if not t.isupper() else t for t in tokens)


def normalize_entity_value(entity_type: EntityType, raw_value: str) -> str:
    """Dispatches to the appropriate normalizer based on EntityType."""
    if entity_type == EntityType.PHONE:
        return normalize_phone(raw_value)
    elif entity_type == EntityType.VEHICLE:
        return normalize_vehicle(raw_value)
    elif entity_type == EntityType.PERSON:
        return normalize_person(raw_value)
    elif entity_type == EntityType.LOCATION:
        return normalize_location(raw_value)
    elif entity_type == EntityType.ORGANIZATION:
        return normalize_organization(raw_value)
    else:
        # Fallback for any unknown entity type: clean whitespace
        return re.sub(r"\s+", " ", raw_value.strip())


class NormalizationService:
    """
    Dedicated service handling normalization of entities and relationships.
    Preserves original raw values while populating canonical normalized_value.
    """

    def normalize_entity(self, entity: Entity) -> Entity:
        """
        Normalizes an Entity while preserving the original extracted value.
        Returns a new Entity with both .value and .normalized_value.
        """
        canonical = normalize_entity_value(entity.type, entity.value)
        return Entity(
            type=entity.type,
            value=entity.value,
            normalized_value=canonical,
        )

    def normalize_relationship(self, rel: ExtractedRelationship) -> ExtractedRelationship:
        """
        Normalizes relationship source and target entities while preserving
        all provenance attributes (fir_id, page, evidence, confidence).
        """
        norm_source = self.normalize_entity(rel.source)
        norm_target = self.normalize_entity(rel.target)

        return ExtractedRelationship(
            source=norm_source,
            target=norm_target,
            relationship=rel.relationship,
            fir_id=rel.fir_id,
            page=rel.page,
            evidence=rel.evidence,
            confidence=rel.confidence,
        )

    def normalize_extraction(
        self,
        entities: List[Entity],
        relationships: List[ExtractedRelationship],
    ) -> Tuple[List[Entity], List[ExtractedRelationship]]:
        """
        Normalizes a complete set of extracted entities and relationships.
        Deduplicates entities based on (type, normalized_value).
        """
        seen_keys = set()
        normalized_entities: List[Entity] = []

        for ent in entities:
            norm_ent = self.normalize_entity(ent)
            key = (norm_ent.type.value, norm_ent.normalized_value)
            if key not in seen_keys:
                seen_keys.add(key)
                normalized_entities.append(norm_ent)

        normalized_relationships: List[ExtractedRelationship] = []
        for rel in relationships:
            norm_rel = self.normalize_relationship(rel)
            normalized_relationships.append(norm_rel)

            # Ensure both endpoints exist in normalized_entities
            for endpoint in (norm_rel.source, norm_rel.target):
                key = (endpoint.type.value, endpoint.normalized_value)
                if key not in seen_keys:
                    seen_keys.add(key)
                    normalized_entities.append(endpoint)

        return normalized_entities, normalized_relationships
