'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

interface Grade {
  id: number;
  courseName: string;
  courseCode: string;
  credits: number;
  score: number;
  gpa: number;
  semester: string;
  courseType: string;
}

export default function GradesPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [grades, setGrades] = useState<Grade[]>([]);
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
    fetchGrades(JSON.parse(userStr).username);
  }, [router]);

  const fetchGrades = async (username: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`http://localhost:8000/api/grades/all?username=${username}`);
      const data = await response.json();

      if (data.success) {
        setGrades(data.data || []);
      } else {
        setError(data.message || '获取成绩失败');
      }
    } catch (error) {
      setError('网络错误，请检查后端服务');
    } finally {
      setLoading(false);
    }
  };

  // 计算统计数据
  const calculateStats = () => {
    if (grades.length === 0) return null;

    const totalCredits = grades.reduce((sum, grade) => sum + grade.credits, 0);
    const weightedScore = grades.reduce(
      (sum, grade) => sum + grade.score * grade.credits,
      0
    );
    const averageGPA = grades.reduce((sum, grade) => sum + grade.gpa, 0) / grades.length;

    return {
      totalCourses: grades.length,
      totalCredits,
      averageScore: (weightedScore / totalCredits).toFixed(2),
      averageGPA: averageGPA.toFixed(2),
    };
  };

  const stats = calculateStats();

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
              成绩查询
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
                正在获取成绩...
              </p>
            </CardContent>
          </Card>
        ) : grades.length > 0 ? (
          <div className="space-y-6">
            {/* 统计信息 */}
            {stats && (
              <Card>
                <CardHeader>
                  <CardTitle>成绩统计</CardTitle>
                  <CardDescription>您的整体成绩概况</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                      <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                        {stats.totalCourses}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        总课程数
                      </p>
                    </div>
                    <div className="text-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                      <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                        {stats.totalCredits}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        总学分
                      </p>
                    </div>
                    <div className="text-center p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                      <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                        {stats.averageScore}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        平均分
                      </p>
                    </div>
                    <div className="text-center p-4 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
                      <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                        {stats.averageGPA}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        平均绩点
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 成绩列表 */}
            <Card>
              <CardHeader>
                <CardTitle>课程成绩</CardTitle>
                <CardDescription>您所有课程的成绩详情</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>课程名称</TableHead>
                        <TableHead>课程代码</TableHead>
                        <TableHead>学分</TableHead>
                        <TableHead>成绩</TableHead>
                        <TableHead>绩点</TableHead>
                        <TableHead>学期</TableHead>
                        <TableHead>课程性质</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {grades.map((grade) => (
                        <TableRow key={grade.id}>
                          <TableCell className="font-medium">
                            {grade.courseName}
                          </TableCell>
                          <TableCell>{grade.courseCode}</TableCell>
                          <TableCell>{grade.credits}</TableCell>
                          <TableCell>
                            <span
                              className={`px-2 py-1 rounded-full text-sm font-medium ${
                                grade.score >= 90
                                  ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                                  : grade.score >= 80
                                  ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
                                  : grade.score >= 70
                                  ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                                  : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                              }`}
                            >
                              {grade.score}
                            </span>
                          </TableCell>
                          <TableCell>{grade.gpa}</TableCell>
                          <TableCell>{grade.semester}</TableCell>
                          <TableCell>{grade.courseType}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <Card>
            <CardContent className="py-12">
              <p className="text-center text-gray-500 dark:text-gray-400">
                暂无成绩记录
              </p>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
