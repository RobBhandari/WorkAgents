import { MetricGrid } from './components/MetricGrid';
import { AlertList } from './components/AlertList';
import { HealthScore } from './components/HealthScore';
import { PlaceholderPanel } from './components/PlaceholderPanel';
import { ProductRiskMatrix } from './components/ProductRiskMatrix';
import { SignalsPanel } from './components/SignalsPanel';
import { useTrendsData } from './hooks/useTrendsData';
import { useHealthScore } from './hooks/useHealthScore';
import { useProductRisk } from './hooks/useProductRisk';
import { useSignalsData } from './hooks/useSignalsData';

function parseDataAge(timestamp: string): { isStale: boolean; label: string } {
  // timestamp format: "March 07, 2026 at 22:47"
  const parsed = new Date(timestamp.replace(' at ', ' '));
  if (isNaN(parsed.getTime())) return { isStale: false, label: 'live' };
  const ageMs = Date.now() - parsed.getTime();
  const ageHours = ageMs / (1000 * 60 * 60);
  if (ageHours < 24) return { isStale: false, label: 'live' };
  const ageDisplay = ageHours < 48 ? `${Math.round(ageHours)}h old` : `${Math.round(ageHours / 24)}d old`;
  return { isStale: true, label: `stale · ${ageDisplay}` };
}

// Shared panel shell used for command-grid cells.
function PanelShell({ title, badge, children }: {
  title: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: '#111827',
        border: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
      }}
    >
      <div
        style={{
          padding: '16px 24px 0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <h2
          style={{
            fontSize: '13px',
            fontWeight: 600,
            color: '#94a3b8',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          {title}
        </h2>
        {badge}
      </div>
      <div style={{ padding: '14px 24px 20px', overflowY: 'auto', flex: 1 }}>
        {children}
      </div>
    </div>
  );
}

export default function App() {
  const { data, error, loading } = useTrendsData();
  const { data: healthData, error: healthError, loading: healthLoading } = useHealthScore();
  const { data: signalsData, error: signalsError, loading: signalsLoading } = useSignalsData();
  const { data: productRiskData, error: productRiskError, loading: productRiskLoading } = useProductRisk();

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

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#0f172a' }}>

      {/* ── Header ── */}
      <header
        style={{
          background: '#0f172a',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          padding: '20px 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div>
          <h1 style={{ fontSize: '18px', fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.01em' }}>
            Engineering Command Centre
          </h1>
          <p style={{ fontSize: '12px', color: '#475569', marginTop: '2px' }}>
            Updated {data.timestamp}
          </p>
        </div>
        {(() => {
          const { isStale, label } = parseDataAge(data.timestamp);
          return (
            <div
              style={{
                fontSize: '11px',
                color: isStale ? '#f59e0b' : '#475569',
                background: isStale ? 'rgba(245, 158, 11, 0.08)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${isStale ? 'rgba(245, 158, 11, 0.25)' : 'rgba(255,255,255,0.07)'}`,
                padding: '4px 10px',
                borderRadius: '6px',
              }}
            >
              {isStale ? label : `live · ${new Date().toLocaleTimeString()}`}
            </div>
          );
        })()}
      </header>

      {/* ── Engineering Health — full-width panel ── */}
      <HealthScore data={healthData} error={healthError} loading={healthLoading} />

      {/* ── Key Signals — full-width panel ── */}
      <SignalsPanel data={signalsData} error={signalsError} loading={signalsLoading} />

      {/* ── Command grid — 2×2 ── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '1px',
          background: 'rgba(255,255,255,0.06)',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        {/* Row 1 left — Active Risks */}
        <PanelShell
          title="Active Risks"
          badge={
            data.alerts.length > 0 ? (
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: '#ef4444',
                  background: 'rgba(239,68,68,0.12)',
                  padding: '2px 8px',
                  borderRadius: '10px',
                }}
              >
                {data.alerts.length}
              </span>
            ) : undefined
          }
        >
          <AlertList alerts={data.alerts} />
        </PanelShell>

        {/* Row 1 right — Products at Risk */}
        <ProductRiskMatrix data={productRiskData} error={productRiskError} loading={productRiskLoading} />

        {/* Row 2 left — Movement Layer */}
        <PlaceholderPanel title="Movement Layer" />

        {/* Row 2 right — Narrative Layer */}
        <PlaceholderPanel title="Narrative Layer" />
      </div>

      {/* ── Metrics section — full-width ── */}
      <div
        style={{
          padding: '24px 32px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <div
          style={{
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <h2
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: '#94a3b8',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            Metrics
          </h2>
          <span style={{ fontSize: '12px', color: '#334155' }}>{data.metrics.length} metrics</span>
        </div>
        <MetricGrid metrics={data.metrics} />
      </div>

    </div>
  );
}
