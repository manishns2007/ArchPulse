import React, { useEffect, useState } from 'react';
import {
  Inbox,
  Sparkles,
  Search,
  Filter,
  FileText,
  Clock,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';
import type { CommunicationRecord } from '../types';
import { getProjectCommunications } from '../api/ingestion';

interface CommunicationsPageProps {
  projectId: string;
  onOpenAddModal: () => void;
  onSelectCommunication: (comm: CommunicationRecord) => void;
  onInspectProvenance: (item: any) => void;
}

export const CommunicationsPage: React.FC<CommunicationsPageProps> = ({
  projectId,
  onOpenAddModal,
  onSelectCommunication,
  onInspectProvenance,
}) => {
  const [communications, setCommunications] = useState<CommunicationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<string>('all');

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await getProjectCommunications(projectId);
      setCommunications(data);
    } catch (err) {
      console.error('Failed to load communications:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [projectId]);

  const filtered = communications.filter(c => {
    const matchesSearch =
      !searchTerm ||
      c.raw_content.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.communication_id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = filterType === 'all' || c.source_type.toLowerCase() === filterType.toLowerCase();
    return matchesSearch && matchesType;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
            Communications Inbox
          </h1>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Raw ingested feeds from chats, emails, and meetings processed through the M1–M8 pipeline.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={loadData}
            disabled={loading}
            className="btn-secondary"
            style={{ fontSize: '12px', padding: '8px 12px' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <button
            onClick={onOpenAddModal}
            className="btn-primary"
            style={{ fontSize: '12px', padding: '8px 14px' }}
          >
            <Sparkles size={14} />
            <span>+ Ingest Communication</span>
          </button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div
        className="glass-panel"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px 16px',
          borderRadius: 'var(--radius-md)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
          <Search size={15} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search communication text or ID..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: '13px',
              outline: 'none',
            }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter size={14} color="var(--text-muted)" />
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value)}
            style={{
              background: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '4px 8px',
              fontSize: '12px',
            }}
          >
            <option value="all">All Source Types</option>
            <option value="text">Text</option>
            <option value="email">Email</option>
            <option value="transcript">Transcript</option>
            <option value="meeting_notes">Meeting Notes</option>
            <option value="slack">Slack / Chat</option>
          </select>
        </div>
      </div>

      {/* Communications Feed */}
      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
          Loading ingested streams...
        </div>
      ) : filtered.length === 0 ? (
        <div
          className="glass-panel"
          style={{
            padding: '48px 24px',
            textAlign: 'center',
            borderRadius: 'var(--radius-lg)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <Inbox size={36} color="var(--text-muted)" />
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
            No communications found
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '400px' }}>
            {searchTerm
              ? 'No communications match your search criteria. Try a different query.'
              : `Project "${projectId}" has no ingested communications yet. Ingest your first message to begin autonomous processing.`}
          </p>
          <button onClick={onOpenAddModal} className="btn-primary" style={{ marginTop: '8px', fontSize: '12px' }}>
            <Sparkles size={14} />
            <span>Ingest First Communication</span>
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filtered.map(comm => (
            <div
              key={comm.communication_id}
              className="glass-panel"
              style={{
                padding: '16px 20px',
                borderRadius: 'var(--radius-md)',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                transition: 'border-color var(--transition-fast)',
              }}
            >
              {/* Card Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span className="badge badge-communication">
                    {comm.source_type}
                  </span>
                  <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--accent-light)' }}>
                    {comm.communication_id}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
                  <Clock size={12} />
                  <span>
                    {comm.ingested_at ? new Date(comm.ingested_at).toLocaleString() : 'Recent'}
                  </span>
                </div>
              </div>

              {/* Snippet Content */}
              <div
                style={{
                  fontSize: '13px',
                  color: 'var(--text-primary)',
                  lineHeight: 1.5,
                  background: 'var(--bg-surface)',
                  padding: '12px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {comm.raw_content}
              </div>

              {/* Actions Footer */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  onClick={() =>
                    onInspectProvenance({
                      item_type: 'communication',
                      source_id: comm.communication_id,
                      communication_id: comm.communication_id,
                      title: `Communication (${comm.source_type})`,
                      content: comm.raw_content,
                      evidence: comm.raw_content.slice(0, 300),
                      score: 1.0,
                      retrieval_mode: 'deterministic',
                      metadata: {
                        source_type: comm.source_type,
                        ingested_at: comm.ingested_at,
                      },
                    })
                  }
                  className="btn-ghost"
                  style={{ fontSize: '11px', padding: '4px 8px', gap: '4px' }}
                >
                  <ShieldCheck size={12} color="var(--status-approved)" />
                  <span>Inspect Provenance</span>
                </button>

                <button
                  onClick={() => onSelectCommunication(comm)}
                  className="btn-primary"
                  style={{ fontSize: '11px', padding: '5px 12px', gap: '6px' }}
                >
                  <span>Inspect Pipeline Breakdown</span>
                  <ArrowRight size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
