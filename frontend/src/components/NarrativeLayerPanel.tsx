import { HealthScorePayload } from '../types/health';
import { SignalsPayload } from '../types/signals';
import { AlertItem } from '../types/trends';
import { CrossDomainCollision } from '../utils/crossDomainCollision';
import { CollisionDispatchHint } from '../utils/collisionDispatch';

interface NarrativeLayerPanelProps {
  healthData: HealthScorePayload | null;
  signalsData: SignalsPayload | null;
  signalsLoading: boolean;
  topAlertDomain: string | null;
  alerts: AlertItem[];
  worsening: number;
  improving: number;
  collision?: CrossDomainCollision | null;
  collisionDispatchHint?: CollisionDispatchHint | null;
}

export function NarrativeLayerPanel({
  healthData,
  signalsData,
  signalsLoading,
  topAlertDomain,
  alerts,
  worsening,
  improving,
  collision,
  collisionDispatchHint,
}: NarrativeLayerPanelProps) {
  const topDomainProducts = topAlertDomain
    ? new Set(
        alerts
          .filter((a) => {
            const label = (a.dashboard || 'other')
              .replace(/-/g, ' ')
              .replace(/\b\w/g, (c) => c.toUpperCase());
            return label === topAlertDomain;
          })
          .map((a) => a.project_name)
          .filter(Boolean),
      ).size
    : 0;

  const topDomainAlertCount = topAlertDomain
    ? alerts.filter((a) => {
        const label = (a.dashboard || 'other')
          .replace(/-/g, ' ')
          .replace(/\b\w/g, (c) => c.toUpperCase());
        return label === topAlertDomain;
      }).length
    : 0;

  const block1: string | null = signalsData?.signals?.[0]?.message ?? null;

  const block2: string | null = topAlertDomain && topDomainAlertCount > 0
    ? `${topAlertDomain}: ${topDomainAlertCount} alert${topDomainAlertCount !== 1 ? 's' : ''}, ${topDomainProducts} product${topDomainProducts !== 1 ? 's' : ''} affected.`
    : null;

  const block3: string | null =
    worsening > 0 && improving > 0
      ? `${worsening} metric${worsening !== 1 ? 's' : ''} declining, ${improving} improving.`
      : worsening > 0
      ? `${worsening} metric${worsening !== 1 ? 's' : ''} declining this period.`
      : improving > 0
      ? `${improving} metric${improving !== 1 ? 's' : ''} improving this period.`
      : healthData?.label === 'healthy'
      ? 'No critical action required at this time.'
      : null;

  const blockCollision: string | null =
    collision && collision.confidence !== 'low'
      ? collision.summary
      : null;

  const blocks = [block1, block2, blockCollision, block3].filter((b): b is string => b !== null);

  return (
    // Reference AiPanel: rounded-[28px] border border-violet-300/10 bg-[linear-gradient(180deg,rgba(76,29,149,0.10),rgba(10,20,34,0.92))] p-6
    <div style={{
      background: 'linear-gradient(180deg, rgba(76,29,149,0.10) 0%, rgba(10,20,34,0.92) 100%)',
      border: '1px solid rgba(167,139,250,0.10)',
      borderRadius: '28px',
      padding: '24px',
      display: 'flex',
      flexDirection: 'column',
      minHeight: '280px',
    }}>
      {/* Category — text-xs uppercase tracking-[0.24em] text-violet-200 */}
      <div style={{
        fontSize: '10px',
        fontWeight: 700,
        color: '#ddd6fe',
        textTransform: 'uppercase',
        letterSpacing: '0.24em',
        marginBottom: '8px',
      }}>
        AI Narrative Layer
      </div>

      {/* h2 — mt-2 text-2xl font-semibold */}
      <h2 style={{
        fontSize: '24px',
        fontWeight: 600,
        color: '#f1f5f9',
        margin: '0 0 4px',
        letterSpacing: '-0.02em',
      }}>
        Executive interpretation
      </h2>
      <p style={{ fontSize: '13px', color: '#64748b', margin: '0 0 20px', lineHeight: 1.5 }}>
        Deterministic signals from the current data window.
      </p>

      {signalsLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {[88, 72, 58].map((w, i) => (
            <div key={i} style={{
              height: '10px',
              width: `${w}%`,
              borderRadius: '3px',
              background: 'rgba(255,255,255,0.05)',
            }} />
          ))}
        </div>
      ) : blocks.length === 0 ? (
        <p style={{ fontSize: '13px', color: '#334155', margin: 0, fontStyle: 'italic' }}>
          Narrative unavailable.
        </p>
      ) : (
        // Reference: rounded-[22px] border border-white/10 bg-white/5 p-4 text-sm leading-6 text-slate-200
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {blocks.map((text, i) => {
            const isFirst     = i === 0;
            const isCollision = blockCollision !== null && text === blockCollision;
            const bg     = isFirst ? 'rgba(99,102,241,0.10)'
                         : isCollision ? 'rgba(245,158,11,0.08)'
                         : 'rgba(255,255,255,0.05)';
            const border = isFirst ? 'rgba(99,102,241,0.22)'
                         : isCollision ? 'rgba(245,158,11,0.22)'
                         : 'rgba(255,255,255,0.10)';
            const color  = isFirst ? '#c4b5fd'
                         : isCollision ? '#fde68a'
                         : '#e2e8f0';
            return (
              <div key={i} style={{
                background:   bg,
                border:       `1px solid ${border}`,
                borderRadius: '22px',
                padding:      '16px',
                fontSize:     '14px',
                color,
                lineHeight:   1.6,
              }}>
                {text}
                {isCollision && collision && collision.confidence && (
                  <div style={{ marginTop: '6px', fontSize: '13px', color: '#fde68a', opacity: 0.85 }}>
                    Confidence: {collision.confidence.charAt(0).toUpperCase() + collision.confidence.slice(1)}
                  </div>
                )}
                {isCollision && collision && collision.sharedDrivers.length > 1 && (
                  <div style={{ marginTop: '6px', fontSize: '13px', color: '#fde68a', opacity: 0.85 }}>
                    {'Related signals: '}
                    {collision.sharedDrivers.slice(1, 3).map((s, i, arr) => (
                      <span key={s.signalKey}>
                        {s.signalLabel}
                        {s.direction === 'up' ? ' ↑' : s.direction === 'down' ? ' ↓' : ''}
                        {i < arr.length - 1 ? ', ' : ''}
                      </span>
                    ))}
                  </div>
                )}
                {isCollision && collisionDispatchHint && (
                  <div style={{ marginTop: '6px', fontSize: '13px', color: '#fbbf24', opacity: 0.8 }}>
                    Suggested investigation: {collisionDispatchHint.dashboardLabel}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
