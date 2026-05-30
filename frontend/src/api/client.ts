const API_BASE = '/api/v1';

let apiKey: string | null = localStorage.getItem('api_key');

export function setApiKey(key: string) {
  apiKey = key;
  localStorage.setItem('api_key', key);
}

export function getApiKey(): string | null {
  return apiKey;
}

export function clearApiKey() {
  apiKey = null;
  localStorage.removeItem('api_key');
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: { rawResponse?: boolean; noAuth?: boolean },
): Promise<T> {
  const headers: Record<string, string> = {};

  if (!options?.noAuth && apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  const init: RequestInit = { method, headers };

  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }

  const res = await fetch(`${API_BASE}${path}`, init);

  if (res.status === 401) {
    clearApiKey();
    throw new ApiError(401, 'API Key 无效或已过期，请重新设置');
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    let detail = text;
    try {
      const j = JSON.parse(text);
      detail = j.detail || text;
    } catch { /* not json */ }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204 || options?.rawResponse) {
    return undefined as T;
  }

  return res.json();
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

// ── 便捷方法 ────────────────────────────────────

export const api = {
  get: <T>(path: string, opts?: { noAuth?: boolean }) =>
    request<T>('GET', path, undefined, opts),

  post: <T>(path: string, body?: unknown, opts?: { noAuth?: boolean }) =>
    request<T>('POST', path, body, opts),

  put: <T>(path: string, body?: unknown) =>
    request<T>('PUT', path, body),

  delete: <T>(path: string) =>
    request<T>('DELETE', path),

  upload: <T>(path: string, file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return request<T>('POST', path, fd);
  },
};
