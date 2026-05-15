"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { ChevronRight, Menu, SearchX } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export type WorkbenchNavItem = {
  label: string;
  href?: string;
  icon?: ReactNode;
  active?: boolean;
  accent?: "default" | "muted";
  onClick?: () => void;
};

type WorkbenchShellProps = {
  badge?: ReactNode;
  title: string;
  description?: string;
  sidebarTitle: string;
  sidebarDescription?: string;
  sidebarHeader?: ReactNode;
  navItems?: WorkbenchNavItem[];
  footer?: ReactNode;
  topActions?: ReactNode;
  children: ReactNode;
};

export function WorkbenchShell({
  badge,
  title,
  description,
  sidebarTitle,
  sidebarDescription,
  sidebarHeader,
  navItems = [],
  footer,
  topActions,
  children,
}: WorkbenchShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(219,234,254,0.64),transparent_22%),radial-gradient(circle_at_bottom_right,rgba(226,232,255,0.62),transparent_18%),linear-gradient(180deg,#f4f6f8_0%,#eef2f6_100%)] px-3 py-4 md:px-5 md:py-6">
      <div className="mx-auto max-w-[1520px]">
        <div className="mb-3 xl:hidden">
          <div className="flex items-center justify-between gap-3 rounded-[1.25rem] border border-slate-200/90 bg-white/92 px-3.5 py-3 shadow-[0_12px_28px_rgba(15,23,42,0.04)]">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-slate-950">{title}</div>
              {description ? <div className="truncate text-xs text-slate-500">{description}</div> : null}
            </div>
            <Dialog open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm" className="shrink-0">
                  <Menu className="h-4 w-4" />
                  导航
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-[92vw] border-slate-200 bg-white p-0 sm:max-w-md">
                <DialogHeader className="border-b border-slate-200 px-5 pb-4 pt-5">
                  <DialogTitle className="text-base font-semibold text-slate-950">{sidebarTitle}</DialogTitle>
                  {sidebarDescription ? (
                    <div className="text-sm leading-6 text-slate-500">{sidebarDescription}</div>
                  ) : null}
                </DialogHeader>
                <div className="space-y-4 px-5 pb-5 pt-4">
                  {sidebarHeader}
                  <div className="space-y-2">
                    {navItems.map((item) => (
                      <div key={`${item.label}-${item.href || "action"} `} onClick={() => setMobileNavOpen(false)}>
                        <WorkbenchNavButton item={item} />
                      </div>
                    ))}
                  </div>
                  {footer}
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[228px_minmax(0,1fr)] 2xl:grid-cols-[244px_minmax(0,1fr)]">
          <aside className="hidden xl:block xl:sticky xl:top-5 xl:h-[calc(100vh-2.5rem)]">
            <Card className="h-full overflow-hidden border-slate-200/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(247,250,252,0.94))] shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur">
              <CardHeader className="gap-4 border-b border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.84),rgba(241,245,249,0.96))] px-4 pb-4 pt-4">
                {sidebarHeader}
                <div className="space-y-1">
                  <CardTitle className="text-base font-semibold tracking-[-0.02em] text-slate-950">{sidebarTitle}</CardTitle>
                  {sidebarDescription ? (
                    <CardDescription className="text-sm leading-6 text-slate-500">{sidebarDescription}</CardDescription>
                  ) : null}
                </div>
              </CardHeader>
              <CardContent className="flex h-[calc(100%-114px)] flex-col gap-4 p-3.5">
                <div className="space-y-2">
                  {navItems.map((item) => (
                    <WorkbenchNavButton key={`${item.label}-${item.href || "action"}`} item={item} />
                  ))}
                </div>
                <div className="mt-auto">{footer}</div>
              </CardContent>
            </Card>
          </aside>

          <main className="min-w-0">
            <div className="space-y-4">
              <Card className="hidden overflow-hidden border-slate-200/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(248,250,252,0.96))] shadow-[0_18px_52px_rgba(15,23,42,0.05)] backdrop-blur xl:block">
                <CardHeader className="gap-4 px-5 py-5 md:flex-row md:items-end md:justify-between">
                  <div className="space-y-3">
                    {badge ? <div>{badge}</div> : null}
                    <div className="space-y-1.5">
                      <CardTitle className="text-[2rem] font-semibold tracking-[-0.04em] text-slate-950">{title}</CardTitle>
                      {description ? (
                        <CardDescription className="max-w-3xl text-sm leading-6 text-slate-600">
                          {description}
                        </CardDescription>
                      ) : null}
                    </div>
                  </div>
                  {topActions ? <div className="flex flex-wrap gap-2">{topActions}</div> : null}
                </CardHeader>
              </Card>
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

function WorkbenchNavButton({ item }: { item: WorkbenchNavItem }) {
  const content = (
    <div
      className={cn(
        "flex w-full items-center justify-between rounded-[1rem] border px-3 py-2.5 text-left transition-all",
        item.active
          ? "border-blue-200 bg-[linear-gradient(135deg,rgba(219,234,254,0.9),rgba(255,255,255,0.95))] text-slate-950 shadow-[0_10px_24px_rgba(31,111,235,0.08)]"
          : "border-transparent bg-transparent text-slate-600 hover:border-slate-200 hover:bg-white/90 hover:shadow-[0_10px_24px_rgba(15,23,42,0.04)]",
        item.accent === "muted" && !item.active ? "text-slate-500" : ""
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        {item.icon ? <span className={cn("text-slate-400", item.active ? "text-blue-600" : "")}>{item.icon}</span> : null}
        <span className="truncate text-sm font-medium">{item.label}</span>
      </div>
      {item.href ? <ChevronRight className={cn("h-4 w-4 text-slate-400", item.active ? "text-blue-500" : "")} /> : null}
    </div>
  );

  if (item.href) {
    return (
      <Link href={item.href} className="block">
        {content}
      </Link>
    );
  }

  return (
    <button type="button" onClick={item.onClick} className="block w-full">
      {content}
    </button>
  );
}

export function WorkbenchBadge({ children }: { children: ReactNode }) {
  return (
    <Badge
      variant="outline"
      className="gap-1.5 rounded-full border-slate-200 bg-white/86 px-3 py-1 text-[11px] font-semibold tracking-[0.18em] text-slate-500 shadow-[0_8px_20px_rgba(15,23,42,0.03)]"
    >
      {children}
    </Badge>
  );
}

export function WorkbenchSection({
  title,
  description,
  actions,
  children,
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("border-slate-200/90 bg-white/94 shadow-[0_18px_48px_rgba(15,23,42,0.05)]", className)}>
      <CardHeader className="gap-3 px-5 py-4 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1">
          <CardTitle className="text-base font-semibold tracking-[-0.02em] text-slate-950">{title}</CardTitle>
          {description ? <CardDescription className="leading-6 text-slate-500">{description}</CardDescription> : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </CardHeader>
      <CardContent className="px-5 pb-5 pt-0">{children}</CardContent>
    </Card>
  );
}

export function WorkbenchStatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
}) {
  return (
    <Card className="border-slate-200/70 bg-[linear-gradient(180deg,#ffffff_0%,#f7fafc_100%)] shadow-[0_12px_30px_rgba(15,23,42,0.03)]">
      <CardContent className="p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
        <div className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-950 md:text-3xl">{value}</div>
        {hint ? <div className="mt-1 text-xs text-slate-500">{hint}</div> : null}
      </CardContent>
    </Card>
  );
}

export function WorkbenchEmpty({
  title,
  description,
  action,
  tone = "neutral",
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  tone?: "neutral" | "hint" | "warning";
}) {
  const iconTone =
    tone === "warning"
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : tone === "hint"
        ? "border-blue-200 bg-blue-50 text-blue-700"
        : "border-slate-200 bg-white text-slate-400";

  return (
    <div className="rounded-[1.5rem] border border-dashed border-slate-200 bg-slate-50/85 px-5 py-8 text-center">
      <div className="mb-3 flex justify-center">
        <div className={cn("flex h-11 w-11 items-center justify-center rounded-2xl border", iconTone)}>
          <SearchX className="h-5 w-5" />
        </div>
      </div>
      <div className="text-sm font-medium text-slate-900">{title}</div>
      {description ? <div className="mt-1 text-sm leading-6 text-slate-500">{description}</div> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function WorkbenchQuickAction({
  href,
  label,
  variant = "outline",
}: {
  href: string;
  label: string;
  variant?: "default" | "outline" | "secondary" | "ghost";
}) {
  return (
    <Link href={href}>
      <Button variant={variant}>{label}</Button>
    </Link>
  );
}
