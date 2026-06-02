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

export interface ApiErrorDetail {
  code: string;
  message: string;
  suggestion?: string;
}

export class ApiError extends Error {
  status: number;
  code: string;
  suggestion?: string;

  constructor(status: number, code: string, message: string, suggestion?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.suggestion = suggestion;
    this.name = 'ApiError';
  }
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
    throw new ApiError(401, 'AUTH_INVALID', 'API Key 无效，请在登录页重新设置', '请检查或重新输入 API Key');
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    let detail = text;
    let code = 'UNKNOWN';
    let suggestion: string | undefined;

    try {
      const j = JSON.parse(text);
      // 新格式: {"error": {"code": "...", "message": "...", "suggestion": "..."}}
      if (j.error && typeof j.error === 'object') {
        code = j.error.code || 'UNKNOWN';
        detail = j.error.message || text;
        suggestion = j.error.suggestion;
      } else if (j.detail) {
        detail = j.detail;
        code = 'INTERNAL_ERROR';
      }
    } catch { /* not json */ }
    console.error(`[API] ${method} ${path} → ${res.status} ${code}: ${detail}`);
    throw new ApiError(res.status, code, detail, suggestion);
  }

  if (res.status === 204 || options?.rawResponse) {
    return undefined as T;
  }

  return res.json();
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
