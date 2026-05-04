import Icon from './Icon';
import SectionHeader from './SectionHeader';
import { actions } from '../data';

interface ActionsCardProps {
  onAction: (name: string) => void;
}

export default function ActionsCard({ onAction }: ActionsCardProps) {
  return (
    <article className="card actions-card">
      <SectionHeader number="5" title="Actions" tone="purple" />
      <div className="card-body action-grid">
        {actions.map(([name, desc, icon]) => (
          <button className="action-item" key={name} onClick={() => onAction(name)}>
            <Icon name={icon} size={28} />
            <strong>{name}</strong>
            <span>{desc}</span>
          </button>
        ))}
      </div>
    </article>
  );
}
