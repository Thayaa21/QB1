# Requirements Document

## Introduction

Graph RAG is a temporal, confidence-scored knowledge graph system for retrieval-augmented generation over multi-document corpora. It extracts named entities from ingested documents, resolves co-referent entities across documents, traverses entity chains via multi-hop reasoning, and synthesizes answers with full verifiable provenance linking every fact to the exact source line. The system supports two extraction engines (LangChain LLM-based and UiPath Document Understanding), a React frontend, a FastAPI REST API, a CLI, and an interactive graph visualization layer.

---

## Glossary

- **Graph_RAG_System**: The complete Graph RAG pipeline including ingestion, resolution, querying, and visualization.
- **Document_Loader**: Component that reads raw text or UiPath JSON files and produces structured Document objects.
- **Document_Classifier**: Component that uses an LLM to detect document type from document text.
- **Entity_Extractor**: LLM-based component that extracts named entities and their attributes from a classified document.
- **Extraction_Provider**: Abstract interface that wraps either LangChainExtractor or UiPathExtractor.
- **LangChain_Extractor**: ExtractionProvider implementation using Document_Classifier + Entity_Extractor LLM pipeline.
- **UiPath_Extractor**: ExtractionProvider implementation that parses pre-structured UiPath Document Understanding JSON.
- **Embedding_Engine**: Component that generates dense vector embeddings using a local sentence-transformer model.
- **Knowledge_Graph**: In-memory NetworkX directed graph holding Document nodes, Entity nodes, and typed edges.
- **Graph_Builder**: Component that adds documents, entities, and typed edges to the Knowledge_Graph.
- **Entity_Resolver**: Component that identifies co-referent entities across documents and produces `same_as` edges.
- **Temporal_Filter**: Component that filters entities and edges by document date and temporal validity windows.
- **Contradiction_Detector**: Component that scans `same_as`-linked entity pairs for conflicting attribute values.
- **Multi_Hop_Traversal**: BFS component that expands entity sets via `same_as` edges up to a configured depth.
- **Context_Aggregator**: Component that deduplicates, ranks, and formats retrieved document chunks.
- **Provenance_Tracker**: Component that records the exact source line for every extracted entity attribute.
- **Query_Engine**: Orchestrator that coordinates traversal, filtering, aggregation, and LLM synthesis for a query.
- **Graph_Visualizer**: Component that renders the Knowledge_Graph as an interactive HTML file using Pyvis.
- **LLM_Provider**: Abstract factory over Ollama (local) and OpenAI (cloud) inference backends.
- **REST_API**: FastAPI server exposing HTTP endpoints for ingest, query, visualization, and administration.
- **CLI**: Click-based command-line interface for ingest, query, visualize, verify, serve, and stats commands.
- **React_Frontend**: TypeScript React single-page application providing the web UI.
- **ExtractionToggle**: React component that switches the active extraction engine between LangChain and UiPath.
- **DocumentUpload**: React component for drag-and-drop file ingestion.
- **QueryInput**: React component for submitting natural language questions.
- **AnswerDisplay**: React component that renders the synthesized answer text.
- **ProvenanceList**: React component that lists per-fact source file, line number, and verbatim line text.
- **ConflictWarnings**: React component that renders color-coded conflict cards.
- **GraphVisualization**: React component that embeds the Pyvis HTML graph in an iframe.
- **EntityTable**: React component showing a searchable table of all entities in the graph.
- **DocType**: Enumeration of supported document types: BIRTH_CERTIFICATE, DRIVERS_LICENSE, PASSPORT, INSURANCE, MEDICAL_RECORD, GENERIC.
- **Entity**: A named node in the Knowledge_Graph with attributes, provenance metadata, and an embedding vector.
- **ProvenanceEntry**: A record linking one extracted fact to its exact source filename, line number, and verbatim line text.
- **ConflictRecord**: A record of a detected attribute mismatch between two `same_as`-linked entities.
- **QueryResult**: The structured response from the Query_Engine containing answer, provenance, conflicts, and metadata.
- **same_as_edge**: A typed graph edge connecting co-referent entities from different source documents.
- **mentions_edge**: A typed graph edge connecting an Entity node to the Document node it was extracted from.
- **conflict_edge**: A typed graph edge recording an attribute mismatch between two same_as-linked entities.
- **Confidence_Score**: A floating-point value in [0.0, 1.0] representing certainty of an extraction or resolution.

---

## Requirements

### Requirement 1: Document Ingestion and Loading

**User Story:** As a user, I want to ingest a set of raw text documents into the system, so that their entities and relationships can be extracted, indexed, and made queryable.

#### Acceptance Criteria

1. WHEN a user provides one or more file paths to the Document_Loader, THE Document_Loader SHALL read each file, split its text into individual lines and paragraphs, record the character offset of each line start, and produce a Document object for each file.
2. WHEN the Document_Loader processes a file, THE Document_Loader SHALL assign a universally unique identifier as the `doc_id` for that Document.
3. IF a provided file path does not exist or cannot be read, THEN THE Document_Loader SHALL skip that file, log a warning containing the path, and continue processing the remaining paths.
4. WHEN a document contains no text, THE Document_Loader SHALL still create a Document node marked with `empty=True` and add it to the Knowledge_Graph without attempting entity extraction.
5. WHEN a directory path is provided to the Document_Loader, THE Document_Loader SHALL discover and load all `.txt` files within that directory.
6. THE Graph_RAG_System SHALL ingest at least one document per ingest call; IF zero valid paths are supplied, THEN THE Graph_RAG_System SHALL return an error message without modifying the Knowledge_Graph.

---

### Requirement 2: Document Type Classification

**User Story:** As a user, I want each ingested document to be automatically classified by type, so that the correct entity extraction schema is applied and downstream processing is tailored to the document's content.

#### Acceptance Criteria

1. WHEN a document is classified, THE Document_Classifier SHALL send the first 500 characters of the document text to the LLM_Provider and assign the returned DocType value to the Document.
2. THE Document_Classifier SHALL support exactly the following DocType values: BIRTH_CERTIFICATE, DRIVERS_LICENSE, PASSPORT, INSURANCE, MEDICAL_RECORD, and GENERIC.
3. WHEN the LLM_Provider returns a DocType value not in the supported set, THE Document_Classifier SHALL assign the DocType GENERIC to that document.
4. WHEN a document is classified as BIRTH_CERTIFICATE, THE Entity_Extractor SHALL use the schema containing the fields: name, dob, place_of_birth, parents, and registration_number.
5. WHEN a document is classified as DRIVERS_LICENSE, THE Entity_Extractor SHALL use the schema containing the fields: name, dob, license_number, address, expiry_date, issue_date, and vehicle_class.
6. WHEN a document is classified as PASSPORT, THE Entity_Extractor SHALL use the schema containing the fields: name, dob, passport_number, nationality, expiry_date, and place_of_issue.
7. WHEN a document is classified as INSURANCE, THE Entity_Extractor SHALL use the schema containing the fields: name, policy_number, beneficiary, coverage_type, premium, and start_date.
8. WHEN a document is classified as MEDICAL_RECORD, THE Entity_Extractor SHALL use the schema containing the fields: patient_name, dob, diagnosis, doctor, date, and medications.
9. WHEN a document is classified as GENERIC, THE Entity_Extractor SHALL attempt best-effort extraction using the fields: name, id_number, date, and address.

---

### Requirement 3: LangChain Entity Extraction with Provenance

**User Story:** As a user, I want every extracted entity to carry exact provenance metadata including line number and verbatim line text, so that every fact in the system is traceable to its source.

#### Acceptance Criteria

1. WHEN the LangChain_Extractor processes a document, THE Entity_Extractor SHALL send the document text and the doc-type-specific schema to the LLM_Provider and parse the response into a list of Entity objects.
2. THE Entity_Extractor SHALL populate the following provenance fields on each Entity: `line_number` (1-indexed), `line_text` (verbatim exact line), `paragraph_index` (0-indexed), `paragraph_text`, `char_offset_start`, and `char_offset_end`.
3. THE Entity_Extractor SHALL tag each Entity with `extractor_model` set to the identifier of the LLM model used, `extraction_timestamp` in ISO 8601 format, and `confidence` as a value in [0.0, 1.0].
4. IF the LLM_Provider returns malformed JSON for an entity, THEN THE Entity_Extractor SHALL retry extraction once and, if the retry also fails, SHALL skip that entity and log a warning including the document filename.
5. WHEN the LangChain_Extractor extracts an entity, THE Embedding_Engine SHALL compute a dense embedding for the concatenation of the entity name and its attributes string, and THE Entity_Extractor SHALL store that embedding on the Entity.
6. THE Entity_Extractor SHALL tag each extracted entity with `extractor_model = "langchain"` when operating in LangChain mode.

---

### Requirement 4: UiPath Document Understanding Extraction

**User Story:** As a user, I want to supply pre-structured UiPath Document Understanding JSON exports as an alternative to raw text, so that I can leverage high-accuracy structured extraction from UiPath without re-running LLM classification.

#### Acceptance Criteria

1. WHEN the UiPath_Extractor receives a UiPath JSON file, THE UiPath_Extractor SHALL parse the `document_type` field and map it to the corresponding DocType enum value, assigning it to the resulting Document.
2. THE UiPath_Extractor SHALL map each field in the `fields` object of the UiPath JSON to an entity attribute, using `fields[key].value` as the attribute value and `fields[key].confidence` as the entity confidence.
3. THE UiPath_Extractor SHALL store the raw `bounding_box` from each UiPath JSON field in the entity's metadata and produce an approximate `char_offset_start` and `char_offset_end` from it.
4. THE UiPath_Extractor SHALL tag each extracted entity with `extractor_model = "uipath-document-understanding"`.
5. WHEN the UiPath_Extractor processes a document, THE Embedding_Engine SHALL compute a dense embedding for each entity and store it on the Entity.
6. IF the UiPath JSON file is malformed or missing required fields, THEN THE UiPath_Extractor SHALL skip the file, log a descriptive error, and continue with remaining files.

---

### Requirement 5: Extraction Mode Switching

**User Story:** As a user, I want to switch the active extraction engine between LangChain and UiPath via the frontend toggle or API, so that I can choose the best extraction approach for each ingestion session.

#### Acceptance Criteria

1. THE Graph_RAG_System SHALL maintain a single active extraction mode at any time, which SHALL be either `"langchain"` or `"uipath"`.
2. WHEN a user sends `POST /extraction/mode` with `{ "mode": "langchain" }` or `{ "mode": "uipath" }`, THE REST_API SHALL update the active extraction mode and return the new mode in the response.
3. WHEN a user sends `GET /extraction/modes`, THE REST_API SHALL return the list of available extraction modes and the currently active mode.
4. WHEN a document ingestion request is submitted, THE Graph_RAG_System SHALL use the currently active extraction mode to process all documents in that request.
5. WHEN the ExtractionToggle component in the React_Frontend is set to LangChain, THE React_Frontend SHALL display the description "LangChain (LLM): accepts raw .txt files — LLM classifies and extracts."
6. WHEN the ExtractionToggle component in the React_Frontend is set to UiPath, THE React_Frontend SHALL display the description "UiPath Document Understanding: accepts UiPath JSON exports — parses pre-extracted structured fields."

---

### Requirement 6: Knowledge Graph Construction

**User Story:** As a developer, I want all documents and entities to be stored as typed nodes and edges in the Knowledge_Graph, so that cross-document relationships and provenance data are queryable via graph traversal.

#### Acceptance Criteria

1. WHEN a Document is ingested, THE Graph_Builder SHALL create a document node in the Knowledge_Graph with attributes: `node_type="document"`, `doc_id`, `filename`, `doc_type`, `doc_date`, `text`, and `embedding`.
2. WHEN an Entity is extracted, THE Graph_Builder SHALL create an entity node in the Knowledge_Graph with attributes: `node_type="entity"`, `entity_id`, `name`, `entity_type`, `attributes`, `source_doc_id`, `embedding`, `confidence`, and `extractor_model`.
3. WHEN an entity node is added, THE Graph_Builder SHALL create a `mentions` edge from the entity node to its source document node carrying: `line_number`, `line_text`, `paragraph_index`, `paragraph_text`, `char_offset_start`, and `char_offset_end`.
4. WHEN a `same_as` edge is added, THE Graph_Builder SHALL store on that edge: `confidence`, `name_score`, `semantic_score`, `llm_confirmed`, `valid_from`, and `valid_until`.
5. WHEN a `conflict` edge is added, THE Graph_Builder SHALL store on that edge: `conflict_type`, `attribute_key`, `value_a`, `value_b`, and `severity`.
6. THE Graph_Builder SHALL support `export_json(path)` which writes the full Knowledge_Graph to a JSON file at the specified path.
7. THE Graph_Builder SHALL support `get_graph()` which returns the current NetworkX graph object.

---

### Requirement 7: Entity Resolution and same_as Edges

**User Story:** As a user, I want the system to automatically identify when the same person or entity appears across different documents, so that cross-document queries return unified results.

#### Acceptance Criteria

1. WHEN entity resolution runs, THE Entity_Resolver SHALL compare entities of the same `entity_type` from different source documents using a hybrid score: `confidence = 0.4 × name_similarity + 0.6 × cosine_semantic_similarity`.
2. THE Entity_Resolver SHALL compute name similarity using the RapidFuzz token ratio algorithm, normalizing the result to [0.0, 1.0].
3. WHEN two entities of the same type from different source documents have a hybrid confidence score of 0.85 or above, THE Entity_Resolver SHALL automatically add a `same_as` edge connecting them without requiring LLM confirmation.
4. WHEN two entities of the same type from different source documents have a hybrid confidence score between 0.60 (inclusive) and 0.85 (exclusive), THE Entity_Resolver SHALL submit the pair to the LLM_Provider for confirmation and SHALL add a `same_as` edge only if the LLM confirms they are the same entity.
5. WHEN two entities have a hybrid confidence score below 0.60, THE Entity_Resolver SHALL not add a `same_as` edge between them.
6. THE Entity_Resolver SHALL not add a `same_as` edge between two entities that share the same `source_doc_id`.
7. THE Entity_Resolver SHALL not add a `same_as` edge from any entity to itself.
8. WHEN a `same_as` edge is added, THE Entity_Resolver SHALL set the `valid_from` timestamp to the document date of the earlier document and include `name_score`, `semantic_score`, and `llm_confirmed` on the edge.
9. THE Entity_Resolver SHALL assign a Confidence_Score in [0.0, 1.0] to every `same_as` edge it creates.

---

### Requirement 8: Contradiction Detection

**User Story:** As a user, I want the system to automatically detect and surface conflicting attribute values across linked entity records, so that I am warned about data inconsistencies before relying on the answer.

#### Acceptance Criteria

1. WHEN contradiction detection runs, THE Contradiction_Detector SHALL examine every pair of entities connected by a `same_as` edge and compare their shared attribute keys after normalizing values.
2. WHEN two same_as-linked entities have differing values for a critical attribute key (dob, name, license_number, passport_number, or policy_number), THE Contradiction_Detector SHALL add a `conflict` edge between them with `severity = "critical"`.
3. WHEN two same_as-linked entities have differing values for a non-critical attribute key (address, phone, or email), THE Contradiction_Detector SHALL add a `conflict` edge between them with `severity = "minor"`.
4. WHEN two same_as-linked entities have identical normalized values for all shared attribute keys, THE Contradiction_Detector SHALL not add any `conflict` edge between them.
5. WHEN a conflict is detected between entity A and entity B, THE Contradiction_Detector SHALL record the `source_doc_a` (source document of A) and `source_doc_b` (source document of B) on the ConflictRecord.
6. THE Contradiction_Detector SHALL produce ConflictRecord objects containing: `entity_id_a`, `entity_id_b`, `conflict_type` (e.g., `"dob_mismatch"`), `attribute_key`, `value_a`, `value_b`, `source_doc_a`, `source_doc_b`, and `severity`.

---

### Requirement 9: Temporal Awareness and Filtering

**User Story:** As a user, I want queries like "current address" to resolve to the most recent document, so that the system returns up-to-date information instead of stale or superseded values.

#### Acceptance Criteria

1. THE Temporal_Filter SHALL accept an `as_of` datetime parameter and return only those entities whose source document `doc_date` is on or before that date.
2. WHEN a query is submitted with `temporal_context = "current"`, THE Temporal_Filter SHALL resolve the most recent value for each requested attribute by selecting the entity whose source `doc_date` is the latest among all same_as-linked candidates.
3. WHEN multiple same_as-linked entities have conflicting values for an attribute, THE Temporal_Filter's `get_most_recent` method SHALL return the attribute value from the entity whose source document has the latest `doc_date`.
4. WHEN a source document has no `doc_date`, THE Temporal_Filter SHALL exclude that document from temporal ordering and note it as undated in the query metadata.
5. WHEN a `same_as` edge has a `valid_from` and `valid_until` set, THE Temporal_Filter SHALL only traverse that edge for queries whose `as_of` date falls within [valid_from, valid_until].

---

### Requirement 10: Multi-Hop Graph Traversal

**User Story:** As a user, I want queries to automatically traverse chains of linked entities up to a configurable depth, so that complex questions spanning three or more documents receive complete answers.

#### Acceptance Criteria

1. WHEN the Multi_Hop_Traversal is invoked, THE Multi_Hop_Traversal SHALL perform a breadth-first search starting from seed entity IDs, expanding only via `same_as` edges, up to the configured `max_hops` depth.
2. THE Multi_Hop_Traversal SHALL only traverse `same_as` edges whose `confidence` is 0.60 or above.
3. WHEN the Multi_Hop_Traversal expands to depth `d`, THE Multi_Hop_Traversal SHALL guarantee that its result set contains all entities reachable from any seed via `same_as` chains of length at most `d`.
4. THE Multi_Hop_Traversal SHALL accept `max_hops` values between 1 and 5 (inclusive).
5. THE Multi_Hop_Traversal SHALL not revisit an entity node already in the visited set, preventing infinite loops on cyclic graphs.
6. WHEN locating seed entities from query terms, THE Multi_Hop_Traversal SHALL compute a match score of `0.5 × rapidfuzz_score + 0.5 × cosine_similarity(query_embedding, entity_embedding)` and seed from entity nodes above a configurable match threshold.
7. WHEN the Multi_Hop_Traversal finds no matching seed entities, THE Query_Engine SHALL return a QueryResult with the answer "No matching entities found." and empty provenance.

---

### Requirement 11: Vector and Graph Hybrid Retrieval

**User Story:** As a developer, I want retrieved context to combine graph traversal results with semantic embedding similarity, so that the system achieves better recall than either approach alone.

#### Acceptance Criteria

1. THE Context_Aggregator SHALL score each candidate document using a hybrid relevance formula: `relevance = 0.4 × graph_centrality_score + 0.6 × cosine_similarity(query_embedding, doc_embedding)`.
2. THE Context_Aggregator SHALL deduplicate documents before ranking so that no document appears more than once in the aggregated context.
3. THE Context_Aggregator SHALL truncate the aggregated context to the configured token budget (default 4,096 tokens for Ollama, 8,192 tokens for GPT-4) before passing it to the LLM_Provider.
4. THE Embedding_Engine SHALL generate embeddings using the `all-MiniLM-L6-v2` sentence-transformer model running fully locally without external API calls.
5. THE Embedding_Engine SHALL cache embeddings by SHA-256 hash of the input text and return the cached result on subsequent calls with the same text.
6. THE Embedding_Engine's `cosine_similarity` method SHALL return a value in [0.0, 1.0] for any pair of valid embedding vectors.

---

### Requirement 12: Provenance Tracking

**User Story:** As a user, I want every fact in a query answer to link to the exact line number and verbatim text in the source document, so that I can independently verify the information.

#### Acceptance Criteria

1. WHEN the Provenance_Tracker extracts provenance for a set of entity IDs, THE Provenance_Tracker SHALL look up the `mentions` edge for each entity and produce a ProvenanceEntry for each attribute key–value pair on the entity.
2. THE Provenance_Tracker SHALL populate each ProvenanceEntry with: `fact` (formatted as `"attribute_key: attribute_value"`), `source_filename`, `doc_type`, `line_number`, `line_text`, `paragraph_index`, `paragraph_text`, `char_offset_start`, `char_offset_end`, `confidence`, and `entity_id`.
3. FOR ALL ProvenanceEntry objects produced by the Provenance_Tracker, the `line_text` field SHALL equal the verbatim text at position `line_number - 1` (0-indexed) in the source document's lines array.
4. THE Provenance_Tracker's `verify(fact)` method SHALL accept a fact string and return all ProvenanceEntry objects from the Knowledge_Graph whose entity attributes match that fact string.
5. WHEN a QueryResult is returned to a user, THE QueryResult SHALL include a non-null `provenance` list containing at least one ProvenanceEntry for each source document used in the answer.

---

### Requirement 13: Query Engine and Answer Synthesis

**User Story:** As a user, I want to submit a natural language question and receive a synthesized answer with provenance, conflict warnings, and resolution metadata, so that I can understand both the answer and its basis.

#### Acceptance Criteria

1. WHEN a query is submitted, THE Query_Engine SHALL extract entity names from the question using the LLM_Provider, embed the question using the Embedding_Engine, and pass both to the Multi_Hop_Traversal to identify seed entities.
2. WHEN the Query_Engine synthesizes an answer, THE LLM_Provider SHALL receive the question, the aggregated context, and provenance hints, and SHALL return the answer text.
3. THE Query_Engine SHALL accept a `max_hops` parameter (integer, 1–5) and a `temporal_context` parameter (`"current"`, `"all"`, or an ISO 8601 date string).
4. THE Query_Engine SHALL return a QueryResult containing: `question`, `answer`, `source_documents`, `resolved_entities`, `resolution_confidence`, `hops_used`, `provenance`, `conflicts`, `has_conflicts`, and `temporal_context`.
5. WHEN the synthesized answer references a fact, THE answer SHALL only reference information present in the aggregated context passed to the LLM_Provider.
6. WHEN conflicts exist among the traversed entities, THE QueryResult `has_conflicts` field SHALL be `True` and the `conflicts` list SHALL contain all ConflictRecord objects for entity pairs in the traversal result set.

---

### Requirement 14: LLM Provider Abstraction and Switching

**User Story:** As a developer, I want to switch between a local Ollama LLM and the OpenAI API using a single environment variable, so that I can use local inference during development and cloud inference for production without code changes.

#### Acceptance Criteria

1. THE LLM_Provider factory SHALL read the `LLM_PROVIDER` environment variable and return an OllamaProvider instance when the value is `"ollama"` and an OpenAIProvider instance when the value is `"openai"`.
2. WHEN `LLM_PROVIDER` is `"ollama"`, THE OllamaProvider SHALL send all LLM requests to the local Ollama HTTP API and SHALL not transmit any document text to external services.
3. WHEN `LLM_PROVIDER` is `"openai"`, THE OpenAIProvider SHALL read the `OPENAI_API_KEY` exclusively from the environment variable and SHALL not accept the key from any other source.
4. IF the LLM_Provider is unreachable, THEN THE Graph_RAG_System SHALL raise a descriptive `LLMProviderError` containing the provider name and a suggested remediation step.
5. WHEN the `LLM_PROVIDER` environment variable is not set, THE LLM_Provider factory SHALL default to `"ollama"`.

---

### Requirement 15: FastAPI REST API

**User Story:** As an integrator, I want to interact with the Graph RAG system through a documented REST API, so that I can build integrations and automate ingestion and querying workflows.

#### Acceptance Criteria

1. THE REST_API SHALL expose `POST /ingest` accepting a JSON body `{ "paths": [...], "extractor": "langchain" | "uipath" }` and SHALL return a JSON response indicating the number of documents ingested and entities extracted.
2. THE REST_API SHALL expose `POST /ingest/uipath` accepting UiPath JSON export files and SHALL ingest them using the UiPath_Extractor.
3. THE REST_API SHALL expose `POST /query` accepting a JSON body `{ "question": "...", "max_hops": 3, "temporal_context": "current" }` and SHALL return a serialized QueryResult.
4. THE REST_API SHALL expose `GET /graph/stats` returning a JSON object containing node count, edge count, and a breakdown of entity counts per entity type.
5. THE REST_API SHALL expose `GET /graph/visualize` returning the Pyvis HTML graph as an HTML response.
6. THE REST_API SHALL expose `GET /entities` returning a JSON array of all entity nodes with their attributes.
7. THE REST_API SHALL expose `DELETE /graph` which resets the in-memory Knowledge_Graph to an empty state and returns a confirmation message.
8. THE REST_API SHALL expose `GET /extraction/modes` returning the available extraction modes and the currently active mode.
9. THE REST_API SHALL expose `POST /extraction/mode` accepting `{ "mode": "langchain" | "uipath" }` and SHALL update the active extraction mode, returning the updated mode in the response.
10. IF `POST /query` is called when the Knowledge_Graph contains no entities, THEN THE REST_API SHALL return a 400 response with a message indicating the graph is empty.

---

### Requirement 16: CLI Interface

**User Story:** As a developer, I want a command-line interface that exposes all major system functions, so that I can script ingestion, querying, and visualization workflows without running the web server.

#### Acceptance Criteria

1. THE CLI SHALL provide an `ingest` command accepting `--dir <directory>` or `--files <file> [<file>...]` and an `--extractor langchain|uipath` flag, which ingests the specified documents and prints a summary of entities extracted.
2. THE CLI SHALL provide a `query` command accepting a question string, an optional `--hops <int>` flag (default 3), and an optional `--temporal <string>` flag (default `"current"`), which prints the answer and provenance to stdout.
3. THE CLI SHALL provide a `visualize` command accepting an `--output <path>` flag (default `"graph.html"`) that generates the Pyvis visualization and saves it to the specified path.
4. THE CLI SHALL provide a `verify` command accepting a fact string that prints all matching ProvenanceEntry objects to stdout.
5. THE CLI SHALL provide a `serve` command accepting an optional `--port <int>` flag (default 8000) that starts the FastAPI REST_API server.
6. THE CLI SHALL provide a `stats` command that prints node count, edge count, and entity type breakdown to stdout.

---

### Requirement 17: Graph Visualization

**User Story:** As a user, I want to explore the knowledge graph interactively in a browser, so that I can understand entity relationships, resolve ambiguities, and inspect confidence scores visually.

#### Acceptance Criteria

1. THE Graph_Visualizer SHALL render the Knowledge_Graph as an interactive Pyvis HTML file at the specified output path.
2. THE Graph_Visualizer SHALL color-code entity nodes by type: PERSON as `#4A90D9`, DOCUMENT as `#27AE60`, ID_NUMBER as `#E67E22`, DATE as `#9B59B6`, ORGANIZATION as `#E74C3C`, and LOCATION as `#1ABC9C`.
3. THE Graph_Visualizer SHALL style `mentions` edges as dashed grey, `same_as` edges as solid bold with color on a red-to-green heatmap mapped to confidence value, and `conflict` edges as dotted red bold.
4. WHEN a user clicks an entity node in the rendered HTML, THE Graph_Visualizer SHALL display a tooltip containing all entity attributes, source document name, and confidence score.
5. THE Graph_Visualizer SHALL support `render_subgraph(entity_ids, output_path)` which renders only the subgraph induced by the supplied entity IDs and their immediate neighbors.
6. IF the Pyvis package is not installed, THEN THE Graph_Visualizer SHALL log an error message suggesting `pip install pyvis` and return without crashing.

---

### Requirement 18: React Frontend

**User Story:** As a user, I want a web interface with all system controls — extraction toggle, document upload, query input, provenance display, and graph visualization — in a single page application, so that I can use the full Graph RAG capability without the command line.

#### Acceptance Criteria

1. THE React_Frontend SHALL render the ExtractionToggle component displaying two buttons labeled "🔗 LangChain (LLM)" and "🤖 UiPath Document Understanding" and SHALL highlight the active mode button.
2. WHEN the user changes the ExtractionToggle selection, THE React_Frontend SHALL send `POST /extraction/mode` with the selected mode and update the displayed active mode description.
3. THE React_Frontend SHALL render the DocumentUpload component supporting drag-and-drop of `.txt` files in LangChain mode and UiPath JSON files in UiPath mode.
4. WHEN documents are uploaded, THE React_Frontend SHALL send a `POST /ingest` request with the selected files and active extraction mode, and SHALL display an ingestion summary upon completion.
5. THE React_Frontend SHALL render the QueryInput component with a text field for natural language questions and controls for `max_hops` (slider 1–5) and `temporal_context` (dropdown: current, all, specific date).
6. WHEN a query is submitted, THE React_Frontend SHALL display the answer in the AnswerDisplay component and SHALL populate the ProvenanceList with per-fact entries showing source filename, line number, and verbatim line text.
7. THE React_Frontend SHALL render the ConflictWarnings component displaying critical conflicts in red cards and minor conflicts in yellow cards when the QueryResult `has_conflicts` is true.
8. THE React_Frontend SHALL render the GraphVisualization component embedding the Pyvis HTML from `GET /graph/visualize` in an iframe.
9. THE React_Frontend SHALL render the EntityTable component as a searchable table of all entities returned by `GET /entities`, showing entity name, type, source document, and confidence.
10. THE React_Frontend SHALL render the GraphStats sub-panel showing total node count, total edge count, and entity type breakdown.

---

### Requirement 19: Confidence Scoring

**User Story:** As a user, I want every entity resolution link and extraction result to carry an explicit confidence score, so that I can assess the reliability of cross-document connections and prioritize high-confidence results.

#### Acceptance Criteria

1. THE Entity_Extractor SHALL assign a `confidence` value in [0.0, 1.0] to every extracted Entity, reflecting the LLM's extraction certainty.
2. THE Entity_Resolver SHALL assign a `confidence` value in [0.0, 1.0] to every `same_as` edge it creates, computed as `0.4 × name_similarity + 0.6 × cosine_semantic_similarity`.
3. THE UiPath_Extractor SHALL use the `fields[key].confidence` value from the UiPath JSON as the entity confidence for each field, clamping any out-of-range values to [0.0, 1.0].
4. THE Provenance_Tracker SHALL include the entity's `confidence` value on every ProvenanceEntry it produces.
5. THE QueryResult SHALL include a `resolution_confidence` list containing the `confidence` value of each `same_as` edge traversed during the query.
6. THE REST_API SHALL serialize all confidence values as floating-point numbers with at least two decimal places of precision.

---

### Requirement 20: Synthetic Dataset and Fixture Documents

**User Story:** As a developer, I want a pre-built synthetic dataset of fixture documents for testing, so that I can validate cross-document entity resolution, multi-hop reasoning, and contradiction detection without real personal data.

#### Acceptance Criteria

1. THE Graph_RAG_System SHALL include a synthetic dataset containing documents for at least 3 fictional people, each represented by at least 3 different document types.
2. THE synthetic dataset SHALL include at least one pair of documents for the same fictional person where a critical attribute (such as `dob`) is deliberately mismatched to exercise contradiction detection.
3. THE synthetic dataset SHALL include at least one scenario with a chain of 3 or more same_as-linked entity nodes to exercise multi-hop traversal.
4. THE synthetic dataset documents SHALL be stored as `.txt` files (for LangChain mode) with corresponding UiPath JSON counterparts (for UiPath mode) covering the same fictional records.
5. THE synthetic dataset SHALL not contain any real personally identifiable information.

---

### Requirement 21: Security and Privacy

**User Story:** As a security-conscious operator, I want the system to handle sensitive document data safely, so that no personal information is accidentally exposed or transmitted to unauthorized services.

#### Acceptance Criteria

1. THE Graph_RAG_System SHALL read the `OPENAI_API_KEY` exclusively from the `OPENAI_API_KEY` environment variable and SHALL not accept or log it from any other source.
2. WHEN `LLM_PROVIDER` is set to `"ollama"`, THE Graph_RAG_System SHALL not transmit any document text or entity attributes to any external network endpoint.
3. THE Graph_RAG_System SHALL sanitize all document text before sending it to the LLM_Provider by stripping control characters and enforcing a maximum input length.
4. THE Knowledge_Graph SHALL be stored exclusively in memory and SHALL not be persisted to disk unless the user explicitly calls `export_json()`.
5. THE Graph_RAG_System SHALL not log any raw document text or entity attribute values at INFO level or above; such data MAY be logged at DEBUG level.

---

### Requirement 22: Error Handling and Resilience

**User Story:** As a user, I want the system to handle errors gracefully and continue processing remaining documents when one fails, so that a single bad file does not abort an entire ingestion run.

#### Acceptance Criteria

1. WHEN the LLM_Provider returns malformed JSON during entity extraction, THE Entity_Extractor SHALL retry once; IF the retry also fails, THE Entity_Extractor SHALL skip the affected document, log a warning with the filename, and continue.
2. WHEN the LLM_Provider is unreachable, THE Graph_RAG_System SHALL raise a `LLMProviderError` with the provider name and a suggested remediation action, and SHALL not leave the Knowledge_Graph in a partially modified state.
3. WHEN the Embedding_Engine model is not found on the local filesystem, THE Embedding_Engine SHALL fall back to name-only string similarity for entity resolution and log a warning suggesting `pip install sentence-transformers`.
4. WHEN a `POST /query` is submitted and no entities match the query, THE Query_Engine SHALL return a QueryResult with a human-readable answer "No matching entities found." rather than raising an exception.
5. WHEN Graph_Visualizer's `render()` is called and the Pyvis package is not installed, THE Graph_Visualizer SHALL log an error message suggesting `pip install pyvis` and return without raising an unhandled exception.
6. WHEN a document has no extractable `doc_date`, THE Temporal_Filter SHALL exclude that document from temporal ordering and include it only in queries with `temporal_context = "all"`.
