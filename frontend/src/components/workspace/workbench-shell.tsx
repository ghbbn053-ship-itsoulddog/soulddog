import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
  return (
    <div className="min-h-screen px-4 py-6 md:px-6 md:py-8">
      <div className="mx-auto max-w-[1560px]">
        <div className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
          <aside className="xl:sticky xl:top-6 xl:h-[calc(100vh-3rem)]">
            <Card className="h-full overflow-hidden border-white/70 bg-white/88 shadow-[0_12px_40px_rgba(15,23,42,0.08)] backdrop-blur">
              <CardHeader className="gap-4 border-b border-[hsl(var(--border))] bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(247,250,252,0.92))] pb-5">
                {sidebarHeader}
                <div className="space-y-1">
                  <CardTitle className="text-base">{sidebarTitle}</CardTitle>
                  {sidebarDescription ? <CardDescription>{sidebarDescription}</CardDescription> : null}
                </div>
              </CardHeader>
              <CardContent className="flex h-[calc(100%-122px)] flex-col gap-5 p-4">
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
              <Card className="overflow-hidden border-white/70 bg-white/82 shadow-[0_12px_40px_rgba(15,23,42,0.06)] backdrop-blur">
                <CardHeader className="gap-4 md:flex-row md:items-end md:justify-between">
                  <div className="space-y-3">
                    {badge ? <div>{badge}</div> : null}
                    <div className="space-y-1.5">
                      <CardTitle className="text-3xl font-semibold tracking-[-0.03em] text-slate-950">{title}</CardTitle>
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
        "flex w-full items-center justify-between rounded-xl border px-3 py-3 text-left transition-colors",
        item.active
          ? "border-[hsl(var(--primary))] bg-[hsla(var(--primary),0.08)] text-slate-950"
          : "border-transparent bg-transparent text-slate-600 hover:border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]",
        item.accent === "muted" && !item.active ? "text-slate-500" : ""
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        {item.icon ? <span className="text-slate-400">{item.icon}</span> : null}
        <span className="truncate text-sm font-medium">{item.label}</span>
      </div>
      {item.href ? <ChevronRight className="h-4 w-4 text-slate-400" /> : null}
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
      className="gap-1.5 rounded-full border-slate-200 bg-white/80 px-3 py-1 text-[11px] font-semibold tracking-[0.18em] text-slate-500"
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
    <Card className={cn("border-white/70 bg-white/90 shadow-[0_10px_32px_rgba(15,23,42,0.05)]", className)}>
      <CardHeader className="gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1">
          <CardTitle className="text-base">{title}</CardTitle>
          {description ? <CardDescription>{description}</CardDescription> : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
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
    <Card className="border-transparent bg-[linear-gradient(180deg,#f8fafc_0%,#f1f5f9_100%)] shadow-none">
      <CardContent className="p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
        <div className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-slate-950">{value}</div>
        {hint ? <div className="mt-1 text-xs text-slate-500">{hint}</div> : null}
      </CardContent>
    </Card>
  );
}

export function WorkbenchEmpty({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 px-5 py-8 text-center">
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
