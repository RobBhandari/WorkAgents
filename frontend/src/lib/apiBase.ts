/// <reference types="vite/client" />
// In dev, Vite proxies /api → localhost:8000
// In production, VITE_API_BASE_URL points to the Azure App Service
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
