'use client';

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Brain, Database, FlagTriangleRight, LayoutGrid, Plus } from "lucide-react";

import { PlatformSidebarFooter, PlatformSidebarHeader, createPlatformNav } from "@/components/workspace/app-sidebar";
import {
  WorkbenchBadge,
  WorkbenchEmpty,
  WorkbenchSection,
  WorkbenchShell,
} from "@/components/workspace/workbench-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InlineStatusMessage, PageLoading } from "@/components/ui/feedback";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type WorkspaceItem = {
  id: number;
  slug: string;
  name: string;
  description?: string;
  is_default: boolean;
  learning_summary?: {
    unresolved: number;
    resolved: number;
    recommended_followup?: {
      headline: string;
      content: string;
      source_label?: string;
      reason?: string;
      memory_id?: number;
      course_name?: string;
      question_type?: string;
      strategy?: string;
    } | null;
  };
  status_summary?: {
    today_minutes: number;
    today_prompts: number;
    documents: number;
  };
};

export default function WorkspacePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceDesc, setWorkspaceDesc] = useState("");
  const [msg, setMsg] = useState("");

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;
  const { username, authLoading } = useRequireAuth(API_BASE);
  const rankedWorkspaces = useMemo(() => {
    return [...workspaces].sort((a, b) => {
      const unresolvedDiff = (b.learning_summary?.unresolved || 0) - (a.learning_summary?.unresolved || 0);
      if (unresolvedDiff !== 0) return unresolvedDiff;
      const minutesDiff = (b.status_summary?.today_minutes || 0) - (a.status_summary?.today_minutes || 0);
      if (minutesDiff !== 0) return minutesDiff;
      return a.id - b.id;
    });
  }, [workspaces]);
  const nextWorkspace = rankedWorkspaces[0] || null;

  const refreshWorkspaces = useCallback(async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}`, { credentials: "include" });
    const json = res.ok ? await res.json() : null;
    setWorkspaces(json?.workspaces || []);
  }, [API_BASE]);

  useEffect(() => {
    if (authLoading || !username) return;
    const run = async () => {
      try {
        await refreshWorkspaces(username);
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [authLoading, refreshWorkspaces, username]);

  const createWorkspace = async () => {
    if (!username || !workspaceName.trim()) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/workspace`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          username,
          name: workspaceName.trim(),
          description: workspaceDesc.trim(),
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json?.success) throw new Error(json?.detail || `创建失败(${res.status})`);
      setWorkspaceName("");
      setWorkspaceDesc("");
      await refreshWorkspaces(username);
      if (json?.workspace?.id) {
        router.push(`/workspace/${json.workspace.id}`);
        return;
      }
      setMsg("工作区已创建");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "创建失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading || authLoading) return <PageLoading label="正在加载工作区..." />;

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <LayoutGrid className="h-3.5 w-3.5" />
          WORKSPACES
        </WorkbenchBadge>
      }
      title="工作区入口"
      description="这里负责选择和创建工作区。进入具体工作区后，会切到以右侧对话为主的详情工作台。"
      sidebarTitle="工作区系统"
      sidebarDescription="保持 `/workspace` 作为入口页，`/workspace/[id]` 作为详情页。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("workspace")}
      footer={<PlatformSidebarFooter username={username} detail="Workspace owner" />}
      topActions={
        <>
          <Button
            variant="outline"
            className="border-slate-300 bg-white/90 text-slate-700 hover:bg-slate-50"
            onClick={() => router.push("/chat")}
          >
            快速会话
          </Button>
          <Button
            className="bg-blue-600 shadow-[0_14px_30px_rgba(31,111,235,0.22)] hover:bg-blue-700"
            onClick={createWorkspace}
            disabled={saving || !workspaceName.trim()}
          >
            创建工作区
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <div className="rounded-[1.7rem] border border-slate-200/90 bg-[linear-gradient(135deg,rgba(255,255,255,0.98),rgba(244,248,252,0.96)_56%,rgba(239,246,255,0.88))] px-5 py-5 shadow-[0_18px_46px_rgba(15,23,42,0.05)]">
          <div className="grid gap-4 xl:grid-cols-[1.18fr_0.82fr]">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{workspaces.length} 个工作区</Badge>
                <Badge variant="outline">{workspaces.some((item) => item.is_default) ? "已有默认工作区" : "暂无默认工作区"}</Badge>
                <Badge variant="secondary">{username || "-"}</Badge>
              </div>
              <div className="max-w-3xl">
                <div className="text-xl font-semibold tracking-[-0.03em] text-slate-950">这里先解决一个问题：我现在应该回哪个空间继续。</div>
                <div className="mt-2 text-sm leading-6 text-slate-600">
                  入口页不再同时强调统计、说明和表单。优先返回已有工作区；只有确实没有合适空间时，再创建新的学习空间。
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {nextWorkspace ? (
                  <Button onClick={() => router.push(`/workspace/${nextWorkspace.id}`)}>
                    <Brain className="h-4 w-4" />
                    继续 {nextWorkspace.name}
                  </Button>
                ) : (
                  <Button onClick={createWorkspace} disabled={saving || !workspaceName.trim()}>
                    <Plus className="h-4 w-4" />
                    直接创建工作区
                  </Button>
                )}
                <Button
                  variant="outline"
                  className="border-slate-300 bg-white/90 text-slate-700 hover:bg-slate-50"
                  onClick={() => router.push("/chat")}
                >
                  快速会话
                </Button>
              </div>
            </div>

            {nextWorkspace ? (
              <div className="rounded-[1.5rem] border border-amber-200 bg-[linear-gradient(135deg,rgba(255,247,237,0.96),rgba(255,255,255,0.98))] p-5 shadow-[0_12px_30px_rgba(15,23,42,0.04)]">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <FlagTriangleRight className="h-4 w-4 text-amber-500" />
                  建议优先返回
                </div>
                <div className="mt-3 text-lg font-semibold text-slate-950">{nextWorkspace.name}</div>
                <div className="mt-2 text-sm leading-6 text-slate-600">
                  {nextWorkspace.learning_summary?.recommended_followup?.headline
                    || nextWorkspace.description
                    || nextWorkspace.slug}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge variant="outline">未解决 {nextWorkspace.learning_summary?.unresolved || 0}</Badge>
                  <Badge variant="outline">今日 {nextWorkspace.status_summary?.today_minutes || 0} min</Badge>
                  <Badge variant="secondary">资料 {nextWorkspace.status_summary?.documents || 0}</Badge>
                </div>
              </div>
            ) : (
              <div className="rounded-[1.5rem] border border-dashed border-slate-300 bg-[linear-gradient(180deg,rgba(248,250,252,0.94),rgba(255,255,255,0.98))] p-5">
                <div className="text-sm font-semibold text-slate-900">还没有可返回的工作区</div>
                <div className="mt-2 text-sm leading-6 text-slate-600">
                  先在右侧定义一个学习目标，再把资料、提问和复习动作沉淀进去。
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.28fr_0.72fr]">
          <div className="grid gap-4">

          <WorkbenchSection
            title="继续已有工作区"
            description="把已有空间按“最值得先回去”的顺序排出来，列表只保留与决策有关的信息。"
          >
            <ScrollArea className="h-[720px] pr-3">
              <div className="space-y-3">
                {workspaces.length === 0 ? (
                  <WorkbenchEmpty title="还没有任何工作区" description="先在右侧创建一个工作区，开始沉淀文档、知识和复习链路。" tone="hint" />
                ) : null}
                {rankedWorkspaces.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => router.push(`/workspace/${item.id}`)}
                    className={cn(
                      "w-full rounded-[1.45rem] border border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.96))] p-4 text-left transition-all hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-[0_14px_32px_rgba(15,23,42,0.06)]"
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="text-sm font-semibold text-slate-950">{item.name}</div>
                          {item.is_default ? <Badge variant="secondary">默认</Badge> : null}
                        </div>
                        <div className="text-xs leading-6 text-slate-500">{item.description || item.slug}</div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">#{item.id}</Badge>
                      </div>
                    </div>
                    <div className="mt-4 flex items-center justify-between rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2 text-xs text-slate-400">
                      <span className="truncate">{item.slug}</span>
                      <span className="flex items-center gap-1 font-medium text-slate-600">
                        <Database className="h-3.5 w-3.5" />
                        进入工作区
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge variant="outline">未解决 {item.learning_summary?.unresolved || 0}</Badge>
                      <Badge variant="outline">今日 {item.status_summary?.today_minutes || 0} min</Badge>
                      <Badge variant="secondary">资料 {item.status_summary?.documents || 0}</Badge>
                    </div>
                    {item.learning_summary?.recommended_followup?.headline ? (
                      <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50/70 px-3 py-3 text-xs leading-6 text-slate-700">
                        <div className="mb-1 font-medium text-slate-900">下一步建议</div>
                        <div>{item.learning_summary.recommended_followup.headline}</div>
                      </div>
                    ) : null}
                  </button>
                ))}
              </div>
            </ScrollArea>
          </WorkbenchSection>

          {msg ? <InlineStatusMessage>{msg}</InlineStatusMessage> : null}
        </div>

        <WorkbenchSection
          title="新建工作区"
          description="新建动作收敛成一个简洁表单。按单门课、单类任务或单阶段目标来建会更稳。"
        >
          <div className="space-y-4">
            <div className="rounded-[1.45rem] border border-dashed border-slate-300 bg-[linear-gradient(180deg,rgba(248,250,252,0.94),rgba(255,255,255,0.98))] p-4">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Workspace Brief</div>
              <div className="mb-3 text-sm font-medium text-slate-900">先定义这个空间的学习目标</div>
              <div className="space-y-3">
                <Input
                  value={workspaceName}
                  onChange={(e) => setWorkspaceName(e.target.value)}
                  placeholder="例如：高数学习 / 计算机网络期末 / 比赛资料整理"
                  className="border-slate-200 bg-white shadow-none"
                />
                <Textarea
                  value={workspaceDesc}
                  onChange={(e) => setWorkspaceDesc(e.target.value)}
                  placeholder="描述工作区用途，例如课程复习、竞赛资料、研究项目。"
                  className="min-h-28 border-slate-200 bg-white shadow-none"
                />
              </div>
            </div>

            <div className="grid gap-3">
              <div className="rounded-2xl border border-blue-100 bg-[linear-gradient(135deg,rgba(219,234,254,0.7),rgba(255,255,255,0.96)_56%,rgba(247,250,252,0.98))] px-4 py-4 text-sm text-slate-600">
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-blue-700">Recommended Use</div>
                <div className="mt-2 leading-6">
                  不要把所有资料都堆进一个大空间。按单门课、单类任务或单阶段目标拆开，更利于后续沉淀和复习。
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-4 text-sm text-slate-600">
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">建议命名</div>
                <div className="mt-2 leading-6">
                  例如：`高数期末复习`、`计网作业整理`、`比赛资料沉淀`。名字越具体，后续越容易判断该回哪个空间。
                </div>
              </div>
            </div>

            <Button
              className="bg-blue-600 shadow-[0_14px_28px_rgba(31,111,235,0.18)] hover:bg-blue-700"
              onClick={createWorkspace}
              disabled={saving || !workspaceName.trim()}
            >
              <Plus className="h-4 w-4" />
              {saving ? "创建中..." : "创建并进入"}
            </Button>
          </div>
        </WorkbenchSection>
      </div>
      </div>
    </WorkbenchShell>
  );
}


