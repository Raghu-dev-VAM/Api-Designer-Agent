import { useState, useRef, useEffect } from 'react';
import Icon from './Icon';
import { startCodeGen } from '../services/documentService';
import type { CodeGenStatus } from '../services/documentService';

interface Props {
  openApiYaml: string;
  projectName: string;
}

const AGENT_COLORS: Record<string, string> = {
  Architect:      '#4f46e5',
  SecurityExpert: '#dc2626',
  Coder:          '#059669',
  SeniorReviewer: '#d97706',
  TestEngineer:   '#0891b2',
  FinalReviewer:  '#7c3aed',
  System:         '#64748b',
};

const AGENT_ICONS: Record<string, string> = {
  Architect:      '🏗️',
  SecurityExpert: '🔐',
  Coder:          '💻',
  SeniorReviewer: '🔎',
  TestEngineer:   '🧪',
  FinalReviewer:  '✅',
  System:         '⚙️',
};

// Last step the Coder produces before the reviewer takes over
const CODER_FINAL_STEPS = new Set(['8_program', '10_integration_tests']);

function downloadBase64Zip(base64: string, filename: string) {
  const byteChars = atob(base64);
  const byteNumbers = new Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) {
    byteNumbers[i] = byteChars.charCodeAt(i);
  }
  const blob = new Blob([new Uint8Array(byteNumbers)], { type: 'application/zip' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function CodeGenPanel({ openApiYaml, projectName }: Props) {
  const [name, setName] = useState(projectName || 'GeneratedApi');
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState<CodeGenStatus[]>([]);
  const [percent, setPercent] = useState(0);
  const [done, setDone] = useState<CodeGenStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preReviewZip, setPreReviewZip] = useState<string | null>(null);
  const [preReviewFileCount, setPreReviewFileCount] = useState(0);
  const cancelRef = useRef<(() => void) | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  useEffect(() => {
    setName(projectName || 'GeneratedApi');
  }, [projectName]);

  const handleStart = () => {
    if (!openApiYaml) return;
    setRunning(true);
    setLogs([]);
    setPercent(0);
    setDone(null);
    setError(null);
    setPreReviewZip(null);
    setPreReviewFileCount(0);

    cancelRef.current = startCodeGen(openApiYaml, name, 'groq', (s) => {
      if (s.event === 'status') {
        setLogs((l) => [...l, s]);
        setPercent(s.percent ?? 0);
      } else if (s.event === 'agent_message') {
        setLogs((l) => [...l, s]);
      } else if (s.event === 'incremental_ready') {
        const stepName = String(s.step ?? 'unknown');
        const fileCount = s.file_count || 0;
        // Capture pre-review snapshot when coder finishes
        if (CODER_FINAL_STEPS.has(stepName)) {
          setPreReviewFileCount(fileCount);
        }
      } else if (s.event === 'done') {
        setDone(s);
        setPercent(100);
        setRunning(false);
        // The done event includes zip_base64 for the final reviewed code
        // and pre_review_available flag
        if (s.zip_base64) {
          // Store final zip from done event
        }
      } else if (s.event === 'error') {
        setError(s.message ?? 'Unknown error');
        setRunning(false);
      }
    });
  };

  const handleCancel = () => {
    cancelRef.current?.();
    setRunning(false);
    setError('Cancelled by user');
  };

  const handleDownloadFinal = () => {
    if (!done?.zip_base64) return;
    downloadBase64Zip(done.zip_base64, `${name}_Final.zip`);
  };

  const handleDownloadPreReview = () => {
    if (!done?.pre_review_zip_base64) return;
    downloadBase64Zip(done.pre_review_zip_base64, `${name}_PreReview.zip`);
  };

  const canDownloadPreReview = !!(done?.pre_review_zip_base64);

  return (
    <article className="card codegen-panel">
      <div className="card-header">
        <div className="title-row">
          <span className="section-num" style={{ background: 'linear-gradient(135deg,#059669,#0f766e)' }}>⚡</span>
          <span className="section-title">.NET API Code Generator</span>
        </div>
        <p>AutoGen multi-agent pipeline — generates production-ready .NET 8 C# boilerplate</p>
      </div>

      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

        <div className="azure-field">
          <label>Project Name</label>
          <input
            className="review-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="MyApi"
            disabled={running}
          />
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button
            className="primary-btn"
            style={{ flex: 1 }}
            onClick={handleStart}
            disabled={running || !openApiYaml}
            title={!openApiYaml ? 'Generate an OpenAPI spec first' : ''}
          >
            {running
              ? <><div className="postman-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />Generating…</>
              : <><Icon name="spark" size={16} />Generate .NET API</>}
          </button>
          {running && (
            <button className="review-cancel-btn" onClick={handleCancel}>Cancel</button>
          )}
        </div>

        {(running || percent > 0) && (
          <div style={{ background: '#e2e8f0', borderRadius: 999, height: 6, overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${percent}%`,
              background: 'linear-gradient(90deg,#4f46e5,#059669)',
              borderRadius: 999, transition: 'width 400ms ease',
            }} />
          </div>
        )}

        {logs.length > 0 && (
          <div className="codegen-log">
            {logs.map((log, i) => {
              const agent = log.agent ?? 'System';
              const color = AGENT_COLORS[agent] ?? '#64748b';
              const icon  = AGENT_ICONS[agent]  ?? '🤖';

              if (log.event === 'status') {
                return (
                  <div key={i} className="codegen-log-entry status">
                    <span className="codegen-agent-badge" style={{ background: color }}>{icon} {agent}</span>
                    <span className="codegen-log-msg">{log.message}</span>
                    {log.step !== undefined && (
                      <span className="codegen-step">Step {log.step}/{log.total}</span>
                    )}
                  </div>
                );
              }

              if (log.event === 'agent_message') {
                return (
                  <div key={i} className="codegen-log-entry message">
                    <span className="codegen-agent-badge" style={{ background: color, opacity: 0.8 }}>{icon} {agent}</span>
                    <span className="codegen-log-preview">{log.preview}</span>
                  </div>
                );
              }

              return null;
            })}
            <div ref={logsEndRef} />
          </div>
        )}

        {error && (
          <div className="upload-status error">
            <Icon name="plus" size={14} />{error}
          </div>
        )}

        {done && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div className="upload-status success">
              <Icon name="check" size={14} />
              <span>
                <strong>{done.project_name}</strong> — {done.src_count ?? done.file_count} source files
                {done.test_count ? ` + ${done.test_count} test files` : ''}
              </span>
            </div>

            {done.src_files && done.src_files.length > 0 && (
              <>
                <p style={{ margin: 0, fontSize: 11, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Source Files</p>
                <div className="codegen-file-list">
                  {done.src_files.map((f: string) => (
                    <div key={f} className="codegen-file-item">
                      <Icon name="doc" size={13} /><span>{f}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {done.test_files && done.test_files.length > 0 && (
              <>
                <p style={{ margin: 0, fontSize: 11, fontWeight: 700, color: '#059669', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Test Files</p>
                <div className="codegen-file-list" style={{ borderColor: '#a7f3d0', background: '#f0fdf4' }}>
                  {done.test_files.map((f: string) => (
                    <div key={f} className="codegen-file-item">
                      <Icon name="check" size={13} /><span>{f}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button className="primary-btn" onClick={handleDownloadFinal} style={{ flex: 1, minWidth: 150 }}>
                <Icon name="download" size={16} />Download Final
              </button>
              {canDownloadPreReview && (
                <button
                  className="secondary-btn"
                  onClick={handleDownloadPreReview}
                  style={{ flex: 1, minWidth: 150 }}
                  title="Download code before reviewer fixes"
                >
                  <Icon name="doc" size={16} />Pre-Review
                </button>
              )}
            </div>
          </div>
        )}

        {!openApiYaml && (
          <p className="hint">Generate an OpenAPI spec first (Section 3) to enable code generation.</p>
        )}
      </div>
    </article>
  );
}
