'use client';

import { useState, useCallback } from 'react';
import Dashboard from '@/components/layout/DashboardLayout';
import SplashScreen from '@/components/layout/SplashScreen';
import { ThemeProvider } from '@/components/layout/DashboardLayout/ThemeProvider';

export default function Home() {
  const [showSplash, setShowSplash] = useState(true);

  const handleReady = useCallback(() => {
    setShowSplash(false);
  }, []);

  return (
    <ThemeProvider>
      {showSplash && <SplashScreen onReady={handleReady} />}
      <Dashboard />
    </ThemeProvider>
  );
}