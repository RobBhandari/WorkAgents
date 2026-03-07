import { MetricGrid } from './components/MetricGrid';
import { AlertList } from './components/AlertList';
import { useTrendsData } from './hooks/useTrendsData';

export default function App() {
  const { data, error, loading } = useTrendsData();

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
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
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
            Engineering Metrics
          </h1>
          <p style={{ fontSize: '12px', color: '#475569', marginTop: '2px' }}>
            Executive Trends — {data.timestamp}
          </p>
        </div>
        <div
          style={{
            fontSize: '11px',
            color: '#475569',
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.07)',
            padding: '4px 10px',
            borderRadius: '6px',
          }}
        >
          live · {new Date().toLocaleTimeString()}
        </div>
      </header>

      {/* Body */}
      <main
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: '1fr 340px',
          gap: '0',
          minHeight: 0,
        }}
      >
        {/* Metric grid pane */}
        <div
          style={{
            padding: '24px 28px',
            overflowY: 'auto',
            borderRight: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ fontSize: '13px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Metrics
            </h2>
            <span style={{ fontSize: '12px', color: '#334155' }}>{data.metrics.length} cards</span>
          </div>
          <MetricGrid metrics={data.metrics} />
        </div>

        {/* Alerts pane */}
        <div
          style={{
            padding: '24px 20px',
            overflowY: 'auto',
            background: '#111827',
          }}
        >
          <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ fontSize: '13px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Active Alerts
            </h2>
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
          </div>
          <AlertList alerts={data.alerts} />
        </div>
      </main>
    </div>
  );
}
