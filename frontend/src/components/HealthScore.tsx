import { HealthScorePayload } from '../types/health';

interface HealthScoreProps {
  data: HealthScorePayload | null;
  error: string | null;
  loading: boolean;
}

const LABEL_COLOR: Record<string, string> = {
  healthy: '#10b981',
  fair:    '#f59e0b',
  'at risk': '#ef4444',
};

const LABEL_BG: Record<string, string> = {
  healthy:  'rgba(16, 185, 129, 0.08)',
  fair:     'rgba(245, 158, 11, 0.08)',
  'at risk': 'rgba(239, 68, 68, 0.08)',
};

const LABEL_BORDER: Record<string, string> = {
  healthy:  'rgba(16, 185, 129, 0.2)',
  fair:     'rgba(245, 158, 11, 0.2)',
  'at risk': 'rgba(239, 68, 68, 0.2)',
};

export function HealthScore({ data, error, loading }: HealthScoreProps) {
  // Loading: hidden — header is already rendered from trends data.
  if (loading) return null;

  // Error: render a subdued unavailable state so layout remains stable.
  if (error || !data) {
    return (
      <div
        style={{
          fontSize: '11px',
          color: '#475569',
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.07)',
          padding: '4px 10px',
          borderRadius: '6px',
        }}
      >
        health unavailable
      </div>
    );
  }

  const color  = LABEL_COLOR[data.label]  ?? '#64748b';
  const bg     = LABEL_BG[data.label]     ?? 'rgba(255,255,255,0.04)';
  const border = LABEL_BORDER[data.label] ?? 'rgba(255,255,255,0.07)';

  return (
    <div
      title={`Based on ${data.contributing_metrics} of ${data.total_metrics} metrics. Provisional score — see individual metric cards for detail.`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        fontSize: '11px',
        color,
        background: bg,
        border: `1px solid ${border}`,
        padding: '4px 10px',
        borderRadius: '6px',
        cursor: 'default',
      }}
    >
      {/* Coloured dot */}
      <div
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          background: color,
          flexShrink: 0,
        }}
      />
      <span style={{ fontWeight: 600 }}>{data.score}</span>
      <span style={{ color: '#64748b' }}>·</span>
      <span>{data.label}</span>
    </div>
  );
}
