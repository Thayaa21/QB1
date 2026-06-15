"""
Tests for ContradictionDetector.
"""

import uuid
import pytest

from graph_rag.core.graph_builder import KnowledgeGraphBuilder
from graph_rag.core.contradiction import ContradictionDetector, CRITICAL_KEYS
from graph_rag.core.models import DocType, Document, Entity, EntityType, ResolvedPair


def make_doc(filename, doc_type=DocType.BIRTH_CERTIFICATE):
    return Document(
        doc_id=str(uuid.uuid4()), filename=filename, text="",
        lines=[""], paragraphs=[""], line_offsets=[0], doc_type=doc_type,
    )


def make_entity(name, attrs, doc, doc_type=DocType.BIRTH_CERTIFICATE):
    return Entity(
        entity_id=str(uuid.uuid4()), name=name, entity_type=EntityType.PERSON,
        attributes=attrs, source_doc_id=doc.doc_id, source_filename=doc.filename,
        doc_type=doc_type,
    )


def build_graph_with_same_as(attrs_a, attrs_b):
    """Helper: build a graph with two same_as linked entities."""
    doc1 = make_doc("birth.txt")
    doc2 = make_doc("insurance.txt", DocType.INSURANCE)
    e1   = make_entity("Alice", attrs_a, doc1)
    e2   = make_entity("Alice", attrs_b, doc2, DocType.INSURANCE)

    builder = KnowledgeGraphBuilder()
    for doc in [doc1, doc2]:
        builder.add_document(doc)
    for e in [e1, e2]:
        builder.add_entity(e)

    pair = ResolvedPair(e1.entity_id, e2.entity_id, 0.97, 1.0, 0.95, False)
    builder.add_same_as_edge(e1.entity_id, e2.entity_id, pair)
    return builder, e1, e2


class TestContradictionDetector:

    def test_dob_mismatch_is_critical(self):
        """DOB mismatch between same_as entities is severity=critical."""
        builder, e1, e2 = build_graph_with_same_as(
            {"dob": "1992-03-15"},
            {"dob": "1992-03-22"},
        )
        detector  = ContradictionDetector(builder.get_graph())
        conflicts = detector.detect()

        assert len(conflicts) == 1
        conflict  = conflicts[0]
        assert conflict.attribute_key == "dob"
        assert conflict.severity      == "critical"
        assert conflict.value_a       == "1992-03-15"
        assert conflict.value_b       == "1992-03-22"

    def test_identical_values_no_conflict(self):
        """Identical attribute values produce no conflict."""
        builder, _, _ = build_graph_with_same_as(
            {"dob": "1992-03-15", "name": "Alice Chen"},
            {"dob": "1992-03-15", "name": "Alice Chen"},
        )
        detector  = ContradictionDetector(builder.get_graph())
        conflicts = detector.detect()
        assert len(conflicts) == 0

    def test_no_same_as_edges_no_conflicts(self):
        """Without same_as edges, no conflicts are detected."""
        doc = make_doc("birth.txt")
        e   = make_entity("Alice", {"dob": "1992-03-15"}, doc)
        builder = KnowledgeGraphBuilder()
        builder.add_document(doc)
        builder.add_entity(e)
        detector  = ContradictionDetector(builder.get_graph())
        conflicts = detector.detect()
        assert len(conflicts) == 0

    def test_critical_keys_set(self):
        """CRITICAL_KEYS includes expected identity fields."""
        assert "dob"            in CRITICAL_KEYS
        assert "name"           in CRITICAL_KEYS
        assert "license_number" in CRITICAL_KEYS
        assert "passport_number" in CRITICAL_KEYS

    def test_date_normalization_no_false_positive(self):
        """Different date formats for same date should NOT produce conflict."""
        # "1992-03-15" and "March 15, 1992" are the same date
        builder, _, _ = build_graph_with_same_as(
            {"dob": "1992-03-15"},
            {"dob": "March 15, 1992"},
        )
        detector  = ContradictionDetector(builder.get_graph())
        conflicts = detector.detect()
        # After normalization, these should be equal → no conflict
        assert len(conflicts) == 0

    def test_multiple_conflicts(self):
        """Multiple attribute mismatches each produce a ConflictRecord."""
        builder, _, _ = build_graph_with_same_as(
            {"dob": "1992-03-15", "name": "Alice Chen"},
            {"dob": "1992-03-22", "name": "Alice C. Chen"},
        )
        detector  = ContradictionDetector(builder.get_graph())
        conflicts = detector.detect()
        keys = {c.attribute_key for c in conflicts}
        assert "dob"  in keys
        assert "name" in keys
