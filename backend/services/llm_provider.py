import os
import re
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import httpx
from models.schemas import PageText

load_dotenv()


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class ConfigurationError(LLMProviderError):
    """Raised when required API keys or configs are missing."""
    pass


class BaseLLMProvider(ABC):
    @abstractmethod
    async def extract(self, fir_id: str, filename: str, pages: List[PageText]) -> Dict[str, Any]:
        """Extract entities and relationships from page-level text."""
        pass


class DemoLLMProvider(BaseLLMProvider):
    """
    Deterministic demo extractor providing exact, reproducible extractions
    for known FIR samples (FIR-001, FIR-002) and rule-based extraction for other inputs.
    """

    async def extract(self, fir_id: str, filename: str, pages: List[PageText]) -> Dict[str, Any]:
        normalized_id = fir_id.upper().replace(".PDF", "").strip()
        
        # 1. Deterministic extractions for standard sample FIRs
        if "FIR-001" in normalized_id or "0142" in normalized_id:
            return self._extract_fir_001(fir_id, filename)
        elif "FIR-002" in normalized_id or "0198" in normalized_id:
            return self._extract_fir_002(fir_id, filename)
        
        # 2. Rule-based fallback for arbitrary custom documents in Demo Mode
        return self._extract_generic(fir_id, filename, pages)

    def _extract_fir_001(self, fir_id: str, filename: str) -> Dict[str, Any]:
        return {
            "fir_id": "FIR-001",
            "filename": filename,
            "extraction_mode": "demo",
            "provider": "deterministic-demo-engine",
            "entities": [
                {"type": "PERSON", "value": "Rahul Menon"},
                {"type": "PERSON", "value": "K. Vijayan"},
                {"type": "PERSON", "value": "M. Thomas"},
                {"type": "PHONE", "value": "9876543210"},
                {"type": "VEHICLE", "value": "KL-11-AB-1234"},
                {"type": "LOCATION", "value": "Emerald Heights, Kozhikode"},
                {"type": "LOCATION", "value": "NH-66"},
                {"type": "LOCATION", "value": "Mavoor Road"}
            ],
            "relationships": [
                {
                    "source": {"type": "PERSON", "value": "Rahul Menon"},
                    "target": {"type": "PHONE", "value": "9876543210"},
                    "relationship": "USES",
                    "fir_id": "FIR-001",
                    "page": 2,
                    "evidence": "Rahul Menon was actively using mobile number 9876543210 to coordinate logistics.",
                    "confidence": 0.95
                },
                {
                    "source": {"type": "PERSON", "value": "Rahul Menon"},
                    "target": {"type": "VEHICLE", "value": "KL-11-AB-1234"},
                    "relationship": "OPERATES",
                    "fir_id": "FIR-001",
                    "page": 2,
                    "evidence": "The suspect was observed driving a dark grey sedan with registration number KL-11-AB-1234.",
                    "confidence": 0.95
                },
                {
                    "source": {"type": "PERSON", "value": "Rahul Menon"},
                    "target": {"type": "LOCATION", "value": "Mavoor Road"},
                    "relationship": "SEEN_AT",
                    "fir_id": "FIR-001",
                    "page": 2,
                    "evidence": "The vehicle was seen parked at Mavoor Road prior to departure toward the highway.",
                    "confidence": 0.90
                },
                {
                    "source": {"type": "PERSON", "value": "Rahul Menon"},
                    "target": {"type": "LOCATION", "value": "NH-66"},
                    "relationship": "SEEN_AT",
                    "fir_id": "FIR-001",
                    "page": 1,
                    "evidence": "During routine highway surveillance near NH-66 on 11-01-2026, the suspect Rahul Menon was observed coordinating suspicious cargo offloading.",
                    "confidence": 0.92
                }
            ]
        }

    def _extract_fir_002(self, fir_id: str, filename: str) -> Dict[str, Any]:
        return {
            "fir_id": "FIR-002",
            "filename": filename,
            "extraction_mode": "demo",
            "provider": "deterministic-demo-engine",
            "entities": [
                {"type": "PERSON", "value": "Arjun Das"},
                {"type": "PERSON", "value": "Rajesh Kumar"},
                {"type": "PHONE", "value": "9876543210"},
                {"type": "VEHICLE", "value": "KL-11-AB-1234"},
                {"type": "LOCATION", "value": "Beach Road, Calicut"}
            ],
            "relationships": [
                {
                    "source": {"type": "PERSON", "value": "Arjun Das"},
                    "target": {"type": "PHONE", "value": "9876543210"},
                    "relationship": "USES",
                    "fir_id": "FIR-002",
                    "page": 1,
                    "evidence": "Investigating officers found Arjun Das using contact number 9876543210.",
                    "confidence": 0.95
                },
                {
                    "source": {"type": "PERSON", "value": "Arjun Das"},
                    "target": {"type": "VEHICLE", "value": "KL-11-AB-1234"},
                    "relationship": "OPERATES",
                    "fir_id": "FIR-002",
                    "page": 1,
                    "evidence": "Furthermore, vehicle registration KL-11-AB-1234 was registered as associated transport used by Arjun Das for local distribution.",
                    "confidence": 0.93
                },
                {
                    "source": {"type": "PERSON", "value": "Arjun Das"},
                    "target": {"type": "LOCATION", "value": "Beach Road, Calicut"},
                    "relationship": "SEEN_AT",
                    "fir_id": "FIR-002",
                    "page": 1,
                    "evidence": "Name: Arjun Das\nAlias: Dasan\nAddress: Beach Road, Calicut",
                    "confidence": 0.88
                }
            ]
        }

    def _extract_generic(self, fir_id: str, filename: str, pages: List[PageText]) -> Dict[str, Any]:
        """Generic fallback for unindexed custom FIRs in demo mode."""
        entities = []
        relationships = []
        seen_entities = set()

        phone_regex = re.compile(r'\b(?:\+?\d{1,3}[- ]?)?\(?\d{3,4}\)?[- ]?\d{3}[- ]?\d{4}\b|\b\d{10}\b')
        vehicle_regex = re.compile(r'\b[A-Z]{2}[ -]?[0-9]{1,2}[ -]?[A-Z]{1,2}[ -]?[0-9]{4}\b')
        name_regex = re.compile(r'(?:Name|Suspect|Accused|Complainant):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)')

        for p in pages:
            # Detect phones
            for match in phone_regex.finditer(p.text):
                val = match.group().strip()
                if ("PHONE", val) not in seen_entities:
                    seen_entities.add(("PHONE", val))
                    entities.append({"type": "PHONE", "value": val})

            # Detect vehicles
            for match in vehicle_regex.finditer(p.text):
                val = match.group().strip()
                if ("VEHICLE", val) not in seen_entities:
                    seen_entities.add(("VEHICLE", val))
                    entities.append({"type": "VEHICLE", "value": val})

            # Detect names
            for match in name_regex.finditer(p.text):
                val = match.group(1).strip()
                if ("PERSON", val) not in seen_entities:
                    seen_entities.add(("PERSON", val))
                    entities.append({"type": "PERSON", "value": val})

        return {
            "fir_id": fir_id,
            "filename": filename,
            "extraction_mode": "demo",
            "provider": "rule-based-demo-fallback",
            "entities": entities,
            "relationships": relationships
        }


class GeminiLLMProvider(BaseLLMProvider):
    """
    Live LLM provider utilizing Gemini structured output via REST API.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")

    async def extract(self, fir_id: str, filename: str, pages: List[PageText]) -> Dict[str, Any]:
        if not self.api_key:
            raise ConfigurationError(
                "No LLM API key configured in environment. Set GEMINI_API_KEY or LLM_API_KEY, or switch to Demo Mode."
            )

        # Build prompt containing page-bounded text
        formatted_pages = []
        for p in pages:
            formatted_pages.append(f"=== PAGE {p.page_number} ===\n{p.text}\n")
        pages_content = "\n".join(formatted_pages)

        system_instruction = (
            "You are an AI investigative support tool extracting structured entities and relationships from FIR documents.\n"
            "CRITICAL RULES:\n"
            "1. Extract ONLY facts explicitly supported by the text. NEVER invent entities, relationships, or evidence.\n"
            "2. Preserve page provenance: each relationship MUST state the exact page number and verbatim quote in 'evidence'.\n"
            "3. Allowed entity types: PERSON, PHONE, VEHICLE, LOCATION, ORGANIZATION.\n"
            "4. Allowed relationship types: USES, OPERATES, SEEN_AT, ASSOCIATED_WITH, COMMUNICATED_WITH, COORDINATED_WITH, REGISTERED_TO, MEMBER_OF.\n"
            "5. Do NOT make legal conclusions or determine guilt. Use factual links (e.g. 'Rahul Menon' USES '9876543210').\n"
            "6. Output strictly valid JSON matching this schema:\n"
            "{\n"
            '  "entities": [{"type": "PERSON", "value": "Name"}],\n'
            '  "relationships": [\n'
            '    {\n'
            '      "source": {"type": "PERSON", "value": "Name"},\n'
            '      "target": {"type": "PHONE", "value": "Number"},\n'
            '      "relationship": "USES",\n'
            f'      "fir_id": "{fir_id}",\n'
            '      "page": 1,\n'
            '      "evidence": "verbatim text snippet",\n'
            '      "confidence": 0.95\n'
            '    }\n'
            '  ]\n'
            "}"
        )

        user_content = f"FIR Document ID: {fir_id}\nFilename: {filename}\n\n{pages_content}"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{system_instruction}\n\nDocument Text:\n{user_content}"}]}
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    raise LLMProviderError(f"Gemini API error ({resp.status_code}): {resp.text}")
                data = resp.json()
                text_response = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text_response)
                
                # Attach metadata
                parsed["fir_id"] = fir_id
                parsed["filename"] = filename
                parsed["extraction_mode"] = "ai"
                parsed["provider"] = "gemini-1.5-flash"
                return parsed
            except Exception as e:
                raise LLMProviderError(f"Failed to communicate with LLM provider: {str(e)}")
