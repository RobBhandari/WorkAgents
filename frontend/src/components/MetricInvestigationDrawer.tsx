import { useEffect } from 'react';
import { AlertItem } from '../types/trends';
import { DrawerTarget } from '../utils/buildDrawerTarget';

export type { DrawerTarget } from '../utils/buildDrawerTarget';

// Maps domainKey to the alert dashboard key used in AlertItem.dashboard
const DOMAIN_TO_ALERT_KEY: Record<string, string> = {
  infrastructure: 'security',
  delivery:       'deployment',
};

// ── Visual sub-components ─────────────────────────────────────────────────────

function MiniSparkBars({ data }: { data: number[] }) {
  const pts = data.slice(-10);
  if (pts.length < 2) return <span style={{ fontSize: '11px', color: '#475569' }}>No trend data</span>;

  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const range = max - min || 1;
  const MIN_H = 8;
  const MAX_H = 36;

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: '40px' }}>
      {pts.map((v, i) => {
        const h = MIN_H + ((v - min) / range) * (MAX_H - MIN_H);
        const isLast = i === pts.length - 1;
        return (
          <div
            key={i}
            style={{
              flex: 1,
              height: `${Math.round(h)}px`,
              background: isLast
                ? 'linear-gradient(to top, rgba(14,165,233,0.90), rgba(103,232,249,0.90))'
                : 'linear-gradient(to top, rgba(14,165,233,0.28), rgba(103,232,249,0.28))',
              borderRadius: '3px',
            }}
          />
        );
      })}
    </div>
  );
}

const SECTION_DIVIDER: React.CSSProperties = {
  borderTop: '1px solid rgba(255,255,255,0.06)',
  paddingTop: '16px',
  marginTop: '16px',
};

const LABEL_STYLE: React.CSSProperties = {
  fontSize: '10px',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.18em',
  color: '#475569',
  marginBottom: '8px',
};

const MOVEMENT_COLORS = {
  up:   '#fca5a5',
  down: '#6ee7b7',
  flat: '#64748b',
};

const INTENSITY_LABELS: Record<string, string> = {
  high:     'High pressure',
  moderate: 'Moderate pressure',
  low:      'Low activity',
};

const CONFIDENCE_LABELS: Record<string, string> = {
  high:     'High confidence',
  moderate: 'Moderate confidence',
  low:      'Low confidence',
};

// ── Main component ────────────────────────────────────────────────────────────

interface MetricInvestigationDrawerProps {
  target: DrawerTarget;
  alerts: AlertItem[];
  onClose: () => void;
}

export function MetricInvestigationDrawer({ target, alerts, onClose }: MetricInvestigationDrawerProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const { kind, metric, movement, implication, evidence, relatedSignals, dispatch } = target;
  const isMetric = kind === 'metric';

  // Alert context: look up by domainKey or its alert-key equivalent
  const alertKey = DOMAIN_TO_ALERT_KEY[target.domainKey] ?? target.domainKey;
  const domainAlerts = alerts.filter((a) => a.dashboard === alertKey);
  const alertLine =
    domainAlerts.length === 0
      ? null
      : domainAlerts.length === 1
        ? `Referenced by 1 active alert: "${domainAlerts[0].message.length > 70
            ? domainAlerts[0].message.slice(0, 70) + '…'
            : domainAlerts[0].message}"`
        : `Referenced by ${domainAlerts.length} active alerts across ${new Set(domainAlerts.map((a) => a.project_name)).size} products.`;

  const movementColor = MOVEMENT_COLORS[movement.direction];

  function scrollToMetric(id: string) {
    const el = document.querySelector(`[data-metric-id="${id}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      onClose();
    }
  }

  return (
    <>
      {/* Overlay */}
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.40)', zIndex: 50 }}
      />

      {/* Drawer */}
      <div
        style={{
          position: 'fixed',
          right: 0,
          top: 0,
          height: '100%',
          width: '440px',
          background: '#0f172a',
          borderLeft: '1px solid rgba(255,255,255,0.08)',
          padding: '24px',
          zIndex: 51,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 0,
        }}
      >
        {/* ── Header ── */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
          <div style={{ minWidth: 0 }}>
            <div style={LABEL_STYLE}>{isMetric ? 'Metric investigation' : 'Domain briefing'}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {isMetric && metric && (
                <span style={{ fontSize: '14px', lineHeight: 1 }}>{metric.icon}</span>
              )}
              <span style={{ fontSize: '20px', fontWeight: 600, color: '#f1f5f9', letterSpacing: '-0.01em' }}>
                {target.label}
              </span>
            </div>
            {/* Headline claim */}
            <p style={{ marginTop: '6px', fontSize: '13px', color: '#94a3b8', lineHeight: 1.5, margin: '6px 0 0' }}>
              {target.headline}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: '1px solid rgba(255,255,255,0.10)',
              borderRadius: '8px',
              color: '#64748b',
              cursor: 'pointer',
              fontSize: '14px',
              padding: '4px 10px',
              flexShrink: 0,
              lineHeight: 1.4,
            }}
          >
            ✕
          </button>
        </div>

        {/* ── Metric mode: current value + trend chip + spark bars ── */}
        {isMetric && metric && metric.current !== '' && (
          <>
            <div style={{ marginTop: '20px' }}>
              <div style={LABEL_STYLE}>Current value</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{
                  fontSize: '48px', fontWeight: 600, letterSpacing: '-0.04em',
                  color: metric.ragColor ?? '#f1f5f9', lineHeight: 1,
                }}>
                  {metric.current === '' || metric.current === null ? '—'
                    : typeof metric.current === 'number'
                      ? metric.current.toLocaleString(undefined, { maximumFractionDigits: 1 })
                      : String(metric.current)}
                </span>
                {metric.unit && (
                  <span style={{ fontSize: '14px', color: '#94a3b8' }}>{metric.unit}</span>
                )}
              </div>
            </div>

            {metric.data && metric.data.length >= 2 && (
              <div style={SECTION_DIVIDER}>
                <div style={LABEL_STYLE}>Recent shape (10 readings)</div>
                <MiniSparkBars data={metric.data} />
                <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#334155' }}>
                  <span>oldest</span>
                  <span>latest</span>
                </div>
              </div>
            )}
          </>
        )}

        {/* ── Movement ── */}
        <div style={SECTION_DIVIDER}>
          <div style={LABEL_STYLE}>Movement</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            {/* Direction chip */}
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: '4px',
              background: `${movementColor}14`,
              border: `1px solid ${movementColor}28`,
              borderRadius: '9999px',
              padding: '3px 10px',
              fontSize: '12px', fontWeight: 700, color: movementColor,
            }}>
              {movement.direction === 'up' ? '↑' : movement.direction === 'down' ? '↓' : '→'}
              {isMetric && metric && metric.change !== '' && typeof metric.change === 'number'
                ? ` ${metric.change > 0 ? '+' : ''}${metric.change.toLocaleString(undefined, { maximumFractionDigits: 1 })}`
                : ` ${movement.direction}`}
            </span>
            {movement.intensity && (
              <span style={{ fontSize: '11px', color: '#475569' }}>
                {INTENSITY_LABELS[movement.intensity]}
              </span>
            )}
            {movement.windowLabel && isMetric && (
              <span style={{ fontSize: '11px', color: '#475569' }}>{movement.windowLabel}</span>
            )}
          </div>
          {!isMetric && (
            <p style={{ marginTop: '8px', fontSize: '13px', color: '#94a3b8', lineHeight: 1.6, margin: '8px 0 0' }}>
              {movement.summary}
            </p>
          )}
        </div>

        {/* ── Implication (Why this matters) ── */}
        <div style={SECTION_DIVIDER}>
          <div style={LABEL_STYLE}>Why this matters</div>
          <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.6, margin: 0 }}>
            {implication.headline}
          </p>
          {implication.detail && (
            <p style={{ marginTop: '6px', fontSize: '12px', color: '#475569', lineHeight: 1.6, margin: '6px 0 0' }}>
              {implication.detail}
            </p>
          )}
        </div>

        {/* ── Evidence (domain mode only) ── */}
        {!isMetric && evidence && (
          <div style={SECTION_DIVIDER}>
            <div style={LABEL_STYLE}>Signal evidence</div>
            {/* Attribution summary prose */}
            <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.6, margin: '0 0 8px' }}>
              {evidence.attributionSummary}
            </p>
            {/* Meta pills: contributor count + confidence */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              <span style={{
                fontSize: '11px', color: '#64748b',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: '9999px', padding: '2px 8px',
              }}>
                {evidence.contributorCount} contributor{evidence.contributorCount !== 1 ? 's' : ''}
              </span>
              <span style={{
                fontSize: '11px',
                color: evidence.confidence === 'high' ? '#6ee7b7' : evidence.confidence === 'moderate' ? '#fcd34d' : '#94a3b8',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: '9999px', padding: '2px 8px',
              }}>
                {CONFIDENCE_LABELS[evidence.confidence]}
              </span>
            </div>
          </div>
        )}

        {/* ── Related signals with scroll-to ── */}
        {relatedSignals.length > 0 && (
          <div style={SECTION_DIVIDER}>
            <div style={LABEL_STYLE}>Related signals</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {relatedSignals.map((s) => (
                <button
                  key={s.id}
                  onClick={() => scrollToMetric(s.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '8px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    borderRadius: '10px',
                    padding: '7px 10px',
                    cursor: 'pointer',
                    textAlign: 'left',
                    color: 'inherit',
                    width: '100%',
                  }}
                >
                  <span style={{ fontSize: '12px', color: '#94a3b8' }}>{s.label}</span>
                  {s.direction && s.direction !== 'flat' && (
                    <span style={{
                      fontSize: '11px',
                      flexShrink: 0,
                      color: s.direction === 'up' ? '#fca5a5' : '#6ee7b7',
                    }}>
                      {s.direction === 'up' ? '↑ rising' : '↓ falling'}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Alert context ── */}
        {alertLine && (
          <div style={SECTION_DIVIDER}>
            <div style={LABEL_STYLE}>Alert context</div>
            <p style={{ fontSize: '12px', color: '#64748b', lineHeight: 1.6, margin: 0 }}>
              {alertLine}
            </p>
          </div>
        )}

        {/* ── Launch CTA ── */}
        {dispatch.url && (
          <div style={{ ...SECTION_DIVIDER, marginTop: 'auto', paddingTop: '20px' }}>
            <a
              href={dispatch.url}
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'block',
                textAlign: 'center',
                padding: '10px 16px',
                background: isMetric && metric
                  ? `${metric.ragColor}14`
                  : 'rgba(56,189,248,0.10)',
                border: `1px solid ${isMetric && metric ? `${metric.ragColor}35` : 'rgba(56,189,248,0.22)'}`,
                borderRadius: '12px',
                fontSize: '13px',
                fontWeight: 600,
                color: isMetric && metric ? metric.ragColor : '#7dd3fc',
                textDecoration: 'none',
              }}
            >
              {dispatch.label}
            </a>
          </div>
        )}
      </div>
    </>
  );
}
