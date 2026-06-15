/**
 * PersonalUploadPanel — upload YOUR real documents.
 *
 * Two upload slots:
 *   - Passport  → UiPath API (better for scanned/printed docs)
 *   - Driver's License → LangChain/Ollama (works on text files)
 *
 * Both get saved to docs/people/{your_name}/ and linked as the same person.
 */

import React, { useRef, useState } from 'react';
import { API_BASE } from '../api/client';

interface UploadResult {
  person_name:       string;
  filename:          string;
  extractor:         string;
  document_type:     string;
  extracted_fields:  Record<string, string>;
  entity_name:       string;
  resolved:          boolean;
  same_as_links?:    unknown[];
  graph_stats?:      Record<string, number>;
}

interface Props {
  onComplete?: (result: UploadResult) => void;
}

const S: Record<string, React.CSSProperties> = {
  container: {
    background:   '#1e1e2e',
    border:       '1px solid #9B59B6',
    borderRadius: '10px',
    padding:      '16px',
  },
  title: {
    fontSize:     '15px',
    fontWeight:   600,
    color:        '#9B59B6',
    marginBottom: '12px',
    display:      'flex',
    alignItems:   'center',
    gap:          '8px',
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
  row: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap:     '12px',
    marginBottom: '12px',
  },
  slot: (active: boolean, done: boolean) => ({
    border:       `2px dashed ${done ? '#27AE60' : active ? '#9B59B6' : '#333'}`,
    borderRadius: '8px',
    padding:      '14px',
    textAlign:    'center' as const,
    cursor:       'pointer',
    background:   done ? '#0d1a0d' : active ? '#1a0d2e' : '#12121f',
    transition:   'all 0.2s',
  }),
  slotTitle: {
    fontSize:   '12px',
    fontWeight: 600,
    color:      '#aaa',
    marginBottom: '4px',
  },
  slotBadge: (color: string) => ({
    display:      'inline-block',
    fontSize:     '10px',
    padding:      '2px 8px',
    borderRadius: '10px',
    background:   color,
    color:        '#fff',
    marginBottom: '6px',
  }),
  slotHint: {
    fontSize: '11px',
    color:    '#555',
  },
  slotDone: {
    fontSize: '12px',
    color:    '#27AE60',
  },
  resultBox: {
    background:   '#0d0d1a',
    borderRadius: '6px',
    padding:      '10px',
    fontSize:     '12px',
    marginTop:    '10px',
  },
  resultTitle: {
    color:        '#9B59B6',
    fontWeight:   600,
    marginBottom: '6px',
  },
  field: {
    display:        'flex',
    justifyContent: 'space-between',
    padding:        '3px 0',
    borderBottom:   '1px solid #1a1a2e',
    color:          '#ccc',
  },
  fieldKey:   { color: '#4A90D9', minWidth: '120px' },
  fieldVal:   { color: '#eee', textAlign: 'right' as const },
  resolvedBadge: (resolved: boolean) => ({
    marginTop:    '8px',
    padding:      '6px 10px',
    borderRadius: '6px',
    background:   resolved ? '#0d1a0d' : '#1a0a00',
    color:        resolved ? '#27AE60' : '#E67E22',
    fontSize:     '12px',
    textAlign:    'center' as const,
  }),
  error: {
    color:        '#E74C3C',
    fontSize:     '12px',
    marginTop:    '8px',
    background:   '#1a0a0a',
    padding:      '6px 10px',
    borderRadius: '6px',
  },
};

interface SlotState {
  dragging: boolean;
  loading:  boolean;
  done:     boolean;
  result:   UploadResult | null;
  error:    string;
}

const defaultSlot = (): SlotState => ({
  dragging: false, loading: false, done: false, result: null, error: '',
});

const PersonalUploadPanel: React.FC<Props> = ({ onComplete }) => {
  const [personName, setPersonName] = useState('thayaananthan_kanagaraj');
  const [passport,   setPassport]   = useState<SlotState>(defaultSlot());
  const [license,    setLicense]    = useState<SlotState>(defaultSlot());

  const passportRef = useRef<HTMLInputElement>(null);
  const licenseRef  = useRef<HTMLInputElement>(null);

  const uploadFile = async (
    file:      File,
    extractor: 'uipath' | 'langchain',
    setter:    React.Dispatch<React.SetStateAction<SlotState>>,
  ) => {
    setter(s => ({ ...s, loading: true, error: '', done: false, result: null }));

    const formData = new FormData();
    formData.append('file', file);
    formData.append('person_name', personName.trim().toLowerCase().replace(/\s+/g, '_'));
    formData.append('extractor', extractor);

    try {
      const res  = await fetch(`${API_BASE}/person/upload`, {
        method: 'POST',
        body:   formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');

      // Fetch person info to check if documents are linked
      const personRes  = await fetch(`${API_BASE}/person/${data.person_name}`);
      const personData = await personRes.json();

      const result: UploadResult = { ...data, ...personData };
      setter(s => ({ ...s, loading: false, done: true, result }));
      onComplete?.(result);

    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setter(s => ({ ...s, loading: false, error: msg }));
    }
  };

  const handleDrop = (
    e: React.DragEvent,
    extractor: 'uipath' | 'langchain',
    setter: React.Dispatch<React.SetStateAction<SlotState>>,
  ) => {
    e.preventDefault();
    setter(s => ({ ...s, dragging: false }));
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file, extractor, setter);
  };

  const handleInput = (
    e: React.ChangeEvent<HTMLInputElement>,
    extractor: 'uipath' | 'langchain',
    setter: React.Dispatch<React.SetStateAction<SlotState>>,
  ) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file, extractor, setter);
  };

  const bothDone     = passport.done && license.done;
  const eitherResult = passport.result || license.result;
  const isLinked     = eitherResult && (eitherResult.same_as_links?.length ?? 0) > 0;

  return (
    <div style={S.container}>
      <div style={S.title}>
        🪪 Upload Your Documents
      </div>

      <input
        style={S.nameInput}
        value={personName}
        onChange={e => setPersonName(e.target.value)}
        placeholder="your_name (folder name, no spaces)"
      />

      <div style={S.row}>
        {/* Passport slot — UiPath */}
        <div
          style={S.slot(passport.dragging, passport.done)}
          onDragOver={e => { e.preventDefault(); setPassport(s => ({ ...s, dragging: true })); }}
          onDragLeave={() => setPassport(s => ({ ...s, dragging: false }))}
          onDrop={e => handleDrop(e, 'uipath', setPassport)}
          onClick={() => !passport.loading && passportRef.current?.click()}
        >
          <div style={S.slotTitle}>PASSPORT</div>
          <div style={S.slotBadge('#E67E22')}>🤖 UiPath API</div>
          <br />
          {passport.loading ? (
            <div style={S.slotHint}>⏳ Extracting...</div>
          ) : passport.done ? (
            <div style={S.slotDone}>✓ Extracted</div>
          ) : (
            <div style={S.slotHint}>Drop PDF/image here</div>
          )}
          {passport.error && <div style={{ fontSize: '10px', color: '#E74C3C', marginTop: '4px' }}>⚠ {passport.error.slice(0, 60)}</div>}
        </div>

        {/* Driver's License slot — LangChain */}
        <div
          style={S.slot(license.dragging, license.done)}
          onDragOver={e => { e.preventDefault(); setLicense(s => ({ ...s, dragging: true })); }}
          onDragLeave={() => setLicense(s => ({ ...s, dragging: false }))}
          onDrop={e => handleDrop(e, 'langchain', setLicense)}
          onClick={() => !license.loading && licenseRef.current?.click()}
        >
          <div style={S.slotTitle}>DRIVER'S LICENSE</div>
          <div style={S.slotBadge('#4A90D9')}>🔗 LangChain LLM</div>
          <br />
          {license.loading ? (
            <div style={S.slotHint}>⏳ Extracting...</div>
          ) : license.done ? (
            <div style={S.slotDone}>✓ Extracted</div>
          ) : (
            <div style={S.slotHint}>Drop .txt file here</div>
          )}
          {license.error && <div style={{ fontSize: '10px', color: '#E74C3C', marginTop: '4px' }}>⚠ {license.error.slice(0, 60)}</div>}
        </div>
      </div>

      <input ref={passportRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff"
        style={{ display: 'none' }} onChange={e => handleInput(e, 'uipath', setPassport)} />
      <input ref={licenseRef}  type="file" accept=".txt,.pdf,.png,.jpg"
        style={{ display: 'none' }} onChange={e => handleInput(e, 'langchain', setLicense)} />

      {/* Results */}
      {eitherResult && (
        <div style={S.resultBox}>
          <div style={S.resultTitle}>
            👤 {eitherResult.entity_name || personName}
          </div>
          {Object.entries(eitherResult.extracted_fields || {}).map(([k, v]) => (
            <div key={k} style={S.field}>
              <span style={S.fieldKey}>{k}</span>
              <span style={S.fieldVal}>{String(v)}</span>
            </div>
          ))}
        </div>
      )}

      {bothDone && (
        <div style={S.resolvedBadge(!!isLinked)}>
          {isLinked
            ? `✓ Both documents linked as the same person — ${personName}`
            : `⏳ Documents saved — run a query to verify linking`
          }
        </div>
      )}
    </div>
  );
};

export default PersonalUploadPanel;
