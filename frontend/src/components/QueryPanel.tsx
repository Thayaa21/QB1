/**
 * QueryPanel — the question input form.
 *
 * Allows setting max hops and temporal context,
 * then calls POST /query and returns the result.
 */

import React, { useState } from 'react';
import { queryGraph } from '../api/client';
import type { QueryResult } from '../types';

interface QueryPanelProps {
  onResult: (result: QueryResult) => void;
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
  input: {
    width:        '100%',
    padding:      '10px',
    background:   '#0d0d1a',
    color:        '#ddd',
    border:       '1px solid #444',
    borderRadius: '4px',
    fontSize:     '14px',
    boxSizing:    'border-box',
  },
  row: {
    display:    'flex',
    gap:        '12px',
    marginTop:  '10px',
    alignItems: 'center',
    flexWrap:   'wrap',
  },
  label: {
    color:    '#888',
    fontSize: '13px',
    display:  'flex',
    alignItems: 'center',
    gap:      '6px',
  },
  select: {
    background:   '#0d0d1a',
    color:        '#ddd',
    border:       '1px solid #444',
    borderRadius: '4px',
    padding:      '4px 8px',
    fontSize:     '13px',
  },
  button: {
    marginLeft:   'auto',
    padding:      '8px 24px',
    background:   '#27AE60',
    color:        'white',
    border:       'none',
    borderRadius: '5px',
    cursor:       'pointer',
    fontSize:     '14px',
    fontWeight:   600,
  },
  error: {
    marginTop:    '10px',
    color:        '#E74C3C',
    fontSize:     '13px',
  },
};

const QueryPanel: React.FC<QueryPanelProps> = ({ onResult }) => {
  const [question,        setQuestion]        = useState('');
  const [maxHops,         setMaxHops]         = useState(3);
  const [temporalContext, setTemporalContext] = useState('current');
  const [loading,         setLoading]         = useState(false);
  const [error,           setError]           = useState<string | null>(null);

  const handleQuery = async () => {
    if (!question.trim()) {
      setError('Please enter a question.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await queryGraph(question, maxHops, temporalContext);
      onResult(result);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Query failed. Is the API running?');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.title}>🔍 Ask a Question</div>
      <input
        style={styles.input}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="e.g. What is Alice Chen's date of birth?"
      />
      <div style={styles.row}>
        <label style={styles.label}>
          Hops:
          <select
            style={styles.select}
            value={maxHops}
            onChange={(e) => setMaxHops(Number(e.target.value))}
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
        <label style={styles.label}>
          Temporal:
          <select
            style={styles.select}
            value={temporalContext}
            onChange={(e) => setTemporalContext(e.target.value)}
          >
            <option value="current">current</option>
            <option value="all">all</option>
          </select>
        </label>
        <button
          style={{ ...styles.button, opacity: loading ? 0.7 : 1 }}
          onClick={handleQuery}
          disabled={loading}
        >
          {loading ? 'Querying...' : 'Ask'}
        </button>
      </div>
      {error && <div style={styles.error}>✗ {error}</div>}
    </div>
  );
};

export default QueryPanel;
