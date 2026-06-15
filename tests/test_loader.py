"""
Tests for DocumentLoader.
"""

import tempfile
from pathlib import Path

import pytest

from graph_rag.core.loader import DocumentLoader, verify_line_offsets
from graph_rag.core.models import DocType


@pytest.fixture
def loader():
    return DocumentLoader()


def test_load_file_basic(tmp_path):
    """Load a simple file and check basic attributes."""
    f = tmp_path / "test.txt"
    f.write_text("Line one\nLine two\nLine three\n")
    loader = DocumentLoader()
    doc = loader.load_file(f)
    assert doc is not None
    assert doc.filename == "test.txt"
    assert len(doc.lines) == 4  # 3 lines + trailing empty
    assert doc.doc_type == DocType.GENERIC
    assert doc.empty is False


def test_load_file_not_found(loader):
    """Missing file returns None."""
    doc = loader.load_file("/nonexistent/path/file.txt")
    assert doc is None


def test_load_file_empty(tmp_path, loader):
    """Empty file marks document as empty=True."""
    f = tmp_path / "empty.txt"
    f.write_text("   \n   \n")
    doc = loader.load_file(f)
    assert doc is not None
    assert doc.empty is True


def test_line_offsets_invariant(tmp_path, loader):
    """
    The line_offsets invariant must hold:
    doc.text[doc.line_offsets[i] : doc.line_offsets[i] + len(doc.lines[i])] == doc.lines[i]
    """
    text = "CERTIFICATE OF BIRTH\nRegistration No: BC-123\nFull Name: Alice Chen\n"
    f    = tmp_path / "cert.txt"
    f.write_text(text)
    doc  = loader.load_file(f)
    assert doc is not None
    assert verify_line_offsets(doc) is True


def test_load_directory(tmp_path, loader):
    """load_directory returns all .txt files."""
    (tmp_path / "a.txt").write_text("Document A")
    (tmp_path / "b.txt").write_text("Document B")
    (tmp_path / "c.json").write_text("{}")  # should be ignored
    docs = loader.load_directory(tmp_path)
    assert len(docs) == 2
    filenames = {doc.filename for doc in docs}
    assert "a.txt" in filenames
    assert "b.txt" in filenames


def test_load_directory_empty(tmp_path, loader):
    """Empty directory raises ValueError."""
    with pytest.raises(ValueError, match="No .txt files"):
        loader.load_directory(tmp_path)


def test_load_batch(tmp_path, loader):
    """load() processes multiple files, skipping bad ones."""
    (tmp_path / "good.txt").write_text("Some content")
    docs = loader.load([tmp_path / "good.txt", "/nonexistent.txt"])
    assert len(docs) == 1


def test_load_empty_paths(loader):
    """load() with empty list raises ValueError."""
    with pytest.raises(ValueError):
        loader.load([])


def test_paragraphs_split(tmp_path, loader):
    """Paragraphs are split on double newlines."""
    text = "Para one line 1\nPara one line 2\n\nPara two\n"
    f    = tmp_path / "paras.txt"
    f.write_text(text)
    doc  = loader.load_file(f)
    assert len(doc.paragraphs) == 2
    assert "Para one" in doc.paragraphs[0]
    assert "Para two" in doc.paragraphs[1]
