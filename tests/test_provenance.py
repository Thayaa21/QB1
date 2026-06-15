"""
Tests for ProvenanceTracker.
"""

import uuid
import pytest

from graph_rag.core.graph_builder import KnowledgeGraphBuilder
from graph_rag.core.models import DocType, Document, Entity, EntityType
from graph_rag.query.provenance import ProvenanceTracker


BIRTH_CERT_TEXT = (
    "CERTIFICATE OF BIRTH\n"
    "Registration No: BC-2024-00441\n"
    "\n"
    "Full Name: Alice Chen\n"
    "Date of Birth: March 15, 1992\n"
    "Place of Birth: Vancouver, British Columbia, Canada\n"
)


def make_alice_doc():
    text  = BIRTH_CERT_TEXT
    lines = text.split("\n")
    line_offsets = []
    pos = 0
    for line in lines:
        line_offsets.append(pos)
        pos += len(line) + 1
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return Document(
        doc_id       = str(uuid.uuid4()),
        filename     = "birth_certificate.txt",
        text         = text,
        lines        = lines,
        paragraphs   = paragraphs,
        line_offsets = line_offsets,
        doc_type     = DocType.BIRTH_CERTIFICATE,
        doc_date     = "1992-04-02",
    )


def make_alice_entity(doc: Document) -> Entity:
    # Alice Chen is at line 4 (1-indexed)
    return Entity(
        entity_id         = str(uuid.uuid4()),
        name              = "Alice Chen",
        entity_type       = EntityType.PERSON,
        attributes        = {
            "name": "Alice Chen",
            "dob":  "1992-03-15",
        },
        source_doc_id     = doc.doc_id,
        source_filename   = doc.filename,
        doc_type          = DocType.BIRTH_CERTIFICATE,
        line_number       = 4,
        line_text         = "Full Name: Alice Chen",
        paragraph_index   = 1,
        paragraph_text    = "Full Name: Alice Chen\nDate of Birth: March 15, 1992",
        char_offset_start = 42,
        char_offset_end   = 63,
        extractor_model   = "test",
        confidence        = 0.99,
    )


class TestProvenanceTracker:

    def test_extract_provenance_basic(self):
        """ProvenanceEntry created for each entity attribute."""
        doc    = make_alice_doc()
        entity = make_alice_entity(doc)

        builder = KnowledgeGraphBuilder()
        builder.add_document(doc)
        builder.add_entity(entity)

        tracker = ProvenanceTracker(builder.get_graph(), {doc.doc_id: doc})
        entries = tracker.extract_provenance([entity.entity_id])

        assert len(entries) >= 2  # at least "name" and "dob"
        facts = {e.fact for e in entries}
        assert "name: Alice Chen" in facts
        assert "dob: 1992-03-15"  in facts

    def test_line_text_matches_document(self):
        """Provenance entry line_text matches actual document line."""
        doc    = make_alice_doc()
        entity = make_alice_entity(doc)

        builder = KnowledgeGraphBuilder()
        builder.add_document(doc)
        builder.add_entity(entity)

        tracker = ProvenanceTracker(builder.get_graph(), {doc.doc_id: doc})
        entries = tracker.extract_provenance([entity.entity_id])

        # All entries should have the same line_text (entity line 4)
        name_entries = [e for e in entries if "name" in e.fact.lower()]
        assert len(name_entries) >= 1

        entry = name_entries[0]
        # line_number = 4, so document.lines[3] = "Full Name: Alice Chen"
        expected_line = doc.lines[entity.line_number - 1]
        assert entry.line_text == expected_line

    def test_verify_finds_fact(self):
        """verify() returns entries matching a fact string."""
        doc    = make_alice_doc()
        entity = make_alice_entity(doc)

        builder = KnowledgeGraphBuilder()
        builder.add_document(doc)
        builder.add_entity(entity)

        tracker = ProvenanceTracker(builder.get_graph(), {doc.doc_id: doc})
        found   = tracker.verify("1992-03-15")
        assert len(found) >= 1
        assert all("1992-03-15" in e.fact for e in found)

    def test_verify_case_insensitive(self):
        """verify() is case-insensitive."""
        doc    = make_alice_doc()
        entity = make_alice_entity(doc)

        builder = KnowledgeGraphBuilder()
        builder.add_document(doc)
        builder.add_entity(entity)

        tracker = ProvenanceTracker(builder.get_graph(), {doc.doc_id: doc})
        found   = tracker.verify("ALICE CHEN")
        assert len(found) >= 1

    def test_verify_no_match(self):
        """verify() returns empty list for unknown fact."""
        doc    = make_alice_doc()
        entity = make_alice_entity(doc)

        builder = KnowledgeGraphBuilder()
        builder.add_document(doc)
        builder.add_entity(entity)

        tracker = ProvenanceTracker(builder.get_graph(), {doc.doc_id: doc})
        found   = tracker.verify("xyzzy_nonexistent_fact_12345")
        assert found == []

    def test_provenance_source_filename(self):
        """Provenance entries reference the correct source filename."""
        doc    = make_alice_doc()
        entity = make_alice_entity(doc)

        builder = KnowledgeGraphBuilder()
        builder.add_document(doc)
        builder.add_entity(entity)

        tracker = ProvenanceTracker(builder.get_graph(), {doc.doc_id: doc})
        entries = tracker.extract_provenance([entity.entity_id])

        for entry in entries:
            assert entry.source_filename == "birth_certificate.txt"
