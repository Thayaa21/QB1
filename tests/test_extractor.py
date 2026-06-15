"""
Tests for LangChainExtractor and UiPathExtractor.
"""

import json
import uuid
from pathlib import Path

import pytest

from tests.conftest import MockLLMProvider
from graph_rag.extraction.langchain_extractor import LangChainExtractor
from graph_rag.extraction.uipath_extractor import UiPathExtractor
from graph_rag.extraction.classifier import DOC_TYPE_SCHEMAS
from graph_rag.core.models import DocType, Document, EntityType


def make_doc(text, doc_type=DocType.BIRTH_CERTIFICATE):
    lines = text.split("\n")
    line_offsets = []
    pos = 0
    for line in lines:
        line_offsets.append(pos)
        pos += len(line) + 1
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return Document(
        doc_id="test-doc-id", filename="birth.txt",
        text=text, lines=lines, paragraphs=paragraphs,
        line_offsets=line_offsets, doc_type=doc_type,
        doc_date="1992-04-02",
    )


VALID_JSON_RESPONSE = json.dumps({
    "entity_type": "PERSON",
    "fields": {
        "name":                {"value": "Alice Chen",   "line_number": 4, "line_text": "Full Name: Alice Chen"},
        "dob":                 {"value": "1992-03-15",   "line_number": 5, "line_text": "Date of Birth: March 15, 1992"},
        "place_of_birth":      {"value": "Vancouver",    "line_number": 6, "line_text": "Place of Birth: Vancouver"},
        "parents":             {"value": "Wei Chen",     "line_number": 0, "line_text": ""},
        "registration_number": {"value": "BC-2024-00441","line_number": 2, "line_text": "Registration No: BC-2024-00441"},
    }
})

BIRTH_CERT_TEXT = (
    "CERTIFICATE OF BIRTH\n"
    "Registration No: BC-2024-00441\n"
    "\n"
    "Full Name: Alice Chen\n"
    "Date of Birth: March 15, 1992\n"
    "Place of Birth: Vancouver, British Columbia, Canada\n"
)


class TestLangChainExtractor:

    def test_extract_valid_response(self):
        """LangChain extractor parses valid JSON response correctly."""
        llm       = MockLLMProvider(complete_response=VALID_JSON_RESPONSE)
        extractor = LangChainExtractor(llm, model_name="mock")
        doc       = make_doc(BIRTH_CERT_TEXT)
        schema    = DOC_TYPE_SCHEMAS["BIRTH_CERTIFICATE"]
        entities  = extractor.extract(doc, schema)

        assert len(entities) == 1
        entity = entities[0]
        assert entity.name == "Alice Chen"
        assert entity.entity_type == EntityType.PERSON
        assert "dob" in entity.attributes
        assert entity.attributes["dob"] == "1992-03-15"
        assert entity.extractor_model == "mock"

    def test_extract_empty_document(self):
        """Empty document returns no entities."""
        llm       = MockLLMProvider(complete_response=VALID_JSON_RESPONSE)
        extractor = LangChainExtractor(llm)
        doc       = make_doc("")
        doc.empty = True
        entities  = extractor.extract(doc, DOC_TYPE_SCHEMAS["BIRTH_CERTIFICATE"])
        assert entities == []

    def test_extract_malformed_json_returns_empty(self):
        """Malformed LLM response returns empty list after retry."""
        llm       = MockLLMProvider(complete_response="not valid json at all !!!")
        extractor = LangChainExtractor(llm)
        doc       = make_doc(BIRTH_CERT_TEXT)
        entities  = extractor.extract(doc, DOC_TYPE_SCHEMAS["BIRTH_CERTIFICATE"])
        assert entities == []

    def test_entity_confidence_computed(self):
        """Entity confidence = filled_fields / total_fields."""
        llm       = MockLLMProvider(complete_response=VALID_JSON_RESPONSE)
        extractor = LangChainExtractor(llm)
        doc       = make_doc(BIRTH_CERT_TEXT)
        schema    = DOC_TYPE_SCHEMAS["BIRTH_CERTIFICATE"]
        entities  = extractor.extract(doc, schema)
        assert len(entities) == 1
        # All 5 fields are filled → confidence = 1.0
        assert entities[0].confidence == 1.0


class TestUiPathExtractor:

    def test_extract_alice_chen_birth_cert(self):
        """Load real Alice Chen birth certificate JSON."""
        extractor = UiPathExtractor()
        path      = Path("docs/people/alice_chen/birth_certificate.json")
        if not path.exists():
            pytest.skip("Sample data not found")
        
        doc, entities = extractor.extract(path)
        assert doc is not None
        assert doc.doc_type == DocType.BIRTH_CERTIFICATE
        assert len(entities) == 1
        entity = entities[0]
        assert entity.name == "Alice Chen"
        assert entity.extractor_model == "uipath-document-understanding"
        assert "dob" in entity.attributes
        assert entity.embedding is None  # not set by extractor

    def test_extract_all_alice_chen_files(self):
        """Load all 3 JSON files for Alice Chen."""
        extractor = UiPathExtractor()
        alice_dir = Path("docs/people/alice_chen")
        if not alice_dir.exists():
            pytest.skip("Sample data not found")
        
        json_files = sorted(alice_dir.glob("*.json"))
        assert len(json_files) >= 2, "Expected at least 2 JSON files for Alice Chen"
        
        total_entities = 0
        for path in json_files:
            doc, entities = extractor.extract(path)
            assert doc is not None, f"Expected document from {path}"
            assert len(entities) > 0, f"Expected entities from {path}"
            total_entities += len(entities)
        
        assert total_entities == len(json_files)

    def test_extract_nonexistent_file(self):
        """Non-existent file returns (None, [])."""
        extractor = UiPathExtractor()
        doc, entities = extractor.extract("/nonexistent/path.json")
        assert doc is None
        assert entities == []

    def test_extract_malformed_json(self, tmp_path):
        """Malformed JSON returns (None, [])."""
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("{not valid json!!}")
        extractor = UiPathExtractor()
        doc, entities = extractor.extract(bad_json)
        assert doc is None
        assert entities == []

    def test_extract_empty_fields(self, tmp_path):
        """JSON with no fields returns empty entity list."""
        empty_json = tmp_path / "empty.json"
        empty_json.write_text(json.dumps({
            "document_type": "BIRTH_CERTIFICATE",
            "confidence": 0.98,
            "fields": {}
        }))
        extractor = UiPathExtractor()
        doc, entities = extractor.extract(empty_json)
        assert doc is not None
        assert entities == []

    def test_uipath_doc_type_mapping(self, tmp_path):
        """document_type in JSON is mapped to DocType enum."""
        for uipath_type, expected_doc_type in [
            ("BIRTH_CERTIFICATE", DocType.BIRTH_CERTIFICATE),
            ("DRIVERS_LICENSE",   DocType.DRIVERS_LICENSE),
            ("PASSPORT",          DocType.PASSPORT),
            ("INSURANCE",         DocType.INSURANCE),
            ("MEDICAL_RECORD",    DocType.MEDICAL_RECORD),
            ("UNKNOWN_XYZ",       DocType.GENERIC),
        ]:
            json_file = tmp_path / f"{uipath_type}.json"
            json_file.write_text(json.dumps({
                "document_type": uipath_type,
                "confidence": 0.9,
                "fields": {
                    "name": {"value": "Test Person", "confidence": 0.9, "bounding_box": [0, 0, 100, 20]}
                }
            }))
            extractor = UiPathExtractor()
            doc, entities = extractor.extract(json_file)
            assert doc is not None
            assert doc.doc_type == expected_doc_type, f"For {uipath_type}"
