import { BookOpenCheck, Clock3, Database, MessageSquareText, Quote } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

type LearningMetrics = {
  today_minutes: number;
  week_minutes: number;
  total_prompts: number;
  today_prompts: number;
  assistant_replies: number;
  knowledge_documents: number;
  knowledge_chunks: number;
  documents_ready: number;
  documents_failed: number;
  knowledge_references: number;
  source_citations: number;
  total_tokens: number;
};

type LearningSignals = {
  knowledge_density?: number;
  document_failure_ratio?: number;
  education_freshness_days?: number | null;
};

export function LearningStatus({
  metrics,
  signals,
}: {
  metrics: LearningMetrics;
  signals?: LearningSignals | null;
}) {
  const cards = [
    {
      label: "今日学习",
      value: `${metrics.today_minutes} 分钟`,
      hint: `本周 ${metrics.week_minutes} 分钟`,
      icon: Clock3,
    },
    {
      label: "提问次数",
      value: String(metrics.total_prompts),
      hint: `今日 ${metrics.today_prompts} 次`,
      icon: MessageSquareText,
    },
    {
      label: "知识引用",
      value: String(metrics.knowledge_references),
      hint: `来源 ${metrics.source_citations} 条`,
      icon: Quote,
    },
    {
      label: "知识沉淀",
      value: `${metrics.knowledge_documents} / ${metrics.knowledge_chunks}`,
      hint: `${metrics.documents_ready} ready · ${metrics.documents_failed} failed`,
      icon: Database,
    },
  ];

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {cards.map((item) => (
          <Card key={item.label} className="bg-slate-50 shadow-none">
            <CardContent className="space-y-2 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                <item.icon className="h-3.5 w-3.5" />
                {item.label}
              </div>
              <div className="text-2xl font-semibold text-slate-950">{item.value}</div>
              <div className="text-xs text-slate-500">{item.hint}</div>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card className="shadow-none">
        <CardContent className="flex flex-wrap items-center gap-3 p-4 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <BookOpenCheck className="h-3.5 w-3.5" />
            知识密度 {signals?.knowledge_density ?? 0}
          </span>
          <span>失败占比 {Math.round((signals?.document_failure_ratio ?? 0) * 100)}%</span>
          <span>
            教务新鲜度 {signals?.education_freshness_days == null ? "未知" : `${signals.education_freshness_days} 天`}
          </span>
          <span>总 tokens 约 {metrics.total_tokens}</span>
        </CardContent>
      </Card>
    </div>
  );
}
