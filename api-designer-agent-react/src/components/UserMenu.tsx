import { useState, useRef, useEffect } from 'react';
import type { AuthUser } from '../services/authService';

interface Props {
  user: AuthUser;
  onProfile: () => void;
  onResetPassword: () => void;
  onLogout: () => void;
}

export default function UserMenu({ user, onProfile, onResetPassword, onLogout }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="user-menu-wrap" ref={ref}>
      <button className="user-menu-trigger" onClick={() => setOpen(v => !v)} title={user.username}>
        <span className="auth-user-avatar">{user.username[0].toUpperCase()}</span>
        <span className="auth-user-name">{user.username}</span>
        <span className="user-menu-caret">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="user-menu-popup">
          <div className="user-menu-popup-header">
            <span className="user-menu-popup-avatar">{user.username[0].toUpperCase()}</span>
            <div>
              <div className="user-menu-popup-name">{user.username}</div>
              <div className="user-menu-popup-email">{user.email}</div>
            </div>
          </div>
          <div className="user-menu-popup-divider" />
          <button className="user-menu-item" onClick={() => { setOpen(false); onProfile(); }}>
            <span className="user-menu-item-icon">👤</span> Profile
          </button>
          <button className="user-menu-item" onClick={() => { setOpen(false); onResetPassword(); }}>
            <span className="user-menu-item-icon">🔑</span> Reset Password
          </button>
          <div className="user-menu-popup-divider" />
          <button className="user-menu-item danger" onClick={() => { setOpen(false); onLogout(); }}>
            <span className="user-menu-item-icon">🚪</span> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
