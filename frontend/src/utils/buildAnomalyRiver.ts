import { MetricItem } from '../types/trends';

export interface AnomalyRiverRow {
  domain: string;
  values: number[]; // 0–1 normalised pressure intensity, up to 10 intervals
  metricIds: string[];
}

/**
 * Per-domain metric configuration.
 * pressureOnRise: true  → higher metric value = more pressure (e.g. bug count)
 * pressureOnRise: false → lower metric value = more pressure (e.g. build success rate)
 */
const DOMAIN_METRICS: Record<string, { id: string; pressureOnRise: boolean }[]> = {
  Security: [
    { id: 'exploitable', pressureOnRise: true },
    { id: 'security',    pressureOnRise: true },
    { id: 'target',      pressureOnRise: true },
  ],
  Infrastructure: [
    { id: 'security-infra', pressureOnRise: false }, // falling posture = more pressure
  ],
  Delivery: [
    { id: 'deployment', pressureOnRise: false }, // falling build success = more pressure
    { id: 'flow',       pressureOnRise: true  }, // rising lead time = more pressure
  ],
  Quality: [
    { id: 'bugs', pressureOnRise: true },
  ],
  Collaboration: [
    { id: 'collaboration', pressureOnRise: false }, // lower health = more pressure
  ],
  Ownership: [
    { id: 'ownership', pressureOnRise: true  }, // rising unassigned % = more pressure
    { id: 'risk',      pressureOnRise: false }, // fewer commits = signal of pressure
  ],
};

const MAX_INTERVALS = 10;
const MIN_DATA_POINTS = 3;

/**
 * Rows whose value range falls below this threshold are considered flat and hidden.
 * Range is computed over the normalised 0–1 pressure values for the domain.
 */
const MIN_ACTIVITY_RANGE = 0.08;

/**
 * Metrics whose raw value range is less than this fraction of their absolute peak
 * are excluded as noisy contributors before domain aggregation.
 * Example: security metric oscillates 299–300 over an absolute level of 300,
 * giving relative range ≈ 0.003 — well below this gate.
 */
const NOISE_RELATIVE_RANGE = 0.01;

function normalizeAndOrient(values: number[], pressureOnRise: boolean): number[] {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min;
  // Flat series → constant mid-pressure so the row stays visible but quiet
  if (range === 0) return values.map(() => 0.3);
  const normalized = values.map((v) => (v - min) / range);
  return pressureOnRise ? normalized : normalized.map((v) => 1 - v);
}

/**
 * Builds domain-level anomaly river rows from a list of MetricItem objects.
 * Returns only domains that have at least one metric with sufficient data.
 */
export function buildAnomalyRiver(metrics: MetricItem[]): AnomalyRiverRow[] {
  const metricMap = new Map(metrics.map((m) => [m.id, m]));

  const rows: AnomalyRiverRow[] = [];

  for (const [domain, mappings] of Object.entries(DOMAIN_METRICS)) {
    const contributions: number[][] = [];
    const metricIds: string[] = [];

    for (const { id, pressureOnRise } of mappings) {
      const metric = metricMap.get(id);
      if (!metric || metric.data.length < MIN_DATA_POINTS) continue;

      const raw = metric.data.slice(-MAX_INTERVALS);

      // Noise gate: exclude metrics whose raw window range is negligible relative
      // to their absolute peak (e.g. 1-unit oscillation over a ~300-unit base).
      const rawRange = Math.max(...raw) - Math.min(...raw);
      const absPeak = Math.max(Math.abs(Math.max(...raw)), 1);
      if (rawRange / absPeak < NOISE_RELATIVE_RANGE) continue;

      const oriented = normalizeAndOrient(raw, pressureOnRise);
      contributions.push(oriented);
      metricIds.push(id);
    }

    if (contributions.length === 0) continue;

    // Align to the shortest series length before averaging
    const len = Math.min(...contributions.map((c) => c.length));
    const aligned = contributions.map((c) => c.slice(-len));

    const values = Array.from({ length: len }, (_, i) => {
      const sum = aligned.reduce((acc, c) => acc + c[i], 0);
      return sum / aligned.length;
    });

    // Suppress flat rows: hide if the value range across intervals is below threshold
    const rangeVal = Math.max(...values) - Math.min(...values);
    if (rangeVal < MIN_ACTIVITY_RANGE) continue;

    rows.push({ domain, values, metricIds });
  }

  return rows;
}

/**
 * Maps an alert dashboard ID to the display domain name used in AnomalyRiver rows.
 */
export const ALERT_DOMAIN_TO_RIVER_DOMAIN: Record<string, string> = {
  security:      'Security',
  'security-infra': 'Infrastructure',
  deployment:    'Delivery',
  flow:          'Delivery',
  bugs:          'Quality',
  collaboration: 'Collaboration',
  ownership:     'Ownership',
  risk:          'Ownership',
};
