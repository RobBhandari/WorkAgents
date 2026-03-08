// Narrative Layer — concise executive interpretation of current dashboard state.
// Backend endpoint not yet available. Rendered as a deliberate preview panel.

export function NarrativeLayerPanel() {
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
          Narrative
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
          Auto-generated executive summary of current engineering health signals.
        </p>
        {/* Skeleton text lines */}
        {[90, 70, 82, 58].map((w, i) => (
          <div
            key={i}
            style={{
              height: '8px',
              width: `${w}%`,
              background: 'rgba(255,255,255,0.04)',
              borderRadius: '4px',
            }}
          />
        ))}
      </div>
    </div>
  );
}
