import { MetricItem } from '../types/trends';

interface SystemShapeRadarProps {
  metrics: MetricItem[];
  loading?: boolean;
}

// Fixed domain definitions — order determines axis position on the radar.
const DOMAINS = [
  { label: 'Security',        ids: ['security', 'security-infra', 'exploitable'] },
  { label: 'Delivery',        ids: ['deployment', 'flow'] },
  { label: 'Infrastructure',  ids: ['security-infra', 'risk'] },
  { label: 'Quality',         ids: ['bugs', 'exploitable'] },
  { label: 'Collaboration',   ids: ['collaboration'] },
  { label: 'Ownership',       ids: ['ownership'] },
] as const;

const RAG_SCORE: Record<string, number> = {
  '#10b981': 100,  // green
  '#f59e0b': 65,   // amber
  '#ef4444': 30,   // red
};

function domainScores(metrics: MetricItem[]): (number | null)[] {
  return DOMAINS.map(({ ids }) => {
    const scores = ids
      .map((id) => metrics.find((m) => m.id === id))
      .filter((m): m is MetricItem => m != null)
      .map((m) => RAG_SCORE[m.ragColor] ?? null)
      .filter((s): s is number => s != null);
    if (scores.length === 0) return null;
    const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
    return Math.min(100, Math.max(0, avg));
  });
}

function radarPoint(
  cx: number, cy: number, radius: number,
  index: number, total: number, value: number,
): [number, number] {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const r = (value / 100) * radius;
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

function axisLabelPoint(
  cx: number, cy: number, radius: number,
  index: number, total: number,
): [number, number] {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const r = radius + 26;
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

function axisEndPoint(
  cx: number, cy: number, radius: number,
  index: number, total: number,
): [number, number] {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  return [cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)];
}

const centeredText = (msg: string) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', height: '100%' }}>
    <span style={{ fontSize: '12px', color: '#475569', fontStyle: 'italic' }}>{msg}</span>
  </div>
);

export function SystemShapeRadar({ metrics, loading }: SystemShapeRadarProps) {
  if (loading) return centeredText('Evaluating system shape\u2026');
  if (!metrics || metrics.length === 0) return centeredText('System shape unavailable.');

  const scores = domainScores(metrics);
  const validCount = scores.filter((s) => s !== null).length;
  if (validCount < 3) return centeredText('Insufficient data to evaluate system shape.');

  const size    = 340;
  const pad     = 36;
  const cx      = size / 2;
  const cy      = size / 2;
  const radius  = 118;
  const n       = DOMAINS.length;
  // Circular grid levels — matching the reference's circle rings
  const gridLevels = [25, 50, 75, 100];

  const filledPoints = scores.map((s, i) =>
    radarPoint(cx, cy, radius, i, n, s ?? 0),
  );
  const polygonPoints = filledPoints.map(([x, y]) => `${x},${y}`).join(' ');

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', height: '100%' }}>
      <svg
        viewBox={`${-pad} ${-pad} ${size + pad * 2} ${size + pad * 2}`}
        style={{ width: '100%', height: 'auto', overflow: 'visible' }}
        aria-label="System shape radar chart"
      >
        {/* Circular grid rings — replacing polygons for premium feel */}
        {gridLevels.map((level) => (
          <circle
            key={level}
            cx={cx}
            cy={cy}
            r={(level / 100) * radius}
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="1"
          />
        ))}

        {/* Axis spokes */}
        {DOMAINS.map((_, i) => {
          const [x, y] = axisEndPoint(cx, cy, radius, i, n);
          return (
            <line
              key={i}
              x1={cx} y1={cy} x2={x} y2={y}
              stroke="rgba(255,255,255,0.10)"
              strokeWidth="1"
            />
          );
        })}

        {/* Filled radar polygon */}
        <polygon
          points={polygonPoints}
          fill="rgba(56,189,248,0.18)"
          stroke="rgba(125,211,252,0.90)"
          strokeWidth="2"
          strokeLinejoin="round"
        />

        {/* Axis vertex dots */}
        {filledPoints.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r="3" fill="#38bdf8" opacity="0.9" />
        ))}

        {/* Axis labels */}
        {DOMAINS.map(({ label }, i) => {
          const [lx, ly] = axisLabelPoint(cx, cy, radius, i, n);
          const score = scores[i];
          const scoreColor =
            score == null ? '#475569'
            : score >= 80  ? '#34d399'
            : score >= 55  ? '#fcd34d'
            :                '#f87171';
          return (
            <text
              key={i}
              x={lx} y={ly}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="11"
              fill="rgba(226,232,240,0.85)"
              fontFamily="inherit"
            >
              <tspan x={lx} dy="0">{label}</tspan>
              {score != null && (
                <tspan x={lx} dy="13" fontSize="10" fill={scoreColor} fontWeight="700">
                  {Math.round(score)}
                </tspan>
              )}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
