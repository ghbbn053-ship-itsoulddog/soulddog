import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// 中间件：保护需要登录的路由
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // 需要登录保护的路由
  const protectedRoutes = ['/chat'];
  
  // 检查是否需要保护
  const isProtectedRoute = protectedRoutes.some(route => 
    pathname.startsWith(route)
  );
  
  if (isProtectedRoute) {
    // 检查是否有登录凭证（从cookie或localStorage）
    // 注意：Next.js中间件无法直接读取localStorage，需要通过cookie
    // 我们在登录时设置cookie
    
    const sessionCookie = request.cookies.get('session_username');
    
    if (!sessionCookie) {
      // 未登录，重定向到登录页
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('redirect', pathname);
      return NextResponse.redirect(loginUrl);
    }
  }
  
  return NextResponse.next();
}

// 配置中间件匹配的路由
export const config = {
  matcher: [
    /*
     * 匹配所有路径，除了：
     * - api (API routes)
     * - _next/static (静态文件)
     * - _next/image (图片优化)
     * - favicon.ico
     * - 登录页本身
     */
    '/((?!api|_next/static|_next/image|favicon.ico|login|$).*)',
  ],
};
