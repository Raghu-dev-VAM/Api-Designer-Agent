import { useState, useEffect } from 'react';
import Icon from './Icon';
import type { Requirement } from '../types';

interface UserStoryReviewPanelProps {
  story: Requirement | null;
  onClose: () => void;
  onConfirm: (story: Requirement) => void;
  viewOnly?: boolean;
}

const METHOD_COLORS: Record<string, string> = {
  get: '#dcfce7',
  post: '#dbeafe',
  patch: '#fef3c7',
  put: '#ede9fe',
  delete: '#fee2e2',
};

const METHOD_TEXT: Record<string, string> = {
  get: '#166534',
  post: '#1e40af',
  patch: '#92400e',
  put: '#5b21b6',
  delete: '#991b1b',
};

export default function UserStoryReviewPanel({ story, onClose, onConfirm, viewOnly = false }: UserStoryReviewPanelProps) {
  const [edited, setEdited] = useState<Requirement | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    setEdited(story);
    setIsEditing(false);
  }, [story]);

  if (!story || !edited) return null;

  const handleConfirm = () => {
    onConfirm(edited);
    setIsEditing(false);
  };

  const updateField = (field: keyof Requirement, value: string) =>
    setEdited((cur) => cur ? { ...cur, [field]: value } : cur);

  const updateCriteria = (index: number, value: string) =>
    setEdited((cur) => {
      if (!cur) return cur;
      const criteria = [...(cur.acceptanceCriteria ?? [])];
      criteria[index] = value;
      return { ...cur, acceptanceCriteria: criteria };
    });

  const addCriteria = () =>
    setEdited((cur) => cur ? { ...cur, acceptanceCriteria: [...(cur.acceptanceCriteria ?? []), ''] } : cur);

  const removeCriteria = (index: number) =>
    setEdited((cur) => {
      if (!cur) return cur;
      return { ...cur, acceptanceCriteria: (cur.acceptanceCriteria ?? []).filter((_, i) => i !== index) };
    });

  const methodBg = METHOD_COLORS[edited.method] ?? '#f3f4f6';
  const methodFg = METHOD_TEXT[edited.method] ?? '#374151';

  return (
    <div className="review-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="review-panel">

        <div className="review-panel-header">
          <div className="review-panel-title">
            <span className="review-id">{edited.id}</span>
            <span>{edited.title}</span>
          </div>
          <div className="review-panel-actions">
            {!viewOnly && (
              <button className="review-edit-btn" onClick={() => setIsEditing((v) => !v)}>
                <Icon name={isEditing ? 'check' : 'eye'} size={14} />
                {isEditing ? 'Done Editing' : 'Edit'}
              </button>
            )}
            <button className="review-close-btn" onClick={onClose} aria-label="Close panel">
              <Icon name="plus" size={16} />
            </button>
          </div>
        </div>

        <div className="review-panel-body">

          <div className="review-section">
            <label className="review-label">Description</label>
            {isEditing ? (
              <textarea
                className="review-textarea"
                value={edited.desc}
                onChange={(e) => updateField('desc', e.target.value)}
                rows={3}
              />
            ) : (
              <p className="review-text">{edited.desc}</p>
            )}
          </div>

          <div className="review-meta-row">
            <div className="review-meta-item">
              <label className="review-label">Method</label>
              <span className="review-method-badge" style={{ background: methodBg, color: methodFg }}>
                {edited.method.toUpperCase()}
              </span>
            </div>
            <div className="review-meta-item review-meta-path">
              <label className="review-label">Path</label>
              {isEditing ? (
                <input className="review-input" value={edited.path} onChange={(e) => updateField('path', e.target.value)} />
              ) : (
                <code className="review-path">{edited.path}</code>
              )}
            </div>
            <div className="review-meta-item">
              <label className="review-label">Priority</label>
              {isEditing ? (
                <select className="review-select" value={edited.priority} onChange={(e) => updateField('priority', e.target.value)}>
                  <option>High</option>
                  <option>Medium</option>
                  <option>Low</option>
                </select>
              ) : (
                <em className={`review-priority ${edited.priority.toLowerCase()}`}>{edited.priority}</em>
              )}
            </div>
            <div className="review-meta-item">
              <label className="review-label">Status</label>
              {isEditing ? (
                <select className="review-select" value={edited.status ?? 'Draft'} onChange={(e) => updateField('status', e.target.value)}>
                  <option value="Draft">Draft</option>
                  <option value="Approved">Approved</option>
                  <option value="Rejected">Rejected</option>
                </select>
              ) : (
                <span className={`review-status-badge ${(edited.status ?? 'Draft').toLowerCase()}`}>{edited.status ?? 'Draft'}</span>
              )}
            </div>
          </div>

          <div className="review-section">
            <label className="review-label">Source</label>
            <p className="review-source"><Icon name="file" size={13} />{edited.source}</p>
          </div>

          {isEditing && (
            <div className="review-section">
              <label className="review-label">Summary</label>
              <input className="review-input" value={edited.summary} onChange={(e) => updateField('summary', e.target.value)} />
            </div>
          )}

          <div className="review-section">
            <div className="review-criteria-header">
              <label className="review-label">Acceptance Criteria</label>
              {isEditing && (
                <button className="review-add-criteria" onClick={addCriteria}>
                  <Icon name="plus" size={12} /> Add
                </button>
              )}
            </div>
            {(edited.acceptanceCriteria ?? []).length === 0 ? (
              <p className="review-empty">No acceptance criteria defined.{isEditing ? ' Click Add to create one.' : ''}</p>
            ) : (
              <ul className="review-criteria-list">
                {(edited.acceptanceCriteria ?? []).map((criterion, i) => (
                  <li key={i} className="review-criteria-item">
                    {isEditing ? (
                      <>
                        <input
                          className="review-input"
                          value={criterion}
                          onChange={(e) => updateCriteria(i, e.target.value)}
                        />
                        <button className="review-remove-criteria" onClick={() => removeCriteria(i)} aria-label="Remove">
                          <Icon name="plus" size={12} />
                        </button>
                      </>
                    ) : (
                      <><Icon name="check" size={13} />{criterion}</>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {(edited.tags ?? []).length > 0 && (
            <div className="review-section">
              <label className="review-label">Tags</label>
              <div className="review-tags">
                {(edited.tags ?? []).map((tag) => <span key={tag} className="review-tag">{tag}</span>)}
              </div>
            </div>
          )}

        </div>

        <div className="review-panel-footer">
          <button className="review-cancel-btn" onClick={onClose}>Close</button>
          {!viewOnly && (
            <button className="review-confirm-btn" onClick={handleConfirm}>
              <Icon name="spark" size={15} />
              Approve requirements
            </button>
          )}
        </div>

      </div>
    </div>
  );
}
