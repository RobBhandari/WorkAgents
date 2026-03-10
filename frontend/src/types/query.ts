export interface EvidenceCard {
  label: string;
  value: string;
  delta: string;
  rag: 'red' | 'amber' | 'green' | 'neutral';
}

export interface SignalPill {
  type: string;
  metric_id: string;
  severity: string;
  label: string;
}

export interface QueryResponse {
  generated_at: string;
  query: string;
  intent: string;
  narrative: string;
  signal_pills: SignalPill[];
  evidence_cards: EvidenceCard[];
  suggested_followups: string[];
  source_modules: string[];
}

export interface QueryContext {
  metric_id?: string;
  product?: string;
  domain?: string;
}
