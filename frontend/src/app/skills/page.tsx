'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Blocks, FileUp, Github, Upload } from "lucide-react";

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

type SkillItem = {
  name: string;
  version: string;
  description: string;
  enabled: boolean;
  always_on?: boolean;
  triggers: string[];
  input_schema?: Record<string, unknown>;
  tools: Array<{ name?: string }>;
  source_type?: string;
  source_ref?: string;
  mode?: string;
  compatibility_level?: string;
  compatibility_notes?: string[];
  capabilities?: string[];
  guidance_excerpt?: string;
  updated_at?: number;
};

const COMPATIBILITY_LABELS: Record<string, string> = {
  direct: "可直接使用",
  adapted: "需要适配",
  rule_only: "仅规则注入",
  incompatible: "暂不兼容",
};

const DEFAULT_SKILL_YAML = `name: sample_schedule_skill
version: 1.0.0
description: 示例课表技能
triggers:
  - 课表
  - 课程安排
input_schema:
  type: object
  properties:
    semester:
      type: string
      description: 学期，如 2025-2026-2
  required: []
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
      const skill = data?.skill || {};
      setMsg(`Skill 上传成功：${COMPATIBILITY_LABELS[skill?.compatibility_level || "direct"] || "可直接使用"}`);
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
      const skill = data?.skill || {};
      setMsg(`Skill 导入成功：${COMPATIBILITY_LABELS[skill?.compatibility_level || "direct"] || "可直接使用"}`);
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
      const skill = data?.skill || {};
      setMsg(`Skill 文件安装成功：${COMPATIBILITY_LABELS[skill?.compatibility_level || "direct"] || "可直接使用"}`);
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
  const enabledCount = sorted.filter((item) => item.enabled).length;

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">加载中...</div>;
  }

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <Blocks className="h-3.5 w-3.5" />
          SKILL REGISTRY
        </WorkbenchBadge>
      }
      title="Skill 管理"
      description="Skill 分两类：工具型 manifest skill，以及仓库/文档型 repo skill。这里只展示真实可导入能力，不再把 GitHub 仓库误当成 YAML。"
      sidebarTitle="能力编排"
      sidebarDescription="以 Skill 为单位维护平台能力和触发路由。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("skills")}
      footer={<PlatformSidebarFooter username={username} detail="Skill 管理账号" />}
      topActions={
        <>
          <Button variant="outline" onClick={() => router.push("/composition")}>
            进入组合编排
          </Button>
          <Button onClick={() => router.push("/chat")}>返回会话</Button>
        </>
      }
    >
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <WorkbenchStatCard label="Installed" value={sorted.length} hint="当前账号可见 Skill 总数" />
            <WorkbenchStatCard label="Enabled" value={enabledCount} hint="当前处于启用状态" />
            <WorkbenchStatCard label="Disabled" value={sorted.length - enabledCount} hint="可在右侧快速启用" />
          </div>

          <WorkbenchSection
            title="安装与导入"
            description="YAML 用于工具型 manifest skill。GitHub 仓库地址会优先尝试 manifest，找不到时自动按 repo/doc skill 导入。注意：repo/doc skill 只会注入规则，不会自动变成可执行工具。"
          >
            <div className="space-y-4">
              <Textarea
                value={yamlText}
                onChange={(e) => setYamlText(e.target.value)}
                className="min-h-[360px] font-mono text-sm"
              />
              <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                <Input
                  value={importUrl}
                  onChange={(e) => setImportUrl(e.target.value)}
                  placeholder="GitHub 仓库、raw YAML、/blob/ 文件链接都可以"
                />
                <Button variant="outline" onClick={importFromUrl} disabled={saving || !importUrl.trim()}>
                  <Github className="h-4 w-4" />
                  URL 导入
                </Button>
              </div>
              <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                <Input type="file" accept=".yaml,.yml,.md,.txt" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} />
                <Button variant="outline" onClick={uploadFromFile} disabled={saving || !uploadFile}>
                  <FileUp className="h-4 w-4" />
                  文件安装
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={upload} disabled={saving}>
                  <Upload className="h-4 w-4" />
                  {saving ? "处理中..." : "上传 Skill"}
                </Button>
                {msg ? (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{msg}</div>
                ) : null}
              </div>
            </div>
          </WorkbenchSection>
        </div>

        <WorkbenchSection title="已安装 Skill" description="清单视图采用 shadcn 卡片，不再使用原生按钮堆叠。">
          <ScrollArea className="h-[720px] pr-3">
            <div className="space-y-3">
              {sorted.length === 0 ? (
                <WorkbenchEmpty title="暂无 Skill" description="先在左侧上传 YAML 或从现成 GitHub 配置导入。" />
              ) : null}
              {sorted.map((skill) => {
                const schemaProperties =
                  (skill.input_schema as Record<string, unknown>)?.properties as Record<string, unknown> | undefined;
                return (
                  <Card key={skill.name} className="border-slate-200 shadow-none">
                    <CardContent className="space-y-3 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="text-sm font-semibold text-slate-950">{skill.name}</div>
                  <div className="text-xs leading-5 text-slate-500">{skill.description || "无描述"}</div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant={skill.enabled ? "success" : "outline"}>{skill.enabled ? "enabled" : "disabled"}</Badge>
                          <Badge variant="outline">v{skill.version || "-"}</Badge>
                          <Badge variant="secondary">{skill.source_type || "yaml"}</Badge>
                          <Badge variant="outline">{skill.mode || "rule"}</Badge>
                          <Badge variant="secondary">{skill.compatibility_level || "direct"}</Badge>
                          {skill.always_on ? <Badge variant="outline">always on</Badge> : null}
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {(skill.triggers || []).length > 0 ? (
                          skill.triggers.map((trigger) => (
                            <Badge key={trigger} variant="secondary">
                              {trigger}
                            </Badge>
                          ))
                        ) : (
                          <Badge variant="outline">无 trigger</Badge>
                        )}
                      </div>

                      <div className="space-y-1 text-xs text-slate-500">
                        <div>compatibility: {COMPATIBILITY_LABELS[skill.compatibility_level || "direct"] || skill.compatibility_level || "-"}</div>
                        <div>tools: {(skill.tools || []).map((tool) => tool?.name || "-").join(", ") || "-"}</div>
                        <div>capabilities: {(skill.capabilities || []).join(", ") || "-"}</div>
                        {skill.source_ref ? <div>source: {skill.source_ref}</div> : null}
                      </div>

                      {skill.compatibility_notes && skill.compatibility_notes.length > 0 ? (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-6 text-slate-600">
                          {skill.compatibility_notes.join("；")}
                        </div>
                      ) : null}

                      {skill.compatibility_level === "rule_only" ? (
                        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-6 text-amber-800">
                          这个 Skill 目前只是规则/提示词注入，不具备真实工具执行能力。像天气、搜索这类外部能力，必须再接入对应 MCP 或平台工具，单靠文档型 Skill 不能直接查询。
                        </div>
                      ) : null}

                      {skill.guidance_excerpt ? (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-6 text-slate-600">
                          {skill.guidance_excerpt}
                        </div>
                      ) : null}

                      {schemaProperties && Object.keys(schemaProperties).length > 0 ? (
                        <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-[11px] leading-5 text-slate-600">
                          {JSON.stringify(skill.input_schema || {}, null, 2)}
                        </pre>
                      ) : null}

                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="outline" onClick={() => toggle(skill.name, !skill.enabled)}>
                          {skill.enabled ? "停用" : "启用"}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => remove(skill.name)}>
                          删除
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </ScrollArea>
        </WorkbenchSection>
      </div>
    </WorkbenchShell>
  );
}
