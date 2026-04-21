'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type SkillItem = {
  name: string;
  version: string;
  description: string;
  enabled: boolean;
  triggers: string[];
  tools: Array<{ name?: string }>;
  updated_at?: number;
};

const DEFAULT_SKILL_YAML = `name: sample_schedule_skill
version: 1.0.0
description: 示例课表技能
triggers:
  - 课表
  - 课程安排
tools:
  - name: query_schedule
    description: 查询课程表
enabled: true
`;

export default function SkillsPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [yamlText, setYamlText] = useState(DEFAULT_SKILL_YAML);
  const [importUrl, setImportUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const refresh = async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/skills/${encodeURIComponent(uname)}`, { credentials: "include" });
    const data = res.ok ? await res.json() : null;
    setSkills(data?.skills || []);
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

  const upload = async () => {
    if (!username) return;
    setSaving(true);
    setMsg("");
    try {
      const validateRes = await fetch(`${API_BASE}/api/skills/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, yaml_content: yamlText }),
      });
      const validateData = await validateRes.json().catch(() => ({}));
      if (!validateRes.ok || !validateData?.success) {
        throw new Error(validateData?.detail || validateData?.message || `校验失败(${validateRes.status})`);
      }

      const res = await fetch(`${API_BASE}/api/skills/upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, yaml_content: yamlText }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `上传失败(${res.status})`);
      setMsg("Skill 上传成功");
      await refresh(username);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "上传失败");
    } finally {
      setSaving(false);
    }
  };

  const importFromUrl = async () => {
    if (!username || !importUrl.trim()) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/skills/import-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, url: importUrl.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `导入失败(${res.status})`);
      setMsg("Skill 导入成功");
      setImportUrl("");
      await refresh(username);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "导入失败");
    } finally {
      setSaving(false);
    }
  };

  const uploadFromFile = async () => {
    if (!username || !uploadFile) return;
    setSaving(true);
    setMsg("");
    try {
      const formData = new FormData();
      formData.append("username", username);
      formData.append("skill_file", uploadFile);
      const res = await fetch(`${API_BASE}/api/skills/upload-file`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) throw new Error(data?.detail || data?.message || `文件安装失败(${res.status})`);
      setMsg("Skill 文件安装成功");
      setUploadFile(null);
      await refresh(username);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "文件安装失败");
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (name: string, enabled: boolean) => {
    if (!username) return;
    await fetch(`${API_BASE}/api/skills/${encodeURIComponent(name)}/enable`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username, enabled }),
    });
    await refresh(username);
  };

  const remove = async (name: string) => {
    if (!username) return;
    await fetch(`${API_BASE}/api/skills/${encodeURIComponent(name)}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username }),
    });
    await refresh(username);
  };

  const sorted = useMemo(() => [...skills].sort((a, b) => a.name.localeCompare(b.name)), [skills]);

  if (loading) return <div className="p-6 text-sm text-gray-500">加载中...</div>;

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded-2xl p-5">
          <h1 className="text-xl font-semibold text-gray-900">Skill 管理</h1>
          <p className="text-sm text-gray-500 mt-1">上传 YAML 声明即可扩展能力。</p>
          <textarea
            value={yamlText}
            onChange={(e) => setYamlText(e.target.value)}
            className="mt-4 w-full h-80 border border-gray-300 rounded-xl p-3 font-mono text-sm"
          />
          <div className="mt-3 flex gap-2">
            <input
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
              placeholder="GitHub YAML 链接（支持 /blob/ 自动转换）"
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
          <div className="mt-3 flex gap-2 items-center">
            <input
              type="file"
              accept=".yaml,.yml"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
            />
            <button
              onClick={uploadFromFile}
              disabled={saving || !uploadFile}
              className="px-4 py-2 rounded-lg border border-gray-300 bg-white disabled:opacity-50"
            >
              文件安装
            </button>
          </div>
          <div className="mt-3 flex gap-2">
            <button
              onClick={upload}
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-gray-900 text-white disabled:opacity-50"
            >
              {saving ? "上传中..." : "上传 Skill"}
            </button>
            <button onClick={() => router.push("/chat")} className="px-4 py-2 rounded-lg border border-gray-300 bg-white">
              返回聊天
            </button>
          </div>
          {msg && <div className="mt-3 text-sm text-gray-700">{msg}</div>}
        </div>

        <div className="bg-white border border-gray-200 rounded-2xl p-5">
          <h2 className="text-lg font-semibold text-gray-900">已安装 Skills</h2>
          <div className="mt-3 space-y-2">
            {sorted.length === 0 && <div className="text-sm text-gray-500">暂无 Skill</div>}
            {sorted.map((s) => (
              <div key={s.name} className="border border-gray-200 rounded-xl p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-gray-900">{s.name}</div>
                    <div className="text-xs text-gray-500">{s.description || "无描述"} · v{s.version || "-"}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggle(s.name, !s.enabled)}
                      className="px-2.5 py-1.5 text-xs rounded-lg border border-gray-300"
                    >
                      {s.enabled ? "停用" : "启用"}
                    </button>
                    <button
                      onClick={() => remove(s.name)}
                      className="px-2.5 py-1.5 text-xs rounded-lg border border-red-300 text-red-600"
                    >
                      删除
                    </button>
                  </div>
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  状态：{s.enabled ? "启用" : "停用"} · tools：{(s.tools || []).map((t) => t?.name || "-").join(", ")}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
