import { ProductRiskPayload } from '../types/product_risk';

interface ProductRiskMatrixProps {
  data: ProductRiskPayload | null;
  error: string | null;
  loading: boolean;
}

function scoreColor(score: number): string {
  if (score >= 9) return '#ef4444';
  if (score >= 4) return '#f59e0b';
  return '#94a3b8';
}

function Pill({ label, bg, color }: { label: string; bg: string; color: string }) {
  return (
    <span
      style={{
        fontSize: '10px',
        fontWeight: 600,
        color,
        background: bg,
        padding: '2px 7px',
        borderRadius: '10px',
      }}
    >
      {label}
    </span>
  );
}

export function ProductRiskMatrix({ data, error, loading }: ProductRiskMatrixProps) {
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
      {/* Header */}
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
          Products at Risk
        </h2>
        {data && data.total_alerts > 0 && (
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
            {data.total_alerts}
          </span>
        )}
      </div>

      {/* Content */}
      <div style={{ padding: '14px 24px 20px', overflowY: 'auto', flex: 1 }}>
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
            <span style={{ fontSize: '12px', color: '#475569', fontStyle: 'italic' }}>
              Loading product risk&hellip;
            </span>
          </div>
        )}

        {!loading && (error || !data) && (
          <span style={{ fontSize: '12px', color: '#f59e0b' }}>Product risk data unavailable.</span>
        )}

        {!loading && !error && data && data.products.length === 0 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
            <span style={{ fontSize: '12px', color: '#334155', fontStyle: 'italic' }}>
              No active product risk.
            </span>
          </div>
        )}

        {!loading &&
          !error &&
          data &&
          data.products.length > 0 &&
          (() => {
            const visible = data.products.slice(0, 10);
            return (
              <>
                {visible.map((entry, idx) => {
                  const isLast = idx === visible.length - 1;
                  return (
                    <div
                      key={entry.product}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                        paddingBottom: '10px',
                        marginBottom: '10px',
                        borderBottom: isLast ? 'none' : '1px solid rgba(255,255,255,0.04)',
                      }}
                    >
                      {/* Row 1: product name + score + bar */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <span style={{ fontSize: '13px', fontWeight: 500, color: '#f1f5f9' }}>
                          {entry.product}
                        </span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <div
                            style={{
                              width: '48px',
                              height: '3px',
                              borderRadius: '2px',
                              background: 'rgba(255,255,255,0.06)',
                            }}
                          >
                            <div
                              style={{
                                height: '100%',
                                borderRadius: '2px',
                                width: `${Math.min(100, Math.round((entry.score / 15) * 100))}%`,
                                background: scoreColor(entry.score),
                              }}
                            />
                          </div>
                          <span
                            style={{
                              fontSize: '13px',
                              fontWeight: 700,
                              color: scoreColor(entry.score),
                              minWidth: '24px',
                              textAlign: 'right',
                            }}
                          >
                            {entry.score}
                          </span>
                        </div>
                      </div>

                      {/* Row 2: severity pills */}
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {entry.critical > 0 && (
                          <Pill
                            label={`${entry.critical} critical`}
                            bg="rgba(239,68,68,0.15)"
                            color="#ef4444"
                          />
                        )}
                        {entry.warn > 0 && (
                          <Pill
                            label={`${entry.warn} warn`}
                            bg="rgba(99,102,241,0.15)"
                            color="#6366f1"
                          />
                        )}
                        {entry.medium > 0 && (
                          <Pill
                            label={`${entry.medium} medium`}
                            bg="rgba(245,158,11,0.15)"
                            color="#f59e0b"
                          />
                        )}
                      </div>

                      {/* Row 3: domain tags */}
                      {entry.domains.length > 0 && (
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                          {entry.domains.map((d) => (
                            <span
                              key={d}
                              style={{
                                fontSize: '10px',
                                color: '#475569',
                                background: 'rgba(255,255,255,0.06)',
                                borderRadius: '4px',
                                padding: '2px 6px',
                              }}
                            >
                              {d}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
                {data.products.length > 10 && (
                  <div
                    style={{
                      textAlign: 'right',
                      fontSize: '11px',
                      color: '#334155',
                      fontStyle: 'italic',
                      marginTop: '4px',
                    }}
                  >
                    and {data.products.length - 10} more
                  </div>
                )}
              </>
            );
          })()}
      </div>
    </div>
  );
}
