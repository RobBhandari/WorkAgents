import { MetricItem } from '../types/trends';
import { MetricCard } from './MetricCard';

interface MetricGridProps {
  metrics: MetricItem[];
}

export function MetricGrid({ metrics }: MetricGridProps) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
        gap: '12px',
      }}
    >
      {metrics.map((item) => (
        <MetricCard key={item.id} item={item} />
      ))}
    </div>
  );
}
