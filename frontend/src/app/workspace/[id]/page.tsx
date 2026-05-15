'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  BookOpenCheck,
  Brain,
  Database,
  FileText,
  FlagTriangleRight,
  Network,
  Upload,
} from "lucide-react";

import { KnowledgeVisualization } from "@/components/knowledge/KnowledgeVisualization";
import { AIPanel } from "@/components/workspace/ai-panel";
import { PlatformSidebarFooter, PlatformSidebarHeader, createPlatformNav } from "@/components/workspace/app-sidebar";
import { ReminderModal } from "@/components/workspace/reminder-modal";
import {
  WorkbenchBadge,
  WorkbenchEmpty,
  WorkbenchSection,
  WorkbenchShell,
} from "@/components/workspace/workbench-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { InlineStatusMessage, PageLoading } from "@/components/ui/feedback";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { getDevPreviewUsername, isDevPreviewEnabled } from "@/lib/dev-preview";

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
    top_source_materials?: Array<{
      title: string;
      source?: string;
      document_id?: number;
      chunk_index?: number;
      hit_count?: number;
    }>;
    course_insights?: Array<{
      course_name: string;
      total: number;
      unresolved: number;
      dominant_type: string;
      dominant_type_count?: number;
    }>;
    overall?: {
      total: number;
      unresolved: number;
      resolved: number;
    };
    scope?: {
      course_name?: string;
      question_type?: string;
      knowledge_point?: string;
      is_filtered?: boolean;
    };
    recommended_followup?: {
      headline: string;
      content: string;
      source_label?: string;
      reason?: string;
      memory_id?: number;
      course_name?: string;
      question_type?: string;
      strategy?: string;
      generated_by?: string;
    } | null;
  };
};

type DraftPromptPayload = {
  id: string;
  content: string;
  sourceLabel?: string;
  headline?: string;
  generatedBy?: string;
};

type WorkspaceModuleKey =
  | "knowledge"
  | "detail"
  | "learningStatus"
  | "suggestions"
  | "learningMemories";

type WorkspaceModuleErrors = Partial<Record<WorkspaceModuleKey, string>>;

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

function getApiErrorMessage(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object") {
    const detail = "detail" in payload ? String((payload as { detail?: unknown }).detail || "").trim() : "";
    if (detail) return detail;
    const message = "message" in payload ? String((payload as { message?: unknown }).message || "").trim() : "";
    if (message) return message;
  }
  return fallback;
}

function summarizeModuleErrors(errors: WorkspaceModuleErrors) {
  const moduleLabels: Record<WorkspaceModuleKey, string> = {
    knowledge: "知识资料",
    detail: "知识图谱",
    learningStatus: "学习状态",
    suggestions: "系统建议",
    learningMemories: "学习记忆",
  };
  return (Object.entries(errors) as Array<[WorkspaceModuleKey, string]>)
    .filter(([, message]) => Boolean(message))
    .map(([key, message]) => `${moduleLabels[key]}：${message}`);
}

export default function WorkspaceDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const workspaceId = Number(params?.id || 0);
  const requestedDocId = Number(searchParams.get("doc") || 0);
  const requestedChunkIndex = Number(searchParams.get("chunk") || 0);
  const requestedRefTitle = (searchParams.get("ref_title") || "").trim();
  const requestedRefSnippet = (searchParams.get("ref_snippet") || "").trim();
  const requestedRefSource = (searchParams.get("ref_source") || "").trim();
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
  const [reminders, setReminders] = useState<SuggestionItem[]>([]);
  const [learningMemories, setLearningMemories] = useState<LearningMemoryItem[]>([]);
  const [learningMemorySummary, setLearningMemorySummary] = useState<LearningMemoryResponse["summary"] | null>(null);
  const [memoryCourseFilter, setMemoryCourseFilter] = useState("");
  const [memoryTypeFilter, setMemoryTypeFilter] = useState("");
  const [memoryPointFilter, setMemoryPointFilter] = useState("");
  const [resolvedMemoriesExpanded, setResolvedMemoriesExpanded] = useState(false);
  const [selectedMemory, setSelectedMemory] = useState<LearningMemoryItem | null>(null);
  const [memoryDetailLoading, setMemoryDetailLoading] = useState(false);
  const [draftPrompt, setDraftPrompt] = useState<DraftPromptPayload | null>(null);
  const [activeReviewContext, setActiveReviewContext] = useState<DraftPromptPayload | null>(null);
  const [reviewContextDismissVersion, setReviewContextDismissVersion] = useState(0);
  const [reminderOpen, setReminderOpen] = useState(false);
  const [textFilename, setTextFilename] = useState("notes.md");
  const [textContent, setTextContent] = useState("");
  const [textAuthority, setTextAuthority] = useState("user");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadAuthority, setUploadAuthority] = useState("user");
  const [msg, setMsg] = useState("");
  const [moduleErrors, setModuleErrors] = useState<WorkspaceModuleErrors>({});
  const [knowledgeStudioOpen, setKnowledgeStudioOpen] = useState(false);
  const [memoryBoardOpen, setMemoryBoardOpen] = useState(false);
  const [referencePreviewOpen, setReferencePreviewOpen] = useState(false);
  const autoReviewSeedRef = useRef("");
  const referencePreviewSeedRef = useRef("");
  const referencePreviewDismissedRef = useRef(false);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const setModuleError = useCallback((key: WorkspaceModuleKey, message: string) => {
    setModuleErrors((prev) => (prev[key] === message ? prev : { ...prev, [key]: message }));
  }, []);

  const clearModuleError = useCallback((key: WorkspaceModuleKey) => {
    setModuleErrors((prev) => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const refreshKnowledge = useCallback(async (uname: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/${encodeURIComponent(uname)}/${workspaceId}`, {
        credentials: "include",
      });
      const json = await res.json().catch(() => null);
      if (!res.ok || !json?.success) {
        setModuleError("knowledge", getApiErrorMessage(json, `加载失败(${res.status})`));
        return;
      }
      clearModuleError("knowledge");
      setWorkspace(json.workspace || null);
      setDocuments(json.documents || []);
    } catch {
      setModuleError("knowledge", "请求失败，请检查网络或登录状态");
    }
  }, [API_BASE, clearModuleError, setModuleError, workspaceId]);

  const refreshDetail = useCallback(async (uname: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}/detail/${workspaceId}`, {
        credentials: "include",
      });
      const json = await res.json().catch(() => null);
      if (!res.ok || !json?.success) {
        setModuleError("detail", getApiErrorMessage(json, `加载失败(${res.status})`));
        return;
      }
      clearModuleError("detail");
      setGraph(json?.graph || null);
    } catch {
      setModuleError("detail", "请求失败，请检查网络或登录状态");
    }
  }, [API_BASE, clearModuleError, setModuleError, workspaceId]);

  const refreshLearningStatus = useCallback(async (uname: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/status/${workspaceId}?username=${encodeURIComponent(uname)}`, {
        credentials: "include",
      });
      const json = await res.json().catch(() => null);
      if (!res.ok || !json?.success) {
        setModuleError("learningStatus", getApiErrorMessage(json, `加载失败(${res.status})`));
        return;
      }
      clearModuleError("learningStatus");
      setLearningStatus(json);
    } catch {
      setModuleError("learningStatus", "请求失败，请检查网络或登录状态");
    }
  }, [API_BASE, clearModuleError, setModuleError, workspaceId]);

  const refreshSuggestions = useCallback(async (uname: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/suggestions/${workspaceId}?username=${encodeURIComponent(uname)}`, {
        credentials: "include",
      });
      const json = await res.json().catch(() => null);
      if (!res.ok || !json?.success) {
        setModuleError("suggestions", getApiErrorMessage(json, `加载失败(${res.status})`));
        return;
      }
      clearModuleError("suggestions");
      setReminders(json.reminders || []);
    } catch {
      setModuleError("suggestions", "请求失败，请检查网络或登录状态");
    }
  }, [API_BASE, clearModuleError, setModuleError, workspaceId]);

  const refreshLearningMemories = useCallback(async (
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
    try {
      const res = await fetch(`${API_BASE}/api/learning-memory/${encodeURIComponent(uname)}?${params.toString()}`, {
        credentials: "include",
      });
      const json = await res.json().catch(() => null);
      if (!res.ok || !json?.success) {
        setModuleError("learningMemories", getApiErrorMessage(json, `加载失败(${res.status})`));
        return;
      }
      clearModuleError("learningMemories");
      setLearningMemories(json.items || []);
      setLearningMemorySummary(json.summary || null);
    } catch {
      setModuleError("learningMemories", "请求失败，请检查网络或登录状态");
    }
  }, [API_BASE, clearModuleError, setModuleError, workspaceId]);

  const refreshLearningLoop = useCallback(async (
    uname: string,
    filters?: { course?: string; type?: string; point?: string }
  ) => {
    await Promise.all([
      refreshLearningMemories(uname, filters),
      refreshLearningStatus(uname),
      refreshSuggestions(uname),
    ]);
  }, [refreshLearningMemories, refreshLearningStatus, refreshSuggestions]);

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

  const refreshDocumentChunks = useCallback(async (uname: string, documentId: number) => {
    const res = await fetch(`${API_BASE}/api/knowledge/${encodeURIComponent(uname)}/${workspaceId}/documents/${documentId}/chunks`, {
      credentials: "include",
    });
    const json = res.ok ? await res.json() : null;
    setDocumentChunks(json?.chunks || []);
  }, [API_BASE, workspaceId]);

  useEffect(() => {
    const run = async () => {
      if (isDevPreviewEnabled()) {
        const previewWorkspace: WorkspaceItem = {
          id: workspaceId,
          slug: `workspace-${workspaceId}`,
          name: `预览工作区 #${workspaceId}`,
          description: "开发预览模式：当前页面展示结构与空态，不依赖真实登录和接口数据。",
          is_default: workspaceId === 1,
        };
        setUsername(getDevPreviewUsername());
        setWorkspace(previewWorkspace);
        setDocuments([]);
        setGraph({
          workspace: { id: previewWorkspace.id, name: previewWorkspace.name, slug: previewWorkspace.slug },
          nodes: [],
          edges: [],
        });
        setLearningStatus(null);
        setReminders([]);
        setLearningMemories([]);
        setLearningMemorySummary(null);
        setDocumentChunks([]);
        setLoading(false);
        return;
      }

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
          refreshLearningLoop(uname),
        ]);
      } catch {
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    };

    if (!workspaceId) {
      router.replace("/workspace");
      return;
    }
    run();
  }, [API_BASE, refreshDetail, refreshKnowledge, refreshLearningLoop, router, workspaceId]);

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

  const moduleErrorSummary = useMemo(() => summarizeModuleErrors(moduleErrors), [moduleErrors]);
  const requestedDocument = useMemo(
    () => documents.find((doc) => doc.id === requestedDocId) || null,
    [documents, requestedDocId]
  );
  const requestedChunk = useMemo(
    () => documentChunks.find((chunk) => chunk.chunk_index === requestedChunkIndex) || null,
    [documentChunks, requestedChunkIndex]
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
  const topSourceMaterialCards = useMemo(
    () => (learningMemorySummary?.top_source_materials || []).slice(0, 4),
    [learningMemorySummary]
  );
  const courseInsightCards = useMemo(
    () => (learningMemorySummary?.course_insights || []).slice(0, 4),
    [learningMemorySummary]
  );

  const primaryPromptStrategy = promptStrategyCards[0]?.strategy || "";
  const hasMemoryFilters = Boolean(memoryCourseFilter || memoryTypeFilter || memoryPointFilter);
  const nextPriorityMemory = reviewPriorityItems[0] || null;
  const recommendedFollowup = learningMemorySummary?.recommended_followup || null;
  const hasActiveReviewContext = Boolean(activeReviewContext?.content?.trim());
  const unresolvedLearningMemories = useMemo(
    () => learningMemories.filter((item) => item.status !== "resolved"),
    [learningMemories]
  );
  const resolvedLearningMemories = useMemo(
    () => learningMemories.filter((item) => item.status === "resolved"),
    [learningMemories]
  );
  const resolvePromptStrategyForChat = () => {
    return primaryPromptStrategy;
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
    setDraftPrompt({
      id: `memory:${memory.id}:${Date.now()}`,
      content: prompt,
      sourceLabel: "学习疑问",
      headline: memory.question_summary || memory.question_text,
    });
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
    setDraftPrompt({
      id: `memory-filter:${Date.now()}`,
      content: prompt,
      sourceLabel: hasMemoryFilters ? "筛选后的学习疑问" : "最近学习疑问",
      headline: focusText || "围绕当前筛选出的学习疑问继续复习",
    });
  };

  const openPriorityMemoryDraftInPanel = () => {
    if (!nextPriorityMemory) return;
    const prompt = [
      `请围绕这个高优先级学习疑问继续辅导我：${nextPriorityMemory.question_summary}`,
      nextPriorityMemory.course_name ? `课程：${nextPriorityMemory.course_name}` : "",
      `问题类型：${formatMemoryTypeLabel(nextPriorityMemory.question_type)}`,
      "请先帮我判断我最可能卡在哪一层，再给我当前工作区里最适合直接继续问的一句追问。",
    ].filter(Boolean).join("\n");
    setDraftPrompt({
      id: `memory-priority:${nextPriorityMemory.id}:${Date.now()}`,
      content: prompt,
      sourceLabel: "高优先级学习疑问",
      headline: nextPriorityMemory.question_summary,
    });
  };

  const openRecommendedFollowupInPanel = () => {
    if (!recommendedFollowup?.content?.trim()) return;
    setDraftPrompt({
      id: `memory-followup:${recommendedFollowup.memory_id || "scoped"}:${Date.now()}`,
      content: recommendedFollowup.content,
      sourceLabel: recommendedFollowup.source_label || "系统建议追问",
      headline: recommendedFollowup.headline || "系统建议追问",
      generatedBy: recommendedFollowup.generated_by || "",
    });
  };

  const openCourseInsightDraftInPanel = (course: {
    course_name: string;
    unresolved: number;
    dominant_type: string;
  }) => {
    const prompt = [
      `请围绕这门课当前最集中的学习卡点继续辅导我：${course.course_name}`,
      `未解决疑问数量：${course.unresolved}`,
      `当前最常见的问题类型：${formatMemoryTypeLabel(course.dominant_type)}`,
      "请先判断我为什么会反复卡在这里，再给我一个最适合继续发给工作区 AI 的具体追问。",
    ].join("\n\n");
    setDraftPrompt({
      id: `course-insight:${course.course_name}:${Date.now()}`,
      content: prompt,
      sourceLabel: "课程洞察",
      headline: `${course.course_name} 的下一步复习入口`,
    });
  };

  const openSourceMaterialDraftInPanel = (material: {
    title: string;
    hit_count?: number;
  }) => {
    const prompt = [
      `我想回到这份高频被引用的资料继续复习：${material.title}`,
      typeof material.hit_count === "number" ? `它在最近学习疑问中被引用了 ${material.hit_count} 次。` : "",
      "请先告诉我这份资料最值得重新看的部分是什么，再给我一个可以直接继续追问的问题。",
    ].filter(Boolean).join("\n\n");
    setDraftPrompt({
      id: `source-material:${material.title}:${Date.now()}`,
      content: prompt,
      sourceLabel: "高频引用资料",
      headline: material.title,
    });
  };

  const draftPromptFromReference = (title: string, snippet: string, sourceLabel: string) => {
    const prompt = [
      `我正在看资料《${title}》`,
      snippet ? `对应片段：${snippet}` : "",
      sourceLabel ? `来源：${sourceLabel}` : "",
      "请基于这段内容帮我提炼出我应该追问的关键问题，并直接给我最短的追问方式。",
    ].filter(Boolean).join("\n\n");
    setDraftPrompt({
      id: `reference:${title}:${Date.now()}`,
      content: prompt,
      sourceLabel: sourceLabel || "知识片段",
      headline: title,
    });
  };

  const clearActiveReviewContext = () => {
    setDraftPrompt(null);
    setActiveReviewContext(null);
    setReviewContextDismissVersion((prev) => prev + 1);
  };

  const focusReviewPanel = () => {
    const panel = document.getElementById("workspace-ai-panel");
    panel?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const openPrimaryReviewEntry = () => {
    if (hasActiveReviewContext) {
      focusReviewPanel();
      return;
    }
    if (recommendedFollowup?.content?.trim()) {
      openRecommendedFollowupInPanel();
      return;
    }
    if (nextPriorityMemory) {
      openPriorityMemoryDraftInPanel();
      return;
    }
    if (learningMemories.length) {
      openFilteredMemoriesDraftInPanel();
      return;
    }
    focusReviewPanel();
  };

  const primaryReviewEntryLabel = hasActiveReviewContext
    ? "继续当前复习"
    : recommendedFollowup?.content?.trim()
      ? "打开系统建议追问"
    : nextPriorityMemory
      ? "开始本轮复习"
      : learningMemories.length
        ? "围绕学习疑问复习"
        : "去右侧开始提问";

  useEffect(() => {
    const seed = [requestedRefTitle, requestedRefSnippet, requestedRefSource, requestedDocId, requestedChunkIndex].join("|");
    if (!seed.replace(/\|/g, "").trim()) return;
    if (seed !== referencePreviewSeedRef.current) {
      referencePreviewSeedRef.current = seed;
      referencePreviewDismissedRef.current = false;
    }
    if (!requestedDocument || referencePreviewDismissedRef.current) return;
    setReferencePreviewOpen(true);
    const node = document.getElementById(`doc-${requestedDocId}`);
    if (!node) return;
    const timer = window.setTimeout(() => {
      node.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [requestedChunkIndex, requestedDocId, requestedDocument, requestedRefSnippet, requestedRefSource, requestedRefTitle]);

  useEffect(() => {
    if (!username || !requestedDocId) {
      setDocumentChunks([]);
      return;
    }
    void refreshDocumentChunks(username, requestedDocId);
  }, [refreshDocumentChunks, requestedDocId, username]);

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
  }, [memoryCourseFilter, memoryPointFilter, memoryTypeFilter, refreshLearningMemories, username, workspaceId]);

  useEffect(() => {
    if (!workspaceId) return;
    if (!requestedMemoryCourse && !requestedMemoryPoint && !requestedMemoryType) return;
    setMemoryCourseFilter(requestedMemoryCourse);
    setMemoryPointFilter(requestedMemoryPoint);
    setMemoryTypeFilter(requestedMemoryType);
  }, [requestedMemoryCourse, requestedMemoryPoint, requestedMemoryType, workspaceId]);

  useEffect(() => {
    if (unresolvedLearningMemories.length === 0 && resolvedLearningMemories.length > 0) {
      setResolvedMemoriesExpanded(true);
    }
  }, [resolvedLearningMemories.length, unresolvedLearningMemories.length]);

  useEffect(() => {
    const seed = [requestedMemoryCourse, requestedMemoryPoint, requestedMemoryType].join("|");
    if (!seed.replace(/\|/g, "").trim()) return;
    if (!recommendedFollowup?.content?.trim()) return;
    if (autoReviewSeedRef.current === seed) return;
    autoReviewSeedRef.current = seed;
    setDraftPrompt({
      id: `auto-followup:${seed}:${Date.now()}`,
      content: recommendedFollowup.content,
      sourceLabel: recommendedFollowup.source_label || "系统建议追问",
      headline: recommendedFollowup.headline || "系统建议追问",
      generatedBy: recommendedFollowup.generated_by || "",
    });
  }, [
    recommendedFollowup,
    requestedMemoryCourse,
    requestedMemoryPoint,
    requestedMemoryType,
  ]);

  useEffect(() => {
    const seed = [requestedRefTitle, requestedRefSnippet, requestedRefSource, requestedDocId, requestedChunkIndex].join("|");
    if (!seed.replace(/\|/g, "").trim()) return;
    if (autoReviewSeedRef.current === seed) return;
    autoReviewSeedRef.current = seed;
    const title = requestedRefTitle || requestedDocument?.title || "当前资料";
    const snippet = requestedRefSnippet || requestedChunk?.content || "";
    setDraftPrompt({
      id: `reference-followup:${seed}:${Date.now()}`,
      content: [
        `我正在看资料《${title}》`,
        snippet ? `对应片段：${snippet}` : "",
        requestedRefSource ? `来源：${requestedRefSource}` : "",
        "请基于这段内容先判断我最应该继续追问的关键点，再直接给我一句可以发给工作区 AI 的追问。",
      ].filter(Boolean).join("\n\n"),
      sourceLabel: requestedRefSource || "知识片段",
      headline: title,
    });
  }, [
    requestedChunkIndex,
    requestedDocId,
    requestedChunk,
    requestedDocument,
    requestedRefSnippet,
    requestedRefSource,
    requestedRefTitle,
  ]);

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

  if (loading) return <PageLoading label="正在加载工作区详情..." />;

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
          <Button
            variant="outline"
            className="border-slate-300 bg-white/90 text-slate-700 hover:bg-slate-50"
            onClick={() => router.push("/workspace")}
          >
            工作区列表
          </Button>
          <Button className="bg-blue-600 shadow-[0_14px_30px_rgba(31,111,235,0.22)] hover:bg-blue-700" onClick={() => router.push(`/workspace/${workspaceId}`)}>
            工作区对话
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        {moduleErrorSummary.length ? (
          <InlineStatusMessage tone="warning">
            当前工作区有部分数据未成功加载：{moduleErrorSummary.join("；")}。其余模块仍可继续使用。
          </InlineStatusMessage>
        ) : null}
        <div className="rounded-[1.65rem] border border-slate-200/90 bg-[linear-gradient(135deg,rgba(255,255,255,0.96),rgba(244,248,252,0.94)_52%,rgba(239,246,255,0.9))] px-5 py-5 shadow-[0_18px_44px_rgba(15,23,42,0.05)]">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{workspace?.is_default ? "默认工作区" : "当前工作区"}</Badge>
                <Badge variant="outline">{stats.documents} 份资料</Badge>
                <Badge variant="outline">{learningMemorySummary?.unresolved || 0} 条未解决</Badge>
                {learningStatus ? <Badge variant="secondary">今日 {learningStatus.metrics.today_minutes} 分钟</Badge> : null}
              </div>
              <div className="max-w-3xl">
                <div className="text-lg font-semibold text-slate-950">工作区详情页现在只服务一件事：把大部分空间让给当前复习对话。</div>
                <div className="mt-2 text-sm leading-6 text-slate-600">
                  资料整理、引用回看、学习记忆都保留，但统一收进左侧控制带和弹层工作台，避免把主画面切碎。
                </div>
              </div>
              {hasActiveReviewContext ? (
                <div className="rounded-2xl border border-sky-200 bg-sky-50/85 px-4 py-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <Brain className="h-4 w-4 text-sky-600" />
                        当前复习会话
                      </div>
                      <div className="mt-1 text-sm text-slate-700">
                        {activeReviewContext?.headline || "AI 面板正在围绕当前资料或学习疑问继续辅导。"}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={focusReviewPanel}>
                        回到输入
                      </Button>
                      <Button size="sm" variant="ghost" onClick={clearActiveReviewContext}>
                        结束当前复习
                      </Button>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-2 xl:max-w-[420px] xl:justify-end">
              <Button onClick={openPrimaryReviewEntry}>
                <Brain className="h-4 w-4" />
                {primaryReviewEntryLabel}
              </Button>
              <Button variant="outline" onClick={() => setMemoryBoardOpen(true)}>
                <BookOpenCheck className="h-4 w-4" />
                学习记忆
              </Button>
              <Button variant="outline" onClick={() => setKnowledgeStudioOpen(true)}>
                <Network className="h-4 w-4" />
                知识工作台
              </Button>
            </div>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)] 2xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="grid gap-4 xl:sticky xl:top-6 xl:self-start">
            <Card className="border-slate-200/90 bg-white/96 shadow-[0_12px_34px_rgba(15,23,42,0.04)]">
              <CardContent className="space-y-4 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">工作区控制塔</div>
                    <div className="mt-1 text-xs leading-6 text-slate-500">
                      这里只保留工作区的关键入口。详细内容统一放到弹层里打开，避免和主对话区抢空间。
                    </div>
                  </div>
                  <Badge variant="outline">精简模式</Badge>
                </div>

                <div className="space-y-3">
                  <button
                    type="button"
                    onClick={() => setKnowledgeStudioOpen(true)}
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-left transition-colors hover:bg-slate-100"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                          <Database className="h-4 w-4 text-slate-600" />
                          知识工作台
                        </div>
                        <div className="mt-1 text-xs leading-6 text-slate-500">
                          文档 {stats.documents} · 节点 {stats.nodes} · 关系 {stats.edges}
                        </div>
                      </div>
                      <Badge variant="outline">{stats.documents} docs</Badge>
                    </div>
                  </button>

                  {moduleErrors.knowledge || moduleErrors.detail ? (
                    <InlineStatusMessage tone="warning">
                      {[moduleErrors.knowledge, moduleErrors.detail].filter(Boolean).join("；")}
                    </InlineStatusMessage>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => requestedDocId && setReferencePreviewOpen(true)}
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-left transition-colors hover:bg-slate-100 disabled:cursor-not-allowed"
                    disabled={!requestedDocId}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                          <FileText className="h-4 w-4 text-slate-600" />
                          引用预览
                        </div>
                        <div className="mt-1 text-xs leading-6 text-slate-500">
                          {requestedDocId
                            ? documents.find((doc) => doc.id === requestedDocId)?.title || `文档 #${requestedDocId}`
                            : "当前没有从聊天或知识页带入的引用文档"}
                        </div>
                      </div>
                      <Badge variant={requestedDocId ? "secondary" : "outline"}>
                        {requestedDocId ? "已定位" : "未指定"}
                      </Badge>
                    </div>
                  </button>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button className="flex-1" onClick={() => setKnowledgeStudioOpen(true)}>
                    <Network className="h-4 w-4" />
                    打开知识工作台
                  </Button>
                  <Button variant="outline" className="flex-1" onClick={() => router.push(`/knowledge?workspace_id=${workspaceId}`)}>
                    全屏知识页
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card className="border-slate-200/90 bg-white/96 shadow-[0_12px_34px_rgba(15,23,42,0.04)]">
              <CardContent className="space-y-4 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                      <FlagTriangleRight className="h-4 w-4 text-amber-500" />
                      复习控制
                    </div>
                    <div className="mt-2 text-sm text-slate-700">
                      {recommendedFollowup?.headline
                        ? recommendedFollowup.headline
                        : nextPriorityMemory
                        ? nextPriorityMemory.question_summary
                        : "先在主对话区持续追问，系统会逐步形成更明确的复习优先项。"}
                    </div>
                    <div className="mt-2 text-xs leading-6 text-slate-500">
                      {recommendedFollowup?.reason
                        ? recommendedFollowup.reason
                        : nextPriorityMemory
                        ? `${nextPriorityMemory.course_name || workspace?.name || "当前课程"} · ${formatMemoryTypeLabel(nextPriorityMemory.question_type)}`
                        : "当前还没有足够的疑问沉淀。"}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3 xl:grid-cols-1">
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

                {moduleErrors.learningMemories || moduleErrors.suggestions || moduleErrors.learningStatus ? (
                  <InlineStatusMessage tone="warning">
                    {[moduleErrors.learningMemories, moduleErrors.suggestions, moduleErrors.learningStatus].filter(Boolean).join("；")}
                  </InlineStatusMessage>
                ) : null}

                <div className="flex flex-wrap gap-2">
                  {recommendedFollowup?.content?.trim() ? (
                    <Button size="sm" onClick={openRecommendedFollowupInPanel}>
                      <Brain className="h-4 w-4" />
                      打开系统追问
                    </Button>
                  ) : nextPriorityMemory ? (
                    <Button size="sm" onClick={openPriorityMemoryDraftInPanel}>
                      <Brain className="h-4 w-4" />
                      切到这条疑问
                    </Button>
                  ) : null}
                    <Button size="sm" variant="outline" onClick={() => setMemoryBoardOpen(true)}>
                      查看记忆面板
                    </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          <WorkbenchSection
            title="当前工作区对话"
            description="右侧是主工作面。先在这里持续追问，只有确实需要资料明细或疑问清单时，再回左侧展开。"
            className="overflow-hidden"
          >
            <div className="min-w-0">
              <AIPanel
                username={username}
                workspaceId={workspaceId}
                workspaceName={workspace?.name}
                draftPrompt={draftPrompt}
                promptStrategy={resolvePromptStrategyForChat()}
                onDraftPromptConsumed={() => setDraftPrompt(null)}
                onDraftPromptCleared={() => setDraftPrompt(null)}
                onActiveReviewContextChange={setActiveReviewContext}
                reviewContextDismissVersion={reviewContextDismissVersion}
                onLearningMemoryCaptured={() =>
                  void refreshLearningLoop(username, {
                    course: memoryCourseFilter,
                    type: memoryTypeFilter,
                    point: memoryPointFilter,
                  })
                }
              />
            </div>
          </WorkbenchSection>

        </div>
      </div>

      {msg ? <InlineStatusMessage className="mt-4">{msg}</InlineStatusMessage> : null}

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

      <Dialog open={knowledgeStudioOpen} onOpenChange={setKnowledgeStudioOpen}>
        <DialogContent className="max-w-6xl border-slate-200 bg-white p-0">
          <DialogHeader className="border-b border-slate-200 px-6 pb-5 pt-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <DialogTitle className="text-xl font-semibold tracking-[-0.03em] text-slate-950">知识工作台</DialogTitle>
                <DialogDescription className="text-sm leading-6 text-slate-600">
                  这里集中处理知识可视化、文本入库和文件上传，不再常驻占用工作区主画面。
                </DialogDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => router.push(`/knowledge?workspace_id=${workspaceId}`)}>
                  <Network className="h-4 w-4" />
                  全屏知识页
                </Button>
              </div>
            </div>
          </DialogHeader>
          <div className="grid gap-5 px-6 pb-6 pt-5 lg:grid-cols-[1.2fr_0.8fr]">
            {moduleErrors.knowledge || moduleErrors.detail ? (
              <div className="lg:col-span-2">
                <InlineStatusMessage tone="warning">
                  {[moduleErrors.knowledge, moduleErrors.detail].filter(Boolean).join("；")}
                </InlineStatusMessage>
              </div>
            ) : null}
            <ScrollArea className="max-h-[70vh] rounded-[1.4rem] border border-slate-200/90 bg-[linear-gradient(180deg,rgba(248,250,252,0.92),rgba(241,245,249,0.88))] p-4">
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

              <Card className="border-dashed border-slate-300 bg-[linear-gradient(180deg,rgba(248,250,252,0.94),rgba(255,255,255,0.96))] shadow-none">
                <CardContent className="space-y-4 p-4">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Knowledge Intake</div>
                    <div className="mt-1 text-sm font-medium text-slate-900">输入文本或选择文件</div>
                  </div>
                  <Textarea
                    value={textContent}
                    onChange={(e) => setTextContent(e.target.value)}
                    className="min-h-40 border-slate-200 bg-white shadow-none"
                    placeholder="在这里直接输入内容，或者下方选择文件后上传。"
                  />
                  <input
                    type="text"
                    value={textFilename}
                    onChange={(e) => setTextFilename(e.target.value)}
                    placeholder="notes.md"
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none"
                  />
                  <input
                    type="file"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="block w-full text-sm text-slate-500 file:mr-3 file:rounded-lg file:border-0 file:bg-white file:px-3 file:py-2"
                  />
                  <div className="flex flex-wrap gap-3">
                    <Button onClick={saveTextDoc} disabled={saving || !textContent.trim()}>
                      <FileText className="h-4 w-4" />
                      入库整理
                    </Button>
                    <Button onClick={uploadDocument} disabled={saving || !uploadFile} variant="outline">
                      <Upload className="h-4 w-4" />
                      文件入库
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={referencePreviewOpen}
        onOpenChange={(open) => {
          setReferencePreviewOpen(open);
          if (!open) {
            referencePreviewDismissedRef.current = true;
          }
        }}
      >
        <DialogContent className="max-w-4xl border-slate-200 bg-white p-0">
          <DialogHeader className="border-b border-slate-200 px-6 pb-5 pt-6">
            <div className="space-y-2">
              <DialogTitle className="text-xl font-semibold tracking-[-0.03em] text-slate-950">引用预览</DialogTitle>
              <DialogDescription className="text-sm leading-6 text-slate-600">
                从聊天来源或知识页带入的资料会在这里展开，方便基于片段继续追问。
              </DialogDescription>
            </div>
          </DialogHeader>
          <div className="px-6 pb-6 pt-5">
            {requestedDocId ? (
              documents
                .filter((doc) => doc.id === requestedDocId)
                .map((doc) => (
                  <div key={doc.id} id={`doc-${doc.id}`} className="space-y-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-base font-semibold text-slate-900">{doc.title}</div>
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
                      <ScrollArea className="h-[420px] pr-3">
                        <div className="space-y-2">
                          {documentChunks.map((chunk) => (
                            <div
                              key={chunk.id}
                              id={`chunk-${doc.id}-${chunk.chunk_index}`}
                              className={
                                chunk.chunk_index === requestedChunkIndex
                                  ? "rounded-xl border border-blue-200 bg-blue-50/80 px-3 py-2 text-xs leading-6 text-slate-700"
                                  : "rounded-xl border border-slate-200 bg-slate-50/85 px-3 py-2 text-xs leading-6 text-slate-600"
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
                ))
            ) : (
              <WorkbenchEmpty title="暂无引用文档" description="后续从聊天引用或知识页跳入时，这里会自动带上对应文档和片段。" />
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={memoryBoardOpen} onOpenChange={setMemoryBoardOpen}>
        <DialogContent className="max-w-5xl border-slate-200 bg-white p-0">
          <DialogHeader className="border-b border-slate-200 px-6 pb-5 pt-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <DialogTitle className="text-xl font-semibold tracking-[-0.03em] text-slate-950">学习记忆面板</DialogTitle>
                <DialogDescription className="text-sm leading-6 text-slate-600">
                  把最近的学习疑问、筛选入口和已解决记录集中在这里，避免把主画面切碎。
                </DialogDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={openFilteredMemoriesDraftInPanel} disabled={!learningMemories.length}>
                  按当前筛选复习
                </Button>
                <Button size="sm" variant="secondary" onClick={openRecommendedFollowupInPanel} disabled={!recommendedFollowup?.content?.trim()}>
                  系统建议追问
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    openFilteredMemoriesDraftInPanel();
                    focusReviewPanel();
                  }}
                  disabled={!learningMemories.length}
                >
                  定位到右侧复习
                </Button>
              </div>
            </div>
          </DialogHeader>
          <div className="space-y-5 px-6 pb-6 pt-5">
              {moduleErrors.learningMemories || moduleErrors.suggestions ? (
                <InlineStatusMessage tone="warning">
                  {[moduleErrors.learningMemories, moduleErrors.suggestions].filter(Boolean).join("；")}
                </InlineStatusMessage>
              ) : null}
              <Card className="border-slate-200 bg-slate-50/50 shadow-none">
                <CardContent className="space-y-4 p-4">
                  {recommendedFollowup?.content?.trim() ? (
                    <div className="rounded-2xl border border-sky-200 bg-sky-50/70 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-slate-900">系统建议的下一句追问</div>
                          <div className="mt-1 text-xs leading-6 text-slate-500">
                            {recommendedFollowup.reason || "根据当前筛选范围里的未解决学习疑问自动生成。"}
                          </div>
                        </div>
                        <Button size="sm" onClick={openRecommendedFollowupInPanel}>
                          去右侧提问
                        </Button>
                      </div>
                      <div className="mt-3 rounded-xl border border-white/80 bg-white/85 px-3 py-3 text-sm leading-6 text-slate-700">
                        {recommendedFollowup.headline}
                      </div>
                    </div>
                  ) : null}
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Brain className="h-4 w-4 text-sky-600" />
                  高频知识点
                </div>
                <div className="flex flex-wrap gap-2">
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
                  {!reviewPointCards.length ? <span className="text-xs text-slate-500">暂无高频知识点</span> : null}
                </div>

                {hasMemoryFilters ? (
                  <div className="flex flex-wrap gap-2">
                    {memoryCourseFilter ? (
                      <button
                        type="button"
                        onClick={() => applyMemoryFilters({ course: "", type: memoryTypeFilter, point: memoryPointFilter })}
                      >
                        <Badge variant="outline">课程：{memoryCourseFilter} ×</Badge>
                      </button>
                    ) : null}
                    {memoryTypeFilter ? (
                      <button
                        type="button"
                        onClick={() => applyMemoryFilters({ course: memoryCourseFilter, type: "", point: memoryPointFilter })}
                      >
                        <Badge variant="outline">类型：{formatMemoryTypeLabel(memoryTypeFilter)} ×</Badge>
                      </button>
                    ) : null}
                    {memoryPointFilter ? (
                      <button
                        type="button"
                        onClick={() => applyMemoryFilters({ course: memoryCourseFilter, type: memoryTypeFilter, point: "" })}
                      >
                        <Badge variant="outline">知识点：{memoryPointFilter} ×</Badge>
                      </button>
                    ) : null}
                    <Button size="sm" variant="ghost" onClick={() => applyMemoryFilters({ course: "", type: "", point: "" })}>
                      清空筛选
                    </Button>
                  </div>
                ) : null}

                {memoryCourseCards.length ? (
                  <div className="flex flex-wrap gap-2">
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
                  <div className="flex flex-wrap gap-2">
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

                {courseInsightCards.length ? (
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-slate-500">课程洞察</div>
                    <div className="grid gap-2">
                      {courseInsightCards.map((item) => (
                        <button
                          key={`${item.course_name}-${item.dominant_type}`}
                          type="button"
                          onClick={() => openCourseInsightDraftInPanel(item)}
                          className="rounded-2xl border border-slate-200 bg-white px-3 py-3 text-left transition-colors hover:bg-slate-50"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="text-sm font-medium text-slate-900">{item.course_name}</span>
                            <Badge variant="outline">{item.unresolved} 条未解决</Badge>
                          </div>
                          <div className="mt-1 text-xs leading-6 text-slate-500">
                            高频问题类型：{formatMemoryTypeLabel(item.dominant_type)}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}

                {topSourceMaterialCards.length ? (
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-slate-500">高频引用资料</div>
                    <div className="grid gap-2">
                      {topSourceMaterialCards.map((item) => (
                        <button
                          key={`${item.document_id || item.title}-${item.chunk_index || 0}`}
                          type="button"
                          onClick={() => openSourceMaterialDraftInPanel(item)}
                          className="rounded-2xl border border-slate-200 bg-white px-3 py-3 text-left transition-colors hover:bg-slate-50"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="text-sm font-medium text-slate-900">{item.title}</span>
                            <Badge variant="secondary">{item.hit_count || 0} 次</Badge>
                          </div>
                          <div className="mt-1 text-xs leading-6 text-slate-500">
                            从这份资料继续追问，通常比重新从空白提问更直接。
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card className="border-amber-200 bg-amber-50/50 shadow-none">
              <CardContent className="space-y-4 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-slate-900">优先清掉的未解决问题</div>
                  <Badge variant="outline">{unresolvedLearningMemories.length} 条</Badge>
                </div>
                {unresolvedLearningMemories.length ? (
                  <div className="grid gap-3">
                    {unresolvedLearningMemories.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => void openMemoryDetail(item)}
                        className="rounded-2xl border border-amber-200 bg-white px-4 py-3 text-left transition-colors hover:bg-amber-50/40"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium text-slate-900">{item.question_summary}</span>
                          <Badge variant="outline">{formatMemoryStatusLabel(item.status)}</Badge>
                          <Badge variant="outline">{formatMemoryTypeLabel(item.question_type)}</Badge>
                        </div>
                        <div className="mt-1 text-xs leading-6 text-slate-500">
                          {item.course_name || workspace?.name || "当前课程"}
                          {item.answer_summary ? ` · ${item.answer_summary}` : ""}
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-emerald-200 bg-emerald-50/60 px-4 py-4 text-xs leading-6 text-emerald-800">
                    当前筛选下没有未解决问题，可以继续查阅已解决记录，或者回到主对话区继续发起新的追问。
                  </div>
                )}
              </CardContent>
            </Card>

            {resolvedLearningMemories.length ? (
              <Card className="border-slate-200 bg-slate-50/50 shadow-none">
                <CardContent className="space-y-4 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-900">已解决记录</div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">{resolvedLearningMemories.length} 条</Badge>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setResolvedMemoriesExpanded((prev) => !prev)}
                      >
                        {resolvedMemoriesExpanded ? "收起" : "展开"}
                      </Button>
                    </div>
                  </div>
                  {resolvedMemoriesExpanded ? (
                    <div className="grid gap-3">
                      {resolvedLearningMemories.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => void openMemoryDetail(item)}
                          className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left transition-colors hover:bg-slate-50"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-medium text-slate-900">{item.question_summary}</span>
                            <Badge variant="secondary">{formatMemoryStatusLabel(item.status)}</Badge>
                            <Badge variant="outline">{formatMemoryTypeLabel(item.question_type)}</Badge>
                          </div>
                          <div className="mt-1 text-xs leading-6 text-slate-500">
                            {item.course_name || workspace?.name || "当前课程"}
                            {item.answer_summary ? ` · ${item.answer_summary}` : ""}
                          </div>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs leading-6 text-slate-500">
                      已解决的问题默认收起，避免稀释当前复习重点。需要回顾时再展开查看。
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : null}

            {!learningMemories.length ? (
              <WorkbenchEmpty title="暂无学习疑问沉淀" description="继续在主对话区问几个关键问题，系统会把有价值的疑问整理到这里。" />
            ) : null}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(selectedMemory)} onOpenChange={(open) => !open && setSelectedMemory(null)}>
        <DialogContent className="max-w-3xl border-slate-200 bg-white p-0">
          <DialogHeader>
            <div className="border-b border-slate-200 px-6 pb-5 pt-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-2">
                  <DialogTitle className="text-xl font-semibold tracking-[-0.03em] text-slate-950">学习疑问详情</DialogTitle>
                  <DialogDescription className="text-sm leading-6 text-slate-600">
                    {selectedMemory?.course_name || workspace?.name || "当前课程"}
                  </DialogDescription>
                </div>
                {selectedMemory ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={selectedMemory.status === "resolved" ? "secondary" : "outline"}>
                      {formatMemoryStatusLabel(selectedMemory.status)}
                    </Badge>
                    <Badge variant="outline">{formatMemoryTypeLabel(selectedMemory.question_type)}</Badge>
                    {selectedMemory.importance ? (
                      <Badge variant="outline">重要度 {selectedMemory.importance}</Badge>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          </DialogHeader>

          {selectedMemory ? (
            <div className="space-y-5 px-6 pb-6 text-sm text-slate-700">
              <div className="rounded-3xl border border-sky-200 bg-sky-50/80 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 space-y-2">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">优先动作</div>
                    <div className="text-base font-semibold text-slate-950">
                      {selectedMemory.question_summary || selectedMemory.question_text}
                    </div>
                    <div className="text-sm leading-6 text-slate-600">
                      先把这条疑问带到右侧继续复习，再决定是否标记为已解决或查看同类问题。
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => openMemoryDraftInPanel(selectedMemory)}>
                      <Brain className="h-4 w-4" />
                      切到这条疑问
                    </Button>
                    <Button
                      variant={selectedMemory.status === "resolved" ? "outline" : "secondary"}
                      onClick={() => void updateMemoryStatus(selectedMemory.id, selectedMemory.status === "resolved" ? "unresolved" : "resolved")}
                    >
                      {selectedMemory.status === "resolved" ? "改回未解决" : "标记为已解决"}
                    </Button>
                  </div>
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
                <div className="space-y-4">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">问题原文</div>
                    <div className="mt-2 text-sm leading-7 text-slate-800">
                      {selectedMemory.question_text || selectedMemory.question_summary}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">AI 摘要</div>
                      {memoryDetailLoading ? (
                        <span className="text-xs text-slate-500">正在刷新详情...</span>
                      ) : null}
                    </div>
                    <div className="mt-2 text-sm leading-7 text-slate-700">
                      {selectedMemory.answer_summary || "暂无摘要"}
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">知识点</div>
                    <div className="mt-3 flex flex-wrap gap-2">
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

                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">后续分流</div>
                    <div className="mt-3 space-y-3">
                      <Button
                        variant="outline"
                        className="w-full justify-start"
                        onClick={() => {
                          openMemoryDraftInPanel(selectedMemory);
                          focusReviewPanel();
                        }}
                      >
                        <BookOpenCheck className="h-4 w-4" />
                        带到右侧复习
                      </Button>
                      <Button
                        variant="ghost"
                        className="w-full justify-start"
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
                  </div>
                </div>
              </div>

              <Separator />

              <div className="text-xs leading-6 text-slate-500">
                处理建议：先在右侧复习这条疑问，如果已经彻底讲清，再标记为已解决；如果发现这是同类问题的代表，再回到列表查看同类问题。
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </WorkbenchShell>
  );
}
