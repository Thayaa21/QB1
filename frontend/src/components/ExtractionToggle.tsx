/**
 * ExtractionToggle — switch between LangChain and UiPath extraction modes.
 *
 * Sends POST /extraction/mode when the user toggles.
 * Shows the current active mode with visual feedback.
 */

import React, { useState } from 'react';
import { setExtractionMode } from '../api/client';

interface ExtractionToggleProps {
  currentMode: 'langchain' | 'uipath';
  onModeChange: (mode: 'langchain' | 'uipath') => void;
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display:        'flex',
    alignItems:     'center',
    gap:            '12px',
    padding:        '12px 16px',
    background:     '#1e1e2e',
    borderRadius:   '8px',
    border:         '1px solid #333',
  },
  label: {
    color:      '#aaa',
    fontSize:   '14px',
    fontWeight: 500,
  },
  toggle: {
    display:      'flex',
    gap:          '4px',
    background:   '#2a2a3e',
    borderRadius: '6px',
    padding:      '3px',
  },
  btn: (active: boolean): React.CSSProperties => ({
    padding:      '6px 14px',
    borderRadius: '4px',
    border:       'none',
    cursor:       'pointer',
    fontSize:     '13px',
    fontWeight:   active ? 600 : 400,
    background:   active ? '#4A90D9' : 'transparent',
    color:        active ? 'white' : '#888',
    transition:   'all 0.2s',
  }),
  status: {
    fontSize: '12px',
    color:    '#666',
    marginLeft: 'auto',
  },
};

const ExtractionToggle: React.FC<ExtractionToggleProps> = ({
  currentMode,
  onModeChange,
}) => {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  const handleToggle = async (mode: 'langchain' | 'uipath') => {
    if (mode === currentMode || loading) return;

    setLoading(true);
    setError(null);
    try {
      await setExtractionMode(mode);
      onModeChange(mode);
    } catch (err) {
      setError('Failed to switch mode');
      console.error('Mode switch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <span style={styles.label}>Extraction Mode:</span>
      <div style={styles.toggle}>
        <button
          style={styles.btn(currentMode === 'langchain')}
          onClick={() => handleToggle('langchain')}
          disabled={loading}
          title="LangChain: uses LLM to extract from raw .txt files"
        >
          🧠 LangChain
        </button>
        <button
          style={styles.btn(currentMode === 'uipath')}
          onClick={() => handleToggle('uipath')}
          disabled={loading}
          title="UiPath: parses pre-structured .json files (faster)"
        >
          ⚡ UiPath
        </button>
      </div>
      {loading && <span style={styles.status}>Switching...</span>}
      {error   && <span style={{ ...styles.status, color: '#E74C3C' }}>{error}</span>}
      {!loading && !error && (
        <span style={styles.status}>
          {currentMode === 'langchain'
            ? 'Raw .txt → LLM extracts entities'
            : 'Pre-structured .json → direct parse'}
        </span>
      )}
    </div>
  );
};

export default ExtractionToggle;
