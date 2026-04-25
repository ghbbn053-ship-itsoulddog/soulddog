import { FileStack, Layers3, ShieldCheck, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type KnowledgeVisualizationDocument = {
  id: number;
  title: string;
  docType: string;
  status: string;
  tokenEstimate: number;
  authorityLevel: string;
  summary?: string;
};

function bucketBy<T extends string>(items: KnowledgeVisualizationDocument[], pick: (item: KnowledgeVisualizationDocument) => T) {
  return items.reduce<Record<string, number>>((acc, item) => {
    const key = pick(item) || "unknown";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function toneForAuthority(authority: string) {
  if (authority === "system") return "warning" as const;
  if (authority === "school") return "secondary" as const;
  return "outline" as const;
}

function toneForStatus(status: string) {
  if (status === "ready") return "success" as const;
  if (status === "failed") return "destructive" as const;
  return "warning" as const;
}

export function KnowledgeVisualization({
  documents,
  relationCount,
}: {
  documents: KnowledgeVisualizationDocument[];
  relationCount: number;
}) {
  const docTypeBuckets = bucketBy(documents, (item) => item.docType);
  const authorityBuckets = bucketBy(documents, (item) => item.authorityLevel);
  const statusBuckets = bucketBy(documents, (item) => item.status);
  const topHeavyDocs = [...documents].sort((a, b) => b.tokenEstimate - a.tokenEstimate).slice(0, 6);
  const maxBucket = Math.max(1, ...Object.values(docTypeBuckets), ...Object.values(authorityBuckets), ...Object.values(statusBuckets));

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard label="文档总量" value={documents.length} icon={<FileStack className="h-4 w-4" />} />
        <MetricCard label="知识关系" value={relationCount} icon={<Layers3 className="h-4 w-4" />} />
        <MetricCard label="高权威文档" value={(authorityBuckets.system || 0) + (authorityBuckets.school || 0)} icon={<ShieldCheck className="h-4 w-4" />} />
        <MetricCard label="已就绪文档" value={statusBuckets.ready || 0} icon={<Sparkles className="h-4 w-4" />} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card className="shadow-none">
          <CardContent className="space-y-4 p-4">
            <div>
              <div className="text-sm font-medium text-slate-900">知识库分布视图</div>
              <div className="mt-1 text-xs leading-5 text-slate-500">
                用文档类型、状态和权威级别来观察知识库结构，先解决“看得见知识库”，再做复杂图谱。
              </div>
            </div>

            <BucketSection title="按文档类型" buckets={docTypeBuckets} maxBucket={maxBucket} palette="blue" />
            <BucketSection title="按权威级别" buckets={authorityBuckets} maxBucket={maxBucket} palette="amber" />
            <BucketSection title="按处理状态" buckets={statusBuckets} maxBucket={maxBucket} palette="emerald" />
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardContent className="space-y-4 p-4">
            <div>
              <div className="text-sm font-medium text-slate-900">高价值知识块</div>
              <div className="mt-1 text-xs leading-5 text-slate-500">
                这里优先展示 token 体量较大的文档，用来快速识别知识库重心。
              </div>
            </div>

            <div className="space-y-3">
              {topHeavyDocs.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                  暂无文档，知识库可视化会在文档入库后自动出现。
                </div>
              ) : (
                topHeavyDocs.map((doc) => (
                  <div key={doc.id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-slate-900">{doc.title}</div>
                        <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{doc.summary || "无摘要"}</div>
                      </div>
                      <div className="text-right text-xs text-slate-500">
                        <div>tokens≈{doc.tokenEstimate}</div>
                        <div className="mt-1">{doc.docType}</div>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge variant={toneForAuthority(doc.authorityLevel)}>{doc.authorityLevel}</Badge>
                      <Badge variant={toneForStatus(doc.status)}>{doc.status}</Badge>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MetricCard({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
  return (
    <Card className="border-transparent bg-[linear-gradient(180deg,#f8fafc_0%,#f1f5f9_100%)] shadow-none">
      <CardContent className="p-4">
        <div className="flex items-center justify-between gap-3 text-slate-500">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em]">{label}</div>
          <div>{icon}</div>
        </div>
        <div className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-slate-950">{value}</div>
      </CardContent>
    </Card>
  );
}

function BucketSection({
  title,
  buckets,
  maxBucket,
  palette,
}: {
  title: string;
  buckets: Record<string, number>;
  maxBucket: number;
  palette: "blue" | "amber" | "emerald";
}) {
  const paletteClass = {
    blue: "bg-blue-500/80",
    amber: "bg-amber-500/80",
    emerald: "bg-emerald-500/80",
  }[palette];

  const entries = Object.entries(buckets).sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-3">
      <div className="text-sm font-medium text-slate-900">{title}</div>
      {entries.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-6 text-center text-xs text-slate-500">
          暂无数据
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map(([key, count]) => (
            <div key={`${title}-${key}`} className="space-y-1">
              <div className="flex items-center justify-between gap-3 text-xs text-slate-600">
                <span className="truncate">{key}</span>
                <span>{count}</span>
              </div>
              <div className="h-2 rounded-full bg-slate-100">
                <div
                  className={cn("h-2 rounded-full transition-all", paletteClass)}
                  style={{ width: `${Math.max(10, (count / maxBucket) * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
