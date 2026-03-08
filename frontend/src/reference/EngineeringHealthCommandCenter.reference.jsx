import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  ChevronRight,
  Radar,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react';

type Severity = 'Critical' | 'High' | 'Medium';
type MetricStatus = 'Critical' | 'At risk' | 'Watch' | 'Improving';
type Tone = 'critical' | 'high' | 'warn' | 'ok';

type AlertItem = {
  id: string;
  title: string;
  severity: Severity;
  headline: string;
  body: string;
  impact: string[];
  metricIds: string[];
  timestamp: string;
};

type BreakdownItem = {
  label: string;
  value: number;
  tone: Tone;
};

type MetricItem = {
  id: string;
  title: string;
  category: string;
  value: string;
  unit: string;
  delta: string;
  direction: 'up' | 'down' | 'flat';
  status: MetricStatus;
  series: number[];
  insight: string;
  summary: string;
  breakdown: BreakdownItem[];
};

type ChangeItem = {
  id: string;
  name: string;
  delta: string;
  dir: 'up' | 'down';
  detail: string;
};

type RadarScore = {
  label: string;
  value: number;
};

type GalaxyNode = {
  name: string;
  risk: 'Critical' | 'High' | 'Warn';
  size: number;
  x: number;
  y: number;
};

type MatrixRow = {
  product: string;
  security: Tone;
  bugs: Tone;
  delivery: Tone;
};

const alerts: AlertItem[] = [
  {
    id: 'infra',
    title: 'Infrastructure Pressure',
    severity: 'Critical',
    headline: '+152 vulnerabilities this week',
    body: 'Risk is clustering across Product I, Compliance, and AI Services. This is not random noise; it is concentrated exposure.',
    impact: ['Product I', 'Compliance', 'AI Services'],
    metricIds: ['infra-vulns', 'security-code-cloud'],
    timestamp: '12m ago',
  },
  {
    id: 'security',
    title: 'Security Escalation',
    severity: 'High',
    headline: '13 critical findings still open',
    body: 'Code and cloud issues are holding above baseline for a second consecutive week.',
    impact: ['Compliance', 'Product I'],
    metricIds: ['security-code-cloud', 'exploitable-vulns'],
    timestamp: '28m ago',
  },
  {
    id: 'delivery',
    title: 'Delivery Drag',
    severity: 'Medium',
    headline: 'Build reliability remains soft',
    body: 'Lead time improved slightly, but low build success is still suppressing true delivery recovery.',
    impact: ['AI Services', 'Financial Director'],
    metricIds: ['build-success', 'lead-time'],
    timestamp: '1h ago',
  },
];

const metrics: MetricItem[] = [
  {
    id: 'security-code-cloud',
    title: 'Security: Code & Cloud',
    category: 'Security',
    value: '306',
    unit: 'findings',
    delta: '+0 vs last week',
    direction: 'flat',
    status: 'Watch',
    series: [36, 40, 44, 41, 52, 78, 76],
    insight: 'Concentration remains highest in Compliance and Product I.',
    summary: 'Code and cloud issues are not worsening rapidly, but they are refusing to resolve. That is still failure.',
    breakdown: [
      { label: 'Compliance', value: 54, tone: 'critical' },
      { label: 'Product I', value: 27, tone: 'high' },
      { label: 'AI Services', value: 24, tone: 'high' },
    ],
  },
  {
    id: 'exploitable-vulns',
    title: 'Exploitable Vulnerabilities',
    category: 'Security',
    value: '491',
    unit: 'vulns',
    delta: '+68 vs last week',
    direction: 'up',
    status: 'Critical',
    series: [70, 68, 69, 66, 48, 35, 51],
    insight: 'Spike is flattening, but the level is still far above tolerance.',
    summary: 'Executives should not celebrate a slower rise. The number is still unacceptable.',
    breakdown: [
      { label: 'Critical', value: 93, tone: 'critical' },
      { label: 'High', value: 218, tone: 'high' },
      { label: 'Medium', value: 180, tone: 'warn' },
    ],
  },
  {
    id: 'infra-vulns',
    title: 'Infrastructure Vulnerabilities',
    category: 'Infrastructure',
    value: '529',
    unit: 'vulns',
    delta: '+152 vs last week',
    direction: 'up',
    status: 'Critical',
    series: [22, 24, 28, 31, 45, 66, 88],
    insight: 'This is the fastest-moving risk in the system.',
    summary: 'This deserves the default landing spotlight because it combines severity, speed, and spread.',
    breakdown: [
      { label: 'Product I', value: 144, tone: 'critical' },
      { label: 'Compliance', value: 118, tone: 'critical' },
      { label: 'AI Services', value: 96, tone: 'high' },
    ],
  },
  {
    id: 'open-bugs',
    title: 'Open Bugs',
    category: 'Quality',
    value: '246',
    unit: 'bugs',
    delta: '-23 vs last week',
    direction: 'down',
    status: 'Improving',
    series: [64, 62, 59, 58, 56, 55, 31],
    insight: 'Backlog is finally moving in the right direction.',
    summary: 'One of the few places where the system is behaving rationally.',
    breakdown: [
      { label: 'Critical bugs', value: 19, tone: 'high' },
      { label: 'High bugs', value: 64, tone: 'warn' },
      { label: 'Medium bugs', value: 163, tone: 'ok' },
    ],
  },
  {
    id: 'build-success',
    title: 'Build Success Rate',
    category: 'Delivery',
    value: '59.6',
    unit: '%',
    delta: '-0.5 vs last week',
    direction: 'down',
    status: 'At risk',
    series: [65, 60, 57, 53, 52, 52, 45],
    insight: 'Two products are dragging the average down hard.',
    summary: 'You do not have delivery health if builds are this unreliable.',
    breakdown: [
      { label: 'AI Services', value: 42, tone: 'critical' },
      { label: 'Financial Director', value: 55, tone: 'high' },
      { label: 'Platform Avg', value: 59.6, tone: 'warn' },
    ],
  },
  {
    id: 'lead-time',
    title: 'Lead Time',
    category: 'Delivery',
    value: '80.9',
    unit: 'days p85',
    delta: '-1.1 vs last week',
    direction: 'down',
    status: 'Watch',
    series: [90, 89, 86, 84, 83, 82, 80],
    insight: 'Slight movement, still structurally too slow.',
    summary: 'Improvement exists, but it is nowhere near enough to call this healthy.',
    breakdown: [
      { label: 'Platform', value: 80.9, tone: 'warn' },
      { label: 'Compliance', value: 94, tone: 'critical' },
      { label: 'AI Services', value: 87, tone: 'high' },
    ],
  },
];

const changes: ChangeItem[] = [
  { id: 'infra-vulns', name: 'Infrastructure vulnerabilities', delta: '+152', dir: 'up', detail: '3 connected products impacted' },
  { id: 'exploitable-vulns', name: 'Exploitable vulnerabilities', delta: '+68', dir: 'up', detail: 'Critical risk still elevated' },
  { id: 'open-bugs', name: 'Open bugs', delta: '-23', dir: 'down', detail: 'Backlog reduction is working' },
  { id: 'lead-time', name: 'Lead time', delta: '-1.1d', dir: 'down', detail: 'Still too slow to claim victory' },
];

const radarScores: RadarScore[] = [
  { label: 'Security', value: 44 },
  { label: 'Delivery', value: 39 },
  { label: 'Infrastructure', value: 28 },
  { label: 'Quality', value: 63 },
  { label: 'Collaboration', value: 75 },
  { label: 'Flow', value: 58 },
  { label: 'Ownership', value: 61 },
];

const galaxyNodes: GalaxyNode[] = [
  { name: 'Compliance', risk: 'Critical', size: 84, x: 20, y: 16 },
  { name: 'Product I', risk: 'High', size: 68, x: 46, y: 40 },
  { name: 'AI Services', risk: 'High', size: 58, x: 74, y: 20 },
  { name: 'Financial Director', risk: 'Warn', size: 48, x: 24, y: 76 },
  { name: 'Product P', risk: 'Warn', size: 40, x: 76, y: 78 },
];

const matrix: MatrixRow[] = [
  { product: 'Compliance', security: 'critical', bugs: 'critical', delivery: 'high' },
  { product: 'Product I', security: 'critical', bugs: 'warn', delivery: 'ok' },
  { product: 'AI Services', security: 'high', bugs: 'ok', delivery: 'warn' },
  { product: 'Financial Director', security: 'warn', bugs: 'warn', delivery: 'ok' },
];

export default function EngineeringHealthCommandCenterSharp() {
  const [selectedMetricId, setSelectedMetricId] = useState<string>('infra-vulns');
  const [activeAlertId, setActiveAlertId] = useState<string>('infra');

  const activeAlert = alerts.find((a) => a.id === activeAlertId) ?? alerts[0];
  const linkedProducts = useMemo(() => new Set(activeAlert.impact), [activeAlert]);

  const filteredMetrics = useMemo<MetricItem[]>(() => {
    const targetIds = new Set(activeAlert.metricIds);
    return [...metrics].sort((a, b) => {
      const aHit = targetIds.has(a.id) ? 1 : 0;
      const bHit = targetIds.has(b.id) ? 1 : 0;
      if (aHit !== bHit) return bHit - aHit;
      return severityRank(b.status) - severityRank(a.status);
    });
  }, [activeAlert]);

  const selectedMetric =
    metrics.find((m) => m.id === selectedMetricId) ?? filteredMetrics[0] ?? metrics[0];

  return (
    <div className="min-h-screen bg-[#07111f] text-slate-50">
      <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
        <ExecutiveHero activeAlert={activeAlert} />

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-6">
            <AlertRail activeAlertId={activeAlertId} setActiveAlertId={setActiveAlertId} />
            <ChangeRail selectedMetricId={selectedMetricId} setSelectedMetricId={setSelectedMetricId} />
            <MetricsGrid
              metrics={filteredMetrics}
              selectedMetricId={selectedMetricId}
              setSelectedMetricId={setSelectedMetricId}
              activeAlert={activeAlert}
            />
          </div>

          <div className="space-y-6">
            <HealthRadarCard />
            <AiPanel activeAlert={activeAlert} selectedMetric={selectedMetric} />
          </div>
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <AnomalyRiver activeAlert={activeAlert} />
          <ProductGalaxy activeAlert={activeAlert} linkedProducts={linkedProducts} />
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <RiskMatrix linkedProducts={linkedProducts} />
          <DrillPanel selectedMetric={selectedMetric} activeAlert={activeAlert} />
        </div>
      </div>
    </div>
  );
}

function ExecutiveHero({ activeAlert }: { activeAlert: AlertItem }) {
  return (
    <section className="relative overflow-hidden rounded-[32px] border border-white/10 bg-[linear-gradient(135deg,rgba(12,24,40,0.96),rgba(8,16,28,0.98))] p-6 shadow-[0_40px_120px_rgba(0,0,0,0.35)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.18),transparent_25%),radial-gradient(circle_at_left,rgba(168,85,247,0.12),transparent_24%),radial-gradient(circle_at_bottom,rgba(239,68,68,0.08),transparent_30%)]" />
      <div className="relative z-10 grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/20 bg-sky-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.28em] text-sky-200">
            <Sparkles className="h-3.5 w-3.5" />
            Engineering health command center
          </div>
          <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
            This version thinks like an executive surface, not a card gallery.
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
            The weak move is making dashboards prettier. The strong move is redesigning around urgency, movement, and investigation. That is what this structure does.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <ActionChip icon={ShieldAlert} label="3 critical risks" tone="danger" />
            <ActionChip icon={TrendingUp} label="8 metrics improving" tone="good" />
            <ActionChip icon={TrendingDown} label="2 metrics declining" tone="warn" />
            <ActionChip icon={AlertTriangle} label={`Spotlight: ${activeAlert.title}`} tone="neutral" />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <GlassCard className="sm:col-span-2">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Health score</div>
                <div className="mt-3 flex items-end gap-3">
                  <span className="text-6xl font-semibold leading-none">74</span>
                  <span className="mb-1 rounded-full bg-emerald-400/10 px-2.5 py-1 text-xs font-medium text-emerald-300">Improving slowly</span>
                </div>
              </div>
              <Radar className="h-10 w-10 text-sky-300" />
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/5">
              <motion.div initial={{ width: 0 }} animate={{ width: '74%' }} transition={{ duration: 0.9 }} className="h-full rounded-full bg-gradient-to-r from-sky-400 via-cyan-300 to-emerald-300" />
            </div>
            <p className="mt-3 text-sm text-slate-300">Collaboration is healthy. Infrastructure and delivery are dragging the whole system down.</p>
          </GlassCard>

          <StatPill label="Active alerts" value="12" />
          <StatPill label="Last anomaly" value="12m" />
        </div>
      </div>
    </section>
  );
}

function AlertRail({ activeAlertId, setActiveAlertId }: { activeAlertId: string; setActiveAlertId: (id: string) => void }) {
  return (
    <section className="rounded-[28px] border border-red-400/15 bg-[linear-gradient(180deg,rgba(127,29,29,0.08),rgba(8,16,28,0.9))] p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-red-200">Global alert layer</div>
          <h2 className="mt-2 text-2xl font-semibold">Active risk signals</h2>
        </div>
        <div className="text-sm text-slate-400">Alerts should control the rest of the dashboard, not float above it.</div>
      </div>
      <div className="mt-5 grid gap-4 md:grid-cols-3">
        {alerts.map((alert) => {
          const active = alert.id === activeAlertId;
          return (
            <button
              key={alert.id}
              onClick={() => setActiveAlertId(alert.id)}
              className={`group rounded-[24px] border p-5 text-left transition ${
                active
                  ? 'border-red-300/35 bg-red-400/10 shadow-[0_0_0_1px_rgba(248,113,113,0.15)]'
                  : 'border-white/10 bg-white/5 hover:bg-white/[0.08]'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${severityBadge(alert.severity)}`}>{alert.severity}</span>
                <span className="text-xs text-slate-500">{alert.timestamp}</span>
              </div>
              <h3 className="mt-4 text-lg font-medium">{alert.title}</h3>
              <p className="mt-1 text-sm font-medium text-slate-100">{alert.headline}</p>
              <p className="mt-3 text-sm leading-6 text-slate-300">{alert.body}</p>
              <div className="mt-4 flex items-center justify-between text-sm text-slate-300">
                <span>{alert.impact.join(' • ')}</span>
                <ArrowRight className={`h-4 w-4 transition ${active ? 'translate-x-1 text-red-200' : 'text-slate-500 group-hover:translate-x-1 group-hover:text-slate-200'}`} />
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function ChangeRail({ selectedMetricId, setSelectedMetricId }: { selectedMetricId: string; setSelectedMetricId: (id: string) => void }) {
  return (
    <section className="rounded-[28px] border border-white/10 bg-[#0b1626] p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-slate-400">Movement layer</div>
          <h2 className="mt-2 text-2xl font-semibold">What changed this week</h2>
        </div>
        <div className="text-sm text-slate-400">Absolute values matter less than direction and speed.</div>
      </div>
      <div className="mt-5 grid gap-3">
        {changes.map((change) => {
          const active = change.id === selectedMetricId;
          const up = change.dir === 'up';
          return (
            <button
              key={change.id}
              onClick={() => setSelectedMetricId(change.id)}
              className={`flex items-center justify-between rounded-[22px] border px-4 py-4 text-left transition ${
                active ? 'border-sky-300/30 bg-sky-400/10' : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.06]'
              }`}
            >
              <div>
                <div className="text-sm font-medium text-slate-100">{change.name}</div>
                <div className="mt-1 text-sm text-slate-400">{change.detail}</div>
              </div>
              <div className={`ml-4 rounded-full px-3 py-1 text-sm font-medium ${up ? 'bg-red-400/10 text-red-300' : 'bg-emerald-400/10 text-emerald-300'}`}>
                {up ? '▲' : '▼'} {change.delta}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function MetricsGrid({ metrics, selectedMetricId, setSelectedMetricId, activeAlert }: { metrics: MetricItem[]; selectedMetricId: string; setSelectedMetricId: (id: string) => void; activeAlert: AlertItem }) {
  return (
    <section className="rounded-[28px] border border-white/10 bg-[#0b1626] p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-slate-400">Metric entry points</div>
          <h2 className="mt-2 text-2xl font-semibold">Cards that actually lead somewhere</h2>
        </div>
        <div className="text-sm text-slate-400">The relevant cards are pulled forward by the active alert.</div>
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <AnimatePresence initial={false}>
          {metrics.map((metric) => {
            const selected = metric.id === selectedMetricId;
            const linkedToAlert = activeAlert.metricIds.includes(metric.id);
            return (
              <motion.button
                layout
                key={metric.id}
                onClick={() => setSelectedMetricId(metric.id)}
                className={`group rounded-[24px] border p-5 text-left transition ${
                  selected
                    ? 'border-sky-300/35 bg-sky-400/10 shadow-[0_0_0_1px_rgba(125,211,252,0.14)]'
                    : linkedToAlert
                      ? 'border-white/15 bg-white/[0.06]'
                      : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.06]'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-100">{metric.title}</span>
                      {linkedToAlert && <span className="rounded-full bg-red-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-red-200">alert linked</span>}
                    </div>
                    <div className="mt-3 flex items-end gap-2">
                      <span className="text-4xl font-semibold leading-none">{metric.value}</span>
                      <span className="mb-1 text-sm text-slate-400">{metric.unit}</span>
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-sm text-slate-400">
                      <StatusDot status={metric.status} />
                      {metric.delta}
                    </div>
                  </div>
                  <ChevronRight className={`h-5 w-5 transition ${selected ? 'translate-x-1 text-sky-200' : 'text-slate-500 group-hover:translate-x-1 group-hover:text-slate-300'}`} />
                </div>

                <MiniBars values={metric.series} />

                <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-sm text-slate-300">
                  {metric.insight}
                </div>
              </motion.button>
            );
          })}
        </AnimatePresence>
      </div>
    </section>
  );
}

function DrillPanel({ selectedMetric, activeAlert }: { selectedMetric: MetricItem; activeAlert: AlertItem }) {
  return (
    <section className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(10,20,34,0.98),rgba(5,12,22,1))] p-6 shadow-[0_20px_70px_rgba(0,0,0,0.3)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-slate-400">Drill-through panel</div>
          <h2 className="mt-2 text-2xl font-semibold">{selectedMetric.title}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">{selectedMetric.summary}</p>
        </div>
        <div className={`rounded-full px-3 py-1 text-xs font-medium ${severityBadge(selectedMetric.status)}`}>{selectedMetric.status}</div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
        <GlassCard>
          <div className="flex items-end justify-between gap-4">
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-slate-400">90 day pattern</div>
              <div className="mt-2 text-3xl font-semibold">{selectedMetric.value} <span className="text-base font-normal text-slate-400">{selectedMetric.unit}</span></div>
            </div>
            <div className="text-sm text-slate-400">Influenced by {activeAlert.title}</div>
          </div>
          <LargeTrend values={selectedMetric.series} direction={selectedMetric.direction} />
        </GlassCard>

        <GlassCard>
          <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Breakdown</div>
          <div className="mt-4 space-y-3">
            {selectedMetric.breakdown.map((item) => (
              <div key={item.label}>
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="text-slate-200">{item.label}</span>
                  <span className="font-medium text-slate-100">{item.value}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/5">
                  <div className={`h-full rounded-full ${toneBar(item.tone)}`} style={{ width: `${Math.min((item.value / maxBreakdown(selectedMetric.breakdown)) * 100, 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <InsightBlock title="Why this matters" body="This metric now has both executive relevance and investigation context. That is the missing bridge in most dashboards." icon={BrainCircuit} />
        <InsightBlock title="Likely cause" body={activeAlert.body} icon={AlertTriangle} />
        <InsightBlock title="Recommended action" body="Pull the affected product owners into the same review. Separate triage would be organizationally stupid here." icon={ShieldAlert} />
      </div>
    </section>
  );
}

function HealthRadarCard() {
  const center = { x: 120, y: 120 };
  const angles = [-90, -38, 14, 66, 118, 170, 222];
  const outer = 98;
  const points = radarScores
    .map((item, i) => polar(center.x, center.y, (item.value / 100) * outer, angles[i]))
    .map((p) => `${p.x},${p.y}`)
    .join(' ');

  return (
    <section className="rounded-[28px] border border-white/10 bg-[#0b1626] p-6">
      <div className="text-xs uppercase tracking-[0.24em] text-slate-400">System shape</div>
      <h2 className="mt-2 text-2xl font-semibold">Engineering health radar</h2>
      <p className="mt-2 text-sm leading-6 text-slate-300">Weakness should be visible as form. If leaders need to read ten cards to understand the system, the design failed.</p>
      <div className="mt-5 rounded-[24px] border border-white/10 bg-[radial-gradient(circle_at_center,rgba(56,189,248,0.12),transparent_38%),linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01))] p-4">
        <svg viewBox="0 0 240 240" className="mx-auto w-full max-w-[340px]">
          {[36, 64, 98].map((r) => <circle key={r} cx="120" cy="120" r={r} fill="none" stroke="rgba(255,255,255,0.08)" />)}
          {[-90, -38, 14, 66, 118, 170, 222].map((angle, i) => {
            const end = polar(center.x, center.y, outer, angle);
            return <line key={i} x1={center.x} y1={center.y} x2={end.x} y2={end.y} stroke="rgba(255,255,255,0.08)" />;
          })}
          <polygon points={points} fill="rgba(56,189,248,0.18)" stroke="rgba(125,211,252,0.9)" strokeWidth="2" />
          {radarScores.map((item, i) => {
            const p = polar(center.x, center.y, outer + 20, [-90, -38, 14, 66, 118, 170, 222][i]);
            return <text key={item.label} x={p.x} y={p.y} fill="rgba(226,232,240,0.9)" fontSize="10" textAnchor="middle">{item.label}</text>;
          })}
        </svg>
      </div>
    </section>
  );
}

function AiPanel({ activeAlert, selectedMetric }: { activeAlert: AlertItem; selectedMetric: MetricItem }) {
  const notes = [
    `${activeAlert.title} is the strongest narrative driver in the current state of the system.`,
    `${selectedMetric.title} is the most useful drill path because it converts alert noise into focused action.`,
    'The dashboard should keep reinforcing connections between alerts, metrics, and products. Otherwise you are just repainting confusion.',
  ];

  return (
    <section className="rounded-[28px] border border-violet-300/10 bg-[linear-gradient(180deg,rgba(76,29,149,0.10),rgba(10,20,34,0.92))] p-6">
      <div className="text-xs uppercase tracking-[0.24em] text-violet-200">AI narrative layer</div>
      <h2 className="mt-2 text-2xl font-semibold">Executive interpretation</h2>
      <div className="mt-5 space-y-3">
        {notes.map((note) => (
          <div key={note} className="rounded-[22px] border border-white/10 bg-white/5 p-4 text-sm leading-6 text-slate-200">{note}</div>
        ))}
      </div>
    </section>
  );
}

function AnomalyRiver({ activeAlert }: { activeAlert: AlertItem }) {
  const rows = [
    { label: 'Security', values: [18, 24, 26, 34, 42, 60, 48, 40, 34, 26] },
    { label: 'Infrastructure', values: [12, 18, 20, 28, 46, 72, 84, 68, 42, 34] },
    { label: 'Delivery', values: [26, 24, 22, 20, 18, 22, 24, 28, 24, 18] },
    { label: 'Quality', values: [10, 12, 14, 16, 18, 22, 18, 14, 12, 10] },
  ];

  return (
    <section className="rounded-[28px] border border-white/10 bg-[#0b1626] p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-slate-400">Temporal anomaly map</div>
          <h2 className="mt-2 text-2xl font-semibold">Anomaly river</h2>
        </div>
        <div className="text-sm text-slate-400">Current spotlight: {activeAlert.title}</div>
      </div>
      <div className="mt-5 space-y-4">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="font-medium text-slate-200">{row.label}</span>
              <span className="text-slate-500">10 intervals</span>
            </div>
            <div className="flex h-16 items-center gap-1 rounded-2xl border border-white/10 bg-white/[0.03] px-2">
              {row.values.map((v, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0.4, scaleY: 0.2 }}
                  animate={{ opacity: 1, scaleY: Math.max(v / 84, 0.2) }}
                  transition={{ delay: i * 0.02 }}
                  className="h-full flex-1 origin-bottom rounded-xl bg-gradient-to-t from-fuchsia-500/30 via-sky-400/40 to-cyan-300/60"
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ProductGalaxy({ activeAlert, linkedProducts }: { activeAlert: AlertItem; linkedProducts: Set<string> }) {
  return (
    <section className="rounded-[28px] border border-white/10 bg-[#0b1626] p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-slate-400">Connected risk layer</div>
          <h2 className="mt-2 text-2xl font-semibold">Product risk galaxy</h2>
        </div>
        <div className="text-sm text-slate-400">Affected cluster: {activeAlert.impact.join(', ')}</div>
      </div>
      <div className="relative mt-5 h-[360px] overflow-hidden rounded-[24px] border border-white/10 bg-[radial-gradient(circle_at_center,rgba(56,189,248,0.18),transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01))]">
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" fill="none">
          <path d="M20 16 C 32 24, 38 30, 46 40" stroke="rgba(255,255,255,0.14)" strokeWidth="0.5" />
          <path d="M74 20 C 62 26, 54 31, 46 40" stroke="rgba(255,255,255,0.14)" strokeWidth="0.5" />
          <path d="M46 40 C 38 52, 30 64, 24 76" stroke="rgba(255,255,255,0.14)" strokeWidth="0.5" />
          <path d="M46 40 C 58 54, 66 66, 76 78" stroke="rgba(255,255,255,0.14)" strokeWidth="0.5" />
        </svg>
        {galaxyNodes.map((node) => {
          const highlighted = linkedProducts.has(node.name);
          return (
            <motion.div
              key={node.name}
              initial={{ scale: 0.9, opacity: 0.7 }}
              animate={{ scale: highlighted ? 1.06 : 1, opacity: highlighted ? 1 : 0.78 }}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${node.x}%`, top: `${node.y}%` }}
            >
              <div
                className={`grid place-items-center rounded-full ring-8 ring-white/5 shadow-[0_0_30px_rgba(255,255,255,0.06)] ${riskColor(node.risk)}`}
                style={{ width: node.size, height: node.size }}
              >
                <div className="px-2 text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-950">{node.risk}</div>
              </div>
              <div className="mt-3 text-center text-xs font-medium text-slate-200">{node.name}</div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}

function RiskMatrix({ linkedProducts }: { linkedProducts: Set<string> }) {
  return (
    <section className="rounded-[28px] border border-white/10 bg-[#0b1626] p-6">
      <div className="text-xs uppercase tracking-[0.24em] text-slate-400">Comparative scan</div>
      <h2 className="mt-2 text-2xl font-semibold">Product risk matrix</h2>
      <div className="mt-5 overflow-hidden rounded-[24px] border border-white/10">
        <div className="grid grid-cols-[1.5fr_repeat(3,1fr)] bg-white/5 px-4 py-3 text-xs uppercase tracking-[0.2em] text-slate-400">
          <div>Product</div>
          <div>Security</div>
          <div>Bugs</div>
          <div>Delivery</div>
        </div>
        {matrix.map((row) => {
          const highlighted = linkedProducts.has(row.product);
          return (
            <div key={row.product} className={`grid grid-cols-[1.5fr_repeat(3,1fr)] items-center border-t px-4 py-4 text-sm ${highlighted ? 'border-sky-300/20 bg-sky-400/[0.04]' : 'border-white/10'}`}>
              <div className="font-medium text-slate-100">{row.product}</div>
              <MatrixCell tone={row.security} />
              <MatrixCell tone={row.bugs} />
              <MatrixCell tone={row.delivery} />
            </div>
          );
        })}
      </div>
    </section>
  );
}

function MiniBars({ values }: { values: number[] }) {
  return (
    <div className="mt-5">
      <div className="mb-2 text-xs uppercase tracking-[0.2em] text-slate-500">7 day shape</div>
      <div className="flex h-24 items-end gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-3">
        {values.map((v, i) => (
          <motion.div
            key={i}
            initial={{ height: 0 }}
            animate={{ height: `${v}%` }}
            transition={{ delay: i * 0.03, duration: 0.35 }}
            className="flex-1 rounded-full bg-gradient-to-t from-sky-500/80 to-cyan-300/80"
          />
        ))}
      </div>
    </div>
  );
}

function LargeTrend({ values, direction }: { values: number[]; direction: MetricItem['direction'] }) {
  const max = Math.max(...values);
  const min = Math.min(...values);
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * 100;
      const y = 100 - ((v - min) / Math.max(max - min, 1)) * 74 - 8;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <div className="mt-5 rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
      <svg viewBox="0 0 100 100" className="h-52 w-full">
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(56,189,248,0.35)" />
            <stop offset="100%" stopColor="rgba(56,189,248,0)" />
          </linearGradient>
        </defs>
        {[20, 40, 60, 80].map((y) => <line key={y} x1="0" y1={y} x2="100" y2={y} stroke="rgba(255,255,255,0.06)" strokeWidth="0.5" />)}
        <polyline fill="none" stroke={direction === 'up' ? 'rgba(248,113,113,0.95)' : direction === 'down' ? 'rgba(52,211,153,0.95)' : 'rgba(148,163,184,0.95)'} strokeWidth="2.4" points={points} />
        <polygon points={`0,100 ${points} 100,100`} fill="url(#trendFill)" />
      </svg>
    </div>
  );
}

function InsightBlock({ title, body, icon: Icon }: { title: string; body: string; icon: LucideIcon }) {
  return (
    <div className="rounded-[22px] border border-white/10 bg-white/[0.04] p-4">
      <div className="flex items-center gap-2 text-slate-100">
        <Icon className="h-4 w-4 text-sky-300" />
        <span className="text-sm font-medium">{title}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-300">{body}</p>
    </div>
  );
}

function ActionChip({ icon: Icon, label, tone = 'neutral' }: { icon: LucideIcon; label: string; tone?: 'danger' | 'good' | 'warn' | 'neutral' }) {
  const tones = {
    danger: 'border-red-300/20 bg-red-400/10 text-red-200',
    good: 'border-emerald-300/20 bg-emerald-400/10 text-emerald-200',
    warn: 'border-amber-300/20 bg-amber-400/10 text-amber-200',
    neutral: 'border-white/10 bg-white/5 text-slate-200',
  };

  return (
    <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${tones[tone]}`}>
      <Icon className="h-4 w-4" />
      {label}
    </div>
  );
}

function GlassCard({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-[24px] border border-white/10 bg-white/5 p-5 backdrop-blur-sm ${className}`}>{children}</div>;
}

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <GlassCard>
      <div className="text-xs uppercase tracking-[0.22em] text-slate-400">{label}</div>
      <div className="mt-2 text-3xl font-semibold">{value}</div>
    </GlassCard>
  );
}

function StatusDot({ status }: { status: MetricStatus }) {
  const cls = {
    Critical: 'bg-red-400',
    'At risk': 'bg-orange-400',
    Watch: 'bg-amber-300',
    Improving: 'bg-emerald-400',
  };
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${cls[status] ?? 'bg-slate-400'}`} />;
}

function MatrixCell({ tone }: { tone: Tone }) {
  return <div className={`h-10 w-24 rounded-2xl border border-white/10 ${toneBar(tone)}`} />;
}

function severityBadge(severity: Severity | MetricStatus) {
  const map = {
    Critical: 'bg-red-400/10 text-red-200',
    High: 'bg-orange-400/10 text-orange-200',
    Medium: 'bg-amber-300/10 text-amber-200',
    'At risk': 'bg-orange-400/10 text-orange-200',
    Watch: 'bg-amber-300/10 text-amber-200',
    Improving: 'bg-emerald-400/10 text-emerald-200',
  };
  return map[severity] ?? 'bg-white/10 text-slate-200';
}

function toneBar(tone: Tone) {
  const map = {
    critical: 'bg-red-500/80',
    high: 'bg-orange-400/80',
    warn: 'bg-amber-300/80',
    ok: 'bg-emerald-400/80',
  };
  return map[tone] ?? 'bg-slate-500/70';
}

function riskColor(risk: GalaxyNode['risk']) {
  const map = {
    Critical: 'bg-red-500/85',
    High: 'bg-orange-400/85',
    Warn: 'bg-yellow-300/85',
  };
  return map[risk] ?? 'bg-slate-400/80';
}

function maxBreakdown(items: BreakdownItem[]) {
  return Math.max(...items.map((i) => i.value), 1);
}

function severityRank(status: MetricStatus) {
  const rank: Record<MetricStatus, number> = {
    Critical: 4,
    'At risk': 3,
    Watch: 2,
    Improving: 1,
  };
  return rank[status];
}

function polar(cx: number, cy: number, r: number, angle: number) {
  const rad = (angle * Math.PI) / 180;
  return {
    x: cx + Math.cos(rad) * r,
    y: cy + Math.sin(rad) * r,
  };
}
