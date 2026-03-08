import {
  AnomalyRiverRow,
  DomainAttribution,
  DomainContributor,
  AttributionStrength,
} from './buildAnomalyRiver';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface CollisionSharedDriver {
  signalKey:      string;
  signalLabel:    string;   // attribution contributor label (metric title or fallback)
  combinedWeight: number;   // sum of min(weightA, weightB) across the pair
  domains:        string[];
  direction?:     'up' | 'down' | 'flat';
}

export interface CrossDomainCollision {
  id:                  string;
  domainKeys:          string[];
  domainLabels:        string[];
  sharedDrivers:       CollisionSharedDriver[];
  primarySharedDriver: CollisionSharedDriver;
  collisionStrength:   number;   // 0–1
  pressureStrength:    number;   // 0–1 average recent pair pressure
  confidence:          AttributionStrength;
  summary:             string;
  brief:               string;
}

export interface CollisionDetectionResult {
  collisions:   CrossDomainCollision[];
  topCollision: CrossDomainCollision | null;
}

// ── Thresholds ────────────────────────────────────────────────────────────────

const COLLISION_MIN_PRESSURE   = 0.35;
const COLLISION_MIN_OVERLAP    = 0.15;
const COLLISION_MIN_PAIR_PRESS = 0.30;

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Flattens dominantSignal + secondarySignals into a metricId → {label, weight} map
 * for structured cross-domain comparison.
 */
function getAttributedSignalWeights(
  attribution: DomainAttribution,
): Map<string, { label: string; weight: number; direction: 'up' | 'down' | 'flat' }> {
  const result = new Map<string, { label: string; weight: number; direction: 'up' | 'down' | 'flat' }>();
  const contributors: DomainContributor[] = [
    ...(attribution.dominantSignal ? [attribution.dominantSignal] : []),
    ...attribution.secondarySignals,
  ];
  for (const c of contributors) {
    result.set(c.metricId, { label: c.label, weight: c.contributionScore, direction: c.direction });
  }
  return result;
}

/**
 * Derives a present-oriented pressure scalar from recent row values.
 * Uses mean of the last 2–3 intervals with a small boost for a rising tail,
 * rather than the historical max which over-promotes stale spikes.
 */
function computeDomainPressureStrength(row: AnomalyRiverRow): number {
  const v = row.values;
  const recent = v.slice(-3);
  const recentMean = recent.reduce((s, x) => s + x, 0) / recent.length;
  const tail = v[v.length - 1] ?? 0;
  const anchor = v[v.length - 3] ?? tail;
  const riseBump = tail > anchor ? 0.05 : 0;
  return Math.min(recentMean + riseBump, 1);
}

/**
 * Intersects contributor signal keys across two domains and scores overlap
 * using sum(min(weightA, weightB)) — a stable, simple formula.
 */
function computeAttributionOverlap(
  aWeights: Map<string, { label: string; weight: number; direction: 'up' | 'down' | 'flat' }>,
  bWeights: Map<string, { label: string; weight: number; direction: 'up' | 'down' | 'flat' }>,
): { overlapScore: number; sharedDrivers: CollisionSharedDriver[] } {
  const shared: CollisionSharedDriver[] = [];
  for (const [key, aEntry] of aWeights.entries()) {
    const bEntry = bWeights.get(key);
    if (!bEntry) continue;
    shared.push({
      signalKey:      key,
      // Attribution label is the primary source: metric title or its fallback label,
      // as stored on DomainContributor.label from buildAnomalyRiver.
      signalLabel:    aEntry.label,
      combinedWeight: Math.min(aEntry.weight, bEntry.weight),
      domains:        [],
      direction:      aEntry.direction,
    });
  }
  shared.sort((a, b) => b.combinedWeight - a.combinedWeight);
  const overlapScore = shared.reduce((s, d) => s + d.combinedWeight, 0);
  return { overlapScore, sharedDrivers: shared };
}

/**
 * Builds compact editorial collision text.
 * Uses the attribution signal label (from DomainContributor.label) directly,
 * with no external suffix dictionary dependency.
 */
function buildCollisionText(
  labels: string[],
  driver: CollisionSharedDriver,
): { summary: string; brief: string } {
  const domainPart  = labels.join(' and ');
  const driverLabel = driver.signalLabel;
  return {
    summary: `${domainPart} pressure rising together. Shared driver: ${driverLabel}.`,
    brief:   `${domainPart}: shared pressure from ${driverLabel}.`,
  };
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Detects cross-domain pressure collisions: pairs of meaningfully pressured
 * domains whose attribution contributors meaningfully overlap.
 *
 * Call this after buildAnomalyRiver() has produced the river rows.
 * Returns top 1–2 collisions ranked by collision strength.
 */
export function detectCrossDomainPressureCollisions(
  rows: AnomalyRiverRow[],
): CollisionDetectionResult {
  const eligible = rows.filter((r) => {
    if (computeDomainPressureStrength(r) < COLLISION_MIN_PRESSURE) return false;
    if (!r.attribution.dominantSignal) return false;
    if (r.attribution.confidence === 'low') return false;
    return true;
  });

  if (eligible.length < 2) return { collisions: [], topCollision: null };

  const collisions: CrossDomainCollision[] = [];

  for (let i = 0; i < eligible.length; i++) {
    for (let j = i + 1; j < eligible.length; j++) {
      const rowA = eligible[i];
      const rowB = eligible[j];

      const pressA       = computeDomainPressureStrength(rowA);
      const pressB       = computeDomainPressureStrength(rowB);
      const pairPressure = (pressA + pressB) / 2;
      if (pairPressure < COLLISION_MIN_PAIR_PRESS) continue;

      const weightsA = getAttributedSignalWeights(rowA.attribution);
      const weightsB = getAttributedSignalWeights(rowB.attribution);
      const { overlapScore, sharedDrivers } = computeAttributionOverlap(weightsA, weightsB);

      if (overlapScore < COLLISION_MIN_OVERLAP || sharedDrivers.length === 0) continue;

      const taggedDrivers = sharedDrivers.map((d) => ({
        ...d,
        domains: [rowA.domain, rowB.domain],
      }));

      const primaryDriver     = taggedDrivers[0];
      const collisionStrength = Math.min(overlapScore * pairPressure * 2, 1);

      const confA          = rowA.attribution.confidence;
      const confB          = rowB.attribution.confidence;
      const bothHigh       = confA === 'high'     && confB === 'high';
      const eitherModerate = confA === 'moderate' || confB === 'moderate';
      const strongOverlap  = overlapScore >= 0.35;
      const confidence: AttributionStrength =
        bothHigh && strongOverlap                         ? 'high'
        : (bothHigh || (eitherModerate && strongOverlap)) ? 'moderate'
        : 'low';

      if (confidence === 'low' && collisionStrength < 0.25) continue;

      const { summary, brief } = buildCollisionText(
        [rowA.domain, rowB.domain],
        primaryDriver,
      );

      collisions.push({
        id:                  `${rowA.domain.toLowerCase()}-${rowB.domain.toLowerCase()}`,
        domainKeys:          [rowA.domain, rowB.domain],
        domainLabels:        [rowA.domain, rowB.domain],
        sharedDrivers:       taggedDrivers,
        primarySharedDriver: primaryDriver,
        collisionStrength,
        pressureStrength:    pairPressure,
        confidence,
        summary,
        brief,
      });
    }
  }

  collisions.sort((a, b) => b.collisionStrength - a.collisionStrength);
  return {
    collisions:   collisions.slice(0, 2),
    topCollision: collisions[0] ?? null,
  };
}
