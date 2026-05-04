import { useRef } from 'react';
import Icon from './Icon';
import SectionHeader from './SectionHeader';
import { sources } from '../data';

interface SourcesCardProps {
  selectedSourceIds: string[];
  onToggle: (id: string) => void;
  onAddSource: () => void;
  onSync: () => void;
  onUploadDocx: (file: File) => void;
  uploading: boolean;
}

export default function SourcesCard({ selectedSourceIds, onToggle, onAddSource, onSync, onUploadDocx, uploading }: SourcesCardProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUploadDocx(file);
    e.target.value = '';
  };

  return (
    <article className="card sources-card">
      <SectionHeader number="1" title="Sources" subtitle="Connect or upload requirement sources" />
      <div className="card-body">
        {sources.map((source) => (
          <button className={`source-item ${selectedSourceIds.includes(source.id) ? 'selected' : ''}`} key={source.id} onClick={() => onToggle(source.id)}>
            <span className="source-icon" style={{ background: source.color }}><Icon name={source.icon} /></span>
            <span><strong>{source.name}</strong><small>{source.desc}</small></span>
            <span className="source-check"><Icon name="check" size={13} /></span>
          </button>
        ))}

        <input
          ref={fileInputRef}
          type="file"
          accept=".docx"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
        <button
          className="source-item add-source"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          <span className="source-icon"><Icon name={uploading ? 'refresh' : 'folder'} /></span>
          <span>
            <strong>{uploading ? 'Extracting…' : 'Upload Word Doccument'}</strong>
            <small>{uploading ? 'Processing with GROQ AI' : 'Upload .docx to extract requirements'}</small>
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
  );
}
