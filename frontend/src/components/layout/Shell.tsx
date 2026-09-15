import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { CommandPalette } from '../common/CommandPalette';
import { ProvenanceDrawer } from '../common/ProvenanceDrawer';
import type { MemorySearchResultItem } from '../../types';

interface ShellProps {
  currentRoute: string;
  onNavigate: (route: string) => void;
  currentProject: string;
  onSelectProject: (projectId: string) => void;
  onOpenAddModal: () => void;
  provenanceItem: MemorySearchResultItem | null;
  onCloseProvenance: () => void;
  onSelectQuery?: (query: string) => void;
  children: React.ReactNode;
}

export const Shell: React.FC<ShellProps> = ({
  currentRoute,
  onNavigate,
  currentProject,
  onSelectProject,
  onOpenAddModal,
  provenanceItem,
  onCloseProvenance,
  onSelectQuery,
  children,
}) => {
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: 'var(--bg-app)' }}>
      {/* Persistent Left Sidebar */}
      <Sidebar
        currentRoute={currentRoute}
        onNavigate={onNavigate}
        onOpenAddModal={onOpenAddModal}
      />

      {/* Main Workspace Viewport */}
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, overflowX: 'hidden' }}>
        <Topbar
          currentProject={currentProject}
          onSelectProject={onSelectProject}
          onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
          onOpenAddModal={onOpenAddModal}
        />

        <main style={{ flex: 1, overflowY: 'auto', padding: '24px 32px' }}>
          {children}
        </main>
      </div>

      {/* Global Command Palette */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onNavigate={(route) => {
          setIsCommandPaletteOpen(false);
          onNavigate(route);
        }}
        onSelectQuery={(query) => {
          setIsCommandPaletteOpen(false);
          if (onSelectQuery) {
            onSelectQuery(query);
          } else {
            onNavigate('/ask');
          }
        }}
      />

      {/* Global Provenance Drawer */}
      <ProvenanceDrawer
        item={provenanceItem}
        onClose={onCloseProvenance}
      />
    </div>
  );
};
