'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Bot, FileSearch, LibraryBig, RefreshCcw, Trash2 } from "lucide-react";

import { PlatformSidebarFooter, PlatformSidebarHeader, createPlatformNav } from "@/components/workspace/app-sidebar";
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
import { InlineStatusMessage, PageFallback, PageLoading } from "@/components/ui/feedback";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";

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
  created_at?: string | null;
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

type KnowledgeModuleKey = "workspaces" | "knowledge" | "chunks";

type KnowledgeModuleErrors = Partial<Record<KnowledgeModuleKey, string>>;

function getApiErrorMessage(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object") {
    const detail = "detail" in payload ? String((payload as { detail?: unknown }).detail || "").trim() : "";
    if (detail) return detail;
    const message = "message" in payload ? String((payload as { message?: unknown }).message || "").trim() : "";
    if (message) return message;
  }
  return fallback;
}

function KnowledgePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [workspaceId, setWorkspaceId] = useState(0);
  const [workspace, setWorkspace] = useState<WorkspaceItem | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [stats, setStats] = useState<KnowledgeOverviewResponse["stats"] | null>(null);
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([]);
  const [selectedDocId, setSelectedDocId] = useState(0);
  const [workspaceSelectorOpen, setWorkspaceSelectorOpen] = useState(false);
  const [chunkPreviewOpen, setChunkPreviewOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [textFilename, setTextFilename] = useState("notes.md");
  const [textContent, setTextContent] = useState("");
  const [textAuthority, setTextAuthority] = useState("user");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadAuthority, setUploadAuthority] = useState("user");
  const [moduleErrors, setModuleErrors] = useState<KnowledgeModuleErrors>({});

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;
  const { username, authLoading } = useRequireAuth(API_BASE, "/workspace");

  const setModuleError = useCallback((key: KnowledgeModuleKey, message: string) => {
    setModuleErrors((prev) => (prev[key] === message ? prev : { ...prev, [key]: message }));
  }, []);

  const clearModuleError = useCallback((key: KnowledgeModuleKey) => {
    setModuleErrors((prev) => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const refreshWorkspaces = useCallback(async (uname: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}`, { credentials: "include" });
      const json = await res.json().catch(() => null);
      if (!res.ok) {
        setModuleError("workspaces", getApiErrorMessage(json, `工作区加载失败(${res.status})`));
        setWorkspaces([]);
        return [];
      }
      clearModuleError("workspaces");
      const items = json?.workspaces || [];
      setWorkspaces(items);
      return items as WorkspaceItem[];
    } catch {
      setModuleError("workspaces", "工作区列表请求失败，请检查网络或登录状态");
      setWorkspaces([]);
      return [];
    }
  }, [API_BASE, clearModuleError, setModuleError]);

  const refreshKnowledge = useCallback(async (uname: string, wid: number) => {
    if (!wid) return;
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/${encodeURIComponent(uname)}/${wid}`, {
        credentials: "include",
      });
      const json = await res.json().catch(() => null);
      if (!res.ok || !json?.success) {
        setModuleError("knowledge", getApiErrorMessage(json, `知识库加载失败(${res.status})`));
        setWorkspace(null);
        setDocuments([]);
        setStats(null);
        return;
      }
      clearModuleError("knowledge");
      setWorkspace(json.workspace || null);
      setDocuments(json.documents || []);
      setStats(json.stats || null);
    } catch {
      setModuleError("knowledge", "知识库请求失败，请检查网络或登录状态");
      setWorkspace(null);
      setDocuments([]);
      setStats(null);
    }
  }, [API_BASE, clearModuleError, setModuleError]);

  const refreshChunks = useCallback(async (uname: string, wid: number, docId: number) => {
    if (!wid || !docId) {
      setChunks([]);
      clearModuleError("chunks");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/${encodeURIComponent(uname)}/${wid}/documents/${docId}/chunks`, {
        credentials: "include",
      });
      const json = await res.json().catch(() => null);
      if (!res.ok) {
        setModuleError("chunks", getApiErrorMessage(json, `切片加载失败(${res.status})`));
        setChunks([]);
        return;
      }
      clearModuleError("chunks");
      setChunks(json?.chunks || []);
    } catch {
      setModuleError("chunks", "切片请求失败，请检查网络或登录状态");
      setChunks([]);
    }
  }, [API_BASE, clearModuleError, setModuleError]);

  const buildWorkspaceReferenceQuery = useCallback((
    doc: KnowledgeDocument | null | undefined,
    chunk?: KnowledgeChunk | null,
  ) => {
    if (!workspaceId || !doc) return "";
    const params = new URLSearchParams();
    params.set("doc", String(doc.id));
    if (chunk && typeof chunk.chunk_index === "number") {
      params.set("chunk", String(chunk.chunk_index));
    }
    if (doc.title) params.set("ref_title", doc.title);
    const snippet = (chunk?.content || doc.summary || "").trim();
    if (snippet) params.set("ref_snippet", snippet.slice(0, 240));
    params.set("ref_source", chunk ? `Chunk #${chunk.chunk_index}` : `${doc.doc_type} 文档`);
    return params.toString();
  }, [workspaceId]);

  useEffect(() => {
    if (authLoading || !username) return;
    const run = async () => {
      try {
        const items = await refreshWorkspaces(username);
        const requestedWorkspaceId = Number(searchParams.get("workspace_id") || 0);
        const initialWorkspaceId = requestedWorkspaceId || items[0]?.id || 0;
        setWorkspaceId(initialWorkspaceId);
        if (initialWorkspaceId) {
          await refreshKnowledge(username, initialWorkspaceId);
        }
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [authLoading, refreshKnowledge, refreshWorkspaces, searchParams, username]);

  useEffect(() => {
    if (!username || !workspaceId) return;
    void refreshKnowledge(username, workspaceId);
    setSelectedDocId(0);
    setChunks([]);
  }, [refreshKnowledge, username, workspaceId]);

  useEffect(() => {
    if (!username || !workspaceId || !selectedDocId) return;
    void refreshChunks(username, workspaceId, selectedDocId);
  }, [refreshChunks, selectedDocId, username, workspaceId]);

  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      const matchesQuery =
        !query.trim() ||
        doc.title.toLowerCase().includes(query.trim().toLowerCase()) ||
        String(doc.summary || "").toLowerCase().includes(query.trim().toLowerCase());
      const matchesStatus = statusFilter === "all" || doc.status === statusFilter;
      return matchesQuery && matchesStatus;
    });
  }, [documents, query, statusFilter]);

  const selectedDocument = useMemo(
    () => documents.find((item) => item.id === selectedDocId) || null,
    [documents, selectedDocId]
  );

  const handleDelete = async (docId: number) => {
    if (!username || !workspaceId || saving) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/${encodeURIComponent(username)}/${workspaceId}/documents/${docId}`, {
        method: "DELETE",
        credentials: "include",
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json?.success) throw new Error(json?.detail || `删除失败(${res.status})`);
      if (selectedDocId === docId) {
        setSelectedDocId(0);
        setChunks([]);
      }
      await refreshKnowledge(username, workspaceId);
      setMsg(`已删除文档：${json?.title || docId}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "删除失败");
    } finally {
      setSaving(false);
    }
  };

  const saveTextDoc = async () => {
    if (!username || !workspaceId || saving || !textFilename.trim() || !textContent.trim()) return;
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
      if (!res.ok || !json?.success) throw new Error(json?.detail || `入库失败(${res.status})`);
      setTextContent("");
      await refreshKnowledge(username, workspaceId);
      setMsg("文本已入库");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "文本入库失败");
    } finally {
      setSaving(false);
    }
  };

  const uploadDocument = async () => {
    if (!username || !workspaceId || saving || !uploadFile) return;
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
      await refreshKnowledge(username, workspaceId);
      setMsg("文件已上传并开始入库整理");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "上传失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading || authLoading) return <PageLoading label="正在加载知识库..." />;

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <LibraryBig className="h-3.5 w-3.5" />
          KNOWLEDGE BASE
        </WorkbenchBadge>
      }
      title="知识库管理台"
      description="把知识库从工作区详情页里拆出来，形成单独的管理面：按工作区筛选、查看文档状态、看 chunk、清理失败文档、直接跳转聊天验证。"
      sidebarTitle="知识库路由"
      sidebarDescription="这里不是图谱展示页，而是知识治理和文档管理台。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("knowledge")}
      footer={<PlatformSidebarFooter username={username} detail="Knowledge operator" />}
      topActions={
        <>
          <Button
            variant="outline"
            className="border-slate-300 bg-white/90 text-slate-700 hover:bg-slate-50"
            onClick={() => workspaceId && refreshKnowledge(username, workspaceId)}
          >
            <RefreshCcw className="h-4 w-4" />
            刷新
          </Button>
          <Button
            className="bg-blue-600 shadow-[0_14px_30px_rgba(31,111,235,0.22)] hover:bg-blue-700"
            onClick={() => {
              const doc = documents.find((item) => item.id === selectedDocId) || null;
              const query = buildWorkspaceReferenceQuery(doc);
              router.push(workspaceId ? `/workspace/${workspaceId}${query ? `?${query}` : ""}` : "/workspace");
            }}
          >
            <Bot className="h-4 w-4" />
            进入工作区对话
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        {moduleErrors.workspaces || moduleErrors.knowledge ? (
          <InlineStatusMessage tone="warning">
            {[moduleErrors.workspaces, moduleErrors.knowledge].filter(Boolean).join("；")}
          </InlineStatusMessage>
        ) : null}
        <div className="rounded-[1.7rem] border border-slate-200/90 bg-[linear-gradient(135deg,rgba(255,255,255,0.98),rgba(244,248,252,0.96)_56%,rgba(239,246,255,0.88))] px-5 py-5 shadow-[0_18px_46px_rgba(15,23,42,0.05)]">
          <div className="grid gap-4 xl:grid-cols-[1.16fr_0.84fr]">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{workspace?.name || "未选择工作区"}</Badge>
                <Badge variant="outline">{stats?.documents || 0} 份文档</Badge>
                <Badge variant="outline">{stats?.knowledge_units || 0} 个切片</Badge>
                <Badge variant="secondary">tokens≈{stats?.total_tokens || 0}</Badge>
              </div>
              <div className="max-w-3xl">
                <div className="text-xl font-semibold tracking-[-0.03em] text-slate-950">知识库页只负责资料治理，不负责承载主要学习动作。</div>
                <div className="mt-2 text-sm leading-6 text-slate-600">
                  这里主要做三件事：切换工作区、清理和浏览文档、把有价值的资料片段送回工作区继续追问。入库仍然保留，但不再抢主画面。
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={() => {
                    const doc = documents.find((item) => item.id === selectedDocId) || null;
                    const query = buildWorkspaceReferenceQuery(doc);
                    router.push(workspaceId ? `/workspace/${workspaceId}${query ? `?${query}` : ""}` : "/workspace");
                  }}
                >
                  <Bot className="h-4 w-4" />
                  回到工作区对话
                </Button>
                <Button variant="outline" onClick={() => setWorkspaceSelectorOpen(true)}>
                  切换工作区
                </Button>
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-blue-100 bg-[linear-gradient(135deg,rgba(239,246,255,0.96),rgba(255,255,255,0.98))] p-5 shadow-[0_12px_30px_rgba(15,23,42,0.04)]">
              <div className="text-sm font-semibold text-slate-900">当前治理重点</div>
              <div className="mt-3 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
                <div className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-3">
                  <div className="text-xs text-slate-500">可用文档</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">{stats?.ready_documents || 0}</div>
                </div>
                <div className="rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3">
                  <div className="text-xs text-slate-500">失败文档</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">{stats?.failed_documents || 0}</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-3">
                  <div className="text-xs text-slate-500">关系数</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">{stats?.relations || 0}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {msg ? <InlineStatusMessage>{msg}</InlineStatusMessage> : null}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.34fr)_360px] 2xl:grid-cols-[minmax(0,1.34fr)_390px]">
          <WorkbenchSection
            title="文档管理"
            description="左侧作为主文档区，只负责筛选、清理和把资料送回工作区。切片明细和工作区切换都走右侧控制塔与弹层。"
            actions={
              <div className="flex flex-wrap gap-2">
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="搜索标题或摘要"
                    className="h-9 w-56 border-slate-200 bg-white shadow-none"
                  />
                  <div className="flex gap-2">
                    {["all", "ready", "failed"].map((item) => (
                      <Button
                        key={item}
                        variant={statusFilter === item ? "default" : "outline"}
                        size="sm"
                        onClick={() => setStatusFilter(item)}
                      >
                        {item}
                      </Button>
                    ))}
                  </div>
              </div>
            }
          >
            <ScrollArea className="h-[720px] pr-3">
              <div className="space-y-3">
                {moduleErrors.knowledge ? (
                  <InlineStatusMessage tone="warning">{moduleErrors.knowledge}</InlineStatusMessage>
                ) : null}
                {!moduleErrors.knowledge && documents.length === 0 ? (
                  <WorkbenchEmpty title="当前工作区还没有文档" description="可以先在右侧快速入库，或者去工作区详情页上传资料。" tone="hint" />
                ) : null}
                {!moduleErrors.knowledge && documents.length > 0 && filteredDocuments.length === 0 ? (
                  <WorkbenchEmpty title="没有匹配文档" description="可以切换工作区、清空筛选，或者先去工作区详情页上传资料。" tone="warning" />
                ) : null}
                {filteredDocuments.map((doc) => {
                  const authority = String(doc.metadata?.authority_level || "user");
                  const duplicateCount = Number(doc.metadata?.duplicate_count || 1);
                  const isLatestVersion = Boolean(doc.metadata?.is_latest_version ?? true);
                  const version = Number(doc.metadata?.version || 1);
                  return (
                    <Card
                      key={doc.id}
                      className={
                        selectedDocId === doc.id
                          ? "border-blue-200 bg-[linear-gradient(135deg,rgba(219,234,254,0.72),rgba(255,255,255,0.98))] shadow-[0_12px_28px_rgba(31,111,235,0.08)]"
                          : "border-slate-200/90 bg-white/96 shadow-[0_8px_22px_rgba(15,23,42,0.03)]"
                      }
                    >
                      <CardContent className="space-y-3 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <button
                            type="button"
                            className="min-w-0 text-left"
                            onClick={() => {
                              setSelectedDocId(doc.id);
                              setChunkPreviewOpen(true);
                            }}
                          >
                            <div className="truncate text-sm font-medium text-slate-900">{doc.title}</div>
                            <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{doc.summary || "无摘要"}</div>
                          </button>
                          <div className="flex gap-2">
                            <Badge variant={doc.status === "ready" ? "success" : doc.status === "failed" ? "destructive" : "outline"}>
                              {doc.status}
                            </Badge>
                            <Badge variant="outline">{doc.doc_type}</Badge>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="outline">{authority}</Badge>
                          <Badge variant="outline">v{version}</Badge>
                          {!isLatestVersion ? <Badge variant="warning">旧版本</Badge> : null}
                          {duplicateCount > 1 ? <Badge variant="warning">重复 {duplicateCount}</Badge> : null}
                          <Badge variant="outline">tokens≈{doc.token_estimate}</Badge>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" onClick={() => {
                            const query = buildWorkspaceReferenceQuery(doc);
                            router.push(`/workspace/${workspaceId}${query ? `?${query}` : ""}`);
                          }}>
                            去工作区对话
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => {
                            const query = buildWorkspaceReferenceQuery(doc);
                            router.push(`/workspace/${workspaceId}${query ? `?${query}` : ""}`);
                          }}>
                            定位到工作区
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setSelectedDocId(doc.id);
                              setChunkPreviewOpen(true);
                            }}
                          >
                            查看 Chunk
                          </Button>
                          <Button size="sm" variant="outline" disabled={saving} onClick={() => void handleDelete(doc.id)}>
                            <Trash2 className="h-4 w-4" />
                            删除
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </ScrollArea>
          </WorkbenchSection>

          <div className="grid gap-4 xl:sticky xl:top-6 xl:self-start">
            <Card className="border-slate-200/90 bg-white/96 shadow-[0_12px_34px_rgba(15,23,42,0.04)]">
              <CardContent className="space-y-4 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">知识控制塔</div>
                    <div className="mt-1 text-xs leading-6 text-slate-500">
                      这里只保留工作区切换、切片预览和快速入库。真正的文档列表始终放在左侧。
                    </div>
                  </div>
                  <Badge variant="outline">{workspace?.name || "未选择"}</Badge>
                </div>

                <button
                  type="button"
                  onClick={() => setWorkspaceSelectorOpen(true)}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-left transition-colors hover:bg-slate-100"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-900">工作区切换</div>
                      <div className="mt-1 text-xs leading-6 text-slate-500">
                        {workspace?.description || workspace?.slug || "按工作区隔离知识库，避免不同课程和任务混在一起。"}
                      </div>
                    </div>
                    <Badge variant="secondary">{workspaces.length}</Badge>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => selectedDocument && setChunkPreviewOpen(true)}
                  disabled={!selectedDocument}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-left transition-colors hover:bg-slate-100 disabled:cursor-not-allowed"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-900">Chunk 预览</div>
                      <div className="mt-1 text-xs leading-6 text-slate-500">
                        {selectedDocument
                          ? selectedDocument.title
                          : "先在左侧选中文档，再查看 chunk 切片和引用定位。"}
                      </div>
                    </div>
                    <Badge variant={selectedDocument ? "secondary" : "outline"}>
                      {selectedDocument ? `${chunks.length} chunks` : "未选择"}
                    </Badge>
                  </div>
                </button>

                <div className="rounded-2xl border border-dashed border-slate-300 bg-[linear-gradient(180deg,rgba(248,250,252,0.94),rgba(255,255,255,0.98))] p-4">
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Quick Intake</div>
                  <div className="mb-3 text-sm font-medium text-slate-900">按需补资料</div>
                  <div className="space-y-3">
                    <Input
                      value={textFilename}
                      onChange={(e) => setTextFilename(e.target.value)}
                      placeholder="例如：规则整理.md"
                      className="border-slate-200 bg-white shadow-none"
                    />
                    <textarea
                      value={textContent}
                      onChange={(e) => setTextContent(e.target.value)}
                      placeholder="只在需要时补充内容，不要让入库流程盖过文档治理主线。"
                      className="min-h-[140px] w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm outline-none"
                    />
                    <Input
                      type="file"
                      onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                      className="border-slate-200 bg-white shadow-none"
                    />
                    <div className="flex flex-wrap gap-2">
                      {["user", "school", "system"].map((level) => (
                        <Button
                          key={`knowledge-${level}`}
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
                    <div className="flex flex-wrap gap-2">
                      <Button className="bg-blue-600 hover:bg-blue-700" onClick={() => void saveTextDoc()} disabled={saving || !textContent.trim()}>
                        入库整理
                      </Button>
                      <Button variant="outline" onClick={() => void uploadDocument()} disabled={saving || !uploadFile}>
                        上传文件
                      </Button>
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button className="flex-1" onClick={() => setWorkspaceSelectorOpen(true)}>
                    选择工作区
                  </Button>
                  <Button variant="outline" className="flex-1" onClick={() => selectedDocument && setChunkPreviewOpen(true)} disabled={!selectedDocument}>
                    查看切片
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <Dialog open={workspaceSelectorOpen} onOpenChange={setWorkspaceSelectorOpen}>
        <DialogContent className="max-w-2xl border-slate-200 bg-white p-0">
          <DialogHeader className="border-b border-slate-200 px-6 pb-5 pt-6">
            <DialogTitle className="text-xl font-semibold tracking-[-0.03em] text-slate-950">工作区切换</DialogTitle>
            <DialogDescription className="text-sm leading-6 text-slate-600">
              按工作区隔离知识库，避免不同课程和任务混在一起。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 px-6 pb-6 pt-5">
            {moduleErrors.workspaces ? (
              <InlineStatusMessage tone="warning">{moduleErrors.workspaces}</InlineStatusMessage>
            ) : null}
            {!moduleErrors.workspaces && workspaces.length === 0 ? (
              <WorkbenchEmpty title="暂无可切换工作区" description="当前没有读取到工作区列表，稍后可以刷新重试。" tone="warning" />
            ) : null}
            {workspaces.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setWorkspaceId(item.id);
                  setWorkspaceSelectorOpen(false);
                }}
                className={`w-full rounded-[1.2rem] border px-3.5 py-3 text-left transition-all ${
                  workspaceId === item.id
                    ? "border-blue-200 bg-[linear-gradient(135deg,rgba(219,234,254,0.9),rgba(255,255,255,0.95))] shadow-[0_10px_24px_rgba(31,111,235,0.08)]"
                    : "border-slate-200 bg-white/96 hover:border-slate-300 hover:bg-slate-50 hover:shadow-[0_10px_24px_rgba(15,23,42,0.04)]"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium text-slate-900">{item.name}</div>
                  {item.is_default ? <Badge variant="secondary">默认</Badge> : <Badge variant="outline">#{item.id}</Badge>}
                </div>
                <div className="mt-1 text-xs text-slate-500">{item.description || item.slug}</div>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={chunkPreviewOpen} onOpenChange={setChunkPreviewOpen}>
        <DialogContent className="max-w-4xl border-slate-200 bg-white p-0">
          <DialogHeader className="border-b border-slate-200 px-6 pb-5 pt-6">
            <DialogTitle className="text-xl font-semibold tracking-[-0.03em] text-slate-950">Chunk 预览</DialogTitle>
            <DialogDescription className="text-sm leading-6 text-slate-600">
              这里直接看文档切片，判断知识是否适合被检索，再决定要不要回工作区继续验证。
            </DialogDescription>
          </DialogHeader>
          <div className="px-6 pb-6 pt-5">
            {!selectedDocument ? (
              <WorkbenchEmpty title="尚未选中文档" description="先在文档列表里点一份文档，这里会加载它的 chunk 列表。" tone="hint" />
            ) : (
              <div className="space-y-3">
                {moduleErrors.chunks ? (
                  <InlineStatusMessage tone="warning">{moduleErrors.chunks}</InlineStatusMessage>
                ) : null}
                <Card className="border-slate-200/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.94))] shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
                  <CardContent className="space-y-2 p-4">
                    <div className="text-sm font-medium text-slate-900">{selectedDocument.title}</div>
                    <div className="text-xs text-slate-500">
                      {selectedDocument.created_at ? new Date(selectedDocument.created_at).toLocaleString("zh-CN") : "时间未知"}
                    </div>
                  </CardContent>
                </Card>
                <ScrollArea className="h-[560px] pr-3">
                  <div className="space-y-3">
                    {!moduleErrors.chunks && chunks.length === 0 ? (
                      <WorkbenchEmpty title="暂无 chunk" description="这份文档还没有可读切片，可能解析失败或尚未完成处理。" tone="warning" />
                    ) : null}
                    {chunks.map((chunk) => (
                      <Card key={chunk.id} className="border-slate-200/90 bg-white/96 shadow-[0_8px_20px_rgba(15,23,42,0.03)]">
                        <CardContent className="space-y-2 p-4">
                          <div className="flex items-center justify-between gap-2">
                            <div className="text-sm font-medium text-slate-900">
                              {chunk.title || `Chunk #${chunk.chunk_index}`}
                            </div>
                            <Badge variant="outline">{chunk.char_count} chars</Badge>
                          </div>
                          <div className="whitespace-pre-wrap text-sm leading-6 text-slate-600">{chunk.content}</div>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                const query = buildWorkspaceReferenceQuery(selectedDocument, chunk);
                                router.push(`/workspace/${workspaceId}${query ? `?${query}` : ""}`);
                              }}
                            >
                              <FileSearch className="h-4 w-4" />
                              在工作区定位
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </WorkbenchShell>
  );
}

function KnowledgePageFallback() {
  return <PageFallback label="正在加载知识库页面..." />;
}

export default function KnowledgePage() {
  return (
    <Suspense fallback={<KnowledgePageFallback />}>
      <KnowledgePageContent />
    </Suspense>
  );
}
