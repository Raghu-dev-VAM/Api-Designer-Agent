import { useState } from 'react';
import { getUser, resetPassword } from '../services/authService';
import Icon from './Icon';

interface Props {
  onClose: () => void;
  view?: 'profile' | 'reset-password';
}

export default function EditProfilePage({ onClose, view = 'profile' }: Props) {
  const user = getUser();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword]         = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrent, setShowCurrent]         = useState(false);
  const [showNew, setShowNew]                 = useState(false);
  const [showConfirm, setShowConfirm]         = useState(false);
  const [loading, setLoading]                 = useState(false);
  const [error, setError]                     = useState('');
  const [success, setSuccess]                 = useState('');

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); setSuccess('');
    if (!currentPassword || !newPassword || !confirmPassword) {
      setError('All fields are required.'); return;
    }
    if (newPassword.length < 6) {
      setError('New password must be at least 6 characters.'); return;
    }
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.'); return;
    }
    if (currentPassword === newPassword) {
      setError('New password must differ from current password.'); return;
    }
    setLoading(true);
    try {
      await resetPassword(currentPassword, newPassword);
      setSuccess('Password updated successfully!');
      setCurrentPassword(''); setNewPassword(''); setConfirmPassword('');
      setTimeout(() => onClose(), 1200);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Password reset failed');
    } finally { setLoading(false); }
  };

  return (
    <div className="edit-profile-overlay">
      <div className="edit-profile-modal">

        {/* Header */}
        <div className="edit-profile-header">
          <div className="edit-profile-header-title">
            <div className="edit-profile-avatar">
              {user?.username?.[0]?.toUpperCase() ?? '?'}
            </div>
            <div>
              <div className="edit-profile-name">{user?.username ?? '—'}</div>
              <div className="edit-profile-email">{user?.email ?? '—'}</div>
            </div>
          </div>
          <button className="edit-profile-close" onClick={onClose} title="Close">
            <Icon name="plus" size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="edit-profile-body">

          {/* Profile Info (read-only) */}
          {view === 'profile' && <section className="edit-profile-section">
            <div className="edit-profile-section-title">Profile Information</div>
            <div className="edit-profile-info-grid">
              <div className="edit-profile-info-item">
                <span className="edit-profile-info-label">Username</span>
                <span className="edit-profile-info-value">{user?.username ?? '—'}</span>
              </div>
              <div className="edit-profile-info-item">
                <span className="edit-profile-info-label">Email</span>
                <span className="edit-profile-info-value">{user?.email ?? '—'}</span>
              </div>
              <div className="edit-profile-info-item">
                <span className="edit-profile-info-label">Member Since</span>
                <span className="edit-profile-info-value">
                  {user?.created_at ? new Date(user.created_at).toLocaleDateString([], { dateStyle: 'medium' }) : '—'}
                </span>
              </div>
              <div className="edit-profile-info-item">
                <span className="edit-profile-info-label">Role</span>
                <span className="edit-profile-info-value edit-profile-role-badge">API Designer</span>
              </div>
            </div>
          </section>}

          {/* Reset Password */}
          {view === 'reset-password' && <section className="edit-profile-section">
            <div className="edit-profile-section-title">Reset Password</div>

            {error   && <div className="auth-banner error"   style={{ marginBottom: 4 }}>⚠ {error}</div>}
            {success && <div className="auth-banner success" style={{ marginBottom: 4 }}>✓ {success}</div>}

            <form className="edit-profile-form" onSubmit={handleResetPassword}>
              {/* Current Password */}
              <div className="auth-field">
                <label>Current Password</label>
                <div className="auth-pass-wrap">
                  <input
                    type={showCurrent ? 'text' : 'password'}
                    placeholder="Enter current password"
                    value={currentPassword}
                    onChange={e => setCurrentPassword(e.target.value)}
                    autoComplete="current-password"
                  />
                  <button type="button" className="auth-pass-toggle" onClick={() => setShowCurrent(v => !v)}>
                    {showCurrent ? '🙈' : '👁'}
                  </button>
                </div>
              </div>

              {/* New Password */}
              <div className="auth-field">
                <label>New Password <span className="auth-hint-text">(min 6 characters)</span></label>
                <div className="auth-pass-wrap">
                  <input
                    type={showNew ? 'text' : 'password'}
                    placeholder="Enter new password"
                    value={newPassword}
                    onChange={e => setNewPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                  <button type="button" className="auth-pass-toggle" onClick={() => setShowNew(v => !v)}>
                    {showNew ? '🙈' : '👁'}
                  </button>
                </div>
              </div>

              {/* Confirm New Password */}
              <div className="auth-field">
                <label>Confirm New Password</label>
                <div className="auth-pass-wrap">
                  <input
                    type={showConfirm ? 'text' : 'password'}
                    placeholder="Re-enter new password"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                  <button type="button" className="auth-pass-toggle" onClick={() => setShowConfirm(v => !v)}>
                    {showConfirm ? '🙈' : '👁'}
                  </button>
                </div>
              </div>

              {/* Password strength indicator */}
              {newPassword.length > 0 && (
                <div className="edit-profile-strength">
                  <div className="edit-profile-strength-bar">
                    <div
                      className={`edit-profile-strength-fill ${
                        newPassword.length < 6 ? 'weak' : newPassword.length < 10 ? 'medium' : 'strong'
                      }`}
                      style={{ width: `${Math.min((newPassword.length / 12) * 100, 100)}%` }}
                    />
                  </div>
                  <span className={`edit-profile-strength-label ${
                    newPassword.length < 6 ? 'weak' : newPassword.length < 10 ? 'medium' : 'strong'
                  }`}>
                    {newPassword.length < 6 ? 'Too short' : newPassword.length < 10 ? 'Medium' : 'Strong'}
                  </span>
                </div>
              )}

              <button type="submit" className="auth-submit" disabled={loading} style={{ marginTop: 4 }}>
                {loading && <span className="auth-spinner" />}
                {loading ? 'Updating…' : 'Update Password'}
              </button>
            </form>
          </section>}
        </div>
      </div>
    </div>
  );
}
