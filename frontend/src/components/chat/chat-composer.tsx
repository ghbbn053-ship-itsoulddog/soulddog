"use client";

import type React from "react";
import { BrainCircuit, Loader2, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

type FollowUpSuggestion = {
  label: string;
  prompt: string;
};

type ModelOption = {
  key: string;
  provider: string;
  model: string;
};

type ChatComposerProps = {
  input: string;
  username: string;
  isLoading: boolean;
  requestedPrompt: string;
  requestedStrategy: string;
  followUpSuggestions: FollowUpSuggestion[];
  showFollowUpSuggestions: boolean;
  modelOptions: ModelOption[];
  selectedModelKey: string;
  showThinking: boolean;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  selectorClassName: string;
  onInputChange: (value: string) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onApplySuggestedPrompt: (prompt: string, label: string) => void;
  onModelChange: (value: string) => void;
  onToggleThinking: () => void;
  onSend: () => void;
};

export function ChatComposer({
  input,
  username,
  isLoading,
  requestedPrompt,
  requestedStrategy,
  followUpSuggestions,
  showFollowUpSuggestions,
  modelOptions,
  selectedModelKey,
  showThinking,
  inputRef,
  selectorClassName,
  onInputChange,
  onKeyDown,
  onApplySuggestedPrompt,
  onModelChange,
  onToggleThinking,
  onSend,
}: ChatComposerProps) {
  return (
    <div className="border-t border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(248,250,252,0.88))] p-3 backdrop-blur-xl md:px-5">
      <div className="mx-auto max-w-5xl">
        {showFollowUpSuggestions && requestedPrompt && followUpSuggestions.length > 0 ? (
          <div className="mb-3 rounded-[1.2rem] border border-slate-200 bg-white/96 px-4 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
            <div className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">追问策略建议</div>
            {requestedStrategy ? (
              <div className="mb-2 text-xs text-slate-500">已按常用策略“{requestedStrategy}”优先排序</div>
            ) : (
              <div className="mb-2 text-xs text-slate-500">当前按默认顺序展示建议</div>
            )}
            <div className="flex flex-wrap gap-2">
              {followUpSuggestions.map((item) => (
                <Button key={item.label} type="button" variant="outline" size="sm" onClick={() => onApplySuggestedPrompt(item.prompt, item.label)}>
                  {item.label}
                </Button>
              ))}
            </div>
          </div>
        ) : null}

        <Card className="border-slate-200/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.94))] shadow-[0_12px_28px_rgba(15,23,42,0.04)]">
          <CardContent className="p-3.5">
            <Textarea
              ref={inputRef}
              value={input}
              onChange={(event) => onInputChange(event.target.value)}
              onKeyDown={onKeyDown}
              placeholder={username ? "输入你的问题，Shift+Enter 换行" : "请先登录"}
              disabled={!username || isLoading}
              className="min-h-20 resize-none border-0 bg-transparent px-0 py-0 text-sm shadow-none focus-visible:ring-0"
            />

            <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex flex-wrap gap-2">
                <select
                  value={selectedModelKey}
                  onChange={(event) => onModelChange(event.target.value)}
                  disabled={isLoading || modelOptions.length === 0}
                  className={`${selectorClassName} h-9 border-slate-200 bg-white shadow-none md:w-[180px]`}
                >
                  {modelOptions.map((item) => (
                    <option key={item.key} value={item.key}>
                      {item.model}
                    </option>
                  ))}
                </select>

                <Button
                  type="button"
                  variant={showThinking ? "default" : "outline"}
                  size="sm"
                  className={showThinking ? "bg-blue-600 hover:bg-blue-700" : "border-slate-300 bg-white/90 text-slate-700 hover:bg-slate-50"}
                  onClick={onToggleThinking}
                  disabled={isLoading}
                >
                  <BrainCircuit className="h-4 w-4" />
                  思考模式
                </Button>
              </div>

              <Button className="bg-blue-600 hover:bg-blue-700 md:min-w-[104px]" onClick={onSend} disabled={!username || !input.trim() || isLoading}>
                {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                发送
              </Button>
            </div>
          </CardContent>
        </Card>

        <p className="mt-2 text-center text-[11px] text-slate-400">AI 助手可能会有错误，请核实重要信息</p>
      </div>
    </div>
  );
}
