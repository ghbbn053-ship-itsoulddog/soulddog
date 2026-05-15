'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { BrainCircuit, Cable, KeyRound, PlusCircle, Settings2, Sparkles } from "lucide-react";

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
import { InlineStatusMessage, PageLoading } from "@/components/ui/feedback";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type ProviderItem = {
  provider: string;
  display_name?: string;
  category?: string;
  models: string[];
  default_model: string;
  supports_custom_endpoint?: boolean;
  supports_custom_model?: boolean;
  supports_reasoning?: boolean;
  preset_api_base?: string;
  endpoint_hint?: string;
};

export default function ModelsSettingsPage() {
  const router = useRouter();
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
  const { username, authLoading } = useRequireAuth(API_BASE);

  useEffect(() => {
    if (authLoading || !username) return;
    const run = async () => {
      try {
        const availRes = await fetch(`${API_BASE}/api/models/available`, { credentials: "include" });
        const avail = availRes.ok ? await availRes.json() : null;
        const list: ProviderItem[] = avail?.providers || [];
        setProviders(list);

        const prefRes = await fetch(`${API_BASE}/api/models/preference/${encodeURIComponent(username)}`, {
          credentials: "include",
        });
        const pref = prefRes.ok ? await prefRes.json() : null;
        const prefProvider = pref?.provider || "qwen";
        const prefMeta = list.find((item) => item.provider === prefProvider);
        setProvider(prefProvider);
        setModel(pref?.model || prefMeta?.default_model || "");
        setApiBase(pref?.api_base || prefMeta?.preset_api_base || "");
        setApiKeyMasked(pref?.api_key_masked || "");
        setReasoningMode(pref?.reasoning_mode || "standard");
        setShowThinking(!!pref?.show_thinking);
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [API_BASE, authLoading, username]);

  const providerMeta = useMemo(
    () => providers.find((item) => item.provider === provider),
    [provider, providers]
  );

  const applyProvider = (nextProvider: string) => {
    const next = providers.find((item) => item.provider === nextProvider);
    if (!next) return;
    setProvider(nextProvider);
    setModel(next.default_model || next.models[0] || "");
    setApiBase(next.preset_api_base || "");
    setMsg("");
  };

  const save = async () => {
    if (!username || !providerMeta) return;
    setSaving(true);
    setMsg("");
    try {
      const payload = {
        username,
        provider,
        provider_label: providerMeta.display_name || providerMeta.provider,
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
      setApiKeyMasked(apiKey.trim() ? `${apiKey.trim().slice(0, 4)}***${apiKey.trim().slice(-4)}` : apiKeyMasked);
      setMsg(`已导入 ${providerMeta.display_name || provider} / ${data.model}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading || authLoading) {
    return <PageLoading label="正在加载模型配置..." />;
  }

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <Settings2 className="h-3.5 w-3.5" />
          MODEL IMPORT
        </WorkbenchBadge>
      }
      title="模型导入与接入"
      description="先选接入类型，再填 endpoint、API Key 和模型名。这里按真实常见 provider 模式组织，不再只给一个粗糙兼容入口。"
      sidebarTitle="模型配置"
      sidebarDescription="聊天页只负责使用模型，这里负责接入和导入。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("models")}
      footer={<PlatformSidebarFooter username={username} detail="模型设置账号" />}
      topActions={
        <>
          <Button variant="outline" onClick={() => router.push("/chat")}>
            返回会话
          </Button>
          <Button onClick={save} disabled={saving || !providerMeta}>
            <PlusCircle className="h-4 w-4" />
            {saving ? "导入中..." : "导入配置"}
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <div className="grid gap-4 md:grid-cols-4">
          <WorkbenchStatCard label="Providers" value={providers.length} hint="当前可选接入方式" />
          <WorkbenchStatCard label="Models" value={providerMeta?.models.length || 0} hint="当前 provider 的预置模型" />
          <WorkbenchStatCard label="Reasoning" value={showThinking ? "On" : "Off"} hint="思考流显示状态" />
          <WorkbenchStatCard label="Endpoint" value={providerMeta?.supports_custom_endpoint ? "Custom" : "Builtin"} hint="是否需要单独配置地址" />
        </div>

        {msg ? <InlineStatusMessage>{msg}</InlineStatusMessage> : null}

        <WorkbenchSection title="选择接入方式" description="先挑 provider，再进入具体配置。">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {providers.map((item) => {
              const active = item.provider === provider;
              return (
                <button
                  key={item.provider}
                  type="button"
                  onClick={() => applyProvider(item.provider)}
                  className={cn(
                    "rounded-2xl border p-4 text-left transition-colors",
                    active
                      ? "border-[hsl(var(--primary))] bg-blue-50/70"
                      : "border-slate-200 bg-white hover:bg-slate-50"
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">{item.display_name || item.provider}</div>
                      <div className="mt-1 text-xs leading-5 text-slate-500">{item.endpoint_hint || "常规模型接入方式"}</div>
                    </div>
                    <Badge variant={active ? "success" : "outline"}>{item.category || "provider"}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span>{item.supports_custom_endpoint ? "可自定义 endpoint" : "内置接入"}</span>
                    <span>{item.supports_custom_model ? "可自定义 model" : "固定模型列表"}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </WorkbenchSection>

        <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <WorkbenchSection title="导入配置" description="参考常见客户端模式：provider / endpoint / key / model 分开配置。">
            <div className="grid gap-4">
              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-2">
                  <div className="text-sm font-medium text-slate-900">模型名称</div>
                  <select
                    className="h-11 w-full rounded-xl border border-[hsl(var(--border))] bg-white px-3 text-sm outline-none"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                  >
                    {(providerMeta?.models || []).map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="space-y-2">
                  <div className="text-sm font-medium text-slate-900">推理模式</div>
                  <select
                    className="h-11 w-full rounded-xl border border-[hsl(var(--border))] bg-white px-3 text-sm outline-none"
                    value={reasoningMode}
                    onChange={(e) => setReasoningMode(e.target.value)}
                  >
                    <option value="standard">标准</option>
                    <option value="thinking">推理</option>
                    <option value="deep">深度推理</option>
                  </select>
                </label>
              </div>

              {providerMeta?.supports_custom_model ? (
                <label className="space-y-2">
                  <div className="text-sm font-medium text-slate-900">自定义模型名</div>
                  <Input
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="例如：gpt-4.1-mini / deepseek-chat / claude-3-7-sonnet / llama3.1:8b"
                  />
                </label>
              ) : null}

              {providerMeta?.supports_custom_endpoint ? (
                <div className="grid gap-4">
                  <label className="space-y-2">
                    <div className="text-sm font-medium text-slate-900">API Base URL</div>
                    <Input
                      value={apiBase}
                      onChange={(e) => setApiBase(e.target.value)}
                      placeholder={providerMeta?.preset_api_base || "https://api.openai.com/v1"}
                    />
                  </label>
                  <label className="space-y-2">
                    <div className="text-sm font-medium text-slate-900">API Key</div>
                    <Input
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={apiKeyMasked ? `已保存(${apiKeyMasked})，留空不修改` : "sk-..."}
                    />
                  </label>
                </div>
              ) : null}

              <label className="flex items-center gap-3 rounded-xl border border-[hsl(var(--border))] bg-slate-50 px-4 py-3">
                <input type="checkbox" checked={showThinking} onChange={(e) => setShowThinking(e.target.checked)} />
                <div>
                  <div className="text-sm font-medium text-slate-900">显示思考流</div>
                  <div className="text-xs text-slate-500">仅在模型/网关支持时有效</div>
                </div>
              </label>
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="当前摘要" description="导入前确认一下当前到底会接到哪里。">
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{providerMeta?.display_name || provider}</Badge>
                <Badge variant="outline">{model || "未填写 model"}</Badge>
                <Badge variant="secondary">{reasoningMode}</Badge>
                <Badge variant={showThinking ? "success" : "outline"}>{showThinking ? "思考流开启" : "思考流关闭"}</Badge>
              </div>

              <Card className="border-slate-200 bg-slate-50 shadow-none">
                <CardContent className="space-y-3 p-4 text-sm text-slate-600">
                  <div className="flex items-center gap-2 text-slate-900">
                    <Cable className="h-4 w-4 text-[hsl(var(--primary))]" />
                    接入信息
                  </div>
                  <div>Provider: {providerMeta?.display_name || provider}</div>
                  <div>Base URL: {providerMeta?.supports_custom_endpoint ? apiBase || providerMeta?.preset_api_base || "未填写" : "平台内置"}</div>
                  <div>API Key: {providerMeta?.supports_custom_endpoint ? (apiKeyMasked || (apiKey ? "本次将写入新 key" : "未填写")) : "平台内置"}</div>
                </CardContent>
              </Card>

              <Card className="border-slate-200 bg-slate-50 shadow-none">
                <CardContent className="space-y-3 p-4 text-sm text-slate-600">
                  <div className="flex items-center gap-2 text-slate-900">
                    <BrainCircuit className="h-4 w-4 text-[hsl(var(--primary))]" />
                    使用说明
                  </div>
                  <div>标准：更快，适合常规对话。</div>
                  <div>推理：适合较复杂问答，若服务端支持可展示思考流。</div>
                  <div>深度推理：延迟更高，适合长链路分析。</div>
                </CardContent>
              </Card>

              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="space-y-2 p-4 text-sm text-slate-600">
                  <div className="flex items-center gap-2 text-slate-900">
                    <KeyRound className="h-4 w-4 text-[hsl(var(--primary))]" />
                    常见导入方式
                  </div>
                  <div>OpenAI / OpenRouter / DeepSeek / SiliconFlow 这类通常填 `Base URL + API Key + model`。</div>
                  <div>Ollama 一般填本地地址，例如 `http://127.0.0.1:11434/v1`，模型名填本地已拉取模型。</div>
                  <div>平台内置千问则不需要额外导入。</div>
                </CardContent>
              </Card>

              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 px-4 py-4 text-xs leading-6 text-slate-500">
                <div className="mb-1 flex items-center gap-2 text-slate-900">
                  <Sparkles className="h-3.5 w-3.5" />
                  导入动作
                </div>
                点右上角 `导入配置` 才会真正写入当前账号配置。
              </div>
            </div>
          </WorkbenchSection>
        </div>
      </div>
    </WorkbenchShell>
  );
}
