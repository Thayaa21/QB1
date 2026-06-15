/**
 * EntityTable — compact collapsible entity list.
 * Collapsed by default, shows count. Click to expand.
 */

import React, { useEffect, useState } from 'react';
import { getEntities } from '../api/client';
import type { EntityNode } from '../types';

interface EntityTableProps { refreshTrigger?: number; }

const S: Record<string, React.CSSProperties> = {
  container: {
    background:   '#1e1e2e',
    border:       '1px solid #333',
    borderRadius: '8px',
    overflow:     'hidden',
  },
  header: {
    display:        'flex',
    alignItems:     'center',
    gap:            '8px',
    padding:        '10px 14px',
    cursor:         'pointer',
    userSelect:     'none' as const,
    borderBottom:   '1px solid #2a2a3e',
  },
  title:  { color: '#eee', fontSize: '14px', fontWeight: 600, flex: 1 },
  count:  { background: '#2a2a3e', color: '#888', borderRadius: '10px', padding: '1px 8px', fontSize: '12px' },
  chevron: (open: boolean) => ({ color: '#555', fontSize: '12px', transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }),
  body:   { padding: '8px 12px' },
  search: {
    background: '#0d0d1a', color: '#ddd', border: '1px solid #444',
    borderRadius: '4px', padding: '5px 8px', fontSize: '12px',
    width: '100%', marginBottom: '8px', boxSizing: 'border-box' as const,
  },
  scroll: { maxHeight: '180px', overflowY: 'auto' as const },
  row: {
    display: 'flex', alignItems: 'center', gap: '6px',
    padding: '4px 0', borderBottom: '1px solid #1a1a2e', fontSize: '12px',
  },
  name:   { color: '#4A90D9', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const },
  badge: (type: string): React.CSSProperties => {
    const c: Record<string, string> = { PERSON: '#4A90D9', ORGANIZATION: '#E74C3C', LOCATION: '#1ABC9C', ID_NUMBER: '#E67E22', DATE: '#9B59B6' };
    return { background: c[type] || '#555', color: '#fff', borderRadius: '3px', padding: '1px 5px', fontSize: '10px', flexShrink: 0 };
  },
  file:   { color: '#666', fontSize: '10px', flexShrink: 0, maxWidth: '100px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const },
  empty:  { color: '#555', fontSize: '12px', padding: '12px', textAlign: 'center' as const },
};

const EntityTable: React.FC<EntityTableProps> = ({ refreshTrigger = 0 }) => {
  const [entities, setEntities] = useState<EntityNode[]>([]);
  const [loading,  setLoading]  = useState(false);
  const [filter,   setFilter]   = useState('');
  const [open,     setOpen]     = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const r = await getEntities();
        setEntities(r.entities);
      } catch { /* ignore */ }
      setLoading(false);
    };
    load();
  }, [refreshTrigger]);

  const filtered = entities.filter(e =>
    !filter ||
    e.name.toLowerCase().includes(filter.toLowerCase()) ||
    e.source_filename.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div style={S.container}>
      <div style={S.header} onClick={() => setOpen(o => !o)}>
        <span style={S.chevron(open)}>▶</span>
        <span style={S.title}>👥 Entities</span>
        <span style={S.count}>{entities.length}</span>
      </div>

      {open && (
        <div style={S.body}>
          <input
            style={S.search}
            placeholder="Filter..."
            value={filter}
            onChange={e => setFilter(e.target.value)}
            onClick={e => e.stopPropagation()}
          />
          {loading ? (
            <div style={S.empty}>Loading...</div>
          ) : filtered.length === 0 ? (
            <div style={S.empty}>{entities.length === 0 ? 'Ingest documents first.' : 'No match.'}</div>
          ) : (
            <div style={S.scroll}>
              {filtered.map(e => (
                <div key={e.node_id} style={S.row}>
                  <span style={S.name} title={e.name}>{e.name}</span>
                  <span style={S.badge(e.entity_type)}>{e.entity_type}</span>
                  <span style={S.file} title={e.source_filename}>{e.source_filename}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EntityTable;
