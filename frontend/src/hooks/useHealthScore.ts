import { useState, useEffect } from 'react';
import { HealthScorePayload } from '../types/health';
import { API_BASE, AUTH_HEADER } from '../lib/apiBase';

export function useHealthScore() {
  const [data, setData] = useState<HealthScorePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/intelligence/health`, { headers: AUTH_HEADER })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<HealthScorePayload>;
      })
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  return { data, error, loading };
}
