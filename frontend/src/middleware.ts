import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// 中间件：保护需要登录的路由
export function middleware(request: NextRequest) {
  // 开发环境放行，避免影响 HMR 与本地调试稳定性
  if (process.env.NODE_ENV !== 'production') {
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;

  // 仅保护 /chat 页面文档请求
  if (!pathname.startsWith('/chat')) {
    return NextResponse.next();
  }

  const accept = request.headers.get('accept') || '';
  if (!accept.includes('text/html')) {
    return NextResponse.next();
  }

  const sessionCookie = request.cookies.get('session_username');

  if (!sessionCookie) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('redirect', pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

// 配置中间件匹配的路由
export const config = {
  matcher: ['/chat/:path*'],
};
