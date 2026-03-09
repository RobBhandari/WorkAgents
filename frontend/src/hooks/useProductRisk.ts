import { useState, useEffect } from 'react';
import { ProductRiskPayload } from '../types/product_risk';
import { API_BASE, AUTH_HEADER } from '../lib/apiBase';

export function useProductRisk() {
  const [data, setData] = useState<ProductRiskPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/intelligence/product-risk`, { headers: AUTH_HEADER })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<ProductRiskPayload>;
      })
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  return { data, error, loading };
}
