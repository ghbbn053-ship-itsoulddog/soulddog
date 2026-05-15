"use client";

import React, { useState } from "react";
import { Eye, EyeOff, GraduationCap, KeyRound, Loader2, ShieldCheck, User } from "lucide-react";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

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
  const [syncStatus, setSyncStatus] = useState<string | null>(null);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const fetchCaptcha = async (currentUsername?: string) => {
    try {
      const uname = currentUsername ?? username;
      const url = uname
        ? `${API_BASE}/api/captcha?username=${encodeURIComponent(uname)}`
        : `${API_BASE}/api/captcha`;
      const res = await fetch(url);

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        setError(`验证码加载失败: ${errorData.detail || "请稍后重试"}`);
        return;
      }

      const data = await res.json();
      if (data.success) {
        setCaptchaImage(data.image);
        setCaptchaSessionId(data.captcha_session_id);
        setCaptcha("");
      } else {
        setError("验证码加载失败，请刷新页面重试");
      }
    } catch {
      setError("验证码网络错误，请检查网络连接");
    }
  };

  React.useEffect(() => {
    try {
      localStorage.removeItem("current_conversation_id");
      const keys = Object.keys(localStorage);
      keys.forEach((k) => {
        if (k.startsWith("current_conversation_id_")) {
          localStorage.removeItem(k);
        }
      });
    } catch {
    }
    fetchCaptcha();
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

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
        captcha_session_id: captchaSessionId,
      };

      const res = await fetch(`${API_BASE}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(requestBody),
      });

      const data = await res.json();

      if (data.success) {
        localStorage.setItem("username", username);
        setSyncStatus("syncing");
        setError("");
        router.replace("/workspace");
        return;
      }

      setError(data.message || data.detail || "登录失败");
      fetchCaptcha();
      setCaptcha("");
    } catch {
      setError("网络错误，请检查网络连接");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen px-4 py-6 md:px-6 md:py-8">
      <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-[1220px] gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <Card className="overflow-hidden border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(241,245,249,0.92))] shadow-[0_20px_60px_rgba(15,23,42,0.08)]">
          <CardHeader className="space-y-6 pb-0">
            <Badge variant="outline" className="w-fit rounded-full px-3 py-1 text-[11px] tracking-[0.18em] text-slate-500">
              CAMPUS AUTH
            </Badge>
            <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-sm">
              <GraduationCap className="h-8 w-8" />
            </div>
            <div className="space-y-3">
              <CardTitle className="text-4xl font-semibold tracking-[-0.04em] text-slate-950">教务登录</CardTitle>
              <CardDescription className="max-w-md text-sm leading-6 text-slate-600">
                登录后优先进入工作区入口。教务同步仍由后端继续执行，但登录页不再强行卡住等待。
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="mt-8 space-y-4">
            <Card className="border-transparent bg-white/70 shadow-none">
              <CardContent className="space-y-3 p-4 text-sm text-slate-600">
                <div className="flex items-center gap-2 text-slate-900">
                  <ShieldCheck className="h-4 w-4 text-[hsl(var(--primary))]" />
                  登录说明
                </div>
                <div>使用教务系统账号和验证码登录。</div>
                <div>登录后默认进入 `/workspace`，后台继续同步数据。</div>
                <div>如需切换账号，直接重新访问 `/login` 即可。</div>
              </CardContent>
            </Card>
            <div className="grid gap-3 sm:grid-cols-2">
              <Card className="border-transparent bg-slate-50 shadow-none">
                <CardContent className="p-4">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">登录对象</div>
                  <div className="mt-2 text-lg font-semibold text-slate-950">教务账号</div>
                </CardContent>
              </Card>
              <Card className="border-transparent bg-slate-50 shadow-none">
                <CardContent className="p-4">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">跳转页面</div>
                  <div className="mt-2 text-lg font-semibold text-slate-950">工作区入口</div>
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>

        <Card className="border-white/70 bg-white/92 shadow-[0_20px_60px_rgba(15,23,42,0.08)]">
          <CardHeader>
            <CardTitle className="text-xl">账号认证</CardTitle>
            <CardDescription>保留现有教务认证逻辑，只重做界面层。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {error ? (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
            ) : null}

            {syncStatus ? (
              <div
                className={`rounded-2xl border px-4 py-4 text-sm ${
                  syncStatus === "syncing"
                    ? "border-blue-200 bg-blue-50 text-blue-700"
                    : syncStatus === "completed"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-amber-200 bg-amber-50 text-amber-700"
                }`}
              >
                {syncStatus === "syncing" ? "登录成功，后台正在同步教务数据..." : null}
                {syncStatus === "completed" ? "数据同步完成，正在跳转..." : null}
                {syncStatus === "failed" ? "数据同步失败，仍会进入工作区基础模式。" : null}
              </div>
            ) : null}

            <form onSubmit={handleLogin} className="space-y-4">
              <label className="block space-y-2">
                <div className="text-sm font-medium text-slate-900">学号</div>
                <div className="relative">
                  <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="请输入学号" className="pl-10" required />
                </div>
              </label>

              <label className="block space-y-2">
                <div className="text-sm font-medium text-slate-900">密码</div>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="请输入密码"
                    className="pl-10 pr-11"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </label>

              <label className="block space-y-2">
                <div className="text-sm font-medium text-slate-900">验证码</div>
                <div className="grid gap-3 sm:grid-cols-[1fr_132px]">
                  <Input value={captcha} onChange={(e) => setCaptcha(e.target.value)} placeholder="请输入验证码" required />
                  {captchaImage ? (
                    <img
                      src={captchaImage}
                      alt="验证码"
                      onClick={() => fetchCaptcha()}
                      className="h-11 w-full cursor-pointer rounded-xl border border-[hsl(var(--border))] bg-slate-50 object-contain"
                    />
                  ) : (
                    <div className="flex h-11 items-center justify-center rounded-xl border border-[hsl(var(--border))] bg-slate-50 text-xs text-slate-400">
                      加载中
                    </div>
                  )}
                </div>
              </label>

              <Button type="submit" disabled={isLoading || !!syncStatus} className="w-full">
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    登录中...
                  </>
                ) : (
                  "登录"
                )}
              </Button>
            </form>

            <div className="text-center text-xs text-slate-400">使用教务系统账号密码登录</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
