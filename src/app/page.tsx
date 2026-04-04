'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [captcha, setCaptcha] = useState('');
  const [captchaImage, setCaptchaImage] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  // 获取验证码
  const fetchCaptcha = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/captcha');
      const data = await response.json();

      if (data.success) {
        setCaptchaImage(data.image);
      } else {
        setMessage({ type: 'error', text: '获取验证码失败' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: '网络错误，请检查后端服务' });
    } finally {
      setLoading(false);
    }
  };

  // 登录
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!username || !password || !captcha) {
      setMessage({ type: 'error', text: '请填写所有字段' });
      return;
    }

    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username,
          password,
          code: captcha,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setMessage({ type: 'success', text: '登录成功！正在跳转...' });
        // TODO: 保存 token 并跳转到主页
        setTimeout(() => {
          // 保存用户信息到 localStorage
          localStorage.setItem('user', JSON.stringify(data));
          // 跳转到主页
          window.location.href = '/dashboard';
        }, 1000);
      } else {
        setMessage({ type: 'error', text: data.message || '登录失败' });
        // 刷新验证码
        fetchCaptcha();
        setCaptcha('');
      }
    } catch (error) {
      setMessage({ type: 'error', text: '网络错误，请稍后重试' });
    } finally {
      setLoading(false);
    }
  };

  // 页面加载时获取验证码
  useEffect(() => {
    fetchCaptcha();
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <Card className="w-full max-w-md shadow-2xl">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">教务系统 AI 助手</CardTitle>
          <CardDescription className="text-center">
            请输入您的教务系统账号密码登录
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            {/* 用户名 */}
            <div className="space-y-2">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                type="text"
                placeholder="请输入学号"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={loading}
              />
            </div>

            {/* 密码 */}
            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                placeholder="请输入密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
              />
            </div>

            {/* 验证码 */}
            <div className="space-y-2">
              <Label htmlFor="captcha">验证码</Label>
              <div className="flex gap-2">
                <Input
                  id="captcha"
                  type="text"
                  placeholder="请输入验证码"
                  value={captcha}
                  onChange={(e) => setCaptcha(e.target.value)}
                  disabled={loading}
                  maxLength={6}
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={fetchCaptcha}
                  disabled={loading}
                  className="w-32"
                >
                  {captchaImage ? (
                    <img
                      src={captchaImage}
                      alt="验证码"
                      className="w-full h-10 object-contain"
                    />
                  ) : (
                    '加载中...'
                  )}
                </Button>
              </div>
            </div>

            {/* 消息提示 */}
            {message && (
              <Alert variant={message.type === 'error' ? 'destructive' : 'default'}>
                <AlertDescription>{message.text}</AlertDescription>
              </Alert>
            )}

            {/* 登录按钮 */}
            <Button
              type="submit"
              className="w-full"
              disabled={loading}
            >
              {loading ? '登录中...' : '登录'}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex flex-col space-y-2">
          <p className="text-xs text-muted-foreground text-center">
            Powered by AI Assistant
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
