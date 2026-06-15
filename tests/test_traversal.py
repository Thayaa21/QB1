"""
Tests for MultiHopTraversal.
"""

import uuid
import pytest

from graph_rag.core.embeddings import EmbeddingEngine
from graph_rag.core.graph_builder import KnowledgeGraphBuilder
from graph_rag.core.models import DocType, Document, Entity, EntityType, ResolvedPair
from graph_rag.core.temporal import TemporalFilter
from graph_rag.query.traversal import MultiHopTraversal


def make_doc(filename, doc_type=DocType.BIRTH_CERTIFICATE, doc_date=None):
    return Document(
        doc_id=str(uuid.uuid4()), filename=filename, text=f"Content of {filename}",
        lines=[f"Content of {filename}"], paragraphs=[f"Content of {filename}"],
        line_offsets=[0], doc_type=doc_type, doc_date=doc_date,
    )


def make_entity(name, attrs, doc, embedding_engine=None):
    e = Entity(
        entity_id=str(uuid.uuid4()), name=name, entity_type=EntityType.PERSON,
        attributes=attrs, source_doc_id=doc.doc_id, source_filename=doc.filename,
        doc_type=doc.doc_type,
    )
    if embedding_engine:
        e.embedding = embedding_engine.embed(f"{name} {attrs}")
    return e


@pytest.fixture
def embedding_engine():
    return EmbeddingEngine()


@pytest.fixture
def three_hop_graph(embedding_engine):
    """
    Graph with 3 entities in a chain: e1 -same_as-> e2 -same_as-> e3
    All entities are Alice Chen across different documents.
    """
    docs    = [make_doc(f"doc{i}.txt") for i in range(3)]
    entities = [
        make_entity("Alice Chen", {"dob": "1992-03-15"}, docs[i], embedding_engine)
        for i in range(3)
    ]

    builder = KnowledgeGraphBuilder()
    for doc in docs:
        builder.add_document(doc)
    for e in entities:
        builder.add_entity(e)
        builder.get_graph().nodes[e.entity_id]["embedding"] = e.embedding

    builder.add_same_as_edge(
        entities[0].entity_id, entities[1].entity_id,
        ResolvedPair(entities[0].entity_id, entities[1].entity_id, 0.95, 1.0, 0.92, False)
    )
    builder.add_same_as_edge(
        entities[1].entity_id, entities[2].entity_id,
        ResolvedPair(entities[1].entity_id, entities[2].entity_id, 0.95, 1.0, 0.92, False)
    )

    return builder, entities, docs


class TestMultiHopTraversal:

    def test_expand_follows_same_as_chain(self, three_hop_graph, embedding_engine):
        """expand() from e1 reaches e2 and e3 via same_as edges."""
        builder, entities, _ = three_hop_graph
        graph   = builder.get_graph()
        tf      = TemporalFilter(graph)
        trav    = MultiHopTraversal(graph, embedding_engine, tf)

        expanded = trav.expand([entities[0].entity_id], max_hops=3)
        assert len(expanded) == 3
        for e in entities:
            assert e.entity_id in expanded

    def test_expand_respects_max_hops(self, three_hop_graph, embedding_engine):
        """expand() with max_hops=1 only reaches direct neighbors."""
        builder, entities, _ = three_hop_graph
        graph   = builder.get_graph()
        tf      = TemporalFilter(graph)
        trav    = MultiHopTraversal(graph, embedding_engine, tf)

        expanded = trav.expand([entities[0].entity_id], max_hops=1)
        # e1 (seed) + e2 (hop 1) — e3 requires hop 2
        assert entities[0].entity_id in expanded
        assert entities[1].entity_id in expanded
        assert entities[2].entity_id not in expanded

    def test_expand_invalid_max_hops(self, three_hop_graph, embedding_engine):
        """expand() raises ValueError for max_hops outside [1, 5]."""
        builder, entities, _ = three_hop_graph
        graph   = builder.get_graph()
        tf      = TemporalFilter(graph)
        trav    = MultiHopTraversal(graph, embedding_engine, tf)

        with pytest.raises(ValueError):
            trav.expand([entities[0].entity_id], max_hops=0)

        with pytest.raises(ValueError):
            trav.expand([entities[0].entity_id], max_hops=6)

    def test_expand_prevents_cycles(self, embedding_engine):
        """expand() never revisits nodes (cycle prevention)."""
        # Create a cycle: e1 -same_as-> e2 -same_as-> e1
        doc1 = make_doc("d1.txt")
        doc2 = make_doc("d2.txt")
        e1   = make_entity("Alice", {"dob": "1992"}, doc1, embedding_engine)
        e2   = make_entity("Alice", {"dob": "1992"}, doc2, embedding_engine)

        builder = KnowledgeGraphBuilder()
        for doc in [doc1, doc2]:
            builder.add_document(doc)
        for e in [e1, e2]:
            builder.add_entity(e)

        builder.add_same_as_edge(e1.entity_id, e2.entity_id,
            ResolvedPair(e1.entity_id, e2.entity_id, 0.95, 1.0, 0.92, False))

        graph = builder.get_graph()
        graph.nodes[e1.entity_id]["embedding"] = e1.embedding
        graph.nodes[e2.entity_id]["embedding"] = e2.embedding

        tf   = TemporalFilter(graph)
        trav = MultiHopTraversal(graph, embedding_engine, tf)

        expanded = trav.expand([e1.entity_id], max_hops=5)
        # Should only visit each node once
        assert len(expanded) == 2
        assert len(set(expanded)) == 2  # no duplicates

    def test_get_source_documents(self, three_hop_graph, embedding_engine):
        """get_source_documents() returns unique documents."""
        builder, entities, docs = three_hop_graph
        graph = builder.get_graph()
        tf    = TemporalFilter(graph)
        trav  = MultiHopTraversal(graph, embedding_engine, tf)

        all_ids = [e.entity_id for e in entities]
        found_docs = trav.get_source_documents(all_ids)
        assert len(found_docs) == 3
        filenames = {d.filename for d in found_docs}
        assert all(f"doc{i}.txt" in filenames for i in range(3))

    def test_find_entities_by_name(self, three_hop_graph, embedding_engine):
        """find_entities returns entities matching the query name."""
        builder, entities, _ = three_hop_graph
        graph = builder.get_graph()
        tf    = TemporalFilter(graph)
        trav  = MultiHopTraversal(graph, embedding_engine, tf)

        query_emb = embedding_engine.embed("Alice Chen birth certificate")
        matched   = trav.find_entities(["Alice Chen"], query_emb, threshold=0.3)
        assert len(matched) >= 1  # At least one match
