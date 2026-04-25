'use client';

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Blocks,
  Database,
  FileText,
  Network,
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";

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

export default function WorkspaceDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const workspaceId = Number(params?.id || 0);
  const requestedDocId = Number(searchParams.get("doc") || 0);
  const requestedChunkIndex = Number(searchParams.get("chunk") || 0);

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
  const [reminderOpen, setReminderOpen] = useState(false);
  const [textFilename, setTextFilename] = useState("notes.md");
  const [textContent, setTextContent] = useState("");
  const [textAuthority, setTextAuthority] = useState("user");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadAuthority, setUploadAuthority] = useState("user");
  const [msg, setMsg] = useState("");

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

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
          <Button onClick={() => router.push(`/chat?workspace_id=${workspaceId}`)}>打开对话</Button>
        </>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="grid gap-4">
          <WorkbenchSection title="WORKSPACE DETAIL" description="工作区状态和学习状态合并展示，不再拆很多解释板块。">
            <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
              <div className="grid gap-3">
                <WorkbenchStatCard label="Documents" value={stats.documents} />
                <WorkbenchStatCard label="Knowledge Units" value={stats.nodes} />
                <WorkbenchStatCard label="Relations" value={stats.edges} />
                <WorkbenchStatCard label="Workspace" value={workspace?.name || "-"} hint={workspace?.slug || "当前工作区"} />
              </div>
              <div>
                {learningStatus ? (
                  <LearningStatus metrics={learningStatus.metrics} signals={learningStatus.signals} />
                ) : (
                  <WorkbenchEmpty title="暂无学习状态" description="等待工作区状态聚合完成。" />
                )}
              </div>
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="知识库可视化" description="中区主视图先聚焦知识库本身，展示文档结构、权威级别、状态和知识覆盖面。">
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
          </WorkbenchSection>

          <WorkbenchSection title="文档资料区" description="这里只保留一个简洁入口：可以打字，也可以丢文件，然后统一入库整理。">
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
                  className="min-h-52 bg-white"
                  placeholder="在这里直接输入内容，或者下方选择文件。这个页面不再堆文档清单和知识检索。"
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
                  <Button variant="outline" onClick={() => router.push(`/knowledge?workspace_id=${workspaceId}`)}>
                    打开这个工作区的知识库
                  </Button>
                </div>
              </div>

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
                                      <span className="text-[11px] text-slate-400">{chunk.char_count} chars</span>
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
          </WorkbenchSection>
        </div>

        <div>
          <WorkbenchSection title="AI 对话" description="右边只保留对话，组合编排和知识治理都去专门页面处理。">
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => router.push("/composition")}>
                  <Blocks className="h-4 w-4" />
                  去组合编排
                </Button>
                <Button variant="outline" onClick={() => router.push(`/knowledge?workspace_id=${workspaceId}`)}>
                  <Network className="h-4 w-4" />
                  这个工作区的知识库
                </Button>
              </div>
              <AIPanel username={username} workspaceId={workspaceId} workspaceName={workspace?.name} />
            </div>
          </WorkbenchSection>
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
    </WorkbenchShell>
  );
}
