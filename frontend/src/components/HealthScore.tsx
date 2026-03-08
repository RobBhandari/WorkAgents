import { HealthScorePayload } from '../types/health';

interface HealthScoreProps {
  data: HealthScorePayload | null;
  error: string | null;
  loading: boolean;
}

const LABEL_COLOR: Record<string, string> = {
  healthy:   '#10b981',
  fair:      '#f59e0b',
  'at risk': '#ef4444',
};

const LABEL_BG: Record<string, string> = {
  healthy:   'rgba(16, 185, 129, 0.08)',
  fair:      'rgba(245, 158, 11, 0.08)',
  'at risk': 'rgba(239, 68, 68, 0.08)',
};

const LABEL_BORDER: Record<string, string> = {
  healthy:   'rgba(16, 185, 129, 0.2)',
  fair:      'rgba(245, 158, 11, 0.2)',
  'at risk': 'rgba(239, 68, 68, 0.2)',
};

export function HealthScore({ data, error, loading }: HealthScoreProps) {
  return (
    <div
      style={{
        borderTop: '1px solid rgba(255,255,255,0.06)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        padding: '20px 32px',
        background: '#111827',
      }}
    >
      {/* Panel header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '14px',
        }}
      >
        <h2
          style={{
            fontSize: '13px',
            fontWeight: 600,
            color: '#94a3b8',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          Engineering Health
        </h2>
      </div>

      {/* Loading */}
      {loading && (
        <p style={{ fontSize: '12px', color: '#94a3b8', margin: 0, fontStyle: 'italic' }}>
          Evaluating health&hellip;
        </p>
      )}

      {/* Error */}
      {!loading && (error || !data) && (
        <p style={{ fontSize: '12px', color: '#f59e0b', margin: 0 }}>
          Health data unavailable — check back shortly or reload the page.
        </p>
      )}

      {/* Score */}
      {!loading && !error && data && (() => {
        const color  = LABEL_COLOR[data.label]  ?? '#64748b';
        const bg     = LABEL_BG[data.label]     ?? 'rgba(255,255,255,0.04)';
        const border = LABEL_BORDER[data.label] ?? 'rgba(255,255,255,0.07)';

        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {/* Score number */}
            <span
              style={{
                fontSize: '32px',
                fontWeight: 700,
                color,
                lineHeight: 1,
                letterSpacing: '-0.02em',
              }}
            >
              {data.score}
            </span>

            {/* Divider */}
            <span style={{ fontSize: '20px', color: '#334155', lineHeight: 1 }}>/</span>

            {/* Out of 100 */}
            <span style={{ fontSize: '20px', fontWeight: 600, color: '#475569', lineHeight: 1 }}>
              100
            </span>

            {/* Label badge */}
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color,
                background: bg,
                border: `1px solid ${border}`,
                padding: '3px 10px',
                borderRadius: '10px',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}
            >
              {data.label}
            </span>

            {/* Coverage note */}
            <span style={{ fontSize: '11px', color: '#334155', marginLeft: '4px' }}>
              {data.contributing_metrics} of {data.total_metrics} metrics
            </span>
          </div>
        );
      })()}
    </div>
  );
}
