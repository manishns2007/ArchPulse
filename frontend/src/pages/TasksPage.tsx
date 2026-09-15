import React, { useEffect, useState } from 'react';
import {
  CheckSquare,
  Search,
  User,
  Calendar,
  ShieldCheck,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import type { StructuredTask } from '../types';
import { getProjectTasks } from '../api/tasks';

interface TasksPageProps {
  projectId: string;
  onOpenAddModal: () => void;
  onInspectProvenance: (item: any) => void;
}

export const TasksPage: React.FC<TasksPageProps> = ({
  projectId,
  onOpenAddModal,
  onInspectProvenance,
}) => {
  const [tasks, setTasks] = useState<StructuredTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [ownerFilter, setOwnerFilter] = useState<string>('all');

  const loadTasks = async () => {
    setLoading(true);
    try {
      const data = await getProjectTasks(projectId, {
        status: statusFilter !== 'all' ? statusFilter : undefined,
      });
      setTasks(data);
    } catch (err) {
      console.error('Failed to load tasks:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
  }, [projectId, statusFilter]);

  // Extract unique responsible parties
  const uniqueOwners = Array.from(
    new Set(tasks.map(t => t.responsible_party).filter(Boolean) as string[])
  );

  const filteredTasks = tasks.filter(t => {
    const matchesSearch =
      !searchTerm ||
      t.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (t.responsible_party && t.responsible_party.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesOwner = ownerFilter === 'all' || t.responsible_party === ownerFilter;
    return matchesSearch && matchesOwner;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
            Structured Tasks (M7)
          </h1>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Authoritative, extracted tasks with explicit ownership, deadlines, and verbatim communication provenance.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={loadTasks}
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
            placeholder="Search task title, description, or owner..."
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
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="blocked">Blocked</option>
          </select>
        </div>

        {/* Owner Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Owner:</span>
          <select
            value={ownerFilter}
            onChange={e => setOwnerFilter(e.target.value)}
            style={{
              background: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '4px 8px',
              fontSize: '12px',
            }}
          >
            <option value="all">All Owners ({uniqueOwners.length})</option>
            {uniqueOwners.map(o => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Task List */}
      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
          Loading structured tasks...
        </div>
      ) : filteredTasks.length === 0 ? (
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
          <CheckSquare size={36} color="var(--text-muted)" />
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
            No structured tasks found
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '420px' }}>
            {searchTerm || statusFilter !== 'all' || ownerFilter !== 'all'
              ? 'No tasks match your selected filters. Try clearing your search or status filters.'
              : `Project "${projectId}" has no structured tasks yet. Ingest an action item or meeting summary to structure tasks automatically.`}
          </p>
          <button onClick={onOpenAddModal} className="btn-primary" style={{ marginTop: '8px', fontSize: '12px' }}>
            <Sparkles size={14} />
            <span>Ingest First Communication</span>
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredTasks.map(task => (
            <div
              key={task.task_id}
              className="glass-panel"
              style={{
                padding: '16px 20px',
                borderRadius: 'var(--radius-md)',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}
            >
              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {task.title}
                  </h3>
                  <span className={`badge badge-${task.status.toLowerCase()}`} style={{ fontSize: '10px' }}>
                    {task.status}
                  </span>
                  {task.priority && (
                    <span
                      style={{
                        fontSize: '10px',
                        padding: '2px 6px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--bg-surface)',
                        color: 'var(--text-secondary)',
                        border: '1px solid var(--border-subtle)',
                        textTransform: 'capitalize',
                      }}
                    >
                      {task.priority} Priority
                    </span>
                  )}
                </div>

                <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {task.task_id}
                </span>
              </div>

              {/* Description */}
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {task.description}
              </p>

              {/* Verbatim Evidence Snippet if present */}
              {task.evidence && (
                <div
                  style={{
                    background: 'var(--bg-surface)',
                    borderLeft: '2px solid var(--accent)',
                    padding: '8px 12px',
                    borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
                    fontSize: '12px',
                    fontStyle: 'italic',
                    color: 'var(--text-secondary)',
                  }}
                >
                  "{task.evidence}"
                </div>
              )}

              {/* Metadata Footer */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingTop: '8px',
                  borderTop: '1px solid var(--border-subtle)',
                  fontSize: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  {task.responsible_party && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-secondary)' }}>
                      <User size={13} color="var(--accent)" />
                      <span>Owner: <strong style={{ color: 'var(--text-primary)' }}>{task.responsible_party}</strong></span>
                    </span>
                  )}

                  {task.deadline && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-secondary)' }}>
                      <Calendar size={13} color="#f59e0b" />
                      <span>Deadline: <strong style={{ color: 'var(--text-primary)' }}>{task.deadline}</strong></span>
                    </span>
                  )}
                </div>

                <button
                  onClick={() =>
                    onInspectProvenance({
                      item_type: 'task',
                      source_id: task.task_id,
                      communication_id: task.communication_id,
                      title: task.title,
                      content: task.description,
                      evidence: task.evidence,
                      score: 1.0,
                      retrieval_mode: 'deterministic',
                      metadata: {
                        responsible_party: task.responsible_party,
                        responsibility_type: task.responsibility_type,
                        deadline: task.deadline,
                        normalized_deadline: task.normalized_deadline,
                        status: task.status,
                        priority: task.priority,
                      },
                    })
                  }
                  className="btn-ghost"
                  style={{ fontSize: '11px', padding: '4px 8px', gap: '5px' }}
                >
                  <ShieldCheck size={13} color="var(--status-approved)" />
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
