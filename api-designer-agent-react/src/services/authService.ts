import { config } from '../config';

const TOKEN_KEY = 'api_designer_token';
const USER_KEY  = 'api_designer_user';

export interface AuthUser {
  username: string;
  email: string;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  username: string;
  email: string;
}

// ── Token helpers ─────────────────────────────────────────────────────────────
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
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
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Registration failed');
  }
  return data as AuthUser;
}

// ── Login ─────────────────────────────────────────────────────────────────────
// Jira/OAuth2 form format: username + password as form fields (not JSON)
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
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Login failed');
  }

  const loginData = data as LoginResponse;
  saveSession(loginData.access_token, {
    username: loginData.username,
    email: loginData.email,
    created_at: new Date().toISOString(),
  });
  return loginData;
}

// ── Get current user from backend ─────────────────────────────────────────────
export async function fetchMe(): Promise<AuthUser> {
  const res = await fetch(`${config.apiBaseUrl}/api/auth/me`, {
    headers: authHeaders(),
  });
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
  const data = await res.json();
  if (!res.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Password reset failed');
  }
}
