'use client';

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Blocks,
  BookOpenCheck,
  Brain,
  ChevronLeft,
  ChevronRight,
  Database,
  FileText,
  FlagTriangleRight,
  Network,
  Sparkles,
  Upload,
} from "lucide-react";

import { KnowledgeVisualization } from "@/components/knowledge/KnowledgeVisualization";
import { AIPanel } from "@/components/workspace/ai-panel";
import { PlatformSidebarFooter, PlatformSidebarHeader, createPlatformNav } from "@/components/workspace/app-sidebar";
import { LearningStatus } from "@/components/workspace/learning-status";
import { ReminderModal } from "@/components/workspace/reminder-modal";
import {
  WorkbenchBadge,
  WorkbenchEmpty,
  WorkbenchSection,
  WorkbenchShell,
  WorkbenchStatCard,
} from "@/components/workspace/workbench-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type WorkspaceItem = {
  id: number;
  slug: string;
  name: string;
  description?: string;
  is_default: boolean;
};

type KnowledgeDocument = {
  id: number;
  workspace_id: number;
  title: string;
  doc_type: string;
  summary?: string;
  status: string;
  token_estimate: number;
  metadata?: Record<string, unknown>;
};

type KnowledgeChunk = {
  id: number;
  document_id: number;
  workspace_id: number;
  chunk_index: number;
  title?: string;
  content: string;
  char_count: number;
  metadata?: Record<string, unknown>;
};

type GraphData = {
  workspace: { id: number; name: string; slug: string };
  nodes: Array<{ id: string; label: string; type: string }>;
  edges: Array<{ id: string; source: string; target: string; label: string }>;
};

type PlatformSkill = {
  id: number;
  name: string;
  version?: string;
  description?: string;
  enabled: boolean;
  triggers: string[];
  tools: Array<{ name?: string }>;
};

type PlatformMcp = {
  id: number;
  name: string;
  description?: string;
  kind: string;
  enabled: boolean;
};

type CompositionData = {
  owner: string;
  skills: string[];
  mcp_tools: string[];
};

type AgentFramework = {
  id: string;
  name: string;
  recommended: boolean;
  available: boolean;
  requires?: string[];
};

type WorkspaceDetailResponse = {
  success: boolean;
  workspace: WorkspaceItem;
  stats: {
    documents: number;
    graph_nodes: number;
    graph_edges: number;
  };
  graph: GraphData;
};

type KnowledgeOverviewResponse = {
  success: boolean;
  workspace: WorkspaceItem;
  stats: {
    documents: number;
    knowledge_units: number;
    relations: number;
    ready_documents: number;
    failed_documents: number;
    total_tokens: number;
    by_doc_type: Record<string, number>;
    by_status: Record<string, number>;
    by_authority: Record<string, number>;
  };
  documents: KnowledgeDocument[];
};

type LearningStatusResponse = {
  success: boolean;
  workspace: { id: number; name: string; slug: string };
  metrics: {
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
  signals: {
    knowledge_density: number;
    document_failure_ratio: number;
    authority_breakdown: Record<string, number>;
    education_freshness_days: number | null;
    last_education_sync_at: string | null;
  };
};

type SuggestionItem = {
  id: number;
  key: string;
  type: string;
  title: string;
  content: string;
  reason?: string;
  tone?: "normal" | "warning" | "urgent";
  status: string;
  payload?: Record<string, unknown>;
  created_at?: string | null;
};

type SuggestionsResponse = {
  success: boolean;
  suggestions: SuggestionItem[];
  reminders: SuggestionItem[];
};

type LearningMemoryItem = {
  id: number;
  owner_username: string;
  workspace_id?: number | null;
  course_name?: string;
  question_text: string;
  question_summary: string;
  question_type: string;
  knowledge_points: string[];
  status: string;
  answer_summary: string;
  source_refs: Record<string, unknown>;
  importance: number;
  conversation_id?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type LearningMemoryResponse = {
  success: boolean;
  items: LearningMemoryItem[];
  summary: {
    total: number;
    unresolved: number;
    resolved: number;
    by_status: Record<string, number>;
    by_type: Record<string, number>;
    by_course: Record<string, number>;
    course_rank: string[];
    top_points: string[];
    review_priority: Array<{
      id: number;
      course_name: string;
      question_summary: string;
      question_type: string;
      importance: number;
      status: string;
    }>;
    prompt_strategy_rank?: Array<{
      strategy: string;
      count: number;
    }>;
  };
};

const MEMORY_TYPE_LABELS: Record<string, string> = {
  practice: "做题应用",
  concept: "概念理解",
  confusion: "易混区分",
  review: "复习记忆",
  reasoning: "推导计算",
  general: "通用追问",
};

function formatMemoryTypeLabel(value: string) {
  return MEMORY_TYPE_LABELS[value] || value || "未分类";
}

function formatMemoryStatusLabel(value: string) {
  if (value === "resolved") return "已解决";
  if (value === "unresolved") return "未解决";
  return value || "未知状态";
}

export default function WorkspaceDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const workspaceId = Number(params?.id || 0);
  const requestedDocId = Number(searchParams.get("doc") || 0);
  const requestedChunkIndex = Number(searchParams.get("chunk") || 0);
  const requestedMemoryCourse = (searchParams.get("course") || searchParams.get("course_name") || "").trim();
  const requestedMemoryPoint = (searchParams.get("point") || searchParams.get("knowledge_point") || "").trim();
  const requestedMemoryType = (searchParams.get("type") || searchParams.get("question_type") || "").trim();

  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [workspace, setWorkspace] = useState<WorkspaceItem | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [documentChunks, setDocumentChunks] = useState<KnowledgeChunk[]>([]);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [learningStatus, setLearningStatus] = useState<LearningStatusResponse | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [reminders, setReminders] = useState<SuggestionItem[]>([]);
  const [learningMemories, setLearningMemories] = useState<LearningMemoryItem[]>([]);
  const [learningMemorySummary, setLearningMemorySummary] = useState<LearningMemoryResponse["summary"] | null>(null);
  const [memoryCourseFilter, setMemoryCourseFilter] = useState("");
  const [memoryTypeFilter, setMemoryTypeFilter] = useState("");
  const [memoryPointFilter, setMemoryPointFilter] = useState("");
  const [preferDefaultPromptSuggestions, setPreferDefaultPromptSuggestions] = useState(false);
  const [selectedMemory, setSelectedMemory] = useState<LearningMemoryItem | null>(null);
  const [memoryDetailLoading, setMemoryDetailLoading] = useState(false);
  const [draftPrompt, setDraftPrompt] = useState("");
  const [reminderOpen, setReminderOpen] = useState(false);
  const [textFilename, setTextFilename] = useState("notes.md");
  const [textContent, setTextContent] = useState("");
  const [textAuthority, setTextAuthority] = useState("user");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadAuthority, setUploadAuthority] = useState("user");
  const [msg, setMsg] = useState("");
  const [knowledgeCollapsed, setKnowledgeCollapsed] = useState(false);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;
  const knowledgePanelStorageKey = useMemo(() => `workspace:${workspaceId}:knowledge-collapsed`, [workspaceId]);

  const refreshKnowledge = async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/knowledge/${encodeURIComponent(uname)}/${workspaceId}`, {
      credentials: "include",
    });
    const json: KnowledgeOverviewResponse | null = res.ok ? await res.json() : null;
    if (!json?.success) return;
    setWorkspace(json.workspace || null);
    setDocuments(json.documents || []);
  };

  const refreshDetail = async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}/detail/${workspaceId}`, {
      credentials: "include",
    });
    const json: WorkspaceDetailResponse | null = res.ok ? await res.json() : null;
    setGraph(json?.graph || null);
  };

  const refreshLearningStatus = async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/status/${workspaceId}?username=${encodeURIComponent(uname)}`, {
      credentials: "include",
    });
    const json: LearningStatusResponse | null = res.ok ? await res.json() : null;
    if (json?.success) setLearningStatus(json);
  };

  const refreshSuggestions = async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/suggestions/${workspaceId}?username=${encodeURIComponent(uname)}`, {
      credentials: "include",
    });
    const json: SuggestionsResponse | null = res.ok ? await res.json() : null;
    if (!json?.success) return;
    setSuggestions(json.suggestions || []);
    setReminders(json.reminders || []);
  };

  const refreshLearningMemories = async (
    uname: string,
    filters?: { course?: string; type?: string; point?: string }
  ) => {
    const params = new URLSearchParams({
      workspace_id: String(workspaceId),
      limit: "12",
    });
    if (filters?.course) params.set("course_name", filters.course);
    if (filters?.type) params.set("question_type", filters.type);
    if (filters?.point) params.set("knowledge_point", filters.point);
    const res = await fetch(`${API_BASE}/api/learning-memory/${encodeURIComponent(uname)}?${params.toString()}`, {
      credentials: "include",
    });
    const json: LearningMemoryResponse | null = res.ok ? await res.json() : null;
    if (!json?.success) return;
    setLearningMemories(json.items || []);
    setLearningMemorySummary(json.summary || null);
  };

  const openMemoryDetail = async (memory: LearningMemoryItem) => {
    setSelectedMemory(memory);
    if (!username) return;
    setMemoryDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/learning-memory/${encodeURIComponent(username)}/${memory.id}`, {
        credentials: "include",
      });
      const json = await res.json().catch(() => ({}));
      if (res.ok && json?.success && json?.memory) {
        setSelectedMemory(json.memory as LearningMemoryItem);
      }
    } finally {
      setMemoryDetailLoading(false);
    }
  };

  const updateMemoryStatus = async (memoryId: number, status: string) => {
    if (!username) return;
    const res = await fetch(`${API_BASE}/api/learning-memory/${encodeURIComponent(username)}/${memoryId}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username, status }),
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json?.success) {
      setMsg(json?.detail || "更新学习疑问状态失败");
      return;
    }
    setSelectedMemory((prev) => (prev && prev.id === memoryId ? { ...prev, status } : prev));
    await refreshLearningMemories(username, {
      course: memoryCourseFilter,
      type: memoryTypeFilter,
      point: memoryPointFilter,
    });
  };

  const refreshDocumentChunks = async (uname: string, documentId: number) => {
    const res = await fetch(`${API_BASE}/api/knowledge/${encodeURIComponent(uname)}/${workspaceId}/documents/${documentId}/chunks`, {
      credentials: "include",
    });
    const json = res.ok ? await res.json() : null;
    setDocumentChunks(json?.chunks || []);
  };

  useEffect(() => {
    const run = async () => {
      try {
        const meRes = await fetch(`${API_BASE}/api/auth/me`, { credentials: "include" });
        const me = meRes.ok ? await meRes.json() : null;
        if (!me?.authenticated || !me?.username) {
          router.replace("/login");
          return;
        }
        const uname = String(me.username);
        setUsername(uname);
        await Promise.all([
          refreshKnowledge(uname),
          refreshDetail(uname),
          refreshLearningStatus(uname),
          refreshSuggestions(uname),
          refreshLearningMemories(uname),
        ]);
      } catch {
        router.replace("/workspace");
      } finally {
        setLoading(false);
      }
    };

    if (!workspaceId) {
      router.replace("/workspace");
      return;
    }
    run();
  }, [API_BASE, router, workspaceId]);

  const authorityTone = (authority: string) => {
    if (authority === "system") return "warning";
    if (authority === "school") return "secondary";
    return "outline";
  };

  const statusTone = (status: string) => {
    if (status === "ready") return "success";
    if (status === "failed") return "destructive";
    return "warning";
  };

  const saveTextDoc = async () => {
    if (!username || !workspaceId || !textFilename.trim() || !textContent.trim()) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/workspace/documents/text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          username,
          workspace_id: workspaceId,
          filename: textFilename.trim(),
          content: textContent,
          authority_level: textAuthority,
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json?.success) throw new Error(json?.detail || `保存失败(${res.status})`);
      setTextContent("");
      await Promise.all([refreshKnowledge(username), refreshDetail(username)]);
      setMsg("文本已入知识库");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const uploadDocument = async () => {
    if (!username || !workspaceId || !uploadFile) return;
    setSaving(true);
    setMsg("");
    try {
      const formData = new FormData();
      formData.append("username", username);
      formData.append("workspace_id", String(workspaceId));
      formData.append("authority_level", uploadAuthority);
      formData.append("document_file", uploadFile);
      const res = await fetch(`${API_BASE}/api/workspace/documents/upload`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json?.success) throw new Error(json?.detail || `上传失败(${res.status})`);
      setUploadFile(null);
      await Promise.all([refreshKnowledge(username), refreshDetail(username)]);
      setMsg("文档已上传并入库");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "上传失败");
    } finally {
      setSaving(false);
    }
  };

  const stats = useMemo(
    () => ({
      documents: documents.length,
      nodes: graph?.nodes?.length || 0,
      edges: graph?.edges?.length || 0,
    }),
    [documents.length, graph]
  );

  const reviewPriorityItems = useMemo(
    () => learningMemorySummary?.review_priority?.slice(0, 4) || [],
    [learningMemorySummary]
  );

  const promptStrategyCards = useMemo(
    () => (learningMemorySummary?.prompt_strategy_rank || []).slice(0, 3),
    [learningMemorySummary]
  );

  const memoryCourseCards = useMemo(() => {
    const byCourse = learningMemorySummary?.by_course || {};
    const rank = learningMemorySummary?.course_rank || [];
    return rank
      .map((course) => ({ course, count: byCourse[course] || 0 }))
      .filter((item) => item.count > 0)
      .slice(0, 6);
  }, [learningMemorySummary]);

  const memoryTypeCards = useMemo(() => {
    const byType = learningMemorySummary?.by_type || {};
    return Object.entries(byType)
      .sort((a, b) => b[1] - a[1])
      .map(([key, count]) => ({
        key,
        label: formatMemoryTypeLabel(key),
        count,
      }))
      .slice(0, 6);
  }, [learningMemorySummary]);

  const reviewPointCards = useMemo(
    () => (learningMemorySummary?.top_points || []).slice(0, 6),
    [learningMemorySummary]
  );

  const primaryPromptStrategy = promptStrategyCards[0]?.strategy || "";
  const hasMemoryFilters = Boolean(memoryCourseFilter || memoryTypeFilter || memoryPointFilter);
  const nextPriorityMemory = reviewPriorityItems[0] || null;

  const resolvePromptStrategyForChat = () => {
    if (preferDefaultPromptSuggestions) return "";
    return primaryPromptStrategy;
  };

  const consumeDefaultPromptSuggestionOverride = () => {
    if (preferDefaultPromptSuggestions) {
      setPreferDefaultPromptSuggestions(false);
    }
  };

  const applyMemoryFilters = (filters: { course?: string; type?: string; point?: string }) => {
    setMemoryCourseFilter(filters.course || "");
    setMemoryTypeFilter(filters.type || "");
    setMemoryPointFilter(filters.point || "");
  };

  const openMemoryDraftInPanel = (memory: LearningMemoryItem) => {
    const prompt = [
      memory.course_name ? `当前课程：${memory.course_name}` : "",
      `问题类型：${formatMemoryTypeLabel(memory.question_type)}`,
      `我之前卡住的问题：${memory.question_text || memory.question_summary}`,
      memory.answer_summary ? `已有摘要：${memory.answer_summary}` : "",
      memory.knowledge_points.length ? `相关知识点：${memory.knowledge_points.join("、")}` : "",
      "请先判断我现在最可能没真正弄懂的是哪一层，再给我一个最适合继续追问的切入点。",
    ].filter(Boolean).join("\n\n");
    setSelectedMemory(null);
    setDraftPrompt(prompt);
  };

  const openFilteredMemoriesDraftInPanel = () => {
    if (!learningMemories.length) return;
    const topQuestions = learningMemories
      .slice(0, 3)
      .map((item, index) => `${index + 1}. ${item.question_summary}`)
      .join("\n");
    const focusText = [
      memoryCourseFilter ? `课程：${memoryCourseFilter}` : "",
      memoryTypeFilter ? `问题类型：${formatMemoryTypeLabel(memoryTypeFilter)}` : "",
      memoryPointFilter ? `知识点：${memoryPointFilter}` : "",
    ].filter(Boolean).join("，");
    const prompt = [
      focusText ? `请围绕这些筛选后的学习疑问继续辅导我，重点关注${focusText}。` : "请围绕我最近的学习疑问继续辅导我。",
      topQuestions ? `当前优先问题有：\n${topQuestions}` : "",
      "请先归纳这些问题背后的共性卡点，再告诉我应该先从哪一个问题切入。",
    ].filter(Boolean).join("\n\n");
    setDraftPrompt(prompt);
  };

  const openPriorityMemoryDraftInPanel = () => {
    if (!nextPriorityMemory) return;
    const prompt = [
      `请围绕这个高优先级学习疑问继续辅导我：${nextPriorityMemory.question_summary}`,
      nextPriorityMemory.course_name ? `课程：${nextPriorityMemory.course_name}` : "",
      `问题类型：${formatMemoryTypeLabel(nextPriorityMemory.question_type)}`,
      "请先帮我判断我最可能卡在哪一层，再给我当前工作区里最适合直接继续问的一句追问。",
    ].filter(Boolean).join("\n");
    setDraftPrompt(prompt);
  };

  const continueWithMemoryInChat = (memory: LearningMemoryItem) => {
    const prompt = memory.question_text || memory.question_summary || "";
    if (!prompt.trim()) return;
    const params = new URLSearchParams({
      workspace_id: String(workspaceId),
      prompt,
    });
    if (memory.course_name) params.set("course", memory.course_name);
    if (memory.question_type) params.set("question_type", memory.question_type);
    const promptStrategy = resolvePromptStrategyForChat();
    if (promptStrategy) params.set("strategy", promptStrategy);
    setSelectedMemory(null);
    consumeDefaultPromptSuggestionOverride();
    router.push(`/chat?${params.toString()}`);
  };

  const continueWithFilteredMemoriesInChat = () => {
    if (!learningMemories.length) return;
    const topQuestions = learningMemories.slice(0, 3).map((item, index) => `${index + 1}. ${item.question_summary}`).join("\n");
    const focusText = [
      memoryCourseFilter ? `课程：${memoryCourseFilter}` : "",
      memoryTypeFilter ? `问题类型：${formatMemoryTypeLabel(memoryTypeFilter)}` : "",
      memoryPointFilter ? `知识点：${memoryPointFilter}` : "",
    ].filter(Boolean).join("，");
    const prompt = [
      focusText ? `请围绕这些筛选后的学习疑问继续辅导我，重点关注${focusText}。` : "请围绕我最近的学习疑问继续辅导我。",
      topQuestions ? `当前优先问题有：\n${topQuestions}` : "",
      "请先帮我归纳共性卡点，再给我一个最适合下一步追问的切入点。",
    ].filter(Boolean).join("\n\n");
    const params = new URLSearchParams({
      workspace_id: String(workspaceId),
      prompt,
    });
    if (memoryCourseFilter) params.set("course", memoryCourseFilter);
    if (memoryPointFilter) params.set("point", memoryPointFilter);
    if (memoryTypeFilter) params.set("question_type", memoryTypeFilter);
    const promptStrategy = resolvePromptStrategyForChat();
    if (promptStrategy) params.set("strategy", promptStrategy);
    consumeDefaultPromptSuggestionOverride();
    router.push(`/chat?${params.toString()}`);
  };

  const continueWithPrioritySummaryInChat = () => {
    if (!nextPriorityMemory) return;
    const prompt = [
      `请围绕这个高优先级学习疑问继续辅导我：${nextPriorityMemory.question_summary}`,
      nextPriorityMemory.course_name ? `课程：${nextPriorityMemory.course_name}` : "",
      `问题类型：${formatMemoryTypeLabel(nextPriorityMemory.question_type)}`,
      "请先帮我说明我最可能卡在哪里，再给我下一步最有效的复习或追问方式。",
    ].filter(Boolean).join("\n");
    const params = new URLSearchParams({
      workspace_id: String(workspaceId),
      prompt,
    });
    if (nextPriorityMemory.course_name) params.set("course", nextPriorityMemory.course_name);
    if (nextPriorityMemory.question_type) params.set("question_type", nextPriorityMemory.question_type);
    const promptStrategy = resolvePromptStrategyForChat();
    if (promptStrategy) params.set("strategy", promptStrategy);
    consumeDefaultPromptSuggestionOverride();
    router.push(`/chat?${params.toString()}`);
  };

  const draftPromptFromReference = (title: string, snippet: string, sourceLabel: string) => {
    const prompt = [
      `我正在看资料《${title}》`,
      snippet ? `对应片段：${snippet}` : "",
      sourceLabel ? `来源：${sourceLabel}` : "",
      "请基于这段内容帮我提炼出我应该追问的关键问题，并直接给我最短的追问方式。",
    ].filter(Boolean).join("\n\n");
    setDraftPrompt(prompt);
  };

  useEffect(() => {
    if (!requestedDocId || documents.length === 0) return;
    const exists = documents.some((doc) => doc.id === requestedDocId);
    if (!exists) return;
    const node = document.getElementById(`doc-${requestedDocId}`);
    if (!node) return;
    const timer = window.setTimeout(() => {
      node.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [documents, requestedDocId]);

  useEffect(() => {
    if (!username || !requestedDocId) {
      setDocumentChunks([]);
      return;
    }
    void refreshDocumentChunks(username, requestedDocId);
  }, [username, requestedDocId]);

  useEffect(() => {
    if (!requestedDocId || documentChunks.length === 0) return;
    const node = document.getElementById(`chunk-${requestedDocId}-${requestedChunkIndex}`);
    if (!node) return;
    const timer = window.setTimeout(() => {
      node.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [documentChunks, requestedChunkIndex, requestedDocId]);

  useEffect(() => {
    if (reminders.length === 0) {
      setReminderOpen(false);
      return;
    }
    setReminderOpen(true);
  }, [reminders]);

  useEffect(() => {
    if (!username || !workspaceId) return;
    void refreshLearningMemories(username, {
      course: memoryCourseFilter,
      type: memoryTypeFilter,
      point: memoryPointFilter,
    });
  }, [memoryCourseFilter, memoryPointFilter, memoryTypeFilter, username, workspaceId]);

  useEffect(() => {
    if (!workspaceId) return;
    if (!requestedMemoryCourse && !requestedMemoryPoint && !requestedMemoryType) return;
    setMemoryCourseFilter(requestedMemoryCourse);
    setMemoryPointFilter(requestedMemoryPoint);
    setMemoryTypeFilter(requestedMemoryType);
  }, [requestedMemoryCourse, requestedMemoryPoint, requestedMemoryType, workspaceId]);

  useEffect(() => {
    if (!workspaceId || typeof window === "undefined") return;
    const saved = window.localStorage.getItem(knowledgePanelStorageKey);
    if (saved === null) return;
    setKnowledgeCollapsed(saved === "1");
  }, [knowledgePanelStorageKey, workspaceId]);

  useEffect(() => {
    if (!workspaceId || typeof window === "undefined") return;
    window.localStorage.setItem(knowledgePanelStorageKey, knowledgeCollapsed ? "1" : "0");
  }, [knowledgeCollapsed, knowledgePanelStorageKey, workspaceId]);

  const handleSuggestionAction = async (suggestionId: number, action: "accept" | "dismiss") => {
    if (!username) return;
    const res = await fetch(`${API_BASE}/api/suggestions/${workspaceId}/${action}?suggestion_id=${suggestionId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username }),
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json?.success) {
      setMsg(json?.detail || `${action === "accept" ? "接受" : "忽略"}建议失败`);
      return;
    }
    await Promise.all([refreshSuggestions(username), refreshLearningStatus(username)]);
  };

  if (loading) return <div className="p-6 text-sm text-slate-500">加载中...</div>;

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <Database className="h-3.5 w-3.5" />
          WORKSPACE DETAIL
        </WorkbenchBadge>
      }
      title={workspace?.name || "工作区详情"}
      description={workspace?.description || "工作区详情页现在收口成两件事：左边整理知识，右边直接对话验证。"}
      sidebarTitle="工作区导航"
      sidebarDescription="从平台入口页进入具体工作区后，围绕该工作区进行知识沉淀和调用。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={[
        ...createPlatformNav("workspace"),
        { label: "返回工作区入口", href: "/workspace", icon: <Database className="h-4 w-4" />, accent: "muted" },
      ]}
      footer={<PlatformSidebarFooter username={username} detail="Workspace owner" />}
      topActions={
        <>
          <Button variant="outline" onClick={() => router.push("/workspace")}>工作区列表</Button>
          <Button onClick={() => router.push(`/workspace/${workspaceId}`)}>工作区对话</Button>
        </>
      }
    >
      <div className="grid gap-4">
        <WorkbenchSection title="WORKSPACE DETAIL" description="默认工作区和当前知识空间摘要放到这一栏，不再占据太多主界面空间。">
          <div className="grid gap-3 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="grid gap-3 md:grid-cols-4">
              <WorkbenchStatCard label="Workspace" value={workspace?.name || "-"} hint={workspace?.description || workspace?.slug || "当前知识空间"} />
              <WorkbenchStatCard label="Default" value={workspace?.is_default ? "Yes" : "No"} hint={workspace?.is_default ? "平台默认知识空间" : "非默认工作区"} />
              <WorkbenchStatCard label="Documents" value={stats.documents} hint={`nodes ${stats.nodes} · edges ${stats.edges}`} />
              <WorkbenchStatCard
                label="Learning"
                value={learningStatus ? `${learningStatus.metrics.today_minutes}m` : "-"}
                hint={learningStatus ? `today prompts ${learningStatus.metrics.today_prompts}` : "等待学习状态聚合"}
              />
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-4 text-sm text-slate-600">
              <div className="font-medium text-slate-900">{workspace?.is_default ? "默认工作区" : "当前工作区"}</div>
              <div className="mt-2 leading-6">
                {workspace?.is_default
                  ? "平台默认知识空间已启用。这里的知识可视化、入库和 AI 对话都围绕这一工作区联动。"
                  : "当前知识空间已启用。这里的知识可视化、入库和 AI 对话都围绕这一工作区联动。"}
              </div>
            </div>
          </div>
        </WorkbenchSection>

        <div
          className={cn(
            "grid gap-4 xl:items-start",
            knowledgeCollapsed
              ? "xl:grid-cols-[92px_minmax(0,1fr)]"
              : "xl:grid-cols-[minmax(340px,430px)_minmax(0,1fr)]"
          )}
        >
          <div className="min-w-0 xl:self-stretch">
            {knowledgeCollapsed ? (
              <Card className="border-white/70 bg-white/90 shadow-[0_10px_32px_rgba(15,23,42,0.05)] xl:sticky xl:top-6">
                <CardContent className="flex flex-col items-center gap-3 p-3">
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => setKnowledgeCollapsed(false)}
                    title="展开知识库"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
                    <Database className="h-5 w-5" />
                  </div>
                  <div className="space-y-2 text-center">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">知识库</div>
                    <div className="text-xl font-semibold text-slate-950">{stats.documents}</div>
                    <div className="text-[11px] text-slate-500">docs</div>
                  </div>
                  <div className="space-y-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      onClick={() => router.push(`/knowledge?workspace_id=${workspaceId}`)}
                      title="打开知识库"
                    >
                      <Network className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      onClick={() => setKnowledgeCollapsed(false)}
                      title="展开并入库"
                    >
                      <Upload className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 xl:sticky xl:top-6 xl:h-[calc(100vh-6.5rem)]">
                <WorkbenchSection
                  title="知识库面板"
                  description="左侧负责知识可视化和入库，可以随时收起，把更多空间让给右侧对话。"
                  className="xl:flex xl:h-full xl:flex-col"
                  actions={
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" variant="outline" size="sm" onClick={() => router.push(`/knowledge?workspace_id=${workspaceId}`)}>
                        <Network className="h-4 w-4" />
                        打开知识库
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={() => setKnowledgeCollapsed(true)}>
                        <ChevronLeft className="h-4 w-4" />
                        收起知识库
                      </Button>
                    </div>
                  }
                >
                  <div className="grid gap-4 xl:flex-1 xl:grid-rows-[minmax(0,1fr)_auto] xl:overflow-hidden">
                    <ScrollArea className="rounded-2xl border border-slate-200 bg-slate-50/70 p-3 xl:min-h-0">
                      <KnowledgeVisualization
                        documents={documents.map((doc) => ({
                          id: doc.id,
                          title: doc.title,
                          docType: doc.doc_type,
                          status: doc.status,
                          tokenEstimate: doc.token_estimate,
                          authorityLevel: String(doc.metadata?.authority_level || "user"),
                          summary: doc.summary,
                        }))}
                        relationCount={stats.edges}
                      />
                    </ScrollArea>

                    <div className="space-y-4">
                      <div className="flex flex-wrap gap-2">
                        {["user", "school", "system"].map((level) => (
                          <Button
                            key={level}
                            type="button"
                            size="sm"
                            variant={textAuthority === level ? "default" : "outline"}
                            onClick={() => {
                              setTextAuthority(level);
                              setUploadAuthority(level);
                            }}
                          >
                            {level}
                          </Button>
                        ))}
                      </div>
                      <div className="rounded-2xl border border-dashed border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-4">
                        <div className="mb-3 text-sm font-medium text-slate-900">输入文本或选择文件</div>
                        <Textarea
                          value={textContent}
                          onChange={(e) => setTextContent(e.target.value)}
                          className="min-h-36 bg-white"
                          placeholder="在这里直接输入内容，或者下方选择文件。知识面板收起后，右侧对话会变成主视图。"
                        />
                        <div className="mt-3 flex flex-wrap gap-3">
                          <input
                            type="text"
                            value={textFilename}
                            onChange={(e) => setTextFilename(e.target.value)}
                            placeholder="notes.md"
                            className="h-10 min-w-[220px] rounded-xl border border-[hsl(var(--border))] bg-white px-3 text-sm outline-none"
                          />
                          <input
                            type="file"
                            onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                            className="block min-w-[220px] text-sm text-slate-500 file:mr-3 file:rounded-lg file:border-0 file:bg-white file:px-3 file:py-2"
                          />
                          <Button onClick={saveTextDoc} disabled={saving || !textContent.trim()}>
                            <FileText className="h-4 w-4" />
                            入库整理
                          </Button>
                          <Button onClick={uploadDocument} disabled={saving || !uploadFile} variant="outline">
                            <Upload className="h-4 w-4" />
                            文件入库
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                </WorkbenchSection>

                {requestedDocId ? (
                  <Card className="shadow-none">
                    <CardContent className="space-y-3 p-4">
                      <div className="text-sm font-medium text-slate-900">引用定位</div>
                      {documents
                        .filter((doc) => doc.id === requestedDocId)
                        .map((doc) => (
                          <div key={doc.id} id={`doc-${doc.id}`} className="space-y-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="text-sm font-medium text-slate-900">{doc.title}</div>
                              <Badge variant="outline">{doc.doc_type}</Badge>
                              <Badge variant={statusTone(doc.status) as "success"}>{doc.status}</Badge>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => draftPromptFromReference(doc.title, doc.summary || "", `${doc.doc_type} 文档`)}
                              >
                                基于此提问
                              </Button>
                            </div>
                            <div className="text-sm leading-6 text-slate-600">{doc.summary || "无摘要"}</div>
                            {documentChunks.length > 0 ? (
                              <ScrollArea className="h-[260px] pr-3">
                                <div className="space-y-2">
                                  {documentChunks.map((chunk) => (
                                    <div
                                      key={chunk.id}
                                      id={`chunk-${doc.id}-${chunk.chunk_index}`}
                                      className={
                                        chunk.chunk_index === requestedChunkIndex
                                          ? "rounded-lg border border-[hsl(var(--primary))] bg-blue-50 px-3 py-2 text-xs leading-6 text-slate-700"
                                          : "rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-6 text-slate-600"
                                      }
                                    >
                                      <div className="mb-1 flex items-center justify-between gap-2">
                                        <span className="font-medium text-slate-900">Chunk #{chunk.chunk_index}</span>
                                        <div className="flex items-center gap-2">
                                          <span className="text-[11px] text-slate-400">{chunk.char_count} chars</span>
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="ghost"
                                            className="h-6 px-2 text-[11px]"
                                            onClick={() => draftPromptFromReference(doc.title, chunk.content, `Chunk #${chunk.chunk_index}`)}
                                          >
                                            基于此提问
                                          </Button>
                                        </div>
                                      </div>
                                      <div className="whitespace-pre-wrap">{chunk.content}</div>
                                    </div>
                                  ))}
                                </div>
                              </ScrollArea>
                            ) : (
                              <WorkbenchEmpty title="暂无片段" description="当前引用文档没有可展示的 chunk。" />
                            )}
                          </div>
                        ))}
                    </CardContent>
                  </Card>
                ) : null}
              </div>
            )}
          </div>

          <div className="min-w-0 xl:self-stretch">
            <WorkbenchSection
              title="AI 对话与学习记忆"
              description={knowledgeCollapsed ? "知识库已收起，当前把更多宽度让给右侧。这里继续对话，同时整理最近学到哪里、卡在哪里。" : "右侧保持主对话区，下方补一层学习记忆面板，方便你继续复习和追问。"}
              className="xl:flex xl:h-[calc(100vh-6.5rem)] xl:flex-col"
              actions={
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={() => router.push("/composition")}>
                    <Blocks className="h-4 w-4" />
                    去组合编排
                  </Button>
                  {knowledgeCollapsed ? (
                    <Button variant="outline" onClick={() => setKnowledgeCollapsed(false)}>
                      <ChevronRight className="h-4 w-4" />
                      展开知识库
                    </Button>
                  ) : null}
                </div>
              }
            >
              <div className="grid gap-4 xl:flex-1 xl:min-h-0 xl:grid-rows-[minmax(360px,1fr)_auto]">
                <div className="xl:min-h-0">
                  <AIPanel
                    username={username}
                    workspaceId={workspaceId}
                    workspaceName={workspace?.name}
                    draftPrompt={draftPrompt}
                    onDraftPromptConsumed={() => setDraftPrompt("")}
                    onLearningMemoryCaptured={() =>
                      void refreshLearningMemories(username, {
                        course: memoryCourseFilter,
                        type: memoryTypeFilter,
                        point: memoryPointFilter,
                      })
                    }
                  />
                </div>

                <div className="grid gap-4 rounded-3xl border border-slate-200 bg-slate-50/70 p-4">
                  <div className="grid gap-3 lg:grid-cols-[1.15fr_0.85fr]">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <Brain className="h-4 w-4 text-sky-600" />
                        学习记忆概览
                      </div>
                      <div className="mt-3 grid gap-3 sm:grid-cols-3">
                        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                          <div className="text-xs text-slate-500">总疑问</div>
                          <div className="mt-1 text-lg font-semibold text-slate-900">{learningMemorySummary?.total || 0}</div>
                        </div>
                        <div className="rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3">
                          <div className="text-xs text-slate-500">未解决</div>
                          <div className="mt-1 text-lg font-semibold text-slate-900">{learningMemorySummary?.unresolved || 0}</div>
                        </div>
                        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-3">
                          <div className="text-xs text-slate-500">已解决</div>
                          <div className="mt-1 text-lg font-semibold text-slate-900">{learningMemorySummary?.resolved || 0}</div>
                        </div>
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2">
                        {reviewPointCards.map((point) => (
                          <button
                            key={point}
                            type="button"
                            onClick={() => applyMemoryFilters({
                              course: memoryCourseFilter,
                              type: memoryTypeFilter,
                              point,
                            })}
                          >
                            <Badge variant="secondary">{point}</Badge>
                          </button>
                        ))}
                        {!reviewPointCards.length ? (
                          <span className="text-xs text-slate-500">暂无高频知识点</span>
                        ) : null}
                      </div>
                    </div>

                    <div className="grid gap-3">
                      <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                          <FlagTriangleRight className="h-4 w-4 text-amber-500" />
                          下一步建议
                        </div>
                        <div className="mt-2 text-sm text-slate-700">
                          {nextPriorityMemory ? nextPriorityMemory.question_summary : "继续在对话里追问关键问题，系统会逐步形成复习优先项。"}
                        </div>
                        <div className="mt-2 text-xs leading-6 text-slate-500">
                          {nextPriorityMemory
                            ? `${nextPriorityMemory.course_name || workspace?.name || "当前课程"} · ${formatMemoryTypeLabel(nextPriorityMemory.question_type)}`
                            : "当前还没有足够的疑问沉淀。"}
                        </div>
                        {nextPriorityMemory ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            <Button size="sm" onClick={openPriorityMemoryDraftInPanel}>
                              <Brain className="h-4 w-4" />
                              先在右侧复习
                            </Button>
                            <Button size="sm" variant="outline" onClick={continueWithPrioritySummaryInChat}>
                              <BookOpenCheck className="h-4 w-4" />
                              去聊天页追问
                            </Button>
                          </div>
                        ) : null}
                      </div>

                      <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                          <Sparkles className="h-4 w-4 text-sky-600" />
                          建议排序
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {promptStrategyCards.length ? promptStrategyCards.map((item) => (
                            <Badge key={item.strategy} variant="outline">
                              {item.strategy} · {item.count}
                            </Badge>
                          )) : (
                            <span className="text-xs text-slate-500">暂无偏好统计</span>
                          )}
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-3 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3">
                          <div className="text-xs text-slate-600">本次按默认建议排序</div>
                          <Button
                            type="button"
                            size="sm"
                            variant={preferDefaultPromptSuggestions ? "default" : "outline"}
                            onClick={() => setPreferDefaultPromptSuggestions((prev) => !prev)}
                          >
                            {preferDefaultPromptSuggestions ? "已启用" : "使用默认"}
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">{hasMemoryFilters ? "筛选后的学习疑问" : "最近学习疑问"}</div>
                        <div className="mt-1 text-xs text-slate-500">
                          {hasMemoryFilters
                            ? `课程：${memoryCourseFilter || "全部"} · 类型：${memoryTypeFilter ? formatMemoryTypeLabel(memoryTypeFilter) : "全部"} · 知识点：${memoryPointFilter || "全部"}`
                            : "系统会把有价值的追问沉淀到这里，便于后续复习。"}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" onClick={openFilteredMemoriesDraftInPanel} disabled={!learningMemories.length}>
                          先在右侧复习
                        </Button>
                        <Button size="sm" variant="outline" onClick={continueWithFilteredMemoriesInChat} disabled={!learningMemories.length}>
                          去聊天页追问
                        </Button>
                        {hasMemoryFilters ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => applyMemoryFilters({ course: "", type: "", point: "" })}
                          >
                            清空筛选
                          </Button>
                        ) : null}
                      </div>
                    </div>

                    {hasMemoryFilters ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {memoryCourseFilter ? (
                          <button
                            type="button"
                            onClick={() => applyMemoryFilters({
                              course: "",
                              type: memoryTypeFilter,
                              point: memoryPointFilter,
                            })}
                          >
                            <Badge variant="outline">课程：{memoryCourseFilter} ×</Badge>
                          </button>
                        ) : null}
                        {memoryTypeFilter ? (
                          <button
                            type="button"
                            onClick={() => applyMemoryFilters({
                              course: memoryCourseFilter,
                              type: "",
                              point: memoryPointFilter,
                            })}
                          >
                            <Badge variant="outline">类型：{formatMemoryTypeLabel(memoryTypeFilter)} ×</Badge>
                          </button>
                        ) : null}
                        {memoryPointFilter ? (
                          <button
                            type="button"
                            onClick={() => applyMemoryFilters({
                              course: memoryCourseFilter,
                              type: memoryTypeFilter,
                              point: "",
                            })}
                          >
                            <Badge variant="outline">知识点：{memoryPointFilter} ×</Badge>
                          </button>
                        ) : null}
                      </div>
                    ) : null}

                    {memoryCourseCards.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {memoryCourseCards.map((item) => (
                          <button
                            key={item.course}
                            type="button"
                            onClick={() => applyMemoryFilters({
                              course: memoryCourseFilter === item.course ? "" : item.course,
                              type: memoryTypeFilter,
                              point: memoryPointFilter,
                            })}
                          >
                            <Badge variant={memoryCourseFilter === item.course ? "default" : "secondary"}>
                              {item.course} · {item.count}
                            </Badge>
                          </button>
                        ))}
                      </div>
                    ) : null}

                    {memoryTypeCards.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {memoryTypeCards.map((item) => (
                          <button
                            key={item.key}
                            type="button"
                            onClick={() => applyMemoryFilters({
                              course: memoryCourseFilter,
                              type: memoryTypeFilter === item.key ? "" : item.key,
                              point: memoryPointFilter,
                            })}
                          >
                            <Badge variant={memoryTypeFilter === item.key ? "default" : "secondary"}>
                              {item.label} · {item.count}
                            </Badge>
                          </button>
                        ))}
                      </div>
                    ) : null}

                    <div className="mt-4 grid gap-3">
                      {learningMemories.length ? learningMemories.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => void openMemoryDetail(item)}
                          className={cn(
                            "rounded-2xl border px-4 py-3 text-left transition-colors hover:bg-slate-50",
                            item.status === "resolved" ? "border-slate-200 bg-white" : "border-amber-200 bg-amber-50/60"
                          )}
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-medium text-slate-900">{item.question_summary}</span>
                            <Badge variant={item.status === "resolved" ? "secondary" : "outline"}>
                              {formatMemoryStatusLabel(item.status)}
                            </Badge>
                            <Badge variant="outline">{formatMemoryTypeLabel(item.question_type)}</Badge>
                          </div>
                          <div className="mt-1 text-xs leading-6 text-slate-500">
                            {item.course_name || workspace?.name || "当前课程"}
                            {item.answer_summary ? ` · ${item.answer_summary}` : ""}
                          </div>
                        </button>
                      )) : (
                        <WorkbenchEmpty
                          title="暂无学习疑问沉淀"
                          description="继续在上方对话区问几个关键问题，系统会把有价值的疑问整理到这里。"
                        />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </WorkbenchSection>
          </div>
        </div>
      </div>

      {msg ? (
        <Card className="mt-4 border-slate-200 bg-slate-50 shadow-none">
          <CardContent className="p-4 text-sm text-slate-700">{msg}</CardContent>
        </Card>
      ) : null}

      <ReminderModal
        open={reminderOpen}
        item={reminders[0] || null}
        onOpenChange={setReminderOpen}
        onLater={() => setReminderOpen(false)}
        onAccept={(id) => {
          setReminderOpen(false);
          void handleSuggestionAction(id, "accept");
        }}
        onDismiss={(id) => {
          setReminderOpen(false);
          void handleSuggestionAction(id, "dismiss");
        }}
      />

      <Dialog open={Boolean(selectedMemory)} onOpenChange={(open) => !open && setSelectedMemory(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>学习疑问详情</DialogTitle>
            <DialogDescription>
              {selectedMemory?.course_name || workspace?.name || "当前课程"}
            </DialogDescription>
          </DialogHeader>

          {selectedMemory ? (
            <div className="space-y-4 text-sm text-slate-700">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">问题</div>
                <div className="mt-2 leading-6">{selectedMemory.question_text || selectedMemory.question_summary}</div>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">状态</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge variant={selectedMemory.status === "resolved" ? "secondary" : "outline"}>
                      {formatMemoryStatusLabel(selectedMemory.status)}
                    </Badge>
                    <Badge variant="outline">{formatMemoryTypeLabel(selectedMemory.question_type)}</Badge>
                    {selectedMemory.importance ? (
                      <Badge variant="outline">重要度 {selectedMemory.importance}</Badge>
                    ) : null}
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">知识点</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selectedMemory.knowledge_points.length ? selectedMemory.knowledge_points.map((point) => (
                      <button
                        key={point}
                        type="button"
                        onClick={() => {
                          applyMemoryFilters({
                            course: selectedMemory.course_name || "",
                            type: selectedMemory.question_type || "",
                            point,
                          });
                          setSelectedMemory(null);
                        }}
                      >
                        <Badge variant="secondary">{point}</Badge>
                      </button>
                    )) : (
                      <span className="text-xs text-slate-500">暂无知识点</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">AI 摘要</div>
                <div className="mt-2 leading-6">{selectedMemory.answer_summary || "暂无摘要"}</div>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button onClick={() => openMemoryDraftInPanel(selectedMemory)}>
                  <Brain className="h-4 w-4" />
                  先在右侧复习
                </Button>
                <Button variant="outline" onClick={() => continueWithMemoryInChat(selectedMemory)}>
                  <BookOpenCheck className="h-4 w-4" />
                  去聊天页追问
                </Button>
                <Button
                  variant="outline"
                  onClick={() => void updateMemoryStatus(selectedMemory.id, selectedMemory.status === "resolved" ? "unresolved" : "resolved")}
                >
                  {selectedMemory.status === "resolved" ? "改回未解决" : "标记为已解决"}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    applyMemoryFilters({
                      course: selectedMemory.course_name || "",
                      type: selectedMemory.question_type || "",
                      point: "",
                    });
                    setSelectedMemory(null);
                  }}
                >
                  查看同类问题
                </Button>
              </div>

              {memoryDetailLoading ? (
                <div className="text-xs text-slate-500">正在刷新详情...</div>
              ) : null}
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </WorkbenchShell>
  );
}
