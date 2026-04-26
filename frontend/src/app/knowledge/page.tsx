'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Bot, FileSearch, LibraryBig, RefreshCcw, Trash2 } from "lucide-react";

import { PlatformSidebarFooter, PlatformSidebarHeader, createPlatformNav } from "@/components/workspace/app-sidebar";
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

export default function KnowledgePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
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
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [textFilename, setTextFilename] = useState("notes.md");
  const [textContent, setTextContent] = useState("");
  const [textAuthority, setTextAuthority] = useState("user");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadAuthority, setUploadAuthority] = useState("user");

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const refreshWorkspaces = async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}`, { credentials: "include" });
    const json = res.ok ? await res.json() : null;
    const items = json?.workspaces || [];
    setWorkspaces(items);
    return items as WorkspaceItem[];
  };

  const refreshKnowledge = async (uname: string, wid: number) => {
    if (!wid) return;
    const res = await fetch(`${API_BASE}/api/knowledge/${encodeURIComponent(uname)}/${wid}`, {
      credentials: "include",
    });
    const json: KnowledgeOverviewResponse | null = res.ok ? await res.json() : null;
    if (!json?.success) return;
    setWorkspace(json.workspace || null);
    setDocuments(json.documents || []);
    setStats(json.stats || null);
  };

  const refreshChunks = async (uname: string, wid: number, docId: number) => {
    if (!wid || !docId) {
      setChunks([]);
      return;
    }
    const res = await fetch(`${API_BASE}/api/knowledge/${encodeURIComponent(uname)}/${wid}/documents/${docId}/chunks`, {
      credentials: "include",
    });
    const json = res.ok ? await res.json() : null;
    setChunks(json?.chunks || []);
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
        const items = await refreshWorkspaces(uname);
        const requestedWorkspaceId = Number(searchParams.get("workspace_id") || 0);
        const initialWorkspaceId = requestedWorkspaceId || items[0]?.id || 0;
        setWorkspaceId(initialWorkspaceId);
        if (initialWorkspaceId) {
          await refreshKnowledge(uname, initialWorkspaceId);
        }
      } catch {
        router.replace("/workspace");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [API_BASE, router, searchParams]);

  useEffect(() => {
    if (!username || !workspaceId) return;
    void refreshKnowledge(username, workspaceId);
    setSelectedDocId(0);
    setChunks([]);
  }, [username, workspaceId]);

  useEffect(() => {
    if (!username || !workspaceId || !selectedDocId) return;
    void refreshChunks(username, workspaceId, selectedDocId);
  }, [username, workspaceId, selectedDocId]);

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

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">加载中...</div>;
  }

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
          <Button variant="outline" onClick={() => workspaceId && refreshKnowledge(username, workspaceId)}>
            <RefreshCcw className="h-4 w-4" />
            刷新
          </Button>
          <Button onClick={() => router.push(workspaceId ? `/workspace/${workspaceId}` : "/workspace")}>
            <Bot className="h-4 w-4" />
            进入工作区对话
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <div className="grid gap-4 md:grid-cols-4">
          <WorkbenchStatCard label="Workspace" value={workspace?.name || "-"} hint="当前知识库所属工作区" />
          <WorkbenchStatCard label="Documents" value={stats?.documents || 0} hint={`ready ${stats?.ready_documents || 0} · failed ${stats?.failed_documents || 0}`} />
          <WorkbenchStatCard label="Chunks" value={stats?.knowledge_units || 0} hint={`relations ${stats?.relations || 0}`} />
          <WorkbenchStatCard label="Tokens" value={stats?.total_tokens || 0} hint="知识体量估算" />
        </div>

        <WorkbenchSection title="快速入库" description="只保留最直接的入口：输入文本或选择文件，然后统一入库整理。">
          <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-3">
              <Input value={textFilename} onChange={(e) => setTextFilename(e.target.value)} placeholder="例如：规则整理.md" />
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
              <Input type="file" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} className="bg-white" />
              <div className="flex flex-wrap gap-2">
                {["user", "school", "system"].map((level) => (
                  <Button
                    key={`upload-${level}`}
                    type="button"
                    size="sm"
                    variant={uploadAuthority === level ? "default" : "outline"}
                    onClick={() => setUploadAuthority(level)}
                  >
                    {level}
                  </Button>
                ))}
              </div>
            </div>
            <div className="space-y-3">
              <textarea
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                placeholder="直接输入要整理进知识库的内容，或者上面选择文件后点击入库整理。"
                className="min-h-[180px] w-full rounded-xl border border-[hsl(var(--border))] bg-white px-3 py-3 text-sm outline-none"
              />
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => void saveTextDoc()} disabled={saving || !textContent.trim()}>
                  入库整理
                </Button>
                <Button variant="outline" onClick={() => void uploadDocument()} disabled={saving || !uploadFile}>
                  上传文件入库
                </Button>
              </div>
            </div>
          </div>
        </WorkbenchSection>

        {msg ? (
          <Card className="border-slate-200 bg-slate-50 shadow-none">
            <CardContent className="p-4 text-sm text-slate-700">{msg}</CardContent>
          </Card>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)_420px]">
          <WorkbenchSection title="工作区切换" description="按工作区隔离知识库。">
            <div className="space-y-2">
              {workspaces.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setWorkspaceId(item.id)}
                  className={`w-full rounded-xl border px-3 py-3 text-left transition-colors ${
                    workspaceId === item.id ? "border-[hsl(var(--primary))] bg-blue-50/70" : "border-slate-200 bg-white hover:bg-slate-50"
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
          </WorkbenchSection>

          <WorkbenchSection
            title="文档管理"
            description="筛选、浏览、删除文档，处理失败文档和重复版本。"
            actions={
              <div className="flex flex-wrap gap-2">
                <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索标题或摘要" className="h-9 w-56" />
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
                {filteredDocuments.length === 0 ? (
                  <WorkbenchEmpty title="没有匹配文档" description="可以切换工作区、清空筛选，或者先去工作区详情页上传资料。" />
                ) : null}
                {filteredDocuments.map((doc) => {
                  const authority = String(doc.metadata?.authority_level || "user");
                  const duplicateCount = Number(doc.metadata?.duplicate_count || 1);
                  const isLatestVersion = Boolean(doc.metadata?.is_latest_version ?? true);
                  const version = Number(doc.metadata?.version || 1);
                  return (
                    <Card
                      key={doc.id}
                      className={selectedDocId === doc.id ? "border-[hsl(var(--primary))] bg-blue-50/60 shadow-none" : "shadow-none"}
                    >
                      <CardContent className="space-y-3 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <button type="button" className="min-w-0 text-left" onClick={() => setSelectedDocId(doc.id)}>
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
                          <Button size="sm" variant="outline" onClick={() => router.push(`/workspace/${workspaceId}?doc=${doc.id}`)}>
                            定位到工作区
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => router.push(`/workspace/${workspaceId}`)}>
                            去工作区对话
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

          <WorkbenchSection title="Chunk 预览" description="独立管理台里直接看文档切片，判断知识是否适合被检索。">
            {!selectedDocument ? (
              <WorkbenchEmpty title="尚未选中文档" description="左侧点一份文档，这里会加载它的 chunk 列表。" />
            ) : (
              <div className="space-y-3">
                <Card className="shadow-none">
                  <CardContent className="space-y-2 p-4">
                    <div className="text-sm font-medium text-slate-900">{selectedDocument.title}</div>
                    <div className="text-xs text-slate-500">
                      {selectedDocument.created_at ? new Date(selectedDocument.created_at).toLocaleString("zh-CN") : "时间未知"}
                    </div>
                  </CardContent>
                </Card>
                <ScrollArea className="h-[620px] pr-3">
                  <div className="space-y-3">
                    {chunks.length === 0 ? (
                      <WorkbenchEmpty title="暂无 chunk" description="这份文档还没有可读切片，可能解析失败或尚未完成处理。" />
                    ) : null}
                    {chunks.map((chunk) => (
                      <Card key={chunk.id} className="shadow-none">
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
                              onClick={() => router.push(`/workspace/${workspaceId}?doc=${selectedDocument.id}&chunk=${chunk.chunk_index}`)}
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
          </WorkbenchSection>
        </div>
      </div>
    </WorkbenchShell>
  );
}
