// Narrative Layer — concise executive interpretation of current dashboard state.
// Backend endpoint not yet available. Rendered as a deliberate reserved panel.

export function NarrativeLayerPanel() {
  const lines = [92, 76, 85, 60, 70];

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
          Narrative
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
          gap: '10px',
        }}
      >
        <p
          style={{
            fontSize: '11px',
            color: '#1e293b',
            lineHeight: 1.6,
            margin: 0,
          }}
        >
          Auto-generated executive summary of current engineering health signals.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
          {lines.map((w, i) => (
            <div
              key={i}
              style={{
                height: '7px',
                width: `${w}%`,
                background: 'rgba(255,255,255,0.04)',
                borderRadius: '3px',
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
