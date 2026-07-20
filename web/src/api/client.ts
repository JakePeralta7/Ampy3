/**
 * Unified HTTP client for API communication.
 *
 * Handles base configuration, error handling, and request/response intercepting.
 * All API calls should use this client or services built on top of it.
 */

const API_BASE_URL = "/api";

export interface FetchOptions extends RequestInit {
  timeout?: number;
}

/**
 * Creates a fetch request with standard configuration and error handling.
 *
 * @param endpoint - API endpoint path (relative to API base URL)
 * @param options - Fetch options (method, body, headers, timeout, etc.)
 * @returns Response from the server
 * @throws Error if the request fails
 */
export async function apiRequest<T = unknown>(
  endpoint: string,
  options: FetchOptions = {},
): Promise<T> {
  const { timeout = 30000, ...fetchOptions } = options;
  const url = `${API_BASE_URL}${endpoint}`;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...fetchOptions.headers,
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      if (response.status === 401 && window.location.pathname !== "/login") {
        window.location.href = "/login";
        throw new Error("unauthenticated");
      }
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Unknown API error occurred");
  }
}

/**
 * Convenience GET request helper.
 */
export async function apiGet<T = unknown>(endpoint: string, options?: FetchOptions): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: "GET" });
}

/**
 * Convenience POST request helper.
 */
export async function apiPost<T = unknown>(
  endpoint: string,
  data?: unknown,
  options?: FetchOptions,
): Promise<T> {
  return apiRequest<T>(endpoint, {
    ...options,
    method: "POST",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * Convenience PUT request helper.
 */
export async function apiPut<T = unknown>(
  endpoint: string,
  data?: unknown,
  options?: FetchOptions,
): Promise<T> {
  return apiRequest<T>(endpoint, {
    ...options,
    method: "PUT",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * Convenience DELETE request helper.
 */
export async function apiDelete<T = unknown>(endpoint: string, options?: FetchOptions): Promise<T> {
  return apiRequest<T>(endpoint, { ...options, method: "DELETE" });
}
