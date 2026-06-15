/**
 * ExplorePanel — explore households and conflicts interactively.
 *
 * Two tabs:
 *   🏠 Households — people sharing the same address
 *   ⚠  Conflicts  — data mismatches between linked entities
 *
 * Click any entity to drill down into its full profile.
 */

import React, { useEffect, useState } from 'react';
import { API_BASE } from '../api/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HouseholdMember { name: string; doc_type: string; source_file: string; entity_id: string; }
interface Household { address: string; member_count: number; members: HouseholdMember[]; }

interface ConflictEntity {
  entity_id: string; name: string; doc_type: string; source_file: string;
  value: string; line_number: number; line_text: string;
  attributes: Record<string, string>;
}
interface Conflict {
  conflict_type: string; attribute_key: string; severity: string;
  entity_a: ConflictEntity; entity_b: ConflictEntity;
}

interface EntityDetail {
  entity_id: string; name: string; entity_type: string; doc_type: string;
  source_filename: string; confidence: number;
  attributes: Record<string, string>;
  source_documents: { filename: string; doc_type: string; line_number: number; line_text: string }[];
  same_as_links:    { entity_id: string; name: string; doc_type: string; confidence: number }[];
  conflict_links:   { entity_id: string; name: string; conflict_type: string; attribute_key: string; value_a: string; value_b: string; severity: string }[];
  lives_with_links: { entity_id: string; name: string; doc_type: string; address: string }[];
}

interface Props { refreshTrigger?: number; }

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const S: Record<string, React.CSSProperties> = {
  container: { background: '#1e1e2e', border: '1px solid #333', borderRadius: '10px', padding: '16px' },
  tabs:      { display: 'flex', gap: '8px', marginBottom: '14px' },
  tab:       (active: boolean) => ({
    padding: '6px 16px', borderRadius: '6px', cursor: 'pointer', fontSize: '13px',
    fontWeight: 600, border: 'none',
    background: active ? '#4A90D9' : '#12121f',
    color:      active ? '#fff' : '#888',
  }),
  card: { background: '#12121f', border: '1px solid #2a2a3e', borderRadius: '8px', padding: '12px', marginBottom: '8px', cursor: 'pointer' },
  cardTitle:   { fontSize: '13px', fontWeight: 700, color: '#eee', marginBottom: '4px' },
  cardMeta:    { fontSize: '11px', color: '#666' },
  badge: (color: string) => ({
    display: 'inline-block', padding: '2px 8px', borderRadius: '10px',
    background: color, color: '#fff', fontSize: '10px', fontWeight: 700, marginRight: '4px',
  }),
  memberRow: { display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 0', borderBottom: '1px solid #1a1a2e', fontSize: '12px' },
  memberName: { color: '#4A90D9', fontWeight: 600, cursor: 'pointer', flex: 1 },
  memberDoc:  { color: '#888', fontSize: '11px' },
  conflictCard: (severity: string) => ({
    background: severity === 'critical' ? '#1a0808' : '#12121f',
    border:     `1px solid ${severity === 'critical' ? '#E74C3C' : '#555'}`,
    borderRadius: '8px', padding: '12px', marginBottom: '8px',
  }),
  conflictTitle: { fontSize: '13px', fontWeight: 700, color: '#eee', marginBottom: '8px' },
  conflictRow:   { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' },
  conflictSide: (color: string) => ({
    background: '#0d0d1a', borderRadius: '6px', padding: '8px',
    borderLeft: `3px solid ${color}`,
  }),
  sideTitle:   { fontSize: '11px', color: '#888', marginBottom: '4px' },
  sideValue:   { fontSize: '14px', color: '#eee', fontWeight: 700, marginBottom: '2px' },
  sideFile:    { fontSize: '10px', color: '#666' },
  sideLine:    { fontSize: '11px', color: '#888', fontStyle: 'italic', marginTop: '4px', borderLeft: '2px solid #333', paddingLeft: '6px' },
  // Entity detail drawer
  drawer: { position: 'fixed' as const, right: 0, top: 0, bottom: 0, width: '380px', background: '#0d0d1a', borderLeft: '1px solid #333', overflowY: 'auto' as const, zIndex: 1000, padding: '16px' },
  drawerTitle: { fontSize: '18px', fontWeight: 700, color: '#4A90D9', marginBottom: '4px' },
  drawerClose: { position: 'absolute' as const, right: '16px', top: '16px', background: 'none', border: 'none', color: '#888', fontSize: '20px', cursor: 'pointer' },
  section:     { marginTop: '14px' },
  sectionTitle:{ fontSize: '12px', fontWeight: 700, color: '#4A90D9', marginBottom: '6px', textTransform: 'uppercase' as const, letterSpacing: '0.5px' },
  attrRow:     { display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #1a1a2e', fontSize: '12px' },
  attrKey:     { color: '#888' },
  attrVal:     { color: '#eee', fontWeight: 600 },
  linkRow:     { padding: '6px 8px', background: '#12121f', borderRadius: '4px', marginBottom: '4px', fontSize: '12px', cursor: 'pointer', border: '1px solid #2a2a3e' },
  linkName:    { color: '#4A90D9', fontWeight: 600 },
  linkMeta:    { color: '#888', fontSize: '11px' },
  empty:       { color: '#555', fontSize: '12px', padding: '20px', textAlign: 'center' as const },
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const ExplorePanel: React.FC<Props> = ({ refreshTrigger = 0 }) => {
  const [activeTab, setActiveTab]       = useState<'households' | 'conflicts'>('households');
  const [households, setHouseholds]     = useState<Household[]>([]);
  const [conflicts,  setConflicts]      = useState<Conflict[]>([]);
  const [loading,    setLoading]        = useState(false);
  const [resolving,  setResolving]      = useState(false);
  const [selectedEntity, setSelected]   = useState<EntityDetail | null>(null);
  const [expandedCards, setExpanded]    = useState<Set<number>>(new Set());

  const resolve = async () => {
    setResolving(true);
    try {
      await fetch(`${API_BASE}/explore/resolve`, { method: 'POST' });
      // Poll until same_as_edges stabilize
      let prev = -1;
      let stable = 0;
      for (let i = 0; i < 30; i++) {
        await new Promise(r => setTimeout(r, 2000));
        const r = await fetch(`${API_BASE}/graph/stats`);
        const stats = await r.json();
        const current = stats.same_as_edges || 0;
        if (current === prev) {
          stable++;
          if (stable >= 2) break; // stable for 2 polls = done
        } else {
          stable = 0;
        }
        prev = current;
      }
      await load(activeTab);
    } catch { /* ignore */ }
    setResolving(false);
  };

  const load = async (tab: 'households' | 'conflicts') => {
    setLoading(true);
    try {
      if (tab === 'households') {
        const r = await fetch(`${API_BASE}/explore/households`);
        const d = await r.json();
        setHouseholds(d.households || []);
      } else {
        const r = await fetch(`${API_BASE}/explore/conflicts`);
        const d = await r.json();
        setConflicts(d.conflicts || []);
      }
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { load(activeTab); }, [activeTab, refreshTrigger]);

  const openEntity = async (entity_id: string) => {
    try {
      const r = await fetch(`${API_BASE}/explore/entity/${entity_id}`);
      const d = await r.json();
      setSelected(d);
    } catch { /* ignore */ }
  };

  const toggleCard = (i: number) =>
    setExpanded(prev => { const n = new Set(prev); n.has(i) ? n.delete(i) : n.add(i); return n; });

  return (
    <div style={S.container}>
      <div style={{ fontSize: '15px', fontWeight: 700, color: '#eee', marginBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        🔎 Explore Graph
        <button
          style={{ padding: '4px 12px', background: resolving ? '#555' : '#9B59B6', border: 'none', borderRadius: '5px', color: '#fff', fontSize: '11px', cursor: resolving ? 'default' : 'pointer', fontWeight: 600 }}
          onClick={resolve}
          disabled={resolving}
          title="Run entity resolution + conflict detection"
        >
          {resolving ? '⏳ Resolving...' : '🔄 Run Resolution'}
        </button>
      </div>

      <div style={S.tabs}>
        <button style={S.tab(activeTab === 'households')} onClick={() => setActiveTab('households')}>
          🏠 Households {households.length > 0 && `(${households.length})`}
        </button>
        <button style={S.tab(activeTab === 'conflicts')} onClick={() => setActiveTab('conflicts')}>
          ⚠ Conflicts {conflicts.length > 0 && `(${conflicts.length})`}
        </button>
      </div>

      {loading && <div style={S.empty}>Loading...</div>}

      {/* Households Tab */}
      {!loading && activeTab === 'households' && (
        households.length === 0
          ? <div style={S.empty}>No same-address matches found.<br/>Ingest documents with address fields first.</div>
          : households.map((h, i) => (
            <div key={i} style={S.card} onClick={() => toggleCard(i)}>
              <div style={S.cardTitle}>
                🏠 {h.address}
                <span style={S.badge('#4A90D9')}>{h.member_count} people</span>
              </div>
              {expandedCards.has(i) && (
                <div style={{ marginTop: '8px' }}>
                  {h.members.map((m, j) => (
                    <div key={j} style={S.memberRow}>
                      <span style={S.memberName} onClick={e => { e.stopPropagation(); openEntity(m.entity_id); }}>
                        👤 {m.name}
                      </span>
                      <span style={S.memberDoc}>{m.doc_type}</span>
                      <span style={{ ...S.memberDoc, color: '#555' }}>{m.source_file}</span>
                    </div>
                  ))}
                </div>
              )}
              {!expandedCards.has(i) && (
                <div style={S.cardMeta}>
                  {h.members.map(m => m.name).join(' · ')}
                </div>
              )}
            </div>
          ))
      )}

      {/* Conflicts Tab */}
      {!loading && activeTab === 'conflicts' && (
        conflicts.length === 0
          ? <div style={S.empty}>No conflicts detected.<br/>Conflicts appear when the same person has different values in different documents.<br/><br/>
              <button style={{ padding: '6px 14px', background: '#9B59B6', border: 'none', borderRadius: '5px', color: '#fff', cursor: 'pointer', fontSize: '12px' }} onClick={resolve}>
                🔄 Run Resolution to detect conflicts
              </button>
            </div>
          : conflicts.map((c, i) => (
            <div key={i} style={S.conflictCard(c.severity)} onClick={() => toggleCard(i)}>
              <div style={S.conflictTitle}>
                <span style={S.badge(c.severity === 'critical' ? '#E74C3C' : '#E67E22')}>
                  {c.severity.toUpperCase()}
                </span>
                {c.conflict_type.replace(/_/g, ' ')} — <span style={{ color: '#4A90D9' }}>{c.attribute_key}</span>
                <span style={{ float: 'right', color: '#555', fontSize: '11px' }}>{expandedCards.has(i) ? '▲ collapse' : '▼ details'}</span>
              </div>

              {/* Always-visible: the conflicting values */}
              <div style={S.conflictRow}>
                <div style={S.conflictSide('#4A90D9')}>
                  <div style={S.sideTitle}>
                    <span style={{ ...S.memberName, fontSize: '12px' }}
                          onClick={e => { e.stopPropagation(); openEntity(c.entity_a.entity_id); }}>
                      👤 {c.entity_a.name}
                    </span>
                  </div>
                  <div style={S.sideValue}>{c.entity_a.value}</div>
                  <div style={S.sideFile}>📄 {c.entity_a.source_file} ({c.entity_a.doc_type})</div>
                  {c.entity_a.line_text && (
                    <div style={S.sideLine}>"{c.entity_a.line_text}"</div>
                  )}
                </div>

                <div style={S.conflictSide('#E74C3C')}>
                  <div style={S.sideTitle}>
                    <span style={{ ...S.memberName, fontSize: '12px' }}
                          onClick={e => { e.stopPropagation(); openEntity(c.entity_b.entity_id); }}>
                      👤 {c.entity_b.name}
                    </span>
                  </div>
                  <div style={S.sideValue}>{c.entity_b.value}</div>
                  <div style={S.sideFile}>📄 {c.entity_b.source_file} ({c.entity_b.doc_type})</div>
                  {c.entity_b.line_text && (
                    <div style={S.sideLine}>"{c.entity_b.line_text}"</div>
                  )}
                </div>
              </div>

              {/* Expanded: full attribute comparison */}
              {expandedCards.has(i) && (
                <div style={{ marginTop: '10px' }}>
                  <div style={{ fontSize: '11px', color: '#888', marginBottom: '6px', fontWeight: 700 }}>
                    📊 Full Attribute Comparison
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr 1fr', gap: '2px', fontSize: '11px' }}>
                    <div style={{ color: '#555', fontWeight: 700, padding: '3px' }}>Field</div>
                    <div style={{ color: '#4A90D9', fontWeight: 700, padding: '3px' }}>📄 {c.entity_a.source_file}</div>
                    <div style={{ color: '#E74C3C', fontWeight: 700, padding: '3px' }}>📄 {c.entity_b.source_file}</div>
                    {/* Show all fields from both entities */}
                    {Array.from(new Set([
                      ...Object.keys(c.entity_a.attributes || {}),
                      ...Object.keys(c.entity_b.attributes || {}),
                    ])).filter(k => !k.startsWith('_')).map(field => {
                      const va = (c.entity_a.attributes || {})[field] || '—';
                      const vb = (c.entity_b.attributes || {})[field] || '—';
                      const isConflict = field === c.attribute_key;
                      return (
                        <React.Fragment key={field}>
                          <div style={{ padding: '3px', color: isConflict ? '#E67E22' : '#666',
                                        fontWeight: isConflict ? 700 : 400,
                                        borderBottom: '1px solid #1a1a2e' }}>
                            {field}
                          </div>
                          <div style={{ padding: '3px', color: isConflict ? '#fff' : '#aaa',
                                        background: isConflict ? '#0d1a2e' : 'transparent',
                                        borderBottom: '1px solid #1a1a2e' }}>
                            {va}
                          </div>
                          <div style={{ padding: '3px', color: isConflict ? '#fff' : '#aaa',
                                        background: isConflict ? '#1a0d0d' : 'transparent',
                                        borderBottom: '1px solid #1a1a2e' }}>
                            {vb}
                          </div>
                        </React.Fragment>
                      );
                    })}
                  </div>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '6px' }}>
                    <button style={{ padding: '4px 10px', background: '#4A90D9', border: 'none', borderRadius: '4px', color: '#fff', fontSize: '11px', cursor: 'pointer' }}
                            onClick={e => { e.stopPropagation(); openEntity(c.entity_a.entity_id); }}>
                      View {c.entity_a.name} full profile
                    </button>
                    <button style={{ padding: '4px 10px', background: '#E74C3C', border: 'none', borderRadius: '4px', color: '#fff', fontSize: '11px', cursor: 'pointer' }}
                            onClick={e => { e.stopPropagation(); openEntity(c.entity_b.entity_id); }}>
                      View {c.entity_b.name} full profile
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
      )}

      {/* Entity Detail Drawer */}
      {selectedEntity && (
        <div style={S.drawer}>
          <button style={S.drawerClose} onClick={() => setSelected(null)}>✕</button>
          <div style={S.drawerTitle}>{selectedEntity.name}</div>
          <div style={{ fontSize: '11px', color: '#888', marginBottom: '8px' }}>
            {selectedEntity.doc_type} · {selectedEntity.source_filename} · conf: {(selectedEntity.confidence * 100).toFixed(0)}%
          </div>

          {/* Attributes */}
          <div style={S.section}>
            <div style={S.sectionTitle}>Attributes</div>
            {Object.entries(selectedEntity.attributes).map(([k, v]) => (
              <div key={k} style={S.attrRow}>
                <span style={S.attrKey}>{k}</span>
                <span style={S.attrVal}>{v}</span>
              </div>
            ))}
          </div>

          {/* Source documents */}
          {selectedEntity.source_documents.length > 0 && (
            <div style={S.section}>
              <div style={S.sectionTitle}>Source Documents</div>
              {selectedEntity.source_documents.map((d, i) => (
                <div key={i} style={S.linkRow}>
                  <div style={S.linkName}>📄 {d.filename}</div>
                  <div style={S.linkMeta}>{d.doc_type}{d.line_number > 0 ? ` · Line ${d.line_number}` : ''}</div>
                  {d.line_text && <div style={{ ...S.linkMeta, fontStyle: 'italic', marginTop: '2px' }}>"{d.line_text}"</div>}
                </div>
              ))}
            </div>
          )}

          {/* Same-as links */}
          {selectedEntity.same_as_links.length > 0 && (
            <div style={S.section}>
              <div style={S.sectionTitle}>Same Person In</div>
              {selectedEntity.same_as_links.map((l, i) => (
                <div key={i} style={S.linkRow} onClick={() => openEntity(l.entity_id)}>
                  <div style={S.linkName}>🔗 {l.name}</div>
                  <div style={S.linkMeta}>{l.doc_type} · {(l.confidence * 100).toFixed(0)}% confidence</div>
                </div>
              ))}
            </div>
          )}

          {/* Conflicts */}
          {selectedEntity.conflict_links.length > 0 && (
            <div style={S.section}>
              <div style={S.sectionTitle}>⚠ Conflicts</div>
              {selectedEntity.conflict_links.map((c, i) => (
                <div key={i} style={{ ...S.linkRow, borderLeft: '3px solid #E74C3C' }}>
                  <div style={{ color: '#E74C3C', fontWeight: 700, fontSize: '12px' }}>
                    {c.conflict_type} ({c.severity})
                  </div>
                  <div style={S.linkMeta}>{c.attribute_key}: {c.value_a} vs {c.value_b}</div>
                </div>
              ))}
            </div>
          )}

          {/* Lives-with links */}
          {selectedEntity.lives_with_links.length > 0 && (
            <div style={S.section}>
              <div style={S.sectionTitle}>🏠 Household Members</div>
              {selectedEntity.lives_with_links.map((l, i) => (
                <div key={i} style={S.linkRow} onClick={() => openEntity(l.entity_id)}>
                  <div style={S.linkName}>👤 {l.name}</div>
                  <div style={S.linkMeta}>{l.doc_type} · {l.address}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ExplorePanel;
