import { MetricItem, AlertItem } from '../types/trends';
import { buildAnomalyRiver, ALERT_DOMAIN_TO_RIVER_DOMAIN } from '../utils/buildAnomalyRiver';
import { DrawerTarget, buildDomainTarget } from '../utils/buildDrawerTarget';

// More descriptive display label when a domain row is backed by only one metric.
const PROXY_ROW_LABELS: Record<string, string> = {
  Infrastructure: 'Infrastructure vulnerability pressure',
  Quality:        'Open bug pressure',
  Security:       'Exploitable vulnerability pressure',
};

// Maps the AnomalyRiver row domain (capitalised) to the WHY_IT_MATTERS / alert domain key.
const ROW_DOMAIN_TO_KEY: Record<string, string> = {
  Security:       'security',
  Infrastructure: 'infrastructure',
  Delivery:       'deployment',
  Quality:        'bugs',
  Collaboration:  'collaboration',
  Ownership:      'ownership',
};

interface AnomalyRiverProps {
  metrics: MetricItem[];
  alerts?: AlertItem[];
  onDomainClick?: (target: DrawerTarget) => void;
}

export function AnomalyRiver({ metrics, alerts = [], onDomainClick }: AnomalyRiverProps) {
  const rows = buildAnomalyRiver(metrics);
  const metricMap = new Map(metrics.map((m) => [m.id, m]));

  if (rows.length === 0) return null;

  // Derive spotlight label from most-alerted domain — plain editorial text, no decoration
  const alertDomainCounts = new Map<string, number>();
  for (const a of alerts) {
    const d = a.dashboard || 'other';
    alertDomainCounts.set(d, (alertDomainCounts.get(d) ?? 0) + 1);
  }
  const topAlertDomain = [...alertDomainCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  const spotlightTitle = topAlertDomain
    ? (ALERT_DOMAIN_TO_RIVER_DOMAIN[topAlertDomain] ?? topAlertDomain.replace(/\b\w/g, (c) => c.toUpperCase())) + ' pressure'
    : null;

  return (
    <section
      style={{
        borderRadius: '28px',
        border: '1px solid rgba(255,255,255,0.10)',
        background: '#0b1626',
        padding: '24px',
      }}
    >
      {/* Header — reference: flex items-end justify-between gap-4 */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '16px' }}>
        <div>
          {/* Eyebrow — reference: text-xs uppercase tracking-[0.24em] text-slate-400 */}
          <div
            style={{
              fontSize: '10px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.24em',
              color: '#94a3b8',
            }}
          >
            Temporal anomaly map
          </div>
          {/* Title — reference: mt-2 text-2xl font-semibold */}
          <h2
            style={{
              margin: '8px 0 0',
              fontSize: '24px',
              fontWeight: 600,
              color: '#f1f5f9',
              letterSpacing: '-0.01em',
            }}
          >
            Anomaly river
          </h2>
        </div>
        {/* Spotlight — reference: text-sm text-slate-400 — plain editorial text only */}
        {spotlightTitle && (
          <div style={{ fontSize: '14px', color: '#64748b', flexShrink: 0 }}>
            Current spotlight: {spotlightTitle}
          </div>
        )}
      </div>

      {/* Domain rows — reference: mt-5 space-y-4 */}
      <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {rows.map((row) => {
          const intervalCount = row.values.length;
          const isProxy = row.metricIds.length === 1;
          const displayLabel = isProxy
            ? (PROXY_ROW_LABELS[row.domain] ?? row.domain)
            : row.domain;

          const domainKey = ROW_DOMAIN_TO_KEY[row.domain] ?? row.domain.toLowerCase();

          function handleClick() {
            if (!onDomainClick) return;
            onDomainClick(buildDomainTarget(row, displayLabel, domainKey, metrics));
          }

          return (
            <div
              key={row.domain}
              onClick={onDomainClick ? handleClick : undefined}
              style={{ cursor: onDomainClick ? 'pointer' : 'default' }}
            >
              {/* Label row — reference: mb-2 flex items-center justify-between text-sm */}
              <div
                style={{
                  marginBottom: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '14px',
                }}
              >
                {/* Domain name — proxy rows get a more descriptive editorial label */}
                <span style={{ fontWeight: 500, color: '#e2e8f0' }}>{displayLabel}</span>
                {/* Interval count — reference: text-slate-500 */}
                <span style={{ color: '#64748b' }}>{intervalCount} interval{intervalCount !== 1 ? 's' : ''}</span>
              </div>

              {/* Bar lane — reference: flex h-16 items-center gap-1 rounded-2xl border border-white/10 bg-white/[0.03] px-2 */}
              <div
                style={{
                  display: 'flex',
                  height: '64px',
                  alignItems: 'center',
                  gap: '4px',
                  borderRadius: '16px',
                  border: '1px solid rgba(255,255,255,0.10)',
                  background: 'rgba(255,255,255,0.03)',
                  padding: '0 8px',
                }}
              >
                {row.values.map((v, i) => {
                  // Reference: scaleY: Math.max(v / 84, 0.2) on h-full bars
                  // Our values are 0–1 normalised; lower floor lets quiet periods read as near-flat
                  const scaleY = Math.max(v, 0.05);

                  return (
                    <div
                      key={i}
                      style={{
                        flex: 1,
                        height: '100%',
                        borderRadius: '10px',
                        transformOrigin: 'bottom',
                        transform: `scaleY(${scaleY.toFixed(3)})`,
                        // Reference gradient: from-fuchsia-500/30 via-sky-400/40 to-cyan-300/60
                        background:
                          'linear-gradient(to top, rgba(217,70,239,0.30), rgba(56,189,248,0.40), rgba(103,232,249,0.60))',
                        transition: 'transform 0.3s ease',
                      }}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
