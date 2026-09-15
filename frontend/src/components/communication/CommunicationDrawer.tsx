import React, { useEffect, useState } from 'react';
import {
  X,
  FileText,
  CheckSquare,
  Scale,
  Calendar,
  User,
  ExternalLink,
  ShieldCheck,
  Tag,
  Clock,
} from 'lucide-react';
import type { CommunicationRecord, StructuredTask, ExtractedDecision } from '../../types';
import { getTasksByCommunication } from '../../api/tasks';
import { getDecisionsByCommunication } from '../../api/decisions';

interface CommunicationDrawerProps {
  communication: CommunicationRecord | null;
  onClose: () => void;
  onInspectProvenance: (item: any) => void;
}

export const CommunicationDrawer: React.FC<CommunicationDrawerProps> = ({
  communication,
  onClose,
  onInspectProvenance,
}) => {
  const [tasks, setTasks] = useState<StructuredTask[]>([]);
  const [decisions, setDecisions] = useState<ExtractedDecision[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!communication) return;
    let mounted = true;
    setLoading(true);

    Promise.all([
      getTasksByCommunication(communication.communication_id).catch(() => []),
      getDecisionsByCommunication(communication.communication_id).catch(() => []),
    ]).then(([taskList, decList]) => {
      if (mounted) {
        setTasks(taskList);
        setDecisions(decList);
        setLoading(false);
      }
    });

    return () => {
      mounted = false;
    };
  }, [communication]);

  if (!communication) return null;

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div
        className="drawer-content"
        onClick={e => e.stopPropagation()}
        style={{
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="badge badge-communication">
              {communication.source_type}
            </span>
            <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              {communication.communication_id.slice(0, 8)}...
            </span>
          </div>
          <button onClick={onClose} className="btn-ghost" aria-label="Close drawer">
            <X size={18} />
          </button>
        </div>

        {/* Ingestion Meta */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div style={{ background: 'var(--bg-surface)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '2px' }}>Project</div>
            <div style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: 600 }}>
              {communication.project_id}
            </div>
          </div>
          <div style={{ background: 'var(--bg-surface)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '2px' }}>Ingested At</div>
            <div style={{ fontSize: '12px', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={12} color="var(--text-muted)" />
              {communication.ingested_at ? new Date(communication.ingested_at).toLocaleString() : 'Just now'}
            </div>
          </div>
        </div>

        {/* Raw Communication Text */}
        <div>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px', letterSpacing: '0.5px' }}>
            Raw Unstructured Content
          </div>
          <div
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-card)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
              fontSize: '13px',
              color: 'var(--text-secondary)',
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              maxHeight: '180px',
              overflowY: 'auto',
            }}
          >
            {communication.raw_content}
          </div>
        </div>

        {/* Extracted Tasks (M7) */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckSquare size={13} color="var(--accent)" />
              <span>Extracted Tasks ({tasks.length})</span>
            </div>
          </div>

          {tasks.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic', padding: '8px 0' }}>
              {loading ? 'Retrieving extracted tasks...' : 'No structured tasks derived from this communication.'}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {tasks.map(t => (
                <div
                  key={t.task_id}
                  style={{
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '10px 12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {t.title}
                    </span>
                    <span className={`badge badge-${t.status.toLowerCase()}`}>
                      {t.status}
                    </span>
                  </div>

                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', lineHeight: 1.4 }}>
                    {t.description}
                  </p>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      {t.responsible_party && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <User size={11} />
                          {t.responsible_party}
                        </span>
                      )}
                      {t.deadline && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <Calendar size={11} />
                          {t.deadline}
                        </span>
                      )}
                    </div>

                    <button
                      onClick={() =>
                        onInspectProvenance({
                          item_type: 'task',
                          source_id: t.task_id,
                          communication_id: communication.communication_id,
                          title: t.title,
                          content: t.description,
                          evidence: t.evidence,
                          score: 1.0,
                          retrieval_mode: 'deterministic',
                          metadata: {
                            responsible_party: t.responsible_party,
                            deadline: t.deadline,
                            status: t.status,
                            priority: t.priority,
                          },
                        })
                      }
                      className="btn-ghost"
                      style={{ padding: '2px 6px', fontSize: '10px', gap: '4px' }}
                    >
                      <ShieldCheck size={11} color="var(--status-approved)" />
                      <span>Provenance</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Extracted Decisions (M6) */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Scale size={13} color="var(--accent)" />
              <span>Decisions & Approvals ({decisions.length})</span>
            </div>
          </div>

          {decisions.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic', padding: '8px 0' }}>
              {loading ? 'Retrieving extracted decisions...' : 'No decisions extracted from this communication.'}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {decisions.map(d => (
                <div
                  key={d.decision_id}
                  style={{
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '10px 12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {d.subject || 'Decision Item'}
                    </span>
                    <span className={`badge badge-${d.status.toLowerCase()}`}>
                      {d.status}
                    </span>
                  </div>

                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', lineHeight: 1.4 }}>
                    {d.description}
                  </p>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', fontSize: '11px' }}>
                    <button
                      onClick={() =>
                        onInspectProvenance({
                          item_type: d.item_type === 'approval' ? 'approval' : 'decision',
                          source_id: d.decision_id,
                          communication_id: communication.communication_id,
                          title: d.subject ? `${d.subject}: ${d.description}` : d.description,
                          content: d.description,
                          evidence: d.evidence,
                          score: d.confidence || 1.0,
                          retrieval_mode: 'deterministic',
                          metadata: {
                            subject: d.subject,
                            status: d.status,
                            confidence: d.confidence,
                          },
                        })
                      }
                      className="btn-ghost"
                      style={{ padding: '2px 6px', fontSize: '10px', gap: '4px' }}
                    >
                      <ShieldCheck size={11} color="var(--status-approved)" />
                      <span>Provenance</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
