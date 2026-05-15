import type { ReactNode } from "react";
import {
  Blocks,
  Bot,
  CalendarDays,
  Database,
  GraduationCap,
  LibraryBig,
  LayoutGrid,
  MessageSquare,
  Network,
  Settings,
  Wrench,
  MonitorPlay,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type { WorkbenchNavItem } from "@/components/workspace/workbench-shell";

export function createPlatformNav(active: string): WorkbenchNavItem[] {
  return [
    { label: "概览", href: "/", active: active === "home", icon: <LayoutGrid className="h-4 w-4" /> },
    { label: "课表", href: "/schedule", active: active === "schedule", icon: <CalendarDays className="h-4 w-4" /> },
    { label: "快速会话", href: "/chat", active: active === "chat", icon: <MessageSquare className="h-4 w-4" /> },
    { label: "工作区", href: "/workspace", active: active === "workspace", icon: <Database className="h-4 w-4" /> },
    { label: "知识库", href: "/knowledge", active: active === "knowledge", icon: <LibraryBig className="h-4 w-4" /> },
    { label: "学习通训练", href: "/chaoxing", active: active === "chaoxing", icon: <MonitorPlay className="h-4 w-4" /> },
    { label: "组合编排", href: "/composition", active: active === "composition", icon: <Network className="h-4 w-4" />, accent: "muted" },
    { label: "Skill 管理", href: "/skills", active: active === "skills", icon: <Blocks className="h-4 w-4" />, accent: "muted" },
    { label: "MCP 管理", href: "/mcp", active: active === "mcp", icon: <Wrench className="h-4 w-4" />, accent: "muted" },
    { label: "模型设置", href: "/settings/models", active: active === "models", icon: <Settings className="h-4 w-4" />, accent: "muted" },
  ];
}

export function PlatformSidebarHeader() {
  return (
    <div className="rounded-[1.35rem] border border-slate-200/90 bg-[linear-gradient(135deg,rgba(219,234,254,0.9),rgba(255,255,255,0.98)_48%,rgba(228,231,255,0.88))] p-4 shadow-[0_14px_36px_rgba(15,23,42,0.05)]">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#1f6feb,#5a67d8)] text-white shadow-[0_12px_24px_rgba(31,111,235,0.24)]">
          <GraduationCap className="h-6 w-6" />
        </div>
        <div className="min-w-0 space-y-1">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Campus AI</div>
          <div className="text-base font-semibold tracking-[-0.02em] text-slate-950">AI 学习工作台</div>
        </div>
      </div>
      <div className="mt-4 rounded-2xl border border-white/80 bg-white/78 px-3.5 py-3 text-sm leading-6 text-slate-600">
        工作区、知识库、MCP 和对话入口保持同一套学习操作面，减少跳转时的割裂感。
      </div>
    </div>
  );
}

export function PlatformSidebarFooter({
  username,
  detail = "当前登录账号",
  extra,
}: {
  username?: string;
  detail?: string;
  extra?: ReactNode;
}) {
  return (
    <div className="space-y-3">
      {extra}
      <Card className="overflow-hidden border-slate-200/90 bg-[linear-gradient(180deg,rgba(248,250,252,0.98),rgba(238,242,255,0.96))] shadow-[0_14px_34px_rgba(15,23,42,0.04)]">
        <CardContent className="space-y-4 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-[0_10px_20px_rgba(15,23,42,0.12)]">
              <Bot className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Session</div>
              <div className="truncate text-sm font-semibold text-slate-950">{username || "未登录"}</div>
            </div>
          </div>
          <div className="rounded-2xl border border-white/70 bg-white/72 px-3.5 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Current Context</div>
            <div className="mt-1 text-sm leading-6 text-slate-700">{detail}</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
