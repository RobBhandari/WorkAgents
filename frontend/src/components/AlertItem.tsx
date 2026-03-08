import { useState } from 'react';
import { AlertItem as AlertItemType } from '../types/trends';
import { alertSignalMap } from '../config/alertSignalMap';

interface AlertItemProps {
  alert: AlertItemType;
}

const SEVERITY_BG: Record<string, string> = {
  critical: 'rgba(239, 68, 68, 0.06)',
  warn: 'rgba(99, 102, 241, 0.06)',
  medium: 'rgba(245, 158, 11, 0.06)',
};

const SEVERITY_BORDER: Record<string, string> = {
  critical: 'rgba(239, 68, 68, 0.2)',
  warn: 'rgba(99, 102, 241, 0.2)',
  medium: 'rgba(245, 158, 11, 0.2)',
};

function scrollToMetric(metricId: string, e: React.MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
  const el = document.querySelector(`[data-metric-id="${metricId}"]`);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

export function AlertItem({ alert }: AlertItemProps) {
  const [expanded, setExpanded] = useState(false);
  const signals = (alertSignalMap[alert.dashboard] ?? []).slice(0, 4);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        padding: '10px 12px',
        background: SEVERITY_BG[alert.severity] ?? 'transparent',
        borderBottom: `1px solid ${SEVERITY_BORDER[alert.severity] ?? 'rgba(255,255,255,0.05)'}`,
        borderRadius: '6px',
        marginBottom: '4px',
      }}
    >
      <span style={{ fontSize: '14px', lineHeight: '20px', flexShrink: 0 }}>{alert.severity_emoji}</span>
      <div style={{ minWidth: 0, width: '100%' }}>
        <div style={{ fontSize: '12px', color: '#f1f5f9', lineHeight: 1.4, wordBreak: 'break-word' }}>
          {alert.message}
        </div>
        <div style={{ marginTop: '3px', display: 'flex', gap: '8px', fontSize: '11px', color: '#475569' }}>
          <span>{alert.dashboard}</span>
          <span>·</span>
          <span>{alert.metric_date}</span>
        </div>

        {signals.length > 0 && (
          <div style={{ marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '6px' }}>
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '11px',
                color: '#475569',
              }}
            >
              <span style={{ fontSize: '9px' }}>{expanded ? '▾' : '▸'}</span>
              <span>Signals contributing ({signals.length})</span>
            </button>

            {expanded && (
              <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                {signals.map((sig) => (
                  <button
                    key={sig.id}
                    onClick={(e) => scrollToMetric(sig.id, e)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: '2px 0',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontSize: '11px',
                      color: '#64748b',
                      textAlign: 'left',
                    }}
                  >
                    <span style={{ color: sig.direction === 'up' ? '#f87171' : '#94a3b8', fontWeight: 700, lineHeight: 1 }}>
                      {sig.direction === 'up' ? '↑' : '↓'}
                    </span>
                    <span>{sig.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
