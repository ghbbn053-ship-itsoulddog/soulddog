"use client";

import type { ReactNode } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function PageLoading({
  label = "加载中...",
  fullScreen = false,
}: {
  label?: string;
  fullScreen?: boolean;
}) {
  if (fullScreen) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,#eaf2ff,transparent_42%),linear-gradient(180deg,#f4f7fb_0%,#eef3f8_100%)]">
        <div className="flex flex-col items-center gap-4 text-sm text-slate-500">
          <div className="flex h-14 w-14 items-center justify-center rounded-3xl border border-slate-200 bg-white shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
          </div>
          {label}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-sm text-slate-500">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        {label}
      </div>
    </div>
  );
}

export function PageFallback({
  label,
}: {
  label: string;
}) {
  return (
    <div className="min-h-screen bg-slate-50 px-4 py-6 md:px-6 md:py-8">
      <div className="mx-auto max-w-6xl">
        <Card className="border-slate-200 shadow-none">
          <CardContent className="flex min-h-[240px] items-center justify-center p-6 text-sm text-slate-500">
            {label}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export function InlineStatusMessage({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "warning" | "danger" | "success";
  className?: string;
}) {
  return (
    <Card
      className={cn(
        "shadow-none",
        tone === "neutral" && "border-slate-200 bg-slate-50",
        tone === "warning" && "border-amber-200 bg-amber-50",
        tone === "danger" && "border-rose-200 bg-rose-50",
        tone === "success" && "border-emerald-200 bg-emerald-50",
        className
      )}
    >
      <CardContent className="flex items-start gap-3 p-4 text-sm text-slate-700">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
        <div className="min-w-0">{children}</div>
      </CardContent>
    </Card>
  );
}
