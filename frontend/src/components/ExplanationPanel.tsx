interface Props {
  summary: string;
  missingRequired: string[];
  unmappedCount: number;
  overallConfidence: number;
}

export default function ExplanationPanel({
  summary,
  missingRequired,
  unmappedCount,
  overallConfidence,
}: Props) {
  return (
    <div className="card">
      <h3 style={{ marginBottom: 12 }}>AI Summary</h3>
      <p style={{ lineHeight: 1.6, margin: '0 0 12px' }}>{summary}</p>

      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginTop: 16 }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
            Overall Confidence
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: overallConfidence >= 0.7 ? 'var(--success)' : overallConfidence >= 0.4 ? 'var(--warning)' : 'var(--danger)' }}>
            {Math.round(overallConfidence * 100)}%
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
            Unmapped Columns
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: unmappedCount > 0 ? 'var(--warning)' : 'var(--success)' }}>
            {unmappedCount}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
            Missing Required
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: missingRequired.length > 0 ? 'var(--danger)' : 'var(--success)' }}>
            {missingRequired.length}
          </div>
        </div>
      </div>

      {missingRequired.length > 0 && (
        <div className="alert alert-danger" style={{ marginTop: 16 }}>
          <strong>Missing required fields:</strong> {missingRequired.join(', ')}
        </div>
      )}
    </div>
  );
}
