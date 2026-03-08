import { MetricGrid } from './components/MetricGrid';
import { ActiveRisksSummary } from './components/ActiveRisksSummary';
import { HealthScore } from './components/HealthScore';
import { MovementLayerPanel } from './components/dashboard/MovementLayerPanel';
import { NarrativeLayerPanel } from './components/NarrativeLayerPanel';
import { SystemShapeRadar } from './components/SystemShapeRadar';
import { SignalsPanel } from './components/SignalsPanel';
import { useTrendsData } from './hooks/useTrendsData';
import { useHealthScore } from './hooks/useHealthScore';
import { useSignalsData } from './hooks/useSignalsData';

function parseDataAge(timestamp: string): { isStale: boolean; label: string } {
  const parsed = new Date(timestamp.replace(' at ', ' '));
  if (isNaN(parsed.getTime())) return { isStale: false, label: 'live' };
  const ageMs = Date.now() - parsed.getTime();
  const ageHours = ageMs / (1000 * 60 * 60);
  if (ageHours < 24) return { isStale: false, label: 'live' };
  const ageDisplay = ageHours < 48 ? `${Math.round(ageHours)}h old` : `${Math.round(ageHours / 24)}d old`;
  return { isStale: true, label: `stale · ${ageDisplay}` };
}

// Shared panel shell.
function PanelShell({ title, badge, accent, children }: {
  title: string;
  badge?: React.ReactNode;
  accent?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: '#111827',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '10px',
        borderTop: accent ? `2px solid ${accent}` : '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        height: '100%',
      }}
    >
      <div
        style={{
          padding: '18px 22px 0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
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
          {title}
        </h2>
        {badge}
      </div>
      <div style={{ padding: '14px 22px 20px', overflowY: 'auto', flex: 1 }}>
        {children}
      </div>
    </div>
  );
}

export default function App() {
  const { data, error, loading } = useTrendsData();
  const { data: healthData, error: healthError, loading: healthLoading } = useHealthScore();
  const { data: signalsData, error: signalsError, loading: signalsLoading } = useSignalsData();

  if (loading) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f172a', color: '#475569', fontSize: '13px' }}>
      Loading...
    </div>
  );

  if (error || !data) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f172a', color: '#ef4444', fontSize: '13px' }}>
      {error ?? 'No data'}
    </div>
  );

  const { isStale, label: ageLabel } = parseDataAge(data.timestamp);
  const activeAlerts = data.alerts.length;
  const worsening = data.metrics.filter((m) => m.ragColor === '#ef4444').length;
  const improving = data.metrics.filter((m) => m.ragColor === '#10b981').length;

  // Split metrics: show top 6 as featured, rest in extended section
  const featuredMetrics = data.metrics.slice(0, 6);
  const extendedMetrics = data.metrics.slice(6);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#0f172a', fontFamily: 'inherit' }}>

      {/* ── Header ── */}
      <header
        style={{
          background: '#0f172a',
          borderBottom: '1px solid rgba(255,255,255,0.05)',
          padding: '16px 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: '#38bdf8',
              flexShrink: 0,
            }}
          />
          <div>
            <h1 style={{ fontSize: '15px', fontWeight: 700, color: '#e2e8f0', letterSpacing: '-0.01em', lineHeight: 1 }}>
              Engineering Command Centre
            </h1>
            <p style={{ fontSize: '11px', color: '#334155', marginTop: '3px' }}>
              {data.timestamp}
            </p>
          </div>
        </div>
        <div
          style={{
            fontSize: '11px',
            color: isStale ? '#f59e0b' : '#334155',
            background: isStale ? 'rgba(245,158,11,0.07)' : 'rgba(255,255,255,0.03)',
            border: `1px solid ${isStale ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.05)'}`,
            padding: '4px 10px',
            borderRadius: '6px',
            letterSpacing: '0.02em',
          }}
        >
          {isStale ? ageLabel : 'live'}
        </div>
      </header>

      {/* ── HERO: Executive Status Surface ── */}
      <div
        style={{
          margin: '20px 32px 0',
          background: '#111827',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: '12px',
          display: 'flex',
          minHeight: '220px',
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        {/* Left — Health score instrument */}
        <div
          style={{
            flex: '0 0 52%',
            padding: '32px 40px',
            borderRight: '1px solid rgba(255,255,255,0.06)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            position: 'relative',
          }}
        >
          <HealthScore
            data={healthData}
            error={healthError}
            loading={healthLoading}
            activeAlerts={activeAlerts}
            worsening={worsening}
            improving={improving}
            inlined
          />
        </div>

        {/* Right — Signals + status blocks */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            minWidth: 0,
          }}
        >
          {/* Signals area */}
          <div
            style={{
              flex: 1,
              padding: '24px 28px 16px',
              overflowY: 'auto',
              minHeight: 0,
            }}
          >
            <SignalsPanel data={signalsData} error={signalsError} loading={signalsLoading} inlined />
          </div>

          {/* Status bar */}
          <div
            style={{
              borderTop: '1px solid rgba(255,255,255,0.05)',
              padding: '12px 28px',
              display: 'flex',
              gap: '0',
              flexShrink: 0,
            }}
          >
            <StatusBlock
              label="Active Alerts"
              value={activeAlerts}
              color={activeAlerts > 0 ? '#ef4444' : '#334155'}
            />
            <div style={{ width: '1px', background: 'rgba(255,255,255,0.05)', margin: '0 20px', alignSelf: 'stretch' }} />
            <StatusBlock
              label="Data Freshness"
              value={isStale ? ageLabel.split('·')[1]?.trim() ?? 'stale' : 'live'}
              color={isStale ? '#f59e0b' : '#10b981'}
            />
            <div style={{ width: '1px', background: 'rgba(255,255,255,0.05)', margin: '0 20px', alignSelf: 'stretch' }} />
            <StatusBlock
              label="Metrics Tracked"
              value={data.metrics.length}
              color="#475569"
            />
          </div>
        </div>
      </div>

      {/* ── INTELLIGENCE ROW: Alert Layer + System Shape ── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '16px',
          padding: '16px 32px 0',
        }}
      >
        {/* Alert Layer */}
        <PanelShell
          title="Active Risks"
          accent={activeAlerts > 0 ? 'rgba(239,68,68,0.6)' : undefined}
          badge={
            activeAlerts > 0 ? (
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: '#ef4444',
                  background: 'rgba(239,68,68,0.1)',
                  border: '1px solid rgba(239,68,68,0.2)',
                  padding: '2px 8px',
                  borderRadius: '10px',
                }}
              >
                {activeAlerts}
              </span>
            ) : undefined
          }
        >
          <ActiveRisksSummary alerts={data.alerts} />
        </PanelShell>

        {/* System Shape */}
        <div
          style={{
            background: '#111827',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: '10px',
            minHeight: '300px',
          }}
        >
          <SystemShapeRadar metrics={data.metrics} />
        </div>
      </div>

      {/* ── PREVIEW ROW: Movement + Narrative ── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '16px',
          padding: '16px 32px 0',
        }}
      >
        <MovementLayerPanel />
        <NarrativeLayerPanel />
      </div>

      {/* ── METRICS: Entry Points ── */}
      <div
        style={{
          margin: '20px 32px 32px',
          background: '#111827',
          border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: '10px',
          padding: '20px 24px 24px',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '16px',
          }}
        >
          <h2
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: '#334155',
              textTransform: 'uppercase',
              letterSpacing: '0.09em',
            }}
          >
            Metric Entry Points
          </h2>
          <span style={{ fontSize: '11px', color: '#1e293b' }}>
            {data.metrics.length} metrics
          </span>
        </div>
        <MetricGrid metrics={featuredMetrics} />
        {extendedMetrics.length > 0 && (
          <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
            <MetricGrid metrics={extendedMetrics} />
          </div>
        )}
      </div>

    </div>
  );
}

// Small status block used in the hero status bar.
function StatusBlock({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
      <span style={{ fontSize: '15px', fontWeight: 700, color, lineHeight: 1, letterSpacing: '-0.02em' }}>
        {value}
      </span>
      <span style={{ fontSize: '10px', color: '#334155', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </span>
    </div>
  );
}
