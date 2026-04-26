'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Activity, Github, KeyRound, RefreshCcw, SearchCheck, ShieldAlert, Trash2, Upload, Wrench } from "lucide-react";

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

type MCPTool = {
  name: string;
  description: string;
  kind?: string;
  parameters?: Record<string, { type?: string; required?: boolean; description?: string }>;
  enabled?: boolean;
  source_type?: string;
  source_ref?: string;
  transport?: string;
  compatibility_level?: string;
  compatibility_notes?: string[];
  capabilities?: string[];
  execution_boundary?: string;
  execution_boundary_notes?: string[];
  web_enabled?: boolean;
  service_scope?: string;
};

type ProbeResult = {
  success: boolean;
  tool: string;
  ready: boolean;
  boundary: string;
  service_scope: string;
  transport: string;
  kind: string;
  checks: Array<{ name: string; ok: boolean; detail: string }>;
};

type PipelineItem = {
  run_id?: string;
  started_at?: string;
  duration_ms?: number;
  reload_count?: number;
  success?: boolean;
  timing_ms?: Record<string, number>;
  error?: string;
};

type PipelineState = {
  running?: boolean;
  run_id?: string;
  started_at?: string;
  status?: string;
  finished_at?: string;
  error?: string;
};

type PipelineTask = {
  run_id: string;
  created_at?: string;
  status?: "running" | "success" | "failed" | string;
  duration_ms?: number;
  reload_count?: number;
  snapshot?: string;
  error?: string;
  priority?: "high" | "normal" | "low" | string;
  retries?: number;
  max_retries?: number;
  next_run_at?: string;
  last_error?: string;
};

type AgentToken = {
  id: number;
  token_name: string;
  token_prefix: string;
  status: string;
  scope_json?: Record<string, unknown>;
  last_used_at?: string | null;
  expires_at?: string | null;
  created_at?: string | null;
};

type ServiceBinding = {
  id: number;
  service_name: string;
  auth_type: string;
  status: string;
  display_name?: string | null;
  metadata_json?: Record<string, unknown>;
  last_verified_at?: string | null;
  expires_at?: string | null;
};

type AgentAccessState = {
  tokens: AgentToken[];
  bindings: ServiceBinding[];
  login_policy?: {
    web_login_source?: string;
    agent_rule?: string;
  };
};

const COMPATIBILITY_LABELS: Record<string, string> = {
  direct: "可直接使用",
  adapted: "需要适配",
  rule_only: "仅规则注入",
  incompatible: "暂不兼容",
};

const BOUNDARY_LABELS: Record<string, string> = {
  hosted_web: "Web 可托管",
  remote_service: "远程服务",
  agent_local_only: "仅本地 Agent",
  unsupported: "暂不支持",
};

export default function MCPPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [importedTools, setImportedTools] = useState<MCPTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [importUrl, setImportUrl] = useState("");
  const [history, setHistory] = useState<PipelineItem[]>([]);
  const [tasks, setTasks] = useState<PipelineTask[]>([]);
  const [state, setState] = useState<PipelineState | null>(null);
  const [queueSize, setQueueSize] = useState(0);
  const [runningCount, setRunningCount] = useState(0);
  const [priority, setPriority] = useState<"high" | "normal" | "low">("normal");
  const [probeMap, setProbeMap] = useState<Record<string, ProbeResult>>({});
  const [agentAccess, setAgentAccess] = useState<AgentAccessState | null>(null);
  const [agentTokenName, setAgentTokenName] = useState("OpenClaw");
  const [createdAgentToken, setCreatedAgentToken] = useState("");

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const refreshTools = async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/mcp/tools?username=${encodeURIComponent(uname)}`, { credentials: "include" });
    const data = res.ok ? await res.json() : null;
    setTools(data?.tools || []);
    setImportedTools(data?.imported_tools || []);
  };

  const refreshHistory = async () => {
    const res = await fetch(`${API_BASE}/api/intake/pipeline/history?limit=8`, { credentials: "include" });
    const data = res.ok ? await res.json() : null;
    setHistory(data?.items || []);
  };

  const refreshState = async () => {
    const res = await fetch(`${API_BASE}/api/intake/pipeline/state`, { credentials: "include" });
    const data = res.ok ? await res.json() : null;
    setState(data?.state || null);
    setQueueSize(Number(data?.queue_size || 0));
    setRunningCount(Number(data?.running_count || 0));
  };

  const refreshTasks = async () => {
    const res = await fetch(`${API_BASE}/api/intake/pipeline/tasks?limit=10`, { credentials: "include" });
    const data = res.ok ? await res.json() : null;
    setTasks(data?.items || []);
  };

  const refreshAgentAccess = async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/agent-access/${encodeURIComponent(uname)}`, { credentials: "include" });
    const data = res.ok ? await res.json() : null;
    setAgentAccess(
      data?.success
        ? {
            tokens: data?.tokens || [],
            bindings: data?.bindings || [],
            login_policy: data?.login_policy || {},
          }
        : null
    );
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
        await Promise.all([
          refreshTools(uname),
          refreshHistory(),
          refreshState(),
          refreshTasks(),
          refreshAgentAccess(uname),
        ]);
      } catch {
        router.replace("/chat");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [API_BASE, router]);

  useEffect(() => {
    const id = setInterval(() => {
      void refreshHistory();
      void refreshState();
      void refreshTasks();
    }, 8000);
    return () => clearInterval(id);
  }, []);

  const createAgentToken = async () => {
    if (!username || !agentTokenName.trim()) return;
    setSaving(true);
    setMsg("");
    setCreatedAgentToken("");
    try {
      const res = await fetch(`${API_BASE}/api/agent-access/tokens`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          username,
          token_name: agentTokenName.trim(),
          ttl_days: 30,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `创建失败(${res.status})`);
      setCreatedAgentToken(String(data?.token?.token || ""));
      await refreshAgentAccess(username);
      setMsg(`已创建 Agent Token：${data?.token?.token_name || agentTokenName.trim()}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "创建失败");
    } finally {
      setSaving(false);
    }
  };

  const revokeAgentToken = async (tokenId: number) => {
    if (!username || !tokenId) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/agent-access/tokens/${tokenId}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `撤销失败(${res.status})`);
      await refreshAgentAccess(username);
      setMsg("已撤销 Agent Token");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "撤销失败");
    } finally {
      setSaving(false);
    }
  };

  const reloadTools = async () => {
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/mcp/tools/reload`, { method: "POST", credentials: "include" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `重载失败(${res.status})`);
      if (username) await refreshTools(username);
      setMsg(`重载成功，当前 registry 工具数：${data?.count ?? "-"}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "重载失败");
    } finally {
      setSaving(false);
    }
  };

  const importFromFile = async () => {
    if (!username || !uploadFile) return;
    setSaving(true);
    setMsg("");
    try {
      const formData = new FormData();
      formData.append("username", username);
      formData.append("mcp_file", uploadFile);
      const res = await fetch(`${API_BASE}/api/mcp/tools/import-file`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `导入失败(${res.status})`);
      setUploadFile(null);
      await refreshTools(username);
      const summary = data?.summary || {};
      setMsg(
        `文件导入成功：${data?.imported ?? 0} 项，direct ${summary.direct ?? 0}，adapted ${summary.adapted ?? 0}，incompatible ${summary.incompatible ?? 0}`
      );
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "导入失败");
    } finally {
      setSaving(false);
    }
  };

  const importFromUrl = async () => {
    if (!username || !importUrl.trim()) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/mcp/tools/import-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, url: importUrl.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `导入失败(${res.status})`);
      setImportUrl("");
      await refreshTools(username);
      const summary = data?.summary || {};
      setMsg(
        `URL / 仓库导入成功：${data?.imported ?? 0} 项，direct ${summary.direct ?? 0}，adapted ${summary.adapted ?? 0}，incompatible ${summary.incompatible ?? 0}`
      );
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "导入失败");
    } finally {
      setSaving(false);
    }
  };

  const toggleImported = async (name: string, enabled: boolean) => {
    if (!username) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/mcp/tools/${encodeURIComponent(name)}/enable`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, enabled }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `操作失败(${res.status})`);
      await refreshTools(username);
      setMsg(`已${enabled ? "启用" : "停用"} ${name}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    } finally {
      setSaving(false);
    }
  };

  const probeSingleTool = async (name: string) => {
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/mcp/tools/${encodeURIComponent(name)}/probe?username=${encodeURIComponent(username)}`, {
        credentials: "include",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `探测失败(${res.status})`);
      setProbeMap((prev) => ({ ...prev, [name]: data as ProbeResult }));
      setMsg(`${name} 探测完成：${data.ready ? "ready" : "not ready"}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "探测失败");
    } finally {
      setSaving(false);
    }
  };

  const removeImported = async (name: string) => {
    if (!username) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/mcp/tools/${encodeURIComponent(name)}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `删除失败(${res.status})`);
      await refreshTools(username);
      setMsg(`已删除 ${name}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "删除失败");
    } finally {
      setSaving(false);
    }
  };

  const runProbe = async (autoEnable: boolean) => {
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/intake/probe-mcp-tools?auto_enable=${autoEnable ? "true" : "false"}`, {
        method: "POST",
        credentials: "include",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `探测失败(${res.status})`);
      setMsg(`探测完成：${data?.summary || "-"}`);
      await reloadTools();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "探测失败");
    } finally {
      setSaving(false);
    }
  };

  const runPipeline = async () => {
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/intake/pipeline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          per_topic: 4,
          clone_top: 1,
          integrate_top: 6,
          no_clone: true,
          update_repo_list: true,
          auto_enable: false,
          timeout_sec: 600,
          idempotency_key: `mcp-ui-${Date.now()}`,
          priority,
          max_retries: 2,
          retry_backoff_base_sec: 5,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `流水线失败(${res.status})`);
      setMsg(data?.deduplicated ? `命中去重：${data?.run_id || "-"}` : `已入队：${data?.run_id || "-"}`);
      await refreshHistory();
      await refreshState();
      await refreshTasks();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "流水线失败");
    } finally {
      setSaving(false);
    }
  };

  const forceUnlock = async () => {
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/intake/pipeline/unlock`, { method: "POST", credentials: "include" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `解锁失败(${res.status})`);
      setMsg(data?.message || "已解锁");
      await refreshState();
      await refreshTasks();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "解锁失败");
    } finally {
      setSaving(false);
    }
  };

  const retryTask = async (runId: string) => {
    if (!runId) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/intake/pipeline/tasks/${encodeURIComponent(runId)}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ auto_start: true }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `重试失败(${res.status})`);
      setMsg(`重试任务已入队：${data?.run_id || runId}`);
      await refreshHistory();
      await refreshState();
      await refreshTasks();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "重试失败");
    } finally {
      setSaving(false);
    }
  };

  const rollbackTask = async (runId: string) => {
    if (!runId) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/intake/pipeline/tasks/${encodeURIComponent(runId)}/rollback`, {
        method: "POST",
        credentials: "include",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `回滚失败(${res.status})`);
      setMsg(`回滚成功：${data?.restored?.restored_files ?? 0} 个文件`);
      if (username) await refreshTools(username);
      await refreshState();
      await refreshTasks();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "回滚失败");
    } finally {
      setSaving(false);
    }
  };

  const cancelTask = async (runId: string) => {
    if (!runId) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/intake/pipeline/tasks/${encodeURIComponent(runId)}/cancel`, {
        method: "POST",
        credentials: "include",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `取消失败(${res.status})`);
      setMsg(data?.message || "已请求取消");
      await refreshState();
      await refreshTasks();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "取消失败");
    } finally {
      setSaving(false);
    }
  };

  const sorted = useMemo(() => [...tools].sort((a, b) => a.name.localeCompare(b.name)), [tools]);
  const importedSorted = useMemo(() => [...importedTools].sort((a, b) => a.name.localeCompare(b.name)), [importedTools]);

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">加载中...</div>;
  }

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <Wrench className="h-3.5 w-3.5" />
          MCP OBJECTS
        </WorkbenchBadge>
      }
      title="MCP 工具管理"
      description="MCP 现在按对象导入和管理。支持 JSON 文件、URL、GitHub 仓库地址自动探测，导入后可单独启停、删除，再进入组合编排。"
      sidebarTitle="工具接入"
      sidebarDescription="MCP 已经不只是 registry 列表，而是用户侧可管理对象。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("mcp")}
      footer={<PlatformSidebarFooter username={username} detail="MCP 管理账号" />}
      topActions={
        <>
          <Button variant="outline" onClick={() => router.push("/composition")}>
            组合编排
          </Button>
          <Button onClick={() => router.push("/chat")}>返回会话</Button>
        </>
      }
    >
      <div className="grid gap-4">
        <div className="grid gap-4 md:grid-cols-4">
          <WorkbenchStatCard label="Imported" value={importedSorted.length} hint="当前账号导入的 MCP 对象" />
          <WorkbenchStatCard label="Registry" value={sorted.length} hint="当前 registry 实际可调用工具" />
          <WorkbenchStatCard label="Queue" value={queueSize} hint="等待中的流水线任务" />
          <WorkbenchStatCard label="Running" value={runningCount} hint={state?.status || "当前执行状态"} />
        </div>

        {msg ? (
          <Card className="border-slate-200 bg-slate-50 shadow-none">
            <CardContent className="p-4 text-sm text-slate-700">{msg}</CardContent>
          </Card>
        ) : null}

        <WorkbenchSection
          title="Agent Access"
          description="Web 端仍然统一走教务系统登录。外部 Agent 只拿平台发放的 token，并复用当前账号已绑定的服务授权。"
        >
          <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
            <div className="space-y-4">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-900">
                  <KeyRound className="h-4 w-4" />
                  创建 Agent Token
                </div>
                <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                  <Input value={agentTokenName} onChange={(e) => setAgentTokenName(e.target.value)} placeholder="例如 OpenClaw / Claude Desktop" />
                  <Button onClick={createAgentToken} disabled={saving || !agentTokenName.trim()}>
                    创建 Token
                  </Button>
                </div>
                <div className="mt-2 text-xs leading-5 text-slate-500">
                  {agentAccess?.login_policy?.web_login_source || "教务系统登录"} 是统一登录入口。外部 Agent 不直接登录教务系统。
                </div>
              </div>

              {createdAgentToken ? (
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
                  <div className="text-sm font-medium text-emerald-900">新 Token</div>
                  <div className="mt-2 break-all font-mono text-xs leading-6 text-emerald-800">{createdAgentToken}</div>
                  <div className="mt-2 text-xs text-emerald-700">这个值只会在创建后返回一次，外部 Agent 接入时直接作为 `Authorization: Bearer &lt;token&gt;` 使用。</div>
                </div>
              ) : null}

              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="text-sm font-medium text-slate-900">服务绑定</div>
                <div className="mt-3 space-y-3">
                  {(agentAccess?.bindings || []).length === 0 ? (
                    <div className="text-sm text-slate-500">暂无绑定信息</div>
                  ) : (
                    (agentAccess?.bindings || []).map((binding) => (
                      <div key={binding.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-sm font-medium text-slate-900">{binding.service_name}</div>
                          <Badge variant={binding.status === "active" ? "success" : "outline"}>{binding.status}</Badge>
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          auth: {binding.auth_type} · account: {binding.display_name || username}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          verified: {binding.last_verified_at || "-"}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="text-sm font-medium text-slate-900">已发放 Token</div>
              <div className="mt-3 space-y-3">
                {(agentAccess?.tokens || []).length === 0 ? (
                  <div className="text-sm text-slate-500">当前账号还没有 Agent Token</div>
                ) : (
                  (agentAccess?.tokens || []).map((token) => (
                    <div key={token.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="text-sm font-medium text-slate-900">{token.token_name}</div>
                          <div className="font-mono text-xs text-slate-500">{token.token_prefix}...</div>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={token.status === "active" ? "success" : "outline"}>{token.status}</Badge>
                          <Button size="sm" variant="outline" disabled={saving || token.status !== "active"} onClick={() => revokeAgentToken(token.id)}>
                            撤销
                          </Button>
                        </div>
                      </div>
                      <div className="mt-2 text-xs text-slate-500">
                        created: {token.created_at || "-"} · last used: {token.last_used_at || "-"}
                      </div>
                      <div className="mt-1 text-xs text-slate-500">expires: {token.expires_at || "-"}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </WorkbenchSection>

        <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr_0.95fr]">
          <div className="grid gap-4">
            <WorkbenchSection title="导入与控制" description="先导入对象，再重载 registry。GitHub 仓库会自动探测常见 JSON manifest。">
              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="text-sm font-medium text-slate-900">URL / GitHub 导入</div>
                  <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                    <Input
                      value={importUrl}
                      onChange={(e) => setImportUrl(e.target.value)}
                      placeholder="JSON 链接，或 GitHub 仓库 /blob/ 链接"
                    />
                    <Button variant="outline" onClick={importFromUrl} disabled={saving || !importUrl.trim()}>
                      <Github className="h-4 w-4" />
                      URL 导入
                    </Button>
                  </div>
                  <div className="text-xs leading-5 text-slate-500">
                    自动探测 `mcp.json`、`tools.json`、`external_tools.json`、`manifest.json` 等常见文件名。
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-medium text-slate-900">本地文件</div>
                  <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                    <Input type="file" accept=".json" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} />
                    <Button variant="outline" onClick={importFromFile} disabled={saving || !uploadFile}>
                      <Upload className="h-4 w-4" />
                      文件导入
                    </Button>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-slate-900">流水线优先级</div>
                      <div className="text-xs text-slate-500">影响 intake pipeline 排队顺序</div>
                    </div>
                    <select
                      value={priority}
                      onChange={(e) => setPriority(e.target.value as "high" | "normal" | "low")}
                      className="h-10 rounded-xl border border-[hsl(var(--border))] bg-white px-3 text-sm outline-none"
                    >
                      <option value="high">高优先级</option>
                      <option value="normal">普通优先级</option>
                      <option value="low">低优先级</option>
                    </select>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Button variant="outline" onClick={reloadTools} disabled={saving}>
                      <RefreshCcw className="h-4 w-4" />
                      重载工具
                    </Button>
                    <Button variant="outline" onClick={() => runProbe(false)} disabled={saving}>
                      <SearchCheck className="h-4 w-4" />
                      探测
                    </Button>
                    <Button variant="outline" onClick={() => runProbe(true)} disabled={saving}>
                      <SearchCheck className="h-4 w-4" />
                      探测并启用
                    </Button>
                    <Button onClick={runPipeline} disabled={saving}>
                      <Activity className="h-4 w-4" />
                      一键流水线
                    </Button>
                    <Button variant="outline" className="sm:col-span-2" onClick={forceUnlock} disabled={saving}>
                      <ShieldAlert className="h-4 w-4" />
                      强制解锁
                    </Button>
                  </div>
                </div>
              </div>
            </WorkbenchSection>

            <WorkbenchSection title="已导入 MCP 对象" description="当前账号真正持有的 MCP 对象，可单独启停和删除。">
              <ScrollArea className="h-[460px] pr-3">
                <div className="space-y-3">
                  {importedSorted.length === 0 ? <WorkbenchEmpty title="暂无导入对象" description="先导入 JSON 或 GitHub 仓库。" /> : null}
                  {importedSorted.map((tool) => (
                    <Card key={tool.name} className="border-slate-200 shadow-none">
                      <CardContent className="space-y-3 p-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="text-sm font-semibold text-slate-950">{tool.name}</div>
                            <div className="text-xs leading-5 text-slate-500">{tool.description || "无描述"}</div>
                          </div>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant={tool.enabled ? "success" : "outline"}>{tool.enabled ? "enabled" : "disabled"}</Badge>
                          <Badge variant="outline">{tool.kind || "python"}</Badge>
                          <Badge variant="secondary">{tool.source_type || "file"}</Badge>
                          <Badge variant="outline">{tool.transport || tool.kind || "python"}</Badge>
                          <Badge variant="secondary">{tool.compatibility_level || "direct"}</Badge>
                          <Badge variant="outline">{BOUNDARY_LABELS[tool.execution_boundary || "hosted_web"] || "边界未知"}</Badge>
                        </div>
                      </div>
                      {tool.source_ref ? <div className="text-xs text-slate-500">source: {tool.source_ref}</div> : null}
                      <div className="text-xs text-slate-500">
                        compatibility: {COMPATIBILITY_LABELS[tool.compatibility_level || "direct"] || tool.compatibility_level || "-"}
                      </div>
                      <div className="text-xs text-slate-500">capabilities: {(tool.capabilities || []).join(", ") || "-"}</div>
                      <div className="text-xs text-slate-500">
                        web: {tool.web_enabled === false ? "不可直接启用" : "可托管"} · scope: {tool.service_scope || "-"}
                      </div>
                      {tool.compatibility_notes && tool.compatibility_notes.length > 0 ? (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-6 text-slate-600">
                          {tool.compatibility_notes.join("；")}
                        </div>
                      ) : null}
                      {tool.execution_boundary_notes && tool.execution_boundary_notes.length > 0 ? (
                        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-6 text-amber-700">
                          {tool.execution_boundary_notes.join("；")}
                        </div>
                      ) : null}
                      {probeMap[tool.name] ? (
                        <div className={`rounded-xl border px-3 py-2 text-xs leading-6 ${probeMap[tool.name].ready ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
                          {probeMap[tool.name].checks.map((item) => `${item.name}: ${item.ok ? "ok" : "fail"} (${item.detail})`).join("；")}
                        </div>
                      ) : null}
                      <div className="flex flex-wrap gap-2">
                          <Button size="sm" variant="outline" disabled={saving} onClick={() => probeSingleTool(tool.name)}>
                            单项探测
                          </Button>
                          <Button size="sm" variant="outline" disabled={saving} onClick={() => toggleImported(tool.name, !tool.enabled)}>
                            {tool.enabled ? "停用" : "启用"}
                          </Button>
                          <Button size="sm" variant="outline" disabled={saving} onClick={() => removeImported(tool.name)}>
                            <Trash2 className="h-4 w-4" />
                            删除
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </ScrollArea>
            </WorkbenchSection>
          </div>

          <WorkbenchSection title="Registry 工具" description="这里是当前重载后实际可调用的工具集合。">
            <ScrollArea className="h-[720px] pr-3">
              <div className="space-y-3">
                {sorted.length === 0 ? <WorkbenchEmpty title="暂无工具" description="先导入对象，再重载 registry。" /> : null}
                {sorted.map((tool) => (
                  <Card key={`registry-${tool.name}`} className="border-slate-200 shadow-none">
                    <CardContent className="space-y-2 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="text-sm font-semibold text-slate-950">{tool.name}</div>
                        <Badge variant="outline">{tool.kind || "python"}</Badge>
                      </div>
                      <div className="text-xs leading-5 text-slate-500">{tool.description || "无描述"}</div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          </WorkbenchSection>

          <WorkbenchSection title="流水线任务" description="保留 intake pipeline 观测与控制。">
            <div className="space-y-4">
              <Card className="border-slate-200 bg-slate-50 shadow-none">
                <CardContent className="space-y-2 p-4 text-sm text-slate-600">
                  <div>state: {state?.status || "idle"}</div>
                  <div>queue: {queueSize}</div>
                  <div>running: {runningCount}</div>
                </CardContent>
              </Card>

              <ScrollArea className="h-[300px] pr-3">
                <div className="space-y-3">
                  {tasks.length === 0 ? <WorkbenchEmpty title="暂无任务" description="还没有排队中的任务。" /> : null}
                  {tasks.map((task) => (
                    <Card key={task.run_id} className="border-slate-200 shadow-none">
                      <CardContent className="space-y-3 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-sm font-semibold text-slate-950">{task.run_id}</div>
                          <Badge variant="outline">{task.status || "unknown"}</Badge>
                        </div>
                        <div className="text-xs text-slate-500">
                          priority={task.priority || "-"} · retries={task.retries ?? 0}/{task.max_retries ?? 0}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" variant="outline" disabled={saving} onClick={() => retryTask(task.run_id)}>
                            重试
                          </Button>
                          <Button size="sm" variant="outline" disabled={saving} onClick={() => rollbackTask(task.run_id)}>
                            回滚
                          </Button>
                          <Button size="sm" variant="outline" disabled={saving} onClick={() => cancelTask(task.run_id)}>
                            取消
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </ScrollArea>

              <ScrollArea className="h-[220px] pr-3">
                <div className="space-y-3">
                  {history.length === 0 ? <WorkbenchEmpty title="暂无历史" description="还没有完成过的流水线任务。" /> : null}
                  {history.map((item) => (
                    <Card key={item.run_id || `${item.started_at || "unknown"}-${item.error || "none"}`} className="border-slate-200 shadow-none">
                      <CardContent className="space-y-2 p-4 text-xs text-slate-500">
                        <div className="text-sm font-medium text-slate-900">{item.run_id || "unknown"}</div>
                        <div>{item.success ? "success" : "failed"}</div>
                        <div>{item.error || "无错误信息"}</div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </ScrollArea>
            </div>
          </WorkbenchSection>
        </div>
      </div>
    </WorkbenchShell>
  );
}
