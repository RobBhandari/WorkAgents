// Movement Layer — directional changes in key engineering signals since the previous period.
// Backend endpoint not yet available. Rendered as a deliberate preview panel.

export function MovementLayerPanel() {
  return (
    <div
      style={{
        background: '#0d1420',
        border: '1px solid rgba(255,255,255,0.04)',
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
            color: '#4b5a6e',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          Movement Layer
        </h2>
        <span
          style={{
            fontSize: '9px',
            fontWeight: 700,
            color: '#3b82f6',
            background: 'rgba(59,130,246,0.08)',
            border: '1px solid rgba(59,130,246,0.2)',
            padding: '2px 8px',
            borderRadius: '8px',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}
        >
          Coming Soon
        </span>
      </div>

      {/* Placeholder body */}
      <div
        style={{
          padding: '20px 24px 24px',
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}
      >
        <p
          style={{
            fontSize: '12px',
            color: '#334155',
            lineHeight: 1.6,
            margin: 0,
          }}
        >
          Week-over-week signal movement — magnitude and direction per metric.
        </p>
        {/* Skeleton rows */}
        {[72, 55, 88, 42, 64].map((w, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingBottom: i < 4 ? '10px' : 0,
              borderBottom: i < 4 ? '1px solid rgba(255,255,255,0.03)' : 'none',
            }}
          >
            <div
              style={{
                height: '8px',
                width: `${w}px`,
                background: 'rgba(255,255,255,0.04)',
                borderRadius: '4px',
              }}
            />
            <div
              style={{
                height: '8px',
                width: '28px',
                background: 'rgba(255,255,255,0.04)',
                borderRadius: '4px',
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
