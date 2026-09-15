import React, { useState, useEffect } from 'react';
import {
  MessageSquare,
  Sparkles,
  Send,
  ShieldCheck,
  AlertTriangle,
  Database,
  ChevronDown,
  ChevronUp,
  Cpu,
  Layers,
  Search,
  ExternalLink,
  Info,
} from 'lucide-react';
import type { AgentResponse, MemorySearchResultItem } from '../types';
import { queryAgent } from '../api/agent';

interface AskAgentPageProps {
  projectId: string;
  initialQuery?: string;
  onInspectProvenance: (item: MemorySearchResultItem) => void;
}

const SUGGESTED_QUERIES = [
  'Who is responsible for MEP ducting?',
  'What decisions were approved for stone tiles?',
  'What tasks are scheduled for Friday?',
  'What was Elena confirmed for regarding chillers?',
  'Are there any structural load calculations pending?',
  'What was decided about acoustic glazing specs?',
];

export const AskAgentPage: React.FC<AskAgentPageProps> = ({
  projectId,
  initialQuery,
  onInspectProvenance,
}) => {
  const [queryInput, setQueryInput] = useState(initialQuery || '');
  const [useLlm, setUseLlm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<AgentResponse[]>([]);
  const [expandedTraceIndex, setExpandedTraceIndex] = useState<number | null>(null);

  useEffect(() => {
    if (initialQuery && initialQuery.trim()) {
      handleQuery(initialQuery.trim());
    }
  }, [initialQuery]);

  const handleQuery = async (queryText: string) => {
    if (!queryText.trim() || loading) return;
    setLoading(true);

    try {
      const resp = await queryAgent(projectId, queryText.trim(), useLlm);
      setHistory(prev => [resp, ...prev]);
      setQueryInput('');
    } catch (err: any) {
      console.error('Agent query failed:', err);
      // Fallback response on network error
      setHistory(prev => [
        {
          query: queryText,
          project_id: projectId,
          answer: `Error executing query against M9 agent: ${err.message || 'Network error'}`,
          confidence: 0,
          evidence_count: 0,
          evidence_items: [],
          is_grounded: false,
        },
        ...prev,
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleQuery(queryInput);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <div
            style={{
              width: '24px',
              height: '24px',
              borderRadius: 'var(--radius-sm)',
              background: 'linear-gradient(135deg, var(--accent) 0%, #4338ca 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Sparkles size={14} color="#fff" />
          </div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
            Ask ArchScale (M9 Grounded Agent)
          </h1>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          Autonomous project intelligence with strict zero-hallucination verification. Every statement is directly anchored to retrieved M8 evidence.
        </p>
      </div>

      {/* Query Formulation Input Box */}
      <div
        className="glass-panel"
        style={{
          padding: '20px',
          borderRadius: 'var(--radius-lg)',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
          boxShadow: 'var(--shadow-md)',
        }}
      >
        <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '10px' }}>
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '10px 16px',
            }}
          >
            <Search size={18} color="var(--accent)" />
            <input
              type="text"
              placeholder="Ask any question about tasks, owners, deadlines, or decisions..."
              value={queryInput}
              onChange={e => setQueryInput(e.target.value)}
              disabled={loading}
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                color: 'var(--text-primary)',
                fontSize: '14px',
                outline: 'none',
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading || !queryInput.trim()}
            className="btn-primary"
            style={{ padding: '0 20px', fontSize: '13px' }}
          >
            <Send size={15} />
            <span>{loading ? 'Synthesizing...' : 'Query'}</span>
          </button>
        </form>

        {/* Options & Settings */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          {/* Preset Queries */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Suggested:
            </span>
            {SUGGESTED_QUERIES.map((q, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleQuery(q)}
                disabled={loading}
                className="btn-ghost"
                style={{
                  fontSize: '11px',
                  padding: '3px 8px',
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-full)',
                  color: 'var(--text-secondary)',
                }}
              >
                {q}
              </button>
            ))}
          </div>

          {/* Toggle LLM Synthesis */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '12px', color: 'var(--text-secondary)' }}>
            <input
              type="checkbox"
              checked={useLlm}
              onChange={e => setUseLlm(e.target.checked)}
              disabled={loading}
            />
            <span>LLM Synthesis (default: deterministic evidence)</span>
          </label>
        </div>
      </div>

      {/* Answers Feed */}
      {loading && (
        <div
          className="glass-panel animate-fade-in"
          style={{
            padding: '32px',
            textAlign: 'center',
            borderRadius: 'var(--radius-lg)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <div className="animate-spin" style={{ color: 'var(--accent)' }}>
            <Sparkles size={24} />
          </div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Retrieving from M8 Memory & Synthesizing Grounded Answer...
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Checking task records, decision registers, and verbatim communication evidence
          </div>
        </div>
      )}

      {history.length === 0 && !loading && (
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
          <MessageSquare size={36} color="var(--text-muted)" />
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
            No queries asked yet
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '420px' }}>
            Select one of the suggested query chips above or type a question about project {projectId}.
          </p>
        </div>
      )}

      {history.map((item, idx) => (
        <div
          key={idx}
          className="glass-panel animate-fade-in"
          style={{
            padding: '24px',
            borderRadius: 'var(--radius-lg)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            border: item.is_grounded ? '1px solid rgba(16, 185, 129, 0.25)' : '1px solid var(--border-subtle)',
          }}
        >
          {/* Query Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Query:</span>
              <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                "{item.query}"
              </h2>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {item.is_grounded ? (
                <span className="badge badge-approved" style={{ fontSize: '11px', gap: '4px' }}>
                  <ShieldCheck size={13} />
                  <span>100% Grounded</span>
                </span>
              ) : (
                <span className="badge badge-review" style={{ fontSize: '11px', gap: '4px' }}>
                  <AlertTriangle size={13} />
                  <span>Ungrounded / No Evidence</span>
                </span>
              )}

              <span style={{ fontSize: '11px', color: 'var(--text-muted)', background: 'var(--bg-surface)', padding: '2px 8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                {item.evidence_count} evidence items
              </span>
            </div>
          </div>

          {/* Answer Box */}
          <div
            style={{
              background: item.is_grounded ? 'rgba(16, 185, 129, 0.04)' : 'rgba(239, 68, 68, 0.04)',
              border: item.is_grounded ? '1px solid rgba(16, 185, 129, 0.2)' : '1px solid rgba(239, 68, 68, 0.2)',
              borderRadius: 'var(--radius-md)',
              padding: '16px 20px',
              fontSize: '14px',
              color: 'var(--text-primary)',
              lineHeight: 1.6,
            }}
          >
            {item.answer}
          </div>

          {/* Reasoning Trace Accordion */}
          {item.reasoning_trace && item.reasoning_trace.length > 0 && (
            <div>
              <button
                type="button"
                onClick={() => setExpandedTraceIndex(expandedTraceIndex === idx ? null : idx)}
                className="btn-ghost"
                style={{
                  fontSize: '11px',
                  color: 'var(--text-muted)',
                  padding: '4px 8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Cpu size={13} />
                <span>{expandedTraceIndex === idx ? 'Hide Reasoning Trace' : 'View Reasoning Trace'}</span>
                {expandedTraceIndex === idx ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              </button>

              {expandedTraceIndex === idx && (
                <div
                  style={{
                    marginTop: '8px',
                    padding: '12px',
                    background: 'var(--bg-surface)',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                  }}
                >
                  {item.reasoning_trace.map((step, sIdx) => (
                    <div key={sIdx} style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      • {step}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Supporting Retrieved Evidence */}
          {item.evidence_items && item.evidence_items.length > 0 && (
            <div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.5px' }}>
                Supporting Evidence Records ({item.evidence_items.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {item.evidence_items.map((ev, evIdx) => (
                  <div
                    key={ev.source_id || evIdx}
                    style={{
                      background: 'var(--bg-surface)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '10px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className={`badge badge-${ev.item_type}`} style={{ fontSize: '10px' }}>
                          {ev.item_type}
                        </span>
                        <strong style={{ fontSize: '12px', color: 'var(--text-primary)' }}>
                          {ev.title}
                        </strong>
                      </div>
                      {ev.evidence && (
                        <div style={{ fontSize: '11px', fontStyle: 'italic', color: 'var(--text-secondary)' }}>
                          "{ev.evidence}"
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => onInspectProvenance(ev)}
                      className="btn-ghost"
                      style={{ fontSize: '11px', padding: '3px 8px', gap: '4px', flexShrink: 0 }}
                    >
                      <ShieldCheck size={12} color="var(--status-approved)" />
                      <span>Inspect Provenance</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
