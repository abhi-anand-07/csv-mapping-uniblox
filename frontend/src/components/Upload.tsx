import { useCallback, useState } from 'react';
import api from '../api';
import { MappingProposal } from '../types';

interface Props {
  onUpload: (proposal: MappingProposal) => void;
  onError: (msg: string) => void;
}

export default function Upload({ onUpload, onError }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      onError('Only CSV files are supported.');
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post('/api/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onUpload(res.data);
    } catch (err: any) {
      onError(err?.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) {
      handleFile(e.dataTransfer.files[0]);
    }
  }, []);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback(() => setDragOver(false), []);

  const testWithSample = async () => {
    setUploading(true);
    try {
      const res = await fetch('/sample.csv');
      const blob = await res.blob();
      const file = new File([blob], 'sample.csv', { type: 'text/csv' });
      const form = new FormData();
      form.append('file', file);
      const uploadRes = await api.post('/api/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onUpload(uploadRes.data);
    } catch (err: any) {
      onError(err?.response?.data?.detail || 'Failed to load sample file.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="card">
      <h2 style={{ marginBottom: 8 }}>Upload Spreadsheet</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>
        Drop your messy CSV here and let the AI propose mappings to the canonical schema.
      </p>

      <div
        className={`upload-zone ${dragOver ? 'dragover' : ''}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => document.getElementById('csv-input')?.click()}
      >
        <input
          id="csv-input"
          type="file"
          accept=".csv"
          style={{ display: 'none' }}
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {uploading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
            <div className="spinner" style={{ borderTopColor: 'var(--primary)' }} />
            <span>Analyzing with AI agent...</span>
          </div>
        ) : (
          <>
            <div style={{ fontSize: 40, marginBottom: 8 }}>⬆️</div>
            <div style={{ fontWeight: 600 }}>Click or drag a CSV file here</div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>
              Max 10MB · The AI will read headers + sample rows
            </div>
          </>
        )}
      </div>

      <div style={{ display: 'flex', gap: 12, marginTop: 16, justifyContent: 'center' }}>
        <a
          href="/sample.csv"
          download
          className="btn btn-outline"
          style={{ fontSize: 13 }}
        >
          ⬇️ Download Sample CSV
        </a>
        <button
          onClick={testWithSample}
          className="btn btn-outline"
          style={{ fontSize: 13 }}
          disabled={uploading}
        >
          🧪 Test with Sample
        </button>
      </div>
    </div>
  );
}
