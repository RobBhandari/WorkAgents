import { MetricItem } from '../types/trends';

// ── Attribution types ─────────────────────────────────────────────────────────

export type AttributionStrength = 'low' | 'moderate' | 'high';
export type AttributionBreadth  = 'single' | 'concentrated' | 'broad';

export interface DomainContributor {
  metricId:          string;
  label:             string;
  contributionScore: number;   // normalised share 0–1 of total domain score
  direction:         'up' | 'down' | 'flat';
}

export interface DomainAttribution {
  contributorCount: number;
  dominantSignal:   DomainContributor | undefined;
  secondarySignals: DomainContributor[];
  breadth:          AttributionBreadth;
  confidence:       AttributionStrength;
  summary:          string;
}

export interface AnomalyRiverRow {
  domain:      string;
  values:      number[];   // 0–1 normalised pressure intensity, up to 10 intervals
  metricIds:   string[];
  attribution: DomainAttribution;
}

// ── Domain metric configuration ───────────────────────────────────────────────

/**
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
    { id: 'security-infra', pressureOnRise: false },
  ],
  Delivery: [
    { id: 'deployment', pressureOnRise: false },
    { id: 'flow',       pressureOnRise: true  },
  ],
  Quality: [
    { id: 'bugs', pressureOnRise: true },
  ],
  Collaboration: [
    { id: 'collaboration', pressureOnRise: false },
  ],
  Ownership: [
    { id: 'ownership', pressureOnRise: true  },
    { id: 'risk',      pressureOnRise: false },
  ],
};

const MAX_INTERVALS    = 10;
const MIN_DATA_POINTS  = 3;
const MIN_ACTIVITY_RANGE   = 0.08;
const NOISE_RELATIVE_RANGE = 0.01;

// ── Fallback label map (used only when MetricItem.title is unavailable) ───────

const METRIC_LABEL_FALLBACK: Record<string, string> = {
  exploitable:    'Exploitable vulnerabilities',
  'security-infra': 'Infrastructure security posture',
  target:         'Security target gap',
  deployment:     'Deployment frequency',
  flow:           'Flow efficiency',
  bugs:           'Open bug count',
  collaboration:  'Collaboration health',
  ownership:      'Ownership coverage',
  risk:           'Risk score',
};

// Direction-aware suffix labels for concentrated pressure prose
const PRESSURE_SUFFIX: Record<string, string> = {
  'deployment:up': 'deployment failures',
  'flow:up':       'flow bottlenecks',
  'bugs:up':       'open bug volume',
  'exploitable:up':'vulnerability backlog',
  'ownership:up':  'unassigned work',
  'risk:up':       'risk concentration',
};

// ── Core normalisation ────────────────────────────────────────────────────────

function normalizeAndOrient(values: number[], pressureOnRise: boolean): number[] {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min;
  if (range === 0) return values.map(() => 0.3);
  const normalized = values.map((v) => (v - min) / range);
  return pressureOnRise ? normalized : normalized.map((v) => 1 - v);
}

// ── Attribution helpers ───────────────────────────────────────────────────────

/** Contribution score: prioritises recent level and directional rise; variance is secondary. */
function scoreOriented(oriented: number[]): number {
  const recent = oriented.slice(-3);
  const recentLevel = recent.reduce((s, v) => s + v, 0) / recent.length;
  const tailDelta   = Math.max(oriented[oriented.length - 1] - oriented[0], 0);
  const mean        = oriented.reduce((s, v) => s + v, 0) / oriented.length;
  const variance    = oriented.reduce((s, v) => s + (v - mean) ** 2, 0) / oriented.length;
  return 0.50 * recentLevel + 0.35 * tailDelta + 0.15 * variance;
}

function directionOf(oriented: number[]): 'up' | 'down' | 'flat' {
  const delta = oriented[oriented.length - 1] - oriented[0];
  if (delta >  0.15) return 'up';
  if (delta < -0.15) return 'down';
  return 'flat';
}

function computeBreadth(topShare: number, count: number): AttributionBreadth {
  if (count === 1) return 'single';
  if (topShare >= 0.60) return 'concentrated';
  return 'broad';
}

function computeConfidence(
  rowMax: number,
  breadth: AttributionBreadth,
  contributors: DomainContributor[],
): AttributionStrength {
  const rowStrength = rowMax >= 0.65 ? 'strong' : rowMax >= 0.40 ? 'moderate' : 'weak';

  if (rowStrength === 'weak') return 'low';

  if (breadth === 'single') {
    return rowStrength === 'strong' ? 'moderate' : 'low';
  }

  const topShare = contributors[0].contributionScore;
  const clarity  = topShare >= 0.60 ? 'clear' : topShare >= 0.40 ? 'partial' : 'diffuse';
  const secondariesMeaningful = contributors.slice(1).some((s) => s.contributionScore >= 0.15);

  if (rowStrength === 'strong') {
    if (clarity === 'clear') return 'high';
    if (secondariesMeaningful) return 'moderate';
    return 'low';
  }

  // rowStrength === 'moderate'
  if (clarity === 'clear') return 'moderate';
  if (secondariesMeaningful) return 'moderate';
  return 'low';
}

function buildSummary(
  breadth: AttributionBreadth,
  confidence: AttributionStrength,
  dominant: DomainContributor | undefined,
  count: number,
): string {
  if (breadth === 'single' || breadth === 'concentrated') {
    if (!dominant) return 'Attribution unclear.';
    const suffixKey = `${dominant.metricId}:${dominant.direction}`;
    const label = PRESSURE_SUFFIX[suffixKey] ?? dominant.label;

    if (breadth === 'single') {
      return confidence === 'low'
        ? `Currently driven by one visible signal: ${label}`.slice(0, 55)
        : `One visible driver: ${label}`.slice(0, 55);
    }
    // concentrated
    return dominant.direction === 'up'
      ? `Primarily influenced by ${label}`.slice(0, 55)
      : `Led by ${dominant.label}`.slice(0, 55);
  }

  // broad
  if (confidence === 'high')     return `Broad across ${count} contributing signals`;
  if (confidence === 'moderate') return `Spread across ${count} signals — no single driver`;
  return 'Signal spread thin — attribution uncertain';
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Builds domain-level anomaly river rows from a list of MetricItem objects.
 * Returns only domains that have at least one metric with sufficient data.
 * Each row includes DomainAttribution derived from the same oriented series.
 */
export function buildAnomalyRiver(metrics: MetricItem[]): AnomalyRiverRow[] {
  const metricMap = new Map(metrics.map((m) => [m.id, m]));
  const rows: AnomalyRiverRow[] = [];

  for (const [domain, mappings] of Object.entries(DOMAIN_METRICS)) {
    const contributions: number[][] = [];
    const metricIds: string[] = [];

    // Per-contributor raw data for attribution scoring
    const rawContributors: { id: string; label: string; oriented: number[] }[] = [];

    for (const { id, pressureOnRise } of mappings) {
      const metric = metricMap.get(id);
      if (!metric || metric.data.length < MIN_DATA_POINTS) continue;

      const raw = metric.data.slice(-MAX_INTERVALS);

      const rawRange = Math.max(...raw) - Math.min(...raw);
      const absPeak  = Math.max(Math.abs(Math.max(...raw)), 1);
      if (rawRange / absPeak < NOISE_RELATIVE_RANGE) continue;

      const oriented = normalizeAndOrient(raw, pressureOnRise);
      contributions.push(oriented);
      metricIds.push(id);

      const label = metric.title || METRIC_LABEL_FALLBACK[id] || id;
      rawContributors.push({ id, label, oriented });
    }

    if (contributions.length === 0) continue;

    // Align to shortest series
    const len     = Math.min(...contributions.map((c) => c.length));
    const aligned = contributions.map((c) => c.slice(-len));

    const values = Array.from({ length: len }, (_, i) => {
      const sum = aligned.reduce((acc, c) => acc + c[i], 0);
      return sum / aligned.length;
    });

    const rangeVal = Math.max(...values) - Math.min(...values);
    if (rangeVal < MIN_ACTIVITY_RANGE) continue;

    // ── Attribution ──────────────────────────────────────────────────────────

    // Score each contributor on its oriented series (aligned to same window)
    const scored = rawContributors.map((c, idx) => ({
      metricId:  c.id,
      label:     c.label,
      rawScore:  scoreOriented(aligned[idx]),
      direction: directionOf(aligned[idx]),
    }));

    const totalScore = scored.reduce((s, c) => s + c.rawScore, 0) || 1;
    const ranked: DomainContributor[] = scored
      .map((c) => ({
        metricId:          c.metricId,
        label:             c.label,
        contributionScore: c.rawScore / totalScore,
        direction:         c.direction,
      }))
      .sort((a, b) => b.contributionScore - a.contributionScore);

    const dominant  = ranked[0];
    const secondary = ranked.slice(1);
    const breadth   = computeBreadth(dominant?.contributionScore ?? 0, ranked.length);
    const rowMax    = Math.max(...values);
    const confidence = computeConfidence(rowMax, breadth, ranked);
    const summary    = buildSummary(breadth, confidence, dominant, ranked.length);

    const attribution: DomainAttribution = {
      contributorCount: ranked.length,
      dominantSignal:   dominant,
      secondarySignals: secondary,
      breadth,
      confidence,
      summary,
    };

    rows.push({ domain, values, metricIds, attribution });
  }

  return rows;
}

/**
 * Maps an alert dashboard ID to the display domain name used in AnomalyRiver rows.
 */
export const ALERT_DOMAIN_TO_RIVER_DOMAIN: Record<string, string> = {
  security:         'Security',
  'security-infra': 'Infrastructure',
  deployment:       'Delivery',
  flow:             'Delivery',
  bugs:             'Quality',
  collaboration:    'Collaboration',
  ownership:        'Ownership',
  risk:             'Ownership',
};
