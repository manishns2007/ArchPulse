import React, { useState } from 'react';
import { ChevronDown, FolderGit2, Check, Plus } from 'lucide-react';

interface ProjectSelectorProps {
  currentProject: string;
  onSelectProject: (projectId: string) => void;
}

export const ProjectSelector: React.FC<ProjectSelectorProps> = ({ currentProject, onSelectProject }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [newProjectId, setNewProjectId] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  // Available known projects
  const [projects, setProjects] = useState<string[]>(['villa-live-proj', 'archscale-demo', 'metro-station-proj']);

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (newProjectId.trim()) {
      const clean = newProjectId.trim();
      if (!projects.includes(clean)) {
        setProjects([...projects, clean]);
      }
      onSelectProject(clean);
      setNewProjectId('');
      setIsAdding(false);
      setIsOpen(false);
    }
  };

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 12px',
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--text-primary)',
          fontSize: '13px',
          fontWeight: 600,
        }}
      >
        <FolderGit2 size={15} color="var(--accent)" />
        <span>{currentProject}</span>
        <ChevronDown size={14} color="var(--text-muted)" />
      </button>

      {isOpen && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 100 }} onClick={() => setIsOpen(false)} />
          <div
            className="glass-panel"
            style={{
              position: 'absolute',
              top: 'calc(100% + 6px)',
              left: 0,
              width: '240px',
              padding: '6px',
              zIndex: 101,
              boxShadow: 'var(--shadow-lg)',
              background: 'var(--bg-card)',
            }}
          >
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', padding: '6px 8px', letterSpacing: '0.5px' }}>
              Active Project
            </div>
            {projects.map(p => (
              <div
                key={p}
                onClick={() => {
                  onSelectProject(p);
                  setIsOpen(false);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '13px',
                  cursor: 'pointer',
                  color: p === currentProject ? 'var(--text-primary)' : 'var(--text-secondary)',
                  background: p === currentProject ? 'var(--bg-surface-hover)' : 'transparent',
                }}
              >
                <span>{p}</span>
                {p === currentProject && <Check size={14} color="var(--accent)" />}
              </div>
            ))}

            <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '6px 0', paddingTop: '6px' }}>
              {isAdding ? (
                <form onSubmit={handleAdd} style={{ display: 'flex', gap: '4px', padding: '4px' }}>
                  <input
                    type="text"
                    placeholder="project-id..."
                    value={newProjectId}
                    onChange={e => setNewProjectId(e.target.value)}
                    autoFocus
                    style={{ flex: 1, padding: '4px 8px', fontSize: '12px' }}
                  />
                  <button type="submit" className="btn-primary" style={{ padding: '4px 8px', fontSize: '11px' }}>
                    Set
                  </button>
                </form>
              ) : (
                <button
                  onClick={() => setIsAdding(true)}
                  className="btn-ghost"
                  style={{ width: '100%', justifyContent: 'flex-start', fontSize: '12px', padding: '6px 8px' }}
                >
                  <Plus size={13} />
                  <span>Switch custom project...</span>
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
