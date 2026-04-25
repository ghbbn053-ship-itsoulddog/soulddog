import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type SuggestionTone = "normal" | "warning" | "urgent";

export type WorkspaceSuggestionItem = {
  id: string;
  title: string;
  content: string;
  reason?: string;
  tone?: SuggestionTone;
};

const toneClassMap: Record<SuggestionTone, string> = {
  normal: "border-slate-200 bg-slate-50",
  warning: "border-amber-200 bg-amber-50",
  urgent: "border-rose-200 bg-rose-50",
};

export function AISuggestion({
  item,
  onAccept,
  onDismiss,
}: {
  item: WorkspaceSuggestionItem;
  onAccept: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  const tone = item.tone || "normal";

  return (
    <Card className={`shadow-none ${toneClassMap[tone]}`}>
      <CardContent className="space-y-3 p-4 text-sm text-slate-700">
        <div className="flex items-center gap-2 text-slate-900">
          <Sparkles className="h-4 w-4 text-[hsl(var(--primary))]" />
          <span className="font-medium">{item.title}</span>
        </div>
        <div className="leading-6">{item.content}</div>
        {item.reason ? <div className="text-xs leading-5 text-slate-500">原因：{item.reason}</div> : null}
        <div className="flex gap-2">
          <Button size="sm" onClick={() => onAccept(item.id)}>
            接受建议
          </Button>
          <Button size="sm" variant="outline" onClick={() => onDismiss(item.id)}>
            忽略
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
