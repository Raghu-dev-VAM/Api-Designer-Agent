import { useState } from 'react';
import { login, register } from '../services/authService';
import Icon from './Icon';

interface Props {
  onAuthenticated: () => void;
}

export default function AuthPage({ onAuthenticated }: Props) {
  const [mode, setMode]         = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const [success, setSuccess]   = useState('');

  const reset = () => { setError(''); setSuccess(''); };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    reset();
    if (!username.trim() || !password.trim()) { setError('Username and password are required.'); return; }
    setLoading(true);
    try {
      await login(username.trim(), password);
      onAuthenticated();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally { setLoading(false); }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    reset();
    if (!username.trim() || !email.trim() || !password.trim()) { setError('All fields are required.'); return; }
    if (password.length < 6) { setError('Password must be at least 6 characters.'); return; }
    setLoading(true);
    try {
      await register(username.trim(), email.trim(), password);
      setSuccess('Account created! Please log in.');
      setMode('login');
      setPassword('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally { setLoading(false); }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">

        {/* Logo + Title */}
        <div className="auth-header">
          <div className="auth-logo"><Icon name="logo" size={36} /></div>
          <h1 className="auth-title">API Designer Agent</h1>
          <p className="auth-subtitle">AI-powered OpenAPI specification generator</p>
        </div>

        {/* Tab switcher */}
        <div className="auth-tabs">
          <button className={mode === 'login' ? 'auth-tab active' : 'auth-tab'} onClick={() => { setMode('login'); reset(); }}>
            Sign In
          </button>
          <button className={mode === 'register' ? 'auth-tab active' : 'auth-tab'} onClick={() => { setMode('register'); reset(); }}>
            Create Account
          </button>
        </div>

        {/* Error / Success banners */}
        {error   && <div className="auth-banner error">⚠ {error}</div>}
        {success && <div className="auth-banner success">✓ {success}</div>}

        {/* Login Form */}
        {mode === 'login' && (
          <form className="auth-form" onSubmit={handleLogin}>
            <div className="auth-field">
              <label>Username</label>
              <input
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoFocus
                autoComplete="username"
              />
            </div>
            <div className="auth-field">
              <label>Password</label>
              <div className="auth-pass-wrap">
                <input
                  type={showPass ? 'text' : 'password'}
                  placeholder="Enter your password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
                <button type="button" className="auth-pass-toggle" onClick={() => setShowPass(v => !v)}>
                  {showPass ? '🙈' : '👁'}
                </button>
              </div>
            </div>
            <button type="submit" className="auth-submit" disabled={loading}>
              {loading ? <span className="auth-spinner" /> : null}
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
        )}

        {/* Register Form */}
        {mode === 'register' && (
          <form className="auth-form" onSubmit={handleRegister}>
            <div className="auth-field">
              <label>Username</label>
              <input
                type="text"
                placeholder="Choose a username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoFocus
                autoComplete="username"
              />
            </div>
            <div className="auth-field">
              <label>Email</label>
              <input
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                autoComplete="email"
              />
            </div>
            <div className="auth-field">
              <label>Password <span className="auth-hint-text">(min 6 characters)</span></label>
              <div className="auth-pass-wrap">
                <input
                  type={showPass ? 'text' : 'password'}
                  placeholder="Create a password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete="new-password"
                />
                <button type="button" className="auth-pass-toggle" onClick={() => setShowPass(v => !v)}>
                  {showPass ? '🙈' : '👁'}
                </button>
              </div>
            </div>
            <button type="submit" className="auth-submit" disabled={loading}>
              {loading ? <span className="auth-spinner" /> : null}
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>
        )}

        <p className="auth-footer-note">
          {mode === 'login'
            ? <>No account? <button className="auth-link" onClick={() => { setMode('register'); reset(); }}>Create one</button></>
            : <>Already have an account? <button className="auth-link" onClick={() => { setMode('login'); reset(); }}>Sign in</button></>
          }
        </p>
      </div>
    </div>
  );
}
