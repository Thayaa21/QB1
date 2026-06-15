"""
Tests for core data models.
"""

import uuid
from graph_rag.core.models import (
    DocType, EdgeType, EntityType,
    Document, Entity, ResolvedPair, ConflictRecord,
    ProvenanceEntry, QueryResult, ExtractionSource,
)


def test_doctype_values():
    """DocType enum has all expected values."""
    assert DocType.BIRTH_CERTIFICATE.value == "BIRTH_CERTIFICATE"
    assert DocType.DRIVERS_LICENSE.value   == "DRIVERS_LICENSE"
    assert DocType.PASSPORT.value          == "PASSPORT"
    assert DocType.INSURANCE.value         == "INSURANCE"
    assert DocType.MEDICAL_RECORD.value    == "MEDICAL_RECORD"
    assert DocType.GENERIC.value           == "GENERIC"


def test_doctype_is_str():
    """DocType inherits from str — can be used as string directly with ==."""
    assert DocType.PASSPORT == "PASSPORT"
    # Note: In Python 3.11+, str(DocType.INSURANCE) returns 'DocType.INSURANCE'
    # but the == comparison still works correctly because DocType inherits from str
    assert DocType.INSURANCE == "INSURANCE"
    assert DocType.BIRTH_CERTIFICATE.value == "BIRTH_CERTIFICATE"


def test_edgetype_values():
    assert EdgeType.MENTIONS.value == "mentions"
    assert EdgeType.SAME_AS.value  == "same_as"
    assert EdgeType.CONFLICT.value == "conflict"


def test_entitytype_values():
    assert EntityType.PERSON.value       == "PERSON"
    assert EntityType.ORGANIZATION.value == "ORGANIZATION"
    assert EntityType.LOCATION.value     == "LOCATION"
    assert EntityType.ID_NUMBER.value    == "ID_NUMBER"
    assert EntityType.DATE.value         == "DATE"


def test_document_instantiation():
    """Document can be created with all required fields."""
    doc = Document(
        doc_id       = "test-id",
        filename     = "test.txt",
        text         = "Hello world",
        lines        = ["Hello world"],
        paragraphs   = ["Hello world"],
        line_offsets = [0],
        doc_type     = DocType.GENERIC,
    )
    assert doc.doc_id    == "test-id"
    assert doc.filename  == "test.txt"
    assert doc.doc_type  == DocType.GENERIC
    assert doc.doc_date  is None
    assert doc.empty     is False
    assert doc.metadata  == {}


def test_entity_instantiation():
    """Entity can be created with required fields and defaults."""
    entity = Entity(
        entity_id      = "e-123",
        name           = "Alice Chen",
        entity_type    = EntityType.PERSON,
        attributes     = {"dob": "1992-03-15"},
        source_doc_id  = "doc-456",
        source_filename = "birth.txt",
        doc_type       = DocType.BIRTH_CERTIFICATE,
    )
    assert entity.name      == "Alice Chen"
    assert entity.embedding is None
    assert entity.line_number == 0
    assert entity.confidence  == 1.0


def test_resolved_pair_instantiation():
    pair = ResolvedPair(
        entity_id_a    = "a",
        entity_id_b    = "b",
        confidence     = 0.95,
        name_score     = 1.0,
        semantic_score = 0.92,
        llm_confirmed  = False,
    )
    assert pair.confidence     == 0.95
    assert pair.llm_confirmed  is False
    assert pair.valid_from     is None
    assert pair.valid_until    is None


def test_conflict_record_instantiation():
    c = ConflictRecord(
        entity_id_a   = "a",
        entity_id_b   = "b",
        conflict_type = "dob_mismatch",
        attribute_key = "dob",
        value_a       = "1992-03-15",
        value_b       = "1992-03-22",
        source_doc_a  = "birth.txt",
        source_doc_b  = "insurance.txt",
        severity      = "critical",
    )
    assert c.severity == "critical"
    assert c.attribute_key == "dob"


def test_provenance_entry_instantiation():
    p = ProvenanceEntry(
        fact             = "dob: 1992-03-15",
        source_filename  = "birth.txt",
        doc_type         = DocType.BIRTH_CERTIFICATE,
        line_number      = 5,
        line_text        = "Date of Birth: March 15, 1992",
        paragraph_index  = 1,
        paragraph_text   = "...",
        char_offset_start = 42,
        char_offset_end   = 70,
        confidence       = 0.99,
        entity_id        = "e-123",
    )
    assert p.fact        == "dob: 1992-03-15"
    assert p.line_number == 5


def test_query_result_instantiation():
    qr = QueryResult(
        question              = "What is Alice's DOB?",
        answer                = "1992-03-15",
        source_documents      = ["birth.txt"],
        resolved_entities     = ["Alice Chen"],
        resolution_confidence = [0.97],
        hops_used             = 2,
        provenance            = [],
        conflicts             = [],
        has_conflicts         = False,
        temporal_context      = "current",
    )
    assert qr.has_conflicts is False
    assert qr.hops_used == 2


def test_extraction_source():
    src = ExtractionSource(mode="langchain", file_path="birth.txt")
    assert src.mode == "langchain"
    assert src.uipath_json_path is None
