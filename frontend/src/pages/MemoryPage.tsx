import React, { useEffect, useState } from 'react';
import {
  Brain,
  Search,
  ShieldCheck,
  Database,
  Sparkles,
} from 'lucide-react';
import type { MemorySearchResultItem } from '../types';
import { searchProjectMemory } from '../api/memory';

interface MemoryPageProps {
  projectId: string;
  onOpenAddModal: () => void;
  onInspectProvenance: (item: MemorySearchResultItem) => void;
}

const QUICK_SEARCH_CHIPS = ['stone tiles', 'MEP ducting', 'September', 'inspection', 'David', 'chillers'];

export const MemoryPage: React.FC<MemoryPageProps> = ({
  projectId,
  onOpenAddModal,
  onInspectProvenance,
}) => {
  const [query, setQuery] = useState('');
  const [itemType, setItemType] = useState<string>('all');
  const [results, setResults] = useState<MemorySearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);

  const executeSearch = async (targetQuery = query, targetType = itemType) => {
    setLoading(true);
    try {
      const res = await searchProjectMemory({
        project_id: projectId,
        query: targetQuery,
        item_type: targetType,
        limit: 50,
      });
      setResults(res.results || []);
    } catch (err) {
      console.error('Failed to search memory:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    executeSearch();
  }, [projectId, itemType]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch();
  };

  const handleChipClick = (chip: string) => {
    setQuery(chip);
    executeSearch(chip, itemType);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
            Project Memory & Search (M8)
          </h1>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Unified retrieval layer indexing communication records, structured tasks, and authoritative decisions.
          </p>
        </div>

        <button
          onClick={onOpenAddModal}
          className="btn-primary"
          style={{ fontSize: '12px', padding: '8px 14px' }}
        >
          <Sparkles size={14} />
          <span>+ Ingest Communication</span>
        </button>
      </div>

      {/* Interactive Search Bar & Chips */}
      <div className="glass-panel" style={{ padding: '20px', borderRadius: 'var(--radius-lg)', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '10px' }}>
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '8px 14px',
            }}
          >
            <Search size={16} color="var(--text-muted)" />
            <input
              type="text"
              placeholder="Search anything in project memory (e.g. 'ducts', 'inspection', 'tiles')..."
              value={query}
              onChange={e => setQuery(e.target.value)}
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

          {/* Type Filter */}
          <select
            value={itemType}
            onChange={e => setItemType(e.target.value)}
            style={{
              background: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '0 12px',
              fontSize: '13px',
              outline: 'none',
            }}
          >
            <option value="all">All Item Types</option>
            <option value="task">Tasks</option>
            <option value="decision">Decisions</option>
            <option value="approval">Approvals</option>
            <option value="communication">Communications</option>
          </select>

          <button type="submit" className="btn-primary" style={{ padding: '0 18px', fontSize: '13px' }}>
            Search
          </button>
        </form>

        {/* Quick Suggestion Chips */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Quick Topics:
          </span>
          {QUICK_SEARCH_CHIPS.map(chip => (
            <button
              key={chip}
              onClick={() => handleChipClick(chip)}
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
              #{chip}
            </button>
          ))}
        </div>
      </div>

      {/* Search Meta Status */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 4px' }}>
        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Database size={14} color="var(--accent)" />
          <span>
            Retrieved <strong style={{ color: 'var(--text-primary)' }}>{results.length}</strong> memory records
            {query && (
              <>
                {' '}for "<span style={{ color: 'var(--accent-light)' }}>{query}</span>"
              </>
            )}
          </span>
        </div>
      </div>

      {/* Results Feed */}
      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
          Querying M8 Project Memory Index...
        </div>
      ) : results.length === 0 ? (
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
          <Brain size={36} color="var(--text-muted)" />
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
            No memory records found
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '400px' }}>
            {query
              ? `No memory items matched "${query}". Try searching for broader terms or clearing filters.`
              : `No memory indexed yet for project "${projectId}". Ingest your first communication to build memory.`}
          </p>
          <button onClick={onOpenAddModal} className="btn-primary" style={{ marginTop: '8px', fontSize: '12px' }}>
            <Sparkles size={14} />
            <span>+ Ingest Communication</span>
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {results.map((item, idx) => (
            <div
              key={item.source_id || idx}
              className="glass-panel"
              style={{
                padding: '16px 20px',
                borderRadius: 'var(--radius-md)',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                transition: 'border-color var(--transition-fast)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className={`badge badge-${item.item_type}`}>
                    {item.item_type}
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {item.source_id}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                  <span>Score: {item.score?.toFixed(1) ?? '1.0'}</span>
                  <span style={{ padding: '2px 6px', background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    {item.retrieval_mode || 'retrieved'}
                  </span>
                </div>
              </div>

              <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                {item.title}
              </h3>

              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {item.content}
              </p>

              {item.evidence && (
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
                  "{item.evidence}"
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '6px' }}>
                <button
                  onClick={() => onInspectProvenance(item)}
                  className="btn-ghost"
                  style={{ fontSize: '11px', padding: '4px 8px', gap: '5px' }}
                >
                  <ShieldCheck size={13} color="var(--status-approved)" />
                  <span>Inspect Provenance Record</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
