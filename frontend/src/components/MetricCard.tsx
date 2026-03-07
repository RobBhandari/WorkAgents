import { MetricItem } from '../types/trends';
import { Sparkline } from './Sparkline';

interface MetricCardProps {
  item: MetricItem;
}

const TREND_COLORS: Record<string, string> = {
  'trend-up': '#ef4444',
  'trend-down': '#10b981',
  'trend-stable': '#94a3b8',
};

function formatValue(current: number | string, unit: string): string {
  if (current === '' || current === null || current === undefined) return '—';
  if (typeof current === 'number') {
    if (current >= 10000) return `${current.toLocaleString()} ${unit}`.trim();
    return `${current.toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}`.trim();
  }
  return String(current);
}

function formatChange(change: number | string): string {
  if (change === '' || change === null || change === undefined) return '';
  if (typeof change === 'number') {
    const sign = change > 0 ? '+' : '';
    return `${sign}${change.toLocaleString(undefined, { maximumFractionDigits: 1 })}`;
  }
  return '';
}

const isLauncher = (item: MetricItem) => item.current === '';

export function MetricCard({ item }: MetricCardProps) {
  const launcher = isLauncher(item);
  const trendColor = TREND_COLORS[item.cssClass] ?? '#94a3b8';

  return (
    <a
      href={item.dashboardUrl}
      target="_blank"
      rel="noreferrer"
      style={{
        display: 'flex',
        flexDirection: 'column',
        background: '#1e293b',
        borderRadius: '10px',
        border: '1px solid rgba(255,255,255,0.07)',
        borderLeft: `3px solid ${item.ragColor}`,
        padding: '16px',
        gap: '8px',
        transition: 'background 0.15s, transform 0.15s',
        cursor: 'pointer',
        textDecoration: 'none',
        color: 'inherit',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.background = '#263347';
        (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.background = '#1e293b';
        (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '16px', lineHeight: 1 }}>{item.icon}</span>
        <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {item.title}
        </span>
      </div>

      {launcher ? (
        /* Launcher variant — no metrics, just a CTA */
        <>
          <p style={{ fontSize: '12px', color: '#64748b', flexGrow: 1, lineHeight: 1.4 }}>
            {item.description}
          </p>
          <div
            style={{
              marginTop: '4px',
              padding: '6px 12px',
              background: item.ragColor + '22',
              border: `1px solid ${item.ragColor}55`,
              borderRadius: '6px',
              fontSize: '12px',
              fontWeight: 600,
              color: item.ragColor,
              textAlign: 'center',
            }}
          >
            View Dashboard
          </div>
        </>
      ) : (
        /* Standard metric variant */
        <>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
            <span style={{ fontSize: '26px', fontWeight: 700, letterSpacing: '-0.02em', color: '#f1f5f9' }}>
              {formatValue(item.current, '')}
            </span>
            {item.unit && (
              <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 500 }}>{item.unit}</span>
            )}
          </div>

          {/* Change row */}
          {item.arrow && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
              <span style={{ color: trendColor, fontWeight: 700, fontSize: '14px' }}>{item.arrow}</span>
              <span style={{ color: trendColor, fontWeight: 600 }}>{formatChange(item.change)}</span>
              <span style={{ color: '#475569' }}>{item.changeLabel}</span>
            </div>
          )}

          {/* Sparkline */}
          {item.data.length >= 2 && (
            <div style={{ marginTop: '4px' }}>
              <Sparkline data={item.data} color={item.ragColor} width={120} height={32} />
            </div>
          )}
        </>
      )}
    </a>
  );
}
