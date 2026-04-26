'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, Blocks, Bot, LibraryBig, Network, Wrench } from "lucide-react";

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
import { ScrollArea } from "@/components/ui/scroll-area";

type CompositionData = {
  owner: string;
  skills: string[];
  all_skills: string[];
  mcp_tools: string[];
  all_mcp_tools: string[];
  profile: {
    skills?: { entries?: Record<string, { enabled?: boolean; priority?: number }> };
    mcp?: {
      entries?: Record<string, { enabled?: boolean; weight?: number }>;
      order?: string[];
    };
  };
};

type PlatformSkill = {
  id: number;
  name: string;
  version?: string;
  description?: string;
  enabled: boolean;
  triggers: string[];
  input_schema?: Record<string, unknown>;
  tools: Array<{ name?: string; description?: string }>;
  mode?: string;
  compatibility_level?: string;
  compatibility_notes?: string[];
  capabilities?: string[];
  always_on?: boolean;
  source_type?: string;
  source_ref?: string;
};

type PlatformMcp = {
  id: number;
  name: string;
  description?: string;
  kind: string;
  enabled: boolean;
  source_type?: string;
  source_ref?: string;
  transport?: string;
  compatibility_level?: string;
  compatibility_notes?: string[];
  capabilities?: string[];
  tool_schema?: {
    parameters?: Record<string, { type?: string; required?: boolean; description?: string }>;
  };
};

type WorkspaceItem = {
  id: number;
  slug: string;
  name: string;
  description?: string;
  is_default: boolean;
};

export default function CompositionPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [data, setData] = useState<CompositionData | null>(null);
  const [platformSkills, setPlatformSkills] = useState<PlatformSkill[]>([]);
  const [platformMcpTools, setPlatformMcpTools] = useState<PlatformMcp[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [workspaceId, setWorkspaceId] = useState<number | null>(null);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const refresh = async (uname: string) => {
    const [compositionRes, skillsRes, mcpRes, workspaceRes, prefRes] = await Promise.all([
      fetch(`${API_BASE}/api/composition/${encodeURIComponent(uname)}`, { credentials: "include" }),
      fetch(`${API_BASE}/api/platform/${encodeURIComponent(uname)}/skills`, { credentials: "include" }),
      fetch(`${API_BASE}/api/platform/${encodeURIComponent(uname)}/mcp`, { credentials: "include" }),
      fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}`, { credentials: "include" }),
      fetch(`${API_BASE}/api/workspace-preference/${encodeURIComponent(uname)}`, { credentials: "include" }),
    ]);
    const compositionJson = compositionRes.ok ? await compositionRes.json() : null;
    const skillsJson = skillsRes.ok ? await skillsRes.json() : null;
    const mcpJson = mcpRes.ok ? await mcpRes.json() : null;
    const workspaceJson = workspaceRes.ok ? await workspaceRes.json() : null;
    const prefJson = prefRes.ok ? await prefRes.json() : null;
    setData(compositionJson?.data || null);
    setPlatformSkills(skillsJson?.skills || []);
    setPlatformMcpTools(mcpJson?.mcp_tools || []);
    const workspaceItems: WorkspaceItem[] = workspaceJson?.workspaces || [];
    setWorkspaces(workspaceItems);
    const preferredWorkspace =
      workspaceItems.find((item) => item.id === prefJson?.workspace_id) ||
      workspaceItems[0] ||
      null;
    setWorkspaceId(preferredWorkspace?.id || null);
  };

  const updateWorkspacePreference = async (uname: string, nextWorkspaceId: number) => {
    const nextWorkspace = workspaces.find((item) => item.id === nextWorkspaceId);
    if (!nextWorkspace) return;
    await fetch(`${API_BASE}/api/workspace-preference`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        username: uname,
        workspace_id: nextWorkspace.id,
        workspace_name: nextWorkspace.name,
      }),
    });
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
        await refresh(uname);
      } catch {
        router.replace("/chat");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [API_BASE, router]);

  const skillEnabled = (name: string) => {
    if (!data) return true;
    const cfg = data.profile?.skills?.entries?.[name];
    if (!cfg) return true;
    return cfg.enabled !== false;
  };

  const mcpEnabled = (name: string) => {
    if (!data) return true;
    const cfg = data.profile?.mcp?.entries?.[name];
    if (!cfg) return true;
    return cfg.enabled !== false;
  };

  const toggleSkill = async (skillName: string, enabled: boolean) => {
    if (!username) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/composition/skills`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, skill_name: skillName, enabled, priority: 50 }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok || !j?.success) throw new Error(j?.detail || j?.message || `保存失败(${res.status})`);
      await refresh(username);
      setMsg("Skill 组合已更新");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const toggleMcp = async (toolName: string, enabled: boolean) => {
    if (!username) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/composition/mcp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, tool_name: toolName, enabled, weight: 50 }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok || !j?.success) throw new Error(j?.detail || j?.message || `保存失败(${res.status})`);
      await refresh(username);
      setMsg("MCP 组合已更新");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const reorderMcp = async (nextOrder: string[]) => {
    if (!username) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/composition/mcp/reorder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, order: nextOrder }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok || !j?.success) throw new Error(j?.detail || j?.message || `排序保存失败(${res.status})`);
      await refresh(username);
      setMsg("MCP 顺序已更新");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "排序保存失败");
    } finally {
      setSaving(false);
    }
  };

  const skillList = useMemo(() => {
    const arr = data?.all_skills || [];
    return [...arr].sort((a, b) => a.localeCompare(b));
  }, [data]);

  const mcpList = useMemo(() => {
    const ordered = data?.mcp_tools || [];
    const all = data?.all_mcp_tools || [];
    const set = new Set(ordered);
    return [...ordered, ...all.filter((x) => !set.has(x))];
  }, [data]);

  const move = async (idx: number, dir: -1 | 1) => {
    const to = idx + dir;
    if (to < 0 || to >= mcpList.length) return;
    const next = [...mcpList];
    const [item] = next.splice(idx, 1);
    next.splice(to, 0, item);
    await reorderMcp(next);
  };

  const enabledSkillDetails = useMemo(() => {
    const enabledNames = new Set(data?.skills || []);
    return platformSkills.filter((item) => enabledNames.has(item.name));
  }, [data, platformSkills]);

  const enabledMcpDetails = useMemo(() => {
    const enabledNames = new Set(data?.mcp_tools || []);
    return platformMcpTools.filter((item) => enabledNames.has(item.name));
  }, [data, platformMcpTools]);

  const compositionSuggestions = useMemo(() => {
    const items: string[] = [];
    if (enabledSkillDetails.length === 0) {
      items.push("先启用至少一个 Skill，不然工作区无法形成真正的能力路由。");
    }
    if (enabledMcpDetails.length === 0) {
      items.push("当前没有 MCP，被启用的 Skill 最终还是只能退化为模型读上下文。");
    }
    if (enabledSkillDetails.length > 0 && enabledMcpDetails.length === 0) {
      items.push("现在最适合补一个执行类或检索类 MCP，让 Skill 有真实工具可调用。");
    }
    if (enabledSkillDetails.length > 0 && enabledMcpDetails.length > 0) {
      items.push("当前已经具备组合基础，可以直接进工作区或聊天页验证 tool trace 和知识命中。");
    }
    if (!workspaceId) {
      items.push("先绑定一个工作区，再去做知识导入和对话验证，不要让编排脱离上下文。");
    }
    return items.slice(0, 3);
  }, [enabledMcpDetails.length, enabledSkillDetails.length, workspaceId]);

  const currentWorkspace = useMemo(
    () => workspaces.find((item) => item.id === workspaceId) || null,
    [workspaces, workspaceId]
  );

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">加载中...</div>;
  }

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <Network className="h-3.5 w-3.5" />
          COMPOSITION
        </WorkbenchBadge>
      }
      title="Skill / MCP 组合编排"
      description="用户侧拼积木入口。这里决定某个账号默认启用哪些 Skill、哪些 MCP，以及 MCP 的执行顺序。"
      sidebarTitle="组合路由"
      sidebarDescription="保持用户体验简单，但底层保留自由拼接能力。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("composition")}
      footer={<PlatformSidebarFooter username={username} detail="Composition owner" />}
      topActions={
        <>
          <Button variant="outline" onClick={() => router.push("/skills")}>
            Skill 管理
          </Button>
          <Button variant="outline" onClick={() => router.push("/mcp")}>
            MCP 管理
          </Button>
          <Button onClick={() => router.push(workspaceId ? `/workspace/${workspaceId}` : "/workspace")}>
            打开工作区
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <div className="grid gap-4 md:grid-cols-4">
          <WorkbenchStatCard label="Skill" value={skillList.length} hint="平台已注册 Skill" />
          <WorkbenchStatCard label="MCP" value={mcpList.length} hint="平台可编排 MCP" />
          <WorkbenchStatCard label="Owner" value={data?.owner || username || "-"} hint="当前组合主体" />
          <WorkbenchStatCard label="Workspace" value={currentWorkspace?.name || "-"} hint="当前绑定的验证工作区" />
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <WorkbenchSection title="运行态摘要" description="不是只看可用对象，而是看当前组合真正启用了什么。">
            <div className="grid gap-3 md:grid-cols-2">
              <Card className="bg-slate-50 shadow-none">
                <CardContent className="space-y-2 p-4">
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    <Blocks className="h-3.5 w-3.5" />
                    Enabled Skills
                  </div>
                  <div className="text-3xl font-semibold text-slate-950">{enabledSkillDetails.length}</div>
                  <div className="text-xs text-slate-500">
                    {enabledSkillDetails.map((item) => item.name).join(", ") || "尚未启用"}
                  </div>
                </CardContent>
              </Card>
              <Card className="bg-slate-50 shadow-none">
                <CardContent className="space-y-2 p-4">
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    <Wrench className="h-3.5 w-3.5" />
                    Enabled MCP
                  </div>
                  <div className="text-3xl font-semibold text-slate-950">{enabledMcpDetails.length}</div>
                  <div className="text-xs text-slate-500">
                    {enabledMcpDetails.map((item) => item.name).join(", ") || "尚未启用"}
                  </div>
                </CardContent>
              </Card>
            </div>
            <div className="mt-4 space-y-2">
              <div className="text-sm font-medium text-slate-900">绑定工作区</div>
              <div className="flex flex-wrap gap-2">
                <select
                  value={workspaceId ?? ""}
                  onChange={async (e) => {
                    const nextId = Number(e.target.value || 0);
                    setWorkspaceId(nextId || null);
                    if (nextId && username) {
                      await updateWorkspacePreference(username, nextId);
                    }
                  }}
                  className="h-10 min-w-[220px] rounded-xl border border-[hsl(var(--border))] bg-white px-3 text-sm outline-none"
                >
                  {workspaces.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
                <Button variant="outline" onClick={() => router.push(workspaceId ? `/knowledge?workspace_id=${workspaceId}` : "/knowledge")}>
                  <LibraryBig className="h-4 w-4" />
                  这个工作区的知识库
                </Button>
                <Button variant="outline" onClick={() => router.push(workspaceId ? `/chat?workspace_id=${workspaceId}` : "/chat")}>
                  <Bot className="h-4 w-4" />
                  这个工作区的聊天验证
                </Button>
              </div>
            </div>
          </WorkbenchSection>

          <WorkbenchSection
            title="联动建议"
            description="这块的目的是把 Skill / MCP / 工作区 / 聊天 串起来，而不是只做开关页。"
            actions={
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => router.push(workspaceId ? `/knowledge?workspace_id=${workspaceId}` : "/knowledge")}>
                  <LibraryBig className="h-4 w-4" />
                  知识库管理台
                </Button>
                <Button size="sm" onClick={() => router.push(workspaceId ? `/workspace/${workspaceId}` : "/workspace")}>
                  <Bot className="h-4 w-4" />
                  进入工作区验证
                </Button>
              </div>
            }
          >
            <div className="space-y-3">
              {compositionSuggestions.map((item, index) => (
                <Card key={`${index}-${item}`} className="border-slate-200 bg-slate-50 shadow-none">
                  <CardContent className="p-4 text-sm leading-6 text-slate-700">{item}</CardContent>
                </Card>
              ))}
            </div>
          </WorkbenchSection>
        </div>

        {msg ? (
          <Card className="border-slate-200 bg-slate-50 shadow-none">
            <CardContent className="p-4 text-sm text-slate-700">{msg}</CardContent>
          </Card>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-2">
          <WorkbenchSection title="Skill 拼装" description="启停 Skill，决定路由是否允许进入对应能力链路。">
            <ScrollArea className="h-[620px] pr-3">
              <div className="space-y-3">
                {skillList.length === 0 ? (
                  <WorkbenchEmpty title="暂无 Skill" description="先去 Skill 管理页导入 manifest，再回这里拼装。" />
                ) : null}
                {skillList.map((skill) => (
                  <Card key={skill} className="border-slate-200 shadow-none">
                    <CardContent className="flex items-center justify-between gap-3 p-4">
                      <div className="space-y-1">
                        <div className="text-sm font-semibold text-slate-950">{skill}</div>
                        <div className="text-xs text-slate-500">
                          {platformSkills.find((item) => item.name === skill)?.description || "当前状态由用户侧 profile 控制。"}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="outline">{platformSkills.find((item) => item.name === skill)?.mode || "rule"}</Badge>
                          <Badge variant="secondary">{platformSkills.find((item) => item.name === skill)?.compatibility_level || "direct"}</Badge>
                          {platformSkills.find((item) => item.name === skill)?.source_type ? (
                            <Badge variant="outline">{platformSkills.find((item) => item.name === skill)?.source_type}</Badge>
                          ) : null}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          capabilities: {(platformSkills.find((item) => item.name === skill)?.capabilities || []).join(", ") || "-"}
                        </div>
                        {platformSkills.find((item) => item.name === skill)?.input_schema ? (
                          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] leading-5 text-slate-600">
                            schema: {JSON.stringify(platformSkills.find((item) => item.name === skill)?.input_schema || {})}
                          </div>
                        ) : null}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={skillEnabled(skill) ? "success" : "outline"}>
                          {skillEnabled(skill) ? "enabled" : "disabled"}
                        </Badge>
                        <Button size="sm" variant="outline" disabled={saving} onClick={() => toggleSkill(skill, !skillEnabled(skill))}>
                          {skillEnabled(skill) ? "禁用" : "启用"}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          </WorkbenchSection>

          <WorkbenchSection title="MCP 拼装" description="启停 MCP 并调整顺序，影响工具选择优先级。">
            <ScrollArea className="h-[620px] pr-3">
              <div className="space-y-3">
                {mcpList.length === 0 ? (
                  <WorkbenchEmpty title="暂无 MCP" description="先去 MCP 管理页导入或探测可用工具。" />
                ) : null}
                {mcpList.map((tool, idx) => (
                  <Card key={tool} className="border-slate-200 shadow-none">
                    <CardContent className="space-y-3 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="space-y-1">
                          <div className="text-sm font-semibold text-slate-950">{tool}</div>
                          <div className="text-xs text-slate-500">
                            {platformMcpTools.find((item) => item.name === tool)?.description || "顺序越靠前，工具路由权重越高。"}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <Badge variant="outline">{platformMcpTools.find((item) => item.name === tool)?.transport || platformMcpTools.find((item) => item.name === tool)?.kind || "python"}</Badge>
                            <Badge variant="secondary">{platformMcpTools.find((item) => item.name === tool)?.compatibility_level || "direct"}</Badge>
                            {platformMcpTools.find((item) => item.name === tool)?.source_type ? (
                              <Badge variant="outline">{platformMcpTools.find((item) => item.name === tool)?.source_type}</Badge>
                            ) : null}
                          </div>
                          <div className="text-[11px] text-slate-500">
                            capabilities: {(platformMcpTools.find((item) => item.name === tool)?.capabilities || []).join(", ") || "-"}
                          </div>
                          {platformMcpTools.find((item) => item.name === tool)?.tool_schema?.parameters ? (
                            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] leading-5 text-slate-600">
                              params: {JSON.stringify(platformMcpTools.find((item) => item.name === tool)?.tool_schema?.parameters || {})}
                            </div>
                          ) : null}
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={mcpEnabled(tool) ? "success" : "outline"}>
                            {mcpEnabled(tool) ? "enabled" : "disabled"}
                          </Badge>
                          <Button size="sm" variant="outline" disabled={saving} onClick={() => toggleMcp(tool, !mcpEnabled(tool))}>
                            {mcpEnabled(tool) ? "禁用" : "启用"}
                          </Button>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="outline" disabled={saving || idx === 0} onClick={() => move(idx, -1)}>
                          <ArrowUp className="h-4 w-4" />
                          上移
                        </Button>
                        <Button size="sm" variant="outline" disabled={saving || idx === mcpList.length - 1} onClick={() => move(idx, 1)}>
                          <ArrowDown className="h-4 w-4" />
                          下移
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          </WorkbenchSection>
        </div>
      </div>
    </WorkbenchShell>
  );
}
