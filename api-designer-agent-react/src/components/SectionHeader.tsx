interface SectionHeaderProps {
  number: string;
  title: string;
  subtitle?: string;
  tone?: string;
}

export default function SectionHeader({ number, title, subtitle, tone = 'blue' }: SectionHeaderProps) {
  return (
    <div className="card-header">
      <div className="title-row">
        <span className={`section-num ${tone}`}>{number}</span>
        <span className={`section-title ${tone}`}>{title}</span>
      </div>
      {subtitle && <p>{subtitle}</p>}
    </div>
  );
}
