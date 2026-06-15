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

    Handles multi-line OCR artifacts (names split across lines),
    and driver's license specific fields like height, weight, eye color.
    """
    fields: dict[str, str] = {}

    # ---- Normalize text for easier matching ----
    # Join lines that look like they're part of the same field
    # (OCR often splits names across 2 lines)
    clean_lines = [l.strip() for l in text.split("\n") if l.strip()]
    clean_text  = " ".join(clean_lines)  # single line for regex

    # ---- Full Name ----
    # Handles: "LN KANAG FN THAYAANANTHAN", "LAST FIRST MIDDLE", "Name: John Smith"
    name_patterns = [
        r"(?:full name|name)[:\s]+([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){1,4})",
        # Driver license format: "LN SURNAME FN FIRSTNAME"
        r"LN\s+([A-Z]+)\s+FN\s+([A-Z]+)",
        # ALL CAPS name (passport / license machine readable)
        r"(?:^|\n)([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})?)\s*(?:\n|$)",
        # "SURNAME, FIRSTNAME" format
        r"([A-Z][A-Z\s]+),\s*([A-Z][A-Z\s]+)",
    ]
    for pat in name_patterns:
        m = re.search(pat, clean_text, re.IGNORECASE | re.MULTILINE)
        if m:
            if m.lastindex and m.lastindex >= 2:
                # LN/FN or LAST/FIRST format — combine
                parts = [g for g in m.groups() if g]
                name  = " ".join(p.strip().title() for p in parts)
            else:
                name = m.group(1).strip().title()
            # Filter out known non-name all-caps labels
            skip_words = {"CLASS", "DONOR", "STATE", "EXPIRES", "ISSUED", "LICENSE",
                          "DRIVER", "IDENTIFICATION", "ARIZONA", "CANADA", "PASSPORT"}
            if not any(w in name.upper() for w in skip_words) and len(name) > 3:
                fields["name"] = name
                break

    # ---- Date of Birth ----
    dob_patterns = [
        r"(?:date of birth|dob|birth date|born|DOB)[:\s]+([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
        r"(?:date of birth|dob|birth date|born)[:\s]+([A-Z][a-z]+ [0-9]{1,2},? [0-9]{4})",
        r"(?:date of birth|dob)[:\s]+([0-9]{4}[\/\-][0-9]{1,2}[\/\-][0-9]{1,2})",
        # Driver license: "DOB 01/03/2003" or standalone date after DOB label
        r"DOB\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
    ]
    for pat in dob_patterns:
        m = re.search(pat, clean_text, re.IGNORECASE)
        if m:
            fields["dob"] = m.group(1).strip()
            break

    # ---- Passport Number ----
    m = re.search(r"(?:passport\s*(?:no|number|#)?)[:\s]*([A-Z]{1,2}[0-9]{6,9})",
                  clean_text, re.IGNORECASE)
    if m:
        fields["passport_number"] = m.group(1).strip().upper()

    # ---- License Number ----
    # Arizona format: letter + 8 digits e.g. U10112277
    lic_patterns = [
        r"(?:licence|license|lic(?:ense)?\.?(?:\s*no)?)[:\s#]*([A-Z][0-9]{7,9})",
        r"\b([A-Z][0-9]{7,9})\b",   # standalone like U10112277
    ]
    for pat in lic_patterns:
        m = re.search(pat, clean_text, re.IGNORECASE)
        if m:
            fields["license_number"] = m.group(1).strip().upper()
            break

    # ---- Issue Date ----
    iss_patterns = [
        r"(?:issue\s*date|issued|iss)[:\s]+([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
        r"ISS\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
    ]
    for pat in iss_patterns:
        m = re.search(pat, clean_text, re.IGNORECASE)
        if m:
            fields["issue_date"] = m.group(1).strip()
            break

    # ---- Expiry Date ----
    exp_patterns = [
        r"(?:expiry|expiration|date of expiry|valid until|exp(?:ires?)?)[:\s]+([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})",
        r"EXP\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
    ]
    for pat in exp_patterns:
        m = re.search(pat, clean_text, re.IGNORECASE)
        if m:
            fields["expiry_date"] = m.group(1).strip()
            break

    # ---- Address ----
    m = re.search(
        r"(?:address|addr)[:\s]+(.{10,100}(?:[A-Z]{2}\s+\d{5}(?:-\d{4})?))",
        clean_text, re.IGNORECASE
    )
    if not m:
        # Try: any line with a US zip code pattern
        m = re.search(r"([A-Z][a-zA-Z\s,]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)", clean_text)
    if m:
        fields["address"] = m.group(1).strip()

    # ---- Sex / Gender ----
    m = re.search(r"(?:sex|gender)[:\s]+([MF](?:ale|emale)?)\b", clean_text, re.IGNORECASE)
    if not m:
        m = re.search(r"\bSEX\s+([MF])\b", clean_text)
    if m:
        val = m.group(1).strip().upper()
        fields["sex"] = "Male" if val.startswith("M") else "Female"

    # ---- Height ----
    # Formats: "5'8"", "508", "5-08", "HGT 508", "58" (5ft 8in)
    ht_patterns = [
        r"(?:hgt|height|ht)[:\s]+([0-9]['`]?\s*[0-9]{1,2}[\"'`]?(?:\s*in)?)",
        r"(?:hgt|height)[:\s]+([0-9]\-[0-9]{2})",  # 5-08 format
        r"\bHGT\s+([0-9]{3})\b",    # HGT 508 → 5'08"
        r"\bHGT\s+([0-9]{2})\b",    # HGT 58 → 5'8"
    ]
    for pat in ht_patterns:
        m = re.search(pat, clean_text, re.IGNORECASE)
        if m:
            ht = m.group(1).strip()
            # Normalize various formats to feet'inches"
            if re.match(r"^[0-9]{3}$", ht):
                # "508" → 5'08"
                ht = f"{ht[0]}'{ht[1:]}\""
            elif re.match(r"^[0-9]{2}$", ht):
                # "58" → 5'8"
                ht = f"{ht[0]}'{ht[1:]}\""
            elif re.match(r"^[0-9]-[0-9]{2}$", ht):
                # "5-08" → 5'08"
                ht = f"{ht[0]}'{ht[2:]}\""
            fields["height"] = ht
            break

    # ---- Weight ----
    wt_patterns = [
        r"(?:wgt|weight|wt)[:\s]+([0-9]{2,3}\s*(?:lbs?|kg)?)",
        r"\bWGT\s+([0-9]{2,3})\b",
    ]
    for pat in wt_patterns:
        m = re.search(pat, clean_text, re.IGNORECASE)
        if m:
            wt = m.group(1).strip()
            if not re.search(r"lbs?|kg", wt, re.I):
                wt += " lbs"
            fields["weight"] = wt
            break

    # ---- Eye Color ----
    m = re.search(r"(?:eyes?|eye\s*color|eye\s*colour|eyz?)[:\s]+([A-Z]{3,8})\b",
                  clean_text, re.IGNORECASE)
    if not m:
        m = re.search(r"\b(BRN|BLU|GRN|HAZ|GRY|BLK|AMB)\b", clean_text)
    if m:
        color_map = {"BRN": "BROWN", "BLU": "BLUE", "GRN": "GREEN",
                     "HAZ": "HAZEL", "GRY": "GRAY",  "BLK": "BLACK", "AMB": "AMBER"}
        val = m.group(1).upper()
        fields["eye_color"] = color_map.get(val, val.title())

    # ---- Vehicle Class ----
    m = re.search(r"(?:class|vehicle\s*class|lic\s*class)[:\s]+([A-Z])\b",
                  clean_text, re.IGNORECASE)
    if not m:
        m = re.search(r"\bCLASS\s+([A-Z])\b", clean_text)
    if m:
        fields["class"] = m.group(1).upper()

    # ---- State / Province abbreviation ----
    m = re.search(r"\b(AZ|CA|NY|TX|FL|BC|ON|AB|QC)\b", clean_text)
    if m:
        fields["state_abbreviation"] = m.group(1)

    # ---- Nationality (passports) ----
    m = re.search(r"(?:nationality|citizenship)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
                  clean_text, re.IGNORECASE)
    if m:
        fields["nationality"] = m.group(1).strip()

    # ---- Place of birth (passports) ----
    m = re.search(r"(?:place of birth|pob|birthplace)[:\s]+([A-Z][a-zA-Z\s,]+)",
                  clean_text, re.IGNORECASE)
    if m:
        fields["place_of_birth"] = m.group(1).strip()

    return fields


# ---------------------------------------------------------------------------
# LLM verifier prompt
# ---------------------------------------------------------------------------

_VERIFY_PROMPT = """\
You are a document verification assistant for identity documents.

Below is:
1. RAW OCR TEXT from a scanned document
2. FIELDS already extracted by a regex parser

Your task:
- Review the extracted fields and CORRECT errors
- Fix OCR artifacts: 0→O, 1→l, broken names across lines, etc.
- For NAMES: combine multi-line OCR names (e.g. "KANAG THAYAANA" + "NTHAN" → "Kanag Thayaananthan")
- For HEIGHT: normalize to feet/inches (e.g. "604" → "6'04\\"", "6-04" → "6'04\\"")
- For dates: use MM/DD/YYYY format as it appears on the document
- Do NOT hallucinate — only use information visible in the OCR text
- Return ONLY a JSON object, no explanation

OCR TEXT (first 1500 chars):
{ocr_text}

REGEX-EXTRACTED FIELDS:
{regex_fields}

DOCUMENT TYPE: {doc_type}

JSON only:"""


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
