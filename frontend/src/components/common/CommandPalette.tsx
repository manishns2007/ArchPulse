import React, { useState, useEffect } from 'react';
import { Search, LayoutDashboard, Inbox, CheckSquare, Scale, Brain, MessageSquare, ArrowRight, X } from 'lucide-react';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (route: string) => void;
  onSelectQuery?: (query: string) => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onNavigate,
  onSelectQuery,
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (isOpen) {
          onClose();
        } else {
          // Open
          setSearchTerm('');
        }
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const quickNav = [
    { title: 'Project Overview', route: '/', icon: LayoutDashboard, desc: 'View intelligence metrics and recent activity' },
    { title: 'Communications Inbox', route: '/communications', icon: Inbox, desc: 'Inspect raw conversations and M1–M8 pipeline' },
    { title: 'Tasks Management', route: '/tasks', icon: CheckSquare, desc: 'Track structured tasks, assignees, and deadlines' },
    { title: 'Decisions Log', route: '/decisions', icon: Scale, desc: 'Explore approved conclusions and formal agreements' },
    { title: 'Project Memory', route: '/memory', icon: Brain, desc: 'Search indexed project intelligence' },
    { title: 'Ask ArchScale Agent', route: '/ask', icon: MessageSquare, desc: 'Query project memory with grounded natural language' },
  ];

  const suggestedQueries = [
    'What did the client approve?',
    'What does the architect need to do?',
    'What is due this week?',
    'What tasks are assigned to Britto Sir?',
    'Show me decisions about the kitchen.',
  ];

  const filteredNav = quickNav.filter(item =>
    item.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.desc.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredQueries = suggestedQueries.filter(q =>
    q.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="glass-panel"
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '560px',
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
          border: '1px solid var(--border-hover)',
        }}
      >
        {/* Search Input */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '14px 18px', borderBottom: '1px solid var(--border-subtle)' }}>
          <Search size={18} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Type a command or ask a question... (ESC to close)"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            autoFocus
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              padding: 0,
              fontSize: '15px',
              color: 'var(--text-primary)',
              boxShadow: 'none',
            }}
          />
          <button onClick={onClose} className="btn-ghost" style={{ padding: '4px' }}>
            <X size={16} />
          </button>
        </div>

        {/* List Content */}
        <div style={{ maxHeight: '360px', overflowY: 'auto', padding: '10px' }}>
          {/* Navigation Section */}
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', padding: '6px 10px', letterSpacing: '0.5px' }}>
            Pages & Tools
          </div>
          {filteredNav.map(item => {
            const Icon = item.icon;
            return (
              <div
                key={item.route}
                onClick={() => {
                  onNavigate(item.route);
                  onClose();
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                  transition: 'background var(--transition-fast)',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-surface-hover)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Icon size={16} color="var(--accent)" />
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>{item.title}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{item.desc}</div>
                  </div>
                </div>
                <ArrowRight size={14} color="var(--text-muted)" />
              </div>
            );
          })}

          {/* Suggested Queries Section */}
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', padding: '14px 10px 6px', letterSpacing: '0.5px' }}>
            Natural Language Queries
          </div>
          {filteredQueries.map(q => (
            <div
              key={q}
              onClick={() => {
                if (onSelectQuery) {
                  onSelectQuery(q);
                } else {
                  onNavigate('/ask');
                }
                onClose();
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                fontSize: '13px',
                color: 'var(--text-secondary)',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'var(--bg-surface-hover)';
                e.currentTarget.style.color = 'var(--text-primary)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = 'var(--text-secondary)';
              }}
            >
              <MessageSquare size={14} color="var(--accent-light)" />
              <span>{q}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
