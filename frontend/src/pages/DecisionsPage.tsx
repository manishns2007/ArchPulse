import React, { useEffect, useState } from 'react';
import {
  Scale,
  Search,
  Filter,
  ShieldCheck,
  RefreshCw,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';
import type { DecisionItem } from '../api/decisions';
import { getProjectDecisions } from '../api/decisions';

interface DecisionsPageProps {
  projectId: string;
  onOpenAddModal: () => void;
  onInspectProvenance: (item: any) => void;
}

export const DecisionsPage: React.FC<DecisionsPageProps> = ({
  projectId,
  onOpenAddModal,
  onInspectProvenance,
}) => {
  const [decisions, setDecisions] = useState<DecisionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'decision' | 'approval'>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const loadDecisions = async () => {
    setLoading(true);
    try {
      const data = await getProjectDecisions(projectId);
      setDecisions(data);
    } catch (err) {
      console.error('Failed to load decisions:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDecisions();
  }, [projectId]);

  const filtered = decisions.filter(d => {
    const matchesSearch =
      !searchTerm ||
      (d.subject && d.subject.toLowerCase().includes(searchTerm.toLowerCase())) ||
      d.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.decision_id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = typeFilter === 'all' || d.item_type === typeFilter;
    const matchesStatus = statusFilter === 'all' || d.status.toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesType && matchesStatus;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
            Decisions & Approvals (M6)
          </h1>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Authoritative project agreements and stakeholder sign-offs extracted from unstructured discussions.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={loadDecisions}
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

      {/* Filter Bar */}
      <div
        className="glass-panel"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px 16px',
          borderRadius: 'var(--radius-md)',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '200px' }}>
          <Search size={15} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search subject, description, or ID..."
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

        {/* Type Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Type:</span>
          <select
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value as any)}
            style={{
              background: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '4px 8px',
              fontSize: '12px',
            }}
          >
            <option value="all">All Types</option>
            <option value="decision">Decision</option>
            <option value="approval">Approval</option>
          </select>
        </div>

        {/* Status Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Status:</span>
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            style={{
              background: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '4px 8px',
              fontSize: '12px',
            }}
          >
            <option value="all">All Statuses</option>
            <option value="approved">Approved</option>
            <option value="pending">Pending</option>
            <option value="rejected">Rejected</option>
            <option value="review">Review</option>
          </select>
        </div>
      </div>

      {/* Decision Cards */}
      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
          Loading decisions and approvals...
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
          <Scale size={36} color="var(--text-muted)" />
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
            No decisions or approvals found
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '420px' }}>
            {searchTerm || typeFilter !== 'all' || statusFilter !== 'all'
              ? 'No records match your selected filters. Try clearing your filters.'
              : `Project "${projectId}" has no decisions indexed yet. Ingest an email or meeting with design or budget decisions.`}
          </p>
          <button onClick={onOpenAddModal} className="btn-primary" style={{ marginTop: '8px', fontSize: '12px' }}>
            <Sparkles size={14} />
            <span>Ingest First Communication</span>
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: '16px' }}>
          {filtered.map(dec => (
            <div
              key={dec.decision_id}
              className="glass-panel"
              style={{
                padding: '16px 20px',
                borderRadius: 'var(--radius-md)',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                justifyContent: 'space-between',
              }}
            >
              <div>
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className={`badge badge-${dec.item_type}`}>
                      {dec.item_type}
                    </span>
                    <span className={`badge badge-${dec.status.toLowerCase()}`}>
                      {dec.status}
                    </span>
                  </div>

                  <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    {dec.decision_id.slice(0, 10)}...
                  </span>
                </div>

                {/* Subject / Title */}
                {dec.subject && (
                  <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
                    {dec.subject}
                  </h3>
                )}

                {/* Description */}
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '10px' }}>
                  {dec.description}
                </p>

                {/* Verbatim Evidence */}
                {dec.evidence && (
                  <div
                    style={{
                      background: 'var(--bg-surface)',
                      borderLeft: '2px solid var(--accent)',
                      padding: '8px 12px',
                      borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
                      fontSize: '12px',
                      fontStyle: 'italic',
                      color: 'var(--text-secondary)',
                      lineHeight: 1.4,
                    }}
                  >
                    "{dec.evidence}"
                  </div>
                )}
              </div>

              {/* Provenance Footer */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingTop: '10px',
                  borderTop: '1px solid var(--border-subtle)',
                  fontSize: '11px',
                }}
              >
                <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  comm: {dec.communication_id ? dec.communication_id.slice(0, 8) + '...' : 'n/a'}
                </span>

                <button
                  onClick={() =>
                    onInspectProvenance({
                      item_type: dec.item_type,
                      source_id: dec.decision_id,
                      communication_id: dec.communication_id,
                      title: dec.subject ? `${dec.subject}: ${dec.description}` : dec.description,
                      content: dec.description,
                      evidence: dec.evidence,
                      score: 1.0,
                      retrieval_mode: 'deterministic',
                      metadata: {
                        subject: dec.subject,
                        status: dec.status,
                      },
                    })
                  }
                  className="btn-ghost"
                  style={{ fontSize: '11px', padding: '3px 8px', gap: '4px' }}
                >
                  <ShieldCheck size={12} color="var(--status-approved)" />
                  <span>Inspect Provenance</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
