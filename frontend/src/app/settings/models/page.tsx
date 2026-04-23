'use client';

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

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

  const providerModels = providers.find((p) => p.provider === provider)?.models || [];
  const providerMeta = providers.find((p) => p.provider === provider);

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

  if (loading) return <div className="p-6 text-sm text-gray-500">加载中...</div>;

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-2xl mx-auto bg-white rounded-2xl border border-gray-200 p-6">
        <h1 className="text-xl font-semibold text-gray-900">模型设置</h1>
        <p className="text-sm text-gray-500 mt-1">按账号保存模型偏好，聊天链路自动使用。</p>

        <div className="mt-6 space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700">Provider</label>
            <select
              className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2"
              value={provider}
              onChange={(e) => {
                const nextProvider = e.target.value;
                setProvider(nextProvider);
                const defaultModel =
                  providers.find((p) => p.provider === nextProvider)?.default_model || "";
                setModel(defaultModel);
              }}
            >
              {providers.map((p) => (
                <option key={p.provider} value={p.provider}>
                  {p.provider}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700">Model</label>
            <select
              className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            >
              {providerModels.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          {providerMeta?.supports_custom_endpoint && (
            <>
              <div>
                <label className="text-sm font-medium text-gray-700">Base URL</label>
                <input
                  value={apiBase}
                  onChange={(e) => setApiBase(e.target.value)}
                  placeholder="https://api.openai.com/v1"
                  className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">API Key</label>
                <input
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={apiKeyMasked ? `已保存(${apiKeyMasked})，留空不修改` : "sk-..."}
                  className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2"
                />
              </div>
            </>
          )}

          <div>
            <label className="text-sm font-medium text-gray-700">模式</label>
            <select
              className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2"
              value={reasoningMode}
              onChange={(e) => setReasoningMode(e.target.value)}
            >
              <option value="standard">标准</option>
              <option value="thinking">推理</option>
              <option value="deep">深度推理</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={showThinking}
              onChange={(e) => setShowThinking(e.target.checked)}
            />
            显示思考流（若模型支持）
          </label>

          <div className="flex gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-gray-900 text-white disabled:opacity-50"
            >
              {saving ? "保存中..." : "保存"}
            </button>
            <button
              onClick={() => router.push("/chat")}
              className="px-4 py-2 rounded-lg border border-gray-300 bg-white"
            >
              返回聊天
            </button>
          </div>
        </div>

        {msg && <div className="mt-4 text-sm text-gray-700">{msg}</div>}
      </div>
    </div>
  );
}
