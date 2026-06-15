/**
 * GraphVisualization — embeds the Pyvis-generated HTML graph in an iframe.
 *
 * Fetches the visualization from GET /graph/visualize and renders it
 * in a full-width iframe. Falls back to stats if pyvis is not installed.
 */

import React, { useEffect, useRef, useState } from 'react';
import { getGraphVisualization } from '../api/client';

interface GraphVisualizationProps {
  refreshTrigger?: number;   // increment to re-fetch
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background:   '#1e1e2e',
    border:       '1px solid #333',
    borderRadius: '8px',
    overflow:     'hidden',
  },
  header: {
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    padding:        '12px 16px',
    borderBottom:   '1px solid #333',
  },
  title: {
    color:      '#eee',
    fontSize:   '15px',
    fontWeight: 600,
  },
  refreshBtn: {
    background:   '#2a2a3e',
    color:        '#888',
    border:       '1px solid #444',
    borderRadius: '4px',
    padding:      '4px 10px',
    cursor:       'pointer',
    fontSize:     '12px',
  },
  iframe: {
    width:   '100%',
    height:  '600px',
    border:  'none',
    display: 'block',
  },
  placeholder: {
    height:         '300px',
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'center',
    color:          '#555',
    fontSize:       '14px',
    flexDirection:  'column',
    gap:            '8px',
  },
};

const GraphVisualization: React.FC<GraphVisualizationProps> = ({
  refreshTrigger = 0,
}) => {
  const [htmlContent, setHtmlContent] = useState<string | null>(null);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState<string | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const fetchVisualization = async () => {
    setLoading(true);
    setError(null);
    try {
      const html = await getGraphVisualization();
      setHtmlContent(html);
    } catch (err) {
      setError('Could not load graph visualization');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVisualization();
  }, [refreshTrigger]);

  // Write HTML directly into iframe's srcdoc
  useEffect(() => {
    if (iframeRef.current && htmlContent) {
      const doc = iframeRef.current.contentDocument;
      if (doc) {
        doc.open();
        doc.write(htmlContent);
        doc.close();
      }
    }
  }, [htmlContent]);

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.title}>🕸 Knowledge Graph</span>
        <button
          style={styles.refreshBtn}
          onClick={fetchVisualization}
          disabled={loading}
        >
          {loading ? 'Loading...' : '↺ Refresh'}
        </button>
      </div>

      {loading && (
        <div style={styles.placeholder}>
          <span>Loading graph visualization...</span>
        </div>
      )}

      {error && (
        <div style={styles.placeholder}>
          <span>⚠ {error}</span>
          <span style={{ fontSize: '12px', color: '#444' }}>
            Install pyvis: pip install pyvis
          </span>
        </div>
      )}

      {!loading && !error && htmlContent && (
        <iframe
          ref={iframeRef}
          style={styles.iframe}
          title="Knowledge Graph Visualization"
          sandbox="allow-scripts allow-same-origin"
        />
      )}

      {!loading && !error && !htmlContent && (
        <div style={styles.placeholder}>
          <span>No graph data available</span>
          <span style={{ fontSize: '12px', color: '#444' }}>
            Ingest documents to see the graph
          </span>
        </div>
      )}
    </div>
  );
};

export default GraphVisualization;
