import { AlertItem } from '../types/trends';

interface ActiveRisksSummaryProps {
  alerts: AlertItem[];
  horizontal?: boolean;
}

const SEVERITY_WEIGHT: Record<string, number> = { critical: 3, warn: 2, medium: 1 };

// Exact badge styles from reference severityBadge()
const SEVERITY_BADGE_COLOR: Record<string, string> = {
  critical: '#fca5a5',   // text-red-200
  warn:     '#fdba74',   // text-orange-300
  medium:   '#fcd34d',   // text-amber-300
};
const SEVERITY_BADGE_BG: Record<string, string> = {
  critical: 'rgba(239,68,68,0.10)',
  warn:     'rgba(251,146,60,0.10)',
  medium:   'rgba(245,158,11,0.10)',
};
const SEVERITY_BORDER_COLOR: Record<string, string> = {
  critical: 'rgba(239,68,68,0.15)',
  warn:     'rgba(251,146,60,0.15)',
  medium:   'rgba(245,158,11,0.15)',
};
const SEVERITY_TOP_BORDER: Record<string, string> = {
  critical: '#ef4444',
  warn:     '#fb923c',
  medium:   '#f59e0b',
};

const SEVERITY_LABEL: Record<string, string> = {
  critical: 'Critical',
  warn:     'High',
  medium:   'Medium',
};

function formatDomain(domain: string): string {
  return domain.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

interface RiskBlock {
  domain: string;
  topSeverity: string;
  alertCount: number;
  products: string[];
  topAlert: AlertItem;
  weight: number;
}

function buildRiskBlocks(alerts: AlertItem[]): RiskBlock[] {
  const domainMap = new Map<string, AlertItem[]>();
  for (const alert of alerts) {
    const domain = alert.dashboard || 'other';
    if (!domainMap.has(domain)) domainMap.set(domain, []);
    domainMap.get(domain)!.push(alert);
  }
  const SEV_ORDER = ['critical', 'warn', 'medium'];
  const blocks: RiskBlock[] = [];
  for (const [domain, items] of domainMap.entries()) {
    const weight = items.reduce((sum, a) => sum + (SEVERITY_WEIGHT[a.severity] ?? 0), 0);
    const products = [...new Set(items.map((a) => a.project_name).filter(Boolean))];
    const topSeverity = SEV_ORDER.find((s) => items.some((a) => a.severity === s)) ?? 'medium';
    const topAlert = items.find((a) => a.severity === topSeverity) ?? items[0];
    blocks.push({ domain, topSeverity, alertCount: items.length, products, topAlert, weight });
  }
  return blocks.sort((a, b) => b.weight - a.weight).slice(0, 3);
}

export function ActiveRisksSummary({ alerts, horizontal }: ActiveRisksSummaryProps) {
  if (alerts.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: '#94a3b8', padding: '8px 0' }}>
        <span style={{ color: '#34d399' }}>✓</span>
        No active risks detected across monitored domains.
      </div>
    );
  }

  const blocks = buildRiskBlocks(alerts);

  if (!horizontal) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {blocks.map((block) => {
          const color = SEVERITY_TOP_BORDER[block.topSeverity] ?? '#64748b';
          const bg    = SEVERITY_BADGE_BG[block.topSeverity]   ?? 'rgba(255,255,255,0.04)';
          const border = SEVERITY_BORDER_COLOR[block.topSeverity] ?? 'rgba(255,255,255,0.07)';
          const label  = SEVERITY_LABEL[block.topSeverity]  ?? block.topSeverity;
          return (
            <div key={block.domain} style={{ padding: '14px 16px', background: bg, border: `1px solid ${border}`, borderLeft: `3px solid ${color}`, borderRadius: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ fontSize: '14px', fontWeight: 600, color: '#f1f5f9' }}>{formatDomain(block.domain)}</span>
                <span style={{ fontSize: '11px', fontWeight: 700, color, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
              </div>
              <div style={{ fontSize: '12px', color: '#94a3b8' }}>{block.alertCount} alert{block.alertCount !== 1 ? 's' : ''} · {block.products.length} product{block.products.length !== 1 ? 's' : ''} affected</div>
            </div>
          );
        })}
      </div>
    );
  }

  // ── Horizontal editorial briefing cards — matching reference AlertRail card anatomy ──
  // Reference: rounded-[24px] border p-5; active: bg-red-400/10 border-red-300/35; inactive: bg-white/5 border-white/10
  // Card anatomy: badge (rounded-full px-2.5 py-1 text-xs) / title (mt-4 text-lg font-medium) / headline (mt-1 text-sm font-medium text-slate-100) / body (mt-3 text-sm leading-6 text-slate-300) / footer (mt-4 text-sm text-slate-300)
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
      {blocks.map((block, idx) => {
        const badgeColor  = SEVERITY_BADGE_COLOR[block.topSeverity] ?? '#cbd5e1';
        const badgeBg     = SEVERITY_BADGE_BG[block.topSeverity]    ?? 'rgba(255,255,255,0.04)';
        const topBorder   = SEVERITY_TOP_BORDER[block.topSeverity]  ?? '#64748b';
        const borderColor = SEVERITY_BORDER_COLOR[block.topSeverity] ?? 'rgba(255,255,255,0.10)';
        const label       = SEVERITY_LABEL[block.topSeverity] ?? block.topSeverity;

        // Key stat — metric_name + count like reference headline
        const headline = block.topAlert.metric_name
          ? `${block.alertCount} alert${block.alertCount !== 1 ? 's' : ''} on ${block.topAlert.metric_name}`
          : `${block.alertCount} active alert${block.alertCount !== 1 ? 's' : ''}`;

        // Body from root_cause_hint or message
        const body = block.topAlert.root_cause_hint || block.topAlert.message || '';

        // Products footer
        const visibleProducts = block.products.slice(0, 3);
        const hiddenCount = block.products.length - visibleProducts.length;

        // First card richer — reference active state
        const isFirst = idx === 0;

        return (
          <div
            key={block.domain}
            style={{
              borderRadius: '24px',
              border: `1px solid ${isFirst ? `${topBorder}38` : borderColor}`,
              borderTop: `2px solid ${topBorder}`,
              background: isFirst ? `${badgeBg}` : 'rgba(255,255,255,0.05)',
              padding: '20px',
              display: 'flex',
              flexDirection: 'column',
              minHeight: '240px',
            }}
          >
            {/* Badge row — rounded-full px-2.5 py-1 text-xs font-medium */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{
                borderRadius: '9999px',
                background: badgeBg,
                padding: '4px 10px',
                fontSize: '12px', fontWeight: 500, color: badgeColor,
              }}>
                {label}
              </span>
            </div>

            {/* Domain title — mt-4 text-lg font-medium */}
            <div style={{ marginTop: '16px', fontSize: '18px', fontWeight: 500, color: '#f8fafc', lineHeight: 1.3 }}>
              {formatDomain(block.domain)}
            </div>

            {/* Headline — mt-1 text-sm font-medium text-slate-100 */}
            <div style={{ marginTop: '4px', fontSize: '14px', fontWeight: 500, color: '#f1f5f9' }}>
              {headline}
            </div>

            {/* Body — mt-3 text-sm leading-6 text-slate-300 */}
            {body && (
              <div style={{
                marginTop: '12px', fontSize: '14px', lineHeight: 1.6, color: '#cbd5e1',
                display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                flex: 1,
              } as React.CSSProperties}>
                {body}
              </div>
            )}

            {/* Product footer — mt-4 text-sm text-slate-300 */}
            {visibleProducts.length > 0 && (
              <div style={{
                marginTop: 'auto', paddingTop: '16px',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                fontSize: '14px', color: '#cbd5e1',
              }}>
                <span>{visibleProducts.join(' · ')}{hiddenCount > 0 ? ` +${hiddenCount}` : ''}</span>
                <span style={{ color: '#94a3b8' }}>→</span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
