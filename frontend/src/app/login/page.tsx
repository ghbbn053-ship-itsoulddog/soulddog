"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { GraduationCap, User, Lock, Eye, EyeOff, Loader2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [captcha, setCaptcha] = useState("");
  const [captchaImage, setCaptchaImage] = useState("");
  const [captchaSessionId, setCaptchaSessionId] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [syncStatus, setSyncStatus] = useState<string | null>(null); // null | syncing | completed | failed

  const API_BASE = "";  // 使用相对路径，通过 Nginx 反向代理

  // 获取验证码
  const fetchCaptcha = async (currentUsername?: string) => {
    try {
      const uname = currentUsername ?? username;
      // 如果已输入用户名，传递给后端用于选择服务器
      const url = uname 
        ? `${API_BASE}/api/captcha?username=${encodeURIComponent(uname)}`
        : `${API_BASE}/api/captcha`;
      const res = await fetch(url);
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        console.error("验证码请求失败:", errorData);
        setError(`验证码加载失败: ${errorData.detail || '请稍后重试'}`);
        return;
      }
      
      const data = await res.json();
      if (data.success) {
        setCaptchaImage(data.image);
        setCaptchaSessionId(data.captcha_session_id);
        setCaptcha(""); // 刷新验证码时清空输入
      } else {
        console.error("验证码响应异常:", data);
        setError("验证码加载失败，请刷新页面重试");
      }
    } catch (error) {
      console.error("获取验证码失败:", error);
      setError("验证码网络错误，请检查网络连接");
    }
  };

  // 页面加载时获取验证码
  React.useEffect(() => {
    fetchCaptcha();
  }, []);

  // 当用户输入用户名后，延迟刷新验证码（确保服务器匹配）
  const usernameRef = React.useRef(username);
  usernameRef.current = username;
  React.useEffect(() => {
    if (username && username.length >= 10) {
      // 用户名输入完成后，刷新验证码
      const timer = setTimeout(() => {
        fetchCaptcha(usernameRef.current);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [username]);

  // 登录
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    // 验证参数
    if (!username || !password || !captcha) {
      setError("请填写所有字段");
      setIsLoading(false);
      return;
    }
    if (!captchaSessionId) {
      setError("验证码会话无效，请点击验证码刷新");
      setIsLoading(false);
      fetchCaptcha();
      return;
    }

    try {
      const requestBody = { 
        username, 
        password, 
        code: captcha, 
        captcha_session_id: captchaSessionId 
      };
      console.log("登录请求:", requestBody);

      const res = await fetch(`${API_BASE}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody)
      });

      const data = await res.json();
      console.log("登录响应:", data);

      if (data.success) {
        // 保存用户名到 localStorage
        localStorage.setItem("username", username);
        
        // 检查同步状态
        const syncStatus = data.sync_status;
        const syncMessage = data.sync_message || "";
        
        if (syncStatus === "completed") {
          // 已有数据，直接跳转（带提示）
          setSyncStatus("completed");
          if (syncMessage) {
            // 显示提示信息
            setError(syncMessage); // 复用error显示，但用不同颜色
          }
          // 1秒后跳转
          setTimeout(() => router.push("/chat"), 1000);
        } else {
          // 首次登录，需要后台同步
          setSyncStatus("syncing");
          pollSyncStatus(username);
        }
      } else {
        setError(data.message || data.detail || "登录失败");
        fetchCaptcha(); // 刷新验证码
        setCaptcha(""); // 清空验证码输入
      }
    } catch (error) {
      console.error("登录错误:", error);
      setError("网络错误，请检查网络连接");
    } finally {
      setIsLoading(false);
    }
  };

  // 轮询数据同步状态
  const pollSyncStatus = async (uname: string) => {
    const maxAttempts = 60; // 最多轮询60次（约2分钟）
    let attempts = 0;
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/sync-status?username=${encodeURIComponent(uname)}`);
        const data = await res.json();
        setSyncStatus(data.status);
        if (data.status === "completed") {
          // 同步完成，跳转到聊天页面
          setTimeout(() => router.push("/chat"), 800);
          return;
        }
        if (data.status === "failed") {
          // 同步失败，仍然跳转（可以使用缓存数据或纯对话）
          setTimeout(() => router.push("/chat"), 1500);
          return;
        }
      } catch (e) {
        console.error("轮询同步状态失败:", e);
      }
      attempts++;
      if (attempts < maxAttempts) {
        setTimeout(poll, 2000);
      } else {
        // 超时也跳转
        router.push("/chat");
      }
    };
    poll();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-2xl shadow-blue-500/20">
            <GraduationCap className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">校园AI助手</h1>
          <p className="text-gray-500 mt-2">请登录教务系统账号</p>
        </div>

        {/* 登录表单 */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
              {error}
            </div>
          )}

          {/* 数据同步状态 */}
          {syncStatus && (
            <div className={`mb-4 p-4 rounded-xl text-sm flex items-center gap-3 ${
              syncStatus === "syncing" ? "bg-blue-50 border border-blue-200 text-blue-700" :
              syncStatus === "completed" ? "bg-green-50 border border-green-200 text-green-700" :
              "bg-yellow-50 border border-yellow-200 text-yellow-700"
            }`}>
              {syncStatus === "syncing" && (
                <>
                  <Loader2 className="w-5 h-5 animate-spin flex-shrink-0" />
                  <div>
                    <p className="font-medium">登录成功，正在同步教务数据...</p>
                    <p className="text-xs mt-0.5 opacity-75">首次登录需要较长时间，请耐心等待</p>
                  </div>
                </>
              )}
              {syncStatus === "completed" && (
                <>
                  <span className="text-lg">✓</span>
                  <p className="font-medium">数据同步完成，正在跳转...</p>
                </>
              )}
              {syncStatus === "failed" && (
                <>
                  <span className="text-lg">⚠</span>
                  <div>
                    <p className="font-medium">数据同步失败，将使用基础对话模式</p>
                    <p className="text-xs mt-0.5 opacity-75">正在跳转...</p>
                  </div>
                </>
              )}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            {/* 学号 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                学号
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="请输入学号"
                  className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>
            </div>

            {/* 密码 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                密码
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  className="w-full pl-10 pr-12 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {/* 验证码 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                验证码
              </label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={captcha}
                  onChange={(e) => setCaptcha(e.target.value)}
                  placeholder="请输入验证码"
                  className="flex-1 px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
                {captchaImage && (
                  <img
                    src={captchaImage}
                    alt="验证码"
                    onClick={() => fetchCaptcha()}
                    className="h-12 w-28 object-contain rounded-xl cursor-pointer hover:opacity-80 bg-gray-100"
                  />
                )}
              </div>
            </div>

            {/* 登录按钮 */}
            <button
              type="submit"
              disabled={isLoading || !!syncStatus}
              className="w-full py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl font-medium hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg shadow-blue-500/25 flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  登录中...
                </>
              ) : (
                "登录"
              )}
            </button>
          </form>

          {/* 提示 */}
          <p className="text-center text-sm text-gray-500 mt-6">
            使用教务系统账号密码登录
          </p>
        </div>
      </div>
    </div>
  );
}
