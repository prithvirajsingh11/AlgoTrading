/**
 * Central API Client for AlgoTrade.
 * Reads API base URL dynamically from settings or defaults to http://localhost:8000.
 * Normalizes backend error responses and enforces timeouts.
 */

const API_BASE_URL_KEY = "algotrade_api_base_url";
export const DEFAULT_API_BASE = "http://localhost:8000";

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem(API_BASE_URL_KEY);
    if (saved && saved.trim()) {
      return saved.trim().replace(/\/+$/, "");
    }
  }
  return DEFAULT_API_BASE;
}

export function setApiBaseUrl(url: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(API_BASE_URL_KEY, url.trim().replace(/\/+$/, ""));
  }
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${baseUrl}/api/v1${cleanEndpoint}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout for heavy backtests

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: options.signal || controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status} ${response.statusText}`;
      let errorData: unknown = null;
      try {
        errorData = await response.json();
        if (typeof errorData === "object" && errorData !== null && "detail" in errorData) {
          const detail = (errorData as { detail: unknown }).detail;
          errorMessage = typeof detail === "string" ? detail : JSON.stringify(detail);
        }
      } catch {
        // Body wasn't JSON
      }
      throw new ApiError(errorMessage, response.status, errorData);
    }

    return (await response.json()) as T;
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    if (err instanceof ApiError) {
      throw err;
    }
    if ((err as Error).name === "AbortError") {
      throw new ApiError("Request timed out after 60 seconds.", 408);
    }
    throw new ApiError(
      (err as Error).message || "Network error. Is the FastAPI backend running?",
      0
    );
  }
}
