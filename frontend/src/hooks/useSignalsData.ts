import { useState, useEffect } from 'react';
import { SignalsPayload } from '../types/signals';
import { API_BASE } from '../lib/apiBase';

export function useSignalsData() {
  const [data, setData] = useState<SignalsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/intelligence/signals`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<SignalsPayload>;
      })
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  return { data, error, loading };
}
