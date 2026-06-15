"""
Tests for KnowledgeGraphBuilder.
"""

import uuid

import pytest

from graph_rag.core.graph_builder import KnowledgeGraphBuilder
from graph_rag.core.models import (
    ConflictRecord, DocType, Document, Entity, EntityType,
    ResolvedPair, EdgeType,
)


def make_doc(filename, doc_type=DocType.BIRTH_CERTIFICATE, doc_date=None):
    return Document(
        doc_id=str(uuid.uuid4()), filename=filename, text="", lines=[""],
        paragraphs=[""], line_offsets=[0], doc_type=doc_type, doc_date=doc_date,
    )


def make_entity(name, doc, doc_type=DocType.BIRTH_CERTIFICATE):
    return Entity(
        entity_id=str(uuid.uuid4()), name=name, entity_type=EntityType.PERSON,
        attributes={"dob": "1992-03-15"}, source_doc_id=doc.doc_id,
        source_filename=doc.filename, doc_type=doc_type,
    )


class TestKnowledgeGraphBuilder:

    def test_add_document_returns_node_id(self):
        builder = KnowledgeGraphBuilder()
        doc     = make_doc("birth.txt")
        node_id = builder.add_document(doc)
        assert node_id == doc.doc_id
        assert node_id in builder.get_graph().nodes

    def test_add_entity_creates_mentions_edge(self):
        builder = KnowledgeGraphBuilder()
        doc     = make_doc("birth.txt")
        entity  = make_entity("Alice", doc)
        builder.add_document(doc)
        builder.add_entity(entity)

        G     = builder.get_graph()
        edges = list(G.edges(data=True))
        mentions = [d for _, _, d in edges if d.get("edge_type") == "mentions"]
        assert len(mentions) == 1

    def test_stats_after_adding_nodes(self):
        builder = KnowledgeGraphBuilder()
        doc1    = make_doc("birth.txt")
        doc2    = make_doc("license.txt")
        e1      = make_entity("Alice", doc1)
        e2      = make_entity("Alice", doc2)

        for doc in [doc1, doc2]:
            builder.add_document(doc)
        for entity in [e1, e2]:
            builder.add_entity(entity)

        stats = builder.stats()
        assert stats["nodes"]     == 4
        assert stats["documents"] == 2
        assert stats["entities"]  == 2
        assert stats["edges"]     >= 2  # at least 2 mentions edges

    def test_add_same_as_edge(self):
        builder = KnowledgeGraphBuilder()
        doc1 = make_doc("birth.txt")
        doc2 = make_doc("license.txt")
        e1   = make_entity("Alice", doc1)
        e2   = make_entity("Alice", doc2)
        builder.add_document(doc1)
        builder.add_document(doc2)
        builder.add_entity(e1)
        builder.add_entity(e2)

        pair = ResolvedPair(e1.entity_id, e2.entity_id, 0.97, 1.0, 0.95, False)
        builder.add_same_as_edge(e1.entity_id, e2.entity_id, pair)

        stats = builder.stats()
        assert stats["same_as_edges"] == 1

    def test_add_conflict_edge(self):
        builder = KnowledgeGraphBuilder()
        doc1 = make_doc("birth.txt")
        doc2 = make_doc("insurance.txt")
        e1   = make_entity("Alice", doc1)
        e2   = make_entity("Alice", doc2)
        builder.add_document(doc1)
        builder.add_document(doc2)
        builder.add_entity(e1)
        builder.add_entity(e2)

        conflict = ConflictRecord(
            entity_id_a="a", entity_id_b="b",
            conflict_type="dob_mismatch", attribute_key="dob",
            value_a="1992-03-15", value_b="1992-03-22",
            source_doc_a="birth.txt", source_doc_b="insurance.txt",
            severity="critical",
        )
        builder.add_conflict_edge(e1.entity_id, e2.entity_id, conflict)
        assert builder.stats()["conflict_edges"] == 1

    def test_get_entity_nodes(self):
        builder = KnowledgeGraphBuilder()
        doc = make_doc("birth.txt")
        e   = make_entity("Alice", doc)
        builder.add_document(doc)
        builder.add_entity(e)

        entity_nodes = builder.get_entity_nodes()
        doc_nodes    = builder.get_document_nodes()
        assert e.entity_id in entity_nodes
        assert doc.doc_id  in doc_nodes
        assert doc.doc_id  not in entity_nodes

    def test_reset_clears_graph(self):
        builder = KnowledgeGraphBuilder()
        doc = make_doc("birth.txt")
        builder.add_document(doc)
        builder.reset()
        assert builder.stats()["nodes"] == 0

    def test_export_json(self, tmp_path):
        builder = KnowledgeGraphBuilder()
        doc     = make_doc("birth.txt")
        entity  = make_entity("Alice", doc)
        builder.add_document(doc)
        builder.add_entity(entity)

        output = tmp_path / "graph.json"
        builder.export_json(output)
        assert output.exists()
        import json
        data = json.loads(output.read_text())
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 2
