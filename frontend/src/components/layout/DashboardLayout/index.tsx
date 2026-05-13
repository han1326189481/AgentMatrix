'use client';

import TopBar from './TopBar';
import SidePanel from './SidePanel';
import MainContent from './MainContent';
import RightPanel from './RightPanel';

export default function DashboardLayout() {
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)' }}>
      <TopBar />
      <div className="main-container" style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative', zIndex: 1 }}>
        <SidePanel />
        <MainContent />
        <RightPanel />
      </div>
    </div>
  );
}
