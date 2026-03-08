import { MetricItem } from '../../types/trends';

interface MovementLayerPanelProps {
  metrics?: MetricItem[];
}

function formatChange(change: number | string): string {
  if (change === '' || change === null || change === undefined) return '';
  if (typeof change === 'number') {
    const sign = change > 0 ? '+' : '';
    return `${sign}${change.toLocaleString(undefined, { maximumFractionDigits: 1 })}`;
  }
  return String(change);
}

export function MovementLayerPanel({ metrics = [] }: MovementLayerPanelProps) {
  const movers = metrics
    .filter((m) => m.current !== '' && m.cssClass !== 'trend-stable' && m.change !== '' && m.change !== 0)
    .sort((a, b) => Math.abs(Number(b.change)) - Math.abs(Number(a.change)))
    .slice(0, 4);

  return (
    <div style={{
      background: '#0b1626',
      border: '1px solid rgba(255,255,255,0.10)',
      borderRadius: '28px',
      padding: '24px',
      display: 'flex',
      flexDirection: 'column',
      minHeight: '280px',
    }}>
      {/* Header */}
      <div style={{
        fontSize: '10px', fontWeight: 700, color: '#94a3b8',
        textTransform: 'uppercase', letterSpacing: '0.24em', marginBottom: '6px',
      }}>
        Movement Layer
      </div>
      <h2 style={{ fontSize: '20px', fontWeight: 600, color: '#f1f5f9', margin: '0 0 4px', letterSpacing: '-0.02em' }}>
        What changed this week
      </h2>
      <p style={{ fontSize: '13px', color: '#64748b', margin: '0 0 20px', lineHeight: 1.5 }}>
        Absolute values matter less than direction and speed.
      </p>

      {/* Mover rows */}
      {movers.length === 0 ? (
        <div style={{ fontSize: '12px', color: '#334155', fontStyle: 'italic' }}>
          No significant movement this period.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {movers.map((m) => {
            const isUp = m.cssClass === 'trend-up';
            const changeStr = formatChange(m.change);

            // Reference ChangeRail: inactive rows bg-white/[0.03] border-white/10
            // active (up) rows: bg-red-400/10 border-red-300/35
            // active (down) rows: bg-emerald-400/10 border-emerald-300/35
            const rowBg    = isUp ? 'rgba(248,113,113,0.10)' : 'rgba(52,211,153,0.10)';
            const rowBorder = isUp ? 'rgba(252,165,165,0.35)' : 'rgba(110,231,183,0.35)';

            // Delta chip: up = bg-red-400/10 text-red-300; down = bg-emerald-400/10 text-emerald-300
            const chipBg    = isUp ? 'rgba(248,113,113,0.10)' : 'rgba(52,211,153,0.10)';
            const chipColor = isUp ? '#fca5a5' : '#6ee7b7';
            const arrow     = isUp ? '▲' : '▼';

            return (
              <div
                key={m.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '16px',        // px-4 py-4
                  background: rowBg,
                  border: `1px solid ${rowBorder}`,
                  borderRadius: '22px',   // rounded-[22px]
                  gap: '16px',
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: '14px', fontWeight: 500, color: '#f1f5f9', lineHeight: 1.3 }}>
                    {m.title}
                  </div>
                  <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                    {m.changeLabel}
                  </div>
                </div>
                {/* Delta chip — rounded-full px-3 py-1 text-sm font-medium */}
                <div style={{
                  flexShrink: 0,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  background: chipBg,
                  borderRadius: '9999px',
                  padding: '4px 12px',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: chipColor,
                }}>
                  <span style={{ fontSize: '10px' }}>{arrow}</span>
                  {changeStr}
                  {m.unit && <span style={{ fontSize: '11px', opacity: 0.7 }}>{m.unit}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
