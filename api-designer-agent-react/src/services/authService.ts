import { config } from '../config';

const TOKEN_KEY = 'api_designer_token';
const USER_KEY  = 'api_designer_user';

export interface AuthUser {
  username: string;
  email: string;
  role: string;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  username: string;
  email: string;
  role: string;
}

// ── Token helpers ─────────────────────────────────────────────────────────────
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as AuthUser) : null;
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

function saveSession(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function logout(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.href = '/';
}

// ── Auth headers — attach to every protected API call ─────────────────────────
export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── Register ──────────────────────────────────────────────────────────────────
export async function register(username: string, email: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${config.apiBaseUrl}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password }),
  });

  const data = await res.json();
  if (!res.ok) {
    const detail = data.detail;
    const msg = Array.isArray(detail)
      ? detail.map((e: { msg: string }) => e.msg).join(', ')
      : typeof detail === 'string' ? detail : 'Registration failed';
    throw new Error(msg);
  }
  return data as AuthUser;
}

// ── Login ─────────────────────────────────────────────────────────────────────
// FastAPI OAuth2PasswordRequestForm requires application/x-www-form-urlencoded
export async function login(username: string, password: string): Promise<LoginResponse> {
  const form = new URLSearchParams();
  form.append('username', username);
  form.append('password', password);

  const res = await fetch(`${config.apiBaseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });

  const data = await res.json();
  if (!res.ok) {
    const detail = data.detail;
    const msg = Array.isArray(detail)
      ? detail.map((e: { msg: string }) => e.msg).join(', ')
      : typeof detail === 'string' ? detail : 'Login failed';
    throw new Error(msg);
  }

  const loginData = data as LoginResponse;
  saveSession(loginData.access_token, {
    username: loginData.username,
    email: loginData.email,
    role: loginData.role,
    created_at: new Date().toISOString(),
  });
  window.location.href = '/';
  return loginData;
}

// ── Get current user from backend ─────────────────────────────────────────────
export async function fetchMe(): Promise<AuthUser> {
  const res = await fetch(`${config.apiBaseUrl}/api/auth/me`, {
    headers: authHeaders(),
  });
  if (res.status === 401) {
    logout();
    throw new Error('Session expired. Please log in again.');
  }
  const data = await res.json();
  if (!res.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Failed to fetch user');
  }
  return data as AuthUser;
}

// ── Reset Password ────────────────────────────────────────────────────────────
export async function resetPassword(currentPassword: string, newPassword: string): Promise<void> {
  const res = await fetch(`${config.apiBaseUrl}/api/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (res.status === 401) {
    logout();
    throw new Error('Session expired. Please log in again.');
  }
  const data = await res.json();
  if (!res.ok) {
    const detail = data.detail;
    const msg = Array.isArray(detail)
      ? detail.map((e: { msg: string }) => e.msg).join(', ')
      : typeof detail === 'string' ? detail : 'Password reset failed';
    throw new Error(msg);
  }
}
