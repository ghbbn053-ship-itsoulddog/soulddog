'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

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
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `流水线失败(${res.status})`);
      setMsg(`已入队：${data?.run_id || "-"} · 队列=${data?.queue_size ?? "-"}`);
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

  const sorted = useMemo(() => [...tools].sort((a, b) => a.name.localeCompare(b.name)), [tools]);

  if (loading) return <div className="p-6 text-sm text-gray-500">加载中...</div>;

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-2xl p-5">
          <h1 className="text-xl font-semibold text-gray-900">MCP 工具管理</h1>
          <p className="text-sm text-gray-500 mt-1">导入 JSON 配置并重载即可接入工具。</p>
          <div className="mt-3 flex gap-2">
            <input
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
              placeholder="MCP 配置 JSON 链接"
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
            <button
              onClick={importFromUrl}
              disabled={saving || !importUrl.trim()}
              className="px-4 py-2 rounded-lg border border-gray-300 bg-white disabled:opacity-50"
            >
              URL 导入
            </button>
          </div>
          <div className="mt-4 flex gap-2 items-center">
            <input
              type="file"
              accept=".json"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
            />
            <button
              onClick={importFromFile}
              disabled={saving || !uploadFile}
              className="px-4 py-2 rounded-lg border border-gray-300 bg-white disabled:opacity-50"
            >
              文件导入
            </button>
          </div>
          <div className="mt-3 flex gap-2">
            <button
              onClick={reloadTools}
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-gray-900 text-white disabled:opacity-50"
            >
              {saving ? "处理中..." : "重载工具"}
            </button>
            <button
              onClick={() => runProbe(false)}
              disabled={saving}
              className="px-4 py-2 rounded-lg border border-gray-300 bg-white disabled:opacity-50"
            >
              探测
            </button>
            <button
              onClick={() => runProbe(true)}
              disabled={saving}
              className="px-4 py-2 rounded-lg border border-gray-300 bg-white disabled:opacity-50"
            >
              探测并启用
            </button>
            <button
              onClick={runPipeline}
              disabled={saving}
              className="px-4 py-2 rounded-lg border border-gray-300 bg-white disabled:opacity-50"
            >
              一键流水线
            </button>
            <button
              onClick={forceUnlock}
              disabled={saving}
              className="px-4 py-2 rounded-lg border border-red-300 text-red-600 bg-white disabled:opacity-50"
            >
              强制解锁
            </button>
            <button onClick={() => router.push("/chat")} className="px-4 py-2 rounded-lg border border-gray-300 bg-white">
              返回聊天
            </button>
          </div>
          <div className="mt-3 text-xs text-gray-500">
            状态：{state?.running ? "运行中" : "空闲"} · run_id: {state?.run_id || "-"} · status: {state?.status || "-"} · 队列: {queueSize}
          </div>
          {msg && <div className="mt-3 text-sm text-gray-700">{msg}</div>}
        </div>

        <div className="bg-white border border-gray-200 rounded-2xl p-5">
          <h2 className="text-lg font-semibold text-gray-900">已注册工具</h2>
          <div className="mt-3 space-y-2">
            {sorted.length === 0 && <div className="text-sm text-gray-500">暂无 MCP 工具</div>}
            {sorted.map((t) => (
              <div key={t.name} className="border border-gray-200 rounded-xl p-3">
                <div className="font-medium text-gray-900">{t.name}</div>
                <div className="text-xs text-gray-500 mt-1">
                  {(t.description || "无描述")} · kind: {t.kind || "python"}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-2xl p-5">
          <h2 className="text-lg font-semibold text-gray-900">任务队列</h2>
          <div className="mt-3 space-y-2">
            {tasks.length === 0 && <div className="text-sm text-gray-500">暂无任务</div>}
            {tasks.map((t) => (
              <div key={t.run_id} className="border border-gray-200 rounded-xl p-3">
                <div className="text-sm font-medium text-gray-900">
                  {t.run_id} · {t.status || "-"}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {t.created_at || "-"} · 耗时: {t.duration_ms ?? "-"} ms · reload: {t.reload_count ?? "-"}
                </div>
                {t.error && <div className="text-xs text-red-600 mt-1 break-all">{t.error}</div>}
                <div className="mt-2 flex gap-2">
                  <button
                    onClick={() => retryTask(t.run_id)}
                    disabled={saving || state?.running}
                    className="px-3 py-1 rounded-lg border border-gray-300 bg-white text-xs disabled:opacity-50"
                  >
                    重试
                  </button>
                  <button
                    onClick={() => rollbackTask(t.run_id)}
                    disabled={saving || state?.running || !t.snapshot}
                    className="px-3 py-1 rounded-lg border border-orange-300 text-orange-700 bg-white text-xs disabled:opacity-50"
                  >
                    回滚
                  </button>
                </div>
              </div>
            ))}
          </div>
          <h2 className="text-lg font-semibold text-gray-900 mt-6">流水线历史</h2>
          <div className="mt-3 space-y-2">
            {history.length === 0 && <div className="text-sm text-gray-500">暂无记录</div>}
            {history.map((h, idx) => (
              <div key={`${h.run_id || idx}`} className="border border-gray-200 rounded-xl p-3">
                <div className="text-sm font-medium text-gray-900">
                  {h.run_id || "-"} · {h.success ? "成功" : "失败"}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {h.started_at || "-"} · 耗时: {h.duration_ms ?? "-"} ms · reload: {h.reload_count ?? "-"}
                </div>
                {h.error && <div className="text-xs text-red-600 mt-1 break-all">{h.error}</div>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
