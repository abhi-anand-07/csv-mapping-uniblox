import { useState, useEffect } from 'react';
import axios from 'axios';
import ConfidenceBadge from './ConfidenceBadge';
import ExplanationPanel from './ExplanationPanel';
import { MappingProposal, PublishResult } from '../types';

interface Props {
  proposal: MappingProposal;
  onRefresh: (p: MappingProposal) => void;
}

interface SchemaInfo {
  type: string;
  required: boolean;
  description: string;
}

interface SchemaResponse {
  schema: Record<string, SchemaInfo>;
  required_fields: string[];
}

export default function MappingReview({ proposal, onRefresh }: Props) {
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [published, setPublished] = useState<PublishResult | null>(null);
  const [error, setError] = useState('');
  const [schema, setSchema] = useState<SchemaResponse | null>(null);

  useEffect(() => {
    axios.get('/api/schema')
      .then((res) => setSchema(res.data))
      .catch((err) => console.error('Failed to load schema', err));
  }, []);

  const handleChange = (source: string, value: string) => {
    setEdits((prev) => ({ ...prev, [source]: value }));
  };

  const handleSave = async () => {
    const updates = Object.entries(edits)
      .filter(([source]) => source)
      .map(([source, target]) => ({
        source_column: source,
        target_column: target || null,
      }));

    if (updates.length === 0) return;
    setSaving(true);
    setError('');
    try {
      const res = await axios.patch(`/api/mappings/${proposal.session_id}`, updates);
      onRefresh(res.data);
      setEdits({});
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save edits.');
    } finally {
      setSaving(false);
    }
  };

  const handleApproveAndPublish = async () => {
    setPublishing(true);
    setError('');
    try {
      await axios.post(`/api/approve/${proposal.session_id}`);
      const res = await axios.post(`/api/publish/${proposal.session_id}`);
      setPublished(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to publish.');
    } finally {
      setPublishing(false);
    }
  };

  const unmappedCount = proposal.mappings.filter((m) => !m.target_column && m.source_column).length;

  return (
    <div>
      <ExplanationPanel
        summary={proposal.summary}
        missingRequired={proposal.missing_required_fields}
        unmappedCount={unmappedCount}
        overallConfidence={proposal.overall_confidence}
      />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ margin: 0 }}>Proposed Mappings</h3>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            {proposal.file_name} · {proposal.ingestion.row_count} rows
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Source Column</th>
                <th>Sample Values</th>
                <th>Mapped To</th>
                <th>Confidence</th>
                <th>Reasoning</th>
                <th>Warnings</th>
              </tr>
            </thead>
            <tbody>
              {proposal.mappings.map((m) => {
                const isConflict = m.warnings.some((w) => w.includes('Conflict'));
                const currentValue = edits[m.source_column] !== undefined ? edits[m.source_column] : (m.target_column || '');
                return (
                  <tr key={m.source_column || m.target_column || Math.random()} className={isConflict ? 'conflict-row' : ''}>
                    <td>
                      <strong>{m.source_column || <em className="missing-required">(missing source)</em>}</strong>
                    </td>
                    <td>
                      <div className="sample-values" title={m.sample_values.join(', ')}>
                        {m.sample_values.slice(0, 2).join(', ') || '—'}
                      </div>
                    </td>
                    <td>
                      <select
                        value={currentValue}
                        onChange={(e) => handleChange(m.source_column, e.target.value)}
                      >
                        <option value="">— Do not map —</option>
                        {schema && Object.entries(schema.schema).map(([key, info]) => (
                          <option key={key} value={key}>
                            {key}{info.required ? ' *' : ''} ({info.type})
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <ConfidenceBadge level={m.confidence_level} score={m.confidence} />
                    </td>
                    <td>
                      <div className="reasoning">{m.reasoning}</div>
                    </td>
                    <td>
                      {m.warnings.length > 0 ? (
                        <div style={{ color: 'var(--warning)', fontSize: 12 }}>
                          {m.warnings.map((w, i) => (
                            <div key={i}>⚠️ {w}</div>
                          ))}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="actions-bar">
          <div>
            {Object.keys(edits).length > 0 && (
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? <div className="spinner" /> : '💾 Save Edits'}
              </button>
            )}
          </div>
          <button
            className="btn btn-success"
            onClick={handleApproveAndPublish}
            disabled={publishing || proposal.missing_required_fields.length > 0}
            title={
              proposal.missing_required_fields.length > 0
                ? 'Cannot publish while required fields are missing'
                : 'Approve and generate canonical CSV'
            }
          >
            {publishing ? <div className="spinner" /> : '✅ Approve & Publish'}
          </button>
        </div>

        {proposal.missing_required_fields.length > 0 && (
          <div className="alert alert-warning" style={{ marginTop: 12 }}>
            Please map all required fields before publishing:{' '}
            <strong>{proposal.missing_required_fields.join(', ')}</strong>
          </div>
        )}
      </div>

      {published && (
        <div className="card" style={{ border: '2px solid var(--success)' }}>
          <h3 style={{ color: 'var(--success)', marginBottom: 8 }}>Published Successfully 🎉</h3>
          <p>
            {published.row_count} rows · {published.column_count} columns ·{' '}
            {published.mapped_fields.length} mapped, {published.unmapped_fields.length} unmapped
          </p>
          <a
            className="btn btn-primary"
            href={published.download_url}
            download
            style={{ marginTop: 8 }}
          >
            ⬇️ Download Canonical CSV
          </a>
        </div>
      )}
    </div>
  );
}
