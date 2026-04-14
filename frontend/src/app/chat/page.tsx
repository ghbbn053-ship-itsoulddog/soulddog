"use client";

import React, { useState, useRef, useEffect } from "react";
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
  LogOut
} from "lucide-react";

interface ToolCall {
  name: string;
}

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  tool_calls?: ToolCall[];
  timestamp?: string;
}

interface Conversation {
  id: number;
  title: string;
  created_at: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [username, setUsername] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const API_BASE = "";  // 使用相对路径，通过 Nginx 反向代理

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 获取对话列表
  const fetchConversations = async () => {
    if (!username) return;
    try {
      const res = await fetch(`${API_BASE}/api/chat/conversations/${username}`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch (error) {
      console.error("获取对话列表失败:", error);
    }
  };

  // 获取对话历史
  const fetchHistory = async (conversationId: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/history/${conversationId}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages.map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          sources: m.meta?.sources || [],
          timestamp: new Date(m.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
        })));
      }
    } catch (error) {
      console.error("获取历史失败:", error);
    }
  };

  // 发送消息
  const sendMessage = async () => {
    if (!input.trim() || !username || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages(prev => [...prev, { 
      id: Date.now(), 
      role: "user", 
      content: userMessage,
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }]);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          message: userMessage,
          conversation_id: currentConversationId
        })
      });

      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, {
          id: Date.now() + 1,
          role: "assistant",
          content: data.message,
          sources: data.sources,
          tool_calls: data.tool_calls,
          timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
        }]);
        setCurrentConversationId(data.conversation_id);
        fetchConversations();
      } else {
        setMessages(prev => [...prev, {
          id: Date.now() + 1,
          role: "assistant",
          content: "抱歉，服务暂时不可用，请稍后再试。",
          timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
        }]);
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: "assistant",
        content: "网络错误，请检查连接。",
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      }]);
    } finally {
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
    localStorage.removeItem("current_conversation_id");
    setSidebarOpen(false);
  };

  // 选择对话
  const selectConversation = (id: number) => {
    setCurrentConversationId(id);
    fetchHistory(id);
    setSidebarOpen(false);
  };

  // 删除对话
  const deleteConversation = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`${API_BASE}/api/chat/conversations/${id}`, { method: "DELETE" });
      if (currentConversationId === id) {
        newConversation();
      }
      fetchConversations();
    } catch (error) {
      console.error("删除失败:", error);
    }
  };

  // 页面加载时从 localStorage 读取用户名和当前会话
  useEffect(() => {
    const savedUsername = localStorage.getItem("username");
    if (savedUsername) {
      setUsername(savedUsername);
      
      // 恢复当前会话ID
      const savedConversationId = localStorage.getItem("current_conversation_id");
      if (savedConversationId) {
        const convId = parseInt(savedConversationId);
        if (!isNaN(convId)) {
          setCurrentConversationId(convId);
          // 延迟加载历史，等待username设置完成
          setTimeout(() => fetchHistory(convId), 100);
        }
      }
    } else {
      // 未登录，跳转到登录页
      window.location.href = "/login";
    }
  }, []);

  // 当 username 变化时加载对话列表
  useEffect(() => {
    if (username) {
      fetchConversations();
    }
  }, [username]);
  
  // 当 currentConversationId 变化时，保存到 localStorage
  useEffect(() => {
    if (currentConversationId !== null) {
      localStorage.setItem("current_conversation_id", currentConversationId.toString());
    } else {
      localStorage.removeItem("current_conversation_id");
    }
  }, [currentConversationId]);

  // 退出登录
  const handleLogout = () => {
    localStorage.removeItem("username");
    localStorage.removeItem("current_conversation_id");
    // 清除cookie
    document.cookie = 'session_username=; path=/; max-age=0';
    window.location.href = "/login";
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
        ${sidebarOpen ? "translate-x-0 w-72" : "-translate-x-full lg:translate-x-0 lg:w-0 lg:overflow-hidden"}
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
        </div>

        {/* 对话列表 */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {conversations.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p className="text-sm">暂无对话记录</p>
            </div>
          ) : (
            conversations.map(conv => (
              <div
                key={conv.id}
                onClick={() => selectConversation(conv.id)}
                className={`
                  group flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all
                  ${currentConversationId === conv.id 
                    ? "bg-blue-50 border border-blue-200 shadow-sm" 
                    : "hover:bg-gray-50 border border-transparent"
                  }
                `}
              >
                <MessageSquare className={`w-4 h-4 flex-shrink-0 ${
                  currentConversationId === conv.id ? "text-blue-600" : "text-gray-400"
                }`} />
                <span className="truncate flex-1 text-sm font-medium text-gray-700">
                  {conv.title}
                </span>
                <button
                  onClick={(e) => deleteConversation(conv.id, e)}
                  className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-100 rounded-lg transition"
                >
                  <Trash2 className="w-3.5 h-3.5 text-red-500" />
                </button>
              </div>
            ))
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
          {messages.length === 0 ? (
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
              {messages.map((msg, idx) => (
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
                      <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                      
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

              {/* 加载中 */}
              {isLoading && (
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center shadow-md">
                    <Bot className="w-4 h-4 text-white" />
                  </div>
                  <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm flex items-center gap-3">
                    <Loader2 className="w-4 h-4 animate-spin text-purple-500" />
                    <span className="text-sm text-gray-500">AI正在思考...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* 输入框 */}
        <div className="bg-white/80 backdrop-blur-xl border-t border-gray-200/50 p-4">
          <div className="max-w-3xl mx-auto">
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
