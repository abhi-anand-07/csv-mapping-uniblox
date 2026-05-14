interface Props {
  level: 'high' | 'medium' | 'low' | 'uncertain';
  score: number;
}

export default function ConfidenceBadge({ level, score }: Props) {
  const labels: Record<string, string> = {
    high: 'High',
    medium: 'Medium',
    low: 'Low',
    uncertain: 'Uncertain',
  };

  return (
    <span className={`badge badge-${level}`}>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          display: 'inline-block',
          background:
            level === 'high'
              ? '#16a34a'
              : level === 'medium'
              ? '#d97706'
              : level === 'low'
              ? '#ea580c'
              : '#dc2626',
        }}
      />
      {labels[level] || level} ({Math.round(score * 100)}%)
    </span>
  );
}
