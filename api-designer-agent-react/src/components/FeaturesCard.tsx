import Icon from './Icon';
import SectionHeader from './SectionHeader';
import { features } from '../data';

export default function FeaturesCard() {
  return (
    <article className="card features-card">
      <SectionHeader number="6" title="What API Designer Agent Does" />
      <div className="card-body feature-grid">
        {features.map(([title, items, icon]) => (
          <div className="feature-col" key={title}>
            <Icon name={icon} size={24} />
            <strong>{title}</strong>
            <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
        ))}
      </div>
    </article>
  );
}
