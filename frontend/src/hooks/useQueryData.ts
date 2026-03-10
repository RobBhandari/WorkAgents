import { useState } from 'react';
import { QueryResponse, QueryContext } from '../types/query';
import { API_BASE, AUTH_HEADER } from '../lib/apiBase';

export function useQueryData() {
  const [data, setData] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(query: string, context?: QueryContext): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/v1/intelligence/query`, {
        method: 'POST',
        headers: { ...AUTH_HEADER, 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, context }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const json = (await r.json()) as QueryResponse;
      setData(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return { data, loading, error, ask };
}
