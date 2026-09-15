import React from 'react';
import { X, ExternalLink, ShieldCheck, Database, FileText, Calendar, User, Tag } from 'lucide-react';
import type { MemorySearchResultItem } from '../../types';

interface ProvenanceDrawerProps {
  item: MemorySearchResultItem | null;
  onClose: () => void;
}

export const ProvenanceDrawer: React.FC<ProvenanceDrawerProps> = ({ item, onClose }) => {
  if (!item) return null;

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-content" onClick={(e) => e.stopPropagation()} style={{ padding: '24px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className={`badge badge-${item.item_type}`}>{item.item_type}</span>
            <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Provenance Record</span>
          </div>
          <button onClick={onClose} className="btn-ghost" aria-label="Close drawer">
            <X size={18} />
          </button>
        </div>

        {/* Title */}
        <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px', lineHeight: 1.4 }}>
          {item.title}
        </h2>

        {/* Content */}
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '20px', lineHeight: 1.6 }}>
          {item.content}
        </p>

        {/* Verbatim Evidence Section */}
        {item.evidence && (
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-md)', padding: '14px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--status-approved)', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.5px' }}>
              <ShieldCheck size={14} />
              <span>Verbatim Source Evidence</span>
            </div>
            <blockquote style={{ fontStyle: 'italic', color: 'var(--text-primary)', fontSize: '13px', lineHeight: 1.5, borderLeft: '2px solid var(--accent)', paddingLeft: '10px' }}>
              "{item.evidence}"
            </blockquote>
          </div>
        )}

        {/* Provenance Metadata Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '20px' }}>
          <div style={{ background: 'var(--bg-surface)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Source ID</div>
            <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', wordBreak: 'break-all' }}>
              {item.source_id}
            </div>
          </div>

          <div style={{ background: 'var(--bg-surface)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Communication ID</div>
            <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--accent-light)', wordBreak: 'break-all' }}>
              {item.communication_id}
            </div>
          </div>

          <div style={{ background: 'var(--bg-surface)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Retrieval Mode</div>
            <div style={{ fontSize: '12px', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Database size={13} color="var(--accent)" />
              {item.retrieval_mode}
            </div>
          </div>

          <div style={{ background: 'var(--bg-surface)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Relevance Score</div>
            <div style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: 600 }}>
              {item.score.toFixed(1)}
            </div>
          </div>
        </div>

        {/* Structured Attributes */}
        {Object.keys(item.metadata || {}).length > 0 && (
          <div style={{ marginTop: '20px' }}>
            <h3 style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.5px', marginBottom: '10px' }}>
              Extracted Metadata
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {Object.entries(item.metadata).map(([key, val]) => {
                if (val === null || val === undefined || (Array.isArray(val) && val.length === 0)) return null;
                return (
                  <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}>
                    <span style={{ color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{key.replace(/_/g, ' ')}</span>
                    <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                      {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
