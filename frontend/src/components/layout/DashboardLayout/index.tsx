import TopBar from './TopBar';
import SidePanel from './SidePanel';
import MainContent from './MainContent';

export default function DashboardLayout() {
  return (
    <div className="min-h-screen bg-dark-900 flex flex-col">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <SidePanel />
        <MainContent />
      </div>
    </div>
  );
}