import Icon from './Icon';
import SectionHeader from './SectionHeader';

interface PreviewCardProps {
  spec: string;
  toast: string;
  lastGeneratedAt: string;
  isGenerating: boolean;
  onPreview: () => void;
  onDownload: () => void;
}

export default function PreviewCard({ spec, toast, lastGeneratedAt, isGenerating, onPreview, onDownload }: PreviewCardProps) {
  return (
    <article className="card preview-card">
      <SectionHeader number="3" title="Generated OpenAPI Preview" subtitle="Preview of generated OpenAPI specification" />
      <div className="card-body">
        <div className="file-toolbar">
          <button className="active">openapi.yaml</button>
          <button onClick={onPreview} disabled={!spec || isGenerating}><Icon name="eye" size={15} />Preview</button>
          <button onClick={onDownload} disabled={!spec || isGenerating}><Icon name="download" size={15} />Download</button>
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
  );
}
