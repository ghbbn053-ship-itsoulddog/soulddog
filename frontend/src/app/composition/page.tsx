'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

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

export default function CompositionPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [data, setData] = useState<CompositionData | null>(null);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const refresh = async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/composition/${encodeURIComponent(uname)}`, { credentials: "include" });
    const json = res.ok ? await res.json() : null;
    setData(json?.data || null);
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

  if (loading) return <div className="p-6 text-sm text-gray-500">加载中...</div>;

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded-2xl p-5">
          <h1 className="text-xl font-semibold text-gray-900">Skill 拼装</h1>
          <p className="text-sm text-gray-500 mt-1">按用户启停 Skill，决定路由是否生效。</p>
          <div className="mt-4 space-y-2">
            {skillList.length === 0 && <div className="text-sm text-gray-500">暂无 Skill</div>}
            {skillList.map((s) => (
              <div key={s} className="border border-gray-200 rounded-xl p-3 flex items-center justify-between">
                <div className="text-sm font-medium text-gray-900">{s}</div>
                <button
                  onClick={() => toggleSkill(s, !skillEnabled(s))}
                  disabled={saving}
                  className="px-3 py-1.5 text-xs rounded-lg border border-gray-300 bg-white disabled:opacity-50"
                >
                  {skillEnabled(s) ? "禁用" : "启用"}
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-2xl p-5">
          <h2 className="text-xl font-semibold text-gray-900">MCP 拼装</h2>
          <p className="text-sm text-gray-500 mt-1">启停工具并调整执行优先顺序。</p>
          <div className="mt-4 space-y-2">
            {mcpList.length === 0 && <div className="text-sm text-gray-500">暂无 MCP 工具</div>}
            {mcpList.map((t, idx) => (
              <div key={t} className="border border-gray-200 rounded-xl p-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium text-gray-900">{t}</div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => move(idx, -1)}
                      disabled={saving || idx === 0}
                      className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40"
                    >
                      上移
                    </button>
                    <button
                      onClick={() => move(idx, 1)}
                      disabled={saving || idx === mcpList.length - 1}
                      className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40"
                    >
                      下移
                    </button>
                    <button
                      onClick={() => toggleMcp(t, !mcpEnabled(t))}
                      disabled={saving}
                      className="px-3 py-1.5 text-xs rounded-lg border border-gray-300 bg-white disabled:opacity-50"
                    >
                      {mcpEnabled(t) ? "禁用" : "启用"}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex gap-2">
            <button onClick={() => router.push("/chat")} className="px-4 py-2 rounded-lg border border-gray-300 bg-white">
              返回聊天
            </button>
            <button onClick={() => router.push("/mcp")} className="px-4 py-2 rounded-lg border border-gray-300 bg-white">
              MCP 管理
            </button>
          </div>
          {msg && <div className="mt-3 text-sm text-gray-700">{msg}</div>}
        </div>
      </div>
    </div>
  );
}

