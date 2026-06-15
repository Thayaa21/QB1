/**
 * QueryPanel — smart query with disambiguation, deep answers, and proof.
 *
 * Uses /smart-query which handles:
 * - Disambiguation: multiple people with same name → show options
 * - Open-ended: "how many licenses" → aggregate summary
 * - Deep answers: always shows source file + line number
 */

import React, { useState } from 'react';
import { API_BASE } from '../api/client';
import type { QueryResult } from '../types';

interface SmartQueryResponse {
  type:     'answer' | 'disambiguation' | 'summary' | 'empty' | 'not_found';
  answer?:  string;
  person?:  string;
  facts?:   FactItem[];
  options?: DisambigOption[];
  entities?: string[];
  count?:   number;
}

interface FactItem {
  fact:            string;
  source_filename: string;
  doc_type:        string;
  line_number:     number;
  line_text:       string;
  attribute_key:   string;
  value:           string;
}

interface DisambigOption {
  name:       string;
  doc_types:  string[];
  files:      string[];
  dob_hint:   string;
  entity_ids: string[];
}

interface QueryPanelProps {
  onResult: (result: QueryResult | SmartQueryResponse) => void;
}

const S: Record<string, React.CSSProperties> = {
  container: {
    background:   '#1e1e2e',
    border:       '1px solid #333',
    borderRadius: '8px',
    padding:      '16px',
  },
  title: { color: '#eee', fontSize: '16px', fontWeight: 600, marginBottom: '12px' },
  input: {
    width: '100%', padding: '10px', background: '#0d0d1a',
    color: '#ddd', border: '1px solid #444', borderRadius: '4px',
    fontSize: '14px', boxSizing: 'border-box' as const,
  },
  row: { display: 'flex', gap: '12px', marginTop: '10px', alignItems: 'center', flexWrap: 'wrap' as const },
  label: { color: '#888', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' },
  select: { background: '#0d0d1a', color: '#ddd', border: '1px solid #444', borderRadius: '4px', padding: '4px 8px', fontSize: '13px' },
  askBtn: { marginLeft: 'auto', padding: '8px 24px', background: '#27AE60', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', fontSize: '14px', fontWeight: 600 },
  error: { marginTop: '10px', color: '#E74C3C', fontSize: '13px' },
  // Result area
  resultBox: { marginTop: '14px', borderTop: '1px solid #2a2a3e', paddingTop: '12px' },
  answerText: { color: '#eee', fontSize: '14px', lineHeight: 1.6, marginBottom: '12px', whiteSpace: 'pre-wrap' as const },
  // Proof section
  proofTitle: { fontSize: '12px', color: '#4A90D9', fontWeight: 600, marginBottom: '6px' },
  factRow: { display: 'flex', flexDirection: 'column' as const, padding: '6px 8px', background: '#12121f', borderRadius: '4px', marginBottom: '4px' },
  factKey: { fontSize: '11px', color: '#4A90D9' },
  factVal: { fontSize: '13px', color: '#eee', fontWeight: 600 },
  factSrc: { fontSize: '10px', color: '#666', marginTop: '2px' },
  factLine: { fontSize: '11px', color: '#888', fontStyle: 'italic', borderLeft: '2px solid #333', paddingLeft: '6px', marginTop: '2px' },
  // Disambiguation
  disambigTitle: { fontSize: '14px', color: '#E67E22', fontWeight: 600, marginBottom: '8px' },
  optionBtn: { width: '100%', padding: '10px 12px', background: '#1a1a2e', border: '1px solid #4A90D9', borderRadius: '6px', color: '#eee', cursor: 'pointer', textAlign: 'left' as const, marginBottom: '6px', fontSize: '13px' },
  optionName: { color: '#4A90D9', fontWeight: 600, fontSize: '14px' },
  optionMeta: { color: '#888', fontSize: '11px', marginTop: '2px' },
  // Summary
  summaryItem: { color: '#ccc', fontSize: '12px', padding: '3px 0', borderBottom: '1px solid #1a1a2e' },
};

const QueryPanel: React.FC<QueryPanelProps> = ({ onResult }) => {
  const [question,        setQuestion]        = useState('');
  const [maxHops,         setMaxHops]         = useState(3);
  const [temporalContext, setTemporalContext] = useState('current');
  const [loading,         setLoading]         = useState(false);
  const [error,           setError]           = useState<string | null>(null);
  const [smartResult,     setSmartResult]     = useState<SmartQueryResponse | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState('');

  const runSmartQuery = async (q: string) => {
    setLoading(true);
    setError(null);
    setSmartResult(null);
    setPendingQuestion(q);

    try {
      const resp = await fetch(`${API_BASE}/smart-query`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ question: q, max_hops: maxHops, temporal_context: temporalContext }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error((data as unknown as { detail: string }).detail || 'Query failed');
      // Validate response has expected shape
      if (!data || typeof data !== 'object') throw new Error('Invalid response from server');
      setSmartResult(data as SmartQueryResponse);
      onResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Query failed. Check console.');
      console.error('Smart query error:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleQuery = () => {
    if (!question.trim()) { setError('Please enter a question.'); return; }
    runSmartQuery(question);
  };

  // When user picks a disambiguation option, refine the question
  const pickOption = (option: DisambigOption) => {
    const refined = `${pendingQuestion} for ${option.name}`;
    setQuestion(refined);
    runSmartQuery(refined);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleQuery(); }
  };

  return (
    <div style={S.container}>
      <div style={S.title}>🔍 Ask a Question</div>
      <input
        style={S.input}
        value={question}
        onChange={e => setQuestion(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="e.g. What is Thayaa's date of birth? / How many licenses do we have?"
      />
      <div style={S.row}>
        <label style={S.label}>
          Hops:
          <select style={S.select} value={maxHops} onChange={e => setMaxHops(Number(e.target.value))}>
            {[1,2,3,4,5].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label style={S.label}>
          Temporal:
          <select style={S.select} value={temporalContext} onChange={e => setTemporalContext(e.target.value)}>
            <option value="current">current</option>
            <option value="all">all</option>
          </select>
        </label>
        <button style={{ ...S.askBtn, opacity: loading ? 0.7 : 1 }}
                onClick={handleQuery} disabled={loading}>
          {loading ? 'Thinking...' : 'Ask'}
        </button>
      </div>
      {error && <div style={S.error}>✗ {error}</div>}

      {/* Results */}
      {smartResult && smartResult.type && (
        <div style={S.resultBox}>

          {/* Disambiguation — multiple people found */}
          {smartResult.type === 'disambiguation' && (
            <>
              <div style={S.disambigTitle}>🤔 {smartResult.answer}</div>
              {(smartResult.options || []).map((opt, i) => (
                <button key={i} style={S.optionBtn} onClick={() => pickOption(opt)}>
                  <div style={S.optionName}>{opt.name}</div>
                  <div style={S.optionMeta}>
                    {opt.doc_types.join(', ')} | {opt.files.join(', ')}
                    {opt.dob_hint ? ` | DOB: ${opt.dob_hint}` : ''}
                  </div>
                </button>
              ))}
            </>
          )}

          {/* Direct answer with proof */}
          {smartResult.type === 'answer' && (
            <>
              <div style={{ fontSize: '12px', color: '#888', marginBottom: '6px' }}>
                👤 {smartResult.person}
              </div>
              <div style={S.answerText}>{smartResult.answer}</div>

              {/* Proof — every fact with source line */}
              {(smartResult.facts || []).length > 0 && (
                <>
                  <div style={S.proofTitle}>📎 Sources (Proof)</div>
                  {(smartResult.facts || [])
                    .filter(f => !f.attribute_key.startsWith('_'))
                    .slice(0, 15)
                    .map((f, i) => (
                      <div key={i} style={S.factRow}>
                        <span style={S.factKey}>{f.attribute_key}</span>
                        <span style={S.factVal}>{f.value}</span>
                        <span style={S.factSrc}>
                          📄 {f.source_filename} ({f.doc_type})
                          {f.line_number > 0 ? ` — Line ${f.line_number}` : ''}
                        </span>
                        {f.line_text && (
                          <span style={S.factLine}>"{f.line_text}"</span>
                        )}
                      </div>
                    ))}
                </>
              )}
            </>
          )}

          {/* Summary for open-ended questions */}
          {smartResult.type === 'summary' && (
            <>
              <div style={S.answerText}>{smartResult.answer}</div>
              {(smartResult.entities || []).slice(0, 15).map((e, i) => (
                <div key={i} style={S.summaryItem}>{e}</div>
              ))}
            </>
          )}

          {/* Empty / not found */}
          {(smartResult.type === 'empty' || smartResult.type === 'not_found') && (
            <div style={{ color: '#E67E22', fontSize: '13px' }}>{smartResult.answer}</div>
          )}

        </div>
      )}
    </div>
  );
};

export default QueryPanel;
