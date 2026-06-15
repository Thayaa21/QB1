/**
 * EntityTable — displays all entity nodes in the graph as a sortable table.
 *
 * Fetches from GET /entities and displays name, type, doc, confidence.
 */

import React, { useEffect, useState } from 'react';
import { getEntities } from '../api/client';
import type { EntityNode } from '../types';

interface EntityTableProps {
  refreshTrigger?: number;
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background:   '#1e1e2e',
    border:       '1px solid #333',
    borderRadius: '8px',
    padding:      '16px',
    overflowX:    'auto',
  },
  title: {
    color:        '#eee',
    fontSize:     '15px',
    fontWeight:   600,
    marginBottom: '12px',
    display:      'flex',
    gap:          '8px',
    alignItems:   'center',
  },
  count: {
    background:   '#2a2a3e',
    color:        '#888',
    borderRadius: '10px',
    padding:      '1px 8px',
    fontSize:     '12px',
  },
  table: {
    width:           '100%',
    borderCollapse:  'collapse',
    fontSize:        '13px',
  },
  th: {
    background:   '#2a2a3e',
    color:        '#aaa',
    padding:      '8px 12px',
    textAlign:    'left' as const,
    border:       '1px solid #333',
    fontWeight:   600,
    whiteSpace:   'nowrap',
  },
  td: {
    color:   '#ccc',
    padding: '7px 12px',
    border:  '1px solid #2a2a3e',
  },
  badge: (type: string): React.CSSProperties => {
    const colors: Record<string, string> = {
      PERSON:       '#4A90D9',
      ORGANIZATION: '#E74C3C',
      LOCATION:     '#1ABC9C',
      ID_NUMBER:    '#E67E22',
      DATE:         '#9B59B6',
    };
    return {
      background:   colors[type] || '#555',
      color:        'white',
      borderRadius: '3px',
      padding:      '2px 6px',
      fontSize:     '11px',
    };
  },
  empty: {
    color:    '#555',
    fontSize: '13px',
    textAlign: 'center' as const,
    padding:  '20px',
  },
  search: {
    background:   '#0d0d1a',
    color:        '#ddd',
    border:       '1px solid #444',
    borderRadius: '4px',
    padding:      '5px 10px',
    fontSize:     '13px',
    marginBottom: '10px',
    width:        '200px',
  },
};

const EntityTable: React.FC<EntityTableProps> = ({ refreshTrigger = 0 }) => {
  const [entities, setEntities]   = useState<EntityNode[]>([]);
  const [loading,  setLoading]    = useState(false);
  const [filter,   setFilter]     = useState('');

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      try {
        const result = await getEntities();
        setEntities(result.entities);
      } catch (err) {
        console.error('Failed to load entities:', err);
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [refreshTrigger]);

  const filtered = entities.filter(
    (e) =>
      e.name.toLowerCase().includes(filter.toLowerCase()) ||
      e.source_filename.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div style={styles.container}>
      <div style={styles.title}>
        👥 Entities
        <span style={styles.count}>{entities.length}</span>
      </div>
      <input
        style={styles.search}
        placeholder="Filter by name..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      {loading ? (
        <div style={styles.empty}>Loading entities...</div>
      ) : filtered.length === 0 ? (
        <div style={styles.empty}>
          {entities.length === 0
            ? 'No entities yet. Ingest documents first.'
            : 'No entities match the filter.'}
        </div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Name</th>
              <th style={styles.th}>Type</th>
              <th style={styles.th}>Source File</th>
              <th style={styles.th}>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((entity) => (
              <tr key={entity.node_id}>
                <td style={styles.td}>{entity.name}</td>
                <td style={styles.td}>
                  <span style={styles.badge(entity.entity_type)}>
                    {entity.entity_type}
                  </span>
                </td>
                <td style={styles.td}>{entity.source_filename}</td>
                <td style={styles.td}>
                  {(entity.confidence * 100).toFixed(0)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default EntityTable;
