'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Blocks, Database, FileText, GitBranch, Upload, Plus, Sparkles } from "lucide-react";

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

export default function WorkspacePage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [currentWorkspaceId, setCurrentWorkspaceId] = useState<number | null>(null);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceDesc, setWorkspaceDesc] = useState("");
  const [textFilename, setTextFilename] = useState("notes.md");
  const [textContent, setTextContent] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [msg, setMsg] = useState("");

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const refreshWorkspaces = async (uname: string) => {
    const res = await fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}`, { credentials: "include" });
    const json = res.ok ? await res.json() : null;
    const items: WorkspaceItem[] = json?.workspaces || [];
    setWorkspaces(items);
    if (!currentWorkspaceId && items.length > 0) {
      setCurrentWorkspaceId(items[0].id);
    }
  };

  const refreshDocuments = async (uname: string, workspaceId: number) => {
    const res = await fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}/documents?workspace_id=${workspaceId}`, {
      credentials: "include",
    });
    const json = res.ok ? await res.json() : null;
    setDocuments(json?.documents || []);
  };

  const refreshGraph = async (uname: string, workspaceId: number) => {
    const res = await fetch(`${API_BASE}/api/workspace/${encodeURIComponent(uname)}/graph/${workspaceId}`, {
      credentials: "include",
    });
    const json = res.ok ? await res.json() : null;
    setGraph(json?.graph || null);
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
        await refreshWorkspaces(uname);
      } catch {
        router.replace("/chat");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [API_BASE, router]);

  useEffect(() => {
    if (!username || !currentWorkspaceId) return;
    refreshDocuments(username, currentWorkspaceId);
    refreshGraph(username, currentWorkspaceId);
  }, [username, currentWorkspaceId]);

  const currentWorkspace = useMemo(
    () => workspaces.find((item) => item.id === currentWorkspaceId) || null,
    [workspaces, currentWorkspaceId]
  );

  const createWorkspace = async () => {
    if (!username || !workspaceName.trim()) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/workspace`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          username,
          name: workspaceName.trim(),
          description: workspaceDesc.trim(),
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json?.success) throw new Error(json?.detail || `创建失败(${res.status})`);
      setWorkspaceName("");
      setWorkspaceDesc("");
      await refreshWorkspaces(username);
      if (json?.workspace?.id) {
        setCurrentWorkspaceId(json.workspace.id);
      }
      setMsg("工作区已创建");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "创建失败");
    } finally {
      setSaving(false);
    }
  };

  const saveTextDoc = async () => {
    if (!username || !currentWorkspaceId || !textFilename.trim() || !textContent.trim()) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/workspace/documents/text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          username,
          workspace_id: currentWorkspaceId,
          filename: textFilename.trim(),
          content: textContent,
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json?.success) throw new Error(json?.detail || `保存失败(${res.status})`);
      setTextContent("");
      await refreshDocuments(username, currentWorkspaceId);
      await refreshGraph(username, currentWorkspaceId);
      setMsg("文本已入知识库");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const uploadDocument = async () => {
    if (!username || !currentWorkspaceId || !uploadFile) return;
    setSaving(true);
    setMsg("");
    try {
      const formData = new FormData();
      formData.append("username", username);
      formData.append("workspace_id", String(currentWorkspaceId));
      formData.append("document_file", uploadFile);
      const res = await fetch(`${API_BASE}/api/workspace/documents/upload`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json?.success) throw new Error(json?.detail || `上传失败(${res.status})`);
      setUploadFile(null);
      await refreshDocuments(username, currentWorkspaceId);
      await refreshGraph(username, currentWorkspaceId);
      setMsg("文档已上传并入库");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "上传失败");
    } finally {
      setSaving(false);
    }
  };

  const searchWorkspace = async () => {
    if (!username || !currentWorkspaceId || !searchQuery.trim()) return;
    setSaving(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/workspace/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          username,
          workspace_id: currentWorkspaceId,
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

  if (loading) return <div className="p-6 text-sm text-slate-500">加载中...</div>;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.12),_transparent_35%),linear-gradient(135deg,#f8fafc,#eef2ff)] px-4 py-5">
      <div className="mx-auto max-w-7xl">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-semibold tracking-[0.2em] text-slate-500">
              <Blocks className="h-3.5 w-3.5" />
              PLATFORM CORE
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">工作区知识库</h1>
            <p className="mt-1 text-sm text-slate-600">用户文档、平台知识、Skill/MCP 关系的统一落点。</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => router.push("/chat")} className="rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700">
              返回聊天
            </button>
            <button onClick={() => router.push("/skills")} className="rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700">
              Skill
            </button>
            <button onClick={() => router.push("/mcp")} className="rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700">
              MCP
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[280px_1fr]">
          <section className="rounded-[28px] border border-slate-200/80 bg-white/85 p-4 shadow-[0_20px_80px_-35px_rgba(15,23,42,0.35)] backdrop-blur">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900">工作区</h2>
              <Database className="h-4 w-4 text-slate-400" />
            </div>
            <div className="mt-4 space-y-2">
              {workspaces.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setCurrentWorkspaceId(item.id)}
                  className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                    item.id === currentWorkspaceId
                      ? "border-blue-400 bg-blue-50 text-blue-900"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium">{item.name}</span>
                    {item.is_default && (
                      <span className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white">
                        default
                      </span>
                    )}
                  </div>
                  <div className="mt-1 truncate text-xs text-slate-500">{item.description || item.slug}</div>
                </button>
              ))}
            </div>

            <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-3">
              <div className="mb-2 text-sm font-medium text-slate-900">新建工作区</div>
              <input
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                placeholder="例如：竞赛资料库"
                className="mb-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none"
              />
              <textarea
                value={workspaceDesc}
                onChange={(e) => setWorkspaceDesc(e.target.value)}
                placeholder="描述这个工作区的用途"
                className="h-24 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none"
              />
              <button
                onClick={createWorkspace}
                disabled={saving || !workspaceName.trim()}
                className="mt-2 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                创建
              </button>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-4">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="rounded-[28px] border border-slate-200/80 bg-white/85 p-5 shadow-[0_20px_80px_-35px_rgba(15,23,42,0.35)] backdrop-blur">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-sm font-medium text-slate-500">当前工作区</div>
                    <div className="mt-1 text-2xl font-semibold text-slate-900">{currentWorkspace?.name || "未选择"}</div>
                    <div className="mt-1 text-sm text-slate-500">{currentWorkspace?.description || "用于沉淀私有资料、任务文档和知识关系。"}</div>
                  </div>
                  <div className="rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-400 p-3 text-white shadow-lg">
                    <Sparkles className="h-5 w-5" />
                  </div>
                </div>

                <div className="mt-5 grid gap-3 md:grid-cols-3">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="text-xs uppercase tracking-wide text-slate-500">Documents</div>
                    <div className="mt-2 text-2xl font-semibold text-slate-900">{documents.length}</div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="text-xs uppercase tracking-wide text-slate-500">Graph Nodes</div>
                    <div className="mt-2 text-2xl font-semibold text-slate-900">{graph?.nodes?.length || 0}</div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="text-xs uppercase tracking-wide text-slate-500">Relations</div>
                    <div className="mt-2 text-2xl font-semibold text-slate-900">{graph?.edges?.length || 0}</div>
                  </div>
                </div>
              </div>

              <div className="rounded-[28px] border border-slate-200/80 bg-white/85 p-5 shadow-[0_20px_80px_-35px_rgba(15,23,42,0.35)] backdrop-blur">
                <div className="flex items-center gap-2 text-slate-900">
                  <GitBranch className="h-4 w-4" />
                  <h2 className="text-base font-semibold">知识关系预览</h2>
                </div>
                <div className="mt-4 space-y-2">
                  {(graph?.edges || []).length === 0 && <div className="text-sm text-slate-500">当前还没有抽取出关系。</div>}
                  {(graph?.edges || []).slice(0, 8).map((edge) => (
                    <div key={edge.id} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                      <span className="font-medium">{edge.source}</span>
                      <span className="mx-2 text-slate-400">→</span>
                      <span className="text-blue-700">{edge.label}</span>
                      <span className="mx-2 text-slate-400">→</span>
                      <span>{edge.target}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1fr]">
              <div className="rounded-[28px] border border-slate-200/80 bg-white/85 p-5 shadow-[0_20px_80px_-35px_rgba(15,23,42,0.35)] backdrop-blur">
                <div className="flex items-center gap-2 text-slate-900">
                  <FileText className="h-4 w-4" />
                  <h2 className="text-base font-semibold">手工整理内容</h2>
                </div>
                <input
                  value={textFilename}
                  onChange={(e) => setTextFilename(e.target.value)}
                  className="mt-4 w-full rounded-2xl border border-slate-300 bg-slate-50 px-3 py-2 text-sm outline-none"
                  placeholder="notes.md"
                />
                <textarea
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  className="mt-3 h-72 w-full rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none"
                  placeholder="把会议纪要、整理后的规则、知识说明贴到这里，直接入平台知识库。"
                />
                <button
                  onClick={saveTextDoc}
                  disabled={saving || !currentWorkspaceId || !textContent.trim()}
                  className="mt-3 rounded-2xl bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
                >
                  入库
                </button>
              </div>

              <div className="rounded-[28px] border border-slate-200/80 bg-white/85 p-5 shadow-[0_20px_80px_-35px_rgba(15,23,42,0.35)] backdrop-blur">
                <div className="flex items-center gap-2 text-slate-900">
                  <Upload className="h-4 w-4" />
                  <h2 className="text-base font-semibold">上传文档</h2>
                </div>
                <div className="mt-4 rounded-[24px] border border-dashed border-slate-300 bg-slate-50 p-5">
                  <div className="text-sm text-slate-600">支持先接入文本型资料：`txt / md / json / html / yaml / csv`。</div>
                  <input
                    type="file"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="mt-4 w-full rounded-2xl border border-slate-300 bg-white px-3 py-2 text-sm"
                  />
                  <button
                    onClick={uploadDocument}
                    disabled={saving || !currentWorkspaceId || !uploadFile}
                    className="mt-3 rounded-2xl bg-white px-4 py-2 text-sm text-slate-800 border border-slate-300 disabled:opacity-50"
                  >
                    上传并整理
                  </button>
                </div>

                <div className="mt-5">
                  <div className="mb-2 text-sm font-medium text-slate-900">当前文档</div>
                  <div className="space-y-2">
                    {documents.length === 0 && <div className="text-sm text-slate-500">暂无文档</div>}
                    {documents.slice(0, 8).map((doc) => (
                      <div key={doc.id} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="truncate font-medium text-slate-900">{doc.title}</div>
                          <div className="rounded-full bg-white px-2 py-0.5 text-[11px] uppercase tracking-wide text-slate-500">
                            {doc.doc_type}
                          </div>
                        </div>
                        <div className="mt-1 text-xs text-slate-500">{doc.summary || "无摘要"}</div>
                        <div className="mt-2 text-[11px] text-slate-400">status={doc.status} · tokens≈{doc.token_estimate}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-[28px] border border-slate-200/80 bg-white/85 p-5 shadow-[0_20px_80px_-35px_rgba(15,23,42,0.35)] backdrop-blur">
              <div className="flex items-center gap-2 text-slate-900">
                <Database className="h-4 w-4" />
                <h2 className="text-base font-semibold">知识检索</h2>
              </div>
              <div className="mt-4 flex flex-col gap-3 md:flex-row">
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="flex-1 rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none"
                  placeholder="搜索工作区里的制度、说明、Skill 或 MCP 相关知识"
                />
                <button
                  onClick={searchWorkspace}
                  disabled={saving || !currentWorkspaceId || !searchQuery.trim()}
                  className="rounded-2xl bg-slate-900 px-4 py-3 text-sm text-white disabled:opacity-50"
                >
                  搜索
                </button>
              </div>
              <div className="mt-4 space-y-3">
                {searchResults.length === 0 && <div className="text-sm text-slate-500">暂无检索结果</div>}
                {searchResults.map((item) => (
                  <div key={`${item.document_id}-${item.chunk_index}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-medium text-slate-900">{item.title}</div>
                      <div className="text-xs text-slate-400">score={item.score.toFixed(3)}</div>
                    </div>
                    <div className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600">{item.content}</div>
                    <div className="mt-2 text-[11px] text-slate-400">{item.source}</div>
                  </div>
                ))}
              </div>
            </div>

            {msg && <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">{msg}</div>}
          </section>
        </div>
      </div>
    </div>
  );
}
