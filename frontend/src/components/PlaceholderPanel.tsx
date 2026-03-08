interface PlaceholderPanelProps {
  title: string;
}

export function PlaceholderPanel({ title }: PlaceholderPanelProps) {
  return (
    <div
      style={{
        background: '#111827',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        padding: '20px 32px',
        display: 'flex',
        flexDirection: 'column',
        minHeight: '160px',
      }}
    >
      <h2
        style={{
          fontSize: '13px',
          fontWeight: 600,
          color: '#94a3b8',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          marginBottom: '14px',
        }}
      >
        {title}
      </h2>
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <span style={{ fontSize: '12px', color: '#334155', fontStyle: 'italic' }}>
          Coming soon
        </span>
      </div>
    </div>
  );
}
