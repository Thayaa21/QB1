/**
 * PersonalUploadPanel — drop ONE image/PDF → extract via BOTH paths.
 *
 * Each drop zone (Passport / Driver's License) sends the file to
 * POST /person/dual-extract which runs:
 *   1. UiPath API       → structured fields + confidence
 *   2. OCR + LLM verify → pytesseract + LLM correction
 *
 * Shows both results side by side + agreement/conflict comparison.
 * Also warns if the person already exists in the graph.
 */

import React, { useRef, useState } from 'react';
import { API_BASE } from '../api/client';

interface FieldResult { [key: string]: string }

interface ExtractionResult {
  doc_type:    string;
  entity_name: string;
  confidence:  number;
  fields:      FieldResult;
  saved_json:  string;
}

interface DualResult {
  person_name:      string;
  saved_to:         string;
  already_exists:   { exists: boolean; count: number; matches: { name: string; doc_type: string; source_file: string }[] };
  uipath_result:    ExtractionResult | null;
  uipath_error:     string | null;
  langchain_result: ExtractionResult | null;
  langchain_error:  string | null;
  agreement:        FieldResult;
  field_conflicts:  { field: string; uipath: string; langchain: string }[];
  agreement_count:  number;
  conflict_count:   number;
  graph_stats:      Record<string, number>;
}

interface SlotState {
  dragging: boolean;
  loading:  boolean;
  result:   DualResult | null;
  error:    string;
}

const defaultSlot = (): SlotState => ({ dragging: false, loading: false, result: null, error: '' });

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
  nameInput: {
    width:        '100%',
    padding:      '8px 10px',
    background:   '#0d0d1a',
    border:       '1px solid #555',
    borderRadius: '6px',
    color:        '#eee',
    fontSize:     '13px',
    marginBottom: '14px',
    boxSizing:    'border-box' as const,
  },
  slotsRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
    marginBottom: '12px',
  },
  slot: (active: boolean, done: boolean, loading: boolean) => ({
    border:       `2px dashed ${done ? '#27AE60' : active ? '#9B59B6' : '#333'}`,
    borderRadius: '8px',
    padding:      '16px 10px',
    textAlign:    'center' as const,
    cursor:       loading ? 'wait' : 'pointer',
    background:   done ? '#0d1a0d' : active ? '#1a0d2e' : '#12121f',
    transition:   'all 0.2s',
    minHeight:    '90px',
    display:      'flex',
    flexDirection: 'column' as const,
    alignItems:   'center',
    justifyContent: 'center',
    gap:          '4px',
  }),
  slotTitle: { fontSize: '12px', fontWeight: 700, color: '#ccc' },
  badge: (color: string) => ({
    fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
    background: color, color: '#fff', fontWeight: 600,
  }),
  hint:  { fontSize: '11px', color: '#666' },
  done:  { fontSize: '12px', color: '#27AE60' },
  error: { fontSize: '10px', color: '#E74C3C', marginTop: '2px', maxWidth: '140px' },
  // Duplicate warning
  dupWarning: {
    background:   '#1a1000',
    border:       '1px solid #E67E22',
    borderRadius: '6px',
    padding:      '8px 10px',
    fontSize:     '12px',
    color:        '#E67E22',
    marginBottom: '10px',
  },
  // Comparison table
  compareBox: {
    background:   '#12121f',
    borderRadius: '6px',
    padding:      '10px',
    fontSize:     '12px',
    marginTop:    '8px',
  },
  compareHeader: {
    display: 'grid', gridTemplateColumns: '120px 1fr 1fr',
    gap: '4px', fontWeight: 700, color: '#777',
    borderBottom: '1px solid #2a2a3e', paddingBottom: '4px', marginBottom: '6px',
  },
  compareRow: (agreed: boolean) => ({
    display: 'grid', gridTemplateColumns: '120px 1fr 1fr',
    gap: '4px', padding: '3px 0',
    borderBottom: '1px solid #1a1a2e',
    background: agreed ? 'transparent' : '#1a0a0a',
  }),
  fieldKey:   { color: '#4A90D9', overflow: 'hidden', textOverflow: 'ellipsis' },
  fieldValU:  { color: '#E67E22', overflow: 'hidden', textOverflow: 'ellipsis' },
  fieldValL:  { color: '#4A90D9', overflow: 'hidden', textOverflow: 'ellipsis' },
  fieldAgreed:{ color: '#27AE60', overflow: 'hidden', textOverflow: 'ellipsis' },
  summaryRow: {
    display: 'flex', gap: '8px', marginTop: '8px', flexWrap: 'wrap' as const,
  },
  pill: (color: string) => ({
    padding: '3px 10px', borderRadius: '12px',
    background: color, color: '#fff', fontSize: '11px',
  }),
};

interface Props {
  onComplete?: (result: DualResult) => void;
}

const PersonalUploadPanel: React.FC<Props> = ({ onComplete }) => {
  const [personName, setPersonName] = useState('thayaananthan_kanagaraj');
  const [passport,   setPassport]   = useState<SlotState>(defaultSlot());
  const [license,    setLicense]    = useState<SlotState>(defaultSlot());
  const passportRef = useRef<HTMLInputElement>(null);
  const licenseRef  = useRef<HTMLInputElement>(null);

  const uploadFile = async (
    file:   File,
    setter: React.Dispatch<React.SetStateAction<SlotState>>,
  ) => {
    setter(s => ({ ...s, loading: true, error: '', result: null }));

    const formData = new FormData();
    formData.append('file', file);
    formData.append('person_name', personName.trim().toLowerCase().replace(/\s+/g, '_'));

    try {
      const res  = await fetch(`${API_BASE}/person/dual-extract`, {
        method: 'POST', body: formData,
      });
      const data: DualResult = await res.json();
      if (!res.ok) throw new Error((data as unknown as { detail: string }).detail || 'Failed');
      setter(s => ({ ...s, loading: false, result: data }));
      onComplete?.(data);
    } catch (e: unknown) {
      setter(s => ({ ...s, loading: false, error: e instanceof Error ? e.message : String(e) }));
    }
  };

  const onDrop = (e: React.DragEvent, setter: React.Dispatch<React.SetStateAction<SlotState>>) => {
    e.preventDefault();
    setter(s => ({ ...s, dragging: false }));
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file, setter);
  };

  const onInput = (e: React.ChangeEvent<HTMLInputElement>, setter: React.Dispatch<React.SetStateAction<SlotState>>) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file, setter);
  };

  const renderResult = (result: DualResult | null) => {
    if (!result) return null;

    // Collect all unique fields from both extractors
    const allFields = new Set([
      ...Object.keys(result.uipath_result?.fields    || {}),
      ...Object.keys(result.langchain_result?.fields || {}),
    ]);
    const agreementSet = new Set(Object.keys(result.agreement));

    return (
      <div>
        {/* Duplicate warning */}
        {result.already_exists.exists && (
          <div style={S.dupWarning}>
            ⚠ Person already in graph ({result.already_exists.count} record{result.already_exists.count > 1 ? 's' : ''}):
            {result.already_exists.matches.map((m, i) => (
              <span key={i}> {m.name} ({m.doc_type})</span>
            ))}
          </div>
        )}

        {/* Comparison table */}
        <div style={S.compareBox}>
          <div style={{ ...S.compareHeader }}>
            <span>Field</span>
            <span style={{ color: '#E67E22' }}>🤖 UiPath</span>
            <span style={{ color: '#4A90D9' }}>🔗 LangChain OCR</span>
          </div>

          {Array.from(allFields).filter(k => !k.startsWith('_')).map(field => {
            const uVal = result.uipath_result?.fields[field]    || '—';
            const lVal = result.langchain_result?.fields[field] || '—';
            const agreed = agreementSet.has(field);

            return (
              <div key={field} style={S.compareRow(agreed)}>
                <span style={S.fieldKey}>{field}</span>
                <span style={agreed ? S.fieldAgreed : S.fieldValU}>{uVal}</span>
                <span style={agreed ? S.fieldAgreed : S.fieldValL}>{lVal}</span>
              </div>
            );
          })}
        </div>

        {/* Summary */}
        <div style={S.summaryRow}>
          <span style={S.pill('#27AE60')}>✓ {result.agreement_count} agreed</span>
          {result.conflict_count > 0 && (
            <span style={S.pill('#E74C3C')}>⚠ {result.conflict_count} conflicts</span>
          )}
          {result.already_exists.exists
            ? <span style={S.pill('#E67E22')}>⚠ Already in graph</span>
            : <span style={S.pill('#4A90D9')}>✓ New person added</span>
          }
        </div>
      </div>
    );
  };

  return (
    <div style={S.container}>
      <div style={S.title}>🪪 Upload Your Documents (Dual Extraction)</div>

      <input
        style={S.nameInput}
        value={personName}
        onChange={e => setPersonName(e.target.value)}
        placeholder="your_name_here"
      />

      <div style={S.slotsRow}>
        {/* Passport */}
        <div
          style={S.slot(passport.dragging, !!passport.result, passport.loading)}
          onDragOver={e => { e.preventDefault(); setPassport(s => ({ ...s, dragging: true })); }}
          onDragLeave={() => setPassport(s => ({ ...s, dragging: false }))}
          onDrop={e => onDrop(e, setPassport)}
          onClick={() => !passport.loading && passportRef.current?.click()}
        >
          <div style={S.slotTitle}>PASSPORT</div>
          <div style={S.badge('#9B59B6')}>Dual Extract</div>
          {passport.loading ? <div style={S.hint}>⏳ Extracting...</div>
            : passport.result ? <div style={S.done}>✓ Done</div>
            : <div style={S.hint}>Drop image / PDF</div>}
          {passport.error && <div style={S.error}>{passport.error.slice(0, 80)}</div>}
        </div>

        {/* Driver's License */}
        <div
          style={S.slot(license.dragging, !!license.result, license.loading)}
          onDragOver={e => { e.preventDefault(); setLicense(s => ({ ...s, dragging: true })); }}
          onDragLeave={() => setLicense(s => ({ ...s, dragging: false }))}
          onDrop={e => onDrop(e, setLicense)}
          onClick={() => !license.loading && licenseRef.current?.click()}
        >
          <div style={S.slotTitle}>DRIVER'S LICENSE</div>
          <div style={S.badge('#9B59B6')}>Dual Extract</div>
          {license.loading ? <div style={S.hint}>⏳ Extracting...</div>
            : license.result ? <div style={S.done}>✓ Done</div>
            : <div style={S.hint}>Drop image / PDF</div>}
          {license.error && <div style={S.error}>{license.error.slice(0, 80)}</div>}
        </div>
      </div>

      <input ref={passportRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff"
        style={{ display: 'none' }} onChange={e => onInput(e, setPassport)} />
      <input ref={licenseRef}  type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff"
        style={{ display: 'none' }} onChange={e => onInput(e, setLicense)} />

      {/* Results for passport */}
      {passport.result && (
        <div style={{ marginTop: '10px' }}>
          <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>
            📄 Passport — {passport.result.uipath_result?.entity_name || passport.result.langchain_result?.entity_name || personName}
          </div>
          {renderResult(passport.result)}
        </div>
      )}

      {/* Results for license */}
      {license.result && (
        <div style={{ marginTop: '10px' }}>
          <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>
            📄 License — {license.result.uipath_result?.entity_name || license.result.langchain_result?.entity_name || personName}
          </div>
          {renderResult(license.result)}
        </div>
      )}
    </div>
  );
};

export default PersonalUploadPanel;
