import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AgentMatrix - 多智能体动态协同与国产算力优化平台',
  description: '基于多Agent协同 + 动态算力路由的AI系统',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
