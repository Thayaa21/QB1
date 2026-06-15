# Graph RAG — Cross-Document Knowledge Graph RAG System

A Python + React system that builds a **knowledge graph** over documents, resolves the same person across multiple documents, and answers natural language queries with **exact source citations down to the line number**.

Normal RAG fails when "John Smith" appears in two different files — it can't connect them. This system uses a graph to link them and answer questions that span both.

---

## The Core Problem It Solves

```
Birth Certificate (John Smith) ──same_as──► Driver's License (John R. Smith)
       │                                              │
    DOB: Jan 1, 1990                        License No: X12345

Query: "What is John's DOB and license number?"
→ Answer: DOB is Jan 1, 1990  [birth_certificate.txt, line 4]
          License is X12345   [drivers_license.txt, line 7]
```

Normal vector RAG retrieves one or the other. Graph RAG retrieves **both**, and shows you exactly which line in which file each fact came from.

---

## Features

| Feature | Description |
|---|---|
| **Cross-document entity resolution** | Links "John Smith" in BC to "John R. Smith" in license via `same_as` graph edges |
| **Multi-hop reasoning** | Traverses chains: BC → License → Insurance to answer complex queries |
| **Dual extraction engine** | Toggle between LangChain (LLM) and UiPath Document Understanding |
| **Document type classification** | Auto-detects BIRTH_CERTIFICATE, DRIVERS_LICENSE, PASSPORT, INSURANCE, MEDICAL_RECORD |
| **Temporal awareness** | "Current address" resolves to the most recent document automatically |
| **Confidence scoring** | Every link scored 0.0–1.0: `0.4 × name_similarity + 0.6 × semantic_similarity` |
| **Contradiction detection** | DOB mismatch between linked docs flagged as `critical` conflict |
| **Provenance / verify links** | Every fact shows: source file + exact line number + verbatim line text |
| **Graph visualization** | Interactive Pyvis HTML: color-coded nodes, styled edges, click for tooltips |
| **Metadata tagging** | Every entity records extractor model, timestamp, confidence, char offsets |
| **React frontend** | LangChain/UiPath toggle, drag-and-drop upload, query UI, provenance display |
| **FastAPI REST API** | 9 endpoints for ingest, query, visualization, stats |
| **CLI** | 6 commands: ingest, query, verify, visualize, serve, stats |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Graph | NetworkX (in-memory) |
| LLM — local | Ollama (llama3 / mistral) — free, private, no API key |
| LLM — production | OpenAI API — switchable via env var |
| Embeddings | `sentence-transformers` all-MiniLM-L6-v2 — fully local |
| Name matching | RapidFuzz |
| Backend | FastAPI + Uvicorn |
| Frontend | React 18 + TypeScript + Vite + TailwindCSS |
| CLI | Click |
| Visualization | Pyvis |
| Testing | pytest + hypothesis (property-based tests) |

---

## Project Structure

```
QB1/
├── graph_rag/                  ← Python backend (not built yet)
│   ├── core/                   ← data models, graph builder
│   ├── extraction/             ← LangChainExtractor, UiPathExtractor
│   ├── query/                  ← QueryEngine, traversal, provenance
│   ├── llm/                    ← OllamaProvider, OpenAIProvider
│   ├── api/                    ← FastAPI routes
│   └── cli/                    ← Click CLI
├── frontend/                   ← React + TypeScript (not built yet)
├── docs/
│   ├── people/                 ← synthetic dataset (48 people, 298 files)
│   │   ├── alice_chen/
│   │   ├── david_anderson/
│   │   └── ...
│   ├── manifest.json           ← index of all people + IDs + contradiction flags
│   └── README.md
├── tests/                      ← pytest unit + hypothesis property tests (not built yet)
├── generate_dataset.py         ← ✅ DONE — synthetic dataset generator
├── rag.py                      ← original stub (to be replaced)
└── README.md                   ← this file
```

---

## What's Built So Far

| Component | Status | Notes |
|---|---|---|
| Synthetic dataset | ✅ Done | 48 people, 298 files, `.txt` + UiPath `.json` |
| Dataset generator script | ✅ Done | `generate_dataset.py` — scale up anytime |
| Design document | ✅ Done | `.kiro/specs/graph-rag/design.md` |
| Requirements document | ✅ Done | `.kiro/specs/graph-rag/requirements.md` |
| Data models | 🔲 Next | `Document`, `Entity`, `ProvenanceEntry`, `ConflictRecord`, `QueryResult` |
| LLM Provider (Ollama/OpenAI) | 🔲 Next | `OllamaProvider`, `OpenAIProvider`, factory |
| Document Loader | 🔲 Next | Read `.txt`, split lines/paragraphs, record offsets |
| Document Classifier | 🔲 Next | LLM → detect BIRTH_CERTIFICATE / LICENSE / etc. |
| LangChain Extractor | 🔲 Next | LLM extract entities with provenance metadata |
| UiPath Extractor | 🔲 Next | Parse UiPath JSON → same Entity format |
| Embedding Engine | 🔲 Next | `sentence-transformers` local, with caching |
| Knowledge Graph Builder | 🔲 Next | NetworkX graph, typed nodes + edges |
| Entity Resolver | 🔲 Next | Hybrid name + semantic matching, same_as edges |
| Contradiction Detector | 🔲 Next | Scan same_as pairs for attribute conflicts |
| Temporal Filter | 🔲 Next | Time-aware edge traversal |
| Multi-hop Traversal | 🔲 Next | BFS up to 5 hops via same_as edges |
| Context Aggregator | 🔲 Next | Hybrid graph + semantic ranking |
| Provenance Tracker | 🔲 Next | Fact → exact line in source document |
| Query Engine | 🔲 Next | Orchestrates full query pipeline |
| Graph Visualizer | 🔲 Next | Pyvis interactive HTML |
| FastAPI REST API | 🔲 Next | 9 endpoints |
| CLI | 🔲 Next | 6 commands |
| React Frontend | 🔲 Next | Full SPA with extraction toggle |
| Unit tests | 🔲 Next | pytest per component |
| Property-based tests | 🔲 Next | hypothesis — no self-loops, confidence bounds, etc. |

---

## Build Order (Recommended)

```
1. Data models          → defines Document, Entity, QueryResult etc.
2. LLM Provider         → Ollama + OpenAI abstraction
3. Document Loader      → read .txt files, split lines
4. Document Classifier  → LLM detects doc type
5. LangChain Extractor  → LLM extracts entities with line provenance
6. UiPath Extractor     → parse UiPath JSON
7. Embedding Engine     → local sentence-transformers
8. Knowledge Graph Builder → NetworkX nodes + edges
9. Entity Resolver      → hybrid matching, same_as edges
10. Contradiction Detector → conflict detection
11. Temporal Filter     → time-aware queries
12. Multi-hop Traversal → BFS expansion
13. Context Aggregator  → hybrid ranking
14. Provenance Tracker  → fact → exact line
15. Query Engine        → full pipeline orchestrator
16. FastAPI API         → HTTP endpoints
17. CLI                 → command-line interface
18. Graph Visualizer    → Pyvis HTML
19. React Frontend      → full SPA
20. Tests               → unit + property-based
```

---

## Quick Start (once built)

```bash
# Install dependencies
pip install networkx rapidfuzz sentence-transformers fastapi uvicorn \
            pyvis python-dotenv openai langchain click hypothesis pytest

# Start Ollama locally
ollama serve
ollama pull llama3

# Set up environment
cp .env.example .env          # edit LLM_PROVIDER=ollama or openai

# Ingest documents
python graph_rag.py ingest --dir docs/people/alice_chen --extractor langchain

# Query
python graph_rag.py query "What is Alice's license number and insurance policy?"

# Verify a fact (shows exact source line)
python graph_rag.py verify "Alice's DOB"

# Visualize the graph
python graph_rag.py visualize --output graph.html

# Start the REST API + React frontend
python graph_rag.py serve --port 8000
```

---

## Dataset

The `docs/people/` folder contains 48 fictional people with intentional test scenarios.
See [`docs/README.md`](docs/README.md) for full details.

```bash
# Regenerate or expand the dataset anytime
python generate_dataset.py --count 100 --seed 42 --out docs
```

---

## LLM Switching

```bash
# Local development (free, private, no internet)
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3

# Production / GitHub deployment
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

---

## UiPath Integration

When `--extractor uipath` is used, the system reads UiPath Document Understanding JSON exports directly instead of calling the LLM for extraction. This is faster and more accurate for scanned documents.

Your company's UiPath tenant outputs JSON like:
```json
{
  "document_type": "DRIVERS_LICENSE",
  "confidence": 0.97,
  "fields": {
    "name":    { "value": "John Smith", "confidence": 0.99, "bounding_box": [72, 100, 400, 120] },
    "dob":     { "value": "1990-01-01", "confidence": 0.99, "bounding_box": [72, 125, 400, 145] },
    "license_number": { "value": "X12345", "confidence": 0.95, "bounding_box": [72, 150, 350, 170] }
  }
}
```

The React frontend toggle switches between LangChain and UiPath — the rest of the pipeline is identical.

---

## Spec Documents

Full requirements and design specs are in `.kiro/specs/graph-rag/`:
- [`design.md`](.kiro/specs/graph-rag/design.md) — architecture, components, algorithms, data models
- [`requirements.md`](.kiro/specs/graph-rag/requirements.md) — 22 requirements with testable acceptance criteria
