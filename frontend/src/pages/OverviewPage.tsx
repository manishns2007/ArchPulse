import React, { useEffect, useState } from 'react';
import {
  Inbox,
  CheckSquare,
  Scale,
  Brain,
  MessageSquare,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Calendar,
  User,
  Activity,
  Layers,
  Search,
  ExternalLink,
} from 'lucide-react';
import type { ProjectMemoryOverview, StructuredTask, DecisionItem, CommunicationRecord } from '../types';
import { getProjectOverview } from '../api/memory';
import { getProjectTasks } from '../api/tasks';
import { getProjectDecisions } from '../api/decisions';
import { getProjectCommunications } from '../api/ingestion';

interface OverviewPageProps {
  projectId: string;
  onNavigate: (route: string) => void;
  onOpenAddModal: () => void;
  onInspectProvenance: (item: any) => void;
  onSelectCommunication: (comm: CommunicationRecord) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  projectId,
  onNavigate,
  onOpenAddModal,
  onInspectProvenance,
  onSelectCommunication,
}) => {
  const [overview, setOverview] = useState<ProjectMemoryOverview | null>(null);
  const [tasks, setTasks] = useState<StructuredTask[]>([]);
  const [decisions, setDecisions] = useState<DecisionItem[]>([]);
  const [communications, setCommunications] = useState<CommunicationRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [ovData, taskData, decData, commData] = await Promise.all([
        getProjectOverview(projectId).catch(() => null),
        getProjectTasks(projectId).catch(() => []),
        getProjectDecisions(projectId).catch(() => []),
        getProjectCommunications(projectId).catch(() => []),
      ]);
      setOverview(ovData);
      setTasks(taskData.slice(0, 5));
      setDecisions(decData.slice(0, 5));
      setCommunications(commData.slice(0, 4));
    } catch (err) {
      console.error('Failed to load overview data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [projectId]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* 10-Second Hero Understanding Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '24px 28px',
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%)',
          border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '24px',
          boxShadow: 'var(--shadow-md)',
        }}
      >
        <div style={{ maxWidth: '800px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <span className="badge badge-accent" style={{ fontSize: '11px', padding: '3px 8px' }}>
              Autonomous Communication Layer
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Project: <strong style={{ color: 'var(--text-primary)' }}>{projectId}</strong>
            </span>
          </div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px', letterSpacing: '-0.3px' }}>
            Project Intelligence Operating System
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            ArchScale continuously ingests unstructured team messages and meeting transcripts, automatically structuring
            actions, owners, deadlines, and approvals into verifiable project memory with zero hallucinations.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', flexShrink: 0 }}>
          <button
            onClick={onOpenAddModal}
            className="btn-primary"
            style={{ padding: '10px 16px', fontSize: '13px' }}
          >
            <Sparkles size={15} />
            <span>+ Ingest Communication</span>
          </button>
          <button
            onClick={() => onNavigate('/ask')}
            className="btn-secondary"
            style={{ padding: '10px 16px', fontSize: '13px' }}
          >
            <MessageSquare size={15} />
            <span>Ask ArchScale</span>
          </button>
        </div>
      </div>

      {/* 4 Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
        {/* Card 1: Total Memory */}
        <div
          className="metric-card"
          onClick={() => onNavigate('/memory')}
          style={{ cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Project Memory
            </span>
            <div style={{ padding: '6px', borderRadius: 'var(--radius-sm)', background: 'var(--accent-subtle)' }}>
              <Brain size={16} color="var(--accent-light)" />
            </div>
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
            {loading ? '...' : overview?.total_items ?? 0}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Indexed items in M8 memory
          </div>
        </div>

        {/* Card 2: Structured Tasks */}
        <div
          className="metric-card"
          onClick={() => onNavigate('/tasks')}
          style={{ cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Structured Tasks
            </span>
            <div style={{ padding: '6px', borderRadius: 'var(--radius-sm)', background: 'rgba(59, 130, 246, 0.12)' }}>
              <CheckSquare size={16} color="#3b82f6" />
            </div>
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
            {loading ? '...' : overview?.active_tasks_count ?? tasks.length}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Derived with owners & deadlines
          </div>
        </div>

        {/* Card 3: Decisions & Approvals */}
        <div
          className="metric-card"
          onClick={() => onNavigate('/decisions')}
          style={{ cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Decisions Captured
            </span>
            <div style={{ padding: '6px', borderRadius: 'var(--radius-sm)', background: 'rgba(16, 185, 129, 0.12)' }}>
              <Scale size={16} color="var(--status-approved)" />
            </div>
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
            {loading ? '...' : overview?.decisions_count ?? decisions.length}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Authoritative project agreements
          </div>
        </div>

        {/* Card 4: Stakeholders */}
        <div
          className="metric-card"
          onClick={() => onNavigate('/communications')}
          style={{ cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Stakeholders
            </span>
            <div style={{ padding: '6px', borderRadius: 'var(--radius-sm)', background: 'rgba(245, 158, 11, 0.12)' }}>
              <User size={16} color="#f59e0b" />
            </div>
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
            {loading ? '...' : overview?.unique_stakeholders?.length ?? 0}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Identified active participants
          </div>
        </div>
      </div>

      {/* Main Dashboard 2-Column Split */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px' }}>
        {/* Left Column: Recent Tasks & Communications */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Recent Extracted Tasks */}
          <div className="glass-panel" style={{ padding: '20px', borderRadius: 'var(--radius-lg)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckSquare size={16} color="var(--accent)" />
                <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Active Tasks (M7)
                </h2>
              </div>
              <button
                onClick={() => onNavigate('/tasks')}
                className="btn-ghost"
                style={{ fontSize: '12px', padding: '4px 8px' }}
              >
                <span>View All</span>
                <ArrowRight size={13} />
              </button>
            </div>

            {tasks.length === 0 ? (
              <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                No tasks indexed yet. Ingest a meeting or text snippet to generate tasks.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {tasks.map(t => (
                  <div
                    key={t.task_id}
                    style={{
                      background: 'var(--bg-surface)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      padding: '12px',
                      transition: 'border-color var(--transition-fast)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {t.title}
                      </span>
                      <span className={`badge badge-${t.status.toLowerCase()}`} style={{ fontSize: '10px' }}>
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
                            <User size={12} color="var(--text-muted)" />
                            <strong style={{ color: 'var(--text-secondary)' }}>{t.responsible_party}</strong>
                          </span>
                        )}
                        {t.deadline && (
                          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Calendar size={12} color="var(--text-muted)" />
                            <span>{t.deadline}</span>
                          </span>
                        )}
                      </div>

                      <button
                        onClick={() =>
                          onInspectProvenance({
                            item_type: 'task',
                            source_id: t.task_id,
                            communication_id: t.communication_id,
                            title: t.title,
                            content: t.description,
                            evidence: t.evidence,
                            score: 1.0,
                            retrieval_mode: 'deterministic',
                            metadata: {
                              responsible_party: t.responsible_party,
                              deadline: t.deadline,
                              status: t.status,
                            },
                          })
                        }
                        className="btn-ghost"
                        style={{ padding: '2px 8px', fontSize: '11px', gap: '4px' }}
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

          {/* Ingested Communications */}
          <div className="glass-panel" style={{ padding: '20px', borderRadius: 'var(--radius-lg)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Inbox size={16} color="var(--accent)" />
                <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Recent Ingested Streams (M1/M2)
                </h2>
              </div>
              <button
                onClick={() => onNavigate('/communications')}
                className="btn-ghost"
                style={{ fontSize: '12px', padding: '4px 8px' }}
              >
                <span>All Streams</span>
                <ArrowRight size={13} />
              </button>
            </div>

            {communications.length === 0 ? (
              <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                No communication records ingested yet for project {projectId}.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {communications.map(c => (
                  <div
                    key={c.communication_id}
                    onClick={() => onSelectCommunication(c)}
                    style={{
                      background: 'var(--bg-surface)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      padding: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <span className="badge badge-communication" style={{ fontSize: '10px' }}>
                        {c.source_type}
                      </span>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {c.communication_id.slice(0, 8)}...
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: '12px',
                        color: 'var(--text-secondary)',
                        lineHeight: 1.4,
                        overflow: 'hidden',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                      }}
                    >
                      {c.raw_content}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Grounded AI Query Card & Decisions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Grounded Agent Fast Query Box */}
          <div
            className="glass-panel"
            style={{
              padding: '20px',
              borderRadius: 'var(--radius-lg)',
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(15, 23, 42, 0.8) 100%)',
              border: '1px solid rgba(99, 102, 241, 0.25)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <div style={{ width: '22px', height: '22px', borderRadius: 'var(--radius-sm)', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Sparkles size={13} color="#fff" />
              </div>
              <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                Ask ArchScale (M9 Agent)
              </h2>
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '14px', lineHeight: 1.5 }}>
              Natural language queries grounded purely in retrieved M8 project memory. If no evidence exists, answers fall back safely with zero hallucinations.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '14px' }}>
              {[
                'What decisions were made about stone tiles?',
                'Who is responsible for MEP ducting?',
                'What tasks are scheduled for Friday?',
              ].map((sampleQuery, idx) => (
                <button
                  key={idx}
                  onClick={() => onNavigate(`/ask?q=${encodeURIComponent(sampleQuery)}`)}
                  className="btn-ghost"
                  style={{
                    justifyContent: 'flex-start',
                    fontSize: '12px',
                    padding: '8px 10px',
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    textAlign: 'left',
                    color: 'var(--text-secondary)',
                  }}
                >
                  <Search size={13} color="var(--accent)" />
                  <span>{sampleQuery}</span>
                </button>
              ))}
            </div>

            <button
              onClick={() => onNavigate('/ask')}
              className="btn-primary"
              style={{ width: '100%', fontSize: '12px', padding: '9px' }}
            >
              <span>Open Natural Language Intelligence</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Key Decisions & Approvals */}
          <div className="glass-panel" style={{ padding: '20px', borderRadius: 'var(--radius-lg)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Scale size={16} color="var(--accent)" />
                <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Decisions & Approvals (M6)
                </h2>
              </div>
              <button
                onClick={() => onNavigate('/decisions')}
                className="btn-ghost"
                style={{ fontSize: '12px', padding: '4px 8px' }}
              >
                <span>View All</span>
                <ArrowRight size={13} />
              </button>
            </div>

            {decisions.length === 0 ? (
              <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                No decisions captured yet.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {decisions.map(d => (
                  <div
                    key={d.decision_id}
                    style={{
                      background: 'var(--bg-surface)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      padding: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {d.subject || 'Decision'}
                      </span>
                      <span className={`badge badge-${d.status.toLowerCase()}`} style={{ fontSize: '10px' }}>
                        {d.status}
                      </span>
                    </div>

                    <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', lineHeight: 1.4 }}>
                      {d.description}
                    </p>

                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <button
                        onClick={() =>
                          onInspectProvenance({
                            item_type: d.item_type === 'approval' ? 'approval' : 'decision',
                            source_id: d.decision_id,
                            communication_id: d.communication_id,
                            title: d.subject ? `${d.subject}: ${d.description}` : d.description,
                            content: d.description,
                            evidence: d.evidence,
                            score: 1.0,
                            retrieval_mode: 'deterministic',
                            metadata: {
                              subject: d.subject,
                              status: d.status,
                            },
                          })
                        }
                        className="btn-ghost"
                        style={{ padding: '2px 6px', fontSize: '11px', gap: '4px' }}
                      >
                        <ShieldCheck size={11} color="var(--status-approved)" />
                        <span>Inspect Evidence</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
