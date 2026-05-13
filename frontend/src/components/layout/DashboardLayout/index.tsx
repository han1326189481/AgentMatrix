'use client';

import TopBar from './TopBar';
import MainContent from './MainContent';

export default function DashboardLayout() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col">
      <TopBar />
      <MainContent />
    </div>
  );
}
