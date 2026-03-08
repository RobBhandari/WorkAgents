export interface Signal {
  id: string;
  metric_id: string;
  type: 'threshold_breach' | 'sustained_deterioration' | 'recovery_trend';
  severity: 'critical' | 'warning' | 'info';
  direction: 'up' | 'down';
  title: string;
  message: string;
  current_value: number;
  baseline_value: number;
  window_weeks: number;
}

export interface SignalsPayload {
  generated_at: string;
  signal_count: number;
  signals: Signal[];
}
