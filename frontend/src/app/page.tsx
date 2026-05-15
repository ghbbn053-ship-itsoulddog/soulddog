"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  ChevronRight,
  Clock3,
  GraduationCap,
  History,
  LibraryBig,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCcw,
  Sparkles,
} from "lucide-react";

import { PlatformSidebarFooter, PlatformSidebarHeader, createPlatformNav } from "@/components/workspace/app-sidebar";
import { WorkbenchBadge, WorkbenchEmpty, WorkbenchShell } from "@/components/workspace/workbench-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { InlineStatusMessage, PageLoading } from "@/components/ui/feedback";
import { EducationStatus, normalizeScheduleData } from "@/lib/education-cache";
import { getDevPreviewUsername, isDevPreviewEnabled } from "@/lib/dev-preview";

type WorkspaceItem = {
  id: number;
  slug: string;
  name: string;
  description?: string;
  is_default: boolean;
};

type ScheduleCourse = Record<string, unknown>;

type ConversationItem = {
  id: number;
  title: string;
  created_at: string;
  workspace_id?: number | null;
};

type WorkspaceLearningSummary = {
  unresolved?: number;
};

type WorkspaceStatusSummary = {
  today_minutes?: number;
};

type RankedWorkspace = WorkspaceItem & {
  learning_summary?: WorkspaceLearningSummary;
  status_summary?: WorkspaceStatusSummary;
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
      tone: "idle" as const,
    };
  }

  const cachedAt = new Date(status.cached_at).getTime();
  const deltaHours = Math.max(0, (Date.now() - cachedAt) / 3600000);

  if (status.freshness === "fresh") {
    return {
      label: deltaHours < 1 ? "更新于 1 小时内" : `更新于 ${Math.floor(deltaHours)} 小时前`,
      badge: "success" as const,
      tone: "fresh" as const,
    };
  }

  if (status.freshness === "stale") {
    return {
      label: `更新于 ${Math.floor(deltaHours / 24)} 天前`,
      badge: "warning" as const,
      tone: "stale" as const,
    };
  }

  return {
    label: `更新于 ${Math.floor(deltaHours / 24)} 天前`,
    badge: "destructive" as const,
    tone: "expired" as const,
  };
}

function formatRelativeTime(dateText: string) {
  const value = new Date(dateText).getTime();
  const deltaMinutes = Math.max(1, Math.floor((Date.now() - value) / 60000));
  if (deltaMinutes < 60) return `${deltaMinutes} 分钟前`;
  if (deltaMinutes < 1440) return `${Math.floor(deltaMinutes / 60)} 小时前`;
  return `${Math.floor(deltaMinutes / 1440)} 天前`;
}

function rankWorkspaces(items: WorkspaceItem[]) {
  return [...items].sort((a, b) => {
    const rankedA = a as RankedWorkspace;
    const rankedB = b as RankedWorkspace;
    const unresolvedDiff = (rankedB.learning_summary?.unresolved || 0) - (rankedA.learning_summary?.unresolved || 0);
    if (unresolvedDiff !== 0) return unresolvedDiff;
    const minutesDiff = (rankedB.status_summary?.today_minutes || 0) - (rankedA.status_summary?.today_minutes || 0);
    if (minutesDiff !== 0) return minutesDiff;
    return a.id - b.id;
  });
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
  const [refreshMessage, setRefreshMessage] = useState("");
  const [refreshTone, setRefreshTone] = useState<"neutral" | "warning" | "danger" | "success">("neutral");

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  useEffect(() => {
    let mounted = true;

    const bootstrap = async () => {
      if (isDevPreviewEnabled()) {
        if (!mounted) return;
        setUsername(getDevPreviewUsername());
        setWorkspaces([]);
        setSchedule([]);
        setEducationStatus(null);
        setConversations([]);
        setLoading(false);
        return;
      }

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

        const normalizedSchedule = normalizeScheduleData(scheduleJson?.data || []);

        setWorkspaces(workspaceJson?.workspaces || []);
        setSchedule(normalizedSchedule.courses);
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
  const connection = educationStatus?.connection;
  const rankedWorkspaces = useMemo(() => rankWorkspaces(workspaces), [workspaces]);
  const featuredWorkspace = useMemo(() => rankedWorkspaces[0] || null, [rankedWorkspaces]);
  const todayCourses = useMemo(() => schedule.slice(0, 4), [schedule]);
  const recentConversations = useMemo(() => conversations.slice(0, 5), [conversations]);
  const workspaceCount = workspaces.length;

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
      setRefreshMessage("");
      const refreshRes = await fetch(`${API_BASE}/api/refresh?username=${encodeURIComponent(username)}`, {
        method: "POST",
        credentials: "include",
      });
      const refreshJson = refreshRes.ok ? await refreshRes.json().catch(() => null) : await refreshRes.json().catch(() => null);
      if (!refreshRes.ok || !refreshJson?.success) {
        const message = refreshJson?.message || refreshJson?.detail || `刷新失败(${refreshRes.status})`;
        setRefreshTone(refreshRes.status === 401 || refreshRes.status === 403 ? "danger" : "warning");
        setRefreshMessage(message);
        if (refreshRes.status === 401) {
          router.push("/login");
        }
        return;
      }

      setRefreshTone("success");
      setRefreshMessage(refreshJson?.message || "已开始刷新缓存数据");

      const statusRes = await fetch(`${API_BASE}/api/education/status?username=${encodeURIComponent(username)}`, {
        credentials: "include",
      });
      const statusJson = statusRes.ok ? await statusRes.json() : null;
      setEducationStatus(statusJson || null);
      const scheduleRes = await fetch(`${API_BASE}/api/schedule/db?username=${encodeURIComponent(username)}`, {
        credentials: "include",
      });
      const scheduleJson = scheduleRes.ok ? await scheduleRes.json() : null;
      const normalizedSchedule = normalizeScheduleData(scheduleJson?.data || []);
      setSchedule(normalizedSchedule.courses);
    } catch {
      setRefreshTone("danger");
      setRefreshMessage("刷新请求失败，请检查网络或登录状态");
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) return <PageLoading fullScreen label="正在进入学习工作台..." />;

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <GraduationCap className="h-3.5 w-3.5" />
          STUDY HUB
        </WorkbenchBadge>
      }
      title="今天先从哪里开始学习"
      description="把教务缓存、工作区和快速会话收束成一个学习启动页。先判断现在该去哪里，再进入具体页面。"
      sidebarTitle="学习导航"
      sidebarDescription="首页负责启动，工作区负责主复习闭环，聊天页只处理外溢问答。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("home")}
      footer={<PlatformSidebarFooter username={username} detail="当前登录用户" />}
      topActions={
        <>
          <Button
            variant="outline"
            onClick={() => router.push(featuredWorkspace ? `/workspace/${featuredWorkspace.id}` : "/workspace")}
            className="border-slate-300 bg-white/90 text-slate-700 hover:bg-slate-50"
          >
            进入工作区
          </Button>
          <Button onClick={() => router.push("/chat")} className="bg-blue-600 hover:bg-blue-700">
            打开快速会话
          </Button>
        </>
      }
    >
      <div className="grid gap-5">
        {refreshMessage ? <InlineStatusMessage tone={refreshTone}>{refreshMessage}</InlineStatusMessage> : null}
        <section className="grid gap-5 xl:grid-cols-[1.28fr_0.72fr]">
          <Card className="overflow-hidden border-slate-200/90 bg-[radial-gradient(circle_at_top_left,rgba(219,234,254,0.9),transparent_38%),linear-gradient(135deg,#ffffff_0%,#f4f8fc_100%)] shadow-[0_20px_60px_rgba(15,23,42,0.08)]">
            <CardContent className="grid gap-6 p-5 lg:grid-cols-[1.22fr_0.78fr] lg:p-7">
              <div className="space-y-6">
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={freshness.badge}>{freshness.label}</Badge>
                    {connection?.label ? <Badge variant="outline">{connection.label}</Badge> : null}
                  </div>
                  <div className="max-w-xl space-y-3">
                    <h2 className="text-3xl font-semibold tracking-[-0.04em] text-slate-950 lg:text-4xl">
                      {featuredWorkspace ? `先回到「${featuredWorkspace.name}」继续推进` : "先决定今天的学习入口"}
                    </h2>
                    <p className="text-sm leading-7 text-slate-600 lg:text-[15px]">
                      首页不再只是展示课表和会话列表，而是优先告诉你现在该去哪里开始。工作区处理主复习闭环，快速会话只承接临时外溢问题，知识库负责沉淀。
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{workspaceCount} 个工作区</Badge>
                  <Badge variant="outline">{schedule.length || 0} 条课程缓存</Badge>
                  <Badge variant="secondary">{conversations.length} 条会话沉淀</Badge>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Button
                    onClick={() => router.push(featuredWorkspace ? `/workspace/${featuredWorkspace.id}` : "/workspace")}
                    className="bg-slate-950 px-5 text-white hover:bg-slate-800"
                  >
                    打开学习工作区
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => router.push("/knowledge")}
                    className="border-slate-300 bg-white/80 text-slate-700 hover:bg-slate-50"
                  >
                    浏览知识库
                  </Button>
                </div>
              </div>

              <div className="grid gap-3 self-start">
                <div className="rounded-[1.55rem] border border-slate-200 bg-white/92 p-4 shadow-[0_14px_32px_rgba(15,23,42,0.05)]">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">首选入口</div>
                      <div className="mt-1.5 text-base font-semibold text-slate-950">
                        {featuredWorkspace ? featuredWorkspace.name : "工作区入口"}
                      </div>
                    </div>
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                      <Sparkles className="h-5 w-5" />
                    </div>
                  </div>
                  <div className="mt-2 text-sm leading-6 text-slate-600">
                    {featuredWorkspace
                      ? featuredWorkspace.description || "进入工作区，把知识、提问和复习动作放到一条线上。"
                      : "如果还没有工作区，先创建或进入一个学习空间，把问题、资料和复习动作放到同一条线上。"}
                  </div>
                  <Button
                    variant="ghost"
                    className="mt-3 w-full justify-between rounded-2xl bg-slate-50 px-4 text-slate-700 hover:bg-slate-100"
                    onClick={() => router.push(featuredWorkspace ? `/workspace/${featuredWorkspace.id}` : "/workspace")}
                  >
                    立即进入
                    <ArrowUpRight className="h-4 w-4" />
                  </Button>
                </div>

                <div className="rounded-[1.55rem] border border-slate-200 bg-[linear-gradient(135deg,#eff6ff_0%,#ffffff_100%)] p-4 shadow-[0_14px_32px_rgba(15,23,42,0.04)]">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                      <Clock3 className="h-4 w-4 text-blue-600" />
                      教务连接状态
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRefresh}
                      disabled={refreshing}
                      className="border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                    >
                      {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
                      刷新
                    </Button>
                  </div>
                  <div className="mt-3 grid gap-3">
                    <div className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-3">
                      <div className="text-xs text-slate-500">当前状态</div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <Badge variant={connection?.has_live_session ? "success" : connection?.has_cache ? "warning" : "destructive"}>
                          {connection?.label || "未连接"}
                        </Badge>
                        <span className="text-xs text-slate-500">{connection?.binding_status || "pending"}</span>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-3">
                      <div className="text-xs text-slate-500">缓存状态</div>
                      <div className="mt-2 text-sm font-medium text-slate-900">
                        {educationStatus?.has_cache ? "缓存可用，可直接用首页和课表视图" : "暂无缓存，需要先完成一次同步"}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#f7fafc_100%)] shadow-[0_18px_48px_rgba(15,23,42,0.05)]">
            <CardContent className="space-y-4 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <History className="h-4 w-4 text-slate-500" />
                    最近会话入口
                  </div>
                  <div className="mt-1 text-sm leading-6 text-slate-500">
                    这里只保留少量历史入口，不再单独强调“快速会话”这条路径。
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push("/chat")}
                  className="rounded-full text-slate-600 hover:bg-slate-100"
                >
                  全部会话
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>

              <div className="grid gap-3">
                {recentConversations.length === 0 ? (
                  <WorkbenchEmpty
                    title="还没有会话沉淀"
                    description="如果只是临时问题，可以新建一条快速会话；主复习链路仍建议先回工作区。"
                    tone="hint"
                    action={
                      <Button onClick={() => router.push("/chat")} className="bg-blue-600 hover:bg-blue-700">
                        <Plus className="h-4 w-4" />
                        创建新会话
                      </Button>
                    }
                  />
                ) : (
                  recentConversations.slice(0, 3).map((item, index) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => openConversation(item.id)}
                      className="group rounded-[1.3rem] border border-slate-200 bg-white px-4 py-4 text-left shadow-[0_8px_24px_rgba(15,23,42,0.04)] transition hover:-translate-y-[1px] hover:border-slate-300 hover:bg-slate-50"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                              {String(index + 1).padStart(2, "0")}
                            </span>
                            <span className="truncate text-sm font-medium text-slate-900">{item.title}</span>
                          </div>
                          <div className="mt-2 text-xs text-slate-500">{formatRelativeTime(item.created_at)}</div>
                        </div>
                        <ArrowUpRight className="h-4 w-4 shrink-0 text-slate-300 transition group-hover:text-slate-500" />
                      </div>
                    </button>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-5 xl:grid-cols-[1.02fr_0.98fr]">
          <Card className="border-slate-200 bg-white/94 shadow-[0_18px_52px_rgba(15,23,42,0.05)]">
            <CardContent className="space-y-5 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Clock3 className="h-4 w-4 text-blue-600" />
                    课程缓存预览
                  </div>
                  <div className="mt-1 text-sm leading-6 text-slate-500">
                    首页只保留几条课程缓存作为入口预览，完整学期周视图放到课表页处理。
                  </div>
                </div>
                <Button size="sm" onClick={() => router.push("/schedule")} className="bg-blue-600 hover:bg-blue-700">
                  完整课表
                </Button>
              </div>

              {todayCourses.length === 0 ? (
                <WorkbenchEmpty title="暂无课表缓存数据" description="先同步教务缓存，首页才会出现课程预览。" tone="warning" />
              ) : (
                <div className="grid gap-3">
                  {todayCourses.slice(0, 3).map((course, index) => (
                    <div
                      key={`${extractCourseLabel(course, ["课程名称", "课程名", "课程"])}-${index}`}
                      className="grid gap-3 rounded-[1.3rem] border border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#f8fbff_100%)] px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.04)] sm:grid-cols-[auto_1fr_auto]"
                    >
                      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                        <CalendarDays className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-slate-900">
                          {extractCourseLabel(course, ["课程名称", "课程名", "课程"]) || "课程待定"}
                        </div>
                        <div className="mt-1 text-xs leading-6 text-slate-500">
                          {extractCourseLabel(course, ["上课时间", "时间", "节次"]) || "时间待定"}
                        </div>
                        <div className="mt-1 text-xs leading-6 text-slate-500">
                          地点：{extractCourseLabel(course, ["地点", "教室"]) || "地点待定"} · 教师：
                          {extractCourseLabel(course, ["教师", "老师"]) || "教师待定"}
                        </div>
                      </div>
                      <div className="flex items-center">
                        <Badge variant="outline" className="border-blue-200 bg-blue-50 text-blue-700">
                          缓存预览
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#f7fafc_100%)] shadow-[0_18px_52px_rgba(15,23,42,0.05)]">
            <CardContent className="space-y-5 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <LibraryBig className="h-4 w-4 text-indigo-600" />
                    学习资产入口
                  </div>
                  <div className="mt-1 text-sm leading-6 text-slate-500">
                    工作区、知识库和快速会话不再平铺介绍，而是明确各自负责什么。
                  </div>
                </div>
              </div>

              <div className="grid gap-3">
                <button
                  type="button"
                  onClick={() => router.push(featuredWorkspace ? `/workspace/${featuredWorkspace.id}` : "/workspace")}
                  className="rounded-[1.45rem] border border-slate-200 bg-white px-5 py-4 text-left shadow-[0_10px_24px_rgba(15,23,42,0.04)] transition hover:-translate-y-[1px] hover:border-slate-300 hover:bg-slate-50"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <BookOpen className="h-4 w-4 text-teal-600" />
                        工作区
                      </div>
                      <div className="mt-2 text-base font-semibold text-slate-950">
                        {featuredWorkspace ? featuredWorkspace.name : "进入学习工作区"}
                      </div>
                      <div className="mt-2 text-sm leading-6 text-slate-500">
                        在同一处完成知识沉淀、复习闭环和右侧 AI 验证，这是今天最应该优先进入的页面。
                      </div>
                    </div>
                    <ArrowUpRight className="h-4 w-4 shrink-0 text-slate-300" />
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => router.push("/knowledge")}
                  className="rounded-[1.45rem] border border-slate-200 bg-white px-5 py-4 text-left shadow-[0_10px_24px_rgba(15,23,42,0.04)] transition hover:-translate-y-[1px] hover:border-slate-300 hover:bg-slate-50"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <LibraryBig className="h-4 w-4 text-indigo-600" />
                        知识库
                      </div>
                      <div className="mt-2 text-base font-semibold text-slate-950">整理资料与文档片段</div>
                      <div className="mt-2 text-sm leading-6 text-slate-500">
                        适合上传材料、检查文档状态、定位知识片段，不负责主要复习动作。
                      </div>
                    </div>
                    <ArrowUpRight className="h-4 w-4 shrink-0 text-slate-300" />
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => router.push("/chat")}
                  className="rounded-[1.45rem] border border-slate-200 bg-white px-5 py-4 text-left shadow-[0_10px_24px_rgba(15,23,42,0.04)] transition hover:-translate-y-[1px] hover:border-slate-300 hover:bg-slate-50"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <MessageSquare className="h-4 w-4 text-blue-600" />
                        快速会话
                      </div>
                      <div className="mt-2 text-base font-semibold text-slate-950">处理即时问题</div>
                      <div className="mt-2 text-sm leading-6 text-slate-500">
                        用于快速起问、临时深挖、打开历史会话，不替代工作区里的长期学习链路。
                      </div>
                    </div>
                    <ArrowUpRight className="h-4 w-4 shrink-0 text-slate-300" />
                  </div>
                </button>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </WorkbenchShell>
  );
}
