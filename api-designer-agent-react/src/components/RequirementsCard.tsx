import Icon from './Icon';
import SectionHeader from './SectionHeader';
import type { Requirement } from '../types';

interface RequirementsCardProps {
  requirements: Requirement[];
  selectedRequirement: Requirement | null;
  rawText: string;
  search: string;
  tab: string;
  onTabChange: (tab: string) => void;
  onSearchChange: (value: string) => void;
  onSelectRequirement: (req: Requirement) => void;
  onViewRequirement: (req: Requirement) => void;
  onStatusChange: (id: string, status: 'Draft' | 'Approved' | 'Rejected') => void;
  onGenerate: () => void;
  isGenerating: boolean;
  onFilter: () => void;
  onRefresh: () => void;
}

const STATUS_STYLES: Record<string, string> = {
  Approved: 'status-approved',
  Rejected: 'status-rejected',
  Draft: 'status-draft',
};

const METHOD_COLORS: Record<string, { bg: string; color: string }> = {
  get:    { bg: '#dcfce7', color: '#166534' },
  post:   { bg: '#dbeafe', color: '#1e40af' },
  put:    { bg: '#ede9fe', color: '#5b21b6' },
  patch:  { bg: '#fef3c7', color: '#92400e' },
  delete: { bg: '#fee2e2', color: '#991b1b' },
};

export default function RequirementsCard({
  requirements, selectedRequirement, rawText, search, tab,
  onTabChange, onSearchChange, onSelectRequirement, onViewRequirement, onStatusChange, onGenerate, isGenerating, onFilter, onRefresh
}: RequirementsCardProps) {
  const canGenerate = !!selectedRequirement && !isGenerating;
  const hideSearch = tab === 'Raw' || tab === 'Summary';

  const approved  = requirements.filter((r) => r.status === 'Approved').length;
  const rejected  = requirements.filter((r) => r.status === 'Rejected').length;
  const draft     = requirements.filter((r) => r.status === 'Draft').length;

  return (
    <article className="card requirements-card">
      <SectionHeader number="2" title="Requirements Input" subtitle="Extracted requirements from sources" tone="purple" />
      <div className="card-body">
        <div className="tabs">
          {['Extracted', 'Raw', 'Summary'].map((item) => (
            <button className={tab === item ? 'active' : ''} key={item} onClick={() => onTabChange(item)}>{item}</button>
          ))}
        </div>

        <label className="search-bar" style={hideSearch ? { display: 'none' } : {}}>
          <Icon name="search" size={16} />
          <input value={search} onChange={(e) => onSearchChange(e.target.value)} placeholder="Search requirements..." />
          <button type="button" aria-label="Filter requirements" onClick={onFilter}><Icon name="filter" size={15} /></button>
        </label>

        {/* ── Raw tab ── */}
        {tab === 'Raw' && (
          <pre className="raw-text-view">{rawText || 'No document uploaded yet.'}</pre>
        )}

        {/* ── Summary tab ── */}
        {tab === 'Summary' && (
          <div className="summary-view">
            {requirements.length === 0 ? (
              <p className="hint" style={{ padding: '1rem', textAlign: 'center' }}>Upload a document to see the summary.</p>
            ) : (
              <>
                <div className="summary-stats">
                  <div className="summary-stat">
                    <span className="summary-stat-value">{requirements.length}</span>
                    <span className="summary-stat-label">Total</span>
                  </div>
                  <div className="summary-stat approved">
                    <span className="summary-stat-value">{approved}</span>
                    <span className="summary-stat-label">Approved</span>
                  </div>
                  <div className="summary-stat draft">
                    <span className="summary-stat-value">{draft}</span>
                    <span className="summary-stat-label">Draft</span>
                  </div>
                  <div className="summary-stat rejected">
                    <span className="summary-stat-value">{rejected}</span>
                    <span className="summary-stat-label">Rejected</span>
                  </div>
                </div>

                <div className="summary-table">
                  <div className="summary-table-head">
                    <span>ID</span>
                    <span>Title</span>
                    <span>Method / Path</span>
                    <span>Priority</span>
                    <span>Status</span>
                  </div>
                  {requirements.map((req) => {
                    const m = METHOD_COLORS[req.method?.toLowerCase()] ?? { bg: '#f3f4f6', color: '#374151' };
                    return (
                      <div key={req.id} className="summary-table-row" onClick={() => onSelectRequirement(req)}>
                        <span className="summary-id">{req.id}</span>
                        <span className="summary-title">{req.title}</span>
                        <span className="summary-endpoint">
                          <em className="summary-method" style={{ background: m.bg, color: m.color }}>{req.method?.toUpperCase()}</em>
                          <code>{req.path}</code>
                        </span>
                        <span className={`summary-priority ${req.priority?.toLowerCase()}`}>{req.priority}</span>
                        <span className={`summary-status ${STATUS_STYLES[req.status] ?? 'status-draft'}`}>{req.status}</span>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Extracted tab ── */}
        {tab === 'Extracted' && (
          <>
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
                      className="status-btn view"
                      title="View details"
                      onClick={() => onViewRequirement(req)}
                    ><Icon name="eye" size={12} /></button>
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
              title={canGenerate ? 'Generate OpenAPI spec' : isGenerating ? 'Generation in progress…' : 'Select a requirement to generate'}
            >
              {isGenerating ? 'Generating…' : 'Generate'} <Icon name="arrow" size={17} />
            </button>
            <p className="hint">
              {isGenerating
                ? 'Generating OpenAPI spec, please wait…'
                : canGenerate
                  ? 'Click Generate to create the OpenAPI spec'
                  : 'Select a requirement to enable generation'}
            </p>
          </>
        )}
      </div>
    </article>
  );
}
