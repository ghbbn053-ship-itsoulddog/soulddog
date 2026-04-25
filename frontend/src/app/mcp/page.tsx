'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Activity, RefreshCcw, SearchCheck, ShieldAlert, Upload, Wrench } from "lucide-react";

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

export default function MCPPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [tools, setTools] = useState<MCPTool[]>([]);
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

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const refresh = async () => {
    const res = await fetch(`${API_BASE}/api/mcp/tools`, { credentials: "include" });
    const data = res.ok ? await res.json() : null;
    setTools(data?.tools || []);
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

  useEffect(() => {
    const run = async () => {
      try {
        const meRes = await fetch(`${API_BASE}/api/auth/me`, { credentials: "include" });
        const me = meRes.ok ? await meRes.json() : null;
        if (!me?.authenticated || !me?.username) {
          router.replace("/login");
          return;
        }
        setUsername(String(me.username));
        await refresh();
        await refreshHistory();
        await refreshState();
        await refreshTasks();
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
      refreshState();
      refreshHistory();
      refreshTasks();
    }, 8000);
    return () => clearInterval(id);
  }, [API_BASE]);

  const reloadTools = async () => {
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/mcp/tools/reload`, {
        method: "POST",
        credentials: "include",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `重载失败(${res.status})`);
      setMsg(`重载成功，当前工具数：${data?.count ?? "-"}`);
      await refresh();
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
      setMsg(`导入成功：${data?.imported ?? 0} 项`);
      setUploadFile(null);
      await refresh();
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
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `URL 导入失败(${res.status})`);
      setMsg(`URL 导入成功：${data?.imported ?? 0} 项`);
      setImportUrl("");
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "URL 导入失败");
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
      if (data?.deduplicated) {
        setMsg(`命中去重：复用任务 ${data?.run_id || "-"} · 队列=${data?.queue_size ?? "-"}`);
      } else {
        setMsg(`已入队：${data?.run_id || "-"} · 队列=${data?.queue_size ?? "-"}`);
      }
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
      const res = await fetch(`${API_BASE}/api/intake/pipeline/unlock`, {
        method: "POST",
        credentials: "include",
      });
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
      setMsg(`重试任务已入队：${data?.run_id || runId} · 队列=${data?.queue_size ?? "-"}`);
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
      await refresh();
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

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">加载中...</div>;
  }

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <Wrench className="h-3.5 w-3.5" />
          MCP TOOLCHAIN
        </WorkbenchBadge>
      }
      title="MCP 工具管理"
      description="统一管理 MCP 工具导入、探测、启用和流水线任务。按钮布局已改为稳定卡片栅格，不再发生文本顶出。"
      sidebarTitle="工具接入"
      sidebarDescription="导入现成配置，重载工具，并观察 intake pipeline 状态。"
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
          <WorkbenchStatCard label="Tools" value={sorted.length} hint="已注册 MCP 工具" />
          <WorkbenchStatCard label="Queue" value={queueSize} hint="等待中的流水线任务" />
          <WorkbenchStatCard label="Running" value={runningCount} hint="当前正在执行" />
          <WorkbenchStatCard label="State" value={state?.running ? "Running" : "Idle"} hint={state?.status || "暂无状态"} />
        </div>

        {msg ? (
          <Card className="border-slate-200 bg-slate-50 shadow-none">
            <CardContent className="p-4 text-sm text-slate-700">{msg}</CardContent>
          </Card>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr_0.95fr]">
          <div className="grid gap-4">
            <WorkbenchSection title="导入与控制" description="这里把导入、探测、流水线控制拆成稳定区块，避免按钮挤压。">
              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="text-sm font-medium text-slate-900">URL 导入</div>
                  <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                    <Input
                      value={importUrl}
                      onChange={(e) => setImportUrl(e.target.value)}
                      placeholder="MCP 配置 JSON 链接"
                    />
                    <Button variant="outline" onClick={importFromUrl} disabled={saving || !importUrl.trim()}>
                      <Upload className="h-4 w-4" />
                      URL 导入
                    </Button>
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

            <WorkbenchSection title="已注册工具" description="工具 manifest 列表。">
              <ScrollArea className="h-[460px] pr-3">
                <div className="space-y-3">
                  {sorted.length === 0 ? <WorkbenchEmpty title="暂无 MCP 工具" description="先导入 JSON 或运行探测。" /> : null}
                  {sorted.map((tool) => (
                    <Card key={tool.name} className="border-slate-200 shadow-none">
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
          </div>

          <WorkbenchSection title="任务队列" description="查看运行、失败、取消、回滚和重试。">
            <ScrollArea className="h-[760px] pr-3">
              <div className="space-y-3">
                {tasks.length === 0 ? <WorkbenchEmpty title="暂无任务" description="执行探测或流水线后，这里会出现任务。" /> : null}
                {tasks.map((task) => (
                  <Card key={task.run_id} className="border-slate-200 shadow-none">
                    <CardContent className="space-y-3 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="text-sm font-semibold text-slate-950">{task.run_id}</div>
                        <Badge
                          variant={
                            task.status === "success"
                              ? "success"
                              : task.status === "failed"
                                ? "destructive"
                                : task.status === "running"
                                  ? "warning"
                                  : "outline"
                          }
                        >
                          {task.status || "-"}
                        </Badge>
                      </div>
                      <div className="text-xs leading-5 text-slate-500">
                        {task.created_at || "-"} · 优先级 {task.priority || "normal"} · 重试 {task.retries ?? 0}/{task.max_retries ?? 0}
                      </div>
                      <div className="text-xs leading-5 text-slate-500">
                        耗时 {task.duration_ms ?? "-"} ms · reload {task.reload_count ?? "-"} · 下次执行 {task.next_run_at || "-"}
                      </div>
                      {task.error ? <div className="text-xs text-rose-600 break-all">{task.error}</div> : null}
                      {task.last_error ? <div className="text-xs text-rose-500 break-all">last_error: {task.last_error}</div> : null}
                      <div className="grid gap-2 sm:grid-cols-3">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => cancelTask(task.run_id)}
                          disabled={saving || !["queued", "running"].includes(String(task.status || ""))}
                        >
                          取消
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => retryTask(task.run_id)} disabled={saving || !!state?.running}>
                          重试
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => rollbackTask(task.run_id)}
                          disabled={saving || !!state?.running || !task.snapshot}
                        >
                          回滚
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          </WorkbenchSection>

          <WorkbenchSection title="流水线历史" description="保留最近执行记录，便于回溯。">
            <ScrollArea className="h-[760px] pr-3">
              <div className="space-y-3">
                {history.length === 0 ? <WorkbenchEmpty title="暂无记录" description="历史记录会在任务执行后出现。" /> : null}
                {history.map((item, idx) => (
                  <Card key={`${item.run_id || idx}`} className="border-slate-200 shadow-none">
                    <CardContent className="space-y-2 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="text-sm font-semibold text-slate-950">{item.run_id || "-"}</div>
                        <Badge variant={item.success ? "success" : "destructive"}>{item.success ? "成功" : "失败"}</Badge>
                      </div>
                      <div className="text-xs leading-5 text-slate-500">
                        {item.started_at || "-"} · 耗时 {item.duration_ms ?? "-"} ms · reload {item.reload_count ?? "-"}
                      </div>
                      {item.error ? <div className="text-xs text-rose-600 break-all">{item.error}</div> : null}
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
