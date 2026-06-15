"""
conftest.py — shared pytest fixtures.

TEACHING NOTES
--------------
conftest.py is a special pytest file. Fixtures defined here are automatically
available in all test files — no import needed.

A fixture is a function decorated with @pytest.fixture that provides a
pre-built object for tests. Instead of creating a Document in every test,
you define it once as a fixture and pytest injects it.

MockLLMProvider:
    We never want real LLM calls in unit tests:
    - They're slow (5-30 seconds per call)
    - They require a running Ollama/API key
    - They're non-deterministic
    
    The mock returns pre-defined responses that make tests predictable.
    We test that the code HANDLES the response correctly, not that the LLM responds correctly.
"""

import uuid
from typing import Union

import pytest

from graph_rag.core.models import (
    Document,
    DocType,
    Entity,
    EntityType,
    ResolvedPair,
    ConflictRecord,
)
from graph_rag.llm.provider import LLMProvider


class MockLLMProvider(LLMProvider):
    """
    Mock LLM that returns pre-configured responses.
    
    Usage:
        mock = MockLLMProvider(complete_response="BIRTH_CERTIFICATE")
        result = mock.complete("any prompt")  # → "BIRTH_CERTIFICATE"
    """

    def __init__(
        self,
        complete_response: str = "GENERIC",
        chat_response:     str = "Test answer.",
    ):
        self._complete_response = complete_response
        self._chat_response     = chat_response
        self._call_count        = 0

    def complete(self, prompt: str, temperature: float = 0.0) -> str:
        self._call_count += 1
        return self._complete_response

    def chat(self, messages: list[dict], temperature: float = 0.0) -> str:
        self._call_count += 1
        return self._chat_response

    @property
    def model_name(self) -> str:
        return "mock-llm"

    @property
    def call_count(self) -> int:
        return self._call_count


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm() -> MockLLMProvider:
    """A mock LLM that returns predictable responses."""
    return MockLLMProvider()


@pytest.fixture
def sample_document() -> Document:
    """
    A minimal Document for testing.
    
    Represents a birth certificate with 5 lines of content.
    """
    text = (
        "CERTIFICATE OF BIRTH\n"
        "Registration No: BC-2024-00441\n"
        "\n"
        "Full Name: Alice Chen\n"
        "Date of Birth: March 15, 1992\n"
        "Place of Birth: Vancouver, British Columbia, Canada\n"
    )
    lines = text.split("\n")
    
    # Compute line offsets
    line_offsets: list[int] = []
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
        empty        = False,
        metadata     = {"full_path": "/docs/birth_certificate.txt"},
    )


@pytest.fixture
def sample_entity(sample_document: Document) -> Entity:
    """
    A sample PERSON entity extracted from sample_document.
    
    Alice Chen, found at line 4 ("Full Name: Alice Chen").
    """
    return Entity(
        entity_id         = str(uuid.uuid4()),
        name              = "Alice Chen",
        entity_type       = EntityType.PERSON,
        attributes        = {
            "name":            "Alice Chen",
            "dob":             "1992-03-15",
            "place_of_birth":  "Vancouver, British Columbia, Canada",
            "registration_number": "BC-2024-00441",
        },
        source_doc_id     = sample_document.doc_id,
        source_filename   = "birth_certificate.txt",
        doc_type          = DocType.BIRTH_CERTIFICATE,
        line_number       = 4,
        line_text         = "Full Name: Alice Chen",
        paragraph_index   = 1,
        paragraph_text    = "Full Name: Alice Chen\nDate of Birth: March 15, 1992",
        char_offset_start = 42,
        char_offset_end   = 63,
        extractor_model   = "mock",
        confidence        = 0.99,
    )


@pytest.fixture
def sample_entity_2() -> Entity:
    """
    A second Alice Chen entity from a different document (drivers license).
    Used for testing entity resolution and contradiction detection.
    """
    doc_id = str(uuid.uuid4())
    return Entity(
        entity_id         = str(uuid.uuid4()),
        name              = "Alice Chen",
        entity_type       = EntityType.PERSON,
        attributes        = {
            "name":           "Alice Chen",
            "dob":            "1992-03-15",
            "license_number": "BC-7745291",
            "address":        "204 Maple Street, Vancouver, BC V5K 1A1",
        },
        source_doc_id     = doc_id,
        source_filename   = "drivers_license.txt",
        doc_type          = DocType.DRIVERS_LICENSE,
        line_number       = 3,
        line_text         = "Name: Alice Chen",
        paragraph_index   = 0,
        paragraph_text    = "DRIVER'S LICENSE\nName: Alice Chen",
        char_offset_start = 20,
        char_offset_end   = 36,
        extractor_model   = "mock",
        confidence        = 0.98,
    )


@pytest.fixture
def sample_document_2(sample_entity_2: Entity) -> Document:
    """
    Document for sample_entity_2 (drivers license).
    doc_id matches sample_entity_2.source_doc_id.
    """
    text = (
        "DRIVER'S LICENSE\n"
        "Province: British Columbia\n"
        "Name: Alice Chen\n"
        "Date of Birth: March 15, 1992\n"
        "License Number: BC-7745291\n"
    )
    lines = text.split("\n")
    line_offsets: list[int] = []
    pos = 0
    for line in lines:
        line_offsets.append(pos)
        pos += len(line) + 1
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    return Document(
        doc_id       = sample_entity_2.source_doc_id,
        filename     = "drivers_license.txt",
        text         = text,
        lines        = lines,
        paragraphs   = paragraphs,
        line_offsets = line_offsets,
        doc_type     = DocType.DRIVERS_LICENSE,
        doc_date     = "2020-06-15",
        empty        = False,
        metadata     = {},
    )
