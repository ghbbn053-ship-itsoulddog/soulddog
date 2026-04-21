import { NextResponse } from 'next/server';

// 临时禁用前端中间件保护，避免开发态路由循环刷新。
// 登录隔离仍由后端接口基于 cookie + session 强校验。
export function middleware() {
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!.*).*)'],
};
