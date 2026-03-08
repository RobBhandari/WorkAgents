import { Signal, SignalsPayload } from '../types/signals';

interface SignalsPanelProps {
  data: SignalsPayload | null;
  error: string | null;
  loading: boolean;
  /** When true, suppresses the component's own border/padding (parent column provides chrome). */
  inlined?: boolean;
}

const SEVERITY_COLOR: Record<string, string> = {
  critical: '#ef4444',
  warning: '#f59e0b',
  info:    '#6366f1',
};

const SEVERITY_BG: Record<string, string> = {
  critical: 'rgba(239, 68, 68, 0.08)',
  warning:  'rgba(245, 158, 11, 0.08)',
  info:     'rgba(99, 102, 241, 0.08)',
};

const SEVERITY_BORDER: Record<string, string> = {
  critical: 'rgba(239, 68, 68, 0.2)',
  warning:  'rgba(245, 158, 11, 0.2)',
  info:     'rgba(99, 102, 241, 0.2)',
};

const TYPE_LABEL: Record<string, string> = {
  threshold_breach:        'threshold',
  sustained_deterioration: 'deteriorating',
  recovery_trend:          'recovering',
};

function SignalRow({ signal }: { signal: Signal }) {
  const color  = SEVERITY_COLOR[signal.severity] ?? '#64748b';
  const bg     = SEVERITY_BG[signal.severity]    ?? 'transparent';
  const border = SEVERITY_BORDER[signal.severity] ?? 'rgba(255,255,255,0.06)';
  const typeLabel = TYPE_LABEL[signal.type] ?? signal.type;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        padding: '10px 14px',
        background: bg,
        border: `1px solid ${border}`,
        borderRadius: '8px',
        minWidth: 0,
      }}
    >
      {/* Severity dot */}
      <div
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: color,
          flexShrink: 0,
          marginTop: '5px',
        }}
      />

      <div style={{ minWidth: 0, flex: 1 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '2px',
          }}
        >
          <span style={{ fontSize: '12px', fontWeight: 600, color: '#f1f5f9' }}>
            {signal.title}
          </span>
          <span
            style={{
              fontSize: '10px',
              fontWeight: 600,
              color: color,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              flexShrink: 0,
            }}
          >
            {signal.severity}
          </span>
        </div>
        <div style={{ fontSize: '11px', color: '#94a3b8', lineHeight: 1.5 }}>
          {signal.message}
        </div>
        {signal.type === 'recovery_trend' && (
          <div style={{ marginTop: '4px', fontSize: '10px', color: '#10b981' }}>
            Trending better
          </div>
        )}
        {signal.type === 'sustained_deterioration' && (
          <div style={{ marginTop: '4px', fontSize: '10px', color: SEVERITY_COLOR[signal.severity] ?? '#64748b' }}>
            Trending worse
          </div>
        )}
      </div>
    </div>
  );
}

export function SignalsPanel({ data, error, loading, inlined }: SignalsPanelProps) {
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
          marginBottom: '14px',
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
          Key Signals
        </h2>
        {data && data.signal_count > 0 && (() => {
          const topSeverity = data.signals[0]?.severity ?? 'info';
          const badgeColor = SEVERITY_COLOR[topSeverity] ?? '#64748b';
          const badgeBg = SEVERITY_BG[topSeverity] ?? 'transparent';
          const badgeBorder = SEVERITY_BORDER[topSeverity] ?? 'rgba(255,255,255,0.06)';
          return (
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color: badgeColor,
                background: badgeBg,
                border: `1px solid ${badgeBorder}`,
                padding: '2px 8px',
                borderRadius: '10px',
              }}
            >
              {data.signal_count} signal{data.signal_count !== 1 ? 's' : ''}
            </span>
          );
        })()}
        {data && data.signal_count === 0 && (
          <span style={{ fontSize: '11px', color: '#334155' }}>0 signals</span>
        )}
      </div>

      {/* States */}
      {loading && (
        <p style={{ fontSize: '12px', color: '#94a3b8', margin: 0, fontStyle: 'italic' }}>
          Evaluating signals&hellip;
        </p>
      )}

      {!loading && error && (
        <p style={{ fontSize: '12px', color: '#f59e0b', margin: 0 }}>
          Signal data unavailable — check back shortly or reload the page.
        </p>
      )}

      {!loading && !error && data && data.signal_count === 0 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '12px',
            color: '#475569',
          }}
        >
          <span style={{ color: '#10b981', fontSize: '14px' }}>&#10003;</span>
          No active signals — all monitored metrics within normal range.
        </div>
      )}

      {!loading && !error && data && data.signal_count > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: '8px',
          }}
        >
          {data.signals.map((signal) => (
            <SignalRow key={signal.id} signal={signal} />
          ))}
        </div>
      )}
    </div>
  );
}
