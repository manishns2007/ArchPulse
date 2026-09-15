import React from 'react';
import {
  LayoutDashboard,
  Inbox,
  CheckSquare,
  Scale,
  Brain,
  MessageSquare,
  Sparkles,
  Layers,
  Activity,
} from 'lucide-react';

interface SidebarProps {
  currentRoute: string;
  onNavigate: (route: string) => void;
  onOpenAddModal: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentRoute, onNavigate, onOpenAddModal }) => {
  const navItems = [
    { label: 'Overview', route: '/', icon: LayoutDashboard },
    { label: 'Communications', route: '/communications', icon: Inbox },
    { label: 'Tasks', route: '/tasks', icon: CheckSquare },
    { label: 'Decisions', route: '/decisions', icon: Scale },
    { label: 'Project Memory', route: '/memory', icon: Brain },
    { label: 'Ask ArchScale', route: '/ask', icon: MessageSquare, highlight: true },
  ];

  return (
    <aside
      style={{
        width: '240px',
        background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '20px 16px',
        flexShrink: 0,
        minHeight: '100vh',
      }}
    >
      <div>
        {/* Brand Header */}
        <div
          onClick={() => onNavigate('/')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            cursor: 'pointer',
            padding: '4px 8px 24px',
          }}
        >
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, var(--accent) 0%, #4338ca 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: 'var(--shadow-glow)',
            }}
          >
            <Layers size={18} color="#fff" />
          </div>
          <div>
            <div style={{ fontSize: '15px', fontWeight: 700, letterSpacing: '0.5px', color: 'var(--text-primary)' }}>
              ARCHSCALE
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
              Project Intelligence
            </div>
          </div>
        </div>

        {/* Action Button: Add Communication */}
        <button
          onClick={onOpenAddModal}
          className="btn-primary"
          style={{
            width: '100%',
            marginBottom: '20px',
            padding: '9px 12px',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-sm)',
            fontSize: '12px',
          }}
        >
          <Sparkles size={14} />
          <span>+ Add Communication</span>
        </button>

        {/* Navigation Section */}
        <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', padding: '0 8px 8px', letterSpacing: '0.6px' }}>
          Platform
        </div>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentRoute === item.route;
            return (
              <button
                key={item.route}
                onClick={() => onNavigate(item.route)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '13px',
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  background: isActive ? 'var(--bg-surface)' : 'transparent',
                  border: isActive ? '1px solid var(--border-subtle)' : '1px solid transparent',
                  transition: 'all var(--transition-fast)',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'var(--bg-card)';
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'transparent';
                }}
              >
                <Icon size={16} color={isActive ? 'var(--accent)' : 'var(--text-muted)'} />
                <span>{item.label}</span>
                {item.highlight && (
                  <span
                    style={{
                      marginLeft: 'auto',
                      fontSize: '9px',
                      background: 'var(--accent-subtle)',
                      color: 'var(--accent-light)',
                      border: '1px solid rgba(99,102,241,0.3)',
                      padding: '1px 5px',
                      borderRadius: 'var(--radius-full)',
                      fontWeight: 700,
                    }}
                  >
                    AI
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer System Status */}
      <div
        style={{
          borderTop: '1px solid var(--border-subtle)',
          paddingTop: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--status-approved)' }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--status-approved)', display: 'inline-block' }} className="pulse-live" />
          <span style={{ fontWeight: 600 }}>System operational</span>
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Activity size={12} />
          <span>M1–M9 connected</span>
        </div>
      </div>
    </aside>
  );
};
