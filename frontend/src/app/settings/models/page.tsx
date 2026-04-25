'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { BrainCircuit, Settings2 } from "lucide-react";

import { PlatformSidebarFooter, PlatformSidebarHeader, createPlatformNav } from "@/components/workspace/app-sidebar";
import {
  WorkbenchBadge,
  WorkbenchSection,
  WorkbenchShell,
  WorkbenchStatCard,
} from "@/components/workspace/workbench-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type ProviderItem = {
  provider: string;
  models: string[];
  default_model: string;
  supports_custom_endpoint?: boolean;
  supports_reasoning?: boolean;
};

export default function ModelsSettingsPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [providers, setProviders] = useState<ProviderItem[]>([]);
  const [provider, setProvider] = useState("qwen");
  const [model, setModel] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiKeyMasked, setApiKeyMasked] = useState("");
  const [reasoningMode, setReasoningMode] = useState("standard");
  const [showThinking, setShowThinking] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

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

        const availRes = await fetch(`${API_BASE}/api/models/available`, { credentials: "include" });
        const avail = availRes.ok ? await availRes.json() : null;
        const list: ProviderItem[] = avail?.providers || [];
        setProviders(list);

        const prefRes = await fetch(`${API_BASE}/api/models/preference/${encodeURIComponent(uname)}`, {
          credentials: "include",
        });
        const pref = prefRes.ok ? await prefRes.json() : null;
        const prefProvider = pref?.provider || "qwen";
        setProvider(prefProvider);
        setModel(pref?.model || list.find((x) => x.provider === prefProvider)?.default_model || "");
        setApiBase(pref?.api_base || "");
        setApiKeyMasked(pref?.api_key_masked || "");
        setReasoningMode(pref?.reasoning_mode || "standard");
        setShowThinking(!!pref?.show_thinking);
      } catch {
        router.replace("/chat");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [API_BASE, router]);

  const providerModels = useMemo(
    () => providers.find((p) => p.provider === provider)?.models || [],
    [providers, provider]
  );
  const providerMeta = useMemo(() => providers.find((p) => p.provider === provider), [providers, provider]);

  const save = async () => {
    if (!username) return;
    setSaving(true);
    setMsg("");
    try {
      const payload = {
        username,
        provider,
        model,
        api_base: apiBase,
        api_key: apiKey.trim() ? apiKey.trim() : null,
        reasoning_mode: reasoningMode,
        show_thinking: showThinking,
      };
      const res = await fetch(`${API_BASE}/api/models/preference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.success) {
        throw new Error(data?.detail || data?.message || `保存失败(${res.status})`);
      }
      setApiKey("");
      setMsg(`已保存：${data.provider} / ${data.model}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">加载中...</div>;
  }

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <Settings2 className="h-3.5 w-3.5" />
          MODEL SETTINGS
        </WorkbenchBadge>
      }
      title="模型设置"
      description="按账号保存 Provider、Model、推理模式和自定义 API 入口。这里的设置会直接作用于快速会话和工作区对话。"
      sidebarTitle="模型偏好"
      sidebarDescription="统一提供模型选择、推理模式和思考流开关。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("models")}
      footer={<PlatformSidebarFooter username={username} detail="模型设置账号" />}
      topActions={
        <>
          <Button variant="outline" onClick={() => router.push("/chat")}>
            返回会话
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? "保存中..." : "保存设置"}
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <div className="grid gap-4 md:grid-cols-3">
          <WorkbenchStatCard label="Providers" value={providers.length} hint="当前后端返回可用供应商" />
          <WorkbenchStatCard label="Models" value={providerModels.length} hint="当前 provider 下的模型数" />
          <WorkbenchStatCard label="Thinking" value={showThinking ? "On" : "Off"} hint="思考流前端显示状态" />
        </div>

        {msg ? (
          <Card className="border-slate-200 bg-slate-50 shadow-none">
            <CardContent className="p-4 text-sm text-slate-700">{msg}</CardContent>
          </Card>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <WorkbenchSection title="基础配置" description="保持页面结构清晰，避免把模型选择藏起来。">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2">
                <div className="text-sm font-medium text-slate-900">Provider</div>
                <select
                  className="h-11 w-full rounded-xl border border-[hsl(var(--border))] bg-white px-3 text-sm outline-none ring-0"
                  value={provider}
                  onChange={(e) => {
                    const nextProvider = e.target.value;
                    setProvider(nextProvider);
                    const defaultModel = providers.find((p) => p.provider === nextProvider)?.default_model || "";
                    setModel(defaultModel);
                  }}
                >
                  {providers.map((item) => (
                    <option key={item.provider} value={item.provider}>
                      {item.provider}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-2">
                <div className="text-sm font-medium text-slate-900">Model</div>
                <select
                  className="h-11 w-full rounded-xl border border-[hsl(var(--border))] bg-white px-3 text-sm outline-none ring-0"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                >
                  {providerModels.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>

              {providerMeta?.supports_custom_endpoint ? (
                <>
                  <label className="space-y-2 md:col-span-2">
                    <div className="text-sm font-medium text-slate-900">Base URL</div>
                    <Input
                      value={apiBase}
                      onChange={(e) => setApiBase(e.target.value)}
                      placeholder="https://api.openai.com/v1"
                    />
                  </label>
                  <label className="space-y-2 md:col-span-2">
                    <div className="text-sm font-medium text-slate-900">API Key</div>
                    <Input
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={apiKeyMasked ? `已保存(${apiKeyMasked})，留空不修改` : "sk-..."}
                    />
                  </label>
                </>
              ) : null}

              <label className="space-y-2">
                <div className="text-sm font-medium text-slate-900">推理模式</div>
                <select
                  className="h-11 w-full rounded-xl border border-[hsl(var(--border))] bg-white px-3 text-sm outline-none ring-0"
                  value={reasoningMode}
                  onChange={(e) => setReasoningMode(e.target.value)}
                >
                  <option value="standard">标准</option>
                  <option value="thinking">推理</option>
                  <option value="deep">深度推理</option>
                </select>
              </label>

              <label className="flex items-center gap-3 rounded-xl border border-[hsl(var(--border))] bg-slate-50 px-4 py-3">
                <input type="checkbox" checked={showThinking} onChange={(e) => setShowThinking(e.target.checked)} />
                <div>
                  <div className="text-sm font-medium text-slate-900">显示思考流</div>
                  <div className="text-xs text-slate-500">仅在模型支持时有效</div>
                </div>
              </label>
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="当前摘要" description="给用户一个清晰的当前配置总览。">
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{provider || "provider"}</Badge>
                <Badge variant="outline">{model || "model"}</Badge>
                <Badge variant="secondary">{reasoningMode}</Badge>
                <Badge variant={showThinking ? "success" : "outline"}>{showThinking ? "思考流开启" : "思考流关闭"}</Badge>
              </div>
              <Card className="border-slate-200 bg-slate-50 shadow-none">
                <CardContent className="space-y-2 p-4 text-sm text-slate-600">
                  <div className="flex items-center gap-2 text-slate-900">
                    <BrainCircuit className="h-4 w-4 text-[hsl(var(--primary))]" />
                    推理模式说明
                  </div>
                  <div>标准：追求响应速度。</div>
                  <div>推理：适合需要展示思考过程的复杂问答。</div>
                  <div>深度推理：适合更长推导链路，但延迟更高。</div>
                </CardContent>
              </Card>
            </div>
          </WorkbenchSection>
        </div>
      </div>
    </WorkbenchShell>
  );
}
