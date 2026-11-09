import createClient from "openapi-fetch";
import type { paths } from "./schema.gen";

export function getApiBaseUrl(
  env: { VITE_API_BASE_URL?: string } = import.meta.env,
): string {
  const value = env.VITE_API_BASE_URL?.trim();
  if (!value) {
    throw new Error("VITE_API_BASE_URL is not set");
  }
  return value.replace(/\/+$/, "");
}

export const api = createClient<paths>({
  baseUrl: getApiBaseUrl(),
  credentials: "include",
  // Resolve fetch at call time so tests (and polyfills) can replace globalThis.fetch.
  fetch: (request) => globalThis.fetch(request),
});
