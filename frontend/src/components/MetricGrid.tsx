import { useState } from 'react';
import { MetricItem, AlertItem } from '../types/trends';
import { MetricCard } from './MetricCard';
import { WHY_IT_MATTERS } from '../utils/buildDrawerTarget';

interface MetricGridProps {
  metrics: MetricItem[];
  alerts?: AlertItem[];
  onInvestigate?: (item: MetricItem) => void;
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

export function MetricGrid({ metrics, alerts = [], onInvestigate }: MetricGridProps) {
  const [expanded, setExpanded] = useState(false);

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

  const PINNED_METRIC_IDS = ['bugs'];
  const VISIBLE_COUNT = 6;

  const pinnedMetrics = sorted.filter((m) => PINNED_METRIC_IDS.includes(m.id));
  const dynamicMetrics = sorted.filter((m) => !PINNED_METRIC_IDS.includes(m.id));
  const dynamicVisible = dynamicMetrics.slice(0, VISIBLE_COUNT - pinnedMetrics.length);
  const visibleMetrics = [...pinnedMetrics, ...dynamicVisible];
  const hiddenMetrics = dynamicMetrics.slice(VISIBLE_COUNT - pinnedMetrics.length);

  return (
    <div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, 1fr)',
        gap: '16px',
      }}>
        {visibleMetrics.map((item) => (
          <MetricCard
            key={item.id}
            item={item}
            isAlertLinked={linkedIds.has(item.id)}
            narrativeSentence={narrativeFor(item)}
            whyItMatters={WHY_IT_MATTERS[item.id]?.headline}
            onInvestigate={onInvestigate}
          />
        ))}
        {expanded && hiddenMetrics.map((item) => (
          <MetricCard
            key={item.id}
            item={item}
            isAlertLinked={linkedIds.has(item.id)}
            narrativeSentence={narrativeFor(item)}
            whyItMatters={WHY_IT_MATTERS[item.id]?.headline}
            onInvestigate={onInvestigate}
          />
        ))}
      </div>
      {hiddenMetrics.length > 0 && (
        <button
          onClick={() => setExpanded((v) => !v)}
          style={{
            marginTop: '12px',
            background: 'none',
            border: 'none',
            padding: '4px 0',
            cursor: 'pointer',
            fontSize: '13px',
            color: '#64748b',
            letterSpacing: '0.01em',
          }}
        >
          {expanded
            ? 'Show fewer'
            : `+${hiddenMetrics.length} more metric${hiddenMetrics.length !== 1 ? 's' : ''}`}
        </button>
      )}
    </div>
  );
}
