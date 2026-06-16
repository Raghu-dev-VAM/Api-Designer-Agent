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
  onUploadDocx: (file: File) => void;
  uploading: boolean;
  onConnectAzure: (cfg: AzureConfig) => void;
  onConnectJira: (cfg: JiraConfig) => void;
  onConnectConfluence: (cfg: ConfluenceConfig) => void;
  connectingSource: ConnectableSource | null;
  onUploadExcel: (file: File) => void;
  uploadingExcel: boolean;
}

export default function SourcesCard({
  selectedSourceIds, onToggle, onAddSource, onSync, onUploadDocx, uploading,
  onConnectAzure, onConnectJira, onConnectConfluence, connectingSource,
  onUploadExcel, uploadingExcel,
}: SourcesCardProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const excelInputRef = useRef<HTMLInputElement>(null);
  const [activeModal, setActiveModal] = useState<ConnectableSource | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUploadDocx(file);
    e.target.value = '';
  };

  const handleSourceClick = (id: string) => {
    if (CONNECTABLE.includes(id as ConnectableSource)) {
      setActiveModal(id as ConnectableSource);
    } else if (id === 'excel') {
      excelInputRef.current?.click();
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
            const isExcel = source.id === 'excel';
            return (
              <button
                className={`source-item ${isConnected ? 'selected' : ''}`}
                key={source.id}
                onClick={() => handleSourceClick(source.id)}
                disabled={isExcel && uploadingExcel}
              >
                <span className="source-icon" style={{ background: source.color }}><Icon name={isExcel && uploadingExcel ? 'refresh' : source.icon} /></span>
                <span>
                  <strong>{isExcel && uploadingExcel ? 'Extracting…' : source.name}</strong>
                  <small>{isConnectable ? 'Click to connect & fetch stories' : isExcel ? 'Click to upload .xlsx or .csv' : source.desc}</small>
                </span>
                {isConnectable
                  ? <span className="source-connect-hint"><Icon name="plug" size={12} />{isConnected ? 'Connected' : 'Connect'}</span>
                  : isExcel
                    ? <span className="source-connect-hint" style={{ color: '#047857', borderColor: '#a7f3d0', background: '#ecfdf5' }}><Icon name="folder" size={12} />Upload</span>
                    : <span className="source-check"><Icon name="check" size={13} /></span>}
              </button>
            );
          })}

          <input ref={fileInputRef} type="file" accept=".docx" style={{ display: 'none' }} onChange={handleFileChange} />
          <input ref={excelInputRef} type="file" accept=".xlsx,.csv" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) onUploadExcel(f); e.target.value = ''; }} />
          <button className={`source-item ${uploading ? '' : selectedSourceIds.includes('docx') ? 'selected' : ''}`} onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            <span className="source-icon" style={{ background: '#f3e8ff' }}><Icon name={uploading ? 'refresh' : 'file'} /></span>
            <span>
              <strong>{uploading ? 'Extracting…' : 'Word Document'}</strong>
              <small>{uploading ? 'Processing with GROQ AI' : 'Upload .docx to extract requirements'}</small>
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
