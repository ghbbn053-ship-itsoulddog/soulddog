'use client';

import React, { Suspense, useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ChatComposer } from "@/components/chat/chat-composer";
import { ChatEmptyState } from "@/components/chat/chat-empty-state";
import {
  getConversationStorageKey,
  mapHistoryMessages,
  type ChatBlindSpotItem,
  type ChatHistoryMessage,
  type ChatViewMessage,
} from "@/components/chat/chat-history";
import {
  sendChatFallback,
  streamChatMessage,
  type ChatTransportPayload,
} from "@/components/chat/chat-transport";
import { ChatMessageList } from "@/components/chat/chat-message-list";
import { ChatSaveDialog } from "@/components/chat/chat-save-dialog";
import { ChatSidebar } from "@/components/chat/chat-sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageFallback, PageLoading } from "@/components/ui/feedback";
import { useChatBootstrap } from "@/hooks/use-chat-bootstrap";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ArrowLeft,
  Menu,
  User,
} from "lucide-react";

type Message = ChatViewMessage;

interface Conversation {
  id: number;
  title: string;
  created_at: string;
}

interface ProviderItem {
  provider: string;
  models: string[];
  default_model: string;
}

interface WorkspaceItem {
  id: number;
  slug: string;
  name: string;
  description?: string;
  is_default: boolean;
}

function toolDisplayName(name: string) {
  return (
    {
      query_personal_info: "个人信息",
      query_grades: "成绩查询",
      query_schedule: "课表查询",
      query_exam_schedule: "考试安排",
      query_academic_progress: "学业进度",
      query_weather: "天气查询",
      refresh_all_data: "刷新数据",
    }[name] || name
  );
}

function buildConversationMarkdown(messages: Message[], conversationId: number | null) {
  const title = conversationId ? `chat-${conversationId}` : `chat-${Date.now()}`;
  const lines: string[] = [
    "# 对话存档",
    "",
    `- conversation_id: ${conversationId ?? "new"}`,
    `- exported_at: ${new Date().toISOString()}`,
    "",
  ];

  for (const msg of messages) {
    lines.push(`## ${msg.role === "user" ? "用户" : "助手"}`);
    if (msg.timestamp) {
      lines.push(`- time: ${msg.timestamp}`);
    }
    lines.push("");
    if (msg.thinking) {
      lines.push("### 思考");
      lines.push("");
      lines.push(msg.thinking);
      lines.push("");
    }
    lines.push(msg.content || "");
    lines.push("");

    if (msg.tool_trace && msg.tool_trace.length > 0) {
      lines.push("### Tool Trace");
      lines.push("");
      for (const trace of msg.tool_trace) {
        lines.push(`- ${trace.skill} -> ${trace.tool} [${trace.status}]`);
        if (trace.params && Object.keys(trace.params).length > 0) {
          lines.push(`  - params: ${JSON.stringify(trace.params)}`);
        }
        if (trace.error) {
          lines.push(`  - error: ${trace.error}`);
        }
      }
      lines.push("");
    }

    if (msg.skill_matches && msg.skill_matches.length > 0) {
      lines.push("### Matched Skills");
      lines.push("");
      for (const skill of msg.skill_matches) {
        lines.push(`- ${skill.name} [${skill.compatibility_level || "direct"}]`);
        if (skill.tools && skill.tools.length > 0) {
          lines.push(`  - tools: ${skill.tools.join(", ")}`);
        }
        if (skill.capabilities && skill.capabilities.length > 0) {
          lines.push(`  - capabilities: ${skill.capabilities.join(", ")}`);
        }
      }
      lines.push("");
    }
  }

  return {
    filename: `${title}.md`,
    content: lines.join("\n"),
  };
}

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

function ChatPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [providers, setProviders] = useState<ProviderItem[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [workspaceId, setWorkspaceId] = useState<number | null>(null);
  const [provider, setProvider] = useState("qwen");
  const [model, setModel] = useState("");
  const [reasoningMode, setReasoningMode] = useState("standard");
  const [showThinking, setShowThinking] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveTargetWorkspaceId, setSaveTargetWorkspaceId] = useState<number | null>(null);
  const [saveWorkspaceName, setSaveWorkspaceName] = useState("");
  const [saveWorkspaceDesc, setSaveWorkspaceDesc] = useState("");
  const [saveStatus, setSaveStatus] = useState("");
  const [savePending, setSavePending] = useState(false);
  const [selectedPromptStrategy, setSelectedPromptStrategy] = useState("");
  const [generatedBy, setGeneratedBy] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const activeHistoryReqRef = useRef(0);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;
  const { username, authLoading } = useRequireAuth(API_BASE, "/login");
  const STREAM_API_BASE = useMemo(() => {
    const envBase = (process.env.NEXT_PUBLIC_STREAM_API_URL || "").trim();
    if (envBase) {
      return envBase.endsWith("/api") ? envBase.slice(0, -4) : envBase;
    }
    if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
      return `${window.location.protocol}//${window.location.hostname}:8000`;
    }
    return API_BASE;
  }, [API_BASE]);
  const requestedWorkspaceId = useMemo(() => {
    const raw = searchParams.get("workspace_id");
    const parsed = Number(raw || 0);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);
  const requestedPrompt = useMemo(() => (searchParams.get("prompt") || "").trim(), [searchParams]);
  const requestedCourse = useMemo(() => (searchParams.get("course") || "").trim(), [searchParams]);
  const requestedPoint = useMemo(
    () => (searchParams.get("point") || searchParams.get("knowledge_point") || "").trim(),
    [searchParams]
  );
  const requestedQuestionType = useMemo(
    () => (searchParams.get("type") || searchParams.get("question_type") || "").trim(),
    [searchParams]
  );
  const requestedStrategy = useMemo(() => (searchParams.get("strategy") || "").trim(), [searchParams]);
  const requestedConversationId = useMemo(() => {
    const raw = searchParams.get("conversation_id");
    const parsed = Number(raw || 0);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);
  const requestedContextTags = useMemo(
    () =>
      [
        requestedCourse ? `课程：${requestedCourse}` : "",
        requestedPoint ? `知识点：${requestedPoint}` : "",
        requestedQuestionType ? `问题类型：${requestedQuestionType}` : "",
      ].filter(Boolean),
    [requestedCourse, requestedPoint, requestedQuestionType]
  );
  const followUpSuggestions = useMemo(() => {
    if (!requestedPrompt) return [];
    const subject = requestedCourse || "这门课";
    const point = requestedPoint || "这个知识点";
    const type = requestedQuestionType || "这个问题";
    const items = [
      {
        label: "先讲清卡点",
        prompt: `请先判断我在${subject}里关于${point}的主要卡点是什么，并用最容易听懂的方式重新讲一遍。`,
      },
      {
        label: "做题化拆解",
        prompt: `请围绕${subject}里的${point}，用“概念 -> 例题 -> 易错点”的顺序带我走一遍，尤其关注${type}。`,
      },
      {
        label: "复习计划",
        prompt: `如果我要在今天解决${subject}里关于${point}的这类问题，请帮我给出一个 20 分钟的小复习计划。`,
      },
    ];
    if (requestedStrategy) {
      const idx = items.findIndex((item) => item.label === requestedStrategy);
      if (idx > 0) {
        const [picked] = items.splice(idx, 1);
        items.unshift(picked);
      }
    }
    return items;
  }, [requestedCourse, requestedPoint, requestedPrompt, requestedQuestionType, requestedStrategy]);
  const shouldShowComposerFollowups = useMemo(
    () => !requestedPrompt || messages.length > 0,
    [messages.length, requestedPrompt]
  );

  const scrollToBottom = (behavior: ScrollBehavior = "auto") => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  useEffect(() => {
    scrollToBottom("smooth");
  }, [messages.length]);

  const fetchConversations = useCallback(async () => {
    if (!username) return;
    try {
      const res = await fetch(`${API_BASE}/api/chat/conversations/${username}`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch (error) {
      console.error("获取对话列表失败:", error);
    }
  }, [API_BASE, username]);

  const updateWorkspacePreference = useCallback(
    async (nextWorkspaceId: number, nextWorkspaceName: string, uname: string = username) => {
      if (!uname) return;
      try {
        await fetch(`${API_BASE}/api/workspace-preference`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            username: uname,
            workspace_id: nextWorkspaceId,
            workspace_name: nextWorkspaceName,
          }),
        });
      } catch {
      }
    },
    [API_BASE, username]
  );

  const fetchModelPrefs = useCallback(
    async (uname: string) => {
      try {
        const availRes = await fetch(`${API_BASE}/api/models/available`, { credentials: "include" });
        const avail = availRes.ok ? await availRes.json() : null;
        const list: ProviderItem[] = avail?.providers || [];
        setProviders(list);

        const prefRes = await fetch(`${API_BASE}/api/models/preference/${encodeURIComponent(uname)}`, { credentials: "include" });
        const pref = prefRes.ok ? await prefRes.json() : null;
        const p = pref?.provider || "qwen";
        const m = pref?.model || list.find((x) => x.provider === p)?.default_model || "";
        setProvider(p);
        setModel(m);
        setReasoningMode(pref?.reasoning_mode || "standard");
        setShowThinking(!!pref?.show_thinking);
      } catch {
      }
    },
    [API_BASE]
  );

  const fetchWorkspacePrefs = useCallback(
    async (uname: string) => {
      try {
        const [workspaceRes, prefRes, compositionRes] = await Promise.all([
          fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}`, { credentials: "include" }),
          fetch(`${API_BASE}/api/workspace-preference/${encodeURIComponent(uname)}`, { credentials: "include" }),
          fetch(`${API_BASE}/api/composition/${encodeURIComponent(uname)}`, { credentials: "include" }),
        ]);
        const workspaceJson = workspaceRes.ok ? await workspaceRes.json() : null;
        const prefJson = prefRes.ok ? await prefRes.json() : null;
        await compositionRes.json().catch(() => null);
        const items: WorkspaceItem[] = workspaceJson?.workspaces || [];
        setWorkspaces(items);
        const requestedWorkspace = requestedWorkspaceId ? items.find((item) => item.id === requestedWorkspaceId) : null;
        const preferredWorkspace = prefJson?.workspace_id ? items.find((item) => item.id === prefJson.workspace_id) : null;
        const selectedWorkspace = requestedWorkspace || preferredWorkspace || items[0] || null;
        const selected = selectedWorkspace?.id || null;
        setWorkspaceId(selected);
        setSaveTargetWorkspaceId(selected);
        if (requestedWorkspace && requestedWorkspace.id !== prefJson?.workspace_id) {
          await updateWorkspacePreference(requestedWorkspace.id, requestedWorkspace.name, uname);
        }
      } catch {
      }
    },
    [API_BASE, requestedWorkspaceId, updateWorkspacePreference]
  );

  const modelOptions = useMemo(
    () =>
      providers.flatMap((item) =>
        item.models.map((modelName) => ({
          key: `${item.provider}::${modelName}`,
          provider: item.provider,
          model: modelName,
        }))
      ),
    [providers]
  );

  const fetchHistory = useCallback(
    async (conversationId: number, uname: string = username) => {
      if (!uname) return;
      if (isLoading) return;
      const reqId = ++activeHistoryReqRef.current;
      try {
        const res = await fetch(`${API_BASE}/api/chat/history/${conversationId}?username=${encodeURIComponent(uname)}`, {
          credentials: "include",
        });
        if (reqId !== activeHistoryReqRef.current) return;
        if (res.ok) {
          const data = await res.json();
          if (reqId !== activeHistoryReqRef.current) return;
          if (data?.messages) {
            setMessages(mapHistoryMessages(data.messages as ChatHistoryMessage[]));
            return;
          }
        }
        if (reqId === activeHistoryReqRef.current && res.status === 404) {
          setCurrentConversationId(null);
          localStorage.removeItem(getConversationStorageKey(uname));
          setMessages([]);
        }
      } catch (error) {
        console.error("获取历史失败:", error);
      }
    },
    [API_BASE, username, isLoading]
  );

  useChatBootstrap({
    apiBase: API_BASE,
    username,
    authLoading,
    requestedConversationId,
    fetchModelPrefs,
    fetchWorkspacePrefs,
    mapMessages: mapHistoryMessages,
    setMessages,
    setCurrentConversationId,
    setInitialLoading,
    activeHistoryReqRef,
  });

  const sendMessage = async () => {
    if (!input.trim() || !username || isLoading) return;

    const userMessage = input.trim();
    const promptStrategy = inferPromptStrategy(userMessage);
    const now = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    const userMsgId = Date.now();
    const assistantMsgId = userMsgId + 1;

    setInput("");
    setIsLoading(true);

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: userMessage, timestamp: now },
      { id: assistantMsgId, role: "assistant", content: "", timestamp: now, streaming: true },
    ]);

    const payload: ChatTransportPayload = {
      username,
      message: userMessage,
      conversation_id: currentConversationId,
      workspace_id: workspaceId,
      override_provider: provider,
      override_model: model,
      reasoning_mode: reasoningMode,
      show_thinking: showThinking,
      execution_mode: "chat",
      agent_framework: "openai_agents",
      prompt_strategy: promptStrategy,
      generated_by: generatedBy || "",
    };

    const patchAssistantMessage = (patch: Partial<Message>) => {
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
          sources: data.sources || [],
          highlights: data.highlights || [],
          blind_spots: data.blind_spots || [],
          tool_calls: data.tool_calls || [],
          tool_trace: data.tool_trace || [],
          skill_matches: data.skill_matches || [],
        });
        if (data.conversationId) {
          setCurrentConversationId(data.conversationId);
          fetchConversations();
        }
      } catch (e) {
        const hint = reason ? `（${reason}）` : "";
        const errText = e instanceof Error ? e.message : "服务暂时不可用";
        patchAssistantMessage({
          content: `请求失败${hint}：${errText}`,
          streaming: false,
        });
      }
    };

    try {
      activeHistoryReqRef.current++;

      const data = await streamChatMessage({
        streamApiBase: STREAM_API_BASE,
        payload,
        onPatch: ({ content, thinking }) => {
          patchAssistantMessage({ content, thinking });
          requestAnimationFrame(() => scrollToBottom("auto"));
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
          streaming: false,
          sources: data.sources || [],
          highlights: data.highlights || [],
          blind_spots: data.blind_spots || [],
          tool_calls: data.tool_calls || [],
          tool_trace: data.tool_trace || [],
          skill_matches: data.skill_matches || [],
        });
        if (data.conversationId) {
          setCurrentConversationId(data.conversationId);
          fetchConversations();
        }
      }
    } catch (error) {
      console.error("流式消息失败:", error);
      await fallbackToNonStream(error instanceof Error ? error.message : "流式失败");
    } finally {
      setSelectedPromptStrategy("");
      setGeneratedBy("");
      setIsLoading(false);
    }
  };

  const inferPromptStrategy = (message: string) => {
    const trimmed = message.trim();
    if (!trimmed) return "";
    if (selectedPromptStrategy) return selectedPromptStrategy;
    const matched = followUpSuggestions.find((item) => item.prompt === trimmed);
    return matched?.label || "";
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const newConversation = () => {
    setCurrentConversationId(null);
    setMessages([]);
    if (username) {
      localStorage.removeItem(getConversationStorageKey(username));
    }
    setSidebarOpen(false);
  };

  const selectConversation = (id: number) => {
    if (isLoading) return;
    setCurrentConversationId(id);
    void fetchHistory(id);
    setSidebarOpen(false);
  };

  const deleteConversation = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`${API_BASE}/api/chat/conversations/${id}?username=${encodeURIComponent(username || "")}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (currentConversationId === id) {
        newConversation();
      }
      fetchConversations();
    } catch (error) {
      console.error("删除失败:", error);
    }
  };

  useEffect(() => {
    if (username) {
      fetchConversations();
    }
  }, [username, fetchConversations]);

  useEffect(() => {
    if (!username) return;
    const key = getConversationStorageKey(username);
    if (currentConversationId !== null) {
      localStorage.setItem(key, currentConversationId.toString());
    } else {
      localStorage.removeItem(key);
    }
  }, [currentConversationId, username]);

  useEffect(() => {
    if (!username || !requestedWorkspaceId || workspaces.length === 0) return;
    const requestedWorkspace = workspaces.find((item) => item.id === requestedWorkspaceId);
    if (!requestedWorkspace) return;
    if (workspaceId === requestedWorkspace.id) return;
    setWorkspaceId(requestedWorkspace.id);
    setSaveTargetWorkspaceId(requestedWorkspace.id);
    updateWorkspacePreference(requestedWorkspace.id, requestedWorkspace.name);
  }, [requestedWorkspaceId, updateWorkspacePreference, username, workspaceId, workspaces]);

  useEffect(() => {
    if (!requestedPrompt) return;
    setInput((current) => {
      if (current.trim()) return current;
      if (messages.length > 0) return current;
      return requestedCourse ? `[${requestedCourse}] ${requestedPrompt}` : requestedPrompt;
    });
    setGeneratedBy("learning_assistant_followup");
  }, [messages.length, requestedCourse, requestedPrompt]);

  useEffect(() => {
    if (!requestedPrompt || messages.length > 0) return;
    const timer = window.setTimeout(() => {
      inputRef.current?.focus();
    }, 80);
    return () => window.clearTimeout(timer);
  }, [messages.length, requestedPrompt]);

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/api/logout`, { method: "POST", credentials: "include" });
    } catch {
    } finally {
      localStorage.removeItem("username");
      if (username) {
        localStorage.removeItem(getConversationStorageKey(username));
      }
      localStorage.removeItem("current_conversation_id");
      router.replace("/login");
    }
  };

  const quickQuestions = ["查询我的成绩", "这学期课表", "我的学分情况", "考试安排"];

  const selectorClassName =
    "h-10 w-full rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] outline-none transition focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]";

  const openSourceLink = (source: string) => {
    const parsed = parseKnowledgeSource(source);
    if (parsed?.workspaceId) {
      const query = new URLSearchParams();
      if (parsed.docId) query.set("doc", String(parsed.docId));
      if (parsed.chunkIndex !== null) query.set("chunk", String(parsed.chunkIndex));
      const next = query.toString()
        ? `/workspace/${parsed.workspaceId}?${query.toString()}`
        : `/workspace/${parsed.workspaceId}`;
      router.push(next);
      return;
    }
  };

  const openRequestedWorkspaceContext = () => {
    if (!requestedWorkspaceId) return;
    const query = new URLSearchParams();
    if (requestedCourse) query.set("course", requestedCourse);
    if (requestedPoint) query.set("point", requestedPoint);
    if (requestedQuestionType) query.set("type", requestedQuestionType);
    const next = query.toString()
      ? `/workspace/${requestedWorkspaceId}?${query.toString()}`
      : `/workspace/${requestedWorkspaceId}`;
    router.push(next);
  };

  const applySuggestedPrompt = (prompt: string, strategyLabel: string) => {
    setSelectedPromptStrategy(strategyLabel);
    setInput(prompt);
    setGeneratedBy("learning_assistant_followup");
    window.setTimeout(() => {
      inputRef.current?.focus();
    }, 60);
  };

  const openBlindSpotLink = (item: ChatBlindSpotItem) => {
    if (!workspaceId) return;
    const query = new URLSearchParams();
    if (item.course_name) query.set("course", item.course_name);
    if (item.top_point) query.set("point", item.top_point);
    router.push(`/workspace/${workspaceId}?${query.toString()}`);
  };

  const openSaveDialog = () => {
    setSaveWorkspaceName("");
    setSaveWorkspaceDesc("");
    setSaveStatus("");
    setSaveTargetWorkspaceId(workspaceId || workspaces[0]?.id || null);
    setSaveDialogOpen(true);
  };

  const handleSaveToWorkspace = async () => {
    if (!username || messages.length === 0) {
      setSaveStatus("当前没有可保存的对话内容");
      return;
    }

    try {
      setSavePending(true);
      setSaveStatus("");

      let targetId = saveTargetWorkspaceId;
      if (!targetId && saveWorkspaceName.trim()) {
        const createRes = await fetch(`${API_BASE}/api/workspace`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            username,
            name: saveWorkspaceName.trim(),
            description: saveWorkspaceDesc.trim(),
          }),
        });
        const createJson = await createRes.json().catch(() => ({}));
        if (!createRes.ok || !createJson?.success) {
          throw new Error(createJson?.detail || `创建工作区失败(${createRes.status})`);
        }
        targetId = createJson.workspace?.id || null;
        await fetchWorkspacePrefs(username);
      }

      if (!targetId) {
        throw new Error("请选择工作区或新建一个工作区");
      }

      const archive = buildConversationMarkdown(messages, currentConversationId);
      const saveRes = await fetch(`${API_BASE}/api/workspace/documents/text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          username,
          workspace_id: targetId,
          filename: archive.filename,
          content: archive.content,
          authority_level: "user",
        }),
      });
      const saveJson = await saveRes.json().catch(() => ({}));
      if (!saveRes.ok || !saveJson?.success) {
        throw new Error(saveJson?.detail || `保存失败(${saveRes.status})`);
      }

      const targetWorkspace = workspaces.find((item) => item.id === targetId);
      if (targetWorkspace) {
        setWorkspaceId(targetId);
        await updateWorkspacePreference(targetWorkspace.id, targetWorkspace.name);
      }
      setSaveStatus("已保存到工作区知识库");
      setTimeout(() => setSaveDialogOpen(false), 600);
    } catch (error) {
      setSaveStatus(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSavePending(false);
    }
  };

  return (
    <>
      <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(219,234,254,0.64),transparent_22%),radial-gradient(circle_at_bottom_right,rgba(226,232,255,0.62),transparent_18%),linear-gradient(180deg,#f4f6f8_0%,#eef2f6_100%)] px-3 py-4 md:px-5 md:py-6">
        <div className="mx-auto flex min-h-[calc(100vh-2.5rem)] max-w-[1500px] overflow-hidden rounded-[1.7rem] border border-slate-200/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.76),rgba(248,250,252,0.84))] shadow-[0_24px_72px_rgba(15,23,42,0.08)] backdrop-blur">
          {sidebarOpen ? <div className="fixed inset-0 z-40 bg-slate-950/20 lg:hidden" onClick={() => setSidebarOpen(false)} /> : null}

          <ChatSidebar
            sidebarOpen={sidebarOpen}
            conversations={conversations}
            currentConversationId={currentConversationId}
            username={username}
            onCloseSidebar={() => setSidebarOpen(false)}
            onNewConversation={newConversation}
            onOpenSaveDialog={openSaveDialog}
            onSelectConversation={selectConversation}
            onDeleteConversation={deleteConversation}
            onLogout={handleLogout}
            canSave={messages.length > 0}
          />

        <main className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 border-b border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(248,250,252,0.84))] backdrop-blur-xl">
            <div className="flex items-center justify-between gap-3 px-4 py-2.5 md:px-5">
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSidebarOpen(true)}>
                  <Menu className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => router.push("/")}>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <div>
                  <div className="text-sm font-semibold text-slate-900">快速会话</div>
                  <div className="text-xs text-slate-500">主界面只保留问答流和最少配置。</div>
                </div>
              </div>
              <Badge variant="success">在线</Badge>
            </div>
            {(requestedWorkspaceId || workspaceId) ? (
              <div className="border-t border-slate-200/80 px-4 py-2 md:px-5">
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span>当前是工作区外溢问答入口</span>
                  <Badge variant="outline">
                    workspace #{requestedWorkspaceId || workspaceId}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs text-slate-600 hover:bg-slate-100"
                    onClick={() => {
                      const targetWorkspaceId = requestedWorkspaceId || workspaceId;
                      if (!targetWorkspaceId) return;
                      router.push(`/workspace/${targetWorkspaceId}`);
                    }}
                  >
                    回到工作区
                  </Button>
                </div>
              </div>
            ) : null}
          </header>

          <div className="flex-1 overflow-hidden">
            <ScrollArea className="h-[calc(100vh-10rem)] md:h-[calc(100vh-9.5rem)]">
              {initialLoading || authLoading ? (
                <PageLoading label="正在加载聊天..." />
              ) : !username ? (
                <div className="flex min-h-[60vh] items-center justify-center px-4">
                  <Card className="w-full max-w-md">
                    <CardContent className="flex flex-col items-center gap-4 p-8 text-center">
                      <User className="h-10 w-10 text-slate-300" />
                      <div>
                        <div className="text-lg font-semibold text-slate-900">未登录</div>
                        <div className="mt-1 text-sm text-slate-500">请先登录后再开始对话</div>
                      </div>
                      <Button onClick={() => router.replace("/login")}>前往登录</Button>
                    </CardContent>
                  </Card>
                </div>
              ) : messages.length === 0 ? (
                <ChatEmptyState
                  requestedPrompt={requestedPrompt}
                  requestedCourse={requestedCourse}
                  requestedStrategy={requestedStrategy}
                  requestedWorkspaceId={requestedWorkspaceId}
                  requestedContextTags={requestedContextTags}
                  quickQuestions={quickQuestions}
                  followUpSuggestions={followUpSuggestions}
                  onQuestionPick={(value) => {
                    setInput(value);
                    inputRef.current?.focus();
                  }}
                  onOpenRequestedWorkspaceContext={openRequestedWorkspaceContext}
                  onApplySuggestedPrompt={applySuggestedPrompt}
                />
              ) : (
                <ChatMessageList
                  messages={messages}
                  workspaceId={workspaceId}
                  messagesEndRef={messagesEndRef}
                  toolDisplayName={toolDisplayName}
                  parseKnowledgeSource={parseKnowledgeSource}
                  onOpenBlindSpotLink={openBlindSpotLink}
                  onOpenSourceLink={openSourceLink}
                />
              )}
            </ScrollArea>
          </div>

          <ChatComposer
            input={input}
            username={username}
            isLoading={isLoading}
            requestedPrompt={requestedPrompt}
            requestedStrategy={requestedStrategy}
            followUpSuggestions={followUpSuggestions}
            showFollowUpSuggestions={shouldShowComposerFollowups}
            modelOptions={modelOptions}
            selectedModelKey={model && provider ? `${provider}::${model}` : ""}
            showThinking={showThinking}
            inputRef={inputRef}
            selectorClassName={selectorClassName}
            onInputChange={(value) => {
              setInput(value);
              if (selectedPromptStrategy) setSelectedPromptStrategy("");
              if (generatedBy && value.trim() !== requestedPrompt.trim()) {
                setGeneratedBy("");
              }
            }}
            onKeyDown={handleKeyDown}
            onApplySuggestedPrompt={applySuggestedPrompt}
            onModelChange={(value) => {
              const selected = modelOptions.find((item) => item.key === value);
              if (!selected) return;
              setProvider(selected.provider);
              setModel(selected.model);
            }}
            onToggleThinking={() => {
              setShowThinking((prev) => !prev);
              setReasoningMode((prev) => (prev === "standard" ? "thinking" : "standard"));
            }}
            onSend={sendMessage}
          />
        </main>
        </div>
      </div>

      <ChatSaveDialog
        open={saveDialogOpen}
        workspaces={workspaces}
        saveTargetWorkspaceId={saveTargetWorkspaceId}
        saveWorkspaceName={saveWorkspaceName}
        saveWorkspaceDesc={saveWorkspaceDesc}
        saveStatus={saveStatus}
        savePending={savePending}
        canSave={messages.length > 0}
        onOpenChange={setSaveDialogOpen}
        onSelectWorkspace={(workspaceTargetId) => setSaveTargetWorkspaceId(workspaceTargetId)}
        onWorkspaceNameChange={(value) => {
          setSaveWorkspaceName(value);
          if (value.trim()) setSaveTargetWorkspaceId(null);
        }}
        onWorkspaceDescChange={setSaveWorkspaceDesc}
        onSave={handleSaveToWorkspace}
      />
    </>
  );
}

function ChatPageFallback() {
  return <PageFallback label="正在加载聊天页面..." />;
}

export default function ChatPage() {
  return (
    <Suspense fallback={<ChatPageFallback />}>
      <ChatPageContent />
    </Suspense>
  );
}



