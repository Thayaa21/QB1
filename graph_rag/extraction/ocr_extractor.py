"""
OCR Extractor — Image/PDF to Entity
=====================================
Processes image and PDF files using:

STEP 1: pytesseract (OCR) — fast Python, NO LLM needed
    - Converts image/PDF pixels → raw text
    - Rule-based regex parsing extracts common fields
    - Takes ~0.5-2 seconds per page

STEP 2: LLM (verifier only) — light verification pass
    - Receives: raw OCR text + regex-extracted fields
    - Task: verify/correct fields, NOT re-extract from scratch
    - Much cheaper than full extraction (shorter prompt, focused task)
    - Takes ~3-5 seconds (vs 15-30s for full LLM extraction)

Why this approach?
    Full LLM extraction: LLM reads raw pixels/text and extracts everything
    → slow, expensive, sometimes hallucinates

    OCR + LLM verify: Python does the heavy lifting (fast, deterministic),
    LLM just double-checks and fixes errors
    → fast, cheap, accurate
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..core.models import Document, DocType, Entity, EntityType
from ..llm.provider import LLMProvider, LLMProviderError
from .classifier import DOC_TYPE_SCHEMAS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OCR helpers
# ---------------------------------------------------------------------------

def _image_to_text(file_path: Path) -> str:
    """
    Convert an image or PDF to raw text using pytesseract OCR.

    Supports: PNG, JPG, JPEG, TIFF, BMP, PDF

    Returns raw OCR text string.
    """
    suffix = file_path.suffix.lower()

    try:
        import pytesseract
        from PIL import Image

        if suffix == ".pdf":
            # Convert PDF pages to images first
            try:
                from pdf2image import convert_from_path
                pages = convert_from_path(str(file_path), dpi=300)
                texts = []
                for page in pages:
                    texts.append(pytesseract.image_to_string(page, lang="eng"))
                return "\n".join(texts)
            except ImportError:
                # pdf2image not installed — try reading as image directly
                logger.warning("pdf2image not installed, trying direct PIL open")
                img = Image.open(file_path)
                return pytesseract.image_to_string(img, lang="eng")
        else:
            img = Image.open(file_path)
            return pytesseract.image_to_string(img, lang="eng")

    except ImportError:
        raise RuntimeError(
            "pytesseract or Pillow not installed. "
            "Run: pip install pytesseract Pillow pdf2image"
        )
    except Exception as e:
        raise RuntimeError(f"OCR failed for {file_path.name}: {e}")


def _text_to_lines(text: str) -> list[str]:
    """Split OCR text into clean lines, removing empty ones."""
    return [line.strip() for line in text.split("\n") if line.strip()]


# ---------------------------------------------------------------------------
# Rule-based field extraction (no LLM)
# ---------------------------------------------------------------------------

def _regex_extract(text: str) -> dict[str, str]:
    """
    Fast rule-based extraction using regex patterns.
    No LLM needed — pure Python pattern matching.

    Returns dict of {field_name: value} for fields that matched.
    """
    fields: dict[str, str] = {}
    text_lower = text.lower()

    # ---- Date of Birth ----
    dob_patterns = [
        r"(?:date of birth|dob|birth date|born)[:\s]+([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
        r"(?:date of birth|dob|birth date|born)[:\s]+([A-Z][a-z]+ [0-9]{1,2},? [0-9]{4})",
        r"(?:date of birth|dob)[:\s]+([0-9]{4}[\/\-][0-9]{1,2}[\/\-][0-9]{1,2})",
    ]
    for pat in dob_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            fields["dob"] = m.group(1).strip()
            break

    # ---- Full Name ----
    name_patterns = [
        r"(?:full name|name|surname.*given)[:\s]+([A-Z][a-z]+(?: [A-Z][a-z]+){1,3})",
        r"(?:full name|name)[:\s]+([A-Z][A-Z ]+)",  # ALL CAPS passports
    ]
    for pat in name_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            fields["name"] = m.group(1).strip().title()
            break

    # ---- Passport Number ----
    m = re.search(
        r"(?:passport\s*(?:no|number|#)?)[:\s]*([A-Z]{1,2}[0-9]{6,9})",
        text, re.IGNORECASE
    )
    if m:
        fields["passport_number"] = m.group(1).strip().upper()

    # ---- License Number ----
    m = re.search(
        r"(?:licence|license)\s*(?:no|number|#)?[:\s]*([A-Z0-9\-]{5,15})",
        text, re.IGNORECASE
    )
    if m:
        fields["license_number"] = m.group(1).strip().upper()

    # ---- Expiry Date ----
    m = re.search(
        r"(?:expiry|expiration|date of expiry|valid until|expires?)[:\s]*"
        r"([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}"
        r"|[A-Z][a-z]+ [0-9]{1,2},? [0-9]{4})",
        text, re.IGNORECASE
    )
    if m:
        fields["expiry_date"] = m.group(1).strip()

    # ---- Nationality ----
    m = re.search(r"(?:nationality|citizenship)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", text, re.IGNORECASE)
    if m:
        fields["nationality"] = m.group(1).strip()

    # ---- Place of birth ----
    m = re.search(r"(?:place of birth|pob)[:\s]+([A-Z][a-zA-Z\s,]+)", text, re.IGNORECASE)
    if m:
        fields["place_of_birth"] = m.group(1).strip()

    # ---- Address ----
    m = re.search(
        r"(?:address|addr)[:\s]+(.{10,80}(?:street|st|avenue|ave|road|rd|drive|dr|"
        r"crescent|blvd|boulevard|way|lane|ln)[^,\n]*(?:,\s*[^\n]{3,40})?)",
        text, re.IGNORECASE
    )
    if m:
        fields["address"] = m.group(1).strip()

    # ---- MRZ (Machine Readable Zone on passports) — very reliable ----
    # MRZ line format: P<COUNTRYNAME<<GIVEN<<NAMES<<<...
    mrz_match = re.search(r"P<([A-Z]{3})([A-Z<]+)", text)
    if mrz_match and "name" not in fields:
        country = mrz_match.group(1)
        name_part = mrz_match.group(2).replace("<", " ").strip()
        if name_part:
            fields["name"] = name_part.title()
        if "nationality" not in fields:
            fields["nationality"] = country

    return fields


# ---------------------------------------------------------------------------
# LLM verifier prompt
# ---------------------------------------------------------------------------

_VERIFY_PROMPT = """\
You are a document verification assistant.

Below is:
1. RAW OCR TEXT from a scanned document
2. FIELDS already extracted by a regex parser

Your task: Review the extracted fields and CORRECT any errors.
Return ONLY a JSON object with the corrected field values.
Keep fields that look correct. Fix obvious OCR errors (0→O, 1→l, etc.).
Add any clearly visible fields that were missed.
Do NOT hallucinate — only use information visible in the OCR text.

OCR TEXT:
{ocr_text}

REGEX-EXTRACTED FIELDS:
{regex_fields}

DOCUMENT TYPE: {doc_type}

Return JSON only (no explanation):
{{"name": "...", "dob": "...", ...}}"""


# ---------------------------------------------------------------------------
# Main OCR Extractor class
# ---------------------------------------------------------------------------

class OCRExtractor:
    """
    Extracts entities from images/PDFs using OCR + LLM verification.

    Pipeline:
    1. pytesseract converts image → raw text (fast, no LLM)
    2. regex patterns extract common fields (fast, no LLM)
    3. LLM verifies/corrects the regex results (light, fast)
    4. Returns Entity with provenance

    Usage:
        extractor = OCRExtractor(llm_provider)
        doc, entities = extractor.extract("passport.jpg", person_name="thayaananthan")
    """

    def __init__(self, llm_provider: LLMProvider, model_name: str = "unknown"):
        self._llm        = llm_provider
        self._model_name = model_name

    def extract(
        self,
        file_path:   str | Path,
        person_name: str = "",
        doc_type_hint: Optional[DocType] = None,
    ) -> tuple[Optional[Document], list[Entity]]:
        """
        Extract entities from an image or PDF file.

        Args:
            file_path     — path to image/PDF
            person_name   — optional hint for the person's name
            doc_type_hint — optional hint for document type

        Returns:
            (Document, list[Entity]) — ready for KnowledgeGraphBuilder
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error("File not found: %s", file_path)
            return None, []

        # Step 1: OCR → raw text
        try:
            raw_text = _image_to_text(file_path)
            logger.info("OCR extracted %d chars from %s", len(raw_text), file_path.name)
        except RuntimeError as e:
            logger.error("OCR failed: %s", e)
            return None, []

        if not raw_text.strip():
            logger.warning("OCR returned empty text for %s", file_path.name)
            return None, []

        # Step 2: Rule-based extraction (fast, no LLM)
        regex_fields = _regex_extract(raw_text)
        logger.info("Regex extracted %d fields: %s", len(regex_fields), list(regex_fields.keys()))

        # Step 3: Detect document type from OCR text
        doc_type = doc_type_hint or self._detect_doc_type(raw_text)

        # Step 4: LLM verification (light pass — just corrects, doesn't re-extract)
        verified_fields = self._verify_with_llm(raw_text, regex_fields, doc_type)
        logger.info("After LLM verify: %d fields", len(verified_fields))

        # Step 5: Build Document object from OCR text
        lines = raw_text.split("\n")
        line_offsets: list[int] = []
        pos = 0
        for line in lines:
            line_offsets.append(pos)
            pos += len(line) + 1
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]

        doc = Document(
            doc_id       = str(uuid.uuid4()),
            filename     = file_path.name,
            text         = raw_text,
            lines        = lines,
            paragraphs   = paragraphs,
            line_offsets = line_offsets,
            doc_type     = doc_type,
            doc_date     = None,
            empty        = False,
            metadata     = {
                "full_path":       str(file_path.resolve()),
                "ocr_char_count":  len(raw_text),
                "extractor":       "ocr+llm-verify",
                "person_name":     person_name,
            },
        )

        # Step 6: Build Entity
        name = (
            verified_fields.get("name")
            or person_name.replace("_", " ").title()
            or "Unknown"
        )

        # Find line number for the name in OCR text
        line_number, line_text = self._find_in_lines(name, lines)
        char_offset_start = line_offsets[line_number - 1] if line_number > 0 else 0

        # Compute confidence based on how many fields were found
        schema    = DOC_TYPE_SCHEMAS.get(doc_type.value, DOC_TYPE_SCHEMAS["GENERIC"])
        n_found   = sum(1 for k in schema if verified_fields.get(k))
        n_total   = len(schema)
        confidence = round(n_found / n_total, 2) if n_total > 0 else 0.5

        entity = Entity(
            entity_id            = str(uuid.uuid4()),
            name                 = name,
            entity_type          = EntityType.PERSON,
            attributes           = verified_fields,
            source_doc_id        = doc.doc_id,
            source_filename      = file_path.name,
            doc_type             = doc_type,
            line_number          = line_number,
            line_text            = line_text,
            paragraph_index      = 0,
            paragraph_text       = paragraphs[0] if paragraphs else "",
            char_offset_start    = char_offset_start,
            char_offset_end      = char_offset_start + len(line_text),
            extractor_model      = f"ocr+{self._model_name}",
            extraction_timestamp = datetime.now(timezone.utc).isoformat(),
            confidence           = confidence,
            embedding            = None,
        )

        return doc, [entity]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_doc_type(self, text: str) -> DocType:
        """Heuristic doc type detection from OCR text keywords."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["passport", "travel document", "p<"]):
            return DocType.PASSPORT
        if any(w in text_lower for w in ["driver", "licence", "license", "driving"]):
            return DocType.DRIVERS_LICENSE
        if any(w in text_lower for w in ["birth certificate", "certificate of birth", "registration no"]):
            return DocType.BIRTH_CERTIFICATE
        if any(w in text_lower for w in ["insurance", "policy", "premium", "coverage"]):
            return DocType.INSURANCE
        if any(w in text_lower for w in ["patient", "diagnosis", "prescription", "hospital"]):
            return DocType.MEDICAL_RECORD
        return DocType.GENERIC

    def _verify_with_llm(
        self,
        ocr_text:     str,
        regex_fields: dict[str, str],
        doc_type:     DocType,
    ) -> dict[str, str]:
        """
        Ask LLM to verify and correct regex-extracted fields.
        Short prompt — LLM only corrects, doesn't re-extract everything.
        """
        import json

        # Only send first 1500 chars of OCR to keep prompt short
        ocr_preview = ocr_text[:1500].strip()

        prompt = _VERIFY_PROMPT.format(
            ocr_text     = ocr_preview,
            regex_fields = json.dumps(regex_fields, indent=2),
            doc_type     = doc_type.value,
        )

        try:
            response = self._llm.complete(prompt, temperature=0.0)
            # Extract JSON from response
            start = response.find("{")
            end   = response.rfind("}") + 1
            if start >= 0 and end > start:
                corrected = json.loads(response[start:end])
                # Merge: prefer LLM corrections but keep regex fields not in LLM response
                merged = {**regex_fields, **corrected}
                # Remove null/empty values
                return {k: str(v) for k, v in merged.items() if v and str(v).strip()}
        except (json.JSONDecodeError, LLMProviderError, Exception) as e:
            logger.warning("LLM verification failed: %s — using regex fields only", e)

        return regex_fields

    def _find_in_lines(self, value: str, lines: list[str]) -> tuple[int, str]:
        """Find a value in document lines. Returns (line_number 1-indexed, line_text)."""
        if not value:
            return 0, ""
        for i, line in enumerate(lines):
            if value.lower() in line.lower():
                return i + 1, line
        return 0, ""
