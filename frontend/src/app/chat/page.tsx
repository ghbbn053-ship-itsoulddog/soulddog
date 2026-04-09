"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, User, Bot, Loader2, Plus, Trash2, Menu, X, GraduationCap } from "lucide-react";

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
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
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [username, setUsername] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
          sources: m.meta?.sources || []
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
    setMessages(prev => [...prev, { id: Date.now(), role: "user", content: userMessage }]);
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
          sources: data.sources
        }]);
        setCurrentConversationId(data.conversation_id);
        fetchConversations();
      } else {
        setMessages(prev => [...prev, {
          id: Date.now() + 1,
          role: "assistant",
          content: "抱歉，服务暂时不可用，请稍后再试。"
        }]);
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: "assistant",
        content: "网络错误，请检查连接。"
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  // 新建对话
  const newConversation = () => {
    setCurrentConversationId(null);
    setMessages([]);
  };

  // 选择对话
  const selectConversation = (id: number) => {
    setCurrentConversationId(id);
    fetchHistory(id);
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

  return (
    <div className="flex h-screen bg-gray-50">
      {/* 侧边栏 */}
      <div className={`${sidebarOpen ? "w-64" : "w-0"} bg-white border-r transition-all duration-300 flex flex-col`}>
        <div className="p-4 border-b">
          <div className="flex items-center gap-2 mb-4">
            <GraduationCap className="w-6 h-6 text-blue-600" />
            <span className="font-bold text-lg">校园AI助手</span>
          </div>
          <button
            onClick={newConversation}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition"
          >
            <Plus className="w-4 h-4" />
            新建对话
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {conversations.map(conv => (
            <div
              key={conv.id}
              onClick={() => selectConversation(conv.id)}
              className={`group flex items-center justify-between p-3 rounded-lg cursor-pointer mb-1 ${
                currentConversationId === conv.id ? "bg-blue-50 border-blue-200" : "hover:bg-gray-100"
              }`}
            >
              <span className="truncate flex-1 text-sm">{conv.title}</span>
              <button
                onClick={(e) => deleteConversation(conv.id, e)}
                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 rounded transition"
              >
                <Trash2 className="w-4 h-4 text-red-500" />
              </button>
            </div>
          ))}
        </div>

        <div className="p-4 border-t">
          <input
            type="text"
            placeholder="输入学号"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onBlur={fetchConversations}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* 主聊天区 */}
      <div className="flex-1 flex flex-col">
        {/* 顶部栏 */}
        <div className="bg-white border-b px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 hover:bg-gray-100 rounded-lg"
            >
              {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <h1 className="font-semibold">
              {currentConversationId ? "当前对话" : "新对话"}
            </h1>
          </div>
        </div>

        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <Bot className="w-16 h-16 mb-4" />
              <p className="text-lg">我是你的校园AI助手</p>
              <p className="text-sm">可以问我关于成绩、课表、学分的问题</p>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                  msg.role === "user" ? "bg-blue-600" : "bg-green-600"
                }`}>
                  {msg.role === "user" ? <User className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-white" />}
                </div>
                <div className={`max-w-[70%] rounded-2xl px-4 py-2 ${
                  msg.role === "user" 
                    ? "bg-blue-600 text-white" 
                    : "bg-white border shadow-sm"
                }`}>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-2 pt-2 border-t text-xs opacity-70">
                      来源: {msg.sources.join(", ")}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          {isLoading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-green-600 flex items-center justify-center">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div className="bg-white border rounded-2xl px-4 py-2 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm text-gray-500">思考中...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入框 */}
        <div className="bg-white border-t p-4">
          <div className="max-w-4xl mx-auto flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder={username ? "输入消息..." : "请先输入学号"}
              disabled={!username || isLoading}
              className="flex-1 px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
            />
            <button
              onClick={sendMessage}
              disabled={!username || !input.trim() || isLoading}
              className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
