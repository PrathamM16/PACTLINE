import { API_BASE } from './api';

const TOKEN_KEY = 'pactline.token';
const WORKSPACE_KEY = 'pactline.workspace';

export interface LoginResponse {
  access_token: string;
  user: { id: string; name: string; email: string };
  workspaces: { id: string; name: string; role: string }[];
}

export function isLoggedIn(): boolean {
  return !!sessionStorage.getItem(TOKEN_KEY) && !!sessionStorage.getItem(WORKSPACE_KEY);
}

export function logout(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(WORKSPACE_KEY);
}

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = sessionStorage.getItem(TOKEN_KEY);
  const workspace = sessionStorage.getItem(WORKSPACE_KEY);
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (workspace) {
    headers['X-Workspace-Id'] = workspace;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    method: init.method ?? (init.body ? 'POST' : 'GET'),
    headers,
    body: init.body ? JSON.stringify(init.body) : undefined,
  });
  if (response.status === 401 && token) {
    logout();
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, typeof detail.detail === 'string' ? detail.detail : response.statusText);
  }
  return response.json() as Promise<T>;
}

export async function authenticate(mode: 'login' | 'register', email: string, password: string, name: string): Promise<void> {
  const body = mode === 'register' ? { email, password, name } : { email, password };
  const result = await api<LoginResponse>(`/api/auth/${mode}`, { body });
  sessionStorage.setItem(TOKEN_KEY, result.access_token);
  sessionStorage.setItem(WORKSPACE_KEY, result.workspaces[0].id);
}
