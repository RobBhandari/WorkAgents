import { AlertItem as AlertItemType } from '../types/trends';
import { AlertItem } from './AlertItem';

interface AlertListProps {
  alerts: AlertItemType[];
}

const SEVERITY_ORDER = ['critical', 'warn', 'medium'] as const;

const SEVERITY_LABEL: Record<string, string> = {
  critical: 'Critical',
  warn: 'Warning',
  medium: 'Medium',
};

const SEVERITY_COLOR: Record<string, string> = {
  critical: '#ef4444',
  warn: '#6366f1',
  medium: '#f59e0b',
};

export function AlertList({ alerts }: AlertListProps) {
  const grouped = SEVERITY_ORDER.map((sev) => ({
    severity: sev,
    items: alerts.filter((a) => a.severity === sev),
  })).filter((g) => g.items.length > 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {grouped.map(({ severity, items }) => (
        <div key={severity}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '8px',
              paddingBottom: '6px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: SEVERITY_COLOR[severity],
                flexShrink: 0,
              }}
            />
            <span style={{ fontSize: '11px', fontWeight: 700, color: SEVERITY_COLOR[severity], textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              {SEVERITY_LABEL[severity]}
            </span>
            <span
              style={{
                marginLeft: 'auto',
                fontSize: '11px',
                fontWeight: 700,
                color: '#475569',
                background: 'rgba(255,255,255,0.05)',
                padding: '1px 7px',
                borderRadius: '10px',
              }}
            >
              {items.length}
            </span>
          </div>
          <div>
            {items.map((alert, i) => (
              <AlertItem key={`${alert.dashboard}-${alert.metric_name}-${alert.project_name}-${i}`} alert={alert} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
