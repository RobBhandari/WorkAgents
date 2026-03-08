import { MetricItem } from '../types/trends';
import { CrossDomainCollision } from './crossDomainCollision';
import { DOMAIN_DASHBOARD_LABEL } from './buildDrawerTarget';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface CollisionDispatchHint {
  domainKey:      string;
  domainLabel:    string;
  dashboardLabel: string;
  dashboardUrl:   string;
  reason:         string;
}

// ── Internal ──────────────────────────────────────────────────────────────────

/**
 * Mirrors ROW_DOMAIN_TO_KEY in AnomalyRiver.tsx.
 * Normalises capitalised river domain display labels to lowercase domainKeys
 * used by DOMAIN_DASHBOARD_LABEL and the alert-signal maps.
 */
const RIVER_DOMAIN_TO_KEY: Record<string, string> = {
  Security:       'security',
  Infrastructure: 'infrastructure',
  Delivery:       'deployment',
  Quality:        'bugs',
  Collaboration:  'collaboration',
  Ownership:      'ownership',
};

/**
 * Resolves the best dispatch domainKey + dashboardUrl for a collision.
 *
 * Priority:
 * 1. primarySharedDriver metricId → find metric in list → use its dashboardUrl;
 *    domain = first collision domain that resolves to a known DOMAIN_DASHBOARD_LABEL entry.
 * 2. Fallback: first collision domain with a known dashboard label + any metric URL.
 */
function resolveDispatch(
  collision: CrossDomainCollision,
  metrics: MetricItem[],
): { domainKey: string; dashboardUrl: string } | null {
  const metricMap = new Map(metrics.map((m) => [m.id, m]));

  // 1. Driver metric path
  const driverKey = collision.primarySharedDriver?.signalKey;
  if (driverKey) {
    const driverMetric = metricMap.get(driverKey);
    if (driverMetric?.dashboardUrl) {
      for (const domainLabel of collision.domainKeys) {
        const domainKey = RIVER_DOMAIN_TO_KEY[domainLabel] ?? domainLabel.toLowerCase();
        if (DOMAIN_DASHBOARD_LABEL[domainKey]) {
          return { domainKey, dashboardUrl: driverMetric.dashboardUrl };
        }
      }
    }
  }

  // 2. Fallback: first collision domain with a known key + any available metric URL
  const anyUrl = metrics.find((m) => m.dashboardUrl)?.dashboardUrl;
  if (anyUrl) {
    for (const domainLabel of collision.domainKeys) {
      const domainKey = RIVER_DOMAIN_TO_KEY[domainLabel] ?? domainLabel.toLowerCase();
      if (DOMAIN_DASHBOARD_LABEL[domainKey]) {
        return { domainKey, dashboardUrl: anyUrl };
      }
    }
  }

  return null;
}

// ── Public ────────────────────────────────────────────────────────────────────

/**
 * Builds a dispatch hint for a cross-domain collision using the existing
 * routing system (backend-provided dashboardUrl + DOMAIN_DASHBOARD_LABEL).
 * Returns null if the collision is absent or routing cannot be resolved.
 */
export function buildCollisionDispatchHint(
  collision: CrossDomainCollision | null,
  metrics: MetricItem[],
): CollisionDispatchHint | null {
  if (!collision) return null;

  const resolved = resolveDispatch(collision, metrics);
  if (!resolved) return null;

  const { domainKey, dashboardUrl } = resolved;
  const dashboardLabel = DOMAIN_DASHBOARD_LABEL[domainKey] ?? 'Dashboard';
  const domainLabel    = domainKey.charAt(0).toUpperCase() + domainKey.slice(1);

  const driverLabel = collision.primarySharedDriver.signalLabel;
  const domains     = collision.domainLabels.join(' and ');
  const reason      = `Best starting point because ${driverLabel} is driving both ${domains} pressure.`;

  return { domainKey, domainLabel, dashboardLabel, dashboardUrl, reason };
}
