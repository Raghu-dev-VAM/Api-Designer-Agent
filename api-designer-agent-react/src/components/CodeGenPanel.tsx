import { useState, useRef, useEffect } from 'react';
import Icon from './Icon';
import { startCodeGen } from '../services/documentService';
import type { CodeGenStatus } from '../services/documentService';
import { config } from '../config';

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

const STEP_LABELS: Record<string, string> = {
  '2_solution':            'Solution Structure',
  '3_auth':                'Authentication & Security',
  '4_entities_dtos':       'Entities & DTOs',
  '5_data_layer':          'Data Layer',
  '6_business_layer':      'Business Layer',
  '7_controllers':         'API Controllers',
  '8_program':             'Application Setup',
  '9_unit_tests':          'Unit Tests',
  '10_integration_tests':  'Integration Tests',
  '11_reviewed_source':    'Reviewed Source',
  '12_reviewed_tests':     'Reviewed Tests',
};

// Last step the Coder produces before the reviewer takes over
const CODER_FINAL_STEPS = new Set(['8_program', '10_integration_tests']);

function getStepLabel(step: string): string {
  return STEP_LABELS[step] || step.replace(/_/g, ' ');
}

export default function CodeGenPanel({ openApiYaml, projectName }: Props) {
  const [name, setName] = useState(projectName || 'GeneratedApi');
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState<CodeGenStatus[]>([]);
  const [percent, setPercent] = useState(0);
  const [done, setDone] = useState<CodeGenStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [incrementalDownloads, setIncrementalDownloads] = useState<Array<{ step: string; fileCount: number; url: string }>>([]);
  const [autoDownload, setAutoDownload] = useState(false);
  // Set as soon as Coder finishes — before reviewer starts
  const [preReviewReady, setPreReviewReady] = useState<{ url: string; fileCount: number } | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  useEffect(() => {
    setName(projectName || 'GeneratedApi');
  }, [projectName]);

  const downloadFromUrl = async (url: string, filename: string) => {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error('Download failed');
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(objectUrl);
    } catch {
      window.open(url, '_blank');
    }
  };

  const handleStart = () => {
    if (!openApiYaml) return;
    setRunning(true);
    setLogs([]);
    setPercent(0);
    setDone(null);
    setError(null);
    setIncrementalDownloads([]);
    setPreReviewReady(null);

    cancelRef.current = startCodeGen(openApiYaml, name, 'groq', (s) => {
      if (s.event === 'status') {
        setLogs((l) => [...l, s]);
        setPercent(s.percent ?? 0);
      } else if (s.event === 'agent_message') {
        setLogs((l) => [...l, s]);
      } else if (s.event === 'incremental_ready') {
        const stepName = s.step || 'unknown';
        const fileCount = s.file_count || 0;
        const downloadUrl = s.download_url || '';

        setIncrementalDownloads((prev) => [...prev, { step: stepName, fileCount, url: downloadUrl }]);

        // Coder finishes at 8_program (no tests) or 10_integration_tests (with tests).
        // Expose pre-review download immediately — reviewer hasn't started yet.
        if (CODER_FINAL_STEPS.has(stepName)) {
          setPreReviewReady({ url: downloadUrl, fileCount });
        }

        if (autoDownload && downloadUrl) {
          downloadFromUrl(`${config.apiBaseUrl}${downloadUrl}`, `${name}_${stepName}.zip`);
        }
      } else if (s.event === 'done') {
        setDone(s);
        setPercent(100);
        setRunning(false);
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

  const handleDownloadPreReview = () => {
    // Use live preReviewReady URL during generation, fall back to done URL after completion
    const url = preReviewReady?.url ?? done?.download_urls?.pre_review;
    if (!url) return;
    downloadFromUrl(`${config.apiBaseUrl}${url}`, `${name}_PreReview.zip`);
  };

  const handleDownloadFinal = () => {
    if (!done?.download_urls?.final) return;
    downloadFromUrl(`${config.apiBaseUrl}${done.download_urls.final}`, `${name}_Final.zip`);
  };

  const handleDownloadStep = (stepUrl: string, stepName: string) => {
    downloadFromUrl(`${config.apiBaseUrl}${stepUrl}`, `${name}_${stepName}.zip`);
  };

  const handleDownloadLatest = () => {
    if (incrementalDownloads.length === 0) return;
    const latest = incrementalDownloads[incrementalDownloads.length - 1];
    downloadFromUrl(`${config.apiBaseUrl}${latest.url}`, `${name}_Latest.zip`);
  };

  const canDownloadPreReview = !!(preReviewReady || done?.download_urls?.pre_review);

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

        {running && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: '#f1f5f9', borderRadius: 6 }}>
            <input
              type="checkbox"
              id="auto-download"
              checked={autoDownload}
              onChange={(e) => setAutoDownload(e.target.checked)}
              style={{ cursor: 'pointer' }}
            />
            <label htmlFor="auto-download" style={{ fontSize: 13, color: '#475569', cursor: 'pointer', userSelect: 'none' }}>
              📥 Auto-download on each step
            </label>
          </div>
        )}

        {/* ── Pre-review download banner — shown as soon as Coder finishes ── */}
        {canDownloadPreReview && !done && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 14px', background: '#ecfdf5', border: '1px solid #6ee7b7',
            borderRadius: 8, gap: 10,
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#065f46' }}>
                💻 Coder finished — pre-review code ready
              </div>
              <div style={{ fontSize: 11, color: '#047857', marginTop: 2 }}>
                {preReviewReady?.fileCount} files · Reviewer is running in background
              </div>
            </div>
            <button
              className="postman-btn preview"
              onClick={handleDownloadPreReview}
              style={{ whiteSpace: 'nowrap', flexShrink: 0 }}
            >
              <Icon name="download" size={13} />Download Pre-Review
            </button>
          </div>
        )}

        {incrementalDownloads.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <p style={{ margin: 0, fontSize: 11, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Available Downloads
              </p>
              {running && (
                <button
                  className="secondary-btn"
                  onClick={handleDownloadLatest}
                  style={{ fontSize: 12, padding: '4px 10px' }}
                  title="Download all code generated so far"
                >
                  <Icon name="download" size={12} />Download Latest
                </button>
              )}
            </div>
            <div style={{
              display: 'flex', flexDirection: 'column', gap: 6,
              maxHeight: 200, overflowY: 'auto', padding: 8,
              background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0',
            }}>
              {incrementalDownloads.map((download, idx) => (
                <div key={idx} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '6px 10px', background: 'white', borderRadius: 4, border: '1px solid #e2e8f0',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 16 }}>✅</span>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>
                        {getStepLabel(download.step)}
                      </div>
                      <div style={{ fontSize: 11, color: '#64748b' }}>{download.fileCount} files</div>
                    </div>
                  </div>
                  <button
                    className="secondary-btn"
                    onClick={() => handleDownloadStep(download.url, download.step)}
                    style={{ fontSize: 11, padding: '4px 8px' }}
                  >
                    <Icon name="download" size={11} />Download
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

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
            <p style={{ margin: 0, fontSize: 12, color: '#64748b', textAlign: 'center', fontStyle: 'italic' }}>
              💡 Tip: Compare versions to see what changed during generation and review
            </p>
          </div>
        )}

        {!openApiYaml && (
          <p className="hint">Generate an OpenAPI spec first (Section 3) to enable code generation.</p>
        )}
      </div>
    </article>
  );
}
