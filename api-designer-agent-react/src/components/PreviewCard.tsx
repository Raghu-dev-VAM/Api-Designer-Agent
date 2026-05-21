import { useState } from 'react';
import Icon from './Icon';
import SectionHeader from './SectionHeader';

interface PreviewCardProps {
  spec: string;
  toast: string;
  lastGeneratedAt: string;
  isGenerating: boolean;
  onPreview: () => void;
  onDownload: () => void;
  onDownloadJson: () => void;
}

export default function PreviewCard({ spec, toast, lastGeneratedAt, isGenerating, onPreview, onDownload, onDownloadJson }: PreviewCardProps) {
  const [showModal, setShowModal] = useState(false);

  const handlePreview = () => {
    onPreview();
    if (spec) setShowModal(true);
  };

  return (
    <>
      <article className="card preview-card">
        <SectionHeader number="3" title="Generated OpenAPI Preview" subtitle="Preview of generated OpenAPI specification" />
        <div className="card-body">
          <div className="file-toolbar">
            <button className="active">openapi.yaml</button>
            <button onClick={handlePreview} disabled={!spec || isGenerating}><Icon name="eye" size={15} />Preview</button>
            <button onClick={onDownload} disabled={!spec || isGenerating}><Icon name="download" size={15} />YAML</button>
            <button onClick={onDownloadJson} disabled={!spec || isGenerating}><Icon name="download" size={15} />JSON</button>
          </div>

          {isGenerating ? (
            <div className="spec-loading">
              <div className="spec-spinner" />
              <p>Generating OpenAPI spec via AI…</p>
              <div className="spec-skeleton">
                {Array.from({ length: 12 }).map((_, i) => (
                  <div key={i} className="skeleton-line" style={{ width: `${45 + (i % 5) * 11}%` }} />
                ))}
              </div>
            </div>
          ) : spec ? (
            <pre className="code-area">
              {spec.split('\n').map((line, index) => (
                <code key={`${line}-${index}`}><span>{index + 1}</span>{line}</code>
              ))}
            </pre>
          ) : (
            <div className="spec-empty">
              <Icon name="doc" size={36} />
              <p>Review and confirm a user story, then click Generate OpenAPI</p>
            </div>
          )}

          <div className="success-row">
            <Icon name="check" size={16} />
            {isGenerating ? 'Generating…' : spec ? toast : 'Waiting for generation'}
            <time>{lastGeneratedAt}</time>
          </div>
        </div>
      </article>

      {showModal && (
        <div className="preview-modal-overlay" onClick={(e) => e.target === e.currentTarget && setShowModal(false)}>
          <div className="preview-modal">
            <div className="preview-modal-header">
              <span className="preview-modal-title"><Icon name="doc" size={16} />openapi.yaml</span>
              <div className="preview-modal-actions">
                <button onClick={onDownload}><Icon name="download" size={15} />YAML</button>
                <button onClick={onDownloadJson}><Icon name="download" size={15} />JSON</button>
                <button className="preview-modal-close" onClick={() => setShowModal(false)} aria-label="Close">
                  <Icon name="plus" size={16} />
                </button>
              </div>
            </div>
            <pre className="preview-modal-code">
              {spec.split('\n').map((line, index) => (
                <code key={`${line}-${index}`}><span>{index + 1}</span>{line}</code>
              ))}
            </pre>
          </div>
        </div>
      )}
    </>
  );
}
