"""
Tests for EntityResolver.
"""

import uuid

import pytest

from tests.conftest import MockLLMProvider
from graph_rag.core.graph_builder import KnowledgeGraphBuilder
from graph_rag.core.embeddings import EmbeddingEngine
from graph_rag.core.resolver import EntityResolver
from graph_rag.core.models import DocType, Document, Entity, EntityType


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


@pytest.fixture
def embedding_engine():
    return EmbeddingEngine()


class TestEntityResolver:

    def test_same_person_linked(self, embedding_engine):
        """Two entities with same name from different docs are resolved."""
        doc1 = make_doc("birth.txt")
        doc2 = make_doc("license.txt", DocType.DRIVERS_LICENSE)
        e1   = make_entity("Alice Chen", {"dob": "1992-03-15"}, doc1)
        e2   = make_entity("Alice Chen", {"dob": "1992-03-15", "license": "BC-123"}, doc2, DocType.DRIVERS_LICENSE)

        # Set embeddings
        embedding_engine.embed_entities([e1, e2])

        builder = KnowledgeGraphBuilder()
        for doc in [doc1, doc2]:
            builder.add_document(doc)
        for e in [e1, e2]:
            builder.add_entity(e)

        # Update node embeddings
        G = builder.get_graph()
        G.nodes[e1.entity_id]["embedding"] = e1.embedding
        G.nodes[e2.entity_id]["embedding"] = e2.embedding

        llm      = MockLLMProvider(complete_response="YES")
        resolver = EntityResolver(llm, embedding_engine, auto_threshold=0.85, confirm_threshold=0.60)
        pairs    = resolver.resolve(G)

        assert len(pairs) >= 1
        names = {e1.entity_id, e2.entity_id}
        assert any(p.entity_id_a in names and p.entity_id_b in names for p in pairs)

    def test_different_person_not_linked(self, embedding_engine):
        """Two entities with very different names and attributes are not linked."""
        doc1 = make_doc("birth1.txt")
        doc2 = make_doc("birth2.txt")
        e1   = make_entity("Alice Chen", {"dob": "1992-03-15"}, doc1)
        e2   = make_entity("Bob Johnson", {"dob": "1985-11-20"}, doc2)

        embedding_engine.embed_entities([e1, e2])

        builder = KnowledgeGraphBuilder()
        for doc in [doc1, doc2]:
            builder.add_document(doc)
        for e in [e1, e2]:
            builder.add_entity(e)

        G = builder.get_graph()
        G.nodes[e1.entity_id]["embedding"] = e1.embedding
        G.nodes[e2.entity_id]["embedding"] = e2.embedding

        llm      = MockLLMProvider(complete_response="NO")
        resolver = EntityResolver(llm, embedding_engine, auto_threshold=0.85, confirm_threshold=0.60)
        pairs    = resolver.resolve(G)

        assert len(pairs) == 0

    def test_same_document_not_linked(self, embedding_engine):
        """Entities from the same document are never linked."""
        doc = make_doc("birth.txt")
        e1  = make_entity("Alice Chen", {"dob": "1992-03-15"}, doc)
        e2  = make_entity("Alice Chen", {"dob": "1992-03-15"}, doc)  # same doc!

        embedding_engine.embed_entities([e1, e2])
        builder = KnowledgeGraphBuilder()
        builder.add_document(doc)
        builder.add_entity(e1)
        builder.add_entity(e2)

        G = builder.get_graph()
        G.nodes[e1.entity_id]["embedding"] = e1.embedding
        G.nodes[e2.entity_id]["embedding"] = e2.embedding

        resolver = EntityResolver(MockLLMProvider(), embedding_engine)
        pairs    = resolver.resolve(G)
        assert len(pairs) == 0
