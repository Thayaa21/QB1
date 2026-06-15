/**
 * DocumentUpload — input field for file paths to ingest.
 *
 * Since the backend reads files from disk, we collect file paths
 * (not file contents). The user enters paths separated by newlines.
 */

import React, { useState } from 'react';
import { ingestDocuments } from '../api/client';
import type { IngestResponse } from '../types';

interface DocumentUploadProps {
  extractionMode: 'langchain' | 'uipath';
  onIngestComplete: (result: IngestResponse) => void;
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background:   '#1e1e2e',
    border:       '1px solid #333',
    borderRadius: '8px',
    padding:      '16px',
  },
  title: {
    color:        '#eee',
    fontSize:     '16px',
    fontWeight:   600,
    marginBottom: '12px',
  },
  textarea: {
    width:        '100%',
    minHeight:    '120px',
    background:   '#0d0d1a',
    color:        '#ddd',
    border:       '1px solid #444',
    borderRadius: '4px',
    padding:      '8px',
    fontSize:     '13px',
    fontFamily:   'monospace',
    resize:       'vertical',
    boxSizing:    'border-box',
  },
  hint: {
    color:      '#666',
    fontSize:   '12px',
    marginTop:  '6px',
  },
  button: {
    marginTop:    '10px',
    padding:      '8px 20px',
    background:   '#4A90D9',
    color:        'white',
    border:       'none',
    borderRadius: '5px',
    cursor:       'pointer',
    fontSize:     '14px',
    fontWeight:   500,
  },
  result: {
    marginTop:    '10px',
    padding:      '8px 12px',
    background:   '#0f2d1f',
    border:       '1px solid #27AE60',
    borderRadius: '4px',
    color:        '#27AE60',
    fontSize:     '13px',
  },
  error: {
    marginTop:    '10px',
    padding:      '8px 12px',
    background:   '#2d0f0f',
    border:       '1px solid #E74C3C',
    borderRadius: '4px',
    color:        '#E74C3C',
    fontSize:     '13px',
  },
};

const DocumentUpload: React.FC<DocumentUploadProps> = ({
  extractionMode,
  onIngestComplete,
}) => {
  const [pathsText, setPathsText] = useState('');
  const [loading,   setLoading]   = useState(false);
  const [result,    setResult]    = useState<IngestResponse | null>(null);
  const [error,     setError]     = useState<string | null>(null);

  const handleIngest = async () => {
    const paths = pathsText
      .split('\n')
      .map((p) => p.trim())
      .filter(Boolean);

    if (paths.length === 0) {
      setError('Please enter at least one file path.');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await ingestDocuments(paths, extractionMode);
      setResult(response);
      onIngestComplete(response);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ingestion failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const placeholder =
    extractionMode === 'uipath'
      ? 'docs/people/alice_chen/birth_certificate.json\ndocs/people/alice_chen/drivers_license.json'
      : 'docs/people/alice_chen/birth_certificate.txt\ndocs/people/alice_chen/drivers_license.txt';

  return (
    <div style={styles.container}>
      <div style={styles.title}>📄 Ingest Documents</div>
      <textarea
        style={styles.textarea}
        value={pathsText}
        onChange={(e) => setPathsText(e.target.value)}
        placeholder={placeholder}
        spellCheck={false}
      />
      <div style={styles.hint}>
        Enter one file path per line.
        {extractionMode === 'uipath'
          ? ' UiPath mode: expects .json files.'
          : ' LangChain mode: expects .txt files.'}
      </div>
      <button
        style={{ ...styles.button, opacity: loading ? 0.7 : 1 }}
        onClick={handleIngest}
        disabled={loading}
      >
        {loading ? 'Ingesting...' : `Ingest (${extractionMode})`}
      </button>

      {result && (
        <div style={styles.result}>
          ✓ Ingested {result.documents_ingested} document(s),
          extracted {result.entities_extracted} entities
          [{result.extraction_mode}]
        </div>
      )}
      {error && <div style={styles.error}>✗ {error}</div>}
    </div>
  );
};

export default DocumentUpload;
