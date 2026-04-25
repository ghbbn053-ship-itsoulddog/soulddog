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
    { label: "Skill 管理", href: "/skills", active: active === "skills", icon: <Blocks className="h-4 w-4" /> },
    { label: "MCP 管理", href: "/mcp", active: active === "mcp", icon: <Wrench className="h-4 w-4" /> },
    { label: "组合编排", href: "/composition", active: active === "composition", icon: <Network className="h-4 w-4" /> },
    { label: "模型设置", href: "/settings/models", active: active === "models", icon: <Settings className="h-4 w-4" /> },
  ];
}

export function PlatformSidebarHeader() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-sm">
        <GraduationCap className="h-6 w-6" />
      </div>
      <div className="space-y-1">
        <div className="text-base font-semibold text-slate-950">AI 学习工作台</div>
        <div className="text-xs text-slate-500">Workspace / Skill / MCP / Agent</div>
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
      <Card className="border-transparent bg-[linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] shadow-none">
        <CardContent className="flex items-center gap-3 p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-900 text-white">
            <Bot className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-slate-900">{username || "未登录"}</div>
            <div className="text-xs text-slate-500">{detail}</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
