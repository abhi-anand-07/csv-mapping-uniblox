import { useState } from 'react';
import Upload from './components/Upload';
import MappingReview from './components/MappingReview';
import { MappingProposal } from './types';

export default function App() {
  const [proposal, setProposal] = useState<MappingProposal | null>(null);
  const [error, setError] = useState('');

  const handleUpload = (p: MappingProposal) => {
    setError('');
    setProposal(null); // clear old data immediately so UI doesn't flash stale rows
    setTimeout(() => setProposal(p), 50); // then show new data
  };

  const handleError = (msg: string) => {
    setError(msg);
  };

  return (
    <div className="container">
      <header style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 16 }}>
        <img src="/logo.jpeg" alt="Uniblox" style={{ width: 48, height: 48, borderRadius: 8, objectFit: 'cover' }} />
        <div>
          <h1 style={{ marginBottom: 4 }}>AI Mapping Copilot</h1>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            Intelligent column mapping for insurance operations. Upload a CSV, review AI proposals, and publish clean data.
          </p>
        </div>
      </header>

      {error && (
        <div className="alert alert-danger" style={{ marginBottom: 20 }}>
          {error}
        </div>
      )}

      <Upload onUpload={handleUpload} onError={handleError} />

      {proposal && <MappingReview key={proposal.session_id} proposal={proposal} onRefresh={setProposal} />}
    </div>
  );
}
