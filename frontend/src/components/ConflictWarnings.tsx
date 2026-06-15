/**
 * ConflictWarnings — displays data contradictions detected in the graph.
 *
 * Critical conflicts (DOB, name, ID numbers) are shown in red.
 * Minor conflicts (address, phone) are shown in yellow.
 */

import React from 'react';
import type { ConflictRecord } from '../types';

interface ConflictWarningsProps {
  conflicts: ConflictRecord[];
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background:   '#1e1e2e',
    border:       '1px solid #E74C3C',
    borderRadius: '8px',
    padding:      '16px',
  },
  title: {
    color:        '#E74C3C',
    fontSize:     '15px',
    fontWeight:   600,
    marginBottom: '12px',
  },
  conflict: (severity: string): React.CSSProperties => ({
    background:   severity === 'critical' ? '#2d0f0f' : '#2d2a0f',
    border:       `1px solid ${severity === 'critical' ? '#E74C3C' : '#E67E22'}`,
    borderRadius: '6px',
    padding:      '10px 12px',
    marginBottom: '10px',
  }),
  header: {
    display:    'flex',
    alignItems: 'center',
    gap:        '8px',
    marginBottom: '6px',
  },
  severityBadge: (severity: string): React.CSSProperties => ({
    background:   severity === 'critical' ? '#E74C3C' : '#E67E22',
    color:        'white',
    borderRadius: '3px',
    padding:      '2px 6px',
    fontSize:     '11px',
    fontWeight:   700,
    textTransform: 'uppercase' as const,
  }),
  conflictType: {
    color:      '#eee',
    fontSize:   '13px',
    fontWeight: 600,
  },
  row: {
    color:      '#ccc',
    fontSize:   '12px',
    fontFamily: 'monospace',
    marginTop:  '4px',
  },
  docName: {
    color: '#888',
  },
  value: {
    color:      '#eee',
    fontWeight: 600,
  },
};

const ConflictWarnings: React.FC<ConflictWarningsProps> = ({ conflicts }) => {
  if (conflicts.length === 0) return null;

  return (
    <div style={styles.container}>
      <div style={styles.title}>⚠ Data Conflicts Detected</div>
      {conflicts.map((c, i) => (
        <div key={i} style={styles.conflict(c.severity)}>
          <div style={styles.header}>
            <span style={styles.severityBadge(c.severity)}>{c.severity}</span>
            <span style={styles.conflictType}>{c.conflict_type}</span>
          </div>
          <div style={styles.row}>
            <span style={styles.docName}>{c.source_doc_a}: </span>
            <span style={styles.value}>"{c.value_a}"</span>
          </div>
          <div style={styles.row}>
            <span style={styles.docName}>{c.source_doc_b}: </span>
            <span style={styles.value}>"{c.value_b}"</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default ConflictWarnings;
