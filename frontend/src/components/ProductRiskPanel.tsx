import { ProductRiskPayload, ProductRiskEntry } from '../types/product_risk';

interface ProductRiskPanelProps {
  data: ProductRiskPayload | null;
  loading: boolean;
  error: string | null;
}

const SCORE_COLOR = (score: number): string => {
  if (score >= 6) return '#ef4444';
  if (score >= 3) return '#f59e0b';
  return '#34d399';
};

function RiskRow({ entry }: { entry: ProductRiskEntry }) {
  const color = SCORE_COLOR(entry.score);
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 120px auto auto auto 1fr',
      alignItems: 'center',
      gap: '16px',
      padding: '12px 16px',
      borderRadius: '12px',
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.05)',
    }}>
      {/* Product name */}
      <span style={{ fontSize: '14px', fontWeight: 500, color: '#f1f5f9' }}>
        {entry.product}
      </span>

      {/* Score bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{ flex: 1, height: '6px', borderRadius: '9999px', background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            borderRadius: '9999px',
            width: `${Math.min(100, (entry.score / 10) * 100)}%`,
            background: color,
            transition: 'width 0.6s ease',
          }} />
        </div>
        <span style={{ fontSize: '13px', fontWeight: 600, color, minWidth: '20px', textAlign: 'right' }}>
          {entry.score}
        </span>
      </div>

      {/* Critical */}
      {entry.critical > 0 ? (
        <span style={{ fontSize: '12px', fontWeight: 500, color: '#fca5a5', background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.20)', borderRadius: '9999px', padding: '2px 8px', whiteSpace: 'nowrap' }}>
          {entry.critical} crit
        </span>
      ) : <span />}

      {/* Warn */}
      {entry.warn > 0 ? (
        <span style={{ fontSize: '12px', fontWeight: 500, color: '#fdba74', background: 'rgba(251,146,60,0.10)', border: '1px solid rgba(251,146,60,0.20)', borderRadius: '9999px', padding: '2px 8px', whiteSpace: 'nowrap' }}>
          {entry.warn} high
        </span>
      ) : <span />}

      {/* Medium */}
      {entry.medium > 0 ? (
        <span style={{ fontSize: '12px', fontWeight: 500, color: '#fcd34d', background: 'rgba(245,158,11,0.10)', border: '1px solid rgba(245,158,11,0.20)', borderRadius: '9999px', padding: '2px 8px', whiteSpace: 'nowrap' }}>
          {entry.medium} med
        </span>
      ) : <span />}

      {/* Domains */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', justifyContent: 'flex-end' }}>
        {entry.domains.map((d) => (
          <span key={d} style={{ fontSize: '11px', color: '#64748b', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '6px', padding: '1px 6px' }}>
            {d.replace(/-/g, ' ')}
          </span>
        ))}
      </div>
    </div>
  );
}

export function ProductRiskPanel({ data, loading, error }: ProductRiskPanelProps) {
  return (
    <section style={{
      borderRadius: '28px',
      border: '1px solid rgba(255,255,255,0.10)',
      background: '#0b1626',
      padding: '24px',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '16px', marginBottom: '20px' }}>
        <div>
          <div style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.24em', color: '#94a3b8', fontWeight: 600 }}>
            Per-product risk
          </div>
          <h2 style={{ margin: '8px 0 0', fontSize: '24px', fontWeight: 600, color: '#f8fafc', letterSpacing: '-0.01em' }}>
            Product risk breakdown
          </h2>
        </div>
        {data && (
          <div style={{ fontSize: '14px', color: '#94a3b8', flexShrink: 0 }}>
            {data.total_alerts} alert{data.total_alerts !== 1 ? 's' : ''} · {data.products.length} product{data.products.length !== 1 ? 's' : ''}
          </div>
        )}
      </div>

      {loading && (
        <div style={{ fontSize: '14px', color: '#94a3b8', fontStyle: 'italic', padding: '8px 0' }}>
          Loading product risk…
        </div>
      )}

      {!loading && error && (
        <div style={{ fontSize: '14px', color: '#f59e0b', padding: '8px 0' }}>
          {error}
        </div>
      )}

      {!loading && !error && data && data.products.length === 0 && (
        <div style={{ fontSize: '14px', color: '#475569', padding: '8px 0' }}>
          No products with active risk signals.
        </div>
      )}

      {!loading && !error && data && data.products.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {data.products.map((entry) => (
            <RiskRow key={entry.product} entry={entry} />
          ))}
        </div>
      )}
    </section>
  );
}
