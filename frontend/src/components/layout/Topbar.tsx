import React, { useEffect, useState } from 'react';
import { Search, Server, Sparkles } from 'lucide-react';
import { ProjectSelector } from './ProjectSelector';
import { request } from '../../api/client';

interface TopbarProps {
  currentProject: string;
  onSelectProject: (projectId: string) => void;
  onOpenCommandPalette: () => void;
  onOpenAddModal: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({
  currentProject,
  onSelectProject,
  onOpenCommandPalette,
  onOpenAddModal,
}) => {
  const [backendStatus, setBackendStatus] = useState<'online' | 'offline' | 'checking'>('checking');

  useEffect(() => {
    let mounted = true;
    const checkHealth = async () => {
      try {
        await request<{ status: string }>('/health');
        if (mounted) setBackendStatus('online');
      } catch {
        if (mounted) setBackendStatus('offline');
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header
      style={{
        height: '56px',
        borderBottom: '1px solid var(--border-subtle)',
        background: 'var(--bg-card)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      {/* Left: Project Selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <ProjectSelector currentProject={currentProject} onSelectProject={onSelectProject} />

        <div
          style={{
            height: '18px',
            width: '1px',
            background: 'var(--border-subtle)',
          }}
        />

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
          <span style={{ color: 'var(--text-muted)' }}>Pipeline:</span>
          <span className="badge badge-accent" style={{ fontSize: '11px', padding: '2px 8px' }}>
            M1 Ingest → M8 Memory → M9 Query
          </span>
        </div>
      </div>

      {/* Center: Command Palette Trigger */}
      <button
        onClick={onOpenCommandPalette}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '6px 14px',
          color: 'var(--text-muted)',
          fontSize: '13px',
          width: '320px',
          cursor: 'pointer',
          transition: 'border-color var(--transition-fast)',
        }}
        onMouseEnter={e => {
          e.currentTarget.style.borderColor = 'var(--border-default)';
        }}
        onMouseLeave={e => {
          e.currentTarget.style.borderColor = 'var(--border-subtle)';
        }}
      >
        <Search size={14} />
        <span style={{ flex: 1, textAlign: 'left' }}>Search memory or type a command...</span>
        <kbd
          style={{
            fontSize: '11px',
            background: 'var(--bg-card)',
            padding: '2px 6px',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-secondary)',
          }}
        >
          Ctrl K
        </kbd>
      </button>

      {/* Right: Quick Ingest + Live Backend Health */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <button
          onClick={onOpenAddModal}
          className="btn-primary"
          style={{
            padding: '6px 12px',
            fontSize: '12px',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <Sparkles size={13} />
          <span>Ingest Feed</span>
        </button>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '5px 10px',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            fontSize: '12px',
          }}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background:
                backendStatus === 'online'
                  ? 'var(--status-approved)'
                  : backendStatus === 'offline'
                  ? 'var(--status-rejected)'
                  : 'var(--status-review)',
            }}
            className={backendStatus === 'online' ? 'pulse-live' : ''}
          />
          <Server size={13} color="var(--text-muted)" />
          <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
            {backendStatus === 'online' ? 'FastAPI :8000' : backendStatus === 'offline' ? 'Backend Offline' : 'Connecting...'}
          </span>
        </div>
      </div>
    </header>
  );
};
