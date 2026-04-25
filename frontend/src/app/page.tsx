"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BookOpen,
  Bot,
  CalendarDays,
  ChevronRight,
  GraduationCap,
  Loader2,
  MessageSquare,
  RefreshCcw,
  Sparkles,
} from "lucide-react";

import { PlatformSidebarFooter, PlatformSidebarHeader, createPlatformNav } from "@/components/workspace/app-sidebar";
import { WorkbenchBadge, WorkbenchShell } from "@/components/workspace/workbench-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

type WorkspaceItem = {
  id: number;
  slug: string;
  name: string;
  description?: string;
  is_default: boolean;
};

type Conversation = {
  id: number;
  title: string;
  created_at: string;
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
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [schedule, setSchedule] = useState<ScheduleCourse[]>([]);
  const [educationStatus, setEducationStatus] = useState<EducationStatus | null>(null);
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

        const [workspaceRes, convRes, scheduleRes, statusRes] = await Promise.all([
          fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}`, { credentials: "include" }),
          fetch(`${API_BASE}/api/chat/conversations/${encodeURIComponent(uname)}`, { credentials: "include" }),
          fetch(`${API_BASE}/api/schedule/db?username=${encodeURIComponent(uname)}`, { credentials: "include" }),
          fetch(`${API_BASE}/api/education/status?username=${encodeURIComponent(uname)}`, { credentials: "include" }),
        ]);

        if (!mounted) return;

        const workspaceJson = workspaceRes.ok ? await workspaceRes.json() : null;
        const convJson = convRes.ok ? await convRes.json() : [];
        const scheduleJson = scheduleRes.ok ? await scheduleRes.json() : null;
        const statusJson = statusRes.ok ? await statusRes.json() : null;

        setWorkspaces(workspaceJson?.workspaces || []);
        setConversations(Array.isArray(convJson) ? convJson : []);
        setSchedule(scheduleJson?.data?.课程列表 || scheduleJson?.data || []);
        setEducationStatus(statusJson || null);
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
          <Button variant="outline" onClick={() => router.push(featuredWorkspace ? `/workspace/${featuredWorkspace.id}` : "/workspace")}>学习工作区</Button>
          <Button onClick={() => router.push("/chat")}>快速会话</Button>
        </>
      }
    >
      <div className="grid gap-4">
        <div className="grid gap-4 lg:grid-cols-2">
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
                <Bot className="h-4 w-4 text-slate-500" />
                <div>
                  <CardTitle className="text-base">快速会话</CardTitle>
                  <CardDescription>保留模型切换、推理模式和流式输出。</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex h-full flex-col justify-between gap-4">
              <div className="space-y-3">
                <div className="text-sm text-slate-600">
                  快速问答适合直接查询成绩、课表、考试安排，也可以进入 Agent Runtime。
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {["查询我的成绩", "这学期课表", "我的学分情况", "考试安排"].map((item) => (
                    <Card key={item} className="shadow-none">
                      <CardContent className="flex items-center gap-3 p-4 text-sm text-slate-700">
                        <Sparkles className="h-4 w-4 text-[hsl(var(--primary))]" />
                        {item}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
              <Button onClick={() => router.push("/chat")}>
                进入会话
                <ChevronRight className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="bg-white/90">
            <CardHeader>
              <div className="flex items-center gap-2">
                <GraduationCap className="h-4 w-4 text-slate-500" />
                <div>
                  <CardTitle className="text-base">学习工作区</CardTitle>
                  <CardDescription>工作区是文档、知识和平台能力的统一容器。</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {featuredWorkspace ? (
                <Card className="shadow-none">
                  <CardContent className="space-y-2 p-4">
                    <div className="text-sm font-medium text-slate-900">{featuredWorkspace.name}</div>
                    <div className="text-xs text-slate-500">{featuredWorkspace.description || featuredWorkspace.slug}</div>
                    {featuredWorkspace.is_default && <Badge variant="secondary">默认工作区</Badge>}
                  </CardContent>
                </Card>
              ) : (
                <Card className="border-dashed shadow-none">
                  <CardContent className="p-6 text-sm text-slate-500">暂无工作区</CardContent>
                </Card>
              )}
              <Button onClick={() => router.push("/schedule")}>
                完整课表
                <ChevronRight className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>

          <Card className="bg-white/90">
            <CardHeader>
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-slate-500" />
                <div>
                  <CardTitle className="text-base">学习状态</CardTitle>
                  <CardDescription>当前先使用轻量统计面板，后续可切真实学习日志。</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <Card className="bg-[hsl(var(--muted))] shadow-none">
                <CardContent className="p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">今日学习</div>
                  <div className="mt-2 text-3xl font-semibold text-slate-950">{conversations.length * 5} 分钟</div>
                </CardContent>
              </Card>
              <Card className="bg-[hsl(var(--muted))] shadow-none">
                <CardContent className="p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">提问次数</div>
                  <div className="mt-2 text-3xl font-semibold text-slate-950">{conversations.length}</div>
                </CardContent>
              </Card>
            </CardContent>
          </Card>
        </div>

        <Card className="bg-white/90">
          <CardHeader>
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-slate-500" />
              <div>
                <CardTitle className="text-base">最近对话</CardTitle>
                <CardDescription>便于从首页直接回到近期上下文。</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-56 pr-3">
              <div className="space-y-3">
                {conversations.length === 0 ? (
                  <div className="text-sm text-slate-500">暂无最近对话</div>
                ) : (
                  conversations.slice(0, 8).map((item) => (
                    <Card key={item.id} className="shadow-none">
                      <CardContent className="flex items-center justify-between gap-3 p-4">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-slate-900">{item.title}</div>
                          <div className="mt-1 text-xs text-slate-500">{new Date(item.created_at).toLocaleString("zh-CN")}</div>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => router.push("/chat")}>
                          打开
                        </Button>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </WorkbenchShell>
  );
}
