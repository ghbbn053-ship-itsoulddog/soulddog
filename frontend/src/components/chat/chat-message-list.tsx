"use client";

import type React from "react";
import { Bot, User } from "lucide-react";

import MarkdownMessage from "@/components/MarkdownMessage";
import { Card, CardContent } from "@/components/ui/card";
import {
  ChatBlindSpots,
  ChatHighlights,
  ChatSkillMatches,
  ChatSources,
  ChatToolCalls,
  ChatToolTrace,
  type BlindSpotItem,
  type MessageHighlight,
  type ParsedKnowledgeSource,
  type SkillMatch,
  type ToolCall,
  type ToolTrace,
} from "@/components/chat/chat-message-sections";
import { cn } from "@/lib/utils";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  sources?: string[];
  highlights?: MessageHighlight[];
  blind_spots?: BlindSpotItem[];
  tool_calls?: ToolCall[];
  tool_trace?: ToolTrace[];
  skill_matches?: SkillMatch[];
  timestamp?: string;
  streaming?: boolean;
};

type ChatMessageListProps = {
  messages: Message[];
  workspaceId: number | null;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  toolDisplayName: (name: string) => string;
  parseKnowledgeSource: (source: string) => ParsedKnowledgeSource | null;
  onOpenBlindSpotLink: (item: BlindSpotItem) => void;
  onOpenSourceLink: (source: string) => void;
};

export function ChatMessageList({
  messages,
  workspaceId,
  messagesEndRef,
  toolDisplayName,
  parseKnowledgeSource,
  onOpenBlindSpotLink,
  onOpenSourceLink,
}: ChatMessageListProps) {
  return (
    <div className="mx-auto flex max-w-[880px] flex-col gap-5 px-4 py-5 md:px-5">
      {messages.map((msg) => (
        <div key={msg.id} className={cn("flex gap-3", msg.role === "user" && "flex-row-reverse")}>
          <div
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white",
              msg.role === "user" ? "bg-slate-900" : "bg-[hsl(var(--primary))]"
            )}
          >
            {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
          </div>
          <div className={cn("flex max-w-[85%] flex-1 flex-col gap-1", msg.role === "user" ? "items-end" : "items-start")}>
            <Card
              className={cn(
                "max-w-full border-slate-200/90 shadow-[0_10px_24px_rgba(15,23,42,0.04)]",
                msg.role === "user"
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.94))]"
              )}
            >
              <CardContent className="space-y-3 p-4">
                {msg.role === "assistant" ? (
                  <>
                    {msg.thinking ? (
                      <div className="whitespace-pre-wrap rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                        <span className="font-medium">思考：</span>
                        {msg.thinking}
                      </div>
                    ) : null}
                    <MarkdownMessage content={msg.content || "正在思考..."} />
                  </>
                ) : (
                  <p className="whitespace-pre-wrap text-sm leading-6">{msg.content}</p>
                )}

                <ChatToolCalls toolCalls={msg.tool_calls || []} toolDisplayName={toolDisplayName} />
                <ChatToolTrace traces={msg.tool_trace || []} />
                <ChatSkillMatches matches={msg.skill_matches || []} />
                <ChatBlindSpots items={msg.blind_spots || []} workspaceId={workspaceId} onOpenBlindSpotLink={onOpenBlindSpotLink} />
                <ChatSources sources={msg.sources || []} parseKnowledgeSource={parseKnowledgeSource} onOpenSourceLink={onOpenSourceLink} />
                <ChatHighlights highlights={msg.highlights || []} parseKnowledgeSource={parseKnowledgeSource} onOpenSourceLink={onOpenSourceLink} />
              </CardContent>
            </Card>
            <span className="px-1 text-xs text-slate-400">{msg.timestamp}</span>
          </div>
        </div>
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
}
