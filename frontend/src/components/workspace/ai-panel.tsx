'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Bot, BrainCircuit, Loader2, MessageSquare, PanelLeft, Send, Settings2, Sparkles } from "lucide-react";

import MarkdownMessage from "@/components/MarkdownMessage";
import {
  sendChatFallback,
  streamChatMessage,
  type ChatTransportPayload,
} from "@/components/chat/chat-transport";
import {
  ChatBlindSpots,
  ChatHighlights,
  ChatSkillMatches,
  ChatSources,
  ChatToolTrace,
  type ParsedKnowledgeSource,
} from "@/components/chat/chat-message-sections";
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

type DraftPromptPayload = {
  id: string;
  content: string;
  sourceLabel?: string;
  headline?: string;
  generatedBy?: string;
};

type HistoryMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  meta?: {
    thinking?: string;
    highlights?: MessageHighlight[];
    blind_spots?: BlindSpotItem[];
    sources?: string[];
    tool_trace?: ToolTrace[];
    skill_matches?: SkillMatch[];
  };
};

function parseKnowledgeSource(source: string) {
  const trimmed = (source || "").trim();
  const match = /^knowledge:\/\/workspace\/([^/]+)\/([^?]+)(?:\?(.*))?$/.exec(trimmed);
  if (!match) return null;
  const [, workspaceRaw, titleRaw, queryRaw] = match;
  const params = new URLSearchParams(queryRaw || "");
  const workspaceId = Number(workspaceRaw || 0);
  const docId = Number(params.get("doc") || 0);
  const chunkIndex = Number(params.get("chunk") || 0);
  return {
    raw: trimmed,
    workspaceId: Number.isFinite(workspaceId) && workspaceId > 0 ? workspaceId : null,
    title: decodeURIComponent(titleRaw || ""),
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

function DetailDisclosure({
  label,
  count,
  children,
}: {
  label: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50/72 p-3">
      <summary className="cursor-pointer list-none text-xs font-medium text-slate-600">
        <div className="flex items-center justify-between gap-3">
          <span>{label}</span>
          <Badge variant="outline">{count}</Badge>
        </div>
      </summary>
      <div className="mt-3">{children}</div>
    </details>
  );
}

export function AIPanel({
  username,
  workspaceId,
  workspaceName,
  onLearningMemoryCaptured,
  draftPrompt,
  onDraftPromptConsumed,
  promptStrategy,
  onDraftPromptCleared,
  onActiveReviewContextChange,
  reviewContextDismissVersion,
}: {
  username: string;
  workspaceId: number;
  workspaceName?: string;
  onLearningMemoryCaptured?: () => void;
  draftPrompt?: DraftPromptPayload | null;
  onDraftPromptConsumed?: () => void;
  promptStrategy?: string;
  onDraftPromptCleared?: () => void;
  onActiveReviewContextChange?: (payload: DraftPromptPayload | null) => void;
  reviewContextDismissVersion?: number;
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
  const [activeDraftPrompt, setActiveDraftPrompt] = useState<DraftPromptPayload | null>(null);
  const [showConversationRail, setShowConversationRail] = useState(false);
  const [showAdvancedControls, setShowAdvancedControls] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRootRef = useRef<HTMLDivElement>(null);
  const activeHistoryReqRef = useRef(0);
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
      const reqId = ++activeHistoryReqRef.current;
      const res = await fetch(
        `${API_BASE}/api/chat/history/${nextConversationId}?username=${encodeURIComponent(username)}`,
        { credentials: "include" }
      );
      const data = res.ok ? await res.json() : null;
      if (reqId !== activeHistoryReqRef.current) return;
      if (!data?.messages) return;
      setMessages(
        (data.messages as HistoryMessage[]).map((m) => ({
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
    activeHistoryReqRef.current++;
    setConversationId(null);
    setMessages([]);
    setShowConversationRail(false);
    void fetchConversations();
  }, [fetchConversations, workspaceId]);

  useEffect(() => {
    if (!draftPrompt?.content?.trim()) return;
    setActiveDraftPrompt(draftPrompt);
    setInput(draftPrompt.content);
    panelRootRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    requestAnimationFrame(() => inputRef.current?.focus());
    onDraftPromptConsumed?.();
  }, [draftPrompt, onDraftPromptConsumed]);

  useEffect(() => {
    onActiveReviewContextChange?.(activeDraftPrompt ?? null);
  }, [activeDraftPrompt, onActiveReviewContextChange]);

  useEffect(() => {
    if (!reviewContextDismissVersion) return;
    setInput((current) => {
      if (!activeDraftPrompt?.content?.trim()) return current;
      return current.trim() === activeDraftPrompt.content.trim() ? "" : current;
    });
    setActiveDraftPrompt(null);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [activeDraftPrompt, reviewContextDismissVersion]);

  const activePromptBase = (input.trim() || activeDraftPrompt?.content?.trim() || "").trim();
  const hasDraftPrompt = Boolean(activeDraftPrompt?.content?.trim());
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

    const payload: ChatTransportPayload = {
      username,
      message: userText,
      conversation_id: conversationId,
      workspace_id: workspaceId,
      override_provider: "",
      override_model: "",
      reasoning_mode: showThinking ? "deep" : "standard",
      show_thinking: showThinking,
      execution_mode: executionMode === "agent" ? "agent" : "chat",
      agent_framework: agentFramework === "langgraph" ? "langgraph" : "openai_agents",
      prompt_strategy: promptStrategy || "",
      generated_by: activeDraftPrompt?.generatedBy || "",
    };

    const patchAssistantMessage = (patch: Partial<PanelMessage>) => {
      setMessages((prev) =>
        prev.map((msg) => (msg.id === assistantMsgId ? { ...msg, ...patch } : msg))
      );
    };

    const fallbackToNonStream = async (reason?: string) => {
      try {
        const data = await sendChatFallback(API_BASE, payload);
        patchAssistantMessage({
          content: data.message,
          streaming: false,
          highlights: data.highlights || [],
          blind_spots: data.blind_spots || [],
          sources: data.sources || [],
          tool_trace: data.tool_trace || [],
          skill_matches: data.skill_matches || [],
        });
        if (data.conversationId) {
          setConversationId(data.conversationId);
          await fetchConversations();
        }
        onLearningMemoryCaptured?.();
      } catch (e) {
        const hint = reason ? `（${reason}）` : "";
        const errorText = e instanceof Error ? e.message : "请求失败";
        patchAssistantMessage({
          content: `请求失败${hint}：${errorText}`,
          streaming: false,
        });
      }
    };

    try {
      const data = await streamChatMessage({
        streamApiBase: STREAM_API_BASE,
        payload,
        onPatch: ({ content, thinking }) => {
          patchAssistantMessage({ content, thinking });
        },
        onPing: (hint) => {
          setMessages((prev) => {
            const idx = prev.findIndex((msg) => msg.id === assistantMsgId);
            if (idx === -1) return prev;
            if ((prev[idx].content || "") === hint) return prev;
            const next = [...prev];
            next[idx] = { ...next[idx], content: hint };
            return next;
          });
        },
      });

      if (!data.receivedAnyChunk) {
        await fallbackToNonStream("流式无分片");
      } else {
        patchAssistantMessage({
          content: data.content,
          thinking: data.thinking,
          highlights: data.highlights || [],
          blind_spots: data.blind_spots || [],
          sources: data.sources || [],
          tool_trace: data.tool_trace || [],
          skill_matches: data.skill_matches || [],
          streaming: false,
        });
        if (data.conversationId) {
          setConversationId(data.conversationId);
          await fetchConversations();
        }
        onLearningMemoryCaptured?.();
      }
    } catch (e) {
      await fallbackToNonStream(e instanceof Error ? e.message : "流式失败");
    } finally {
      setLoading(false);
    }
  };

  const startNewConversation = () => {
    activeHistoryReqRef.current++;
    setConversationId(null);
    setMessages([]);
    setShowConversationRail(false);
  };

  return (
    <div id="workspace-ai-panel" ref={panelRootRef} className="grid gap-3">
      <Card className="border-slate-200/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.94))] shadow-[0_10px_26px_rgba(15,23,42,0.04)]">
        <CardContent className="space-y-3 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                <Bot className="h-4 w-4 text-blue-600" />
                工作区内嵌 AI
              </div>
              <div className="mt-1 text-xs leading-6 text-slate-500">
                当前绑定 {workspaceName || `workspace #${workspaceId}`}。默认把注意力留给当前复习对话，历史会话和运行设置按需展开。
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">workspace #{workspaceId}</Badge>
              <Badge variant="outline">{conversations.length} 会话</Badge>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={showConversationRail ? "default" : "outline"}
              className="xl:hidden"
              onClick={() => setShowConversationRail((prev) => !prev)}
            >
              <PanelLeft className="h-4 w-4" />
              {showConversationRail ? "收起会话" : "查看会话"}
            </Button>
            <Button
              size="sm"
              variant={showAdvancedControls ? "default" : "outline"}
              onClick={() => setShowAdvancedControls((prev) => !prev)}
            >
              <Settings2 className="h-4 w-4" />
              {showAdvancedControls ? "收起设置" : "运行设置"}
            </Button>
            <Button size="sm" variant="outline" onClick={startNewConversation}>
              新对话
            </Button>
          </div>
          {showAdvancedControls ? (
            <div className="grid gap-2 rounded-[1.2rem] border border-slate-200 bg-slate-50/80 p-3 md:grid-cols-3">
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-3">
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
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-3">
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
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-3">
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
          ) : null}
        </CardContent>
      </Card>

      <div className="grid gap-3 xl:grid-cols-[210px_minmax(0,1fr)]">
        <Card className={`${showConversationRail ? "block" : "hidden"} border-slate-200/90 shadow-none xl:block`}>
          <CardContent className="p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-900">
              <MessageSquare className="h-4 w-4" />
              本工作区会话
            </div>
            <ScrollArea className="h-[620px] pr-3">
              <div className="space-y-2">
                <Button
                  className="w-full"
                  variant="outline"
                  onClick={startNewConversation}
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
                      setShowConversationRail(false);
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

        <Card className="border-slate-200/90 shadow-none">
          <CardContent className="p-0">
            <div className="flex h-[760px] min-h-[70vh] flex-col 2xl:h-[800px]">
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
                          <DetailDisclosure label="工具轨迹" count={msg.tool_trace.length}>
                            <ChatToolTrace traces={msg.tool_trace} />
                          </DetailDisclosure>
                        ) : null}
                        {msg.skill_matches && msg.skill_matches.length > 0 ? (
                          <DetailDisclosure label="技能匹配" count={msg.skill_matches.length}>
                            <ChatSkillMatches matches={msg.skill_matches} />
                          </DetailDisclosure>
                        ) : null}
                        {msg.blind_spots && msg.blind_spots.length > 0 ? (
                          <DetailDisclosure label="学习盲点" count={msg.blind_spots.length}>
                            <ChatBlindSpots
                              items={msg.blind_spots}
                              workspaceId={workspaceId}
                              onOpenBlindSpotLink={(item) => router.push(buildBlindSpotWorkspaceLink(workspaceId, item))}
                            />
                          </DetailDisclosure>
                        ) : null}
                        {msg.sources && msg.sources.length > 0 ? (
                          <DetailDisclosure label="参考来源" count={msg.sources.length}>
                            <ChatSources
                              sources={msg.sources}
                              parseKnowledgeSource={parseKnowledgeSource as (source: string) => ParsedKnowledgeSource | null}
                              onOpenSourceLink={(source) => {
                                const parsed = parseKnowledgeSource(source);
                                if (parsed?.workspaceId && parsed.docId) {
                                  const query = parsed.chunkIndex != null ? `?doc=${parsed.docId}&chunk=${parsed.chunkIndex}` : `?doc=${parsed.docId}`;
                                  router.push(`/workspace/${parsed.workspaceId}${query}`);
                                }
                              }}
                            />
                          </DetailDisclosure>
                        ) : null}
                        {msg.highlights && msg.highlights.length > 0 ? (
                          <DetailDisclosure label="引用片段" count={msg.highlights.length}>
                            <ChatHighlights
                              highlights={msg.highlights}
                              parseKnowledgeSource={parseKnowledgeSource as (source: string) => ParsedKnowledgeSource | null}
                              onOpenSourceLink={(source) => {
                                const parsed = parseKnowledgeSource(source);
                                if (parsed?.workspaceId && parsed.docId) {
                                  const query = parsed.chunkIndex != null ? `?doc=${parsed.docId}&chunk=${parsed.chunkIndex}` : `?doc=${parsed.docId}`;
                                  router.push(`/workspace/${parsed.workspaceId}${query}`);
                                }
                              }}
                            />
                          </DetailDisclosure>
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
                        已经把当前复习上下文转成问题草稿。你可以直接发送，也可以先用下面的快捷动作改写一下。
                      </div>
                    ) : null}
                    {activeDraftPrompt?.headline ? (
                      <div className="mb-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs leading-6 text-slate-600">
                        <div className="mb-1 font-medium text-slate-900">当前复习上下文</div>
                        <div>{activeDraftPrompt.headline}</div>
                      </div>
                    ) : null}
                    {activeDraftPrompt?.sourceLabel ? (
                      <div className="mb-3">
                        <Badge variant="outline">{activeDraftPrompt.sourceLabel}</Badge>
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
                      {hasDraftPrompt ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setInput("");
                            setActiveDraftPrompt(null);
                            onDraftPromptCleared?.();
                            requestAnimationFrame(() => inputRef.current?.focus());
                          }}
                        >
                          结束当前复习
                        </Button>
                      ) : null}
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
