'use client';

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import MarkdownMessage from "@/components/MarkdownMessage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  Bot,
  BrainCircuit,
  GraduationCap,
  History,
  Loader2,
  LogOut,
  Menu,
  MessageSquare,
  PanelLeft,
  Plus,
  Save,
  Send,
  Sparkles,
  Trash2,
  User,
  WandSparkles,
  Wrench,
} from "lucide-react";

interface ToolCall {
  name: string;
}

interface ToolTrace {
  skill: string;
  tool: string;
  params?: Record<string, unknown>;
  status: "success" | "failed" | "empty";
  error?: string;
}

interface MessageHighlight {
  source: string;
  title: string;
  snippet: string;
  document_id?: number;
  chunk_index?: number;
  score?: number;
}

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  sources?: string[];
  highlights?: MessageHighlight[];
  tool_calls?: ToolCall[];
  tool_trace?: ToolTrace[];
  timestamp?: string;
  streaming?: boolean;
}

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

interface CompositionData {
  owner: string;
  skills: string[];
  mcp_tools: string[];
}

function toolDisplayName(name: string) {
  return (
    {
      query_personal_info: "个人信息",
      query_grades: "成绩查询",
      query_schedule: "课表查询",
      query_exam_schedule: "考试安排",
      query_academic_progress: "学业进度",
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

export default function ChatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [username, setUsername] = useState("");
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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const activeHistoryReqRef = useRef(0);
  const streamFlushTimerRef = useRef<number | null>(null);
  const currentConversationIdRef = useRef<number | null>(null);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;
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
  const getConversationStorageKey = (uname: string) => `current_conversation_id_${uname}`;
  const requestedWorkspaceId = useMemo(() => {
    const raw = searchParams.get("workspace_id");
    const parsed = Number(raw || 0);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  useEffect(() => {
    currentConversationIdRef.current = currentConversationId;
  }, [currentConversationId]);

  const scrollToBottom = (behavior: ScrollBehavior = "auto") => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  const flushAssistantContent = (assistantMsgId: number, content: string) => {
    setMessages((prev) => {
      const idx = prev.findIndex((msg) => msg.id === assistantMsgId);
      if (idx === -1) return prev;
      if (prev[idx].content === content) return prev;
      const next = [...prev];
      next[idx] = { ...next[idx], content };
      return next;
    });
    requestAnimationFrame(() => scrollToBottom("auto"));
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
        const compositionJson = compositionRes.ok ? await compositionRes.json() : null;
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
      if (currentConversationIdRef.current !== conversationId) return;
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
            setMessages(
              data.messages.map((m: any) => ({
                id: m.id,
                role: m.role,
                content: m.content,
                sources: m.meta?.sources || [],
                highlights: m.meta?.highlights || [],
                tool_calls: m.meta?.tool_calls || [],
                tool_trace: m.meta?.tool_trace || [],
                timestamp: new Date(m.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
              }))
            );
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

  const sendMessage = async () => {
    if (!input.trim() || !username || isLoading) return;

    const userMessage = input.trim();
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

    const fallbackToNonStream = async (reason?: string) => {
      try {
        const res = await fetch(`${API_BASE}/api/chat/send`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
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
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          const detail = err?.detail || err?.message || `请求失败(${res.status})`;
          throw new Error(String(detail));
        }
        const data = await res.json();
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content: data?.message || "未获取到回答",
                  streaming: false,
                  highlights: data?.highlights || [],
                  tool_calls: data?.tool_calls || [],
                  tool_trace: data?.tool_trace || [],
                }
              : msg
          )
        );
        if (data?.conversation_id) {
          setCurrentConversationId(data.conversation_id);
          fetchConversations();
        }
      } catch (e) {
        const hint = reason ? `（${reason}）` : "";
        const errText = e instanceof Error ? e.message : "服务暂时不可用";
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId ? { ...msg, content: `请求失败${hint}：${errText}`, streaming: false } : msg
          )
        );
      }
    };

    try {
      activeHistoryReqRef.current++;

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 180000);
      const response = await fetch(`${STREAM_API_BASE}/api/chat/send-stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          "Cache-Control": "no-cache",
          "x-trace-id": `chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        },
        credentials: "include",
        signal: controller.signal,
        cache: "no-store",
        body: JSON.stringify({
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
        }),
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        if (response.status === 403) {
          throw new Error("登录账号与会话不一致，请退出后重新登录");
        }
        throw new Error(err?.detail || err?.message || `请求失败(${response.status})`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("无法读取响应流");
      }

      const decoder = new TextDecoder();
      let aiContent = "";
      let aiThinking = "";
      let conversationId = currentConversationId;
      let sseBuffer = "";
      let receivedAnyChunk = false;

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

          for (const dataLine of dataLines) {
            if (!dataLine) continue;
            try {
              const data = JSON.parse(dataLine);

              if (data.conversation_id && !conversationId) {
                conversationId = data.conversation_id;
              }

              if (data.content) {
                aiContent += data.content;
                receivedAnyChunk = true;
                if (streamFlushTimerRef.current === null) {
                  streamFlushTimerRef.current = window.setTimeout(() => {
                    setMessages((prev) => {
                      const idx = prev.findIndex((msg) => msg.id === assistantMsgId);
                      if (idx === -1) return prev;
                      const next = [...prev];
                      next[idx] = { ...next[idx], content: aiContent, thinking: aiThinking };
                      return next;
                    });
                    requestAnimationFrame(() => scrollToBottom("auto"));
                    streamFlushTimerRef.current = null;
                  }, 60);
                }
              }

              if (data.thinking) {
                aiThinking += data.thinking;
                receivedAnyChunk = true;
                if (streamFlushTimerRef.current === null) {
                  streamFlushTimerRef.current = window.setTimeout(() => {
                    setMessages((prev) => {
                      const idx = prev.findIndex((msg) => msg.id === assistantMsgId);
                      if (idx === -1) return prev;
                      const next = [...prev];
                      next[idx] = { ...next[idx], content: aiContent, thinking: aiThinking };
                      return next;
                    });
                    requestAnimationFrame(() => scrollToBottom("auto"));
                    streamFlushTimerRef.current = null;
                  }, 60);
                }
              }

              if (data.ping) {
                if (!receivedAnyChunk) {
                  const stageHint = data.stage === "tool_call" ? "正在调用教务工具..." : "正在生成回答...";
                  setMessages((prev) => {
                    const idx = prev.findIndex((msg) => msg.id === assistantMsgId);
                    if (idx === -1) return prev;
                    if ((prev[idx].content || "") === stageHint) return prev;
                    const next = [...prev];
                    next[idx] = { ...next[idx], content: stageHint };
                    return next;
                  });
                }
                continue;
              }

              if (data.done) {
                if (streamFlushTimerRef.current !== null) {
                  clearTimeout(streamFlushTimerRef.current);
                  streamFlushTimerRef.current = null;
                }
                flushAssistantContent(assistantMsgId, aiContent);
                if (data.conversation_id) {
                  conversationId = data.conversation_id;
                  setCurrentConversationId(conversationId);
                  fetchConversations();
                }
                setMessages((prev) => {
                  const idx = prev.findIndex((msg) => msg.id === assistantMsgId);
                  if (idx === -1) return prev;
                  const next = [...prev];
                  next[idx] = {
                    ...next[idx],
                    highlights: data.highlights || next[idx].highlights || [],
                    tool_calls: data.tool_calls || next[idx].tool_calls || [],
                    tool_trace: data.tool_trace || next[idx].tool_trace || [],
                    streaming: false,
                  };
                  return next;
                });
                continue;
              }
            } catch {
            }
          }
        }
      }

      if (sseBuffer.trim().startsWith("data:")) {
        try {
          const tail = sseBuffer.trim().replace(/^data:\s?/, "").trim();
          const data = JSON.parse(tail);
          if (data.content) {
            aiContent += data.content;
            receivedAnyChunk = true;
            flushAssistantContent(assistantMsgId, aiContent);
          }
          if (data.conversation_id && !conversationId) {
            setCurrentConversationId(data.conversation_id);
          }
        } catch {
        }
      }

      if (!receivedAnyChunk) {
        await fallbackToNonStream("流式无分片");
      } else {
        setMessages((prev) => prev.map((msg) => (msg.id === assistantMsgId ? { ...msg, streaming: false } : msg)));
      }
    } catch (error) {
      console.error("流式消息失败:", error);
      if (streamFlushTimerRef.current !== null) {
        clearTimeout(streamFlushTimerRef.current);
        streamFlushTimerRef.current = null;
      }
      await fallbackToNonStream(error instanceof Error ? error.message : "流式失败");
    } finally {
      if (streamFlushTimerRef.current !== null) {
        clearTimeout(streamFlushTimerRef.current);
        streamFlushTimerRef.current = null;
      }
      setIsLoading(false);
    }
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
    activeHistoryReqRef.current++;
    setCurrentConversationId(id);
    fetchHistory(id);
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
    let mounted = true;
    const bootstrap = async () => {
      try {
        const meRes = await fetch(`${API_BASE}/api/auth/me`, { credentials: "include" });
        if (!meRes.ok) {
          if (mounted) router.replace("/login");
          return;
        }
        const me = await meRes.json();
        if (!me?.authenticated || !me?.username) {
          if (mounted) router.replace("/login");
          return;
        }

        const authUsername = String(me.username);
        if (!mounted) return;
        setUsername(authUsername);
        localStorage.setItem("username", authUsername);
        await Promise.all([fetchModelPrefs(authUsername), fetchWorkspacePrefs(authUsername)]);

        const migratedKey = getConversationStorageKey(authUsername);
        const oldConversationId = localStorage.getItem("current_conversation_id");
        if (oldConversationId && !localStorage.getItem(migratedKey)) {
          localStorage.setItem(migratedKey, oldConversationId);
          localStorage.removeItem("current_conversation_id");
        }

        const savedConversationId = localStorage.getItem(migratedKey);
        if (!savedConversationId) {
          setInitialLoading(false);
          return;
        }

        const convId = parseInt(savedConversationId, 10);
        if (Number.isNaN(convId)) {
          setInitialLoading(false);
          return;
        }

        setCurrentConversationId(convId);
        const reqId = ++activeHistoryReqRef.current;
        const res = await fetch(`${API_BASE}/api/chat/history/${convId}?username=${encodeURIComponent(authUsername)}`, {
          credentials: "include",
        });
        if (reqId !== activeHistoryReqRef.current || !mounted) return;

        if (res.ok) {
          const data = await res.json();
          if (reqId !== activeHistoryReqRef.current || !mounted) return;
          if (data?.messages) {
            setMessages(
              data.messages.map((m: any) => ({
                id: m.id,
                role: m.role,
                content: m.content,
                sources: m.meta?.sources || [],
                highlights: m.meta?.highlights || [],
                tool_calls: m.meta?.tool_calls || [],
                tool_trace: m.meta?.tool_trace || [],
                timestamp: new Date(m.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
              }))
            );
          }
        } else if (res.status === 404) {
          localStorage.removeItem(migratedKey);
          setCurrentConversationId(null);
        }
      } catch (err) {
        console.error("初始化聊天会话失败:", err);
        router.replace("/login");
      } finally {
        if (mounted) setInitialLoading(false);
      }
    };

    bootstrap();
    return () => {
      mounted = false;
    };
  }, [API_BASE, router, fetchModelPrefs, fetchWorkspacePrefs]);

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
      <div className="flex min-h-screen bg-transparent">
        {sidebarOpen && <div className="fixed inset-0 z-40 bg-slate-950/20 lg:hidden" onClick={() => setSidebarOpen(false)} />}

        <aside
          className={cn(
            "fixed inset-y-0 left-0 z-50 flex w-[260px] flex-col border-r border-[hsl(var(--border))] bg-white/95 backdrop-blur-xl transition-transform duration-200 lg:static lg:translate-x-0",
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          )}
        >
          <div className="p-5">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-sm">
                  <GraduationCap className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-900">校园 AI 助手</div>
                  <div className="text-xs text-slate-500">快速会话</div>
                </div>
              </div>
              <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSidebarOpen(false)}>
                <PanelLeft className="h-4 w-4" />
              </Button>
            </div>

            <div className="grid gap-2">
              <Button className="w-full justify-start" onClick={newConversation}>
                <Plus className="h-4 w-4" />
                新建对话
              </Button>
              <Button variant="outline" className="w-full justify-start" onClick={openSaveDialog} disabled={messages.length === 0}>
                <Save className="h-4 w-4" />
                保存到工作区
              </Button>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2">
              <div className="col-span-2 rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs leading-6 text-slate-500">
                快速会话只保留新建、保存到工作区和历史。Skill、MCP、模型配置统一去平台页管理。
              </div>
            </div>
          </div>

          <Separator />

          <div className="flex-1 px-4 py-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
              <History className="h-4 w-4 text-slate-500" />
              对话历史
            </div>
            <ScrollArea className="h-[calc(100vh-25rem)] pr-2 lg:h-[calc(100vh-22rem)]">
              <div className="space-y-2">
                {conversations.length === 0 ? (
                  <Card className="border-dashed shadow-none">
                    <CardContent className="flex flex-col items-center gap-2 p-6 text-center text-sm text-slate-500">
                      <MessageSquare className="h-8 w-8 text-slate-300" />
                      暂无对话记录
                    </CardContent>
                  </Card>
                ) : (
                  conversations.map((conv) => (
                    <button
                      key={conv.id}
                      onClick={() => selectConversation(conv.id)}
                      className={cn(
                        "group w-full rounded-lg border px-3 py-3 text-left transition-colors",
                        currentConversationId === conv.id
                          ? "border-[hsl(var(--primary))] bg-blue-50"
                          : "border-[hsl(var(--border))] bg-white hover:bg-[hsl(var(--accent))]"
                      )}
                    >
                      <div className="flex items-start gap-3">
                        <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium text-slate-900">{conv.title}</div>
                          <div className="mt-1 text-xs text-slate-500">{new Date(conv.created_at).toLocaleString("zh-CN")}</div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100"
                          onClick={(e) => deleteConversation(conv.id, e)}
                        >
                          <Trash2 className="h-4 w-4 text-slate-500" />
                        </Button>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </ScrollArea>
          </div>

          <div className="border-t border-[hsl(var(--border))] p-4">
            <Card className="shadow-none">
              <CardContent className="flex items-center gap-3 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">
                  <User className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-slate-900">{username || "未登录"}</div>
                  <div className="text-xs text-slate-500">学号登录</div>
                </div>
                <Button variant="ghost" size="icon" onClick={handleLogout}>
                  <LogOut className="h-4 w-4 text-slate-500" />
                </Button>
              </CardContent>
            </Card>
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 border-b border-[hsl(var(--border))] bg-white/80 backdrop-blur-xl">
            <div className="flex items-center justify-between gap-3 px-4 py-3 md:px-6">
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSidebarOpen(true)}>
                  <Menu className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => router.push("/")}>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <div>
                  <div className="text-sm font-semibold text-slate-900">快速会话</div>
                  <div className="text-xs text-slate-500">保留干净的问答界面和流式输出，复杂配置放到别处。</div>
                </div>
              </div>
              <Badge variant="success">在线</Badge>
            </div>
          </header>

          <div className="flex-1 overflow-hidden">
            <ScrollArea className="h-[calc(100vh-10rem)] md:h-[calc(100vh-9.5rem)]">
              {initialLoading ? (
                <div className="flex min-h-[60vh] items-center justify-center">
                  <div className="flex flex-col items-center gap-3 text-sm text-slate-500">
                    <Loader2 className="h-8 w-8 animate-spin text-[hsl(var(--primary))]" />
                    加载中...
                  </div>
                </div>
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
                <div className="mx-auto flex min-h-[60vh] max-w-3xl flex-col items-center justify-center px-4 py-12 text-center">
                  <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-sm">
                    <Bot className="h-10 w-10" />
                  </div>
                  <h2 className="text-2xl font-semibold tracking-tight text-slate-950">快速会话</h2>
                  <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
                    这里专注快问快答。模型从输入框旁边选，问完可以直接保存到工作区。
                  </p>
                  <div className="mt-8 grid w-full max-w-2xl gap-3 sm:grid-cols-2">
                    {quickQuestions.map((question) => (
                      <button
                        key={question}
                        onClick={() => {
                          setInput(question);
                          inputRef.current?.focus();
                        }}
                        className="rounded-lg border border-[hsl(var(--border))] bg-white p-4 text-left transition hover:bg-[hsl(var(--accent))]"
                      >
                        <WandSparkles className="mb-3 h-4 w-4 text-[hsl(var(--primary))]" />
                        <div className="text-sm font-medium text-slate-900">{question}</div>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6 md:px-6">
                  {messages.map((msg) => (
                    <div key={msg.id} className={cn("flex gap-3", msg.role === "user" && "flex-row-reverse")}>
                      <div
                        className={cn(
                          "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white",
                          msg.role === "user" ? "bg-slate-900" : "bg-[hsl(var(--primary))]"
                        )}
                      >
                        {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                      </div>
                      <div className={cn("flex max-w-[85%] flex-1 flex-col gap-1", msg.role === "user" ? "items-end" : "items-start")}>
                        <Card className={cn("max-w-full", msg.role === "user" ? "bg-slate-900 text-white" : "bg-white")}>
                          <CardContent className="space-y-3 p-4">
                            {msg.role === "assistant" ? (
                              <>
                                {msg.thinking && (
                                  <div className="whitespace-pre-wrap rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                                    <span className="font-medium">思考：</span>
                                    {msg.thinking}
                                  </div>
                                )}
                                <MarkdownMessage content={msg.content || "正在思考..."} />
                              </>
                            ) : (
                              <p className="whitespace-pre-wrap text-sm leading-6">{msg.content}</p>
                            )}

                            {msg.tool_calls && msg.tool_calls.length > 0 && (
                              <div className="flex flex-wrap gap-2 border-t border-[hsl(var(--border))] pt-3">
                                {msg.tool_calls.map((tc, i) => (
                                  <Badge key={`${tc.name}-${i}`} variant="secondary" className="gap-1.5">
                                    <Wrench className="h-3 w-3" />
                                    {toolDisplayName(tc.name)}
                                  </Badge>
                                ))}
                              </div>
                            )}

                            {msg.tool_trace && msg.tool_trace.length > 0 && (
                              <div className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-3">
                                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Tool Trace</div>
                                <div className="space-y-2">
                                  {msg.tool_trace.map((trace, i) => (
                                    <div key={`${trace.tool}-${i}`} className="rounded-md border border-[hsl(var(--border))] bg-white px-3 py-2 text-xs text-slate-700">
                                      <div className="flex flex-wrap items-center gap-2">
                                        <span className="font-medium">{trace.skill}</span>
                                        <span className="text-slate-400">→</span>
                                        <span>{trace.tool}</span>
                                        <Badge variant={trace.status === "success" ? "success" : trace.status === "failed" ? "destructive" : "warning"}>
                                          {trace.status}
                                        </Badge>
                                      </div>
                                      {trace.params && Object.keys(trace.params).length > 0 && (
                                        <div className="mt-1 text-slate-500">params: {JSON.stringify(trace.params)}</div>
                                      )}
                                      {trace.error && <div className="mt-1 text-rose-600">{trace.error}</div>}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {msg.sources && msg.sources.length > 0 && (
                              <div className="border-t border-[hsl(var(--border))] pt-3">
                                <div className="mb-2 text-xs font-medium text-slate-500">参考来源</div>
                                <div className="flex flex-wrap gap-2">
                                  {msg.sources.map((source, index) => (
                                    (() => {
                                      const parsed = parseKnowledgeSource(source);
                                      if (parsed?.workspaceId) {
                                        return (
                                          <button
                                            key={`${source}-${index}`}
                                            type="button"
                                            onClick={() => openSourceLink(source)}
                                            className="max-w-full text-left"
                                          >
                                            <Badge variant="outline" className="max-w-full break-all text-[11px] text-slate-600 hover:bg-[hsl(var(--accent))]">
                                              {parsed.title || source}
                                            </Badge>
                                          </button>
                                        );
                                      }
                                      return (
                                        <Badge key={`${source}-${index}`} variant="outline" className="max-w-full break-all text-[11px] text-slate-600">
                                          {source}
                                        </Badge>
                                      );
                                    })()
                                  ))}
                                </div>
                              </div>
                            )}

                            {msg.highlights && msg.highlights.length > 0 && (
                              <div className="border-t border-[hsl(var(--border))] pt-3">
                                <div className="mb-2 text-xs font-medium text-slate-500">引用片段</div>
                                <div className="space-y-2">
                                  {msg.highlights.map((highlight, index) => {
                                    const parsed = parseKnowledgeSource(highlight.source);
                                    return (
                                      <button
                                        key={`${highlight.source}-${index}`}
                                        type="button"
                                        onClick={() => openSourceLink(highlight.source)}
                                        className="block w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-left transition hover:bg-[hsl(var(--accent))]"
                                      >
                                        <div className="flex items-center justify-between gap-2">
                                          <div className="truncate text-xs font-medium text-slate-900">{highlight.title || parsed?.title || "引用片段"}</div>
                                          {typeof highlight.score === "number" ? (
                                            <span className="text-[11px] text-slate-400">score {highlight.score.toFixed(3)}</span>
                                          ) : null}
                                        </div>
                                        <div className="mt-2 line-clamp-3 text-xs leading-6 text-slate-600">{highlight.snippet}</div>
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </CardContent>
                        </Card>
                        <span className="px-1 text-xs text-slate-400">{msg.timestamp}</span>
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </ScrollArea>
          </div>

          <div className="border-t border-[hsl(var(--border))] bg-white/85 p-4 backdrop-blur-xl md:px-6">
            <div className="mx-auto max-w-5xl">
              <Card>
                <CardContent className="p-4">
                  <Textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={username ? "输入你的问题，Shift+Enter 换行" : "请先登录"}
                    disabled={!username || isLoading}
                    className="min-h-24 resize-none border-0 bg-transparent px-0 py-0 shadow-none focus-visible:ring-0"
                  />
                  <div className="mt-3 flex items-center justify-between gap-3">
                    <div className="flex flex-wrap gap-2">
                      <select
                        value={model && provider ? `${provider}::${model}` : ""}
                        onChange={(e) => {
                          const selected = modelOptions.find((item) => item.key === e.target.value);
                          if (!selected) return;
                          setProvider(selected.provider);
                          setModel(selected.model);
                        }}
                        disabled={isLoading || modelOptions.length === 0}
                        className={selectorClassName}
                      >
                        {modelOptions.map((item) => (
                          <option key={item.key} value={item.key}>
                            {item.model}
                          </option>
                        ))}
                      </select>
                      <Button
                        type="button"
                        variant={showThinking ? "default" : "outline"}
                        onClick={() => {
                          setShowThinking((prev) => !prev);
                          setReasoningMode((prev) => (prev === "standard" ? "thinking" : "standard"));
                        }}
                        disabled={isLoading}
                      >
                        <BrainCircuit className="h-4 w-4" />
                        思考模式
                      </Button>
                    </div>
                    <Button onClick={sendMessage} disabled={!username || !input.trim() || isLoading}>
                      {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                      发送
                    </Button>
                  </div>
                </CardContent>
              </Card>
              <p className="mt-2 text-center text-xs text-slate-400">AI 助手可能会有错误，请核实重要信息</p>
            </div>
          </div>
        </main>
      </div>

      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>保存到工作区</DialogTitle>
            <DialogDescription>将当前对话整理为 Markdown 文档，存入工作区知识库。</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <div className="text-sm font-medium text-slate-900">选择工作区</div>
              <div className="space-y-2">
                {workspaces.map((item) => (
                  <label key={item.id} className="flex cursor-pointer items-start gap-3 rounded-lg border border-[hsl(var(--border))] p-3 text-sm hover:bg-[hsl(var(--accent))]">
                    <input
                      type="radio"
                      name="save-workspace"
                      checked={saveTargetWorkspaceId === item.id}
                      onChange={() => setSaveTargetWorkspaceId(item.id)}
                      className="mt-1"
                    />
                    <div>
                      <div className="font-medium text-slate-900">{item.name}</div>
                      <div className="text-xs text-slate-500">{item.description || item.slug}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <Separator />

            <div className="space-y-2">
              <div className="text-sm font-medium text-slate-900">或新建工作区</div>
              <Input
                value={saveWorkspaceName}
                onChange={(e) => {
                  setSaveWorkspaceName(e.target.value);
                  if (e.target.value.trim()) setSaveTargetWorkspaceId(null);
                }}
                placeholder="例如：微积分答疑"
              />
              <Textarea value={saveWorkspaceDesc} onChange={(e) => setSaveWorkspaceDesc(e.target.value)} placeholder="描述这个工作区的用途" className="min-h-24" />
            </div>

            {saveStatus && <div className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-3 py-2 text-sm text-slate-700">{saveStatus}</div>}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setSaveDialogOpen(false)} disabled={savePending}>取消</Button>
            <Button onClick={handleSaveToWorkspace} disabled={savePending || messages.length === 0}>
              {savePending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
