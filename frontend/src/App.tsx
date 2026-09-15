import { useState } from 'react';
import { Shell } from './components/layout/Shell';
import { OverviewPage } from './pages/OverviewPage';
import { CommunicationsPage } from './pages/CommunicationsPage';
import { TasksPage } from './pages/TasksPage';
import { DecisionsPage } from './pages/DecisionsPage';
import { MemoryPage } from './pages/MemoryPage';
import { AskAgentPage } from './pages/AskAgentPage';
import { AddCommunicationModal } from './components/communication/AddCommunicationModal';
import { CommunicationDrawer } from './components/communication/CommunicationDrawer';
import type { CommunicationRecord, MemorySearchResultItem } from './types';
import { getCommunicationById } from './api/ingestion';

export function App() {
  const [currentRoute, setCurrentRoute] = useState<string>('/');
  const [currentProject, setCurrentProject] = useState<string>('villa-live-proj');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [activeCommunication, setActiveCommunication] = useState<CommunicationRecord | null>(null);
  const [provenanceItem, setProvenanceItem] = useState<MemorySearchResultItem | null>(null);
  const [agentInitialQuery, setAgentInitialQuery] = useState<string>('');

  // Handle URL hash or route navigation
  const navigateTo = (route: string) => {
    if (route.startsWith('/ask?q=')) {
      const q = decodeURIComponent(route.split('/ask?q=')[1] || '');
      setAgentInitialQuery(q);
      setCurrentRoute('/ask');
    } else {
      if (route !== '/ask') {
        setAgentInitialQuery('');
      }
      setCurrentRoute(route);
    }
  };

  const handleSelectQueryFromPalette = (query: string) => {
    setAgentInitialQuery(query);
    setCurrentRoute('/ask');
  };

  const handleAddSuccess = async (commId: string) => {
    try {
      const comm = await getCommunicationById(commId);
      setActiveCommunication(comm);
      setCurrentRoute('/communications');
    } catch {
      setCurrentRoute('/communications');
    }
  };

  const renderActivePage = () => {
    switch (currentRoute) {
      case '/':
        return (
          <OverviewPage
            projectId={currentProject}
            onNavigate={navigateTo}
            onOpenAddModal={() => setIsAddModalOpen(true)}
            onInspectProvenance={(item) => setProvenanceItem(item)}
            onSelectCommunication={(comm) => setActiveCommunication(comm)}
          />
        );
      case '/communications':
        return (
          <CommunicationsPage
            projectId={currentProject}
            onOpenAddModal={() => setIsAddModalOpen(true)}
            onSelectCommunication={(comm) => setActiveCommunication(comm)}
            onInspectProvenance={(item) => setProvenanceItem(item)}
          />
        );
      case '/tasks':
        return (
          <TasksPage
            projectId={currentProject}
            onOpenAddModal={() => setIsAddModalOpen(true)}
            onInspectProvenance={(item) => setProvenanceItem(item)}
          />
        );
      case '/decisions':
        return (
          <DecisionsPage
            projectId={currentProject}
            onOpenAddModal={() => setIsAddModalOpen(true)}
            onInspectProvenance={(item) => setProvenanceItem(item)}
          />
        );
      case '/memory':
        return (
          <MemoryPage
            projectId={currentProject}
            onOpenAddModal={() => setIsAddModalOpen(true)}
            onInspectProvenance={(item) => setProvenanceItem(item)}
          />
        );
      case '/ask':
        return (
          <AskAgentPage
            projectId={currentProject}
            initialQuery={agentInitialQuery}
            onInspectProvenance={(item) => setProvenanceItem(item)}
          />
        );
      default:
        return (
          <OverviewPage
            projectId={currentProject}
            onNavigate={navigateTo}
            onOpenAddModal={() => setIsAddModalOpen(true)}
            onInspectProvenance={(item) => setProvenanceItem(item)}
            onSelectCommunication={(comm) => setActiveCommunication(comm)}
          />
        );
    }
  };

  return (
    <Shell
      currentRoute={currentRoute}
      onNavigate={navigateTo}
      currentProject={currentProject}
      onSelectProject={(newProj) => setCurrentProject(newProj)}
      onOpenAddModal={() => setIsAddModalOpen(true)}
      provenanceItem={provenanceItem}
      onCloseProvenance={() => setProvenanceItem(null)}
      onSelectQuery={handleSelectQueryFromPalette}
    >
      {renderActivePage()}

      {/* Add Communication Pipeline Runner Modal */}
      <AddCommunicationModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        projectId={currentProject}
        onSuccess={handleAddSuccess}
      />

      {/* Detailed Communication & Pipeline Breakdown Drawer */}
      <CommunicationDrawer
        communication={activeCommunication}
        onClose={() => setActiveCommunication(null)}
        onInspectProvenance={(item) => setProvenanceItem(item)}
      />
    </Shell>
  );
}

export default App;
