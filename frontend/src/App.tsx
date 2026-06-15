/**
 * App — main application component with all panels.
 *
 * Layout:
 *   Header (title + graph stats bar)
 *   Left panel:  Extraction Toggle + Document Upload + Entity Table
 *   Right panel: Query Panel + Answer Display + Provenance List + Conflict Warnings
 *   Bottom:      Graph Visualization
 */

import React, { useCallback, useEffect, useState } from 'react';
import AnswerDisplay        from './components/AnswerDisplay';
import ConflictWarnings     from './components/ConflictWarnings';
import DocumentUpload       from './components/DocumentUpload';
import EntityTable          from './components/EntityTable';
import ExtractionToggle     from './components/ExtractionToggle';
import GraphVisualization   from './components/GraphVisualization';
import ProvenanceList       from './components/ProvenanceList';
import QueryPanel           from './components/QueryPanel';
import { getGraphStats }    from './api/client';
import type { GraphStats, IngestResponse, QueryResult } from './types';

const styles: Record<string, React.CSSProperties> = {
  app: {
    minHeight:    '100vh',
    background:   '#0d0d1a',
    color:        '#eee',
    fontFamily:   '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    padding:      '16px',
    boxSizing:    'border-box',
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
  subtitle: {
    fontSize: '14px',
    color:    '#555',
    marginTop: '2px',
  },
  statsBar: {
    display:      'flex',
    gap:          '12px',
    flexWrap:     'wrap',
  },
  statPill: {
    background:   '#1e1e2e',
    border:       '1px solid #333',
    borderRadius: '16px',
    padding:      '4px 12px',
    fontSize:     '12px',
    color:        '#aaa',
  },
  grid: {
    display:      'grid',
    gridTemplate: 'auto / 1fr 1fr',
    gap:          '16px',
    marginBottom: '16px',
  },
  column: {
    display:       'flex',
    flexDirection: 'column',
    gap:           '16px',
  },
};

const App: React.FC = () => {
  const [extractionMode, setExtractionMode] = useState<'langchain' | 'uipath'>('langchain');
  const [queryResult,    setQueryResult]    = useState<QueryResult | null>(null);
  const [stats,          setStats]          = useState<GraphStats | null>(null);
  const [refreshCount,   setRefreshCount]   = useState(0);

  const refreshStats = useCallback(async () => {
    try {
      const s = await getGraphStats();
      setStats(s);
    } catch {
      // API might not be running yet
    }
  }, []);

  useEffect(() => {
    refreshStats();
    const interval = setInterval(refreshStats, 10_000);
    return () => clearInterval(interval);
  }, [refreshStats]);

  const handleIngestComplete = (_result: IngestResponse) => {
    refreshStats();
    setRefreshCount((c) => c + 1);
  };

  const handleQueryResult = (result: QueryResult) => {
    setQueryResult(result);
  };

  return (
    <div style={styles.app}>
      {/* ---- Header ---- */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>🕸 Graph RAG</h1>
          <div style={styles.subtitle}>Knowledge Graph Question Answering</div>
        </div>
        {stats && (
          <div style={styles.statsBar}>
            <span style={styles.statPill}>📄 {stats.documents} docs</span>
            <span style={styles.statPill}>👥 {stats.entities} entities</span>
            <span style={styles.statPill}>↔ {stats.same_as_edges} links</span>
            {stats.conflict_edges > 0 && (
              <span style={{ ...styles.statPill, color: '#E74C3C', borderColor: '#E74C3C' }}>
                ⚠ {stats.conflict_edges} conflicts
              </span>
            )}
          </div>
        )}
      </div>

      {/* ---- Two-column grid ---- */}
      <div style={styles.grid}>
        {/* Left column: ingestion */}
        <div style={styles.column}>
          <ExtractionToggle
            currentMode={extractionMode}
            onModeChange={setExtractionMode}
          />
          <DocumentUpload
            extractionMode={extractionMode}
            onIngestComplete={handleIngestComplete}
          />
          <EntityTable refreshTrigger={refreshCount} />
        </div>

        {/* Right column: query + results */}
        <div style={styles.column}>
          <QueryPanel onResult={handleQueryResult} />
          {queryResult && (
            <>
              <AnswerDisplay result={queryResult} />
              {queryResult.has_conflicts && (
                <ConflictWarnings conflicts={queryResult.conflicts} />
              )}
              <ProvenanceList entries={queryResult.provenance} />
            </>
          )}
        </div>
      </div>

      {/* ---- Full-width graph visualization ---- */}
      <GraphVisualization refreshTrigger={refreshCount} />
    </div>
  );
};

export default App;
