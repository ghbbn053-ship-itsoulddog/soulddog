"use client";

import { Wrench } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type ToolCall = {
  name: string;
};

export type ToolTrace = {
  skill: string;
  tool: string;
  params?: Record<string, unknown>;
  status: "success" | "failed" | "empty";
  error?: string;
};

export type SkillMatch = {
  name: string;
  mode?: string;
  source_type?: string;
  compatibility_level?: string;
  capabilities?: string[];
  always_on?: boolean;
  matched_triggers?: string[];
  has_tools?: boolean;
  tools?: string[];
};

export type MessageHighlight = {
  source: string;
  title: string;
  snippet: string;
  document_id?: number;
  chunk_index?: number;
  score?: number;
};

export type BlindSpotItem = {
  course_name: string;
  unresolved: number;
  dominant_type: string;
  dominant_type_count?: number;
  top_point?: string;
  top_point_count?: number;
};

export type ParsedKnowledgeSource = {
  raw: string;
  workspaceId: number | null;
  title: string;
  docId: number | null;
  chunkIndex: number | null;
};

export function ChatToolCalls({
  toolCalls,
  toolDisplayName,
}: {
  toolCalls: ToolCall[];
  toolDisplayName: (name: string) => string;
}) {
  if (!toolCalls.length) return null;

  return (
    <div className="flex flex-wrap gap-2 border-t border-[hsl(var(--border))] pt-3">
      {toolCalls.map((tc, index) => (
        <Badge key={`${tc.name}-${index}`} variant="secondary" className="gap-1.5">
          <Wrench className="h-3 w-3" />
          {toolDisplayName(tc.name)}
        </Badge>
      ))}
    </div>
  );
}

export function ChatToolTrace({ traces }: { traces: ToolTrace[] }) {
  if (!traces.length) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/92 p-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Tool Trace</div>
      <div className="space-y-2">
        {traces.map((trace, index) => (
          <div key={`${trace.tool}-${index}`} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{trace.skill}</span>
              <span className="text-slate-400">→</span>
              <span>{trace.tool}</span>
              <Badge variant={trace.status === "success" ? "success" : trace.status === "failed" ? "destructive" : "warning"}>
                {trace.status}
              </Badge>
            </div>
            {trace.params && Object.keys(trace.params).length > 0 ? <div className="mt-1 text-slate-500">params: {JSON.stringify(trace.params)}</div> : null}
            {trace.error ? <div className="mt-1 text-rose-600">{trace.error}</div> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChatSkillMatches({ matches }: { matches: SkillMatch[] }) {
  if (!matches.length) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/92 p-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Matched Skills</div>
      <div className="space-y-2">
        {matches.map((skill, index) => (
          <div key={`${skill.name}-${index}`} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{skill.name}</span>
              <Badge variant="outline">{skill.mode || "rule"}</Badge>
              <Badge variant="secondary">{skill.compatibility_level || "direct"}</Badge>
              {skill.source_type ? <Badge variant="outline">{skill.source_type}</Badge> : null}
            </div>
            <div className="mt-1 text-slate-500">
              {skill.always_on ? "always on" : `matched triggers: ${(skill.matched_triggers || []).join(", ") || "-"}`}
            </div>
            {skill.compatibility_level === "rule_only" ? (
              <div className="mt-1 text-amber-700">仅规则注入：会影响提示词，不会直接调用外部天气/搜索等工具。</div>
            ) : null}
            <div className="mt-1 text-slate-500">capabilities: {(skill.capabilities || []).join(", ") || "-"}</div>
            <div className="mt-1 text-slate-500">tools: {(skill.tools || []).join(", ") || "-"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChatBlindSpots({
  items,
  workspaceId,
  onOpenBlindSpotLink,
}: {
  items: BlindSpotItem[];
  workspaceId: number | null;
  onOpenBlindSpotLink: (item: BlindSpotItem) => void;
}) {
  if (!items.length) return null;

  return (
    <div className="rounded-md border border-amber-200 bg-amber-50/80 p-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">本轮参考的学习盲点</div>
      <div className="space-y-2">
        {items.map((item, index) => (
          <div key={`${item.course_name}-${index}`} className="rounded-md border border-amber-200 bg-white px-3 py-2 text-xs text-slate-700">
            <div className="font-medium text-slate-900">{item.course_name}</div>
            <div className="mt-1 leading-6">
              未解决 {item.unresolved} 条
              {item.top_point ? `，高频卡点 ${item.top_point}` : ""}
            </div>
            {workspaceId ? (
              <div className="mt-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 border-amber-200 bg-amber-50 px-2 text-[11px] text-amber-800 hover:bg-amber-100"
                  onClick={() => onOpenBlindSpotLink(item)}
                >
                  回到工作区定位
                </Button>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChatSources({
  sources,
  parseKnowledgeSource,
  onOpenSourceLink,
}: {
  sources: string[];
  parseKnowledgeSource: (source: string) => ParsedKnowledgeSource | null;
  onOpenSourceLink: (source: string) => void;
}) {
  if (!sources.length) return null;

  return (
    <div className="border-t border-[hsl(var(--border))] pt-3">
      <div className="mb-2 text-xs font-medium text-slate-500">参考来源</div>
      <div className="flex flex-wrap gap-2">
        {sources.map((source, index) => {
          const parsed = parseKnowledgeSource(source);
          if (parsed?.workspaceId) {
            return (
              <button key={`${source}-${index}`} type="button" onClick={() => onOpenSourceLink(source)} className="max-w-full text-left">
                <Badge variant="outline" className="max-w-full break-all text-[11px] text-slate-600 hover:bg-slate-50">
                  {parsed.title || source}
                </Badge>
              </button>
            );
          }
          return (
            <Badge key={`${source}-${index}`} variant="outline" className="max-w-full break-all text-[11px] text-slate-600">
              {source}
            </Badge>
          );
        })}
      </div>
    </div>
  );
}

export function ChatHighlights({
  highlights,
  parseKnowledgeSource,
  onOpenSourceLink,
}: {
  highlights: MessageHighlight[];
  parseKnowledgeSource: (source: string) => ParsedKnowledgeSource | null;
  onOpenSourceLink: (source: string) => void;
}) {
  if (!highlights.length) return null;

  return (
    <div className="border-t border-[hsl(var(--border))] pt-3">
      <div className="mb-2 text-xs font-medium text-slate-500">引用片段</div>
      <div className="space-y-2">
        {highlights.map((highlight, index) => {
          const parsed = parseKnowledgeSource(highlight.source);
          return (
            <button
              key={`${highlight.source}-${index}`}
              type="button"
              onClick={() => onOpenSourceLink(highlight.source)}
              className="block w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-left transition hover:bg-slate-100"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="truncate text-xs font-medium text-slate-900">{highlight.title || parsed?.title || "引用片段"}</div>
                {typeof highlight.score === "number" ? <span className="text-[11px] text-slate-400">score {highlight.score.toFixed(3)}</span> : null}
              </div>
              <div className="mt-2 line-clamp-3 text-xs leading-6 text-slate-600">{highlight.snippet}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
