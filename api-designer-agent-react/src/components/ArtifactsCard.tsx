import Icon from './Icon';
import SectionHeader from './SectionHeader';
import { artifacts } from '../data';
import type { Requirement, ActivityItem } from '../types';

interface ArtifactsCardProps {
  selectedRequirement: Requirement | null;
  lastGeneratedAt: string;
  activity: ActivityItem[];
  onDownload: (filename: string, contents: string) => void;
}

export default function ArtifactsCard({ selectedRequirement, lastGeneratedAt, activity, onDownload }: ArtifactsCardProps) {
  return (
    <article className="card artifact-card">
      <SectionHeader number="4" title="Output Artifacts" subtitle="Download and share design artifacts" tone="green" />
      <div className="card-body">
        {artifacts.map(([name, desc, icon, color]) => (
          <button className="artifact-item" key={name} disabled={!selectedRequirement} onClick={() => selectedRequirement && onDownload(
            `${name.split(' ')[0].toLowerCase()}-${selectedRequirement.id}.txt`,
            `${name}\n${desc}\n\nGenerated for ${selectedRequirement.id}: ${selectedRequirement.title}`
          )}>
            <span className="artifact-icon" style={{ background: color }}><Icon name={icon} /></span>
            <span><strong>{name}</strong><small>{desc}</small></span>
            <Icon name="download" size={16} />
          </button>
        ))}
        <div className="last-generated">
          <Icon name="bot" size={38} />
          <div>
            <strong>Last Generated</strong>
            <p>Requirement: {selectedRequirement ? `${selectedRequirement.id}: ${selectedRequirement.title}` : '—'}</p>
            <p>Generated on: Apr 28, 2026 {lastGeneratedAt}</p>
            {activity.map((item, index) => <p key={`${item.label}-${index}`}>{item.label}: {item.value}</p>)}
          </div>
        </div>
      </div>
    </article>
  );
}
