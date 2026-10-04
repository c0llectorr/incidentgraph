/**
 * Single source of truth for API routing (PRD §12.8: no hard-coded URLs in
 * components). Local dev leaves VITE_API_BASE_URL unset → same-origin `/api`
 * (the Vite dev proxy forwards to :8000). In production, VITE_API_BASE_URL
 * is set to the backend's absolute URL (e.g. a Hugging Face Space), because
 * a static deployment has no proxy.
 */
export const API_ORIGIN: string = import.meta.env.VITE_API_BASE_URL ?? "";

export const API_BASE: string = `${API_ORIGIN}/api/v1`;
