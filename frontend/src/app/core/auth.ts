import { API_BASE } from './api';

const TOKEN_KEY = 'pactline.token';
const WORKSPACE_KEY = 'pactline.workspace';
const USER_KEY = 'pactline.user';

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
  sessionStorage.removeItem(USER_KEY);
}

export function currentUserName(): string {
  return sessionStorage.getItem(USER_KEY) ?? '';
}

function sessionLost(status: number, message: string): boolean {
  return status === 401 || (status === 403 && message === 'not a member of this workspace');
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
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    const message = typeof detail.detail === 'string' ? detail.detail : response.statusText;
    if (token && sessionLost(response.status, message)) {
      logout();
      window.location.assign('/login');
      throw new ApiError(response.status, 'Your session expired. Please sign in again.');
    }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

export async function authenticate(mode: 'login' | 'register', email: string, password: string, name: string): Promise<void> {
  const body = mode === 'register' ? { email, password, name } : { email, password };
  const result = await api<LoginResponse>(`/api/auth/${mode}`, { body });
  sessionStorage.setItem(TOKEN_KEY, result.access_token);
  sessionStorage.setItem(WORKSPACE_KEY, result.workspaces[0].id);
  sessionStorage.setItem(USER_KEY, result.user.name || result.user.email);
}
