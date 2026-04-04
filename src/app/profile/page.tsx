'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface UserInfo {
  name: string;
  studentId: string;
  major?: string;
  className?: string;
}

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 检查是否已登录
    const userStr = localStorage.getItem('user');
    if (!userStr) {
      router.push('/');
      return;
    }
    setUser(JSON.parse(userStr));
    fetchUserInfo(JSON.parse(userStr).username);
  }, [router]);

  const fetchUserInfo = async (username: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`http://localhost:8000/api/user/info?username=${username}`);
      const data = await response.json();

      if (data.success) {
        setUserInfo(data.data);
      } else {
        setError(data.message || '获取个人信息失败');
      }
    } catch (error) {
      setError('网络错误，请检查后端服务');
    } finally {
      setLoading(false);
    }
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
              个人信息
            </h1>
            <div className="flex items-center gap-4">
              <Button
                onClick={() => router.push('/dashboard')}
                variant="outline"
              >
                返回首页
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <Alert className="mb-6 border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20">
            <AlertDescription className="text-red-800 dark:text-red-200">
              {error}
            </AlertDescription>
          </Alert>
        )}

        {loading ? (
          <Card>
            <CardContent className="py-12">
              <p className="text-center text-gray-500 dark:text-gray-400">
                正在获取个人信息...
              </p>
            </CardContent>
          </Card>
        ) : userInfo ? (
          <div className="grid gap-6">
            {/* 基本信息 */}
            <Card>
              <CardHeader>
                <CardTitle>基本信息</CardTitle>
                <CardDescription>您的教务系统个人信息</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4">
                  <div className="flex items-center justify-between border-b pb-3">
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      姓名
                    </span>
                    <span className="font-semibold text-gray-900 dark:text-white">
                      {userInfo.name}
                    </span>
                  </div>
                  <div className="flex items-center justify-between border-b pb-3">
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      学号
                    </span>
                    <span className="font-semibold text-gray-900 dark:text-white">
                      {userInfo.studentId}
                    </span>
                  </div>
                  {userInfo.major && (
                    <div className="flex items-center justify-between border-b pb-3">
                      <span className="text-sm text-gray-500 dark:text-gray-400">
                        专业
                      </span>
                      <span className="font-semibold text-gray-900 dark:text-white">
                        {userInfo.major}
                      </span>
                    </div>
                  )}
                  {userInfo.className && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500 dark:text-gray-400">
                        班级
                      </span>
                      <span className="font-semibold text-gray-900 dark:text-white">
                        {userInfo.className}
                      </span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* 提示信息 */}
            <Alert className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20">
              <AlertDescription className="text-blue-800 dark:text-blue-200">
                💡 提示：如需修改个人信息，请联系教务处
              </AlertDescription>
            </Alert>
          </div>
        ) : (
          <Card>
            <CardContent className="py-12">
              <p className="text-center text-gray-500 dark:text-gray-400">
                暂无个人信息
              </p>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
