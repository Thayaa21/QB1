"""
Tests for DocumentClassifier.
"""

import pytest

from tests.conftest import MockLLMProvider
from graph_rag.extraction.classifier import DocumentClassifier, DOC_TYPE_SCHEMAS
from graph_rag.core.models import DocType, Document


def make_doc(text, doc_type=DocType.GENERIC):
    lines = text.split("\n")
    return Document(
        doc_id="test-id", filename="test.txt",
        text=text, lines=lines, paragraphs=[text],
        line_offsets=[0], doc_type=doc_type,
    )


def test_classify_birth_certificate():
    """LLM response BIRTH_CERTIFICATE → DocType.BIRTH_CERTIFICATE."""
    llm        = MockLLMProvider(complete_response="BIRTH_CERTIFICATE")
    classifier = DocumentClassifier(llm)
    doc        = make_doc("CERTIFICATE OF BIRTH\nFull Name: Alice Chen\n")
    doc_type, schema = classifier.classify(doc)
    assert doc_type == DocType.BIRTH_CERTIFICATE
    assert doc.doc_type == DocType.BIRTH_CERTIFICATE
    assert "name" in schema
    assert "dob" in schema


def test_classify_drivers_license():
    llm        = MockLLMProvider(complete_response="DRIVERS_LICENSE")
    classifier = DocumentClassifier(llm)
    doc        = make_doc("DRIVER'S LICENSE\nName: Alice Chen\n")
    doc_type, schema = classifier.classify(doc)
    assert doc_type == DocType.DRIVERS_LICENSE
    assert "license_number" in schema


def test_classify_fallback_to_generic():
    """Unknown LLM response falls back to GENERIC."""
    llm        = MockLLMProvider(complete_response="UNKNOWN_THING_XYZ")
    classifier = DocumentClassifier(llm)
    doc        = make_doc("Some random document text")
    doc_type, schema = classifier.classify(doc)
    assert doc_type == DocType.GENERIC
    assert schema == DOC_TYPE_SCHEMAS["GENERIC"]


def test_classify_empty_document():
    """Empty document → GENERIC without calling LLM."""
    llm        = MockLLMProvider(complete_response="BIRTH_CERTIFICATE")
    classifier = DocumentClassifier(llm)
    doc        = make_doc("   \n")
    doc.empty  = True
    doc_type, schema = classifier.classify(doc)
    assert doc_type == DocType.GENERIC
    # LLM should NOT be called for empty docs
    assert llm.call_count == 0


def test_classify_llm_failure_fallback():
    """LLM that raises an exception → fallback to GENERIC."""
    class FailingLLM(MockLLMProvider):
        def complete(self, prompt, temperature=0.0):
            raise Exception("Connection refused")
    
    classifier = DocumentClassifier(FailingLLM())
    doc        = make_doc("PASSPORT\nSurname: CHEN\n")
    doc_type, _schema = classifier.classify(doc)
    assert doc_type == DocType.GENERIC


def test_classify_partial_match():
    """LLM returns 'this is a PASSPORT document' → still matches PASSPORT."""
    llm        = MockLLMProvider(complete_response="This is a PASSPORT document.")
    classifier = DocumentClassifier(llm)
    doc        = make_doc("PASSPORT\nSurname: CHEN\n")
    doc_type, _schema = classifier.classify(doc)
    assert doc_type == DocType.PASSPORT


def test_doc_type_schemas_complete():
    """All DocType values (except GENERIC) have schemas with at least 3 fields."""
    for doc_type in DocType:
        assert doc_type.value in DOC_TYPE_SCHEMAS, f"Missing schema for {doc_type.value}"
        schema = DOC_TYPE_SCHEMAS[doc_type.value]
        assert len(schema) >= 3, f"Schema for {doc_type.value} has too few fields"
