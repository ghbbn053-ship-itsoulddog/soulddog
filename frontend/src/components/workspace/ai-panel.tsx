'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Bot, BrainCircuit, Loader2, MessageSquare, Send, Sparkles } from "lucide-react";

import MarkdownMessage from "@/components/MarkdownMessage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { WorkbenchEmpty } from "@/components/workspace/workbench-shell";

type ConversationItem = {
  id: number;
  title: string;
  created_at: string;
  workspace_id?: number | null;
};

type MessageHighlight = {
  source: string;
  title: string;
  snippet: string;
  document_id?: number;
  chunk_index?: number;
  score?: number;
};

type BlindSpotItem = {
  course_name: string;
  unresolved: number;
  dominant_type: string;
  dominant_type_count?: number;
  top_point?: string;
  top_point_count?: number;
};

type ToolTrace = {
  skill: string;
  tool: string;
  params?: Record<string, unknown>;
  status: "success" | "failed" | "empty";
  error?: string;
};

type SkillMatch = {
  name: string;
  mode?: string;
  source_type?: string;
  compatibility_level?: string;
  capabilities?: string[];
  always_on?: boolean;
  matched_triggers?: string[];
  has_tools?: boolean;
  tools?: string[];
};

type PanelMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  highlights?: MessageHighlight[];
  blind_spots?: BlindSpotItem[];
  sources?: string[];
  tool_trace?: ToolTrace[];
  skill_matches?: SkillMatch[];
  timestamp?: string;
  streaming?: boolean;
};

function parseKnowledgeSource(source: string) {
  const trimmed = (source || "").trim();
  const match = /^knowledge:\/\/workspace\/([^/]+)\/([^?]+)(?:\?(.*))?$/.exec(trimmed);
  if (!match) return null;
  const [, workspaceRaw, _titleRaw, queryRaw] = match;
  const params = new URLSearchParams(queryRaw || "");
  const workspaceId = Number(workspaceRaw || 0);
  const docId = Number(params.get("doc") || 0);
  const chunkIndex = Number(params.get("chunk") || 0);
  return {
    workspaceId: Number.isFinite(workspaceId) && workspaceId > 0 ? workspaceId : null,
    docId: Number.isFinite(docId) && docId > 0 ? docId : null,
    chunkIndex: Number.isFinite(chunkIndex) && chunkIndex >= 0 ? chunkIndex : null,
  };
}

function buildBlindSpotWorkspaceLink(workspaceId: number, item: BlindSpotItem) {
  const params = new URLSearchParams();
  if (item.course_name) params.set("course", item.course_name);
  if (item.top_point) params.set("point", item.top_point);
  const query = params.toString();
  return query ? `/workspace/${workspaceId}?${query}` : `/workspace/${workspaceId}`;
}

export function AIPanel({
  username,
  workspaceId,
  workspaceName,
  onLearningMemoryCaptured,
  draftPrompt,
  onDraftPromptConsumed,
}: {
  username: string;
  workspaceId: number;
  workspaceName?: string;
  onLearningMemoryCaptured?: () => void;
  draftPrompt?: string;
  onDraftPromptConsumed?: () => void;
}) {
  const router = useRouter();
  const [messages, setMessages] = useState<PanelMessage[]>([]);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [executionMode, setExecutionMode] = useState("agent");
  const [agentFramework, setAgentFramework] = useState("openai_agents");
  const [showThinking, setShowThinking] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;
  const STREAM_API_BASE = useMemo(() => {
    if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
      return `${window.location.protocol}//${window.location.hostname}:8000`;
    }
    return API_BASE;
  }, [API_BASE]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages.length]);

  const fetchConversations = useCallback(async () => {
    if (!username || !workspaceId) return;
    const res = await fetch(
      `${API_BASE}/api/chat/conversations/${encodeURIComponent(username)}?workspace_id=${workspaceId}`,
      { credentials: "include" }
    );
    const data = res.ok ? await res.json() : [];
    setConversations(Array.isArray(data) ? data : []);
  }, [API_BASE, username, workspaceId]);

  const fetchHistory = useCallback(
    async (nextConversationId: number) => {
      if (!username || !nextConversationId) return;
      const res = await fetch(
        `${API_BASE}/api/chat/history/${nextConversationId}?username=${encodeURIComponent(username)}`,
        { credentials: "include" }
      );
      const data = res.ok ? await res.json() : null;
      if (!data?.messages) return;
      setMessages(
        data.messages.map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          thinking: m.meta?.thinking || "",
          highlights: m.meta?.highlights || [],
          blind_spots: m.meta?.blind_spots || [],
          sources: m.meta?.sources || [],
          tool_trace: m.meta?.tool_trace || [],
          skill_matches: m.meta?.skill_matches || [],
          timestamp: new Date(m.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        }))
      );
    },
    [API_BASE, username]
  );

  useEffect(() => {
    setConversationId(null);
    setMessages([]);
    void fetchConversations();
  }, [fetchConversations, workspaceId]);

  useEffect(() => {
    if (!draftPrompt?.trim()) return;
    setInput(draftPrompt);
    onDraftPromptConsumed?.();
  }, [draftPrompt, onDraftPromptConsumed]);

  const activePromptBase = (input.trim() || draftPrompt?.trim() || "").trim();
  const hasDraftPrompt = Boolean(draftPrompt?.trim());
  const quickPromptTitle = hasDraftPrompt ? "基于当前资料的快捷追问" : "快速提问";

  const applyPromptTemplate = useCallback(
    (kind: "explain" | "keypoints" | "quiz" | "followup") => {
      const base = activePromptBase;
      const prefix = base ? `基于下面内容：\n${base}\n\n` : "";
      const nextPrompt =
        kind === "explain"
          ? `${prefix}请先把这段内容讲清楚，按最容易理解的方式解释关键概念，并指出我最容易卡住的地方。`
          : kind === "keypoints"
            ? `${prefix}请提炼这段内容的核心考点、易错点和必须记住的结论。`
            : kind === "quiz"
              ? `${prefix}请基于这段内容出 1 道练习题，并给出标准答案要点和解题思路。`
              : `${prefix}请告诉我基于这段内容，下一步最值得追问的问题是什么。`;
      setInput(nextPrompt);
      requestAnimationFrame(() => inputRef.current?.focus());
    },
    [activePromptBase]
  );

  const sendMessage = async () => {
    if (!username || !workspaceId || !input.trim() || loading) return;
    const userText = input.trim();
    const now = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    const userMsgId = Date.now();
    const assistantMsgId = userMsgId + 1;

    setInput("");
    setLoading(true);
    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: userText, timestamp: now },
      { id: assistantMsgId, role: "assistant", content: "", timestamp: now, streaming: true },
    ]);

    try {
      const response = await fetch(`${STREAM_API_BASE}/api/chat/send-stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          "Cache-Control": "no-cache",
        },
        credentials: "include",
        body: JSON.stringify({
          username,
          message: userText,
          conversation_id: conversationId,
          workspace_id: workspaceId,
          execution_mode: executionMode,
          agent_framework: agentFramework,
          show_thinking: showThinking,
          reasoning_mode: showThinking ? "deep" : "standard",
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`请求失败(${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let content = "";
      let thinking = "";
      let sseBuffer = "";
      let nextConversationId = conversationId;
      let streamDone = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        sseBuffer += decoder.decode(value, { stream: true });
        const parts = sseBuffer.split(/\r?\n\r?\n/);
        sseBuffer = parts.pop() || "";

        for (const event of parts) {
          const dataLines = event
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter((line) => line.startsWith("data:"))
            .map((line) => line.replace(/^data:\s?/, "").trim());

          for (const line of dataLines) {
            if (!line) continue;
            try {
              const data = JSON.parse(line);
              if (data.conversation_id) {
                nextConversationId = data.conversation_id;
              }
              if (data.thinking) {
                thinking += data.thinking;
              }
              if (data.content) {
                content += data.content;
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMsgId ? { ...msg, content, thinking } : msg
                  )
                );
              }
              if (data.done) {
                streamDone = true;
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMsgId
                      ? {
                          ...msg,
                          content,
                          thinking,
                          highlights: data.highlights || [],
                          blind_spots: data.blind_spots || [],
                          sources: data.sources || [],
                          tool_trace: data.tool_trace || [],
                          skill_matches: data.skill_matches || [],
                          streaming: false,
                        }
                      : msg
                  )
                );
              }
            } catch {
            }
          }
        }
      }

      if (nextConversationId) {
        setConversationId(nextConversationId);
        await fetchConversations();
      }
      if (streamDone) {
        onLearningMemoryCaptured?.();
      }
    } catch (e) {
      const errorText = e instanceof Error ? e.message : "请求失败";
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId ? { ...msg, content: `请求失败：${errorText}`, streaming: false } : msg
        )
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid gap-4">
      <Card className="shadow-none">
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                <Bot className="h-4 w-4 text-[hsl(var(--primary))]" />
                工作区内嵌 AI 面板
              </div>
              <div className="text-xs text-slate-500">
                当前绑定 {workspaceName || `workspace #${workspaceId}`}，直接在工作区内部做验证对话。
              </div>
            </div>
            <Badge variant="secondary">workspace #{workspaceId}</Badge>
          </div>
          <div className="grid gap-2 md:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Execution</div>
              <div className="flex flex-wrap gap-2">
                {["chat", "agent"].map((mode) => (
                  <Button
                    key={mode}
                    size="sm"
                    variant={executionMode === mode ? "default" : "outline"}
                    onClick={() => setExecutionMode(mode)}
                  >
                    {mode}
                  </Button>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Framework</div>
              <div className="flex flex-wrap gap-2">
                {["openai_agents", "langgraph"].map((framework) => (
                  <Button
                    key={framework}
                    size="sm"
                    variant={agentFramework === framework ? "default" : "outline"}
                    onClick={() => setAgentFramework(framework)}
                    disabled={executionMode !== "agent"}
                  >
                    {framework}
                  </Button>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Thinking</div>
              <Button
                size="sm"
                variant={showThinking ? "default" : "outline"}
                onClick={() => setShowThinking((prev) => !prev)}
              >
                <BrainCircuit className="h-4 w-4" />
                {showThinking ? "on" : "off"}
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => router.push(`/workspace/${workspaceId}`)}>
              返回工作区对话
            </Button>
            <Button size="sm" variant="outline" onClick={() => router.push("/composition")}>
              继续调整编排
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)]">
        <Card className="shadow-none">
          <CardContent className="p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-900">
              <MessageSquare className="h-4 w-4" />
              本工作区会话
            </div>
            <ScrollArea className="h-[520px] pr-3">
              <div className="space-y-2">
                <Button
                  className="w-full"
                  variant="outline"
                  onClick={() => {
                    setConversationId(null);
                    setMessages([]);
                  }}
                >
                  新对话
                </Button>
                {conversations.length === 0 ? (
                  <WorkbenchEmpty title="暂无对话" description="在右侧发起第一条工作区问题。" />
                ) : null}
                {conversations.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setConversationId(item.id);
                      void fetchHistory(item.id);
                    }}
                    className={`w-full rounded-xl border px-3 py-3 text-left transition-colors ${
                      conversationId === item.id ? "border-[hsl(var(--primary))] bg-blue-50/70" : "border-slate-200 bg-white hover:bg-slate-50"
                    }`}
                  >
                    <div className="truncate text-sm font-medium text-slate-900">{item.title}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {new Date(item.created_at).toLocaleString("zh-CN")}
                    </div>
                  </button>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardContent className="p-0">
            <div className="flex h-[620px] flex-col">
              <ScrollArea className="flex-1 px-4 py-4">
                <div className="space-y-4">
                  {messages.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-500">
                      现在可以直接在工作区里问问题，系统会自动带上当前 `workspace_id`，回答中的引用也能跳回文档。
                    </div>
                  ) : null}
                  {messages.map((msg) => (
                    <div key={msg.id} className={msg.role === "user" ? "ml-8" : "mr-8"}>
                      <div className={`rounded-2xl border px-4 py-3 ${msg.role === "user" ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-900"}`}>
                        <div className="mb-2 flex items-center justify-between gap-3 text-[11px] uppercase tracking-[0.14em] opacity-70">
                          <span>{msg.role === "user" ? "User" : "Assistant"}</span>
                          <span>{msg.timestamp}</span>
                        </div>
                        {msg.thinking ? (
                          <div className="mb-3 rounded-xl bg-slate-50 px-3 py-2 text-xs leading-6 text-slate-600">
                            <div className="mb-1 flex items-center gap-1.5 font-medium text-slate-500">
                              <Sparkles className="h-3.5 w-3.5" />
                              思考
                            </div>
                            <div className="whitespace-pre-wrap">{msg.thinking}</div>
                          </div>
                        ) : null}
                        <MarkdownMessage content={msg.content || (msg.streaming ? "生成中..." : "")} />
                        {msg.tool_trace && msg.tool_trace.length > 0 ? (
                          <div className="mt-3 space-y-2 border-t border-slate-200 pt-3">
                            <div className="text-xs font-medium text-slate-500">Tool Trace</div>
                            {msg.tool_trace.map((trace, index) => (
                              <div key={`${trace.tool}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                                {trace.skill} {"->"} {trace.tool} [{trace.status}]
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {msg.skill_matches && msg.skill_matches.length > 0 ? (
                          <div className="mt-3 space-y-2 border-t border-slate-200 pt-3">
                            <div className="text-xs font-medium text-slate-500">Matched Skills</div>
                            {msg.skill_matches.map((skill, index) => (
                              <div key={`${skill.name}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                                <div className="flex flex-wrap items-center gap-2 text-slate-900">
                                  <span className="font-medium">{skill.name}</span>
                                  <Badge variant="outline">{skill.mode || "rule"}</Badge>
                                  <Badge variant="secondary">{skill.compatibility_level || "direct"}</Badge>
                                  {skill.source_type ? <Badge variant="outline">{skill.source_type}</Badge> : null}
                                </div>
                                <div className="mt-1 leading-6">
                                  {skill.always_on ? "always on" : `matched triggers: ${(skill.matched_triggers || []).join(", ") || "-"}`}
                                </div>
                                {skill.compatibility_level === "rule_only" ? (
                                  <div className="leading-6 text-amber-700">
                                    仅规则注入：会影响提示词，不会直接调用外部天气/搜索等工具。
                                  </div>
                                ) : null}
                                <div className="leading-6">
                                  capabilities: {(skill.capabilities || []).join(", ") || "-"}
                                </div>
                                <div className="leading-6">
                                  tools: {(skill.tools || []).join(", ") || "-"}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {msg.blind_spots && msg.blind_spots.length > 0 ? (
                          <div className="mt-3 space-y-2 border-t border-amber-200 pt-3">
                            <div className="text-xs font-medium text-amber-700">本轮参考的学习盲点</div>
                            {msg.blind_spots.map((item, index) => (
                              <div key={`${item.course_name}-${index}`} className="rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-900">
                                <div className="font-medium text-slate-900">{item.course_name}</div>
                                <div className="mt-1 leading-6">
                                  未解决 {item.unresolved} 条
                                  {item.top_point ? `，高频卡点 ${item.top_point}` : ""}
                                </div>
                                <div className="mt-2">
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    className="h-7 border-amber-200 bg-white px-2 text-[11px] text-amber-800 hover:bg-amber-100"
                                    onClick={() => router.push(buildBlindSpotWorkspaceLink(workspaceId, item))}
                                  >
                                    定位到学习疑问
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {msg.highlights && msg.highlights.length > 0 ? (
                          <div className="mt-3 space-y-2 border-t border-slate-200 pt-3">
                            <div className="text-xs font-medium text-slate-500">引用片段</div>
                            {msg.highlights.map((item, index) => (
                              <button
                                key={`${item.source}-${index}`}
                                type="button"
                                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-left text-xs text-slate-600 transition-colors hover:bg-slate-100"
                                onClick={() => {
                                  const parsed = parseKnowledgeSource(item.source);
                                  if (parsed?.workspaceId && parsed.docId) {
                                    const query = parsed.chunkIndex != null ? `?doc=${parsed.docId}&chunk=${parsed.chunkIndex}` : `?doc=${parsed.docId}`;
                                    router.push(`/workspace/${parsed.workspaceId}${query}`);
                                  }
                                }}
                              >
                                <div className="mb-1 text-sm font-medium text-slate-900">{item.title}</div>
                                <div className="line-clamp-4 whitespace-pre-wrap leading-6">{item.snippet}</div>
                              </button>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              </ScrollArea>

              <Separator />

              <div className="p-4">
                {activePromptBase ? (
                  <div className="mb-3 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <div className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-slate-500">{quickPromptTitle}</div>
                    {hasDraftPrompt ? (
                      <div className="mb-3 text-xs leading-6 text-slate-500">
                        已把资料片段转成问题草稿。你可以直接发送，也可以先用下面的快捷动作改写一下。
                      </div>
                    ) : null}
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" size="sm" variant="outline" onClick={() => applyPromptTemplate("explain")}>
                        {hasDraftPrompt ? "解释这段资料" : "解释这段"}
                      </Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => applyPromptTemplate("keypoints")}>
                        {hasDraftPrompt ? "提炼这段考点" : "提炼考点"}
                      </Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => applyPromptTemplate("quiz")}>
                        {hasDraftPrompt ? "基于它出题" : "出一道题"}
                      </Button>
                      <Button type="button" size="sm" variant="ghost" onClick={() => applyPromptTemplate("followup")}>
                        {hasDraftPrompt ? "生成追问" : "继续追问"}
                      </Button>
                    </div>
                  </div>
                ) : null}
                <div className="flex gap-2">
                  <Input
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="直接在当前工作区提问..."
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        void sendMessage();
                      }
                    }}
                  />
                  <Button onClick={() => void sendMessage()} disabled={loading || !input.trim()}>
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
