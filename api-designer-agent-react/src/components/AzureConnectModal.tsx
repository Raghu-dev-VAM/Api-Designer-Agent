import { useState } from 'react';
import Icon from './Icon';
import type { AzureConfig } from '../services/documentService';

interface AzureConnectModalProps {
  onClose: () => void;
  onConnect: (cfg: AzureConfig) => void;
  connecting: boolean;
}

export default function AzureConnectModal({ onClose, onConnect, connecting }: AzureConnectModalProps) {
  const [org, setOrg] = useState('');
  const [project, setProject] = useState('');
  const [pat, setPat] = useState('');
  const [areaPath, setAreaPath] = useState('');
  const [maxItems, setMaxItems] = useState('50');

  const canConnect = org.trim() && project.trim() && pat.trim() && !connecting;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canConnect) return;
    onConnect({ organization: org.trim(), project: project.trim(), pat: pat.trim(), areaPath: areaPath.trim() || undefined, maxItems: parseInt(maxItems) || 50 });
  };

  return (
    <div className="azure-modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="azure-modal">
        <div className="azure-modal-header">
          <span className="azure-modal-title"><Icon name="azure" size={18} />Connect to Azure DevOps</span>
          <button className="review-close-btn" onClick={onClose} aria-label="Close"><Icon name="plus" size={16} /></button>
        </div>

        <form className="azure-modal-body" onSubmit={handleSubmit}>
          <div className="azure-field">
            <label>Organization <span>*</span></label>
            <input value={org} onChange={(e) => setOrg(e.target.value)} placeholder="e.g. my-org" autoFocus />
            <small>Your Azure DevOps organization name from dev.azure.com/<strong>org</strong></small>
          </div>

          <div className="azure-field">
            <label>Project <span>*</span></label>
            <input value={project} onChange={(e) => setProject(e.target.value)} placeholder="e.g. MyProject" />
          </div>

          <div className="azure-field">
            <label>Personal Access Token (PAT) <span>*</span></label>
            <input type="password" value={pat} onChange={(e) => setPat(e.target.value)} placeholder="Paste your PAT here" />
            <small>Requires <strong>Work Items (Read)</strong> scope</small>
          </div>

          <div className="azure-field-row">
            <div className="azure-field">
              <label>Area Path <span className="optional">(optional)</span></label>
              <input value={areaPath} onChange={(e) => setAreaPath(e.target.value)} placeholder="e.g. MyProject\\Team" />
            </div>
            <div className="azure-field azure-field-sm">
              <label>Max Items</label>
              <input type="number" value={maxItems} onChange={(e) => setMaxItems(e.target.value)} min="1" max="200" />
            </div>
          </div>

          <div className="azure-modal-footer">
            <button type="button" className="review-cancel-btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="review-confirm-btn" disabled={!canConnect}>
              {connecting
                ? <><div className="postman-spinner" />Fetching stories…</>
                : <><Icon name="azure" size={15} />Fetch User Stories</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
