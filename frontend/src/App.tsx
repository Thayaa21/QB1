/**
 * App — main application component.
 *
 * Layout:
 *   Header (title + graph stats bar)
 *   Left:  Extraction Toggle + Upload + Test Dataset Panel + Entity Table
 *   Right: Query Panel + Answer + Provenance + Conflicts
 *   Bottom: Graph Visualization
 */

import React, { useCallback, useEffect, useState } from 'react';
import AnswerDisplay      from './components/AnswerDisplay';
import ConflictWarnings   from './components/ConflictWarnings';
import DocumentUpload     from './components/DocumentUpload';
import EntityTable        from './components/EntityTable';
import ExtractionToggle   from './components/ExtractionToggle';
import GraphVisualization from './components/GraphVisualization';
import ProvenanceList     from './components/ProvenanceList';
import QueryPanel         from './components/QueryPanel';
import TestDatasetPanel   from './components/TestDatasetPanel';
import UiPathLivePanel    from './components/UiPathLivePanel';
import PersonalUploadPanel from './components/PersonalUploadPanel';
import ExplorePanel        from './components/ExplorePanel';
import { getGraphStats, resetGraph } from './api/client';
import type { GraphStats, IngestResponse, QueryResult } from './types';

const S: Record<string, React.CSSProperties> = {
  app: {
    minHeight:  '100vh',
    background: '#0d0d1a',
    color:      '#eee',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    padding:    '16px',
    boxSizing:  'border-box',
  },
  header: {
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    marginBottom:   '16px',
    flexWrap:       'wrap',
    gap:            '8px',
  },
  title: {
    fontSize:   '24px',
    fontWeight: 700,
    color:      '#4A90D9',
    margin:     0,
  },
  subtitle: { fontSize: '13px', color: '#555', marginTop: '2px' },
  statsBar:  { display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' },
  statPill: {
    background:   '#1e1e2e',
    border:       '1px solid #333',
    borderRadius: '16px',
    padding:      '4px 12px',
    fontSize:     '12px',
    color:        '#aaa',
  },
  resetBtn: {
    padding:      '4px 12px',
    background:   'transparent',
    border:       '1px solid #E74C3C',
    borderRadius: '16px',
    color:        '#E74C3C',
    fontSize:     '12px',
    cursor:       'pointer',
  },
  grid: {
    display:      'grid',
    gridTemplate: 'auto / 1fr 1fr',
    gap:          '16px',
    marginBottom: '16px',
  },
  col: { display: 'flex', flexDirection: 'column', gap: '14px' },
};

const App: React.FC = () => {
  const [extractionMode, setExtractionMode] = useState<'langchain' | 'uipath'>('langchain');
  const [queryResult,    setQueryResult]    = useState<QueryResult | null>(null);
  const [stats,          setStats]          = useState<GraphStats | null>(null);
  const [refreshCount,   setRefreshCount]   = useState(0);

  const refreshStats = useCallback(async () => {
    try { setStats(await getGraphStats()); } catch { /* API not ready */ }
  }, []);

  useEffect(() => {
    refreshStats();
    const t = setInterval(refreshStats, 8_000);
    return () => clearInterval(t);
  }, [refreshStats]);

  const handleIngest = (_r: IngestResponse) => {
    refreshStats();
    setRefreshCount(c => c + 1);
  };

  const handleReset = async () => {
    if (!window.confirm('Reset the knowledge graph? All ingested data will be lost.')) return;
    await resetGraph();
    setQueryResult(null);
    setRefreshCount(c => c + 1);
    refreshStats();
  };

  return (
    <div style={S.app}>
      {/* ---- Header ---- */}
      <div style={S.header}>
        <div>
          <h1 style={S.title}>🕸 Graph RAG</h1>
          <div style={S.subtitle}>Cross-document Knowledge Graph · Question Answering</div>
        </div>

        <div style={S.statsBar}>
          {stats ? (
            <>
              <span style={S.statPill}>📄 {stats.documents} docs</span>
              <span style={S.statPill}>👥 {stats.entities} entities</span>
              <span style={S.statPill}>↔ {stats.same_as_edges} links</span>
              {stats.conflict_edges > 0 && (
                <span style={{ ...S.statPill, color: '#E74C3C', borderColor: '#E74C3C' }}>
                  ⚠ {stats.conflict_edges} conflicts
                </span>
              )}
              <button style={S.resetBtn} onClick={handleReset}>Reset Graph</button>
            </>
          ) : (
            <span style={{ ...S.statPill, color: '#E74C3C' }}>⚠ API not connected</span>
          )}
        </div>
      </div>

      {/* ---- Two-column grid ---- */}
      <div style={S.grid}>
        {/* Left: ingestion */}
        <div style={S.col}>
          <ExtractionToggle
            currentMode={extractionMode}
            onModeChange={setExtractionMode}
          />
          <DocumentUpload
            extractionMode={extractionMode}
            onIngestComplete={handleIngest}
          />
          <TestDatasetPanel
            extractionMode={extractionMode}
            onIngestComplete={handleIngest}
          />
          <UiPathLivePanel onIngestComplete={handleIngest} />
          <PersonalUploadPanel onComplete={handleIngest} />
          <EntityTable refreshTrigger={refreshCount} />
        </div>

        {/* Right: query + results */}
        <div style={S.col}>
          <QueryPanel onResult={() => {}} />
          {/* Results are shown inline in QueryPanel now */}
        </div>
      </div>

      {/* ---- Graph visualization ---- */}
      <GraphVisualization refreshTrigger={refreshCount} />

      {/* ---- Explore: Households + Conflicts ---- */}
      <ExplorePanel refreshTrigger={refreshCount} />
    </div>
  );
};

export default App;
