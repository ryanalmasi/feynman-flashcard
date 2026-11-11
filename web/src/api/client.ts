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

let csrfToken: string | null = null;
let unauthenticatedHandler: (() => void) | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function setUnauthenticatedHandler(fn: (() => void) | null): void {
  unauthenticatedHandler = fn;
}

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

api.use({
  onRequest({ request }) {
    if (csrfToken && !SAFE_METHODS.has(request.method.toUpperCase())) {
      request.headers.set("X-CSRF-Token", csrfToken);
    }
    return request;
  },
  async onResponse({ request, response }) {
    if (response.status !== 401) return undefined;
    if (new URL(request.url).pathname.endsWith("/auth/session")) {
      return undefined;
    }
    try {
      const body = await response.clone().json();
      if (body?.error?.code === "not_authenticated") {
        unauthenticatedHandler?.();
      }
    } catch {
      // Non-JSON 401: not our error shape, ignore.
    }
    return undefined;
  },
});

export function errorMessage(
  error: unknown,
  fallback = "Something went wrong. Try again.",
): string {
  if (typeof error === "object" && error !== null && "error" in error) {
    const inner = (error as { error?: { message?: unknown } }).error;
    if (typeof inner?.message === "string" && inner.message) {
      return inner.message;
    }
  }
  return fallback;
}

/** A 422's first detail message when present (any `loc`), else errorMessage. */
export function validationMessage(error: unknown): string {
  const details = (error as { error?: { details?: unknown } } | null)?.error
    ?.details;
  if (Array.isArray(details)) {
    const msg = (details[0] as { msg?: unknown } | undefined)?.msg;
    if (typeof msg === "string" && msg) return msg;
  }
  return errorMessage(error);
}
