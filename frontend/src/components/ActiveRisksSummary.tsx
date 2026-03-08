// Active Risks Summary — compact grouped risk blocks for leadership surface.
// Replaces the raw AlertList feed with a top-3 domain-grouped summary.
// Alert data model (AlertItem[]) is unchanged.

import { AlertItem } from '../types/trends';

interface ActiveRisksSummaryProps {
  alerts: AlertItem[];
}

const SEVERITY_WEIGHT: Record<string, number> = {
  critical: 3,
  warn: 2,
  medium: 1,
};

const SEVERITY_COLOR: Record<string, string> = {
  critical: '#ef4444',
  warn: '#6366f1',
  medium: '#f59e0b',
};

const SEVERITY_BG: Record<string, string> = {
  critical: 'rgba(239,68,68,0.08)',
  warn: 'rgba(99,102,241,0.08)',
  medium: 'rgba(245,158,11,0.08)',
};

const SEVERITY_BORDER: Record<string, string> = {
  critical: 'rgba(239,68,68,0.2)',
  warn: 'rgba(99,102,241,0.2)',
  medium: 'rgba(245,158,11,0.2)',
};

const SEVERITY_LABEL: Record<string, string> = {
  critical: 'Critical',
  warn: 'Warning',
  medium: 'Medium',
};

// Format dashboard/domain names for display.
function formatDomain(domain: string): string {
  return domain
    .replace(/-/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

interface RiskBlock {
  domain: string;
  topSeverity: string;
  alertCount: number;
  productCount: number;
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
    const products = new Set(items.map((a) => a.project_name).filter(Boolean));
    const topSeverity = SEV_ORDER.find((s) => items.some((a) => a.severity === s)) ?? 'medium';
    blocks.push({ domain, topSeverity, alertCount: items.length, productCount: products.size, weight });
  }

  return blocks.sort((a, b) => b.weight - a.weight).slice(0, 3);
}

export function ActiveRisksSummary({ alerts }: ActiveRisksSummaryProps) {
  if (alerts.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#475569' }}>
        <span style={{ color: '#10b981', fontSize: '14px' }}>&#10003;</span>
        No active risks detected.
      </div>
    );
  }

  const blocks = buildRiskBlocks(alerts);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {blocks.map((block, idx) => {
        const color  = SEVERITY_COLOR[block.topSeverity] ?? '#64748b';
        const bg     = SEVERITY_BG[block.topSeverity]    ?? 'rgba(255,255,255,0.04)';
        const border = SEVERITY_BORDER[block.topSeverity] ?? 'rgba(255,255,255,0.07)';
        const label  = SEVERITY_LABEL[block.topSeverity]  ?? block.topSeverity;
        const isLast = idx === blocks.length - 1;

        return (
          <div
            key={block.domain}
            style={{
              padding: '12px 14px',
              background: bg,
              border: `1px solid ${border}`,
              borderRadius: '6px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              marginBottom: isLast ? 0 : 2,
            }}
          >
            {/* Row 1: domain title + severity badge */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: '#f1f5f9' }}>
                {formatDomain(block.domain)}
              </span>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  color,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                {label}
              </span>
            </div>

            {/* Row 2: affected products + alert count */}
            <div style={{ display: 'flex', gap: '16px' }}>
              <span style={{ fontSize: '11px', color: '#64748b' }}>
                <span style={{ color: '#94a3b8', fontWeight: 600 }}>{block.productCount}</span>
                {' '}product{block.productCount !== 1 ? 's' : ''} affected
              </span>
              <span style={{ fontSize: '11px', color: '#64748b' }}>
                <span style={{ color: '#94a3b8', fontWeight: 600 }}>{block.alertCount}</span>
                {' '}alert{block.alertCount !== 1 ? 's' : ''}
              </span>
            </div>
          </div>
        );
      })}

      {/* Total count footer */}
      <div style={{ fontSize: '11px', color: '#334155', marginTop: '2px' }}>
        {alerts.length} total alert{alerts.length !== 1 ? 's' : ''} across all domains
      </div>
    </div>
  );
}
