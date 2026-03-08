import { MetricItem } from '../types/trends';
import { AnomalyRiverRow } from './buildAnomalyRiver';
import { alertSignalMap } from '../config/alertSignalMap';

// ── Briefing contract types ───────────────────────────────────────────────────

export interface DrawerRelatedSignal {
  id: string;
  label: string;
  direction?: 'up' | 'down' | 'flat';
  reason?: string;
}

export interface DrawerEvidence {
  contributorCount: number;
  confidence: 'low' | 'moderate' | 'high';
  dominantSignalLabel?: string;
  isBroad?: boolean;
}

export interface DrawerMovement {
  summary: string;
  direction: 'up' | 'down' | 'flat';
  intensity?: 'low' | 'moderate' | 'high';
  windowLabel?: string;
}

export interface DrawerDispatch {
  label: string;
  url: string;
}

export interface DrawerImplication {
  headline: string;
  detail?: string;
}

export interface DrawerTarget {
  kind: 'metric' | 'domain';
  /** Entity name shown in drawer header */
  label: string;
  /** Concise briefing claim shown prominently below the header */
  headline: string;
  /** Lowercase domain key for alert lookups */
  domainKey: string;
  /** Capitalised domain display label */
  domainLabel: string;
  movement: DrawerMovement;
  implication: DrawerImplication;
  evidence?: DrawerEvidence;
  relatedSignals: DrawerRelatedSignal[];
  dispatch: DrawerDispatch;
  /** Populated when kind === 'metric' */
  metric?: MetricItem;
}

// ── Editorial copy ────────────────────────────────────────────────────────────

const WHY_IT_MATTERS: Record<string, { headline: string; detail: string }> = {
  security:       { headline: 'Persistent security pressure raises exposure and increases remediation load.', detail: 'Unresolved vulnerabilities compound risk over time and erode compliance posture.' },
  infrastructure: { headline: 'Infrastructure risk compounds quietly and is often underweighted until it disrupts delivery.', detail: 'Degrading posture signals future reliability gaps before they become incidents.' },
  deployment:     { headline: 'Sustained delivery pressure slows release velocity and limits recovery capacity.', detail: 'Bottlenecks here affect every team downstream and increase change-failure rate.' },
  delivery:       { headline: 'Sustained delivery pressure slows release velocity and limits recovery capacity.', detail: 'Bottlenecks here affect every team downstream and increase change-failure rate.' },
  flow:           { headline: 'Flow pressure signals bottlenecks that limit delivery throughput across teams.', detail: 'Lead time increases are an early indicator of systemic blockage.' },
  quality:        { headline: 'Quality pressure increases rework cycles and broadens incident risk across the portfolio.', detail: 'Open bug volume is a leading indicator of incident frequency.' },
  bugs:           { headline: 'Open bug volume increases rework cycles and raises the risk of unresolved incidents.', detail: 'Unresolved defects accumulate cost and complexity over time.' },
  ownership:      { headline: 'Ownership pressure delays incident response and weakens accountability in high-risk areas.', detail: 'Gaps in assignment increase mean time to resolution across products.' },
  risk:           { headline: 'Commit-level risk patterns can indicate knowledge concentration or delivery fragility.', detail: 'Single-owner files increase bus-factor risk and reduce team resilience.' },
  collaboration:  { headline: 'Collaboration pressure can indicate review bottlenecks or growing team isolation.', detail: 'Low PR velocity reduces knowledge sharing and slows quality gatekeeping.' },
};

const DOMAIN_DASHBOARD_LABEL: Record<string, string> = {
  security:       'Security Dashboard',
  infrastructure: 'Infrastructure Dashboard',
  deployment:     'Delivery Dashboard',
  delivery:       'Delivery Dashboard',
  flow:           'Flow Dashboard',
  quality:        'Quality Dashboard',
  bugs:           'Quality Dashboard',
  ownership:      'Ownership Dashboard',
  risk:           'Risk Dashboard',
  collaboration:  'Collaboration Dashboard',
};

// ── Internal helpers ──────────────────────────────────────────────────────────

function buildRelatedSignals(domainKey: string, metricIds: string[]): DrawerRelatedSignal[] {
  const direct = alertSignalMap[domainKey];
  if (direct && direct.length > 0) {
    return direct.slice(0, 4).map((s) => ({ id: s.id, label: s.label, direction: s.direction }));
  }
  const seen = new Set<string>();
  const results: DrawerRelatedSignal[] = [];
  for (const signals of Object.values(alertSignalMap)) {
    for (const s of signals) {
      if (metricIds.includes(s.id) && !seen.has(s.id)) {
        seen.add(s.id);
        results.push({ id: s.id, label: s.label, direction: s.direction });
        if (results.length >= 4) return results;
      }
    }
  }
  return results;
}

function metricHeadline(m: MetricItem): string {
  const { ragColor, cssClass } = m;
  if (ragColor === '#ef4444' && cssClass === 'trend-up')   return 'Rising and above tolerance threshold.';
  if (ragColor === '#ef4444' && cssClass === 'trend-down') return 'Improving but still below target.';
  if (ragColor === '#ef4444')                              return 'Below target — action required.';
  if (ragColor === '#f59e0b' && cssClass === 'trend-up')   return 'Heading in the wrong direction — watch closely.';
  if (ragColor === '#f59e0b' && cssClass === 'trend-down') return 'Recovering — not yet at target.';
  if (ragColor === '#f59e0b')                              return 'Within amber range — monitor closely.';
  if (ragColor === '#10b981')                              return 'Within healthy range.';
  return `${m.title} is being tracked.`;
}

function metricMovement(m: MetricItem): DrawerMovement {
  const direction: 'up' | 'down' | 'flat' =
    m.cssClass === 'trend-up' ? 'up' : m.cssClass === 'trend-down' ? 'down' : 'flat';
  const changeStr = m.arrow && m.change !== '' && typeof m.change === 'number'
    ? `${m.change > 0 ? '+' : ''}${m.change.toLocaleString(undefined, { maximumFractionDigits: 1 })}`
    : null;
  const summary = changeStr && m.changeLabel
    ? `${changeStr} ${m.changeLabel}`
    : changeStr
    ? changeStr
    : 'No recent change data.';
  return { summary, direction, windowLabel: m.changeLabel ?? undefined };
}

function anomalyMovement(values: number[]): DrawerMovement {
  const n = values.length;
  if (n < 2) return { summary: 'Insufficient data.', direction: 'flat', intensity: 'low' };

  const first = values[0];
  const last = values[n - 1];
  const max = Math.max(...values);
  const maxIdx = values.indexOf(max);
  const midSpike = max > 0.7 && maxIdx > 0 && maxIdx < n - 2;

  let summary: string;
  let direction: 'up' | 'down' | 'flat';
  let intensity: 'low' | 'moderate' | 'high';

  if (midSpike) {
    summary = 'Spiked mid-window and remains elevated above the earlier baseline.';
    direction = 'up'; intensity = 'high';
  } else if (last - first > 0.3) {
    summary = 'Pressure has risen across recent intervals.';
    direction = 'up'; intensity = last > 0.65 ? 'high' : 'moderate';
  } else if (first - last > 0.3) {
    summary = 'Pressure has eased after an earlier elevated period.';
    direction = 'down'; intensity = 'moderate';
  } else if (last > 0.65) {
    summary = 'Signal remains elevated with sustained high-pressure readings.';
    direction = 'up'; intensity = 'high';
  } else {
    summary = 'Signal shows low movement across the recent window.';
    direction = 'flat'; intensity = 'low';
  }

  return { summary, direction, intensity, windowLabel: `${n} intervals` };
}

// ── Public factory functions ──────────────────────────────────────────────────

export function buildMetricTarget(m: MetricItem, domainKey: string): DrawerTarget {
  const impl = WHY_IT_MATTERS[domainKey] ?? WHY_IT_MATTERS['deployment'];
  const dashLabel = DOMAIN_DASHBOARD_LABEL[domainKey] ?? 'Dashboard';
  return {
    kind: 'metric',
    label: m.title,
    headline: metricHeadline(m),
    domainKey,
    domainLabel: domainKey.charAt(0).toUpperCase() + domainKey.slice(1),
    movement: metricMovement(m),
    implication: { headline: impl.headline, detail: impl.detail },
    evidence: { contributorCount: 1, confidence: 'high' },
    relatedSignals: buildRelatedSignals(domainKey, [m.id]),
    dispatch: { label: `Open ${dashLabel} →`, url: m.dashboardUrl },
    metric: m,
  };
}

export function buildDomainTarget(
  row: AnomalyRiverRow,
  displayLabel: string,
  domainKey: string,
  metrics: MetricItem[],
): DrawerTarget {
  const metricMap = new Map(metrics.map((m) => [m.id, m]));
  const dashboardUrl = row.metricIds.map((id) => metricMap.get(id)?.dashboardUrl).find((u) => !!u) ?? '';

  const impl = WHY_IT_MATTERS[domainKey] ?? WHY_IT_MATTERS['deployment'];
  const dashLabel = DOMAIN_DASHBOARD_LABEL[domainKey] ?? 'Dashboard';
  const mvmt = anomalyMovement(row.values);

  const contributorCount = row.metricIds.length;
  const confidence: 'low' | 'moderate' | 'high' =
    contributorCount >= 3 ? 'high' : contributorCount === 2 ? 'moderate' : 'low';
  const dominantMetric = contributorCount === 1 ? metricMap.get(row.metricIds[0]) : undefined;

  const dirLabel = mvmt.direction === 'up' ? 'rising' : mvmt.direction === 'down' ? 'easing' : 'stable';
  const headline = `${row.domain} pressure is ${dirLabel} — ${mvmt.summary.toLowerCase().replace(/\.$/, '')}.`;

  return {
    kind: 'domain',
    label: displayLabel,
    headline,
    domainKey,
    domainLabel: row.domain,
    movement: mvmt,
    implication: { headline: impl.headline, detail: impl.detail },
    evidence: {
      contributorCount,
      confidence,
      dominantSignalLabel: dominantMetric?.title,
      isBroad: contributorCount >= 3,
    },
    relatedSignals: buildRelatedSignals(domainKey, row.metricIds),
    dispatch: { label: `Open ${dashLabel} →`, url: dashboardUrl },
  };
}
