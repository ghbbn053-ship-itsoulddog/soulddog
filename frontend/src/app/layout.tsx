import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '校园AI助手',
  description: '校园AI助手 - 智能问答、教务查询',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
