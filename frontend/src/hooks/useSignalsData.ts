import { useState, useEffect } from 'react';
import { SignalsPayload } from '../types/signals';

export function useSignalsData() {
  const [data, setData] = useState<SignalsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/v1/intelligence/signals')
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
