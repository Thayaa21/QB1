"""
FastAPI REST API — Step 16
===========================
Exposes the Graph RAG pipeline as an HTTP API.
All state is in-memory; the graph resets when the server restarts.

TEACHING NOTES
--------------
FastAPI basics:
    FastAPI is a modern Python web framework that:
    - Generates OpenAPI docs automatically at /docs
    - Validates request/response bodies using Pydantic models
    - Is async-capable (we use sync for simplicity here)
    - Has built-in CORS middleware for frontend access

Pydantic models:
    We define Request and Response models as Pydantic BaseModel subclasses.
    FastAPI uses these to:
    1. Validate incoming JSON (wrong types → 422 Unprocessable Entity)
    2. Serialize outgoing Python objects to JSON

Global pipeline state:
    We store the pipeline state as module-level variables.
    In production you'd use dependency injection or a proper state manager.
    For this learning project, global state is simple and clear.

CORS (Cross-Origin Resource Sharing):
    The React frontend runs on http://localhost:5173 (Vite dev server).
    The API runs on http://localhost:8000 (uvicorn).
    Without CORS middleware, the browser blocks the frontend from calling the API.
    allow_origins=["*"] permits all origins — fine for development, not production.

Endpoints:
    POST /ingest           — ingest documents using LangChain extractor
    POST /ingest/uipath    — ingest documents using UiPath extractor
    POST /query            — query the graph
    GET  /graph/stats      — get graph statistics
    GET  /graph/visualize  — get interactive HTML visualization
    GET  /entities         — list all entity nodes
    DELETE /graph          — reset the graph
    GET  /extraction/modes — list available extraction modes
    POST /extraction/mode  — switch active extraction mode
"""

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..core.embeddings import EmbeddingEngine
from ..core.graph_builder import KnowledgeGraphBuilder
from ..core.models import Document
from ..extraction.classifier import DocumentClassifier, DOC_TYPE_SCHEMAS
from ..extraction.langchain_extractor import LangChainExtractor
from ..extraction.uipath_extractor import UiPathExtractor
from ..llm.provider import create_llm_provider
from ..query.engine import QueryEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GLOBAL PIPELINE STATE
# ---------------------------------------------------------------------------
# In a production system, this would be managed by a database or Redis.
# For this project, we keep everything in memory.

_graph_builder    = KnowledgeGraphBuilder()
_documents: dict[str, Document] = {}  # doc_id → Document
_llm              = None
_embedding_engine = EmbeddingEngine()
_extraction_mode  = "langchain"  # "langchain" or "uipath"
_query_engine     = None         # built on first query or after ingest


def _get_llm():
    """Lazily initialize the LLM provider."""
    global _llm
    if _llm is None:
        _llm = create_llm_provider()
    return _llm


def _get_query_engine():
    """Build or rebuild the query engine."""
    global _query_engine
    llm = _get_llm()
    _query_engine = QueryEngine(
        graph            = _graph_builder.get_graph(),
        llm_provider     = llm,
        embedding_engine = _embedding_engine,
        documents        = _documents,
    )
    return _query_engine


# ---------------------------------------------------------------------------
# FASTAPI APP
# ---------------------------------------------------------------------------

app = FastAPI(
    title       = "Graph RAG API",
    description = "Knowledge graph-based retrieval-augmented generation pipeline",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ---- CORS middleware ----
# Allow all origins for development. In production, restrict to specific origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ---------------------------------------------------------------------------
# PYDANTIC REQUEST/RESPONSE MODELS
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    """Request body for POST /ingest"""
    paths:     list[str]
    extractor: str = "langchain"   # "langchain" or "uipath"


class IngestResponse(BaseModel):
    """Response from POST /ingest"""
    documents_ingested:  int
    entities_extracted:  int
    extraction_mode:     str


class QueryRequest(BaseModel):
    """Request body for POST /query"""
    question:         str
    max_hops:         int  = 3
    temporal_context: str  = "current"


class ExtractionModeRequest(BaseModel):
    """Request body for POST /extraction/mode"""
    mode: str   # "langchain" or "uipath"


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _run_entity_resolution():
    """
    Run entity resolution and contradiction detection on the current graph.
    Called after each ingest to keep the graph up to date.
    """
    from ..core.resolver import EntityResolver
    from ..core.contradiction import ContradictionDetector

    graph = _graph_builder.get_graph()

    # Only resolve if we have entities
    entity_count = len(_graph_builder.get_entity_nodes())
    if entity_count < 2:
        return

    try:
        llm = _get_llm()
        resolver = EntityResolver(llm, _embedding_engine)
        pairs    = resolver.resolve(graph)
        for pair in pairs:
            _graph_builder.add_same_as_edge(
                pair.entity_id_a, pair.entity_id_b, pair
            )
        logger.info("Resolution: added %d same_as edges", len(pairs))

        # Detect contradictions
        detector   = ContradictionDetector(graph)
        conflicts  = detector.detect()
        for conflict in conflicts:
            _graph_builder.add_conflict_edge(
                conflict.entity_id_a, conflict.entity_id_b, conflict
            )
        logger.info("Contradiction: found %d conflicts", len(conflicts))
    except Exception as e:
        logger.warning("Resolution/contradiction detection failed: %s", e)


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "status":  "ok",
        "service": "Graph RAG API",
        "docs":    "/docs",
    }


@app.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest):
    """
    Ingest documents into the knowledge graph.

    Accepts .txt files (LangChain mode) or .json files (UiPath mode).
    Auto-detects mode based on the `extractor` field.

    Returns count of documents and entities successfully ingested.
    """
    global _extraction_mode

    extractor_mode = request.extractor.lower().strip()
    if extractor_mode not in ("langchain", "uipath"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid extractor: {extractor_mode}. Use 'langchain' or 'uipath'."
        )

    _extraction_mode = extractor_mode
    docs_ingested    = 0
    entities_total   = 0

    if extractor_mode == "uipath":
        extractor = UiPathExtractor()
        for path_str in request.paths:
            try:
                doc, entities = extractor.extract(path_str)
                if doc is None:
                    continue
                _documents[doc.doc_id] = doc
                _graph_builder.add_document(doc)
                _embedding_engine.embed_entities(entities)
                for entity in entities:
                    _graph_builder.add_entity(entity)
                docs_ingested  += 1
                entities_total += len(entities)
            except Exception as e:
                logger.warning("Failed to ingest %s: %s", path_str, e)

    else:  # langchain
        from ..core.loader import DocumentLoader
        llm        = _get_llm()
        classifier = DocumentClassifier(llm)
        extractor  = LangChainExtractor(llm, model_name=getattr(llm, "model_name", "unknown"))
        loader     = DocumentLoader()

        for path_str in request.paths:
            try:
                doc = loader.load_file(path_str)
                if doc is None:
                    continue
                doc_type, schema = classifier.classify(doc)
                entities = extractor.extract(doc, schema)
                _documents[doc.doc_id] = doc
                _graph_builder.add_document(doc)
                _embedding_engine.embed_entities(entities)
                for entity in entities:
                    _graph_builder.add_entity(entity)
                docs_ingested  += 1
                entities_total += len(entities)
            except Exception as e:
                logger.warning("Failed to ingest %s: %s", path_str, e)

    # Run entity resolution after ingestion
    _run_entity_resolution()
    # Refresh query engine
    _get_query_engine()

    return IngestResponse(
        documents_ingested = docs_ingested,
        entities_extracted = entities_total,
        extraction_mode    = extractor_mode,
    )


@app.post("/ingest/uipath", response_model=IngestResponse)
def ingest_uipath(request: IngestRequest):
    """
    Ingest UiPath JSON files specifically.
    Shorthand for POST /ingest with extractor='uipath'.
    """
    request.extractor = "uipath"
    return ingest(request)


@app.post("/query")
def query_endpoint(request: QueryRequest):
    """
    Query the knowledge graph with a natural language question.

    Returns QueryResult as a JSON dict.
    Returns 400 if the graph is empty.
    """
    stats = _graph_builder.stats()
    if stats["nodes"] == 0:
        raise HTTPException(
            status_code=400,
            detail="Graph is empty. Ingest documents first via POST /ingest"
        )

    engine = _get_query_engine()

    try:
        result = engine.query(
            question         = request.question,
            max_hops         = request.max_hops,
            temporal_context = request.temporal_context,
        )
    except Exception as e:
        logger.error("Query failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    # Serialize QueryResult to dict (dataclass → dict manually)
    return {
        "question":              result.question,
        "answer":                result.answer,
        "source_documents":      result.source_documents,
        "resolved_entities":     result.resolved_entities,
        "resolution_confidence": result.resolution_confidence,
        "hops_used":             result.hops_used,
        "provenance": [
            {
                "fact":             p.fact,
                "source_filename":  p.source_filename,
                "doc_type":         p.doc_type.value,
                "line_number":      p.line_number,
                "line_text":        p.line_text,
                "confidence":       p.confidence,
                "entity_id":        p.entity_id,
            }
            for p in result.provenance
        ],
        "conflicts": [
            {
                "conflict_type":  c.conflict_type,
                "attribute_key":  c.attribute_key,
                "value_a":        c.value_a,
                "value_b":        c.value_b,
                "severity":       c.severity,
                "source_doc_a":   c.source_doc_a,
                "source_doc_b":   c.source_doc_b,
            }
            for c in result.conflicts
        ],
        "has_conflicts":    result.has_conflicts,
        "temporal_context": result.temporal_context,
    }


@app.get("/graph/stats")
def graph_stats():
    """Return statistics about the current graph state."""
    return _graph_builder.stats()


@app.get("/graph/visualize", response_class=HTMLResponse)
def graph_visualize():
    """
    Return an interactive HTML visualization of the graph using Pyvis.
    Falls back to a simple HTML placeholder if Pyvis is not installed.
    """
    try:
        from ..visualization.visualizer import GraphVisualizer
        import tempfile
        visualizer = GraphVisualizer(_graph_builder.get_graph())
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            output_path = f.name

        result_path = visualizer.render(output_path)
        if result_path:
            return HTMLResponse(content=Path(result_path).read_text(), status_code=200)
    except Exception as e:
        logger.warning("Visualization failed: %s", e)

    # Fallback HTML
    stats = _graph_builder.stats()
    return HTMLResponse(content=f"""
    <html><head><title>Graph RAG Visualization</title></head>
    <body>
    <h1>Graph RAG Knowledge Graph</h1>
    <p><b>Nodes:</b> {stats['nodes']} | <b>Edges:</b> {stats['edges']} |
       <b>Entities:</b> {stats['entities']} | <b>Documents:</b> {stats['documents']}</p>
    <p>Install pyvis for interactive visualization: <code>pip install pyvis</code></p>
    </body></html>
    """, status_code=200)


@app.get("/entities")
def list_entities():
    """Return all entity nodes in the graph as a list of dicts."""
    graph = _graph_builder.get_graph()
    entities = []
    for node_id, data in graph.nodes(data=True):
        if data.get("node_type") == "entity":
            # Exclude large/non-serializable fields
            entity_dict = {
                k: v for k, v in data.items()
                if k != "embedding" and isinstance(v, (str, int, float, bool, dict, list, type(None)))
            }
            entity_dict["node_id"] = node_id
            entities.append(entity_dict)
    return {"entities": entities, "count": len(entities)}


@app.delete("/graph")
def reset_graph():
    """Reset the knowledge graph (removes all nodes and edges)."""
    global _documents, _query_engine
    _graph_builder.reset()
    _documents    = {}
    _query_engine = None
    return {"message": "Graph reset", "stats": _graph_builder.stats()}


@app.get("/extraction/modes")
def get_extraction_modes():
    """Return available extraction modes and the currently active mode."""
    return {
        "modes":  ["langchain", "uipath"],
        "active": _extraction_mode,
    }


@app.post("/extraction/mode")
def set_extraction_mode(request: ExtractionModeRequest):
    """
    Switch the active extraction mode.

    Args:
        mode — "langchain" or "uipath"
    """
    global _extraction_mode
    mode = request.mode.lower().strip()
    if mode not in ("langchain", "uipath"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {mode!r}. Use 'langchain' or 'uipath'."
        )
    _extraction_mode = mode
    return {"mode": _extraction_mode, "message": f"Extraction mode set to {mode}"}
