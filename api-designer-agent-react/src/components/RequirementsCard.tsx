import Icon from './Icon';
import SectionHeader from './SectionHeader';
import type { Requirement } from '../types';

interface RequirementsCardProps {
  requirements: Requirement[];
  selectedRequirement: Requirement | null;
  search: string;
  tab: string;
  onTabChange: (tab: string) => void;
  onSearchChange: (value: string) => void;
  onSelectRequirement: (req: Requirement) => void;
  onStatusChange: (id: string, status: 'Draft' | 'Approved' | 'Rejected') => void;
  onGenerate: () => void;
  onFilter: () => void;
  onRefresh: () => void;
}

const STATUS_STYLES: Record<string, string> = {
  Approved: 'status-approved',
  Rejected: 'status-rejected',
  Draft: 'status-draft',
};

export default function RequirementsCard({
  requirements, selectedRequirement, search, tab,
  onTabChange, onSearchChange, onSelectRequirement, onStatusChange, onGenerate, onFilter, onRefresh
}: RequirementsCardProps) {
  const canGenerate = selectedRequirement?.status === 'Approved';

  return (
    <article className="card requirements-card">
      <SectionHeader number="2" title="Requirements Input" subtitle="Extracted requirements from sources" tone="purple" />
      <div className="card-body">
        <div className="tabs">
          {['Extracted', 'Raw', 'Summary'].map((item) => (
            <button className={tab === item ? 'active' : ''} key={item} onClick={() => onTabChange(item)}>{item}</button>
          ))}
        </div>
        <label className="search-bar">
          <Icon name="search" size={16} />
          <input value={search} onChange={(e) => onSearchChange(e.target.value)} placeholder="Search requirements..." />
          <button type="button" aria-label="Filter requirements" onClick={onFilter}><Icon name="filter" size={15} /></button>
        </label>

        {tab !== 'Extracted' && (
          <div className="tab-note">
            {tab === 'Raw' ? 'Raw source text is ready for review and traceability.' : 'Summary created from selected sources with entities, actions, and business rules.'}
          </div>
        )}

        <div className="requirements-list">
          {requirements.length === 0 && (
            <p className="hint" style={{ padding: '1rem', textAlign: 'center' }}>Upload a document to extract requirements.</p>
          )}
          {requirements.map((req) => (
            <div key={req.id} className={`req-item ${selectedRequirement?.id === req.id ? 'active' : ''}`}>
              <button className="req-item-body" onClick={() => onSelectRequirement(req)}>
                <strong>{req.id}: {req.title}</strong>
                <span>{req.desc}</span>
                <small>
                  {req.source}
                  <em className={req.priority.toLowerCase()}>{req.priority}</em>
                  <em className={STATUS_STYLES[req.status] ?? 'status-draft'}>{req.status}</em>
                </small>
              </button>
              <div className="req-status-actions">
                <button
                  className={`status-btn approve ${req.status === 'Approved' ? 'active' : ''}`}
                  title="Approve"
                  onClick={() => onStatusChange(req.id, req.status === 'Approved' ? 'Draft' : 'Approved')}
                >✓</button>
                <button
                  className={`status-btn reject ${req.status === 'Rejected' ? 'active' : ''}`}
                  title="Reject"
                  onClick={() => onStatusChange(req.id, req.status === 'Rejected' ? 'Draft' : 'Rejected')}
                >✕</button>
              </div>
            </div>
          ))}
        </div>

        <div className="req-footer">
          <span>Showing {requirements.length} requirements</span>
          <button onClick={onRefresh}><Icon name="refresh" size={14} /></button>
        </div>

        <button
          className="primary-btn"
          onClick={onGenerate}
          disabled={!canGenerate}
          title={canGenerate ? 'Generate OpenAPI spec' : 'Only Approved requirements can be used to generate a spec'}
        >
          Generate <Icon name="arrow" size={17} />
        </button>
        <p className="hint">
          {canGenerate
            ? 'Click Generate to create the OpenAPI spec'
            : 'Approve a requirement to enable generation'}
        </p>
      </div>
    </article>
  );
}
