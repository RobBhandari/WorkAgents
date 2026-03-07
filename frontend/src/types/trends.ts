export interface MetricItem {
  id: string;
  icon: string;
  title: string;
  description: string;
  current: number | string;
  unit: string;
  change: number | string;
  changeLabel: string;
  data: number[];
  arrow: string;
  cssClass: string;
  ragColor: string;
  dashboardUrl: string;
}

export interface AlertItem {
  dashboard: string;
  project_name: string;
  metric_name: string;
  metric_date: string;
  alert_type: string;
  severity: 'critical' | 'warn' | 'medium';
  severity_emoji: string;
  message: string;
  root_cause_hint: string;
}

export interface TrendsPayload {
  metrics: MetricItem[];
  alerts: AlertItem[];
  timestamp: string;
}
