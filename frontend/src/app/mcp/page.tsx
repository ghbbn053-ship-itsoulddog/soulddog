'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type MCPTool = {
  name: string;
  description: string;
  kind?: string;
  parameters?: Record<string, { type?: string; required?: boolean; description?: string }>;
};

export default function MCPPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const refresh = async () => {
    const res = await fetch(`${API_BASE}/api/mcp/tools`, { credentials: "include" });
    const data = res.ok ? await res.json() : null;
    setTools(data?.tools || []);
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
      } catch {
        router.replace("/chat");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [API_BASE, router]);

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

  const sorted = useMemo(() => [...tools].sort((a, b) => a.name.localeCompare(b.name)), [tools]);

  if (loading) return <div className="p-6 text-sm text-gray-500">加载中...</div>;

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded-2xl p-5">
          <h1 className="text-xl font-semibold text-gray-900">MCP 工具管理</h1>
          <p className="text-sm text-gray-500 mt-1">导入 JSON 配置并重载即可接入工具。</p>
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
            <button onClick={() => router.push("/chat")} className="px-4 py-2 rounded-lg border border-gray-300 bg-white">
              返回聊天
            </button>
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
      </div>
    </div>
  );
}
