import { useState, useEffect } from 'react';
import { TrendsPayload } from '../types/trends';
import { API_BASE } from '../lib/apiBase';

export function useTrendsData() {
  const [data, setData] = useState<TrendsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/dashboards/executive-trends`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<TrendsPayload>;
      })
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  return { data, error, loading };
}
