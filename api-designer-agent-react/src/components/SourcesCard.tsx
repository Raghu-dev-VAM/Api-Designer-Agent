import { useRef, useState } from 'react';
import Icon from './Icon';
import SectionHeader from './SectionHeader';
import SourceConnectModal from './SourceConnectModal';
import { sources } from '../data';
import type { AzureConfig, JiraConfig, ConfluenceConfig } from '../services/documentService';

type ConnectableSource = 'azure' | 'jira' | 'confluence';
const CONNECTABLE: ConnectableSource[] = ['azure', 'jira', 'confluence'];

interface SourcesCardProps {
  selectedSourceIds: string[];
  onToggle: (id: string) => void;
  onAddSource: () => void;
  onSync: () => void;
  onUploadFile: (file: File) => void;
  uploading: boolean;
  onConnectAzure: (cfg: AzureConfig) => void;
  onConnectJira: (cfg: JiraConfig) => void;
  onConnectConfluence: (cfg: ConfluenceConfig) => void;
  connectingSource: ConnectableSource | null;
}

export default function SourcesCard({
  selectedSourceIds, onToggle, onAddSource, onSync, onUploadFile, uploading,
  onConnectAzure, onConnectJira, onConnectConfluence, connectingSource,
}: SourcesCardProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeModal, setActiveModal] = useState<ConnectableSource | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUploadFile(file);
    e.target.value = '';
  };

  const handleSourceClick = (id: string) => {
    if (CONNECTABLE.includes(id as ConnectableSource)) {
      setActiveModal(id as ConnectableSource);
    } else {
      onToggle(id);
    }
  };

  const handleConnect = (cfg: AzureConfig | JiraConfig | ConfluenceConfig) => {
    if (activeModal === 'azure') onConnectAzure(cfg as AzureConfig);
    else if (activeModal === 'jira') onConnectJira(cfg as JiraConfig);
    else if (activeModal === 'confluence') onConnectConfluence(cfg as ConfluenceConfig);
    setActiveModal(null);
  };

  return (
    <>
      <article className="card sources-card">
        <SectionHeader number="1" title="Sources" subtitle="Connect or upload requirement sources" />
        <div className="card-body">
          {sources.map((source) => {
            const isConnectable = CONNECTABLE.includes(source.id as ConnectableSource);
            const isConnected = selectedSourceIds.includes(source.id);
            return (
              <button
                className={`source-item ${isConnected ? 'selected' : ''}`}
                key={source.id}
                onClick={() => handleSourceClick(source.id)}
              >
                <span className="source-icon" style={{ background: source.color }}><Icon name={source.icon} /></span>
                <span>
                  <strong>{source.name}</strong>
                  <small>{isConnectable ? 'Click to connect & fetch stories' : source.desc}</small>
                </span>
                {isConnectable
                  ? <span className="source-connect-hint"><Icon name="plug" size={12} />{isConnected ? 'Connected' : 'Connect'}</span>
                  : <span className="source-check"><Icon name="check" size={13} /></span>}
              </button>
            );
          })}

          {/* Single unified upload button for Word + Excel/CSV */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx,.xlsx,.csv"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
          <button
            className={`source-item ${uploading ? '' : selectedSourceIds.includes('docx') ? 'selected' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            <span className="source-icon" style={{ background: '#f3e8ff' }}>
              <Icon name={uploading ? 'refresh' : 'file'} />
            </span>
            <span>
              <strong>{uploading ? 'Extracting…' : 'Upload Document'}</strong>
              <small>{uploading ? 'Processing…' : 'Upload .docx, .xlsx or .csv'}</small>
            </span>
            <span className="source-connect-hint" style={{ color: '#7c3aed', borderColor: '#c4b5fd', background: '#f5f3ff' }}>
              <Icon name="folder" size={12} />{uploading ? 'Loading' : 'Upload'}
            </span>
          </button>

          <button className="source-item add-source" onClick={onAddSource}>
            <span className="source-icon"><Icon name="plus" /></span>
            <span><strong>More Sources</strong><small>Add connectors</small></span>
          </button>

          <div className="connected-bar">
            <Icon name="check" size={16} />
            <span><strong>Source connected successfully</strong><small>{selectedSourceIds.length} sources | Last sync: 2 min ago</small></span>
            <button aria-label="Sync sources" onClick={onSync}><Icon name="refresh" /></button>
          </div>
        </div>
      </article>

      {activeModal && (
        <SourceConnectModal
          source={activeModal}
          onClose={() => setActiveModal(null)}
          onConnectAzure={onConnectAzure}
          onConnectJira={onConnectJira}
          onConnectConfluence={onConnectConfluence}
          connecting={connectingSource === activeModal}
        />
      )}
    </>
  );
}
