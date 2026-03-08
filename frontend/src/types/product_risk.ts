export interface ProductRiskEntry {
  product: string;
  score: number;
  critical: number;
  warn: number;
  medium: number;
  domains: string[];
}

export interface ProductRiskPayload {
  generated_at: string;
  total_alerts: number;
  products: ProductRiskEntry[];
}
