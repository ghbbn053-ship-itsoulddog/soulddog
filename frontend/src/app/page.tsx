"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BookOpen,
  CalendarDays,
  ChevronRight,
  GraduationCap,
  History,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCcw,
} from "lucide-react";

import { PlatformSidebarFooter, PlatformSidebarHeader, createPlatformNav } from "@/components/workspace/app-sidebar";
import { WorkbenchBadge, WorkbenchShell } from "@/components/workspace/workbench-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type WorkspaceItem = {
  id: number;
  slug: string;
  name: string;
  description?: string;
  is_default: boolean;
};

type ScheduleCourse = Record<string, unknown>;

type EducationStatus = {
  success?: boolean;
  has_cache?: boolean;
  freshness?: string;
  cached_at?: string | null;
  sync?: {
    status?: string;
    message?: string;
    timestamp?: number;
  };
};

type ConversationItem = {
  id: number;
  title: string;
  created_at: string;
  workspace_id?: number | null;
};

function extractCourseLabel(course: ScheduleCourse, keys: string[]) {
  for (const key of keys) {
    const value = String(course[key] ?? "").trim();
    if (value) return value;
  }
  return "";
}

function getFreshnessMeta(status: EducationStatus | null) {
  if (!status?.cached_at) {
    return {
      label: "暂无同步数据",
      badge: "outline" as const,
    };
  }

  const cachedAt = new Date(status.cached_at).getTime();
  const deltaHours = Math.max(0, (Date.now() - cachedAt) / 3600000);

  if (status.freshness === "fresh") {
    return {
      label: deltaHours < 1 ? "更新于 1 小时内" : `更新于 ${Math.floor(deltaHours)} 小时前`,
      badge: "success" as const,
    };
  }

  if (status.freshness === "stale") {
    return {
      label: `更新于 ${Math.floor(deltaHours / 24)} 天前`,
      badge: "warning" as const,
    };
  }

  return {
    label: `更新于 ${Math.floor(deltaHours / 24)} 天前`,
    badge: "destructive" as const,
  };
}

export default function HomePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [schedule, setSchedule] = useState<ScheduleCourse[]>([]);
  const [educationStatus, setEducationStatus] = useState<EducationStatus | null>(null);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  useEffect(() => {
    let mounted = true;

    const bootstrap = async () => {
      try {
        const meRes = await fetch(`${API_BASE}/api/auth/me`, { credentials: "include" });
        const me = meRes.ok ? await meRes.json() : null;
        if (!me?.authenticated || !me?.username) {
          if (mounted) router.replace("/login");
          return;
        }

        const uname = String(me.username);
        if (!mounted) return;
        setUsername(uname);

        const [workspaceRes, scheduleRes, statusRes, conversationRes] = await Promise.all([
          fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}`, { credentials: "include" }),
          fetch(`${API_BASE}/api/schedule/db?username=${encodeURIComponent(uname)}`, { credentials: "include" }),
          fetch(`${API_BASE}/api/education/status?username=${encodeURIComponent(uname)}`, { credentials: "include" }),
          fetch(`${API_BASE}/api/chat/conversations/${encodeURIComponent(uname)}`, { credentials: "include" }),
        ]);

        if (!mounted) return;

        const workspaceJson = workspaceRes.ok ? await workspaceRes.json() : null;
        const scheduleJson = scheduleRes.ok ? await scheduleRes.json() : null;
        const statusJson = statusRes.ok ? await statusRes.json() : null;
        const conversationJson = conversationRes.ok ? await conversationRes.json() : null;

        setWorkspaces(workspaceJson?.workspaces || []);
        setSchedule(scheduleJson?.data?.课程列表 || scheduleJson?.data || []);
        setEducationStatus(statusJson || null);
        setConversations(Array.isArray(conversationJson) ? conversationJson : []);
      } catch {
        if (mounted) router.replace("/login");
      } finally {
        if (mounted) setLoading(false);
      }
    };

    bootstrap();
    return () => {
      mounted = false;
    };
  }, [API_BASE, router]);

  const freshness = useMemo(() => getFreshnessMeta(educationStatus), [educationStatus]);
  const featuredWorkspace = useMemo(() => workspaces[0] || null, [workspaces]);
  const todayCourses = useMemo(() => schedule.slice(0, 3), [schedule]);
  const recentConversations = useMemo(() => conversations.slice(0, 6), [conversations]);

  const openConversation = (conversationId: number) => {
    if (!username) {
      router.push("/chat");
      return;
    }
    localStorage.setItem(`current_conversation_id_${username}`, String(conversationId));
    router.push(`/chat?conversation_id=${conversationId}`);
  };

  const handleRefresh = async () => {
    if (!username || refreshing) return;
    try {
      setRefreshing(true);
      await fetch(`${API_BASE}/api/refresh?username=${encodeURIComponent(username)}`, {
        method: "POST",
        credentials: "include",
      });
      const statusRes = await fetch(`${API_BASE}/api/education/status?username=${encodeURIComponent(username)}`, {
        credentials: "include",
      });
      const statusJson = statusRes.ok ? await statusRes.json() : null;
      setEducationStatus(statusJson || null);
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-sm text-slate-500">
          <Loader2 className="h-8 w-8 animate-spin text-[hsl(var(--primary))]" />
          加载中...
        </div>
      </div>
    );
  }

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <GraduationCap className="h-3.5 w-3.5" />
          DASHBOARD
        </WorkbenchBadge>
      }
      title="平台首页"
      description="首页现在优先读取 PostgreSQL 缓存教务数据，不再每次访问都打实时爬虫。"
      sidebarTitle="平台导航"
      sidebarDescription="快速会话、工作区、Skill、MCP 和模型设置统一入口。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("home")}
      footer={<PlatformSidebarFooter username={username} detail="当前登录用户" />}
      topActions={
        <>
          <Button variant="outline" onClick={() => router.push(featuredWorkspace ? `/workspace/${featuredWorkspace.id}` : "/workspace")}>进入工作区</Button>
          <Button onClick={() => router.push("/chat")}>快速会话</Button>
        </>
      }
    >
      <div className="grid gap-4">
        <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <Card className="bg-white/90">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <CalendarDays className="h-4 w-4 text-slate-500" />
                  <div>
                    <CardTitle className="text-base">今日课表</CardTitle>
                    <CardDescription>优先读取缓存课表，支持进入完整周视图。</CardDescription>
                  </div>
                </div>
                <Button variant="ghost" size="sm" onClick={() => router.push("/schedule")}>
                  查看
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {todayCourses.length === 0 ? (
                <Card className="border-dashed shadow-none">
                  <CardContent className="p-6 text-sm text-slate-500">暂无课表缓存数据</CardContent>
                </Card>
              ) : (
                todayCourses.map((course, index) => (
                  <Card key={index} className="shadow-none">
                    <CardContent className="space-y-2 p-4">
                      <div className="text-sm font-medium text-slate-900">
                        {extractCourseLabel(course, ["课程名称", "课程名", "课程"])}
                      </div>
                      <div className="text-xs text-slate-500">
                        {extractCourseLabel(course, ["上课时间", "时间", "节次"]) || "时间待定"}
                      </div>
                      <div className="text-xs text-slate-500">
                        📍 {extractCourseLabel(course, ["地点", "教室"]) || "地点待定"}　
                        👤 {extractCourseLabel(course, ["教师", "老师"]) || "教师待定"}
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[hsl(var(--border))] pt-3">
                <Badge variant={freshness.badge}>{freshness.label}</Badge>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
                    {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
                    刷新
                  </Button>
                  <Button size="sm" onClick={() => router.push("/schedule")}>
                    完整课表
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white/90">
            <CardHeader>
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-slate-500" />
                <div>
                  <CardTitle className="text-base">会话列表</CardTitle>
                  <CardDescription>这里直接进入已有快速会话，或者新建一条空会话。</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex h-full flex-col gap-4">
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => router.push("/chat")}>
                  <Plus className="h-4 w-4" />
                  创建新会话
                </Button>
              </div>
              <div className="space-y-2">
                {recentConversations.length === 0 ? (
                  <Card className="border-dashed shadow-none">
                    <CardContent className="flex items-center gap-3 p-5 text-sm text-slate-500">
                      <MessageSquare className="h-4 w-4 text-slate-300" />
                      暂无历史会话，先创建一条新的快速会话。
                    </CardContent>
                  </Card>
                ) : (
                  recentConversations.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => openConversation(item.id)}
                      className="w-full rounded-xl border border-slate-200 bg-white p-4 text-left transition hover:bg-slate-50"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium text-slate-900">{item.title}</div>
                          <div className="mt-1 text-xs text-slate-500">{new Date(item.created_at).toLocaleString("zh-CN")}</div>
                        </div>
                        <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                      </div>
                    </button>
                  ))
                )}
              </div>
              <div className="text-xs text-slate-400">点击某条会话会直接带着该会话上下文进入快速会话页。</div>
            </CardContent>
          </Card>
        </div>

        <Card className="bg-white/90">
          <CardHeader>
            <div className="flex items-center gap-2">
              <GraduationCap className="h-4 w-4 text-slate-500" />
              <div>
                <CardTitle className="text-base">学习工作区</CardTitle>
                <CardDescription>把知识库、组合编排和对话验证放在一个地方做闭环。</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-4">
              {featuredWorkspace ? (
                <Card className="shadow-none">
                  <CardContent className="space-y-3 p-5">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-base font-semibold text-slate-900">{featuredWorkspace.name}</div>
                      {featuredWorkspace.is_default ? <Badge variant="secondary">默认工作区</Badge> : null}
                    </div>
                    <div className="text-sm leading-6 text-slate-600">
                      {featuredWorkspace.description || featuredWorkspace.slug}
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <Card className="bg-[hsl(var(--muted))] shadow-none">
                        <CardContent className="p-4">
                          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">知识沉淀</div>
                          <div className="mt-2 text-2xl font-semibold text-slate-950">知识库</div>
                          <div className="mt-1 text-xs text-slate-500">文档、片段、引用都在这里收口</div>
                        </CardContent>
                      </Card>
                      <Card className="bg-[hsl(var(--muted))] shadow-none">
                        <CardContent className="p-4">
                          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">验证方式</div>
                          <div className="mt-2 text-2xl font-semibold text-slate-950">对话</div>
                          <div className="mt-1 text-xs text-slate-500">直接在工作区里做问答验证</div>
                        </CardContent>
                      </Card>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <Card className="border-dashed shadow-none">
                  <CardContent className="p-6 text-sm text-slate-500">暂无工作区</CardContent>
                </Card>
              )}
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => router.push(featuredWorkspace ? `/workspace/${featuredWorkspace.id}` : "/workspace")}>
                  打开工作区
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <Button variant="outline" onClick={() => router.push("/knowledge")}>
                  打开知识库
                </Button>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-slate-500" />
                <div>
                  <div className="text-base font-semibold text-slate-900">学习状态</div>
                  <div className="text-sm text-slate-500">首页先给你一个简洁版，不再单独占一整块。</div>
                </div>
              </div>
              <div className="grid gap-3">
                <Card className="bg-[hsl(var(--muted))] shadow-none">
                  <CardContent className="p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">今日学习</div>
                    <div className="mt-2 text-3xl font-semibold text-slate-950">{Math.max(schedule.length, 1) * 5} 分钟</div>
                    <div className="mt-1 text-xs text-slate-500">按当前缓存课表和平台访问做轻量估算</div>
                  </CardContent>
                </Card>
                <Card className="bg-[hsl(var(--muted))] shadow-none">
                  <CardContent className="p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">课业密度</div>
                    <div className="mt-2 text-3xl font-semibold text-slate-950">{schedule.length}</div>
                    <div className="mt-1 text-xs text-slate-500">当前缓存到的课程条目数</div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </WorkbenchShell>
  );
}
