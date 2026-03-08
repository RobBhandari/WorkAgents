export interface HealthScorePayload {
  generated_at: string;
  score: number;
  label: 'healthy' | 'fair' | 'at risk';
  contributing_metrics: number;
  total_metrics: number;
}
