/**
 * TypeScript interfaces matching the backend data models.
 * These mirror the Python dataclasses in graph_rag/core/models.py
 */

// ---- Enums (matching Python DocType, EntityType etc.) ----

export type DocType =
  | 'BIRTH_CERTIFICATE'
  | 'DRIVERS_LICENSE'
  | 'PASSPORT'
  | 'INSURANCE'
  | 'MEDICAL_RECORD'
  | 'GENERIC';

export type EntityType = 'PERSON' | 'ORGANIZATION' | 'LOCATION' | 'ID_NUMBER' | 'DATE';

// ---- API Response Types ----

export interface ProvenanceEntry {
  fact:             string;
  source_filename:  string;
  doc_type:         DocType;
  line_number:      number;
  line_text:        string;
  confidence:       number;
  entity_id:        string;
}

export interface ConflictRecord {
  conflict_type:  string;
  attribute_key:  string;
  value_a:        string;
  value_b:        string;
  severity:       'critical' | 'minor';
  source_doc_a:   string;
  source_doc_b:   string;
}

export interface QueryResult {
  question:              string;
  answer:                string;
  source_documents:      string[];
  resolved_entities:     string[];
  resolution_confidence: number[];
  hops_used:             number;
  provenance:            ProvenanceEntry[];
  conflicts:             ConflictRecord[];
  has_conflicts:         boolean;
  temporal_context:      string;
}

export interface GraphStats {
  nodes:          number;
  edges:          number;
  entities:       number;
  documents:      number;
  same_as_edges:  number;
  conflict_edges: number;
}

export interface IngestResponse {
  documents_ingested: number;
  entities_extracted: number;
  extraction_mode:    string;
}

export interface EntityNode {
  node_id:        string;
  node_type:      string;
  entity_id:      string;
  name:           string;
  entity_type:    EntityType;
  attributes:     Record<string, string>;
  source_filename: string;
  doc_type:       DocType;
  confidence:     number;
}

export interface ExtractionModesResponse {
  modes:  string[];
  active: string;
}
