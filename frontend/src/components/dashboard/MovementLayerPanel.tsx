// Movement Layer — directional changes in key engineering signals since the previous period.
// Backend endpoint not yet available. Rendered as a deliberate reserved panel.

export function MovementLayerPanel() {
  const rows = [
    { label: 'Security posture', width: 68 },
    { label: 'Deployment frequency', width: 82 },
    { label: 'Open vulnerability count', width: 55 },
    { label: 'Flow efficiency', width: 74 },
    { label: 'Ownership coverage', width: 61 },
  ];

  return (
    <div
      style={{
        background: '#111827',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '10px',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
      }}
    >
      {/* Header */}
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
          Movement Layer
        </h2>
        <span
          style={{
            fontSize: '9px',
            fontWeight: 600,
            color: '#1d4ed8',
            background: 'rgba(29,78,216,0.08)',
            border: '1px solid rgba(29,78,216,0.15)',
            padding: '2px 8px',
            borderRadius: '8px',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}
        >
          Reserved
        </span>
      </div>

      {/* Body */}
      <div
        style={{
          padding: '14px 22px 20px',
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: '0',
        }}
      >
        <p
          style={{
            fontSize: '11px',
            color: '#1e293b',
            lineHeight: 1.6,
            margin: '0 0 14px',
          }}
        >
          Week-over-week signal movement — magnitude and direction per metric.
        </p>
        {rows.map(({ label, width }, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 0',
              borderBottom: i < rows.length - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none',
            }}
          >
            <span style={{ fontSize: '11px', color: '#1e293b' }}>{label}</span>
            <div
              style={{
                height: '6px',
                width: `${width}px`,
                background: 'rgba(255,255,255,0.04)',
                borderRadius: '3px',
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
