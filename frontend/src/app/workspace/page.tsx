'use client';

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Database, LayoutGrid, Plus } from "lucide-react";

import { PlatformSidebarFooter, PlatformSidebarHeader, createPlatformNav } from "@/components/workspace/app-sidebar";
import {
  WorkbenchBadge,
  WorkbenchEmpty,
  WorkbenchSection,
  WorkbenchShell,
  WorkbenchStatCard,
} from "@/components/workspace/workbench-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
};

export default function WorkspacePage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceDesc, setWorkspaceDesc] = useState("");
  const [msg, setMsg] = useState("");

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const refreshWorkspaces = async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}`, { credentials: "include" });
    const json = res.ok ? await res.json() : null;
    setWorkspaces(json?.workspaces || []);
  };

  useEffect(() => {
    const run = async () => {
      try {
        const meRes = await fetch(`${API_BASE}/api/auth/me`, { credentials: "include" });
        const me = meRes.ok ? await meRes.json() : null;
        if (!me?.authenticated || !me?.username) {
          router.replace("/login");
          return;
        }
        const uname = String(me.username);
        setUsername(uname);
        await refreshWorkspaces(uname);
      } catch {
        router.replace("/chat");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [API_BASE, router]);

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

  if (loading) return <div className="p-6 text-sm text-slate-500">加载中...</div>;

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <LayoutGrid className="h-3.5 w-3.5" />
          WORKSPACES
        </WorkbenchBadge>
      }
      title="工作区入口"
      description="这里负责选择和创建工作区。进入具体工作区后，会切到三栏详情工作台。"
      sidebarTitle="工作区系统"
      sidebarDescription="保持 `/workspace` 作为入口页，`/workspace/[id]` 作为详情页。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("workspace")}
      footer={<PlatformSidebarFooter username={username} detail="Workspace owner" />}
      topActions={
        <>
          <Button variant="outline" onClick={() => router.push("/chat")}>快速会话</Button>
          <Button onClick={createWorkspace} disabled={saving || !workspaceName.trim()}>创建工作区</Button>
        </>
      }
    >
      <div className="grid gap-4 lg:grid-cols-[0.92fr_1.08fr]">
        <div className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <WorkbenchStatCard label="Workspaces" value={workspaces.length} hint="当前账号的工作区数量" />
            <WorkbenchStatCard label="Default" value={workspaces.some((item) => item.is_default) ? "Yes" : "No"} hint="默认工作区是否存在" />
            <WorkbenchStatCard label="Owner" value={username || "-"} hint="当前隔离主体" />
          </div>

          <WorkbenchSection title="创建工作区" description="通过入口页创建新工作区，创建后直接进入详情页。">
            <div className="space-y-3">
              <Input value={workspaceName} onChange={(e) => setWorkspaceName(e.target.value)} placeholder="例如：高数学习" />
              <Textarea
                value={workspaceDesc}
                onChange={(e) => setWorkspaceDesc(e.target.value)}
                placeholder="描述工作区用途，例如课程复习、竞赛资料、研究项目。"
                className="min-h-28"
              />
              <Button onClick={createWorkspace} disabled={saving || !workspaceName.trim()}>
                <Plus className="h-4 w-4" />
                {saving ? "创建中..." : "创建并进入"}
              </Button>
            </div>
          </WorkbenchSection>

          {msg ? (
            <Card className="border-slate-200 bg-slate-50 shadow-none">
              <CardContent className="p-4 text-sm text-slate-700">{msg}</CardContent>
            </Card>
          ) : null}
        </div>

        <WorkbenchSection title="工作区列表" description="选择一个工作区，进入对应详情页。">
          <ScrollArea className="h-[680px] pr-3">
            <div className="space-y-3">
              {workspaces.length === 0 ? (
                <WorkbenchEmpty title="还没有任何工作区" description="创建一个开始沉淀文档、知识和能力。" />
              ) : null}
              {workspaces.map((item) => (
                <button
                  key={item.id}
                  onClick={() => router.push(`/workspace/${item.id}`)}
                  className={cn(
                    "w-full rounded-2xl border border-slate-200 bg-white p-4 text-left transition-colors hover:bg-slate-50"
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="text-sm font-semibold text-slate-950">{item.name}</div>
                      <div className="text-xs leading-5 text-slate-500">{item.description || item.slug}</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {item.is_default ? <Badge variant="secondary">默认</Badge> : null}
                      <Badge variant="outline">#{item.id}</Badge>
                    </div>
                  </div>
                  <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
                    <span>{item.slug}</span>
                    <span className="flex items-center gap-1 text-slate-500">
                      <Database className="h-3.5 w-3.5" />
                      进入详情
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </ScrollArea>
        </WorkbenchSection>
      </div>
    </WorkbenchShell>
  );
}