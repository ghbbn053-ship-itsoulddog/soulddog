import type { Metadata } from 'next';
import { Inspector } from 'react-dev-inspector';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: '教务系统 AI 助手',
    template: '%s | 教务系统 AI 助手',
  },
  description:
    '教务系统 AI 助手 - 智能问答、信息查询、数据分析',
  keywords: [
    '教务系统',
    'AI 助手',
    '智能问答',
    '信息查询',
    '数据分析',
  ],
  generator: '教务系统 AI 助手',
  openGraph: {
    title: '教务系统 AI 助手',
    description: '教务系统 AI 助手 - 智能问答、信息查询、数据分析',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const isDev = process.env.COZE_PROJECT_ENV === 'DEV';

  return (
    <html lang="en">
      <body className={`antialiased`}>
        {isDev && <Inspector />}
        {children}
      </body>
    </html>
  );
}
