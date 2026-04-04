'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    // 检查是否已登录
    const userStr = localStorage.getItem('user');
    if (!userStr) {
      router.push('/');
      return;
    }
    setUser(JSON.parse(userStr));
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('user');
    router.push('/');
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-lg">正在加载...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
      {/* 顶部导航 */}
      <header className="bg-white dark:bg-gray-800 shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              教务系统 AI 助手
            </h1>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600 dark:text-gray-300">
                欢迎, {user.username}
              </span>
              <Button onClick={handleLogout} variant="outline">
                退出登录
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* AI 问答卡片 */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle>AI 智能问答</CardTitle>
              <CardDescription>
                向 AI 助手提问，获取教务系统相关信息
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button className="w-full" disabled>
                即将推出...
              </Button>
            </CardContent>
          </Card>

          {/* 个人信息卡片 */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle>个人信息</CardTitle>
              <CardDescription>
                查看您的教务系统个人信息
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button className="w-full" disabled>
                即将推出...
              </Button>
            </CardContent>
          </Card>

          {/* 成绩查询卡片 */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle>成绩查询</CardTitle>
              <CardDescription>
                查看您的考试成绩和学分
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button className="w-full" disabled>
                即将推出...
              </Button>
            </CardContent>
          </Card>

          {/* 课程表卡片 */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle>课程表</CardTitle>
              <CardDescription>
                查看您的课程安排
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button className="w-full" disabled>
                即将推出...
              </Button>
            </CardContent>
          </Card>

          {/* 选课卡片 */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle>选课中心</CardTitle>
              <CardDescription>
                浏览和选择课程
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button className="w-full" disabled>
                即将推出...
              </Button>
            </CardContent>
          </Card>

          {/* 设置卡片 */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle>系统设置</CardTitle>
              <CardDescription>
                管理您的账户和偏好设置
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button className="w-full" disabled>
                即将推出...
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* 提示信息 */}
        <div className="mt-8">
          <Card>
            <CardHeader>
              <CardTitle>开发进度</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-600 dark:text-gray-300">
                当前版本：v1.0.0 (开发中)
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-300 mt-2">
                ✅ 已完成：登录系统、验证码获取、服务器选择逻辑
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-300 mt-2">
                🚧 开发中：数据爬取、AI 问答、向量存储
              </p>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
