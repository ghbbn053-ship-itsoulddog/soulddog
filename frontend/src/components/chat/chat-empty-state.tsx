"use client";

import { Bot, WandSparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type FollowUpSuggestion = {
  label: string;
  prompt: string;
};

type ChatEmptyStateProps = {
  requestedPrompt: string;
  requestedCourse: string;
  requestedStrategy: string;
  requestedWorkspaceId: number | null;
  requestedContextTags: string[];
  quickQuestions: string[];
  followUpSuggestions: FollowUpSuggestion[];
  onQuestionPick: (value: string) => void;
  onOpenRequestedWorkspaceContext: () => void;
  onApplySuggestedPrompt: (prompt: string, label: string) => void;
};

export function ChatEmptyState({
  requestedPrompt,
  requestedCourse,
  requestedStrategy,
  requestedWorkspaceId,
  requestedContextTags,
  quickQuestions,
  followUpSuggestions,
  onQuestionPick,
  onOpenRequestedWorkspaceContext,
  onApplySuggestedPrompt,
}: ChatEmptyStateProps) {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-3xl flex-col justify-center px-4 py-12 text-center">
      {requestedPrompt ? (
        <div className="mb-6 rounded-2xl border border-sky-200 bg-sky-50/80 px-4 py-3 text-left text-sm text-slate-700">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">来自学习疑问</Badge>
            {requestedCourse ? <Badge variant="secondary">{requestedCourse}</Badge> : null}
          </div>
          {requestedContextTags.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {requestedContextTags.map((tag) => (
                <Badge key={tag} variant="outline" className="bg-white/80 text-slate-600">
                  {tag}
                </Badge>
              ))}
            </div>
          ) : null}
          <div className="mt-2 leading-6">已为你带入一条追问草稿。你可以直接发送，也可以先改写成你现在最关心的问法。</div>
          {requestedStrategy ? (
            <div className="mt-2 text-xs leading-5 text-slate-500">当前已按你最近更常使用的追问方式“{requestedStrategy}”优先排序建议。</div>
          ) : requestedPrompt ? (
            <div className="mt-2 text-xs leading-5 text-slate-500">当前使用默认建议顺序，你可以按这次实际需求自由选择追问方式。</div>
          ) : null}
          {requestedWorkspaceId ? (
            <div className="mt-3">
              <Button type="button" size="sm" variant="outline" onClick={onOpenRequestedWorkspaceContext}>
                回到工作区结果
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-[1.6rem] bg-[linear-gradient(135deg,#1f6feb,#5a67d8)] text-white shadow-[0_18px_40px_rgba(31,111,235,0.2)]">
        <Bot className="h-10 w-10" />
      </div>
      <h2 className="text-2xl font-semibold tracking-tight text-slate-950">快速会话</h2>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">这里专注快问快答。模型从输入框旁边选，问完可以直接保存到工作区。</p>

      {!requestedPrompt ? (
        <div className="mt-8 grid w-full max-w-2xl gap-3 sm:grid-cols-2">
          {quickQuestions.map((question) => (
            <button
              key={question}
              onClick={() => onQuestionPick(question)}
              className="rounded-[1.2rem] border border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.96))] p-4 text-left transition-all hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-[0_12px_26px_rgba(15,23,42,0.05)]"
            >
              <WandSparkles className="mb-3 h-4 w-4 text-blue-600" />
              <div className="text-sm font-medium text-slate-900">{question}</div>
            </button>
          ))}
        </div>
      ) : (
        <div className="mt-8 max-w-2xl rounded-2xl border border-dashed border-slate-200 bg-white/80 px-4 py-4 text-left text-sm text-slate-600">
          <div className="leading-6">当前更适合直接围绕这条疑问继续追问。发送后如果还想发起别的话题，再新建一轮快速会话即可。</div>
          {followUpSuggestions.length > 0 ? (
            <div className="mt-4">
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">可直接使用的追问策略</div>
              <div className="grid gap-2 sm:grid-cols-3">
                {followUpSuggestions.map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => onApplySuggestedPrompt(item.prompt, item.label)}
                    className="rounded-[1.1rem] border border-slate-200 bg-white px-3 py-3 text-left transition-all hover:-translate-y-0.5 hover:border-slate-300 hover:bg-slate-50 hover:shadow-[0_10px_24px_rgba(15,23,42,0.04)]"
                  >
                    <div className="text-sm font-medium text-slate-900">{item.label}</div>
                    <div className="mt-1 text-xs leading-5 text-slate-500">{item.prompt}</div>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
