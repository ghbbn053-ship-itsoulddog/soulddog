import path from 'node:path';
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  /* config options here */
  // 开发模式不使用静态导出，以支持 rewrites 反向代理
  // output: 'export',
  turbopack: {
    root: path.join(__dirname, '..'),
  },
  allowedDevOrigins: [
    '*.dev.coze.site',
    'http://localhost:5000',
    'http://127.0.0.1:5000',
    'http://192.168.88.100:5000',
    'http://192.168.88.1:5000',
    'localhost',
    'localhost:5000',
    '127.0.0.1',
    '127.0.0.1:5000',
    '192.168.88.100',
    '192.168.88.100:5000',
    '192.168.88.1',
    '192.168.88.1:5000',
  ],
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*',
        pathname: '/**',
      },
    ],
  },
  // 反向代理：将 /api 请求转发到后端
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://backend:8000/api/:path*',
      },
    ];
  },
};

export default nextConfig;
