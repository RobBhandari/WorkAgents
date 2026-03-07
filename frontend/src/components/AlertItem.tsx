import { AlertItem as AlertItemType } from '../types/trends';

interface AlertItemProps {
  alert: AlertItemType;
}

const SEVERITY_BG: Record<string, string> = {
  critical: 'rgba(239, 68, 68, 0.06)',
  warn: 'rgba(99, 102, 241, 0.06)',
  medium: 'rgba(245, 158, 11, 0.06)',
};

const SEVERITY_BORDER: Record<string, string> = {
  critical: 'rgba(239, 68, 68, 0.2)',
  warn: 'rgba(99, 102, 241, 0.2)',
  medium: 'rgba(245, 158, 11, 0.2)',
};

export function AlertItem({ alert }: AlertItemProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        padding: '10px 12px',
        background: SEVERITY_BG[alert.severity] ?? 'transparent',
        borderBottom: `1px solid ${SEVERITY_BORDER[alert.severity] ?? 'rgba(255,255,255,0.05)'}`,
        borderRadius: '6px',
        marginBottom: '4px',
      }}
    >
      <span style={{ fontSize: '14px', lineHeight: '20px', flexShrink: 0 }}>{alert.severity_emoji}</span>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: '12px', color: '#f1f5f9', lineHeight: 1.4, wordBreak: 'break-word' }}>
          {alert.message}
        </div>
        <div style={{ marginTop: '3px', display: 'flex', gap: '8px', fontSize: '11px', color: '#475569' }}>
          <span>{alert.dashboard}</span>
          <span>·</span>
          <span>{alert.metric_date}</span>
        </div>
      </div>
    </div>
  );
}
