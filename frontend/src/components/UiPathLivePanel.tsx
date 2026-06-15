/**
 * UiPathLivePanel — upload a real scanned document to the UiPath API.
 *
 * Shows the UiPath connection status and lets you drag-and-drop a real
 * PDF/image to send to UiPath Document Understanding live API.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../api/client';

interface UiPathStatus {
  configured: boolean;
  connected?: boolean;
  client_id?: string;
  message:    string;
}

interface Props {
  onIngestComplete?: (result: unknown) => void;
}

const S: Record<string, React.CSSProperties> = {
  container: {
    background:   '#1e1e2e',
    border:       '1px solid #E67E22',
    borderRadius: '10px',
    padding:      '16px',
  },
  title: {
    fontSize:   '15px',
    fontWeight: 600,
    color:      '#E67E22',
    marginBottom: '10px',
    display:    'flex',
    alignItems: 'center',
    gap:        '8px',
  },
  statusRow: {
    display:      'flex',
    alignItems:   'center',
    gap:          '8px',
    marginBottom: '12px',
    fontSize:     '12px',
    color:        '#aaa',
  },
  dot: (connected: boolean | undefined, configured: boolean) => ({
    width:        '8px',
    height:       '8px',
    borderRadius: '50%',
    background:   !configured ? '#888' : connected ? '#27AE60' : '#E74C3C',
    flexShrink:   0,
  }),
  dropzone: (dragging: boolean) => ({
    border:       `2px dashed ${dragging ? '#E67E22' : '#444'}`,
    borderRadius: '8px',
    padding:      '20px',
    textAlign:    'center',
    cursor:       'pointer',
    transition:   'all 0.2s',
    background:   dragging ? '#2a1a00' : 'transparent',
    marginBottom: '10px',
  }),
  dropText: {
    fontSize: '13px',
    color:    '#888',
  },
  dropHint: {
    fontSize:   '11px',
    color:      '#555',
    marginTop:  '4px',
  },
  select: {
    width:        '100%',
    padding:      '6px 10px',
    background:   '#0d0d1a',
    border:       '1px solid #444',
    borderRadius: '6px',
    color:        '#eee',
    fontSize:     '12px',
    marginBottom: '8px',
  },
  result: {
    background:   '#0d0d1a',
    borderRadius: '6px',
    padding:      '10px',
    fontSize:     '12px',
    fontFamily:   'monospace',
    color:        '#27AE60',
    maxHeight:    '150px',
    overflow:     'auto',
    marginTop:    '8px',
  },
  error: {
    background:   '#1a0a0a',
    borderRadius: '6px',
    padding:      '8px',
    fontSize:     '12px',
    color:        '#E74C3C',
    marginTop:    '8px',
  },
  configNote: {
    fontSize:     '11px',
    color:        '#666',
    background:   '#16162a',
    borderRadius: '6px',
    padding:      '8px 10px',
    marginTop:    '8px',
  },
};

const EXTRACTOR_OPTIONS = [
  { value: 'identity_documents', label: '🪪 Identity Documents (passport, license, ID)' },
  { value: 'invoices',           label: '🧾 Invoices' },
  { value: 'receipts',           label: '🧾 Receipts' },
  { value: 'contracts',          label: '📄 Contracts' },
];

const UiPathLivePanel: React.FC<Props> = ({ onIngestComplete }) => {
  const [status,    setStatus]    = useState<UiPathStatus | null>(null);
  const [extractor, setExtractor] = useState('identity_documents');
  const [dragging,  setDragging]  = useState(false);
  const [loading,   setLoading]   = useState(false);
  const [result,    setResult]    = useState<unknown>(null);
  const [error,     setError]     = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/uipath/status`)
      .then(r => r.json())
      .then(setStatus)
      .catch(() => setStatus({ configured: false, message: 'API not available' }));
  }, []);

  const handleFile = useCallback(async (file: File) => {
    setLoading(true);
    setError('');
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('extractor', extractor);

    try {
      const res = await fetch(`${API_BASE}/uipath/extract?extractor=${extractor}`, {
        method: 'POST',
        body:   formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Extraction failed');
      setResult(data);
      onIngestComplete?.(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [extractor, onIngestComplete]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div style={S.container}>
      <div style={S.title}>
        🤖 UiPath Live API
      </div>

      {/* Status */}
      <div style={S.statusRow}>
        <div style={S.dot(status?.connected, status?.configured ?? false)} />
        <span>{status?.message || 'Checking...'}</span>
        {status?.client_id && (
          <span style={{ color: '#555' }}>({status.client_id})</span>
        )}
      </div>

      {!status?.configured && (
        <div style={S.configNote}>
          <b>Setup:</b> Add to your <code>.env</code> file:<br />
          <code>UIPATH_CLIENT_ID=...</code><br />
          <code>UIPATH_CLIENT_SECRET=...</code><br />
          Get them at <b>cloud.uipath.com → Admin → External Applications</b>
        </div>
      )}

      {/* Extractor selector */}
      <select
        style={S.select}
        value={extractor}
        onChange={e => setExtractor(e.target.value)}
      >
        {EXTRACTOR_OPTIONS.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* Drop zone */}
      <div
        style={S.dropzone(dragging)}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
      >
        {loading ? (
          <div style={S.dropText}>⏳ Extracting via UiPath API...</div>
        ) : (
          <>
            <div style={S.dropText}>
              {dragging ? 'Drop to extract' : 'Drop a PDF or image here'}
            </div>
            <div style={S.dropHint}>
              or click to browse — PDF, PNG, JPG, TIFF
            </div>
          </>
        )}
      </div>

      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif"
        style={{ display: 'none' }}
        onChange={onInputChange}
      />

      {/* Error */}
      {error && <div style={S.error}>⚠ {error}</div>}

      {/* Result */}
      {result && (
        <div style={S.result}>
          {JSON.stringify(result, null, 2)
            .split('\n').slice(0, 30).join('\n')}
        </div>
      )}
    </div>
  );
};

export default UiPathLivePanel;
