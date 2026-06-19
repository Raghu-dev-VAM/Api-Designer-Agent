import { useState } from 'react';
import Icon from './Icon';
import type { ColumnMapping } from '../services/documentService';

interface Props {
  columns: string[];
  filename: string;
  onConfirm: (mapping: ColumnMapping) => void;
  onCancel: () => void;
}

const FIELDS: { key: keyof ColumnMapping; label: string; required: boolean; hint: string }[] = [
  { key: 'userStory',          label: 'User Story / Description', required: true,  hint: 'Main story text (As a... I want...)' },
  { key: 'acceptanceCriteria', label: 'Acceptance Criteria',      required: false, hint: 'Criteria for completion' },
  { key: 'title',              label: 'Title',                    required: false, hint: 'Short title or epic name' },
  { key: 'storyId',            label: 'Story ID',                 required: false, hint: 'e.g. US-001, JIRA-123' },
  { key: 'priority',           label: 'Priority',                 required: false, hint: 'High / Medium / Low' },
];

const PATTERNS: Record<keyof ColumnMapping, string[]> = {
  userStory:          ['user story', 'description', 'story', 'as a', 'requirement'],
  acceptanceCriteria: ['acceptance', 'criteria', 'ac', 'done when', 'definition'],
  title:              ['title', 'name', 'summary'],
  storyId:            ['story id', 'storyid', 'story_id', 'id', 'ticket'],
  priority:           ['priority', 'severity', 'importance'],
};

function autoDetect(columns: string[]): ColumnMapping {
  const mapping: ColumnMapping = { userStory: '', acceptanceCriteria: '', title: '', storyId: '', priority: '' };
  for (const field of FIELDS) {
    const patterns = PATTERNS[field.key];
    const match = columns.find((col) => patterns.some((p) => col.toLowerCase().includes(p)));
    if (match) mapping[field.key] = match;
  }
  return mapping;
}

export default function ExcelColumnMapModal({ columns, filename, onConfirm, onCancel }: Props) {
  const [mapping, setMapping] = useState<ColumnMapping>(() => autoDetect(columns));

  const set = (key: keyof ColumnMapping, value: string) =>
    setMapping((m) => ({ ...m, [key]: value }));

  const canConfirm = !!mapping.userStory;

  return (
    <div className="azure-modal-overlay">
      <div className="azure-modal" style={{ maxWidth: 520 }}>
        <div className="azure-modal-header" style={{ background: 'linear-gradient(135deg, #f0fdf4, #fff)' }}>
          <div className="azure-modal-title" style={{ color: '#047857' }}>
            <Icon name="file" size={18} />
            Map Columns — {filename}
          </div>
          <button className="review-close-btn" onClick={onCancel}><Icon name="plus" size={14} /></button>
        </div>

        <div className="azure-modal-body">
          <p style={{ margin: '0 0 4px', fontSize: 12.5, color: '#64748b' }}>
            <strong>{columns.length} columns detected.</strong> Map them to requirement fields.
            Auto-detected matches are pre-filled — adjust if needed.
          </p>

          {FIELDS.map(({ key, label, required, hint }) => (
            <div className="azure-field" key={key}>
              <label>
                {label}
                {required
                  ? <span style={{ color: '#dc2626' }}> *</span>
                  : <span className="optional"> (optional)</span>}
              </label>
              <select
                className="review-select"
                style={{ width: '100%', padding: '8px 10px' }}
                value={mapping[key]}
                onChange={(e) => set(key, e.target.value)}
              >
                <option value="">— skip —</option>
                {columns.map((col) => (
                  <option key={col} value={col}>{col}</option>
                ))}
              </select>
              <small>{hint}</small>
            </div>
          ))}
        </div>

        <div className="review-panel-footer">
          <button className="review-cancel-btn" onClick={onCancel}>Cancel</button>
          <button
            className="review-confirm-btn"
            disabled={!canConfirm}
            onClick={() => onConfirm(mapping)}
            style={!canConfirm ? { opacity: 0.5, cursor: 'not-allowed' } : {}}
          >
            <Icon name="spark" size={15} /> Extract Requirements
          </button>
        </div>
      </div>
    </div>
  );
}
