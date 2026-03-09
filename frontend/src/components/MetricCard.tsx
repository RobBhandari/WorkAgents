import { MetricItem } from '../types/trends';

interface MetricCardProps {
  item: MetricItem;
  isAlertLinked?: boolean;
  narrativeSentence?: string;
  whyItMatters?: string;
  onInvestigate?: (item: MetricItem) => void;
}

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

// Reference MetricsGrid mini-bars: always sky→cyan gradient, h-24(96px) container, rounded-full bars
function MiniBarChart({ data }: { data: number[] }) {
  const pts = data.slice(-10);
  if (pts.length < 2) return null;

  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const range = max - min || 1;
  const MIN_H = 20;
  const MAX_H = 64;

  return (
    <div style={{ marginTop: '20px' }}>
      <div style={{
        fontSize: '9px',
        fontWeight: 700,
        color: '#334155',
        textTransform: 'uppercase',
        letterSpacing: '0.12em',
        marginBottom: '8px',
      }}>
        10-week shape
      </div>
      {/* Reference: h-24(96px) rounded-2xl border-white/10 bg-white/[0.03] px-3 py-3 */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: '3px',
        height: '72px',
        padding: '12px',
        background: 'rgba(255,255,255,0.03)',
        borderRadius: '16px',
        border: '1px solid rgba(255,255,255,0.10)',
      }}>
        {pts.map((v, i) => {
          const h = MIN_H + ((v - min) / range) * (MAX_H - MIN_H);
          const isLast = i === pts.length - 1;
          return (
            <div
              key={i}
              style={{
                flex: 1,
                height: `${Math.round(h)}px`,
                // Reference: always bg-gradient-to-t from-sky-500/80 to-cyan-300/80
                background: isLast
                  ? 'linear-gradient(to top, rgba(14,165,233,0.90), rgba(103,232,249,0.90))'
                  : 'linear-gradient(to top, rgba(14,165,233,0.35), rgba(103,232,249,0.35))',
                borderRadius: '9999px',
                transition: 'height 0.2s',
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

const isLauncher = (item: MetricItem) => item.current === '';

export function MetricCard({ item, isAlertLinked, narrativeSentence, whyItMatters, onInvestigate }: MetricCardProps) {
  const launcher = isLauncher(item);
  const changeStr = formatChange(item.change);

  const TREND_COLORS: Record<string, string> = {
    'trend-up':     '#f87171',
    'trend-down':   '#34d399',
    'trend-stable': '#64748b',
  };
  const trendColor = TREND_COLORS[item.cssClass] ?? '#94a3b8';

  return (
    <a
      href={item.dashboardUrl}
      target="_blank"
      rel="noreferrer"
      data-metric-id={item.id}
      onClick={(e) => { if (onInvestigate) { e.preventDefault(); onInvestigate(item); } }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        // Reference: default border-white/10 bg-white/[0.03]; alert-linked border-white/15 bg-white/[0.06]
        background: isAlertLinked ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.03)',
        borderRadius: '24px',
        border: `1px solid ${isAlertLinked ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.10)'}`,
        borderTop: `2px solid ${isAlertLinked ? 'rgba(239,68,68,0.45)' : item.ragColor + '70'}`,
        padding: '20px',
        minHeight: '220px',
        transition: 'background 0.15s, transform 0.12s, box-shadow 0.15s',
        cursor: 'pointer',
        textDecoration: 'none',
        color: 'inherit',
        position: 'relative',
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLElement;
        el.style.transform = 'translateY(-2px)';
        el.style.boxShadow = '0 12px 32px rgba(0,0,0,0.25)';
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLElement;
        el.style.transform = 'translateY(0)';
        el.style.boxShadow = 'none';
      }}
    >
      {/* Header: icon + title + alert badge */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px', minWidth: 0 }}>
          <span style={{ fontSize: '14px', lineHeight: 1, flexShrink: 0 }}>{item.icon}</span>
          {/* Reference: text-sm font-medium text-slate-100 */}
          <span style={{
            fontSize: '14px', fontWeight: 500, color: '#f1f5f9',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {item.title}
          </span>
        </div>
        {isAlertLinked && (
          // Reference: rounded-full bg-red-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-red-200
          <span style={{
            fontSize: '10px',
            fontWeight: 700,
            color: '#fecaca',
            background: 'rgba(248,113,113,0.10)',
            border: '1px solid rgba(248,113,113,0.22)',
            padding: '2px 8px',
            borderRadius: '9999px',
            textTransform: 'uppercase',
            letterSpacing: '0.18em',
            flexShrink: 0,
          }}>
            Alert
          </span>
        )}
      </div>

      {launcher ? (
        <>
          <p style={{ fontSize: '12px', color: '#475569', flexGrow: 1, lineHeight: 1.5, margin: '12px 0 0' }}>
            {item.description}
          </p>
          <div style={{
            marginTop: '12px',
            padding: '8px 14px',
            background: item.ragColor + '14',
            border: `1px solid ${item.ragColor}35`,
            borderRadius: '12px',
            fontSize: '12px',
            fontWeight: 600,
            color: item.ragColor,
            textAlign: 'center',
          }}>
            View Dashboard →
          </div>
        </>
      ) : (
        <>
          {/* Value — mt-3 text-4xl(36px) font-semibold leading-none */}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '12px' }}>
            <span style={{ fontSize: '36px', fontWeight: 600, letterSpacing: '-0.04em', color: '#f1f5f9', lineHeight: 1 }}>
              {formatValue(item.current, '')}
            </span>
            {/* Unit below value: mb-1 text-sm text-slate-400 */}
            {item.unit && (
              <span style={{ fontSize: '13px', color: '#94a3b8', fontWeight: 400 }}>{item.unit}</span>
            )}
          </div>

          {/* Delta chip */}
          {item.arrow && changeStr && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px' }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: '4px',
                background: `${trendColor}14`,
                border: `1px solid ${trendColor}28`,
                borderRadius: '9999px',
                padding: '2px 8px',
              }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: trendColor }}>
                  {changeStr}
                </span>
              </span>
              <span style={{ fontSize: '11px', color: '#475569' }}>{item.changeLabel}</span>
            </div>
          )}

          {/* Mini bar chart — sky/cyan gradient always */}
          {item.data.length >= 2 && <MiniBarChart data={item.data} />}

          {/* Insight block — mt-4 rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-sm text-slate-300 */}
          {(narrativeSentence || whyItMatters) && (
            <div style={{
              fontSize: '13px',
              color: '#cbd5e1',
              lineHeight: 1.6,
              padding: '12px',
              marginTop: 'auto',
              paddingTop: '16px',
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.10)',
              borderRadius: '16px',
            }}>
              {narrativeSentence && <div>{narrativeSentence}</div>}
              {whyItMatters && (
                <div style={{
                  fontSize: '11px',
                  color: '#64748b',
                  marginTop: narrativeSentence ? '6px' : undefined,
                  lineHeight: 1.5,
                }}>
                  {whyItMatters}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </a>
  );
}
