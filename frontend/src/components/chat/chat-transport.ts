"use client";

import type {
  ChatBlindSpotItem,
  ChatMessageHighlight,
  ChatSkillMatch,
  ChatToolCall,
  ChatToolTrace,
} from "@/components/chat/chat-history";

export type ChatTransportPayload = {
  username: string;
  message: string;
  conversation_id: number | null;
  workspace_id: number | null;
  override_provider: string;
  override_model: string;
  reasoning_mode: string;
  show_thinking: boolean;
  execution_mode: "chat" | "agent";
  agent_framework: "openai_agents" | "langgraph";
  prompt_strategy: string;
  generated_by?: string;
};

type ChatTransportMeta = {
  sources?: string[];
  highlights?: ChatMessageHighlight[];
  blind_spots?: ChatBlindSpotItem[];
  tool_calls?: ChatToolCall[];
  tool_trace?: ChatToolTrace[];
  skill_matches?: ChatSkillMatch[];
};

type StreamEventPayload = ChatTransportMeta & {
  content?: string;
  thinking?: string;
  conversation_id?: number;
  ping?: boolean;
  stage?: string;
  done?: boolean;
};

export type ChatFallbackResult = ChatTransportMeta & {
  message: string;
  conversationId: number | null;
};

export type ChatStreamResult = ChatTransportMeta & {
  content: string;
  thinking: string;
  conversationId: number | null;
  receivedAnyChunk: boolean;
};

type StreamChatMessageArgs = {
  streamApiBase: string;
  payload: ChatTransportPayload;
  onPatch: (patch: { content: string; thinking: string }) => void;
  onPing: (hint: string) => void;
};

function buildStageHint(stage?: string) {
  return stage === "tool_call" ? "正在调用教务工具..." : "正在生成回答...";
}

function readMeta(data: ChatTransportMeta): ChatTransportMeta {
  return {
    sources: data.sources || [],
    highlights: data.highlights || [],
    blind_spots: data.blind_spots || [],
    tool_calls: data.tool_calls || [],
    tool_trace: data.tool_trace || [],
    skill_matches: data.skill_matches || [],
  };
}

export async function sendChatFallback(
  apiBase: string,
  payload: ChatTransportPayload
): Promise<ChatFallbackResult> {
  const res = await fetch(`${apiBase}/api/chat/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err?.detail || err?.message || `请求失败(${res.status})`;
    throw new Error(String(detail));
  }

  const data = await res.json();
  return {
    message: data?.message || "未获取到回答",
    conversationId: data?.conversation_id || null,
    ...readMeta(data || {}),
  };
}

export async function streamChatMessage({
  streamApiBase,
  payload,
  onPatch,
  onPing,
}: StreamChatMessageArgs): Promise<ChatStreamResult> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 180000);

  let flushTimer: ReturnType<typeof setTimeout> | null = null;
  let content = "";
  let thinking = "";
  let conversationId = payload.conversation_id;
  let receivedAnyChunk = false;
  let meta: ChatTransportMeta = {};

  const flushNow = () => {
    onPatch({ content, thinking });
  };

  const scheduleFlush = () => {
    if (flushTimer !== null) return;
    flushTimer = setTimeout(() => {
      flushNow();
      flushTimer = null;
    }, 60);
  };

  const finalize = () => {
    if (flushTimer !== null) {
      clearTimeout(flushTimer);
      flushTimer = null;
    }
    clearTimeout(timeoutId);
  };

  try {
    const response = await fetch(`${streamApiBase}/api/chat/send-stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "Cache-Control": "no-cache",
        "x-trace-id": `chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      },
      credentials: "include",
      signal: controller.signal,
      cache: "no-store",
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      clearTimeout(timeoutId);
      const err = await response.json().catch(() => ({}));
      if (response.status === 403) {
        throw new Error("登录账号与会话不一致，请退出后重新登录");
      }
      throw new Error(err?.detail || err?.message || `请求失败(${response.status})`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("无法读取响应流");
    }

    const decoder = new TextDecoder();
    let sseBuffer = "";
    let streamDone = false;

    const applyEvent = (data: StreamEventPayload) => {
      if (data.conversation_id && !conversationId) {
        conversationId = data.conversation_id;
      }

      if (data.content) {
        content += data.content;
        receivedAnyChunk = true;
        scheduleFlush();
      }

      if (data.thinking) {
        thinking += data.thinking;
        receivedAnyChunk = true;
        scheduleFlush();
      }

      if (data.ping && !receivedAnyChunk) {
        onPing(buildStageHint(data.stage));
      }

      if (data.done) {
        meta = readMeta(data);
        if (data.conversation_id) {
          conversationId = data.conversation_id;
        }
        streamDone = true;
      }
    };

    while (!streamDone) {
      const { done, value } = await reader.read();
      if (done) break;

      sseBuffer += decoder.decode(value, { stream: true });
      const parts = sseBuffer.split(/\r?\n\r?\n/);
      sseBuffer = parts.pop() || "";

      for (const event of parts) {
        const dataLines = event
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.replace(/^data:\s?/, "").trim());

        for (const dataLine of dataLines) {
          if (!dataLine) continue;
          try {
            applyEvent(JSON.parse(dataLine) as StreamEventPayload);
            if (streamDone) {
              break;
            }
          } catch {
          }
        }

        if (streamDone) {
          break;
        }
      }
    }

    if (!streamDone && sseBuffer.trim().startsWith("data:")) {
      try {
        applyEvent(JSON.parse(sseBuffer.trim().replace(/^data:\s?/, "").trim()) as StreamEventPayload);
      } catch {
      }
    }

    flushNow();

    return {
      content,
      thinking,
      conversationId,
      receivedAnyChunk,
      ...meta,
    };
  } finally {
    finalize();
  }
}
