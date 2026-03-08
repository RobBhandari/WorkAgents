import { MetricItem, AlertItem } from '../types/trends';
import { MetricCard } from './MetricCard';

interface MetricGridProps {
  metrics: MetricItem[];
  alerts?: AlertItem[];
}

function narrativeFor(item: MetricItem): string | undefined {
  if (item.current === '') return undefined; // launcher
  const { ragColor, cssClass } = item;
  if (ragColor === '#ef4444' && cssClass === 'trend-up')   return 'Rising and above tolerance threshold.';
  if (ragColor === '#ef4444' && cssClass === 'trend-down') return 'Improving but still below target.';
  if (ragColor === '#ef4444')                              return 'Below target — action required.';
  if (ragColor === '#f59e0b' && cssClass === 'trend-up')   return 'Heading in the wrong direction — watch closely.';
  if (ragColor === '#f59e0b' && cssClass === 'trend-down') return 'Recovering — not yet at target.';
  if (ragColor === '#f59e0b')                              return 'Within amber range — monitor closely.';
  if (ragColor === '#10b981')                              return 'Within healthy range.';
  return undefined;
}

export function MetricGrid({ metrics, alerts = [] }: MetricGridProps) {
  // Build set of alert-linked metric IDs by matching metric.id against alert.dashboard
  const linkedIds = new Set(alerts.map((a) => a.dashboard).filter(Boolean));

  // Sort: alert-linked first, then red → amber → green, then non-stable before stable
  const SEV: Record<string, number> = { '#ef4444': 0, '#f59e0b': 1, '#10b981': 2 };
  const sorted = [...metrics].sort((a, b) => {
    const aLinked = linkedIds.has(a.id) ? 0 : 1;
    const bLinked = linkedIds.has(b.id) ? 0 : 1;
    if (aLinked !== bLinked) return aLinked - bLinked;
    const sevDiff = (SEV[a.ragColor] ?? 3) - (SEV[b.ragColor] ?? 3);
    if (sevDiff !== 0) return sevDiff;
    // Within same severity: non-stable before stable
    const aStable = a.cssClass === 'trend-stable' ? 1 : 0;
    const bStable = b.cssClass === 'trend-stable' ? 1 : 0;
    return aStable - bStable;
  });

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(2, 1fr)',
      gap: '16px',
    }}>
      {sorted.slice(0, 6).map((item) => (
        <MetricCard
          key={item.id}
          item={item}
          isAlertLinked={linkedIds.has(item.id)}
          narrativeSentence={narrativeFor(item)}
        />
      ))}
    </div>
  );
}
