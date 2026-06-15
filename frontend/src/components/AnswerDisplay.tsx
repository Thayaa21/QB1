/**
 * AnswerDisplay — shows the LLM-synthesized answer with metadata.
 */

import React from 'react';
import type { QueryResult } from '../types';

interface AnswerDisplayProps {
  result: QueryResult;
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background:   '#1e1e2e',
    border:       '1px solid #333',
    borderRadius: '8px',
    padding:      '16px',
  },
  question: {
    color:        '#888',
    fontSize:     '13px',
    marginBottom: '8px',
    fontStyle:    'italic',
  },
  answer: {
    color:          '#e8e8e8',
    fontSize:       '15px',
    lineHeight:     1.6,
    whiteSpace:     'pre-wrap',
    background:     '#0d0d1a',
    padding:        '12px',
    borderRadius:   '6px',
    border:         '1px solid #2a2a3e',
  },
  meta: {
    display:    'flex',
    gap:        '16px',
    marginTop:  '12px',
    flexWrap:   'wrap',
  },
  tag: {
    background:   '#2a2a3e',
    color:        '#aaa',
    padding:      '3px 8px',
    borderRadius: '4px',
    fontSize:     '12px',
  },
};

const AnswerDisplay: React.FC<AnswerDisplayProps> = ({ result }) => {
  return (
    <div style={styles.container}>
      <div style={styles.question}>Q: {result.question}</div>
      <div style={styles.answer}>{result.answer}</div>
      <div style={styles.meta}>
        <span style={styles.tag}>🕐 {result.temporal_context}</span>
        <span style={styles.tag}>↔ {result.hops_used} hop(s)</span>
        <span style={styles.tag}>📄 {result.source_documents.length} doc(s)</span>
        <span style={styles.tag}>👥 {result.resolved_entities.length} entities</span>
        {result.has_conflicts && (
          <span style={{ ...styles.tag, background: '#3d1a1a', color: '#E74C3C' }}>
            ⚠ {result.conflicts.length} conflict(s)
          </span>
        )}
      </div>
    </div>
  );
};

export default AnswerDisplay;
