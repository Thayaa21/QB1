/**
 * PersonalUploadPanel — Two completely separate extraction pipelines.
 *
 * LEFT PANEL:  UiPath Document Understanding API
 *   - Drop image/PDF → sends to cloud.uipath.com
 *   - Shows extracted fields
 *   - "Add to Graph" button (user confirms before adding)
 *
 * RIGHT PANEL: LangChain OCR + LLM
 *   - Drop image/PDF → pytesseract OCR → LLM verify
 *   - Shows extracted fields
 *   - "Add to Graph" button (user confirms before adding)
 *
 * Both are fully independent. Results are shown for review before
 * anything is added to the knowledge graph.
 */

import React, { useRef, useState } from 'react';
import { API_BASE } from '../api/client';

interface FieldEntry {
  value:      string;
  confidence: number;
}

interface ExtractionResult {
  person_name:  string;
  filename:     string;
  doc_type:     string;
  entity_name:  string;
  confidence:   number;
  fields:       Record<string, FieldEntry | string>;
  saved_json:   string;
  extractor:    string;
  graph_stats?: Record<string, number>;
}

type SlotPhase = 'idle' | 'extracting' | 'review' | 'adding' | 'added' | 'error';

interface SlotState {
  phase:   SlotPhase;
  result:  ExtractionResult | null;
  error:   string;
  dragging: boolean;
}

const defaultSlot = (): SlotState => ({
  phase: 'idle', result: null, error: '', dragging: false,
});

interface Props {
  onAdded?: (result: ExtractionResult) => void;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const S: Record<string, React.CSSProperties> = {
  container: {
    background:   '#1e1e2e',
    border:       '1px solid #9B59B6',
    borderRadius: '10px',
    padding:      '16px',
  },
  title: {
    fontSize:   '15px',
    fontWeight: 600,
    color:      '#9B59B6',
    marginBottom: '12px',
  },
  nameRow: {
    display:       'flex',
    gap:           '8px',
    marginBottom:  '14px',
    alignItems:    'center',
  },
  nameInput: {
    flex:         1,
    padding:      '7px 10px',
    background:   '#0d0d1a',
    border:       '1px solid #555',
    borderRadius: '6px',
    color:        '#eee',
    fontSize:     '13px',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
  },
  panel: (borderColor: string) => ({
    background:   '#12121f',
    border:       `1px solid ${borderColor}`,
    borderRadius: '8px',
    padding:      '12px',
    display:      'flex',
    flexDirection: 'column' as const,
    gap:          '8px',
  }),
  panelTitle: (color: string) => ({
    fontSize:   '12px',
    fontWeight: 700,
    color,
    display:    'flex',
    alignItems: 'center',
    gap:        '6px',
  }),
  dropzone: (dragging: boolean, done: boolean) => ({
    border:       `2px dashed ${done ? '#27AE60' : dragging ? '#9B59B6' : '#333'}`,
    borderRadius: '6px',
    padding:      '14px 8px',
    textAlign:    'center' as const,
    cursor:       'pointer',
    background:   done ? '#0d1a0d' : dragging ? '#1a0d2e' : '#0d0d1a',
    transition:   'all 0.2s',
    fontSize:     '12px',
    color:        '#888',
  }),
  fieldsBox: {
    background:   '#0d0d1a',
    borderRadius: '6px',
    padding:      '8px',
    maxHeight:    '200px',
    overflow:     'auto',
  },
  fieldRow: {
    display:        'flex',
    justifyContent: 'space-between',
    padding:        '3px 0',
    borderBottom:   '1px solid #1a1a2e',
    fontSize:       '11px',
    gap:            '6px',
  },
  fieldKey: {
    color:    '#4A90D9',
    minWidth: '110px',
    flexShrink: 0,
  },
  fieldVal: {
    color:    '#eee',
    textAlign: 'right' as const,
    wordBreak: 'break-word' as const,
  },
  fieldConf: {
    color:    '#666',
    fontSize: '10px',
    flexShrink: 0,
  },
  addBtn: (disabled: boolean) => ({
    padding:      '7px 14px',
    background:   disabled ? '#333' : '#27AE60',
    border:       'none',
    borderRadius: '6px',
    color:        disabled ? '#666' : '#fff',
    fontSize:     '12px',
    fontWeight:   600,
    cursor:       disabled ? 'default' : 'pointer',
    width:        '100%',
  }),
  editRow: {
    display:  'flex',
    gap:      '4px',
    fontSize: '11px',
  },
  editInput: {
    flex:         1,
    padding:      '3px 6px',
    background:   '#0d0d1a',
    border:       '1px solid #444',
    borderRadius: '4px',
    color:        '#eee',
    fontSize:     '11px',
  },
  editSave: {
    padding:      '3px 8px',
    background:   '#4A90D9',
    border:       'none',
    borderRadius: '4px',
    color:        '#fff',
    fontSize:     '11px',
    cursor:       'pointer',
  },
  statusBadge: (color: string) => ({
    padding:      '2px 8px',
    borderRadius: '10px',
    background:   color,
    color:        '#fff',
    fontSize:     '10px',
    fontWeight:   600,
    display:      'inline-block',
  }),
  error: {
    color:   '#E74C3C',
    fontSize: '11px',
    padding:  '4px 6px',
    background: '#1a0a0a',
    borderRadius: '4px',
  },
};

// ---------------------------------------------------------------------------
// Single extraction panel (reused for both UiPath and LangChain)
// ---------------------------------------------------------------------------

interface PanelProps {
  title:      string;
  icon:       string;
  color:      string;
  extractor:  'uipath' | 'langchain';
  personName: string;
  onAdded?:   (result: ExtractionResult) => void;
}

const ExtractionPanel: React.FC<PanelProps> = ({
  title, icon, color, extractor, personName, onAdded,
}) => {
  const [state,    setState]    = useState<SlotState>(defaultSlot());
  const [editKey,  setEditKey]  = useState<string | null>(null);
  const [editVal,  setEditVal]  = useState('');
  const [editedFields, setEditedFields] = useState<Record<string, string>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  const extract = async (file: File) => {
    setState(s => ({ ...s, phase: 'extracting', error: '', dragging: false }));

    const formData = new FormData();
    formData.append('file', file);
    formData.append('person_name', personName.trim().toLowerCase().replace(/\s+/g, '_'));
    formData.append('extractor', extractor);
    formData.append('dry_run', 'true');  // extract only, don't add to graph yet

    try {
      const res  = await fetch(`${API_BASE}/person/extract-preview`, {
        method: 'POST', body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Extraction failed');
      setState(s => ({ ...s, phase: 'review', result: data }));
      setEditedFields({});
    } catch (e: unknown) {
      setState(s => ({
        ...s, phase: 'error',
        error: e instanceof Error ? e.message : String(e),
      }));
    }
  };

  const addToGraph = async () => {
    if (!state.result) return;
    setState(s => ({ ...s, phase: 'adding' }));

    // Apply any edits the user made
    const finalResult = {
      ...state.result,
      fields: {
        ...Object.fromEntries(
          Object.entries(state.result.fields).map(([k, v]) => [
            k, editedFields[k] !== undefined
              ? { value: editedFields[k], confidence: 1.0 }
              : v,
          ])
        ),
      },
    };

    try {
      const res = await fetch(`${API_BASE}/person/add-to-graph`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          extraction_result: finalResult,
          person_name:       personName.trim().toLowerCase().replace(/\s+/g, '_'),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to add to graph');
      setState(s => ({ ...s, phase: 'added', result: { ...s.result!, graph_stats: data.graph_stats } }));
      onAdded?.(finalResult);
    } catch (e: unknown) {
      setState(s => ({
        ...s, phase: 'error',
        error: e instanceof Error ? e.message : String(e),
      }));
    }
  };

  const reset = () => {
    setState(defaultSlot());
    setEditedFields({});
    setEditKey(null);
  };

  const startEdit = (key: string, currentVal: string) => {
    setEditKey(key);
    setEditVal(currentVal);
  };

  const saveEdit = () => {
    if (editKey) {
      setEditedFields(prev => ({ ...prev, [editKey]: editVal }));
      setEditKey(null);
    }
  };

  const getFieldValue = (key: string, raw: FieldEntry | string): string => {
    if (editedFields[key] !== undefined) return editedFields[key];
    if (typeof raw === 'string') return raw;
    return raw.value || '';
  };

  const getFieldConf = (raw: FieldEntry | string): number => {
    if (typeof raw === 'object') return raw.confidence;
    return 1.0;
  };

  return (
    <div style={S.panel(color)}>
      <div style={S.panelTitle(color)}>
        <span>{icon}</span>
        <span>{title}</span>
        {state.phase === 'added' && <span style={S.statusBadge('#27AE60')}>✓ In Graph</span>}
        {state.phase === 'review' && <span style={S.statusBadge('#E67E22')}>Review</span>}
        {state.phase === 'extracting' && <span style={S.statusBadge('#4A90D9')}>Extracting...</span>}
      </div>

      {/* Drop zone */}
      {(state.phase === 'idle' || state.phase === 'error') && (
        <div
          style={S.dropzone(state.dragging, false)}
          onDragOver={e => { e.preventDefault(); setState(s => ({ ...s, dragging: true })); }}
          onDragLeave={() => setState(s => ({ ...s, dragging: false }))}
          onDrop={e => {
            e.preventDefault();
            const f = e.dataTransfer.files[0];
            if (f) extract(f);
          }}
          onClick={() => fileRef.current?.click()}
        >
          Drop image / PDF here<br />
          <span style={{ fontSize: '10px', color: '#555' }}>PNG, JPG, PDF, TIFF</span>
        </div>
      )}

      {state.phase === 'extracting' && (
        <div style={{ ...S.dropzone(false, false), color: '#4A90D9' }}>
          ⏳ Extracting fields...
        </div>
      )}

      {state.error && (
        <div style={S.error}>⚠ {state.error}</div>
      )}

      {/* Review: show fields for editing before adding */}
      {(state.phase === 'review' || state.phase === 'adding' || state.phase === 'added') && state.result && (
        <>
          <div style={{ fontSize: '11px', color: '#888' }}>
            📄 {state.result.filename} — <b style={{ color: '#ccc' }}>{state.result.doc_type}</b>
          </div>

          <div style={S.fieldsBox}>
            {Object.entries(state.result.fields)
              .filter(([k]) => !k.startsWith('_'))
              .map(([key, raw]) => {
                const val  = getFieldValue(key, raw);
                const conf = getFieldConf(raw);
                const isEditing = editKey === key;

                return (
                  <div key={key} style={S.fieldRow}>
                    <span style={S.fieldKey}>{key}</span>
                    {isEditing ? (
                      <div style={S.editRow}>
                        <input
                          style={S.editInput}
                          value={editVal}
                          onChange={e => setEditVal(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && saveEdit()}
                          autoFocus
                        />
                        <button style={S.editSave} onClick={saveEdit}>✓</button>
                      </div>
                    ) : (
                      <span
                        style={{ ...S.fieldVal, cursor: state.phase === 'review' ? 'pointer' : 'default',
                                 textDecoration: editedFields[key] !== undefined ? 'underline' : 'none',
                                 color: editedFields[key] !== undefined ? '#E67E22' : '#eee' }}
                        title={state.phase === 'review' ? 'Click to edit' : undefined}
                        onClick={() => state.phase === 'review' && startEdit(key, val)}
                      >
                        {val || '—'}
                      </span>
                    )}
                    <span style={S.fieldConf}>{Math.round(conf * 100)}%</span>
                  </div>
                );
              })}
          </div>

          {state.phase === 'review' && (
            <div style={{ fontSize: '10px', color: '#555', textAlign: 'center' as const }}>
              Click any field to edit before adding
            </div>
          )}

          {/* Action buttons */}
          {state.phase === 'review' && (
            <div style={{ display: 'flex', gap: '6px' }}>
              <button style={{ ...S.addBtn(false), background: '#27AE60' }} onClick={addToGraph}>
                ✓ Add to Graph
              </button>
              <button
                style={{ ...S.addBtn(false), background: '#E74C3C', flex: '0 0 auto', width: 'auto', padding: '7px 12px' }}
                onClick={reset}
              >
                ✕ Discard
              </button>
            </div>
          )}

          {state.phase === 'adding' && (
            <button style={S.addBtn(true)}>Adding to graph...</button>
          )}

          {state.phase === 'added' && (
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <div style={{ ...S.statusBadge('#27AE60'), flex: 1, textAlign: 'center' as const, padding: '6px' }}>
                ✓ Added to Knowledge Graph
              </div>
              <button
                style={{ ...S.addBtn(false), background: '#555', width: 'auto', padding: '6px 10px' }}
                onClick={reset}
              >
                Upload another
              </button>
            </div>
          )}
        </>
      )}

      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.tiff"
        style={{ display: 'none' }}
        onChange={e => {
          const f = e.target.files?.[0];
          if (f) extract(f);
        }}
      />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main panel — two independent pipelines side by side
// ---------------------------------------------------------------------------

const PersonalUploadPanel: React.FC<Props> = ({ onAdded }) => {
  const [personName, setPersonName] = useState('thayaananthan_kanagaraj');

  return (
    <div style={S.container}>
      <div style={S.title}>🪪 Upload Your Documents</div>

      <div style={S.nameRow}>
        <input
          style={S.nameInput}
          value={personName}
          onChange={e => setPersonName(e.target.value)}
          placeholder="your_name_here"
        />
      </div>

      <div style={S.grid}>
        <ExtractionPanel
          title="UiPath API"
          icon="🤖"
          color="#E67E22"
          extractor="uipath"
          personName={personName}
          onAdded={onAdded}
        />
        <ExtractionPanel
          title="LangChain OCR"
          icon="🔗"
          color="#4A90D9"
          extractor="langchain"
          personName={personName}
          onAdded={onAdded}
        />
      </div>
    </div>
  );
};

export default PersonalUploadPanel;
