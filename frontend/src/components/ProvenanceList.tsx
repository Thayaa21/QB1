/**
 * ProvenanceList — shows source citations for each fact in the answer.
 *
 * Displays each ProvenanceEntry as:
 *   📄 birth_certificate.txt — Line 5
 *      "Date of Birth: March 15, 1992"
 *      Fact: dob: 1992-03-15
 */

import React, { useState } from 'react';
import type { ProvenanceEntry } from '../types';

interface ProvenanceListProps {
  entries: ProvenanceEntry[];
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
    fontSize:     '15px',
    fontWeight:   600,
    marginBottom: '12px',
    display:      'flex',
    alignItems:   'center',
    gap:          '8px',
  },
  count: {
    background:   '#2a2a3e',
    color:        '#888',
    borderRadius: '10px',
    padding:      '1px 8px',
    fontSize:     '12px',
  },
  entry: {
    borderLeft:   '3px solid #4A90D9',
    paddingLeft:  '10px',
    marginBottom: '10px',
    paddingTop:   '2px',
    paddingBottom: '2px',
  },
  filename: {
    color:      '#4A90D9',
    fontSize:   '13px',
    fontWeight: 600,
  },
  lineInfo: {
    color:    '#666',
    fontSize: '12px',
    marginLeft: '6px',
  },
  lineText: {
    color:      '#aaa',
    fontSize:   '12px',
    fontFamily: 'monospace',
    fontStyle:  'italic',
    marginTop:  '3px',
  },
  fact: {
    color:      '#ddd',
    fontSize:   '13px',
    marginTop:  '2px',
  },
  empty: {
    color:    '#555',
    fontSize: '13px',
    textAlign: 'center' as const,
    padding:  '20px',
  },
  toggleBtn: {
    background:  'none',
    border:      'none',
    color:       '#4A90D9',
    cursor:      'pointer',
    fontSize:    '13px',
    padding:     '4px 0',
    marginTop:   '8px',
  },
};

const ProvenanceList: React.FC<ProvenanceListProps> = ({ entries }) => {
  const [showAll, setShowAll] = useState(false);
  const MAX_SHOW = 8;

  if (entries.length === 0) {
    return (
      <div style={styles.container}>
        <div style={styles.title}>📎 Sources <span style={styles.count}>0</span></div>
        <div style={styles.empty}>No provenance data available</div>
      </div>
    );
  }

  // Deduplicate by fact
  const seen = new Set<string>();
  const unique = entries.filter((e) => {
    if (seen.has(e.fact)) return false;
    seen.add(e.fact);
    return true;
  });

  const displayed = showAll ? unique : unique.slice(0, MAX_SHOW);

  return (
    <div style={styles.container}>
      <div style={styles.title}>
        📎 Sources
        <span style={styles.count}>{unique.length}</span>
      </div>
      {displayed.map((entry, i) => (
        <div key={i} style={styles.entry}>
          <div>
            <span style={styles.filename}>📄 {entry.source_filename}</span>
            {entry.line_number > 0 && (
              <span style={styles.lineInfo}>— Line {entry.line_number}</span>
            )}
          </div>
          {entry.line_text && (
            <div style={styles.lineText}>"{entry.line_text}"</div>
          )}
          <div style={styles.fact}>{entry.fact}</div>
        </div>
      ))}
      {unique.length > MAX_SHOW && (
        <button
          style={styles.toggleBtn}
          onClick={() => setShowAll((s) => !s)}
        >
          {showAll
            ? '▲ Show less'
            : `▼ Show ${unique.length - MAX_SHOW} more...`}
        </button>
      )}
    </div>
  );
};

export default ProvenanceList;
