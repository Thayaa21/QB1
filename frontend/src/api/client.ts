/**
 * API client — axios-based functions for all backend endpoints.
 *
 * TEACHING NOTES
 * --------------
 * axios is an HTTP client library for the browser.
 * It provides a cleaner API than the native fetch() function:
 * - Automatic JSON parsing/serialization
 * - Interceptors for error handling
 * - TypeScript-friendly generics: axios.get<MyType>(url)
 *
 * Base URL:
 *   The Vite proxy (in vite.config.ts) rewrites /api → http://localhost:8000
 *   So axios.get('/api/graph/stats') calls http://localhost:8000/graph/stats
 *
 *   In production, you'd set baseURL to the actual API server URL.
 */

import axios from 'axios';
import type {
  ConflictRecord,
  EntityNode,
  ExtractionModesResponse,
  GraphStats,
  IngestResponse,
  QueryResult,
} from '../types';

// Base URL — the Vite proxy rewrites /api to http://localhost:8000
const BASE_URL = '/api';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120_000, // 2 minutes — LLM calls can be slow
});

// ---- Ingest ----

export async function ingestDocuments(
  paths: string[],
  extractor: 'langchain' | 'uipath' = 'langchain'
): Promise<IngestResponse> {
  const response = await api.post<IngestResponse>('/ingest', { paths, extractor });
  return response.data;
}

export async function ingestUiPath(paths: string[]): Promise<IngestResponse> {
  const response = await api.post<IngestResponse>('/ingest/uipath', { paths });
  return response.data;
}

// ---- Query ----

export async function queryGraph(
  question: string,
  maxHops: number = 3,
  temporalContext: string = 'current'
): Promise<QueryResult> {
  const response = await api.post<QueryResult>('/query', {
    question,
    max_hops: maxHops,
    temporal_context: temporalContext,
  });
  return response.data;
}

// ---- Graph ----

export async function getGraphStats(): Promise<GraphStats> {
  const response = await api.get<GraphStats>('/graph/stats');
  return response.data;
}

export async function getGraphVisualization(): Promise<string> {
  const response = await api.get<string>('/graph/visualize', {
    responseType: 'text',
  });
  return response.data;
}

export async function resetGraph(): Promise<{ message: string; stats: GraphStats }> {
  const response = await api.delete('/graph');
  return response.data;
}

// ---- Entities ----

export async function getEntities(): Promise<{ entities: EntityNode[]; count: number }> {
  const response = await api.get('/entities');
  return response.data;
}

// ---- Extraction Mode ----

export async function getExtractionModes(): Promise<ExtractionModesResponse> {
  const response = await api.get<ExtractionModesResponse>('/extraction/modes');
  return response.data;
}

export async function setExtractionMode(
  mode: 'langchain' | 'uipath'
): Promise<{ mode: string; message: string }> {
  const response = await api.post('/extraction/mode', { mode });
  return response.data;
}

// ---- File Upload ----

// Export API_BASE so TestDatasetPanel can use it directly for fetch()
export const API_BASE = 'http://localhost:8000';

export async function uploadFiles(
  files: FileList | File[],
  extractor: 'langchain' | 'uipath' = 'langchain'
): Promise<IngestResponse> {
  const formData = new FormData();
  Array.from(files).forEach(f => formData.append('files', f));
  formData.append('extractor', extractor);

  const response = await axios.post(`${API_BASE}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000, // 5 min for multiple LLM calls
  });
  return response.data;
}
