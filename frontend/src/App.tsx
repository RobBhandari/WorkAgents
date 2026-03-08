import { useState } from 'react';
import { MetricGrid } from './components/MetricGrid';
import { ActiveRisksSummary } from './components/ActiveRisksSummary';
import { MovementLayerPanel } from './components/dashboard/MovementLayerPanel';
import { NarrativeLayerPanel } from './components/NarrativeLayerPanel';
import { SystemShapeRadar } from './components/SystemShapeRadar';
import { MetricInvestigationDrawer } from './components/MetricInvestigationDrawer';
import { DrawerTarget, buildMetricTarget } from './utils/buildDrawerTarget';
import { AnomalyRiver } from './components/AnomalyRiver';
import { useTrendsData } from './hooks/useTrendsData';
import { useHealthScore } from './hooks/useHealthScore';
import { useSignalsData } from './hooks/useSignalsData';
import { MetricItem } from './types/trends';
import { buildAnomalyRiver } from './utils/buildAnomalyRiver';
import { detectCrossDomainPressureCollisions, CrossDomainCollision } from './utils/crossDomainCollision';

function shouldEscalateCollision(collision: CrossDomainCollision | null): boolean {
  if (!collision) return false;
  if (collision.confidence !== 'high') return false;
  if (collision.sharedDrivers.length === 0) return false;
  return true;
}

// Maps metric IDs to their WHY_IT_MATTERS / alert-domain key
const METRIC_TO_DOMAIN: Record<string, string> = {
  exploitable:      'security',
  security:         'security',
  'security-infra': 'infrastructure',
  target:           'security',
  deployment:       'deployment',
  flow:             'flow',
  bugs:             'bugs',
  collaboration:    'collaboration',
  ownership:        'ownership',
  risk:             'risk',
};

function parseDataAge(timestamp: string): { isStale: boolean; label: string } {
  const parsed = new Date(timestamp.replace(' at ', ' '));
  if (isNaN(parsed.getTime())) return { isStale: false, label: 'live' };
  const ageMs = Date.now() - parsed.getTime();
  const ageHours = ageMs / (1000 * 60 * 60);
  if (ageHours < 24) return { isStale: false, label: 'live' };
  const ageDisplay = ageHours < 48 ? `${Math.round(ageHours)}h old` : `${Math.round(ageHours / 24)}d old`;
  return { isStale: true, label: `stale · ${ageDisplay}` };
}

const LABEL_COLOR: Record<string, string> = {
  healthy:   '#10b981',
  fair:      '#f59e0b',
  'at risk': '#ef4444',
};

// Precise gradient stops for progress bar by health label
const SCORE_GRADIENT: Record<string, string> = {
  healthy:   'linear-gradient(to right, #38bdf8, #67e8f9, #34d399)',
  fair:      'linear-gradient(to right, #fbbf24, #f59e0b)',
  'at risk': 'linear-gradient(to right, #f87171, #ef4444)',
};

export default function App() {
  const [renderedTarget, setRenderedTarget] = useState<DrawerTarget | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  function openDrawer(target: DrawerTarget) {
    setRenderedTarget(target);
    // Allow the DOM to mount before transitioning in
    requestAnimationFrame(() => requestAnimationFrame(() => setDrawerOpen(true)));
  }

  function closeDrawer() {
    setDrawerOpen(false);
    setTimeout(() => setRenderedTarget(null), 520);
  }

  function openMetricDrawer(m: MetricItem) {
    openDrawer(buildMetricTarget(m, METRIC_TO_DOMAIN[m.id] ?? 'deployment'));
  }
  const { data, error, loading } = useTrendsData();
  const { data: healthData, error: healthError, loading: healthLoading } = useHealthScore();
  const { data: signalsData, loading: signalsLoading } = useSignalsData();

  if (loading) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#07111f', color: '#94a3b8', fontSize: '14px' }}>
      Loading…
    </div>
  );

  if (error || !data) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#07111f', color: '#f87171', fontSize: '14px' }}>
      {error ?? 'No data'}
    </div>
  );

  const { isStale, label: ageLabel } = parseDataAge(data.timestamp);
  const activeAlerts = data.alerts.length;
  const worsening = data.metrics.filter((m) => m.ragColor === '#ef4444').length;
  const improving = data.metrics.filter((m) => m.ragColor === '#10b981').length;

  const domainCounts = new Map<string, number>();
  for (const a of data.alerts) {
    const d = a.dashboard || 'other';
    domainCounts.set(d, (domainCounts.get(d) ?? 0) + 1);
  }
  const topAlertDomain = [...domainCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
  const topAlertDomainLabel = topAlertDomain
    ? topAlertDomain.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : null;

  const riverRows   = buildAnomalyRiver(data.metrics);
  const collisionResult = detectCrossDomainPressureCollisions(riverRows);
  const topCollision: CrossDomainCollision | null = collisionResult.topCollision;

  const heroHeadline =
    !healthData ? 'Engineering health data loading…'
    : healthData.label === 'at risk' ? 'Several metrics are below target and require action.'
    : healthData.label === 'fair' ? 'Some metrics need attention — review the signals below.'
    : 'Portfolio is in good shape across tracked metrics.';

  const heroSubline =
    !healthData ? ''
    : healthData.label === 'at risk' ? `${worsening} metric${worsening !== 1 ? 's' : ''} below threshold. ${activeAlerts} active alert${activeAlerts !== 1 ? 's' : ''} across the portfolio.`
    : healthData.label === 'fair' ? `${worsening} metric${worsening !== 1 ? 's' : ''} trending amber. ${improving} recovering.`
    : `${improving} metric${improving !== 1 ? 's' : ''} tracking green. ${activeAlerts} alert${activeAlerts !== 1 ? 's' : ''} to review.`;

  const scoreColor = healthData ? (LABEL_COLOR[healthData.label] ?? '#64748b') : '#334155';
  const scoreGradient = healthData ? (SCORE_GRADIENT[healthData.label] ?? SCORE_GRADIENT.fair) : SCORE_GRADIENT.fair;

  // Chip tone → exact reference ActionChip colors
  const chipDanger  = { color: '#fca5a5', bg: 'rgba(239,68,68,0.10)',   border: 'rgba(239,68,68,0.20)'   };
  const chipGood    = { color: '#6ee7b7', bg: 'rgba(16,185,129,0.10)',  border: 'rgba(16,185,129,0.20)'  };
  const chipWarn    = { color: '#fcd34d', bg: 'rgba(245,158,11,0.10)',  border: 'rgba(245,158,11,0.20)'  };
  const chipNeutral = { color: '#e2e8f0', bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.10)' };

  const chip = (c: typeof chipDanger, _label: string): React.CSSProperties => ({
    display: 'inline-flex', alignItems: 'center', gap: '8px',
    padding: '6px 12px',
    background: c.bg, border: `1px solid ${c.border}`, borderRadius: '9999px',
    fontSize: '14px', fontWeight: 500, color: c.color,
    whiteSpace: 'nowrap' as const,
  });

  return (
    <div style={{ minHeight: '100vh', background: '#07111f', color: '#f8fafc', fontFamily: 'inherit' }}>

      {/* ── Header ── */}
      <header style={{
        padding: '12px 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#38bdf8', boxShadow: '0 0 6px rgba(56,189,248,0.7)' }} />
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#94a3b8', letterSpacing: '0.04em' }}>
            Engineering Command Centre
          </span>
        </div>
        <span style={{
          fontSize: '11px',
          color: isStale ? '#f59e0b' : '#475569',
          background: isStale ? 'rgba(245,158,11,0.07)' : 'transparent',
          border: `1px solid ${isStale ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.06)'}`,
          padding: '3px 9px', borderRadius: '6px',
        }}>
          {isStale ? ageLabel : 'live'}
        </span>
      </header>

      {/* ── Centered composition wrapper ── */}
      <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '32px 24px 48px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

        {/* ── HERO ── */}
        {/* Reference: rounded-[32px] border border-white/10 bg-[linear-gradient(135deg,...)] p-6 shadow-[0_40px_120px_rgba(0,0,0,0.35)] */}
        <section style={{
          position: 'relative',
          overflow: 'hidden',
          borderRadius: '32px',
          border: '1px solid rgba(255,255,255,0.10)',
          background: 'linear-gradient(135deg, rgba(12,24,40,0.96), rgba(8,16,28,0.98))',
          padding: '24px',
          boxShadow: '0 40px 120px rgba(0,0,0,0.35)',
        }}>
          {/* Radial glow overlay — exact reference */}
          <div style={{
            position: 'absolute', inset: 0, pointerEvents: 'none',
            background: 'radial-gradient(circle at top right, rgba(56,189,248,0.18), transparent 25%), radial-gradient(circle at left, rgba(168,85,247,0.12), transparent 24%), radial-gradient(circle at bottom, rgba(239,68,68,0.08), transparent 30%)',
          }} />

          {/* Grid: 1.15fr 0.85fr */}
          <div style={{ position: 'relative', zIndex: 1, display: 'grid', gridTemplateColumns: '1.15fr 0.85fr', gap: '24px' }}>

            {/* Left */}
            <div>
              {/* Category badge — exact reference */}
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: '8px',
                borderRadius: '9999px', border: '1px solid rgba(56,189,248,0.20)',
                background: 'rgba(56,189,248,0.10)',
                padding: '4px 12px',
                fontSize: '11px', fontWeight: 600,
                textTransform: 'uppercase', letterSpacing: '0.28em',
                color: '#bae6fd',
              }}>
                ✦ Engineering health command centre
              </div>

              {/* Hero h1 — text-5xl font-semibold tracking-tight */}
              <h1 style={{
                marginTop: '16px',
                fontSize: '48px', fontWeight: 600,
                color: '#f8fafc',
                lineHeight: 1.08,
                letterSpacing: '-0.025em',
                maxWidth: '640px',
              }}>
                {heroHeadline}
              </h1>

              {/* Subline — text-base leading-6 text-slate-300 */}
              {heroSubline && (
                <p style={{
                  marginTop: '16px',
                  fontSize: '16px', lineHeight: 1.6,
                  color: '#cbd5e1',
                  maxWidth: '560px',
                }}>
                  {heroSubline}
                </p>
              )}

              {/* Chips — gap-3, rounded-full, px-3 py-1.5, text-sm */}
              <div style={{ marginTop: '24px', display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
                <span style={chip(activeAlerts > 0 ? chipDanger : chipNeutral, '')}>
                  ◎ {activeAlerts} critical risk{activeAlerts !== 1 ? 's' : ''}
                </span>
                <span style={chip(improving > 0 ? chipGood : chipNeutral, '')}>
                  ↗ {improving} metric{improving !== 1 ? 's' : ''} improving
                </span>
                <span style={chip(worsening > 0 ? chipWarn : chipNeutral, '')}>
                  ↘ {worsening} metric{worsening !== 1 ? 's' : ''} declining
                </span>
                {topAlertDomainLabel && (
                  <span style={chip(chipNeutral, '')}>
                    ⚑ Spotlight: {topAlertDomainLabel}
                  </span>
                )}
              </div>
            </div>

            {/* Right — glass card stack */}
            <div style={{ display: 'grid', gridTemplateRows: 'auto auto', gap: '16px' }}>

              {/* Health Score GlassCard — rounded-[24px] border-white/10 bg-white/5 p-5 */}
              <div style={{
                gridColumn: '1 / -1',
                borderRadius: '24px', border: '1px solid rgba(255,255,255,0.10)',
                background: 'rgba(255,255,255,0.05)',
                padding: '20px',
                backdropFilter: 'blur(8px)',
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
                  <div>
                    <div style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.22em', color: '#94a3b8' }}>
                      Health score
                    </div>
                    {healthLoading && <span style={{ fontSize: '14px', color: '#94a3b8', fontStyle: 'italic', display: 'block', marginTop: '12px' }}>Evaluating…</span>}
                    {!healthLoading && (healthError || !healthData) && <span style={{ fontSize: '14px', color: '#f59e0b', display: 'block', marginTop: '12px' }}>Unavailable</span>}
                    {!healthLoading && !healthError && healthData && (
                      <div style={{ marginTop: '12px', display: 'flex', alignItems: 'flex-end', gap: '12px' }}>
                        <span style={{ fontSize: '60px', fontWeight: 600, color: scoreColor, lineHeight: 1, letterSpacing: '-0.04em' }}>
                          {healthData.score}
                        </span>
                        <span style={{
                          marginBottom: '4px',
                          borderRadius: '9999px',
                          background: `${scoreColor}18`, border: `1px solid ${scoreColor}30`,
                          padding: '4px 10px', fontSize: '12px', fontWeight: 500, color: scoreColor,
                        }}>
                          {healthData.label}
                        </span>
                      </div>
                    )}
                  </div>
                  <div style={{ fontSize: '24px', color: '#7dd3fc', flexShrink: 0, marginTop: '4px', opacity: 0.6 }}>◉</div>
                </div>

                {/* Progress bar — gradient sky→cyan→emerald */}
                {!healthLoading && !healthError && healthData && (
                  <>
                    <div style={{ marginTop: '16px', height: '8px', overflow: 'hidden', borderRadius: '9999px', background: 'rgba(255,255,255,0.05)' }}>
                      <div style={{
                        height: '100%', borderRadius: '9999px',
                        width: `${healthData.score}%`,
                        background: scoreGradient,
                        transition: 'width 0.9s ease',
                      }} />
                    </div>
                    <p style={{ marginTop: '12px', fontSize: '14px', color: '#cbd5e1', lineHeight: 1.5 }}>
                      {healthData.contributing_metrics} of {healthData.total_metrics} metrics contributing.{' '}
                      {healthData.label === 'healthy' ? 'Portfolio is in good shape.' : healthData.label === 'fair' ? 'Some signals need attention.' : 'Action required across multiple domains.'}
                    </p>
                  </>
                )}
              </div>

              {/* Stat pills row — 2 columns */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                {/* Active alerts stat */}
                <div style={{ borderRadius: '24px', border: '1px solid rgba(255,255,255,0.10)', background: 'rgba(255,255,255,0.05)', padding: '20px', backdropFilter: 'blur(8px)' }}>
                  <div style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.22em', color: '#94a3b8' }}>Active alerts</div>
                  <div style={{ marginTop: '8px', fontSize: '36px', fontWeight: 600, color: activeAlerts > 0 ? '#f87171' : '#475569', lineHeight: 1, letterSpacing: '-0.03em' }}>
                    {activeAlerts}
                  </div>
                  <div style={{ marginTop: '4px', fontSize: '12px', color: '#64748b' }}>
                    {activeAlerts > 0 ? `${domainCounts.size} domain${domainCounts.size !== 1 ? 's' : ''}` : 'all clear'}
                  </div>
                </div>
                {/* Data freshness stat */}
                <div style={{ borderRadius: '24px', border: '1px solid rgba(255,255,255,0.10)', background: 'rgba(255,255,255,0.05)', padding: '20px', backdropFilter: 'blur(8px)' }}>
                  <div style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.22em', color: '#94a3b8' }}>Data</div>
                  <div style={{ marginTop: '8px', fontSize: '36px', fontWeight: 600, color: isStale ? '#f59e0b' : '#34d399', lineHeight: 1, letterSpacing: '-0.03em' }}>
                    {isStale ? (ageLabel.split('·')[1]?.trim() ?? 'stale') : 'live'}
                  </div>
                  <div style={{ marginTop: '4px', fontSize: '12px', color: '#64748b' }}>
                    {data.metrics.length} metrics tracked
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── ALERT LAYER + SYSTEM SHAPE ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '24px' }}>

          {/* Alert Layer — rounded-[28px] border-red-400/15 gradient p-6 */}
          <section style={{
            borderRadius: '28px',
            border: '1px solid rgba(239,68,68,0.15)',
            background: 'linear-gradient(180deg, rgba(127,29,29,0.08) 0%, rgba(8,16,28,0.90) 100%)',
            padding: '24px',
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '16px' }}>
              <div>
                <div style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.24em', color: '#fecaca', fontWeight: 600 }}>
                  Global alert layer
                </div>
                <h2 style={{ margin: '8px 0 0', fontSize: '24px', fontWeight: 600, color: '#f8fafc', letterSpacing: '-0.01em' }}>
                  Active risk signals
                </h2>
              </div>
              <div style={{ fontSize: '14px', color: '#94a3b8', flexShrink: 0 }}>
                {activeAlerts > 0
                  ? `${activeAlerts} alert${activeAlerts !== 1 ? 's' : ''} · ${domainCounts.size} domain${domainCounts.size !== 1 ? 's' : ''}`
                  : 'No active alerts'}
              </div>
            </div>
            <div style={{ marginTop: '20px' }}>
              {/* Only show API alerts when present; suppress empty-state when collision escalates instead */}
              {(activeAlerts > 0 || !shouldEscalateCollision(topCollision)) && (
                <ActiveRisksSummary alerts={data.alerts} horizontal />
              )}
              {shouldEscalateCollision(topCollision) && (
                <div style={{
                  marginTop: activeAlerts > 0 ? '12px' : '0',
                  padding: '14px 18px',
                  borderRadius: '14px',
                  background: 'rgba(245,158,11,0.07)',
                  border: '1px solid rgba(245,158,11,0.20)',
                  borderLeft: '3px solid #f59e0b',
                  fontSize: '14px',
                  lineHeight: 1.6,
                  color: '#fde68a',
                }}>
                  {topCollision!.summary}
                </div>
              )}
            </div>
          </section>

          {/* System Shape — rounded-[28px] bg-[#0b1626] p-6 */}
          <section style={{
            borderRadius: '28px',
            border: '1px solid rgba(255,255,255,0.10)',
            background: '#0b1626',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
          }}>
            <div style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.24em', color: '#94a3b8', fontWeight: 600 }}>
              System shape
            </div>
            <h2 style={{ margin: '8px 0 0', fontSize: '24px', fontWeight: 600, color: '#f8fafc', letterSpacing: '-0.01em' }}>
              Engineering health radar
            </h2>
            <p style={{ margin: '8px 0 0', fontSize: '14px', lineHeight: 1.6, color: '#cbd5e1' }}>
              Weakness should be visible as form. If leaders need ten cards to understand the system, the design failed.
            </p>
            {/* Radar container — rounded-[24px] border-white/10 radial-gradient p-4 */}
            <div style={{
              marginTop: '20px',
              flex: 1,
              borderRadius: '24px',
              border: '1px solid rgba(255,255,255,0.10)',
              background: 'radial-gradient(circle at center, rgba(56,189,248,0.12), transparent 38%), linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01))',
              padding: '16px',
              minHeight: '340px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <SystemShapeRadar metrics={data.metrics} />
            </div>
          </section>
        </div>

        {/* ── MOVEMENT + NARRATIVE ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '24px' }}>
          <MovementLayerPanel metrics={data.metrics} />
          <NarrativeLayerPanel
            healthData={healthData}
            signalsData={signalsData}
            signalsLoading={signalsLoading}
            topAlertDomain={topAlertDomainLabel}
            alerts={data.alerts}
            worsening={worsening}
            improving={improving}
            collision={topCollision}
          />
        </div>

        {/* ── ANOMALY RIVER ── */}
        <AnomalyRiver
          rows={riverRows}
          metrics={data.metrics}
          alerts={data.alerts}
          onDomainClick={openDrawer}
        />

        {/* ── METRIC ENTRY POINTS — rounded-[28px] bg-[#0b1626] p-6 ── */}
        <section style={{
          borderRadius: '28px',
          border: '1px solid rgba(255,255,255,0.10)',
          background: '#0b1626',
          padding: '24px',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '16px', marginBottom: '20px' }}>
            <div>
              <div style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.24em', color: '#94a3b8', fontWeight: 600 }}>
                Metric entry points
              </div>
              <h2 style={{ margin: '8px 0 0', fontSize: '24px', fontWeight: 600, color: '#f8fafc', letterSpacing: '-0.01em' }}>
                Cards that actually lead somewhere
              </h2>
            </div>
            <div style={{ fontSize: '14px', color: '#94a3b8' }}>
              The relevant cards are pulled forward.
            </div>
          </div>
          <MetricGrid metrics={data.metrics} alerts={data.alerts} onInvestigate={openMetricDrawer} />
        </section>

      </div>
      {renderedTarget && (
        <MetricInvestigationDrawer
          target={renderedTarget}
          alerts={data.alerts}
          isOpen={drawerOpen}
          onClose={closeDrawer}
        />
      )}
    </div>
  );
}
