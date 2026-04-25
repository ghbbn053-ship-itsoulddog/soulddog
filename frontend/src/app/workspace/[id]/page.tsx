'use client';

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Blocks,
  BrainCircuit,
  Database,
  FileText,
  Network,
  Search,
  Sparkles,
  Upload,
} from "lucide-react";

import { KnowledgeVisualization } from "@/components/knowledge/KnowledgeVisualization";
import { AIPanel } from "@/components/workspace/ai-panel";
import { AISuggestion } from "@/components/workspace/ai-suggestion";
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
import { Input } from "@/components/ui/input";
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

type SearchResult = {
  document_id: number;
  title: string;
  content: string;
  score: number;
  chunk_index: number;
  source: string;
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
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [platformSkills, setPlatformSkills] = useState<PlatformSkill[]>([]);
  const [platformMcpTools, setPlatformMcpTools] = useState<PlatformMcp[]>([]);
  const [composition, setComposition] = useState<CompositionData | null>(null);
  const [agentFrameworks, setAgentFrameworks] = useState<AgentFramework[]>([]);
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

  const refreshPlatformObjects = async (uname: string) => {
    const [skillsRes, mcpRes, compositionRes, frameworkRes] = await Promise.all([
      fetch(`${API_BASE}/api/platform/${encodeURIComponent(uname)}/skills`, { credentials: "include" }),
      fetch(`${API_BASE}/api/platform/${encodeURIComponent(uname)}/mcp`, { credentials: "include" }),
      fetch(`${API_BASE}/api/composition/${encodeURIComponent(uname)}`, { credentials: "include" }),
      fetch(`${API_BASE}/api/agents/frameworks`, { credentials: "include" }),
    ]);
    const skillsJson = skillsRes.ok ? await skillsRes.json() : null;
    const mcpJson = mcpRes.ok ? await mcpRes.json() : null;
    const compositionJson = compositionRes.ok ? await compositionRes.json() : null;
    const frameworkJson = frameworkRes.ok ? await frameworkRes.json() : null;
    setPlatformSkills(skillsJson?.skills || []);
    setPlatformMcpTools(mcpJson?.mcp_tools || []);
    setComposition(compositionJson?.data || null);
    setAgentFrameworks(frameworkJson?.frameworks || []);
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
          refreshPlatformObjects(uname),
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

  const searchWorkspace = async () => {
    if (!username || !workspaceId || !searchQuery.trim()) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/workspace/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          username,
          workspace_id: workspaceId,
          query: searchQuery.trim(),
          top_k: 8,
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json?.success) throw new Error(json?.detail || `检索失败(${res.status})`);
      setSearchResults(json?.results || []);
      setMsg(`已返回 ${json?.results?.length || 0} 条结果`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "检索失败");
    } finally {
      setSaving(false);
    }
  };

  const enabledSkills = useMemo(() => {
    const enabledNames = new Set(composition?.skills || []);
    return platformSkills.filter((item) => enabledNames.has(item.name));
  }, [composition, platformSkills]);

  const enabledMcpTools = useMemo(() => {
    const enabledNames = new Set(composition?.mcp_tools || []);
    return platformMcpTools.filter((item) => enabledNames.has(item.name));
  }, [composition, platformMcpTools]);

  const stats = useMemo(
    () => ({
      documents: documents.length,
      nodes: graph?.nodes?.length || 0,
      edges: graph?.edges?.length || 0,
      searchHits: searchResults.length,
      enabledSkills: enabledSkills.length,
      enabledMcp: enabledMcpTools.length,
    }),
    [documents.length, enabledMcpTools.length, enabledSkills.length, graph, searchResults.length]
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
      description={workspace?.description || "工作区详情页承载知识、文档、检索和 AI 能力面板。"}
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
      <div className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)_360px]">
        <div className="grid gap-4">
          <WorkbenchSection title="工作区状态" description="当前工作区的核心统计。">
            <div className="grid gap-3">
              <WorkbenchStatCard label="Documents" value={stats.documents} />
              <WorkbenchStatCard label="Knowledge Units" value={stats.nodes} />
              <WorkbenchStatCard label="Relations" value={stats.edges} />
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="运行态概览" description="这一区域承接工作台左下状态位，但先展示真实可用状态。">
            <div className="grid gap-3">
              <WorkbenchStatCard label="Search Hits" value={stats.searchHits} hint="当前检索区返回的结果数" />
              <WorkbenchStatCard label="Enabled Skills" value={stats.enabledSkills} hint="真实参与组合编排的 Skill 数量" />
              <WorkbenchStatCard label="Enabled MCP" value={stats.enabledMcp} hint="真实挂入组合编排的工具数量" />
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="学习状态" description="当前不再是占位统计，而是基于工作区文档、对话引用和缓存新鲜度聚合出来的学习信号。">
            {learningStatus ? (
              <LearningStatus metrics={learningStatus.metrics} signals={learningStatus.signals} />
            ) : (
              <WorkbenchEmpty title="暂无学习状态" description="等待工作区状态聚合完成。" />
            )}
          </WorkbenchSection>

          <WorkbenchSection title="平台能力接入" description="当前工作区能够使用的平台对象总览。">
            <div className="space-y-3 text-sm text-slate-600">
              <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                <span className="flex items-center gap-2"><Blocks className="h-4 w-4 text-slate-400" /> Skills</span>
                <Badge variant="secondary">{platformSkills.length}</Badge>
              </div>
              <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                <span className="flex items-center gap-2"><Network className="h-4 w-4 text-slate-400" /> MCP</span>
                <Badge variant="secondary">{platformMcpTools.length}</Badge>
              </div>
            </div>
          </WorkbenchSection>
        </div>

        <div className="grid gap-4">
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

          <WorkbenchSection title="文档资料区" description="支持手工录入、上传文件，并立即回写到工作区知识库。">
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-3">
                <div className="text-sm font-medium text-slate-900">手工录入</div>
                <Input value={textFilename} onChange={(e) => setTextFilename(e.target.value)} placeholder="notes.md" />
                <div className="flex flex-wrap gap-2">
                  {["user", "school", "system"].map((level) => (
                    <Button
                      key={level}
                      type="button"
                      size="sm"
                      variant={textAuthority === level ? "default" : "outline"}
                      onClick={() => setTextAuthority(level)}
                    >
                      {level}
                    </Button>
                  ))}
                </div>
                <Textarea
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  className="min-h-60"
                  placeholder="输入整理后的制度、规则、课题资料、会议纪要。"
                />
                <Button onClick={saveTextDoc} disabled={saving || !textContent.trim()}>
                  <FileText className="h-4 w-4" />
                  入库整理
                </Button>
              </div>

              <div className="space-y-4">
                <div className="rounded-xl border border-dashed border-[hsl(var(--border))] bg-[hsl(var(--muted))] p-4">
                  <div className="text-sm font-medium text-slate-900">上传文件</div>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    支持 `txt / md / json / html / yaml / csv / pdf / docx / xlsx / pptx`
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {["user", "school", "system"].map((level) => (
                      <Button
                        key={level}
                        type="button"
                        size="sm"
                        variant={uploadAuthority === level ? "default" : "outline"}
                        onClick={() => setUploadAuthority(level)}
                      >
                        {level}
                      </Button>
                    ))}
                  </div>
                  <Input type="file" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} className="mt-4 bg-white" />
                  <Button onClick={uploadDocument} disabled={saving || !uploadFile} variant="outline" className="mt-3">
                    <Upload className="h-4 w-4" />
                    上传并解析
                  </Button>
                </div>

                <div className="space-y-3">
                  <div className="text-sm font-medium text-slate-900">文档清单</div>
                  <ScrollArea className="h-[320px] pr-3">
                    <div className="space-y-3">
                      {documents.length === 0 && <WorkbenchEmpty title="暂无文档" description="先录入一段文本或上传文件。" />}
                      {documents.map((doc) => (
                        <Card
                          key={doc.id}
                          id={`doc-${doc.id}`}
                          className={doc.id === requestedDocId ? "border-[hsl(var(--primary))] bg-blue-50/60 shadow-none" : "shadow-none"}
                        >
                          <CardContent className="space-y-3 p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="truncate text-sm font-medium text-slate-900">{doc.title}</div>
                                <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{doc.summary || "无摘要"}</div>
                              </div>
                              <Badge variant="outline" className="uppercase">{doc.doc_type}</Badge>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <Badge variant={authorityTone(String(doc.metadata?.authority_level || "user")) as "outline"}>
                                {String(doc.metadata?.authority_level || "user")}
                              </Badge>
                              <Badge variant={statusTone(doc.status) as "success"}>{doc.status}</Badge>
                              <Badge variant="outline">tokens≈{doc.token_estimate}</Badge>
                            </div>
                            {doc.id === requestedDocId && documentChunks.length > 0 && (
                              <div className="space-y-2 border-t border-[hsl(var(--border))] pt-3">
                                <div className="text-xs font-medium text-slate-500">引用片段定位</div>
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
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </ScrollArea>
                </div>
              </div>
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="知识检索" description="在当前工作区范围内搜索制度、说明和知识片段。">
            <div className="space-y-3">
              <div className="flex gap-2">
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="例如：培养方案、流程规范、MCP 接入"
                />
                <Button onClick={searchWorkspace} disabled={saving || !searchQuery.trim()} size="icon">
                  <Search className="h-4 w-4" />
                </Button>
              </div>
              <ScrollArea className="h-[260px] pr-3">
                <div className="space-y-3">
                  {searchResults.length === 0 && <WorkbenchEmpty title="暂无检索结果" description="输入问题后会返回当前工作区相关片段。" />}
                  {searchResults.map((item) => (
                    <Card key={`${item.document_id}-${item.chunk_index}`} className="shadow-none">
                      <CardContent className="space-y-2 p-4">
                        <div className="flex items-center justify-between gap-2">
                          <div className="truncate text-sm font-medium text-slate-900">{item.title}</div>
                          <Badge variant="outline">score {item.score.toFixed(3)}</Badge>
                        </div>
                        <div className="whitespace-pre-wrap text-sm leading-6 text-slate-600">{item.content}</div>
                        <div className="text-[11px] text-slate-400">{item.source}</div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </ScrollArea>
            </div>
          </WorkbenchSection>
        </div>

        <div className="grid gap-4">
          <WorkbenchSection title="AI 能力面板" description="右侧聚合当前工作区的聊天入口、组合状态和 Agent 框架能力。">
            <div className="space-y-3">
              <AIPanel username={username} workspaceId={workspaceId} workspaceName={workspace?.name} />

              <Card className="bg-[hsl(var(--muted))] shadow-none">
                <CardContent className="space-y-3 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-medium text-slate-900">Skill Composition</div>
                      <div className="text-xs text-slate-500">当前真正启用的 Skill</div>
                    </div>
                    <Badge variant="secondary">{enabledSkills.length}</Badge>
                  </div>
                  <div className="space-y-2">
                    {enabledSkills.length === 0 ? <WorkbenchEmpty title="尚未启用 Skill" description="去编排页启用至少一个业务 Skill。" /> : null}
                    {enabledSkills.slice(0, 4).map((item) => (
                      <div key={item.id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                        <div className="text-sm font-medium text-slate-900">{item.name}</div>
                        <div className="mt-1 text-xs leading-5 text-slate-500">{item.description || "无描述"}</div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-[hsl(var(--muted))] shadow-none">
                <CardContent className="space-y-3 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-medium text-slate-900">MCP Composition</div>
                      <div className="text-xs text-slate-500">当前真正挂入编排的 MCP 工具</div>
                    </div>
                    <Badge variant="secondary">{enabledMcpTools.length}</Badge>
                  </div>
                  <div className="space-y-2">
                    {enabledMcpTools.length === 0 ? <WorkbenchEmpty title="尚未启用 MCP" description="当前工作区还没有挂接工具生态。" /> : null}
                    {enabledMcpTools.slice(0, 4).map((item) => (
                      <div key={item.id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-sm font-medium text-slate-900">{item.name}</div>
                          <Badge variant="outline">{item.kind}</Badge>
                        </div>
                        <div className="mt-1 text-xs leading-5 text-slate-500">{item.description || "无描述"}</div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="shadow-none">
                <CardContent className="space-y-3 p-4">
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                    <BrainCircuit className="h-4 w-4 text-[hsl(var(--primary))]" />
                    Agent Frameworks
                  </div>
                  <div className="space-y-2">
                    {agentFrameworks.map((item) => (
                      <div key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-sm font-medium text-slate-900">{item.name}</div>
                          <Badge variant={item.available ? "success" : "outline"}>
                            {item.available ? "available" : "unavailable"}
                          </Badge>
                        </div>
                        <div className="mt-1 text-xs leading-5 text-slate-500">
                          {item.recommended ? "推荐框架" : "可选框架"}
                          {item.requires?.length ? ` · requires: ${item.requires.join(", ")}` : ""}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="建议区" description="基于当前工作区真实状态给出下一步，而不是静态文案。">
            <div className="space-y-3">
              {suggestions.length === 0 ? <WorkbenchEmpty title="当前没有待处理建议" description="说明工作区状态比较干净，或者刚刚已经处理过建议。" /> : null}
              {suggestions.map((item) => (
                <AISuggestion
                  key={item.id}
                  item={{
                    id: String(item.id),
                    title: item.title,
                    content: item.content,
                    reason: item.reason,
                    tone: item.tone,
                  }}
                  onAccept={(id) => void handleSuggestionAction(Number(id), "accept")}
                  onDismiss={(id) => void handleSuggestionAction(Number(id), "dismiss")}
                />
              ))}
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="Skill / MCP 清单" description="右侧快速核对平台对象与实际编排是否一致。">
            <ScrollArea className="h-[420px] pr-3">
              <div className="space-y-3">
                {platformSkills.slice(0, 4).map((item) => (
                  <Card key={`skill-${item.id}`} className="shadow-none">
                    <CardContent className="space-y-1 p-4">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-medium text-slate-900">{item.name}</div>
                        <Badge variant={enabledSkills.some((skill) => skill.id === item.id) ? "success" : "outline"}>
                          {enabledSkills.some((skill) => skill.id === item.id) ? "enabled" : "registered"}
                        </Badge>
                      </div>
                      <div className="text-xs text-slate-500">{item.description || "无描述"}</div>
                    </CardContent>
                  </Card>
                ))}
                {platformMcpTools.slice(0, 4).map((item) => (
                  <Card key={`mcp-${item.id}`} className="shadow-none">
                    <CardContent className="space-y-1 p-4">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-medium text-slate-900">{item.name}</div>
                        <Badge variant={enabledMcpTools.some((tool) => tool.id === item.id) ? "success" : "outline"}>
                          {enabledMcpTools.some((tool) => tool.id === item.id) ? item.kind : "registered"}
                        </Badge>
                      </div>
                      <div className="text-xs text-slate-500">{item.description || "无描述"}</div>
                    </CardContent>
                  </Card>
                ))}
                {platformSkills.length === 0 && platformMcpTools.length === 0 ? (
                  <WorkbenchEmpty title="暂无平台对象" description="先到 Skill / MCP 页面导入。" />
                ) : null}
              </div>
            </ScrollArea>
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
