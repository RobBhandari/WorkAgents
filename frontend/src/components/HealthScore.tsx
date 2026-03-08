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

function Chip({ label, value, color, bg, border }: {
  label: string;
  value: number | string;
  color: string;
  bg: string;
  border: string;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '5px 10px',
        background: bg,
        border: `1px solid ${border}`,
        borderRadius: '8px',
      }}
    >
      <span style={{ fontSize: '14px', fontWeight: 700, color, lineHeight: 1, letterSpacing: '-0.02em' }}>
        {value}
      </span>
      <span style={{ fontSize: '10px', color: '#334155', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
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
          marginBottom: '24px',
        }}
      >
        <h2
          style={{
            fontSize: '11px',
            fontWeight: 600,
            color: '#475569',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            {/* Score row */}
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '14px' }}>
              <span style={{ fontSize: '80px', fontWeight: 800, color, lineHeight: 1, letterSpacing: '-0.04em' }}>
                {data.score}
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', paddingBottom: '10px' }}>
                <span
                  style={{
                    fontSize: '11px', fontWeight: 700, color,
                    background: bg, border: `1px solid ${border}`,
                    padding: '3px 10px', borderRadius: '10px',
                    textTransform: 'uppercase', letterSpacing: '0.07em',
                    alignSelf: 'flex-start',
                  }}
                >
                  {data.label}
                </span>
                <span style={{ fontSize: '11px', color: '#334155' }}>
                  {data.contributing_metrics} of {data.total_metrics} metrics contributing
                </span>
              </div>
            </div>

            {/* Interpretation */}
            <p style={{ fontSize: '13px', color: '#475569', margin: 0, lineHeight: 1.5, maxWidth: '380px' }}>{summary}</p>

            {/* Status chips */}
            <div style={{ display: 'flex', gap: '10px' }}>
              <Chip
                label="Active alerts"
                value={activeAlerts ?? '—'}
                color={activeAlerts != null && activeAlerts > 0 ? '#ef4444' : '#334155'}
                bg={activeAlerts != null && activeAlerts > 0 ? 'rgba(239,68,68,0.08)' : 'rgba(255,255,255,0.03)'}
                border={activeAlerts != null && activeAlerts > 0 ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.06)'}
              />
              <Chip
                label="Worsening"
                value={worsening ?? '—'}
                color={worsening != null && worsening > 0 ? '#f59e0b' : '#334155'}
                bg={worsening != null && worsening > 0 ? 'rgba(245,158,11,0.08)' : 'rgba(255,255,255,0.03)'}
                border={worsening != null && worsening > 0 ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.06)'}
              />
              <Chip
                label="Improving"
                value={improving ?? '—'}
                color={improving != null && improving > 0 ? '#10b981' : '#334155'}
                bg={improving != null && improving > 0 ? 'rgba(16,185,129,0.08)' : 'rgba(255,255,255,0.03)'}
                border={improving != null && improving > 0 ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.06)'}
              />
            </div>
          </div>
        );
      })()}
    </div>
  );
}
