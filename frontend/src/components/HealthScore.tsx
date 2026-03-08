import { HealthScorePayload } from '../types/health';

interface HealthScoreProps {
  data: HealthScorePayload | null;
  error: string | null;
  loading: boolean;
  activeAlerts?: number;
  worsening?: number;
  improving?: number;
  /** When true, suppresses the component's own border/padding (parent column provides chrome). */
  inlined?: boolean;
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

function Indicator({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
      <span style={{ fontSize: '18px', fontWeight: 700, color, lineHeight: 1, letterSpacing: '-0.02em' }}>
        {value}
      </span>
      <span style={{ fontSize: '10px', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </span>
    </div>
  );
}

export function HealthScore({ data, error, loading, activeAlerts, worsening, improving, inlined }: HealthScoreProps) {
  return (
    <div
      style={inlined ? {} : {
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
          marginBottom: '28px',
        }}
      >
        <h2
          style={{
            fontSize: '12px',
            fontWeight: 700,
            color: '#f1f5f9',
            textTransform: 'uppercase',
            letterSpacing: '0.09em',
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

        const summary =
          data.label === 'healthy'
            ? 'Portfolio is in good shape across tracked metrics.'
            : data.label === 'fair'
            ? 'Some metrics need attention — review amber signals below.'
            : 'Several metrics are below target and require action.';

        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Score row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <span style={{ fontSize: '58px', fontWeight: 700, color, lineHeight: 1, letterSpacing: '-0.03em' }}>
                {data.score}
              </span>
              <span style={{ fontSize: '20px', color: '#334155', lineHeight: 1 }}>/</span>
              <span style={{ fontSize: '20px', fontWeight: 600, color: '#475569', lineHeight: 1 }}>100</span>
              <span
                style={{
                  fontSize: '11px', fontWeight: 700, color,
                  background: bg, border: `1px solid ${border}`,
                  padding: '3px 10px', borderRadius: '10px',
                  textTransform: 'uppercase', letterSpacing: '0.06em',
                }}
              >
                {data.label}
              </span>
              <span style={{ fontSize: '11px', color: '#334155', marginLeft: '4px' }}>
                {data.contributing_metrics} of {data.total_metrics} metrics
              </span>
            </div>

            {/* Explanatory sentence */}
            <p style={{ fontSize: '12px', color: '#64748b', margin: 0 }}>{summary}</p>

            {/* Summary indicators */}
            <div style={{ display: 'flex', gap: '24px' }}>
              <Indicator
                label="Active alerts"
                value={activeAlerts ?? '—'}
                color={activeAlerts != null && activeAlerts > 0 ? '#ef4444' : '#475569'}
              />
              <Indicator
                label="Worsening"
                value={worsening ?? '—'}
                color={worsening != null && worsening > 0 ? '#f59e0b' : '#475569'}
              />
              <Indicator
                label="Improving"
                value={improving ?? '—'}
                color={improving != null && improving > 0 ? '#10b981' : '#475569'}
              />
            </div>
          </div>
        );
      })()}
    </div>
  );
}
