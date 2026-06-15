/**
 * TestDatasetPanel — browse and ingest test data files one by one.
 *
 * Shows a tree of all synthetic dataset files grouped by person.
 * Each file has an "Ingest" button so you can test one document at a time.
 */

import React, { useEffect, useState } from 'react';
import { API_BASE } from '../api/client';

interface TestFile {
  name:  string;
  type:  string;
  path:  string;
  size:  number;
}

interface TestPerson {
  name:  string;
  label: string;
  files: TestFile[];
}

interface Props {
  extractionMode:    'langchain' | 'uipath';
  onIngestComplete?: (result: unknown) => void;
}

const s: Record<string, React.CSSProperties> = {
  container: {
    background:   '#1e1e2e',
    border:       '1px solid #333',
    borderRadius: '10px',
    padding:      '16px',
  },
  title: {
    fontSize:   '15px',
    fontWeight: 600,
    color:      '#4A90D9',
    marginBottom: '12px',
  },
  filter: {
    width:        '100%',
    padding:      '6px 10px',
    background:   '#0d0d1a',
    border:       '1px solid #444',
    borderRadius: '6px',
    color:        '#eee',
    fontSize:     '13px',
    marginBottom: '12px',
    boxSizing:    'border-box' as const,
  },
  personRow: {
    marginBottom: '8px',
    border:       '1px solid #2a2a3e',
    borderRadius: '6px',
    overflow:     'hidden',
  },
  personHeader: {
    display:        'flex',
    justifyContent: 'space-between',
    alignItems:     'center',
    padding:        '8px 12px',
    background:     '#16162a',
    cursor:         'pointer',
    userSelect:     'none' as const,
  },
  personLabel: {
    fontSize:   '13px',
    fontWeight: 600,
    color:      '#ccc',
  },
  ingestAllBtn: {
    padding:      '3px 10px',
    background:   '#27AE60',
    border:       'none',
    borderRadius: '4px',
    color:        '#fff',
    fontSize:     '11px',
    cursor:       'pointer',
  },
  fileRow: {
    display:        'flex',
    justifyContent: 'space-between',
    alignItems:     'center',
    padding:        '6px 12px',
    borderTop:      '1px solid #2a2a3e',
    background:     '#12121f',
  },
  fileName: {
    fontSize: '12px',
    color:    '#aaa',
    flex:     1,
  },
  badge: {
    fontSize:     '10px',
    padding:      '1px 6px',
    borderRadius: '4px',
    marginRight:  '8px',
    fontWeight:   600,
  },
  ingestBtn: {
    padding:      '3px 10px',
    background:   '#4A90D9',
    border:       'none',
    borderRadius: '4px',
    color:        '#fff',
    fontSize:     '11px',
    cursor:       'pointer',
  },
  doneBtn: {
    padding:      '3px 10px',
    background:   '#27AE60',
    border:       'none',
    borderRadius: '4px',
    color:        '#fff',
    fontSize:     '11px',
  },
  errorBtn: {
    padding:      '3px 10px',
    background:   '#E74C3C',
    border:       'none',
    borderRadius: '4px',
    color:        '#fff',
    fontSize:     '11px',
  },
  log: {
    marginTop:  '10px',
    fontSize:   '11px',
    color:      '#27AE60',
    background: '#0d1a0d',
    padding:    '6px 8px',
    borderRadius: '4px',
    maxHeight:  '80px',
    overflow:   'auto',
    fontFamily: 'monospace',
  },
};

const TestDatasetPanel: React.FC<Props> = ({ extractionMode, onIngestComplete }) => {
  const [people,      setPeople]      = useState<TestPerson[]>([]);
  const [filter,      setFilter]      = useState('');
  const [expanded,    setExpanded]    = useState<Set<string>>(new Set());
  const [ingesting,   setIngesting]   = useState<Set<string>>(new Set());
  const [done,        setDone]        = useState<Set<string>>(new Set());
  const [errors,      setErrors]      = useState<Record<string, string>>({});
  const [log,         setLog]         = useState<string[]>([]);
  const [batchRunning, setBatchRunning] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/testdata`)
      .then(r => r.json())
      .then(d => setPeople(d.people || []))
      .catch(() => {});
  }, []);

  const appendLog = (msg: string) =>
    setLog(prev => [...prev.slice(-20), msg]);

  const ingestFile = async (file: TestFile) => {
    const key = file.path;
    setIngesting(prev => new Set(prev).add(key));
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });

    try {
      const res = await fetch(`${API_BASE}/testdata/ingest`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ path: file.path, extractor: extractionMode }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed');
      setDone(prev => new Set(prev).add(key));
      appendLog(`✓ ${file.name} → ${data.entities_extracted} entities`);
      onIngestComplete?.(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrors(prev => ({ ...prev, [key]: msg }));
      appendLog(`✗ ${file.name}: ${msg}`);
    } finally {
      setIngesting(prev => { const n = new Set(prev); n.delete(key); return n; });
    }
  };

  const ingestAll = async (person: TestPerson) => {
    const relevant = person.files.filter(f =>
      extractionMode === 'uipath' ? f.type === 'json' : f.type === 'txt'
    );
    for (const file of relevant) {
      await ingestFile(file);
    }
  };

  // Ingest ALL people at once (UiPath mode only — fast)
  const ingestEverything = async () => {
    if (extractionMode !== 'uipath') {
      appendLog('⚠ Switch to UiPath mode for fast batch ingest');
      return;
    }
    setBatchRunning(true);
    appendLog('Starting batch ingest (UiPath mode)...');
    const allFiles = people.flatMap(p =>
      p.files.filter(f => f.type === 'json' && !done.has(f.path))
    );
    appendLog(`Ingesting ${allFiles.length} files...`);
    for (const file of allFiles) {
      await ingestFile(file);
    }
    // Run entity resolution once at the end
    appendLog('Running entity resolution...');
    try {
      const r = await fetch(`${API_BASE}/testdata/resolve`, { method: 'POST' });
      const d = await r.json();
      appendLog(`✓ Resolution done. Graph: ${JSON.stringify(d.graph_stats)}`);
      onIngestComplete?.(d);
    } catch {
      appendLog('Resolution failed');
    }
    setBatchRunning(false);
  };

  const toggleExpand = (name: string) => {
    setExpanded(prev => {
      const n = new Set(prev);
      if (n.has(name)) n.delete(name); else n.add(name);
      return n;
    });
  };

  const filtered = people.filter(p =>
    !filter || p.label.toLowerCase().includes(filter.toLowerCase())
  );

  // Decide which file type to show based on mode
  const relevantType = extractionMode === 'uipath' ? 'json' : 'txt';

  const badgeColor = (type: string) =>
    type === 'json'
      ? { background: '#E67E22', color: '#fff' }
      : { background: '#4A90D9', color: '#fff' };

  return (
    <div style={s.container}>
      <div style={s.title}>🧪 Test Dataset — Ingest One by One</div>

      {/* Speed tip + Ingest All button */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '11px', color: extractionMode === 'uipath' ? '#27AE60' : '#E67E22' }}>
          {extractionMode === 'uipath'
            ? '⚡ UiPath mode — fast (~0.1s/file)'
            : '⚠ LangChain mode — slow (~30s/file). Switch to UiPath for speed.'}
        </span>
        {extractionMode === 'uipath' && (
          <button
            style={{
              padding: '4px 12px', background: batchRunning ? '#555' : '#9B59B6',
              border: 'none', borderRadius: '5px', color: '#fff', fontSize: '11px',
              cursor: batchRunning ? 'default' : 'pointer', fontWeight: 600, marginLeft: 'auto',
            }}
            onClick={ingestEverything}
            disabled={batchRunning}
          >
            {batchRunning ? '⏳ Ingesting...' : '⚡ Ingest ALL (UiPath)'}
          </button>
        )}
      </div>

      <input
        style={s.filter}
        placeholder="Filter people..."
        value={filter}
        onChange={e => setFilter(e.target.value)}
      />

      <div style={{ maxHeight: '320px', overflow: 'auto' }}>
        {filtered.map(person => {
          const isOpen    = expanded.has(person.name);
          const relevant  = person.files.filter(f => f.type === relevantType);
          const allDone   = relevant.every(f => done.has(f.path));

          return (
            <div key={person.name} style={s.personRow}>
              <div style={s.personHeader} onClick={() => toggleExpand(person.name)}>
                <span style={s.personLabel}>
                  {isOpen ? '▼' : '▶'} {person.label}
                  {allDone && relevant.length > 0 && (
                    <span style={{ color: '#27AE60', marginLeft: '6px' }}>✓</span>
                  )}
                </span>
                <button
                  style={s.ingestAllBtn}
                  onClick={e => { e.stopPropagation(); ingestAll(person); }}
                >
                  Ingest all {relevantType.toUpperCase()}
                </button>
              </div>

              {isOpen && person.files.map(file => {
                // Dim files not relevant to current mode
                const isRelevant = file.type === relevantType;
                const key        = file.path;
                const isLoading  = ingesting.has(key);
                const isDone     = done.has(key);
                const hasError   = errors[key];

                return (
                  <div
                    key={key}
                    style={{
                      ...s.fileRow,
                      opacity: isRelevant ? 1 : 0.35,
                    }}
                  >
                    <span style={s.fileName}>{file.name}</span>
                    <span style={{ ...s.badge, ...badgeColor(file.type) }}>
                      {file.type.toUpperCase()}
                    </span>

                    {isRelevant && (
                      hasError ? (
                        <button style={s.errorBtn} title={errors[key]}
                          onClick={() => ingestFile(file)}>
                          Retry
                        </button>
                      ) : isDone ? (
                        <button style={s.doneBtn} disabled>Done ✓</button>
                      ) : isLoading ? (
                        <button style={s.ingestBtn} disabled>...</button>
                      ) : (
                        <button style={s.ingestBtn} onClick={() => ingestFile(file)}>
                          Ingest
                        </button>
                      )
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      {log.length > 0 && (
        <div style={s.log}>
          {log.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      )}
    </div>
  );
};

export default TestDatasetPanel;
