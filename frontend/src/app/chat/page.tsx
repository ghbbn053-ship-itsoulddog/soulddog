'use client';

import React, { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import MarkdownMessage from "@/components/MarkdownMessage";
import { 
  Send, 
  User, 
  Bot, 
  Loader2, 
  Plus, 
  Trash2, 
  Menu, 
  X, 
  GraduationCap,
  MessageSquare,
  ChevronLeft,
  Sparkles,
  Wrench,
  LogOut,
  Settings,
  Blocks
} from "lucide-react";

interface ToolCall {
  name: string;
}

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  sources?: string[];
  tool_calls?: ToolCall[];
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

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [username, setUsername] = useState("");
  const [providers, setProviders] = useState<ProviderItem[]>([]);
  const [provider, setProvider] = useState("qwen");
  const [model, setModel] = useState("");
  const [reasoningMode, setReasoningMode] = useState("standard");
  const [showThinking, setShowThinking] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true); // 初始加载状态，防止空状态闪烁
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const activeHistoryReqRef = useRef(0);
  const streamFlushTimerRef = useRef<number | null>(null);
  const currentConversationIdRef = useRef<number | null>(null);

  // 默认走同域 /api 反向代理，避免不同访问入口下的地址不一致问题
  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;
  const getConversationStorageKey = (uname: string) => `current_conversation_id_${uname}`;

  useEffect(() => {
    currentConversationIdRef.current = currentConversationId;
  }, [currentConversationId]);

  // 滚动到底部
  const scrollToBottom = (behavior: ScrollBehavior = "auto") => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  const flushAssistantContent = (assistantMsgId: number, content: string) => {
    setMessages(prev => {
      const idx = prev.findIndex(msg => msg.id === assistantMsgId);
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

  // 获取对话列表
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

  const fetchModelPrefs = useCallback(async (uname: string) => {
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
      // ignore
    }
  }, [API_BASE]);

  // 获取对话历史
  const fetchHistory = useCallback(async (conversationId: number, uname: string = username) => {
    if (!uname) return;
    if (isLoading) return;
    if (currentConversationIdRef.current !== conversationId) return;
    const reqId = ++activeHistoryReqRef.current;
    try {
      const res = await fetch(
        `${API_BASE}/api/chat/history/${conversationId}?username=${encodeURIComponent(uname)}`,
        { credentials: "include" }
      );
      // 忽略过时请求，避免覆盖最新会话或正在发送中的消息
      if (reqId !== activeHistoryReqRef.current) return;
      if (res.ok) {
        const data = await res.json();
        if (reqId !== activeHistoryReqRef.current) return;
        if (data?.messages) {
          setMessages(data.messages.map((m: any) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            sources: m.meta?.sources || [],
            timestamp: new Date(m.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
          })));
          return;
        }
      }
      // 仅在会话确实不存在(404)时清理，避免临时网络/权限抖动导致界面闪空
      if (reqId === activeHistoryReqRef.current && res.status === 404) {
        setCurrentConversationId(null);
        localStorage.removeItem(getConversationStorageKey(uname));
        setMessages([]);
      }
    } catch (error) {
      console.error("获取历史失败:", error);
      // 网络异常时保留当前消息，避免“闪一下全无”
    }
  }, [API_BASE, username, isLoading]);

  // 发送消息（流式版本）
  const sendMessage = async () => {
    if (!input.trim() || !username || isLoading) return;

    const userMessage = input.trim();
    const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    const userMsgId = Date.now();
    const assistantMsgId = userMsgId + 1;
    
    setInput("");
    setIsLoading(true);
    
    // 合并添加用户消息和空assistant消息，避免两次setState闪烁
    setMessages(prev => [...prev, 
      { id: userMsgId, role: "user", content: userMessage, timestamp: now },
      { id: assistantMsgId, role: "assistant", content: "", timestamp: now, streaming: true }
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
            override_provider: provider,
            override_model: model,
            reasoning_mode: reasoningMode,
            show_thinking: showThinking,
          })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          const detail = err?.detail || err?.message || `请求失败(${res.status})`;
          throw new Error(String(detail));
        }
        const data = await res.json();
        setMessages(prev =>
          prev.map(msg =>
            msg.id === assistantMsgId
              ? { ...msg, content: data?.message || "未获取到回答", streaming: false, tool_calls: data?.tool_calls || [] }
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
        setMessages(prev =>
          prev.map(msg =>
            msg.id === assistantMsgId
              ? { ...msg, content: `请求失败${hint}：${errText}`, streaming: false }
              : msg
          )
        );
      }
    };

    try {
      // 发送新消息时使所有未完成的历史加载请求失效，防止覆盖当前消息列表
      activeHistoryReqRef.current++;

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 180000);
      const response = await fetch(`${API_BASE}/api/chat/send-stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
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
          override_provider: provider,
          override_model: model,
          reasoning_mode: reasoningMode,
          show_thinking: showThinking,
        })
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
        // 兼容 \n\n 与 \r\n\r\n 两种 SSE 分隔
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
                // 节流刷新：降低高频分片导致的整页重绘抖动
                if (streamFlushTimerRef.current === null) {
                  streamFlushTimerRef.current = window.setTimeout(() => {
                    setMessages(prev => {
                      const idx = prev.findIndex(msg => msg.id === assistantMsgId);
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
                    setMessages(prev => {
                      const idx = prev.findIndex(msg => msg.id === assistantMsgId);
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
                // 后端保活帧，忽略
                continue;
              }

              if (data.done) {
                if (streamFlushTimerRef.current !== null) {
                  clearTimeout(streamFlushTimerRef.current);
                  streamFlushTimerRef.current = null;
                }
                flushAssistantContent(assistantMsgId, aiContent);
                // 流式完成（注意：某些返回会把 content + done 放在同一帧，需先处理 content 再结束）
                if (data.conversation_id) {
                  conversationId = data.conversation_id;
                  setCurrentConversationId(conversationId);
                  fetchConversations();
                }
                if (data.tool_calls && data.tool_calls.length > 0) {
                  setMessages(prev => {
                    const idx = prev.findIndex(msg => msg.id === assistantMsgId);
                    if (idx === -1) return prev;
                    const next = [...prev];
                    next[idx] = { ...next[idx], tool_calls: data.tool_calls, streaming: false };
                    return next;
                  });
                } else {
                  setMessages(prev => {
                    const idx = prev.findIndex(msg => msg.id === assistantMsgId);
                    if (idx === -1) return prev;
                    const next = [...prev];
                    next[idx] = { ...next[idx], streaming: false };
                    return next;
                  });
                }
                continue;
              }
            } catch (e) {
              // 允许分片未完整时的解析失败，等待后续分片拼接
            }
          }
        }
      }

      // 如果网络切分导致最后一个事件没被 \n\n 结束，这里兜底处理一次
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
          // ignore
        }
      }

      // 流接口返回成功但没有有效分片时，给出可见兜底信息
      if (!receivedAnyChunk) {
        await fallbackToNonStream("流式无分片");
      } else {
        // 确保任何路径都能结束 streaming 状态
        setMessages(prev =>
          prev.map(msg =>
            msg.id === assistantMsgId ? { ...msg, streaming: false } : msg
          )
        );
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

  // 处理回车发送
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // 新建对话
  const newConversation = () => {
    setCurrentConversationId(null);
    setMessages([]);
    if (username) {
      localStorage.removeItem(getConversationStorageKey(username));
    }
    setSidebarOpen(false);
  };

  // 选择对话
  const selectConversation = (id: number) => {
    if (isLoading) return;
    activeHistoryReqRef.current++;
    setCurrentConversationId(id);
    fetchHistory(id);
    setSidebarOpen(false);
  };

  // 删除对话
  const deleteConversation = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(
        `${API_BASE}/api/chat/conversations/${id}?username=${encodeURIComponent(username || '')}`,
        { method: "DELETE", credentials: "include" }
      );
      if (currentConversationId === id) {
        newConversation();
      }
      fetchConversations();
    } catch (error) {
      console.error("删除失败:", error);
    }
  };

  // 页面加载时先验证服务端会话，再恢复本地会话ID
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
        fetchModelPrefs(authUsername);

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
        const res = await fetch(
          `${API_BASE}/api/chat/history/${convId}?username=${encodeURIComponent(authUsername)}`,
          { credentials: "include" }
        );
        if (reqId !== activeHistoryReqRef.current || !mounted) return;

        if (res.ok) {
          const data = await res.json();
          if (reqId !== activeHistoryReqRef.current || !mounted) return;
          if (data?.messages) {
            setMessages(data.messages.map((m: any) => ({
              id: m.id,
              role: m.role,
              content: m.content,
              sources: m.meta?.sources || [],
              timestamp: new Date(m.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
            })));
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
  }, [API_BASE, router, fetchModelPrefs]);

  // 当 username 变化时加载对话列表
  useEffect(() => {
    if (username) {
      fetchConversations();
    }
  }, [username, fetchConversations]);
  
  // 当 currentConversationId 变化时，保存到 localStorage
  useEffect(() => {
    if (!username) return;
    const key = getConversationStorageKey(username);
    if (currentConversationId !== null) {
      localStorage.setItem(key, currentConversationId.toString());
    } else {
      localStorage.removeItem(key);
    }
  }, [currentConversationId, username]);

  // 退出登录
  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/api/logout`, { method: "POST", credentials: "include" });
    } catch {
      // ignore
    } finally {
      localStorage.removeItem("username");
      if (username) {
        localStorage.removeItem(getConversationStorageKey(username));
      }
      localStorage.removeItem("current_conversation_id");
      router.replace("/login");
    }
  };

  // 快捷问题
  const quickQuestions = [
    "查询我的成绩",
    "这学期课表",
    "我的学分情况",
    "考试安排"
  ];

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* 移动端侧边栏遮罩 */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 侧边栏 */}
      <div className={`
        fixed lg:static inset-y-0 left-0 z-50
        bg-white/80 backdrop-blur-xl border-r border-gray-200/50
        transition-all duration-300 ease-in-out
        ${sidebarOpen ? "translate-x-0 w-72" : "-translate-x-full lg:translate-x-0 lg:w-72"}
        flex flex-col shadow-xl lg:shadow-none
      `}>
        {/* 侧边栏头部 */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
                <GraduationCap className="w-6 h-6 text-white" />
              </div>
              <span className="font-bold text-lg bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                校园AI助手
              </span>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden p-2 hover:bg-gray-100 rounded-lg transition"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
          </div>
            <button
              onClick={newConversation}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-gray-900 text-white rounded-xl hover:bg-gray-800 transition shadow-lg shadow-gray-900/20"
            >
              <Plus className="w-4 h-4" />
              <span className="font-medium">新建对话</span>
            </button>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <button
              onClick={() => router.push("/settings/models")}
              className="flex items-center justify-center gap-1.5 py-2 px-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition text-sm text-gray-700"
            >
              <Settings className="w-4 h-4" />
              模型
            </button>
            <button
              onClick={() => router.push("/skills")}
              className="flex items-center justify-center gap-1.5 py-2 px-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition text-sm text-gray-700"
            >
              <Blocks className="w-4 h-4" />
              Skills
            </button>
            <button
              onClick={() => router.push("/mcp")}
              className="col-span-2 flex items-center justify-center gap-1.5 py-2 px-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition text-sm text-gray-700"
            >
              <Wrench className="w-4 h-4" />
              MCP 工具
            </button>
            <button
              onClick={() => router.push("/composition")}
              className="col-span-2 flex items-center justify-center gap-1.5 py-2 px-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition text-sm text-gray-700"
            >
              <Blocks className="w-4 h-4" />
              组合编排
            </button>
          </div>
        </div>

        {/* 对话列表 */}
        <div className="flex-1 overflow-y-auto px-2 py-2">
          {conversations.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <MessageSquare className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">暂无对话记录</p>
            </div>
          ) : (
            <div className="space-y-1">
              {conversations.map(conv => (
                <div
                  key={conv.id}
                  onClick={() => selectConversation(conv.id)}
                  className={`
                    group flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all
                    ${currentConversationId === conv.id 
                      ? "bg-gray-100" 
                      : "hover:bg-gray-50"
                    }
                  `}
                >
                  <MessageSquare className={`w-4 h-4 flex-shrink-0 ${
                    currentConversationId === conv.id ? "text-gray-700" : "text-gray-400"
                  }`} />
                  <span className="truncate flex-1 text-sm text-gray-700">
                    {conv.title}
                  </span>
                  <button
                    onClick={(e) => deleteConversation(conv.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-200 rounded transition"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-gray-500" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 用户信息 */}
        <div className="p-4 border-t border-gray-100">
          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
              <User className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-gray-900 truncate">{username || "未登录"}</p>
              <p className="text-xs text-gray-500">学号登录</p>
            </div>
            <button
              onClick={handleLogout}
              className="p-2 hover:bg-gray-200 rounded-lg transition"
              title="退出登录"
            >
              <LogOut className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
      </div>

      {/* 主聊天区 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部栏 */}
        <header className="bg-white/80 backdrop-blur-xl border-b border-gray-200/50 px-4 py-3 flex items-center justify-between sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 hover:bg-gray-100 rounded-xl transition"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h1 className="font-semibold text-gray-800">
              {currentConversationId ? "当前对话" : "新对话"}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-3 py-1.5 bg-green-100 text-green-700 rounded-full font-medium">
              在线
            </span>
          </div>
        </header>

        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto">
          {initialLoading ? (
            /* 初始加载中：显示加载指示器而非空状态，防止闪烁 */
            <div className="flex items-center justify-center h-full">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-gray-400">加载中...</p>
              </div>
            </div>
          ) : !username ? (
            <div className="flex flex-col items-center justify-center min-h-[60vh] px-4">
              <div className="w-20 h-20 bg-gradient-to-br from-gray-400 to-gray-500 rounded-2xl flex items-center justify-center shadow-2xl shadow-gray-400/20 mb-6">
                <User className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-800 mb-2">未登录</h2>
              <p className="text-gray-500 mb-6 text-center max-w-md">请先登录后再开始对话</p>
              <button
                onClick={() => { router.replace("/login"); }}
                className="px-5 py-2.5 rounded-xl bg-gray-900 text-white hover:bg-gray-800 transition"
              >
                前往登录
              </button>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center min-h-[60vh] px-4">
              <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-2xl shadow-blue-500/20 mb-6">
                <Bot className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-800 mb-2">我是你的校园AI助手</h2>
              <p className="text-gray-500 mb-8 text-center max-w-md">
                我可以帮你查询成绩、课表、学分等信息，也可以回答关于学校的各种问题
              </p>
              
              {/* 快捷问题 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
                {quickQuestions.map((question, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setInput(question);
                      inputRef.current?.focus();
                    }}
                    className="p-4 text-left bg-white border border-gray-200 rounded-xl hover:border-blue-300 hover:shadow-md transition group"
                  >
                    <Sparkles className="w-4 h-4 text-blue-500 mb-2 group-hover:scale-110 transition" />
                    <p className="text-sm text-gray-700 font-medium">{question}</p>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto py-6 px-4 space-y-6">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
                >
                  {/* 头像 */}
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center shadow-md ${
                    msg.role === "user" 
                      ? "bg-gradient-to-br from-blue-500 to-blue-600" 
                      : "bg-gradient-to-br from-purple-500 to-purple-600"
                  }`}>
                    {msg.role === "user" ? (
                      <User className="w-4 h-4 text-white" />
                    ) : (
                      <Bot className="w-4 h-4 text-white" />
                    )}
                  </div>

                  {/* 消息内容 */}
                  <div className={`flex-1 max-w-[85%] sm:max-w-[75%] ${
                    msg.role === "user" ? "items-end" : "items-start"
                  } flex flex-col`}>
                    <div className={`
                      rounded-2xl px-4 py-3 shadow-sm
                      ${msg.role === "user" 
                        ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-br-md" 
                        : "bg-white border border-gray-200 rounded-bl-md"
                      }
                    `}>
                      {msg.role === 'assistant' ? (
                        <>
                          {msg.thinking && (
                            <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 whitespace-pre-wrap">
                              <span className="font-medium">思考：</span>{msg.thinking}
                            </div>
                          )}
                          <MarkdownMessage content={msg.content || "✨ 正在思考..."} />
                        </>
                      ) : (
                        <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                      )}
                      
                      {/* 工具调用标记 */}
                      {msg.tool_calls && msg.tool_calls.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-gray-100 flex flex-wrap gap-1.5">
                          {msg.tool_calls.map((tc, i) => (
                            <span key={i} className="inline-flex items-center gap-1 text-xs px-2 py-1 bg-purple-50 text-purple-700 rounded-lg border border-purple-200">
                              <Wrench className="w-3 h-3" />
                              {tc.name === "query_personal_info" ? "个人信息" :
                               tc.name === "query_grades" ? "成绩查询" :
                               tc.name === "query_schedule" ? "课表查询" :
                               tc.name === "query_exam_schedule" ? "考试安排" :
                               tc.name === "query_academic_progress" ? "学业进度" :
                               tc.name === "refresh_all_data" ? "刷新数据" :
                               tc.name}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* 来源引用 */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="mt-3 pt-2 border-t border-white/20 text-xs opacity-80">
                          <span className="font-medium">参考来源：</span>
                          {msg.sources.join(", ")}
                        </div>
                      )}
                    </div>
                    <span className="text-xs text-gray-400 mt-1 px-1">
                      {msg.timestamp}
                    </span>
                  </div>
                </div>
              ))}

              {/* 加载中指示器：仅在assistant消息尚未出现时显示 */}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* 输入框 */}
        <div className="bg-white/80 backdrop-blur-xl border-t border-gray-200/50 p-4">
          <div className="max-w-3xl mx-auto">
            <div className="mb-2 grid grid-cols-1 sm:grid-cols-3 gap-2">
              <select
                value={provider}
                onChange={(e) => {
                  const p = e.target.value;
                  setProvider(p);
                  const defaultModel = providers.find((x) => x.provider === p)?.default_model || "";
                  setModel(defaultModel);
                }}
                disabled={isLoading}
                className="h-9 rounded-lg border border-gray-300 bg-white px-2 text-sm disabled:opacity-60"
              >
                {providers.map((p) => (
                  <option key={p.provider} value={p.provider}>{p.provider}</option>
                ))}
              </select>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={isLoading}
                className="h-9 rounded-lg border border-gray-300 bg-white px-2 text-sm disabled:opacity-60"
              >
                {(providers.find((p) => p.provider === provider)?.models || []).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              <select
                value={reasoningMode}
                onChange={(e) => setReasoningMode(e.target.value)}
                disabled={isLoading}
                className="h-9 rounded-lg border border-gray-300 bg-white px-2 text-sm disabled:opacity-60"
              >
                <option value="standard">标准模式</option>
                <option value="thinking">推理模式</option>
                <option value="deep">深度推理</option>
              </select>
            </div>
            <label className="mb-2 inline-flex items-center gap-2 text-xs text-gray-600">
              <input type="checkbox" checked={showThinking} onChange={(e) => setShowThinking(e.target.checked)} />
              显示思考流
            </label>
            <div className="relative flex items-end gap-2 bg-white border border-gray-200 rounded-2xl shadow-lg shadow-gray-200/50 p-2 focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-400 transition">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={username ? "输入消息，按 Enter 发送..." : "请先输入学号"}
                disabled={!username || isLoading}
                rows={1}
                className="flex-1 px-3 py-2.5 max-h-32 resize-none bg-transparent focus:outline-none text-[15px] disabled:text-gray-400"
                style={{ minHeight: "44px" }}
              />
              <button
                onClick={sendMessage}
                disabled={!username || !input.trim() || isLoading}
                className="flex-shrink-0 p-2.5 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition shadow-lg shadow-blue-500/25"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
            <p className="text-center text-xs text-gray-400 mt-2">
              AI助手可能会有错误，请核实重要信息
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
