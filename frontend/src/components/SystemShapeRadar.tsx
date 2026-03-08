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

// Compute SVG polygon point for axis i at value v (0–100).
function radarPoint(
  cx: number,
  cy: number,
  radius: number,
  index: number,
  total: number,
  value: number,
): [number, number] {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const r = (value / 100) * radius;
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

function axisLabelPoint(
  cx: number,
  cy: number,
  radius: number,
  index: number,
  total: number,
): [number, number] {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const r = radius + 24;
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

export function SystemShapeRadar({ metrics, loading }: SystemShapeRadarProps) {
  const panelStyle: React.CSSProperties = {
    background: '#111827',
    border: '1px solid rgba(255,255,255,0.06)',
    display: 'flex',
    flexDirection: 'column',
    minHeight: 0,
    height: '100%',
  };

  const headerStyle: React.CSSProperties = {
    padding: '16px 24px 0',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexShrink: 0,
  };

  const titleStyle: React.CSSProperties = {
    fontSize: '13px',
    fontWeight: 600,
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  };

  const contentStyle: React.CSSProperties = {
    padding: '14px 24px 20px',
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  const centeredText = (msg: string) => (
    <span style={{ fontSize: '12px', color: '#475569', fontStyle: 'italic' }}>{msg}</span>
  );

  if (loading) {
    return (
      <div style={panelStyle}>
        <div style={headerStyle}><h2 style={titleStyle}>System Shape</h2></div>
        <div style={contentStyle}>{centeredText('Evaluating system shape\u2026')}</div>
      </div>
    );
  }

  if (!metrics || metrics.length === 0) {
    return (
      <div style={panelStyle}>
        <div style={headerStyle}><h2 style={titleStyle}>System Shape</h2></div>
        <div style={contentStyle}>{centeredText('System shape unavailable.')}</div>
      </div>
    );
  }

  const scores = domainScores(metrics);
  const validCount = scores.filter((s) => s !== null).length;

  if (validCount < 3) {
    return (
      <div style={panelStyle}>
        <div style={headerStyle}><h2 style={titleStyle}>System Shape</h2></div>
        <div style={contentStyle}>{centeredText('Insufficient data to evaluate system shape.')}</div>
      </div>
    );
  }

  // SVG dimensions — chart fills the panel with room for labels.
  const size = 340;
  const pad = 32;          // extra canvas on each side for label text
  const cx = size / 2;     // chart center is the middle of the 340 square
  const cy = size / 2;
  const radius = 118;
  const n = DOMAINS.length;
  const gridLevels = [25, 50, 75, 100];

  // Filled polygon — use 0 for null domains.
  const filledPoints = scores.map((s, i) =>
    radarPoint(cx, cy, radius, i, n, s ?? 0),
  );
  const polygonPoints = filledPoints.map(([x, y]) => `${x},${y}`).join(' ');

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>
        <h2 style={titleStyle}>System Shape</h2>
      </div>
      <div style={{ ...contentStyle, padding: '10px 24px 16px' }}>
        <svg
          viewBox={`${-pad} ${-pad} ${size + pad * 2} ${size + pad * 2}`}
          style={{ width: '100%', maxWidth: '340px', overflow: 'hidden' }}
          aria-label="System shape radar chart"
        >
          {/* Radial grid lines */}
          {gridLevels.map((level) => {
            const pts = Array.from({ length: n }, (_, i) =>
              radarPoint(cx, cy, radius, i, n, level),
            );
            return (
              <polygon
                key={level}
                points={pts.map(([x, y]) => `${x},${y}`).join(' ')}
                fill="none"
                stroke="rgba(148,163,184,0.15)"
                strokeWidth="1"
              />
            );
          })}

          {/* Axis spokes */}
          {DOMAINS.map((_, i) => {
            const [x, y] = radarPoint(cx, cy, radius, i, n, 100);
            return (
              <line
                key={i}
                x1={cx}
                y1={cy}
                x2={x}
                y2={y}
                stroke="rgba(148,163,184,0.25)"
                strokeWidth="1"
              />
            );
          })}

          {/* Filled radar polygon */}
          <polygon
            points={polygonPoints}
            fill="rgba(56,189,248,0.20)"
            stroke="#38bdf8"
            strokeWidth="2"
            strokeLinejoin="round"
          />

          {/* Axis dots */}
          {filledPoints.map(([x, y], i) => (
            <circle
              key={i}
              cx={x}
              cy={y}
              r="2.5"
              fill="#38bdf8"
            />
          ))}

          {/* Axis labels */}
          {DOMAINS.map(({ label }, i) => {
            const [lx, ly] = axisLabelPoint(cx, cy, radius, i, n);
            const score = scores[i];
            const scoreColor =
              score == null ? '#334155'
              : score >= 80 ? '#10b981'
              : score >= 55 ? '#f59e0b'
              : '#ef4444';
            return (
              <text
                key={i}
                x={lx}
                y={ly}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize="11"
                fill="#94a3b8"
                fontFamily="inherit"
              >
                <tspan x={lx} dy="0">{label}</tspan>
                {score != null && (
                  <tspan x={lx} dy="12" fontSize="9" fill={scoreColor} fontWeight="700">
                    {Math.round(score)}
                  </tspan>
                )}
              </text>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
