/// <reference types="vite/client" />
// In dev, Vite proxies /api → localhost:8000 (auth injected by vite.config.ts)
// In production, VITE_API_BASE_URL points to the Azure App Service
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

const _u = import.meta.env.VITE_API_USERNAME ?? '';
const _p = import.meta.env.VITE_API_PASSWORD ?? '';
export const AUTH_HEADER: Record<string, string> =
  _u && _p ? { Authorization: `Basic ${btoa(`${_u}:${_p}`)}` } : {};
