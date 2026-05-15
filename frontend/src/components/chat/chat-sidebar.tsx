"use client";

import type React from "react";
import {
  GraduationCap,
  History,
  LogOut,
  MessageSquare,
  PanelLeft,
  Plus,
  Save,
  Trash2,
  User,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

type ConversationItem = {
  id: number;
  title: string;
  created_at: string;
};

type ChatSidebarProps = {
  sidebarOpen: boolean;
  conversations: ConversationItem[];
  currentConversationId: number | null;
  username: string;
  onCloseSidebar: () => void;
  onNewConversation: () => void;
  onOpenSaveDialog: () => void;
  onSelectConversation: (id: number) => void;
  onDeleteConversation: (id: number, event: React.MouseEvent<HTMLButtonElement>) => void;
  onLogout: () => void;
  canSave: boolean;
};

export function ChatSidebar({
  sidebarOpen,
  conversations,
  currentConversationId,
  username,
  onCloseSidebar,
  onNewConversation,
  onOpenSaveDialog,
  onSelectConversation,
  onDeleteConversation,
  onLogout,
  canSave,
}: ChatSidebarProps) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-50 flex w-[264px] flex-col border-r border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(247,250,252,0.98))] backdrop-blur-xl transition-transform duration-200 lg:static lg:translate-x-0",
        sidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}
    >
      <div className="p-4">
        <div className="mb-4 rounded-[1.2rem] border border-slate-200/90 bg-[linear-gradient(135deg,rgba(219,234,254,0.88),rgba(255,255,255,0.98)_48%,rgba(228,231,255,0.86))] p-3.5 shadow-[0_12px_30px_rgba(15,23,42,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#1f6feb,#5a67d8)] text-white shadow-[0_12px_24px_rgba(31,111,235,0.24)]">
                <GraduationCap className="h-4.5 w-4.5" />
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Campus AI</div>
                <div className="text-sm font-semibold text-slate-950">快速会话</div>
              </div>
            </div>
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={onCloseSidebar}>
              <PanelLeft className="h-4 w-4" />
            </Button>
          </div>
          <div className="mt-3 rounded-2xl border border-white/80 bg-white/78 px-3 py-2.5 text-sm leading-6 text-slate-600">
            对话、保存、历史三件事留在这里，其余配置回平台页处理。
          </div>
        </div>

        <div className="grid gap-2">
          <Button className="w-full justify-start bg-blue-600 shadow-[0_12px_24px_rgba(31,111,235,0.18)] hover:bg-blue-700" onClick={onNewConversation}>
            <Plus className="h-4 w-4" />
            新建对话
          </Button>
          <Button
            variant="outline"
            className="w-full justify-start border-slate-300 bg-white/90 text-slate-700 hover:bg-slate-50"
            onClick={onOpenSaveDialog}
            disabled={!canSave}
          >
            <Save className="h-4 w-4" />
            保存到工作区
          </Button>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="col-span-2 rounded-[1.1rem] border border-dashed border-slate-200 bg-slate-50/92 px-3 py-2.5 text-xs leading-6 text-slate-500">
            这里只做快问快答和保存沉淀。
          </div>
        </div>
      </div>

      <Separator />

      <div className="flex-1 px-3.5 py-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
          <History className="h-4 w-4 text-slate-500" />
          对话历史
        </div>
        <ScrollArea className="h-[calc(100vh-22.5rem)] pr-2 lg:h-[calc(100vh-19.5rem)]">
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
                <div
                  key={conv.id}
                  className={cn(
                    "group flex items-start gap-3 rounded-[1rem] border px-3 py-3 transition-all",
                    currentConversationId === conv.id
                      ? "border-blue-200 bg-[linear-gradient(135deg,rgba(219,234,254,0.9),rgba(255,255,255,0.95))] shadow-[0_10px_24px_rgba(31,111,235,0.08)]"
                      : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 hover:shadow-[0_10px_24px_rgba(15,23,42,0.04)]"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                    <button type="button" onClick={() => onSelectConversation(conv.id)} className="min-w-0 flex-1 text-left">
                      <div className="truncate text-sm font-medium text-slate-900">{conv.title}</div>
                      <div className="mt-1 text-xs text-slate-500">{new Date(conv.created_at).toLocaleString("zh-CN")}</div>
                    </button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100"
                      onClick={(event) => onDeleteConversation(conv.id, event)}
                    >
                      <Trash2 className="h-4 w-4 text-slate-500" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </div>

      <div className="border-t border-slate-200 p-3.5">
        <Card className="overflow-hidden border-slate-200/90 bg-[linear-gradient(180deg,rgba(248,250,252,0.98),rgba(238,242,255,0.96))] shadow-[0_14px_34px_rgba(15,23,42,0.04)]">
          <CardContent className="flex items-center gap-3 p-3.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.12)]">
              <User className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-slate-900">{username || "未登录"}</div>
              <div className="text-xs text-slate-500">学号登录</div>
            </div>
            <Button variant="ghost" size="icon" onClick={onLogout}>
              <LogOut className="h-4 w-4 text-slate-500" />
            </Button>
          </CardContent>
        </Card>
      </div>
    </aside>
  );
}
