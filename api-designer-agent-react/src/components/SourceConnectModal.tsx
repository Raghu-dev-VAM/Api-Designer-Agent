import { useState } from 'react';
import Icon from './Icon';
import type { AzureConfig, JiraConfig, ConfluenceConfig } from '../services/documentService';

type SourceType = 'azure' | 'jira' | 'confluence';

interface SourceConnectModalProps {
  source: SourceType;
  onClose: () => void;
  onConnectAzure: (cfg: AzureConfig) => void;
  onConnectJira: (cfg: JiraConfig) => void;
  onConnectConfluence: (cfg: ConfluenceConfig) => void;
  connecting: boolean;
}

const SOURCE_META: Record<SourceType, { title: string; icon: string; color: string }> = {
  azure:      { title: 'Azure DevOps',  icon: 'azure',   color: '#1e40af' },
  jira:       { title: 'Jira',          icon: 'diamond', color: '#0052cc' },
  confluence: { title: 'Confluence',    icon: 'waves',   color: '#0065ff' },
};

export default function SourceConnectModal({ source, onClose, onConnectAzure, onConnectJira, onConnectConfluence, connecting }: SourceConnectModalProps) {
  const meta = SOURCE_META[source];

  // Shared
  const [host, setHost] = useState('');
  const [email, setEmail] = useState('');
  const [apiToken, setApiToken] = useState('');
  const [maxItems, setMaxItems] = useState(source === 'confluence' ? '20' : '50');

  // Azure-specific
  const [org, setOrg] = useState('');
  const [project, setProject] = useState('');
  const [pat, setPat] = useState('');
  const [areaPath, setAreaPath] = useState('');

  // Jira-specific
  const [projectKey, setProjectKey] = useState('');

  // Confluence-specific
  const [spaceKey, setSpaceKey] = useState('');

  const canConnect = !connecting && (() => {
    if (source === 'azure') return org.trim() && project.trim() && pat.trim();
    if (source === 'jira') return host.trim() && email.trim() && apiToken.trim() && projectKey.trim();
    if (source === 'confluence') return host.trim() && email.trim() && apiToken.trim() && spaceKey.trim();
    return false;
  })();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canConnect) return;
    if (source === 'azure') {
      onConnectAzure({ organization: org.trim(), project: project.trim(), pat: pat.trim(), areaPath: areaPath.trim() || undefined, maxItems: parseInt(maxItems) || 50 });
    } else if (source === 'jira') {
      onConnectJira({ host: host.trim(), email: email.trim(), apiToken: apiToken.trim(), projectKey: projectKey.trim(), maxItems: parseInt(maxItems) || 50 });
    } else {
      onConnectConfluence({ host: host.trim(), email: email.trim(), apiToken: apiToken.trim(), spaceKey: spaceKey.trim(), maxItems: parseInt(maxItems) || 20 });
    }
  };

  return (
    <div className="azure-modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="azure-modal">
        <div className="azure-modal-header" style={{ background: `linear-gradient(135deg, ${meta.color}18, #fff)` }}>
          <span className="azure-modal-title" style={{ color: meta.color }}>
            <Icon name={meta.icon} size={18} />Connect to {meta.title}
          </span>
          <button className="review-close-btn" onClick={onClose} aria-label="Close"><Icon name="plus" size={16} /></button>
        </div>

        <form className="azure-modal-body" onSubmit={handleSubmit}>

          {/* ── Azure fields ── */}
          {source === 'azure' && <>
            <div className="azure-field">
              <label>Organization <span>*</span></label>
              <input value={org} onChange={(e) => setOrg(e.target.value)} placeholder="e.g. my-org" autoFocus />
              <small>From dev.azure.com/<strong>org</strong></small>
            </div>
            <div className="azure-field">
              <label>Project <span>*</span></label>
              <input value={project} onChange={(e) => setProject(e.target.value)} placeholder="e.g. MyProject" />
            </div>
            <div className="azure-field">
              <label>Personal Access Token (PAT) <span>*</span></label>
              <input type="password" value={pat} onChange={(e) => setPat(e.target.value)} placeholder="Paste your PAT" />
              <small>Requires <strong>Work Items (Read)</strong> scope</small>
            </div>
            <div className="azure-field-row">
              <div className="azure-field">
                <label>Area Path <span className="optional">(optional)</span></label>
                <input value={areaPath} onChange={(e) => setAreaPath(e.target.value)} placeholder="e.g. MyProject\Team" />
              </div>
              <div className="azure-field azure-field-sm">
                <label>Max Items</label>
                <input type="number" value={maxItems} onChange={(e) => setMaxItems(e.target.value)} min="1" max="200" />
              </div>
            </div>
          </>}

          {/* ── Jira fields ── */}
          {source === 'jira' && <>
            <div className="azure-field">
              <label>Jira Host <span>*</span></label>
              <input value={host} onChange={(e) => setHost(e.target.value)} placeholder="https://your-org.atlassian.net" autoFocus />
            </div>
            <div className="azure-field">
              <label>Email <span>*</span></label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
            </div>
            <div className="azure-field">
              <label>API Token <span>*</span></label>
              <input type="password" value={apiToken} onChange={(e) => setApiToken(e.target.value)} placeholder="Paste your API token" />
              <small>Generate at <strong>id.atlassian.com/manage-profile/security/api-tokens</strong></small>
            </div>
            <div className="azure-field-row">
              <div className="azure-field">
                <label>Project Key <span>*</span></label>
                <input value={projectKey} onChange={(e) => setProjectKey(e.target.value)} placeholder="e.g. PROJ" />
              </div>
              <div className="azure-field azure-field-sm">
                <label>Max Items</label>
                <input type="number" value={maxItems} onChange={(e) => setMaxItems(e.target.value)} min="1" max="200" />
              </div>
            </div>
          </>}

          {/* ── Confluence fields ── */}
          {source === 'confluence' && <>
            <div className="azure-field">
              <label>Confluence Host <span>*</span></label>
              <input value={host} onChange={(e) => setHost(e.target.value)} placeholder="https://your-org.atlassian.net/wiki" autoFocus />
            </div>
            <div className="azure-field">
              <label>Email <span>*</span></label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
            </div>
            <div className="azure-field">
              <label>API Token <span>*</span></label>
              <input type="password" value={apiToken} onChange={(e) => setApiToken(e.target.value)} placeholder="Paste your API token" />
              <small>Generate at <strong>id.atlassian.com/manage-profile/security/api-tokens</strong></small>
            </div>
            <div className="azure-field-row">
              <div className="azure-field">
                <label>Space Key <span>*</span></label>
                <input value={spaceKey} onChange={(e) => setSpaceKey(e.target.value)} placeholder="e.g. TEAM" />
              </div>
              <div className="azure-field azure-field-sm">
                <label>Max Pages</label>
                <input type="number" value={maxItems} onChange={(e) => setMaxItems(e.target.value)} min="1" max="100" />
              </div>
            </div>
          </>}

          <div className="azure-modal-footer">
            <button type="button" className="review-cancel-btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="review-confirm-btn" disabled={!canConnect} style={{ background: `linear-gradient(90deg, ${meta.color}, ${meta.color}cc)` }}>
              {connecting
                ? <><div className="postman-spinner" />Fetching stories…</>
                : <><Icon name={meta.icon} size={15} />Fetch User Stories</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
