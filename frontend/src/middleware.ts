import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// 长期策略：开发环境不介入；生产环境仅保护 /chat 的 HTML 文档请求。
export function middleware(request: NextRequest) {
  if (process.env.NODE_ENV !== 'production') {
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;
  if (!pathname.startsWith('/chat')) {
    return NextResponse.next();
  }

  const accept = request.headers.get('accept') || '';
  if (!accept.includes('text/html')) {
    return NextResponse.next();
  }

  const authSessionId = request.cookies.get('auth_session_id');
  if (!authSessionId) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('redirect', pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/chat/:path*'],
};
