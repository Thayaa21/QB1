# Graph RAG — Complete Study Guide

Everything you need to understand this project, step by step.
Use this as your reference while building and learning.

---

## Table of Contents

1. [What is RAG?](#1-what-is-rag)
2. [What is Graph RAG and why is it better?](#2-what-is-graph-rag-and-why-is-it-better)
3. [Project Overview](#3-project-overview)
4. [The Full Pipeline — How Data Flows](#4-the-full-pipeline--how-data-flows)
5. [DONE — Step 0: The Dataset](#5-done--step-0-the-dataset)
6. [DONE — Step 1: Data Models](#6-done--step-1-data-models)
7. [DONE — Step 2: LLM Provider](#7-done--step-2-llm-provider)
8. [NEXT — Step 3: Document Loader](#8-next--step-3-document-loader)
9. [UPCOMING — Step 4: Document Classifier](#9-upcoming--step-4-document-classifier)
10. [UPCOMING — Step 5: LangChain Extractor](#10-upcoming--step-5-langchain-extractor)
11. [UPCOMING — Step 6: UiPath Extractor](#11-upcoming--step-6-uipath-extractor)
12. [UPCOMING — Step 7: Embedding Engine](#12-upcoming--step-7-embedding-engine)
13. [UPCOMING — Step 8: Knowledge Graph Builder](#13-upcoming--step-8-knowledge-graph-builder)
14. [UPCOMING — Step 9: Entity Resolver](#14-upcoming--step-9-entity-resolver)
15. [UPCOMING — Step 10: Contradiction Detector](#15-upcoming--step-10-contradiction-detector)
16. [UPCOMING — Step 11: Temporal Filter](#16-upcoming--step-11-temporal-filter)
17. [UPCOMING — Step 12: Multi-hop Traversal](#17-upcoming--step-12-multi-hop-traversal)
18. [UPCOMING — Step 13: Context Aggregator](#18-upcoming--step-13-context-aggregator)
19. [UPCOMING — Step 14: Provenance Tracker](#19-upcoming--step-14-provenance-tracker)
20. [UPCOMING — Step 15: Query Engine](#20-upcoming--step-15-query-engine)
21. [UPCOMING — Step 16: FastAPI REST API](#21-upcoming--step-16-fastapi-rest-api)
22. [UPCOMING — Step 17: CLI](#22-upcoming--step-17-cli)
23. [UPCOMING — Step 18: Graph Visualizer](#23-upcoming--step-18-graph-visualizer)
24. [UPCOMING — Step 19: React Frontend](#24-upcoming--step-19-react-frontend)
25. [UPCOMING — Step 20: Tests](#25-upcoming--step-20-tests)
26. [Key Concepts Glossary](#26-key-concepts-glossary)
27. [Common Questions](#27-common-questions)

---

## 1. What is RAG?

**RAG = Retrieval-Augmented Generation**

An LLM (like ChatGPT) knows a lot from training, but it doesn't know
YOUR documents. RAG solves this:

```
Normal LLM:
  User: "What is Alice's license number?"
  LLM:  "I don't know — I haven't seen your documents."

RAG:
  1. Search your documents for anything about "Alice"
  2. Find: drivers_license.txt — "License Number: BC-7745291"
  3. Give that text to the LLM as context
  4. LLM: "Alice's license number is BC-7745291."
```

**The standard RAG pipeline:**
```
Question → Embed question → Search vector DB → Get top-K chunks → LLM → Answer
```

**The problem:** each document chunk is treated independently.
If the answer spans two documents, standard RAG misses it.

---

## 2. What is Graph RAG and why is it better?

**Graph RAG adds a knowledge graph on top of RAG.**

Instead of treating documents as isolated chunks, it:
1. Extracts entities (people, IDs, dates) from every document
2. Links the same entity across different documents with `same_as` edges
3. Traverses the graph to collect all related context before answering

**The core problem it solves:**

```
birth_certificate.txt:    "Full Name: Alice Chen, DOB: March 15, 1992"
drivers_license.txt:      "Name: Alice Chen, License: BC-7745291"
insurance.txt:            "Policyholder: Alice Chen, Policy: INS-887341"

Question: "What is Alice's license number and insurance policy?"

Normal RAG: returns one document — either the license OR the insurance
Graph RAG:  connects all three via same_as edges → returns BOTH → complete answer
```

**The graph structure:**

```
[birth_certificate.txt]          [drivers_license.txt]         [insurance.txt]
        │                                │                            │
  [Alice Chen]  ←────same_as────  [Alice Chen]  ────same_as────►  [Alice Chen]
  (PERSON node)                   (PERSON node)                   (PERSON node)
  DOB: Mar 15                     License: BC-7745291             Policy: INS-887341
```

When you query for "Alice", the graph traversal finds ALL three nodes
and ALL three documents automatically.

---

## 3. Project Overview

**What we're building:**

A Python + React system with:
- **Backend**: FastAPI + NetworkX graph + LLM pipeline
- **Frontend**: React SPA with LangChain/UiPath toggle
- **Two extraction modes**:
  - LangChain: send raw `.txt` → LLM classifies + extracts
  - UiPath: send structured `.json` → parse directly (no LLM needed)

**Tech stack:**

| Layer | Technology | Why |
|---|---|---|
| Graph storage | NetworkX | In-memory, no DB setup, pure Python |
| LLM local | Ollama (qwen2.5) | Free, private, runs on your Mac |
| LLM cloud | OpenAI API | For production/GitHub |
| Embeddings | sentence-transformers | Local, no API key, fast |
| Name matching | RapidFuzz | Fast fuzzy string similarity |
| Backend API | FastAPI | Modern, auto-generates docs |
| Frontend | React + TypeScript + Vite | Component-based, type-safe |
| CLI | Click | Simple command-line interface |
| Visualization | Pyvis | Interactive HTML graphs |
| Testing | pytest + hypothesis | Unit + property-based tests |

---

## 4. The Full Pipeline — How Data Flows

### Ingestion (loading documents into the graph)

```
.txt or .json files
        │
        ▼
DocumentLoader          ← reads file, splits into lines, records char offsets
        │
        ▼
DocumentClassifier      ← LLM: "Is this a birth cert, license, or passport?"
        │
        ▼
LangChainExtractor      ← LLM: "Extract name, DOB, license number + exact line"
  OR UiPathExtractor    ← parse JSON fields directly (no LLM)
        │
        ▼
EmbeddingEngine         ← convert entity name+attrs to 384-float vector
        │
        ▼
KnowledgeGraphBuilder   ← add Document node + Entity nodes + mentions edges
        │
        ▼
EntityResolver          ← compare entities across docs → add same_as edges
        │
        ▼
ContradictionDetector   ← find DOB mismatches → add conflict edges
        │
        ▼
Graph is ready ✓
```

### Query (answering a question)

```
"What is Alice's license number and insurance policy?"
        │
        ▼
QueryEngine
        │
        ├── LLM extracts entity names from question → ["Alice"]
        ├── EmbeddingEngine embeds the question → [384 floats]
        │
        ▼
MultiHopTraversal       ← BFS: find Alice nodes, traverse same_as edges
        │
        ▼
TemporalFilter          ← filter by date if needed ("current address")
        │
        ▼
ContextAggregator       ← deduplicate, rank by hybrid score, truncate
        │
        ▼
ProvenanceTracker       ← map each fact to exact line in source file
        │
        ▼
LLM synthesizes answer  ← "Alice's license is BC-7745291 and policy is INS-887341"
        │
        ▼
QueryResult             ← answer + provenance + conflicts + confidence scores
```

---

## 5. ✅ DONE — Step 0: The Dataset

**What:** Synthetic documents for 48 fictional people. No real data.

**Files:**
```
docs/people/
├── alice_chen/
│   ├── birth_certificate.txt    ← raw text (LangChain mode)
│   ├── birth_certificate.json   ← UiPath structured JSON (UiPath mode)
│   ├── drivers_license.txt/.json
│   └── insurance.txt/.json
├── david_anderson/
│   ├── birth_certificate.txt/.json
│   ├── passport.txt/.json
│   └── medical_record.txt/.json
└── ... (48 people total)
docs/manifest.json               ← index: all people, IDs, contradiction flags
generate_dataset.py              ← script to regenerate or expand the dataset
```

**What each scenario tests:**

| Scenario | Example | Tests |
|---|---|---|
| DOB contradiction | Alice's insurance says wrong DOB | Contradiction detection |
| 3-document chain | BC → Passport → Medical | Multi-hop traversal |
| Same first name | James Lee vs James Wilson vs James Smith | Disambiguation |
| Name variation | "James Lee" vs "James R. Lee" | Entity resolution |

**Key concept: why .txt AND .json?**

`.txt` = raw text that the LLM will read and extract entities from (LangChain mode)
`.json` = pre-extracted structured data from UiPath Document Understanding (UiPath mode)

The JSON format looks like this:
```json
{
  "document_type": "BIRTH_CERTIFICATE",
  "confidence": 0.98,
  "fields": {
    "name": { "value": "Alice Chen", "confidence": 0.99, "bounding_box": [72, 120, 400, 140] },
    "dob":  { "value": "1992-03-15", "confidence": 0.99, "bounding_box": [72, 145, 400, 165] }
  }
}
```

**To regenerate or expand:**
```bash
python generate_dataset.py --count 100 --seed 42 --out docs
```

---

## 6. ✅ DONE — Step 1: Data Models

**File:** `graph_rag/core/models.py`

**What:** Python dataclasses that define the shape of every object in the pipeline.

**Why not just use dicts?**
- 10+ components pass data between each other
- A typo in a dict key (`data["lnes"]`) fails silently at runtime
- A typo in a model attribute (`doc.lnes`) fails immediately with AttributeError
- Models carry computed fields (like `line_offsets`) that dicts can't

**The models:**

### DocType (Enum)
```python
class DocType(str, Enum):
    BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE"
    DRIVERS_LICENSE   = "DRIVERS_LICENSE"
    PASSPORT          = "PASSPORT"
    INSURANCE         = "INSURANCE"
    MEDICAL_RECORD    = "MEDICAL_RECORD"
    GENERIC           = "GENERIC"
```
Why Enum? So `DocType.PASSPORT` is always valid. A raw string like `"passpot"` typo
silently breaks things. An Enum typo fails at import time.

### Document
```python
@dataclass
class Document:
    doc_id:       str          # unique UUID per file
    filename:     str          # "birth_certificate.txt"
    text:         str          # full raw text
    lines:        list[str]    # text.split("\n")
    paragraphs:   list[str]    # text.split("\n\n")
    line_offsets: list[int]    # char position where each line starts
    doc_type:     DocType      # set by DocumentClassifier
    doc_date:     str          # "1992-04-02" — for temporal queries
    empty:        bool         # True if file had no text
```

**What is `line_offsets`?**
```
text = "CERTIFICATE OF BIRTH\nRegistration No: BC-123\nFull Name: Alice"
lines = ["CERTIFICATE OF BIRTH", "Registration No: BC-123", "Full Name: Alice"]
line_offsets = [0, 21, 46]
               ↑           ↑                                ↑
               line 0      line 1 starts at char 21         line 2 starts at char 46
```
This lets ProvenanceTracker say "the name is at line 3, chars 46–56" with perfect precision.

### Entity
```python
@dataclass
class Entity:
    entity_id:        str          # unique UUID
    name:             str          # "Alice Chen"
    entity_type:      EntityType   # PERSON, ID_NUMBER, DATE, etc.
    attributes:       dict         # {"dob": "1992-03-15", "license_number": "BC-7745291"}
    source_doc_id:    str          # which document this came from
    source_filename:  str          # "birth_certificate.txt"
    line_number:      int          # 5  (1-indexed)
    line_text:        str          # "Full Name: Alice Chen"  ← verbatim exact line
    char_offset_start: int         # 46
    char_offset_end:   int         # 56
    extractor_model:  str          # "langchain" or "uipath-document-understanding"
    confidence:       float        # 0.0–1.0
    embedding:        list[float]  # 384 floats from sentence-transformers
```

### ResolvedPair
```python
@dataclass
class ResolvedPair:
    entity_id_a:    str    # Alice Chen in birth_certificate
    entity_id_b:    str    # Alice Chen in drivers_license
    confidence:     float  # 0.97 = 0.4 × name_score + 0.6 × semantic_score
    name_score:     float  # RapidFuzz similarity = 1.0 (exact match)
    semantic_score: float  # cosine similarity of embeddings = 0.96
    llm_confirmed:  bool   # False (auto-resolved, high confidence)
```

### ConflictRecord
```python
@dataclass
class ConflictRecord:
    entity_id_a:   str   # Alice Chen in birth_certificate
    entity_id_b:   str   # Alice Chen in insurance
    conflict_type: str   # "dob_mismatch"
    attribute_key: str   # "dob"
    value_a:       str   # "1992-03-15"  ← from birth cert
    value_b:       str   # "1992-03-22"  ← from insurance (wrong)
    severity:      str   # "critical"
```

### ProvenanceEntry
```python
@dataclass
class ProvenanceEntry:
    fact:            str   # "dob: 1992-03-15"
    source_filename: str   # "birth_certificate.txt"
    line_number:     int   # 5
    line_text:       str   # "Date of Birth: March 15, 1992"  ← verbatim
    confidence:      float # 0.99
```

### QueryResult
```python
@dataclass
class QueryResult:
    question:              str
    answer:                str                  # the actual answer text
    source_documents:      list[str]            # ["birth_certificate.txt", "drivers_license.txt"]
    resolved_entities:     list[str]            # ["Alice Chen", "Alice Chen"]
    resolution_confidence: list[float]          # [0.97]
    hops_used:             int                  # 2
    provenance:            list[ProvenanceEntry] # exact source lines
    conflicts:             list[ConflictRecord]  # any contradictions found
    has_conflicts:         bool                  # True
    temporal_context:      str                   # "current"
```

---

## 7. ✅ DONE — Step 2: LLM Provider

**Files:** `graph_rag/llm/provider.py`, `ollama.py`, `openai_provider.py`

**What:** An abstraction layer so the pipeline doesn't care which LLM is running.

**Key concept: Abstract Base Class (ABC)**

```python
class LLMProvider(ABC):              # ABC = "you can't instantiate me directly"
    @abstractmethod
    def complete(self, prompt): ...  # every subclass MUST implement this
    @abstractmethod
    def chat(self, messages): ...    # every subclass MUST implement this
```

Like a job description. `OllamaProvider` and `OpenAIProvider` both fulfill it.

**Key concept: Factory function**

```python
def create_llm_provider():
    if os.getenv("LLM_PROVIDER") == "openai":
        return OpenAIProvider(...)
    else:
        return OllamaProvider(...)    # default
```

One function, reads from env var, returns the right object.
Change `LLM_PROVIDER=openai` in `.env` → entire pipeline switches to OpenAI.

**OllamaProvider** — calls `http://localhost:11434`
- Uses `requests` library to make HTTP POST calls
- `/api/generate` for single prompts
- `/api/chat` for conversation history
- `stream: false` to get the full response at once
- Your Ollama is running with `qwen2.5:14b-instruct-q4_K_M` ✓

**OpenAIProvider** — calls OpenAI API
- Uses the `openai` Python SDK
- Reads `OPENAI_API_KEY` from environment variable only
- Never hardcoded in source code

**Temperature = 0.0**
For extraction tasks we want deterministic output.
- Temperature 0.0 = same input always gives same output
- Temperature 1.0 = creative, random, unpredictable
We always use 0.0 for document classification and entity extraction.

**Environment variables** (in `.env` file, never committed to git):
```
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:14b-instruct-q4_K_M
OLLAMA_HOST=http://localhost:11434
```

**Usage:**
```python
from graph_rag.llm import create_llm_provider

llm = create_llm_provider()
result = llm.complete("What type of document is this? ...")
# → "BIRTH_CERTIFICATE"
```

---

## 8. 🔲 NEXT — Step 3: Document Loader

**File:** `graph_rag/core/loader.py` (to be built)

**What:** Reads `.txt` files from disk and converts them into `Document` objects.

**Concept: Why split into lines and compute offsets?**

The provenance feature requires knowing the exact line number and character
position of every extracted fact. The DocumentLoader pre-computes this
once so every downstream component has instant access.

```python
text = open("birth_certificate.txt").read()

# Split into lines
lines = text.split("\n")
# → ["CERTIFICATE OF BIRTH", "Registration No: BC-123", "Full Name: Alice Chen", ...]

# Compute where each line starts in the full text
line_offsets = []
pos = 0
for line in lines:
    line_offsets.append(pos)
    pos += len(line) + 1  # +1 for the \n character

# Later: ProvenanceTracker can verify
assert text[line_offsets[4]:line_offsets[4]+len(lines[4])] == lines[4]
```

**What it will do:**
- Read `.txt` files (UTF-8 encoding)
- Split text into lines (by `\n`) and paragraphs (by `\n\n`)
- Compute character offset for each line
- Assign a UUID v4 as `doc_id`
- Handle missing files gracefully (log warning, skip, continue)
- Handle empty files (mark `empty=True`, still add to graph)
- Support loading a single file or an entire directory

**What it will NOT do:**
- It won't classify the document type (that's the Classifier)
- It won't extract entities (that's the Extractor)
- It just reads and structures the raw text

---

## 9. 🔲 UPCOMING — Step 4: Document Classifier

**File:** `graph_rag/extraction/classifier.py` (to be built)

**What:** Sends the first 500 characters to the LLM and gets back a `DocType`.

**How it works:**
```python
prompt = """You are a document classifier.
Classify this document as exactly one of:
BIRTH_CERTIFICATE, DRIVERS_LICENSE, PASSPORT, INSURANCE, MEDICAL_RECORD, GENERIC

Respond with ONLY the type name.

Document:
{text[:500]}"""

result = llm.complete(prompt)
# → "BIRTH_CERTIFICATE"
doc_type = DocType(result)
```

**Why only 500 characters?**
The beginning of a document (header, title) is almost always enough to
identify its type. Using the full document wastes tokens and time.

**Fallback:** if LLM returns something not in DocType, assign GENERIC.

**Each DocType maps to a specific extraction schema:**
- BIRTH_CERTIFICATE → extract: name, dob, place_of_birth, parents, registration_number
- DRIVERS_LICENSE   → extract: name, dob, license_number, address, expiry_date
- PASSPORT          → extract: name, dob, passport_number, nationality, expiry_date
- INSURANCE         → extract: name, dob, policy_number, coverage_type, beneficiary
- MEDICAL_RECORD    → extract: patient_name, dob, diagnosis, doctor, medications

---

## 10. 🔲 UPCOMING — Step 5: LangChain Extractor

**File:** `graph_rag/extraction/langchain_extractor.py` (to be built)

**What:** Uses the LLM to extract entities with exact provenance from `.txt` files.

**The key innovation — provenance extraction:**

Normal extraction just pulls values. This extractor also finds the exact
line number and verbatim text for every value.

```python
prompt = """Extract entities from this BIRTH_CERTIFICATE.
Return JSON with this exact structure:
{
  "entities": [
    {
      "name": "Alice Chen",
      "entity_type": "PERSON",
      "attributes": {"dob": "1992-03-15", "place_of_birth": "Vancouver"},
      "line_number": 5,
      "line_text": "Full Name: Alice Chen"
    }
  ]
}

Document (with line numbers):
1: CERTIFICATE OF BIRTH
2: Registration No: BC-2024-00441
3:
4: Full Name: Alice Chen
5: Date of Birth: March 15, 1992
...
"""
```

**JSON parsing with retry:**
- LLMs sometimes return malformed JSON
- Try to parse → if it fails → retry once with a stricter prompt
- If retry fails → skip this entity, log warning, continue

**After extraction:**
- `EmbeddingEngine.embed(entity.name + str(entity.attributes))` → store as `entity.embedding`
- Set `extractor_model = "langchain"` on every entity

---

## 11. 🔲 UPCOMING — Step 6: UiPath Extractor

**File:** `graph_rag/extraction/uipath_extractor.py` (to be built)

**What:** Parses UiPath Document Understanding JSON into the same `Entity` format.
No LLM call needed — UiPath already extracted the fields.

**Input (your .json files):**
```json
{
  "document_type": "BIRTH_CERTIFICATE",
  "confidence": 0.98,
  "fields": {
    "name": { "value": "Alice Chen",  "confidence": 0.99, "bounding_box": [72, 120, 400, 140] },
    "dob":  { "value": "1992-03-15",  "confidence": 0.99, "bounding_box": [72, 145, 400, 165] }
  }
}
```

**Mapping to Entity:**
```python
entity.name              = fields["name"]["value"]       # "Alice Chen"
entity.confidence        = fields["name"]["confidence"]  # 0.99
entity.char_offset_start = bounding_box[0]               # 72 (x1)
entity.char_offset_end   = bounding_box[2]               # 400 (x2)
entity.extractor_model   = "uipath-document-understanding"
```

**Advantage over LangChain:**
- Faster (no LLM call for extraction)
- More accurate for scanned/printed documents
- Bounding boxes give pixel-level location, not just line number
- Used in your company's existing UiPath pipeline

---

## 12. 🔲 UPCOMING — Step 7: Embedding Engine

**File:** `graph_rag/core/embeddings.py` (to be built)

**What:** Converts text into vectors (lists of numbers) that capture meaning.

**Concept: What is an embedding?**

```
"Alice Chen, born 1992"    → [0.23, -0.41, 0.87, 0.12, ...]  (384 numbers)
"Alice Chen, DOB 03/1992"  → [0.24, -0.40, 0.86, 0.11, ...]  (384 numbers)
"John Smith, born 1988"    → [-0.31, 0.22, -0.44, 0.67, ...] (384 numbers)
```

The first two are similar (same person, different format) → their vectors
are close together in 384-dimensional space.
The third is different → its vector is far away.

**Cosine similarity** measures the "angle" between two vectors:
- 1.0 = identical meaning
- 0.0 = completely unrelated
- Values < 0 = opposite meaning

**Model: `all-MiniLM-L6-v2`**
- Runs 100% locally (no API, no internet needed)
- Generates 384-dimensional vectors
- Fast: ~1000 sentences per second on CPU
- Install: `pip install sentence-transformers`

**Caching:**
Computing embeddings takes time. If you ingest 1000 documents,
you don't want to recompute the embedding for "Alice Chen" every time it appears.
We cache by SHA-256 hash of the input text.

**Used in:**
- EntityResolver: compare entity embeddings to find same people
- QueryEngine: embed the question for semantic search
- ContextAggregator: rank documents by semantic similarity to query

---

## 13. 🔲 UPCOMING — Step 8: Knowledge Graph Builder

**File:** `graph_rag/core/graph_builder.py` (to be built)

**What:** Maintains the in-memory NetworkX graph. Adds nodes and edges.

**Concept: What is NetworkX?**

NetworkX is a Python library for working with graphs (networks of nodes
connected by edges). Our knowledge graph has:

```
Nodes:
  document node — one per file
  entity node   — one per extracted entity

Edges:
  mentions  — entity → document (entity was found in this file)
  same_as   — entity ↔ entity (same person, different documents)
  conflict  — entity ↔ entity (same person but contradictory data)
```

**Visual example:**
```
[birth_certificate.txt]   [drivers_license.txt]   [insurance.txt]
        │                          │                      │
     mentions                   mentions               mentions
        │                          │                      │
  [Alice Chen BC]  ←─same_as─►  [Alice Chen DL] ─same_as─►  [Alice Chen INS]
      PERSON                       PERSON                     PERSON
  dob: Mar 15                  license: BC-7745          dob: Mar 22 ← conflict!
                                                          policy: INS-887
                                     └──────────conflict──────────┘
```

**Node attributes (what's stored on each node):**
```python
# Document node
{
    "node_type": "document",
    "doc_id":    "abc-123",
    "filename":  "birth_certificate.txt",
    "doc_type":  "BIRTH_CERTIFICATE",
    "doc_date":  "1992-04-02",
    "text":      "CERTIFICATE OF BIRTH\n..."
}

# Entity node
{
    "node_type":       "entity",
    "entity_id":       "def-456",
    "name":            "Alice Chen",
    "entity_type":     "PERSON",
    "attributes":      {"dob": "1992-03-15"},
    "source_doc_id":   "abc-123",
    "embedding":       [0.23, -0.41, ...],
    "confidence":      0.99
}
```

**Edge attributes:**
```python
# mentions edge
{"edge_type": "mentions", "line_number": 5, "line_text": "Full Name: Alice Chen"}

# same_as edge
{"edge_type": "same_as", "confidence": 0.97, "name_score": 1.0, "semantic_score": 0.96}

# conflict edge
{"edge_type": "conflict", "conflict_type": "dob_mismatch", "severity": "critical",
 "value_a": "1992-03-15", "value_b": "1992-03-22"}
```

---

## 14. 🔲 UPCOMING — Step 9: Entity Resolver

**File:** `graph_rag/core/resolver.py` (to be built)

**What:** Finds entities across different documents that refer to the same real person,
and adds `same_as` edges between them.

**The hybrid scoring formula:**
```
confidence = 0.4 × name_similarity + 0.6 × semantic_similarity
```

**Name similarity (RapidFuzz):**
```python
from rapidfuzz import fuzz
score = fuzz.token_ratio("James Lee", "James Robert Lee") / 100.0
# → 0.82
```
RapidFuzz is like difflib but 100x faster. `token_ratio` handles word reordering.

**Semantic similarity (cosine):**
```python
# embed "James Lee, DOB 1988, Toronto" and "James R. Lee, patient"
# → vectors are close because both are about the same person
semantic_score = cosine_similarity(embedding_a, embedding_b)
# → 0.91
```

**Decision thresholds:**
```
confidence ≥ 0.85 → auto-link (add same_as edge directly)
0.60 ≤ confidence < 0.85 → ask LLM to confirm
confidence < 0.60 → no link (different people)
```

**Why not just name matching?**
"James Lee" and "James Walker" have similar names (both "James").
Their embeddings would be different because the contexts differ.
The hybrid approach catches this — name_score alone might be high,
but semantic_score brings it below 0.60, so no false link.

**Rules:**
- Never link two entities from the same document (same person can't appear twice)
- Never link an entity to itself

---

## 15. 🔲 UPCOMING — Step 10: Contradiction Detector

**File:** `graph_rag/core/contradiction.py` (to be built)

**What:** After same_as edges are added, scans every linked pair for
attribute value mismatches. Adds `conflict` edges for each mismatch.

**Example:**
```
Alice Chen (birth_cert):  dob = "1992-03-15"
Alice Chen (insurance):   dob = "1992-03-22"
→ conflict_type = "dob_mismatch", severity = "critical"
```

**Severity levels:**
```python
CRITICAL_KEYS = {"dob", "name", "license_number", "passport_number", "policy_number"}
MINOR_KEYS    = {"address", "phone", "email"}
```

**Value normalization before comparison:**
- Strip whitespace
- Lowercase
- Normalize date formats: "March 15, 1992" == "1992-03-15" == "15/03/1992"
- This prevents false conflicts from formatting differences

**Output in QueryResult:**
```
⚠ CONFLICT DETECTED:
  dob_mismatch (critical)
  birth_certificate.txt says: 1992-03-15
  insurance.txt says:         1992-03-22
```

---

## 16. 🔲 UPCOMING — Step 11: Temporal Filter

**File:** `graph_rag/core/temporal.py` (to be built)

**What:** Handles time-aware queries — "current address" returns the most recent document.

**Concept:** Documents have a `doc_date`. When a person moves, their new
license has a newer date than their old one. The temporal filter picks
the most recent.

**Query: "What is Alice's current address?"**
```
drivers_license_2015.txt  doc_date = 2015-06-10  address = "100 Oak Ave"
drivers_license_2022.txt  doc_date = 2022-03-01  address = "204 Maple Street"

temporal_context = "current" → picks doc_date = 2022-03-01
→ returns "204 Maple Street"
```

**same_as edges have validity windows:**
```python
# The 2015 license is superseded by the 2022 one
same_as edge: valid_from = "2015-06-10", valid_until = "2022-02-28"
```

**Three temporal contexts:**
- `"current"` — most recent document wins
- `"all"` — return all documents regardless of date
- `"2020-01-01"` — return documents valid as of that date

---

## 17. 🔲 UPCOMING — Step 12: Multi-hop Traversal

**File:** `graph_rag/query/traversal.py` (to be built)

**What:** BFS (Breadth-First Search) through the graph, following same_as edges.

**Concept: BFS (Breadth-First Search)**

BFS explores a graph level by level. Starting from seed nodes (the entities
matching your query), it visits all direct neighbors first, then their
neighbors, and so on — up to `max_hops` depth.

```
Query: "What medication was prescribed to James Lee?"

Hop 0 (seed):  [James Lee — birth_certificate.txt]
Hop 1:         [James Lee — passport.txt]          ← via same_as
Hop 2:         [James R. Lee — medical_record.txt] ← via same_as
               → finds: diagnosis, medications, doctor

Answer: "Cetirizine 10mg daily, Fluticasone nasal spray
         (from medical_record.txt, line 12)"
```

**Why max_hops?**
Without a limit, BFS could traverse the entire graph for every query.
We cap at 5 hops — enough for complex scenarios, fast enough to be practical.

**Confidence threshold:**
Only traverse `same_as` edges with confidence ≥ 0.60.
Low-confidence links might be false positives — don't follow them.

**Cycle prevention:**
BFS keeps a `visited` set. Once a node is visited, never visit it again.
This prevents infinite loops on circular graphs.

---

## 18. 🔲 UPCOMING — Step 13: Context Aggregator

**File:** `graph_rag/query/aggregator.py` (to be built)

**What:** Takes the documents found by traversal, deduplicates them,
ranks them by relevance, and truncates to fit the LLM's context window.

**Hybrid relevance score:**
```
relevance = 0.4 × graph_centrality + 0.6 × cosine_similarity(query, doc)
```

- `graph_centrality` — how connected this document is in the graph
  (a document mentioned by many entities scores higher)
- `cosine_similarity` — how semantically similar the document is to the query

**Context window:**
LLMs can only process a limited amount of text at once:
- Ollama (qwen2.5): ~4,096 tokens ≈ 3,000 words
- OpenAI GPT-4o: ~128,000 tokens ≈ 96,000 words

If we found 20 documents but only 5 fit in the context window,
we keep the top 5 by relevance score.

---

## 19. 🔲 UPCOMING — Step 14: Provenance Tracker

**File:** `graph_rag/query/provenance.py` (to be built)

**What:** For every entity in the answer, finds the exact line in the
source document and creates a `ProvenanceEntry`.

**How it works:**
```python
# Entity has: line_number = 5, source_filename = "birth_certificate.txt"
# Document has: lines[4] = "Date of Birth: March 15, 1992"
#                          (line_number is 1-indexed, list is 0-indexed)

entry = ProvenanceEntry(
    fact            = "dob: 1992-03-15",
    source_filename = "birth_certificate.txt",
    line_number     = 5,
    line_text       = "Date of Birth: March 15, 1992",  # ← verbatim
    confidence      = 0.99
)
```

**The `verify()` function:**
```python
entries = tracker.verify("Alice's DOB")
print(entries[0].line_text)
# → "Date of Birth: March 15, 1992"
print(entries[0].source_filename, "line", entries[0].line_number)
# → birth_certificate.txt line 5
```

**React ProvenanceList displays:**
```
📄 birth_certificate.txt — Line 5
   "Date of Birth: March 15, 1992"
   Confidence: 99%
```

---

## 20. 🔲 UPCOMING — Step 15: Query Engine

**File:** `graph_rag/query/engine.py` (to be built)

**What:** Orchestrates the entire query pipeline. The main coordinator.

**Steps:**
1. LLM extracts entity names from the question → `["Alice Chen"]`
2. EmbeddingEngine embeds the question → `[384 floats]`
3. MultiHopTraversal finds matching entities and expands via same_as
4. TemporalFilter filters by date if needed
5. ContextAggregator ranks and truncates documents
6. ProvenanceTracker maps facts to source lines
7. LLM synthesizes the final answer
8. Returns `QueryResult` with answer + provenance + conflicts

**Usage:**
```python
engine = QueryEngine(graph, llm, embedding_engine)
result = engine.query(
    "What is Alice's license number and insurance policy?",
    max_hops=3,
    temporal_context="current"
)
print(result.answer)
# → "Alice's license number is BC-7745291 and her insurance policy is INS-2019-887341."
for p in result.provenance:
    print(f"  [{p.source_filename}:{p.line_number}] {p.line_text}")
# → [drivers_license.txt:5] License Number: BC-7745291
# → [insurance.txt:4] Policy Number: INS-2019-887341
```

---

## 21. 🔲 UPCOMING — Step 16: FastAPI REST API

**File:** `graph_rag/api/app.py` (to be built)

**What:** HTTP server that exposes the pipeline as a REST API.

**Concept: What is FastAPI?**

FastAPI is a modern Python web framework. You define functions with
type annotations and it automatically:
- Validates incoming JSON
- Generates interactive docs at `/docs`
- Serializes responses as JSON

**Endpoints:**

| Method | Path | What it does |
|---|---|---|
| `POST` | `/ingest` | Ingest `.txt` files (LangChain mode) |
| `POST` | `/ingest/uipath` | Ingest UiPath `.json` files |
| `POST` | `/query` | Ask a question, get QueryResult |
| `GET` | `/graph/stats` | Node/edge counts by type |
| `GET` | `/graph/visualize` | Interactive HTML graph |
| `GET` | `/entities` | List all entities |
| `DELETE` | `/graph` | Reset the graph |
| `GET` | `/extraction/modes` | Which extractor is active |
| `POST` | `/extraction/mode` | Switch LangChain ↔ UiPath |

**Example request:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Alice'\''s license number?", "max_hops": 3}'
```

---

## 22. 🔲 UPCOMING — Step 17: CLI

**File:** `graph_rag.py` (to be built, replaces the stub `rag.py`)

**What:** Command-line interface using the `Click` library.

```bash
# Ingest documents
python graph_rag.py ingest --dir docs/people/alice_chen --extractor langchain
python graph_rag.py ingest --dir docs/people/alice_chen --extractor uipath

# Query
python graph_rag.py query "What is Alice's license number?"
python graph_rag.py query "What is Alice's DOB?" --hops 3 --temporal current

# Verify a fact (shows exact source line)
python graph_rag.py verify "Alice's DOB"

# Visualize the graph
python graph_rag.py visualize --output graph.html

# Start the REST API server
python graph_rag.py serve --port 8000

# Graph statistics
python graph_rag.py stats
```

---

## 23. 🔲 UPCOMING — Step 18: Graph Visualizer

**File:** `graph_rag/visualization/visualizer.py` (to be built)

**What:** Renders the knowledge graph as an interactive HTML file using Pyvis.

**Pyvis** is a Python library that wraps the vis.js JavaScript library.
You pass it a NetworkX graph and it generates an HTML file you can open
in any browser — drag nodes, zoom, click for details.

**Node colors:**
| Entity Type | Color |
|---|---|
| PERSON | `#4A90D9` (blue) |
| DOCUMENT | `#27AE60` (green) |
| ID_NUMBER | `#E67E22` (orange) |
| DATE | `#9B59B6` (purple) |
| ORGANIZATION | `#E74C3C` (red) |
| LOCATION | `#1ABC9C` (teal) |

**Edge styles:**
| Edge Type | Style |
|---|---|
| `mentions` | dashed grey |
| `same_as` | solid bold, color = red→green based on confidence |
| `conflict` | dotted red bold |

**Click a node** → tooltip shows all attributes, source file, confidence.

---

## 24. 🔲 UPCOMING — Step 19: React Frontend

**Directory:** `frontend/` (to be built)

**What:** A single-page web app built with React + TypeScript + Vite + TailwindCSS.

**Component tree:**
```
App
├── Header
│   └── ExtractionToggle    ← [🔗 LangChain]  [🤖 UiPath] button toggle
├── IngestPanel
│   ├── DocumentUpload      ← drag & drop files
│   └── IngestButton
├── QueryPanel
│   ├── QueryInput          ← text field for the question
│   ├── HopSlider           ← 1 ─────────●───── 5  (max_hops)
│   ├── TemporalSelect      ← [current ▼] dropdown
│   └── QueryButton
├── ResultsPanel
│   ├── AnswerDisplay       ← the answer text
│   ├── ProvenanceList      ← 📄 birth_certificate.txt — Line 5
│   │                          "Date of Birth: March 15, 1992"
│   ├── ConflictWarnings    ← 🔴 CRITICAL: dob_mismatch
│   └── SourceDocuments     ← list of files used
├── GraphPanel
│   ├── GraphVisualization  ← embedded Pyvis HTML in iframe
│   └── GraphStats          ← Nodes: 142  Edges: 89
└── EntitiesPanel
    └── EntityTable         ← searchable table of all entities
```

**ExtractionToggle — the key UI feature:**
```
Extraction Engine:  [🔗 LangChain (LLM)]  [🤖 UiPath Document Understanding]
                     ↑ active (highlighted)  ↑ inactive
```
Clicking sends `POST /extraction/mode` to the backend.
The file upload then accepts `.txt` (LangChain) or `.json` (UiPath) accordingly.

**React + TypeScript concepts:**
- `useState` — local component state (e.g. active extraction mode)
- `useEffect` — side effects (e.g. fetch `/entities` on mount)
- `axios` — HTTP client for API calls
- TypeScript interfaces — type safety for API responses

---

## 25. 🔲 UPCOMING — Step 20: Tests

**Directory:** `tests/` (to be built)

**Two types of tests:**

### Unit tests (pytest)
Test each component in isolation with mock inputs:
```python
def test_contradiction_detector_finds_dob_mismatch():
    # Build a minimal graph with two same_as entities that have different DOBs
    # Run ContradictionDetector
    # Assert: one ConflictRecord with conflict_type="dob_mismatch", severity="critical"
```

### Property-based tests (hypothesis)
Instead of one specific input, hypothesis generates hundreds of random inputs
and checks that a property ALWAYS holds:
```python
@given(entities=st.lists(entity_strategy(), min_size=2))
def test_no_self_loop_same_as_edges(entities):
    # After resolution, no entity should have a same_as edge to itself
    resolver.resolve(graph)
    for node in graph.nodes:
        assert not graph.has_edge(node, node)
```

**Key properties to test:**
- No self-loop `same_as` edges
- All `same_as` edges connect entities from DIFFERENT source documents
- Confidence scores always in [0.0, 1.0]
- `expand(expand(seed)) == expand(seed)` (BFS fixed point)
- `provenance.line_text == document.lines[provenance.line_number - 1]`

---

## 26. Key Concepts Glossary

| Term | Definition |
|---|---|
| **RAG** | Retrieval-Augmented Generation — give an LLM your documents as context |
| **Graph RAG** | RAG + knowledge graph to link entities across documents |
| **Entity** | A named thing extracted from a document (person, ID, date) |
| **Embedding** | A list of numbers representing the meaning of text |
| **Cosine similarity** | How similar two embeddings are (1.0 = identical, 0.0 = unrelated) |
| **same_as edge** | Graph edge linking the same entity across different documents |
| **conflict edge** | Graph edge marking a data contradiction between linked entities |
| **mentions edge** | Graph edge linking an entity to the document it came from |
| **BFS** | Breadth-First Search — graph traversal algorithm level by level |
| **Multi-hop** | Following a chain of same_as edges across 3+ documents |
| **Provenance** | Tracing a fact back to its exact source line in the document |
| **DocType** | Enum: BIRTH_CERTIFICATE, DRIVERS_LICENSE, PASSPORT, INSURANCE, MEDICAL_RECORD |
| **ABC** | Abstract Base Class — defines a contract that subclasses must fulfill |
| **Factory function** | A function that returns the right object based on config |
| **Temperature** | LLM randomness: 0.0 = deterministic, 1.0 = creative |
| **Token** | ~3/4 of a word. LLMs process tokens, not words |
| **Context window** | Max tokens an LLM can process at once |
| **UiPath** | RPA platform with Document Understanding — extracts fields from scanned docs |
| **NetworkX** | Python library for working with graphs (nodes + edges) |
| **RapidFuzz** | Fast fuzzy string similarity library |
| **hypothesis** | Property-based testing library — generates random test inputs |

---

## 27. Common Questions

**Q: Why NetworkX instead of Neo4j?**
Neo4j is a proper graph database — great for production at scale.
NetworkX is in-memory Python — simpler setup, no database server needed.
The `KnowledgeGraphBuilder` interface is designed so you can swap to Neo4j
later without changing any other component.

**Q: Why sentence-transformers instead of OpenAI embeddings?**
OpenAI embeddings cost money and require internet. sentence-transformers
runs completely locally, is free, and for our use case (person name matching)
it performs equally well.

**Q: What's the difference between LangChain mode and UiPath mode?**
LangChain: you give it raw text → LLM reads and extracts entities
UiPath: UiPath already extracted the fields → we just parse the JSON
UiPath is faster and better for scanned documents. LangChain is more
flexible and works with any text format.

**Q: Why does the Entity have BOTH `line_number` AND `char_offset_start`?**
`line_number` is human-readable ("line 5 of the document").
`char_offset_start` is machine-precise ("character 46 in the full text").
The ProvenanceTracker uses line_number for display and char offsets for
verification.

**Q: What is the confidence threshold 0.85 / 0.60 based on?**
These are common thresholds in entity resolution research.
≥ 0.85: high enough confidence to auto-link without review.
0.60–0.85: borderline — ask the LLM to make the final call.
< 0.60: too uncertain — don't link.
These can be tuned based on your specific documents.

**Q: Why do we need the Temporal Filter?**
Without it, "Alice's current address" would return ALL addresses Alice
ever had (from 2015 license AND 2022 license). The temporal filter
picks the most recent document, giving you the current address.

---

## Progress Tracker

| Step | Component | Status | File |
|---|---|---|---|
| 0 | Synthetic Dataset | ✅ Done | `docs/people/` |
| 0 | Dataset Generator | ✅ Done | `generate_dataset.py` |
| 1 | Data Models | ✅ Done | `graph_rag/core/models.py` |
| 2 | LLM Provider | ✅ Done | `graph_rag/llm/` |
| 3 | Document Loader | ✅ Done | `graph_rag/core/loader.py` |
| 4 | Document Classifier | 🔲 | `graph_rag/extraction/classifier.py` |
| 5 | LangChain Extractor | 🔲 | `graph_rag/extraction/langchain_extractor.py` |
| 6 | UiPath Extractor | 🔲 | `graph_rag/extraction/uipath_extractor.py` |
| 7 | Embedding Engine | 🔲 | `graph_rag/core/embeddings.py` |
| 8 | Knowledge Graph Builder | 🔲 | `graph_rag/core/graph_builder.py` |
| 9 | Entity Resolver | 🔲 | `graph_rag/core/resolver.py` |
| 10 | Contradiction Detector | 🔲 | `graph_rag/core/contradiction.py` |
| 11 | Temporal Filter | 🔲 | `graph_rag/core/temporal.py` |
| 12 | Multi-hop Traversal | 🔲 | `graph_rag/query/traversal.py` |
| 13 | Context Aggregator | 🔲 | `graph_rag/query/aggregator.py` |
| 14 | Provenance Tracker | 🔲 | `graph_rag/query/provenance.py` |
| 15 | Query Engine | 🔲 | `graph_rag/query/engine.py` |
| 16 | FastAPI REST API | 🔲 | `graph_rag/api/app.py` |
| 17 | CLI | 🔲 | `graph_rag.py` |
| 18 | Graph Visualizer | 🔲 | `graph_rag/visualization/visualizer.py` |
| 19 | React Frontend | 🔲 | `frontend/` |
| 20 | Tests | 🔲 | `tests/` |
