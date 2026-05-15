"use client";

export interface ChatToolCall {
  name: string;
}

export interface ChatToolTrace {
  skill: string;
  tool: string;
  params?: Record<string, unknown>;
  status: "success" | "failed" | "empty";
  error?: string;
}

export interface ChatSkillMatch {
  name: string;
  mode?: string;
  source_type?: string;
  compatibility_level?: string;
  capabilities?: string[];
  always_on?: boolean;
  matched_triggers?: string[];
  has_tools?: boolean;
  tools?: string[];
}

export interface ChatMessageHighlight {
  source: string;
  title: string;
  snippet: string;
  document_id?: number;
  chunk_index?: number;
  score?: number;
}

export interface ChatBlindSpotItem {
  course_name: string;
  unresolved: number;
  dominant_type: string;
  dominant_type_count?: number;
  top_point?: string;
  top_point_count?: number;
}

export interface ChatHistoryMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  meta?: {
    sources?: string[];
    highlights?: ChatMessageHighlight[];
    blind_spots?: ChatBlindSpotItem[];
    tool_calls?: ChatToolCall[];
    tool_trace?: ChatToolTrace[];
    skill_matches?: ChatSkillMatch[];
  };
}

export interface ChatViewMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  sources?: string[];
  highlights?: ChatMessageHighlight[];
  blind_spots?: ChatBlindSpotItem[];
  tool_calls?: ChatToolCall[];
  tool_trace?: ChatToolTrace[];
  skill_matches?: ChatSkillMatch[];
  timestamp?: string;
  streaming?: boolean;
}

export function getConversationStorageKey(username: string) {
  return `current_conversation_id_${username}`;
}

export function mapHistoryMessages(messages: ChatHistoryMessage[]): ChatViewMessage[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    sources: message.meta?.sources || [],
    highlights: message.meta?.highlights || [],
    blind_spots: message.meta?.blind_spots || [],
    tool_calls: message.meta?.tool_calls || [],
    tool_trace: message.meta?.tool_trace || [],
    skill_matches: message.meta?.skill_matches || [],
    timestamp: new Date(message.created_at).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    }),
  }));
}

export function migrateLegacyConversationStorage(username: string) {
  const scopedKey = getConversationStorageKey(username);
  const legacyConversationId = localStorage.getItem("current_conversation_id");
  if (legacyConversationId && !localStorage.getItem(scopedKey)) {
    localStorage.setItem(scopedKey, legacyConversationId);
    localStorage.removeItem("current_conversation_id");
  }
  return scopedKey;
}
