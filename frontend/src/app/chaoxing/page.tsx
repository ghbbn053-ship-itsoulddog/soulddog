"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BookMarked,
  CheckCircle2,
  CircleDashed,
  ClipboardList,
  FileCheck2,
  GraduationCap,
  QrCode,
  RefreshCcw,
  ScanLine,
  Target,
  UserRound,
} from "lucide-react";

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
import { ScrollArea } from "@/components/ui/scroll-area";

type CourseCatalogItem = {
  title: string;
  url: string;
  teacher?: string;
  course_id?: string;
  class_id?: string;
  cpi?: string;
  image?: string;
};

type CourseMetricItem = {
  metric_key?: string;
  title?: string;
  teacher?: string;
  course_id?: string;
  class_id?: string;
  cpi?: string;
  progress_percent?: number | null;
  chapter_count?: number | null;
  completed_chapter_count?: number | null;
  chapter_completion_percent?: number | null;
  assignment_count?: number | null;
  completed_assignment_count?: number | null;
  exam_count?: number | null;
  completed_exam_count?: number | null;
  score_text?: string;
  status_text?: string;
  status?: string;
  error?: string;
};

type QrLoginSession = {
  id: number;
  owner_username: string;
  session_token: string;
  status: "pending" | "scannable" | "scanned" | "confirmed" | "expired" | "failed";
  login_url?: string;
  qr_page_url?: string;
  qr_image_url?: string;
  qr_image_data?: string;
  page_title?: string;
  last_error?: string | null;
  last_seen_at?: string | null;
  expires_at?: string | null;
  created_at?: string | null;
  browser_meta?: {
    course_catalog?: CourseCatalogItem[];
    course_metrics?: CourseMetricItem[];
    course_base_url?: string;
    course_home_url?: string;
    business_landing_url?: string;
    last_auth_status?: Record<string, unknown>;
  };
};

type VisualCourse = {
  title: string;
  teacher: string;
  courseId: string;
  classId: string;
  cpi: string;
  url?: string;
  progressPercent?: number | null;
  chapterCount?: number | null;
  completedChapterCount?: number | null;
  chapterCompletionPercent?: number | null;
  assignmentCount?: number | null;
  completedAssignmentCount?: number | null;
  examCount?: number | null;
  completedExamCount?: number | null;
  scoreText?: string;
  statusText?: string;
  status?: string;
  error?: string;
};

const QR_POLL_MS = 3000;
const QR_SESSION_STORAGE_PREFIX = "chaoxing_qr_session_token:";

function text(value: unknown) {
  return String(value ?? "").trim();
}

function normalizeName(value: string) {
  return value.replace(/\s+/g, "").replace(/[（）()]/g, "").toLowerCase();
}

function toMetricMap(metrics: CourseMetricItem[]) {
  const map = new Map<string, CourseMetricItem[]>();
  for (const metric of metrics) {
    const primaryKey = [text(metric.course_id), text(metric.class_id), text(metric.cpi)].filter(Boolean).join("__");
    const fallbackKey = `${normalizeName(text(metric.title))}__${text(metric.class_id)}__${text(metric.course_id)}`;
    const key = primaryKey || fallbackKey;
    const current = map.get(key) || [];
    current.push(metric);
    map.set(key, current);
  }
  return map;
}

function buildVisualCourses(catalog: CourseCatalogItem[], metrics: CourseMetricItem[]) {
  const metricMap = toMetricMap(metrics);
  const seen = new Set<string>();
  const merged: VisualCourse[] = [];
  for (const [index, course] of catalog.entries()) {
    const metricKey = [text(course.course_id), text(course.class_id), text(course.cpi)].filter(Boolean).join("__");
    const fallbackMetricKey = `${normalizeName(course.title || "")}__${text(course.class_id)}__${text(course.course_id)}`;
    const matchedMetrics = metricMap.get(metricKey || fallbackMetricKey) || [];
    const metric = matchedMetrics[0];
    const title = text(course.title) || text(metric?.title) || `课程 ${text(course.course_id) || index + 1}`;
    const dedupeKey = text(course.url) || `${text(course.course_id)}__${text(course.class_id)}__${text(course.cpi)}__${index}`;
    if (seen.has(dedupeKey)) continue;
    seen.add(dedupeKey);
    merged.push({
      title,
      teacher: course.teacher || text(metric?.teacher),
      courseId: text(course.course_id),
      classId: text(course.class_id),
      cpi: text(course.cpi),
      url: course.url,
      progressPercent: typeof metric?.progress_percent === "number" ? metric.progress_percent : null,
      chapterCount: typeof metric?.chapter_count === "number" ? metric.chapter_count : null,
      completedChapterCount: typeof metric?.completed_chapter_count === "number" ? metric.completed_chapter_count : null,
      chapterCompletionPercent:
        typeof metric?.chapter_completion_percent === "number" ? metric.chapter_completion_percent : null,
      assignmentCount: typeof metric?.assignment_count === "number" ? metric.assignment_count : null,
      completedAssignmentCount:
        typeof metric?.completed_assignment_count === "number" ? metric.completed_assignment_count : null,
      examCount: typeof metric?.exam_count === "number" ? metric.exam_count : null,
      completedExamCount: typeof metric?.completed_exam_count === "number" ? metric.completed_exam_count : null,
      scoreText: text(metric?.score_text),
      statusText: text(metric?.status_text),
      status: text(metric?.status),
      error: text(metric?.error),
    });
  }

  // Fallback: when course catalog extraction is empty or partial, still render
  // the learning dashboard from per-course metrics so the page does not go blank.
  for (const [index, metric] of metrics.entries()) {
    const dedupeKey =
      [text(metric.course_id), text(metric.class_id), text(metric.cpi)].filter(Boolean).join("__") ||
      `${normalizeName(text(metric.title))}__metric__${index}`;
    if (seen.has(dedupeKey)) continue;
    seen.add(dedupeKey);
    merged.push({
      title: text(metric.title) || `课程 ${text(metric.course_id) || index + 1}`,
      teacher: text(metric.teacher),
      courseId: text(metric.course_id),
      classId: text(metric.class_id),
      cpi: text(metric.cpi),
      progressPercent: typeof metric.progress_percent === "number" ? metric.progress_percent : null,
      chapterCount: typeof metric.chapter_count === "number" ? metric.chapter_count : null,
      completedChapterCount: typeof metric.completed_chapter_count === "number" ? metric.completed_chapter_count : null,
      chapterCompletionPercent:
        typeof metric.chapter_completion_percent === "number" ? metric.chapter_completion_percent : null,
      assignmentCount: typeof metric.assignment_count === "number" ? metric.assignment_count : null,
      completedAssignmentCount:
        typeof metric.completed_assignment_count === "number" ? metric.completed_assignment_count : null,
      examCount: typeof metric.exam_count === "number" ? metric.exam_count : null,
      completedExamCount: typeof metric.completed_exam_count === "number" ? metric.completed_exam_count : null,
      scoreText: text(metric.score_text),
      statusText: text(metric.status_text),
      status: text(metric.status),
      error: text(metric.error),
    });
  }

  return merged;
}

function metricNumber(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function displayMetric(value: number | null | undefined) {
  const num = metricNumber(value);
  return num === null ? "-" : `${num}`;
}

function displayPercent(value: number | null | undefined) {
  const num = metricNumber(value);
  return num === null ? "-" : `${num}%`;
}

function courseStatusLabel(status?: string) {
  switch (status) {
    case "completed":
      return "已完成";
    case "in_progress":
      return "学习中";
    default:
      return "待识别";
  }
}

function courseStatusBadge(status?: string) {
  if (status === "completed") return "success";
  if (status === "in_progress") return "warning";
  return "outline";
}

function statusBadgeVariant(status: string | undefined) {
  if (status === "confirmed") return "success";
  if (status === "scanned") return "warning";
  if (status === "expired" || status === "failed") return "destructive";
  return "outline";
}

function statusLabel(status: string | undefined) {
  switch (status) {
    case "scannable":
      return "等待扫码";
    case "scanned":
      return "已扫码，待确认";
    case "confirmed":
      return "登录成功";
    case "expired":
      return "二维码失效";
    case "failed":
      return "登录失败";
    default:
      return "准备中";
  }
}

export default function ChaoxingLearningPage() {
  const router = useRouter();
  const pollTimerRef = useRef<number | null>(null);

  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [qrSession, setQrSession] = useState<QrLoginSession | null>(null);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const visualCourses = useMemo(
    () => buildVisualCourses(qrSession?.browser_meta?.course_catalog || [], qrSession?.browser_meta?.course_metrics || []),
    [qrSession]
  );

  const teacherStats = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of visualCourses) {
      const key = item.teacher || "教师待定";
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([teacher, count]) => ({ teacher, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  }, [visualCourses]);

  const duplicateTitleStats = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of visualCourses) {
      const key = item.title || "未命名课程";
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([title, count]) => ({ title, count }))
      .sort((a, b) => b.count - a.count || a.title.localeCompare(b.title, "zh-CN"));
  }, [visualCourses]);

  const courseSummary = useMemo(() => {
    let completedCourses = 0;
    let inProgressCourses = 0;
    let totalChapters = 0;
    let totalAssignments = 0;
    let totalExams = 0;
    let totalProgress = 0;
    let progressCount = 0;

    for (const course of visualCourses) {
      if (course.status === "completed") completedCourses += 1;
      if (course.status === "in_progress") inProgressCourses += 1;
      totalChapters += metricNumber(course.chapterCount) || 0;
      totalAssignments += metricNumber(course.assignmentCount) || 0;
      totalExams += metricNumber(course.examCount) || 0;
      const progress = metricNumber(course.progressPercent);
      if (progress !== null) {
        totalProgress += progress;
        progressCount += 1;
      }
    }

    return {
      completedCourses,
      inProgressCourses,
      totalChapters,
      totalAssignments,
      totalExams,
      averageProgress: progressCount > 0 ? Math.round((totalProgress / progressCount) * 10) / 10 : null,
    };
  }, [visualCourses]);

  const stopPolling = () => {
    if (pollTimerRef.current) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const getStoredSessionToken = (uname: string) => {
    if (typeof window === "undefined" || !uname) return "";
    return window.localStorage.getItem(`${QR_SESSION_STORAGE_PREFIX}${uname}`) || "";
  };

  const storeSessionToken = (uname: string, sessionToken: string) => {
    if (typeof window === "undefined" || !uname || !sessionToken) return;
    window.localStorage.setItem(`${QR_SESSION_STORAGE_PREFIX}${uname}`, sessionToken);
  };

  const loadLatestSession = async (uname: string, sessionToken: string) => {
    const qs = new URLSearchParams({ username: uname, session_token: sessionToken });
    const res = await fetch(`${API_BASE}/api/chaoxing/qr-login/session?${qs.toString()}`, { credentials: "include" });
    const data = res.ok ? await res.json() : null;
    if (data?.session) {
      setQrSession(data.session);
      storeSessionToken(uname, sessionToken);
    }
  };

  const pollSession = async (uname: string, sessionToken: string) => {
    const res = await fetch(`${API_BASE}/api/chaoxing/qr-login/poll`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: uname, session_token: sessionToken }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setMessage(data?.detail || "轮询扫码状态失败");
      return;
    }
    const nextSession = data?.session as QrLoginSession | undefined;
    if (!nextSession) return;
    setQrSession(nextSession);
    storeSessionToken(uname, nextSession.session_token);
    if (nextSession.status === "confirmed") {
      stopPolling();
      setMessage("扫码登录成功，课程列表已抓取。");
      return;
    }
    if (nextSession.status === "expired" || nextSession.status === "failed") {
      stopPolling();
      setMessage(nextSession.last_error || "二维码会话已结束");
    }
  };

  const ensurePolling = (uname: string, sessionToken: string) => {
    stopPolling();
    pollTimerRef.current = window.setInterval(() => {
      void pollSession(uname, sessionToken);
    }, QR_POLL_MS);
  };

  const createQrSession = async () => {
    if (!username) return;
    setSubmitting(true);
    setMessage("");
    try {
      const res = await fetch(`${API_BASE}/api/chaoxing/qr-login/session`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.session) {
        setMessage(data?.detail || "生成二维码失败");
        return;
      }
      setQrSession(data.session);
      storeSessionToken(username, data.session.session_token);
      ensurePolling(username, data.session.session_token);
      setMessage("二维码已生成，请使用手机扫码并在手机上确认登录。");
    } finally {
      setSubmitting(false);
    }
  };

  const refreshAll = async () => {
    if (!username) return;
    setMessage("");
    if (qrSession?.session_token) {
      if (qrSession.status === "confirmed") {
        const res = await fetch(`${API_BASE}/api/chaoxing/qr-login/refresh`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, session_token: qrSession.session_token }),
        });
        const data = await res.json().catch(() => null);
        if (!res.ok || !data?.session) {
          setMessage(data?.detail || "刷新学习通课程数据失败");
          return;
        }
        setQrSession(data.session);
        setMessage("学习通课程数据已刷新。");
        return;
      }
      await loadLatestSession(username, qrSession.session_token);
    }
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
        const storedSessionToken = getStoredSessionToken(uname);
        if (storedSessionToken) {
          await loadLatestSession(uname, storedSessionToken);
        }
      } catch {
        router.replace("/chat");
      } finally {
        setLoading(false);
      }
    };
    void run();
    return () => stopPolling();
  }, [API_BASE, router]);

  useEffect(() => {
    if (!username || !qrSession?.session_token) return;
    if (qrSession.status === "scannable" || qrSession.status === "scanned" || qrSession.status === "pending") {
      ensurePolling(username, qrSession.session_token);
    } else {
      stopPolling();
    }
    return () => {
      if (qrSession.status === "confirmed" || qrSession.status === "expired" || qrSession.status === "failed") {
        stopPolling();
      }
    };
  }, [username, qrSession?.session_token, qrSession?.status]);

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">加载中...</div>;
  }

  return (
      <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <GraduationCap className="h-3.5 w-3.5" />
          QR LOGIN
        </WorkbenchBadge>
      }
      title="学习通扫码课程看板"
      description="当前页面只做后端托管扫码登录、课程抓取和学习通课程统计。不暴露自动化执行入口。"
      sidebarTitle="AI 学习工作台"
      sidebarDescription="Workspace / Skill / MCP / Agent"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("chaoxing")}
      footer={<PlatformSidebarFooter username={username} detail="二维码登录课程面板" />}
      topActions={
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={statusBadgeVariant(qrSession?.status)}>{statusLabel(qrSession?.status)}</Badge>
          <Button variant="outline" onClick={() => void refreshAll()}>
            <RefreshCcw className="h-4 w-4" />
            刷新
          </Button>
        </div>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[0.92fr_1.08fr]">
        <div className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-4">
            <WorkbenchStatCard label="Courses" value={visualCourses.length} hint="学习通抓到的课程总数" />
            <WorkbenchStatCard label="Completed" value={courseSummary.completedCourses} hint="判定为已完成的课程" />
            <WorkbenchStatCard
              label="Avg Progress"
              value={displayPercent(courseSummary.averageProgress)}
              hint="有进度数据的课程平均值"
            />
            <WorkbenchStatCard label="Teachers" value={teacherStats.length} hint="课程涉及教师数" />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <WorkbenchStatCard label="Chapters" value={courseSummary.totalChapters} hint="累计章节数" />
            <WorkbenchStatCard label="Assignments" value={courseSummary.totalAssignments} hint="累计作业/测验数" />
            <WorkbenchStatCard label="Exams" value={courseSummary.totalExams} hint="累计考试数" />
          </div>

          {message ? (
            <Card className="border-slate-200 bg-slate-50 shadow-none">
              <CardContent className="whitespace-pre-line p-4 text-sm text-slate-700">{message}</CardContent>
            </Card>
          ) : null}

          <WorkbenchSection
            title="扫码登录"
            description="后端生成二维码、轮询登录状态、拿到课程页并继续抓章节/作业/考试统计。前端只展示结果。"
            actions={
              <Button onClick={() => void createQrSession()} disabled={submitting}>
                <QrCode className="h-4 w-4" />
                {submitting ? "生成中..." : "生成二维码"}
              </Button>
            }
          >
            <div className="grid gap-4 lg:grid-cols-[0.86fr_1.14fr]">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-900">
                  <ScanLine className="h-4 w-4" />
                  扫码区域
                </div>
                {qrSession?.qr_image_data ? (
                  <div className="space-y-3">
                    <div className="flex justify-center rounded-2xl bg-white p-3 md:p-5">
                      <img
                        src={qrSession.qr_image_data}
                        alt="学习通登录二维码"
                        className="h-[320px] w-[320px] rounded-xl object-contain md:h-[380px] md:w-[380px]"
                      />
                    </div>
                    <div className="text-center text-xs text-slate-500">
                      二维码有效期通常较短。若扫码无响应，直接重新生成。电脑端显示已放大，手机贴近屏幕即可扫。
                    </div>
                  </div>
                ) : (
                  <WorkbenchEmpty title="还没有二维码" description="点击上方按钮后，这里会显示后端生成的扫码二维码。" />
                )}
              </div>

              <div className="grid gap-3">
                <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
                  <div className="font-medium text-slate-900">会话状态</div>
                  <div className="mt-3 grid gap-2">
                    <div>状态: {statusLabel(qrSession?.status)}</div>
                    <div>标题: {qrSession?.page_title || "-"}</div>
                    <div>最后更新: {qrSession?.last_seen_at || "-"}</div>
                    <div>过期时间: {qrSession?.expires_at || "-"}</div>
                    <div>会话 token: {qrSession?.session_token || "-"}</div>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
                  <div className="font-medium text-slate-900">登录链路</div>
                  <div className="mt-3 space-y-2 break-all leading-6">
                    <div>1. 后端打开登录页并提取二维码。</div>
                    <div>2. 用户扫码后，后端轮询确认状态。</div>
                    <div>3. 登录成功后，后端进入课程页并抽取课程列表。</div>
                    <div>4. 页面只显示学习通课程与统计，不做自动化操作。</div>
                  </div>
                </div>

                {qrSession?.status === "confirmed" ? (
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                    <div className="flex items-center gap-2 font-medium">
                      <CheckCircle2 className="h-4 w-4" />
                      已完成课程抓取
                    </div>
                  <div className="mt-2 leading-6">
                      当前会话已经登录成功，并已从课程页提取课程入口与课程统计。下面的数据都以学习通课程页为准。
                  </div>
                </div>
              ) : null}
              </div>
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="学习通课程明细" description="每门课都展示抓到的真实学习口径，不再混入教务课表。">
            <ScrollArea className="h-[500px] pr-3">
              <div className="space-y-3">
                {visualCourses.length === 0 ? (
                  <WorkbenchEmpty title="还没有抓到学习通课程" description="先完成扫码登录，等待后端进入课程页并提取课程列表。" />
                ) : null}
                {visualCourses.map((course) => (
                  <Card key={`${course.title}-${course.courseId}-${course.classId}`} className="border-slate-200 shadow-none">
                    <CardContent className="space-y-2 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="text-sm font-medium text-slate-900">{course.title}</div>
                        <Badge variant={courseStatusBadge(course.status)}>{courseStatusLabel(course.status)}</Badge>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                        <span>courseId: {course.courseId || "-"}</span>
                        <span>clazzId: {course.classId || "-"}</span>
                        <span>cpi: {course.cpi || "-"}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <UserRound className="h-3.5 w-3.5" />
                        {course.teacher || "教师待定"}
                      </div>
                      <div className="grid gap-2 pt-1 sm:grid-cols-2">
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                          <div className="flex items-center gap-2 font-medium text-slate-900">
                            <Target className="h-3.5 w-3.5" />
                            学习进度
                          </div>
                          <div className="mt-1 text-sm">{displayPercent(course.progressPercent)}</div>
                          <div className="mt-1 text-[11px] text-slate-500">
                            状态文本: {course.statusText || "-"}
                            {course.scoreText ? ` · 成绩: ${course.scoreText}` : ""}
                          </div>
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                          <div className="flex items-center gap-2 font-medium text-slate-900">
                            <BookMarked className="h-3.5 w-3.5" />
                            章节完成
                          </div>
                          <div className="mt-1 text-sm">
                            {displayMetric(course.completedChapterCount)} / {displayMetric(course.chapterCount)}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-500">
                            完成率: {displayPercent(course.chapterCompletionPercent)}
                          </div>
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                          <div className="flex items-center gap-2 font-medium text-slate-900">
                            <ClipboardList className="h-3.5 w-3.5" />
                            作业统计
                          </div>
                          <div className="mt-1 text-sm">
                            {displayMetric(course.completedAssignmentCount)} / {displayMetric(course.assignmentCount)}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-500">已完成 / 总数</div>
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                          <div className="flex items-center gap-2 font-medium text-slate-900">
                            <FileCheck2 className="h-3.5 w-3.5" />
                            考试统计
                          </div>
                          <div className="mt-1 text-sm">
                            {displayMetric(course.completedExamCount)} / {displayMetric(course.examCount)}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-500">已完成 / 总数</div>
                        </div>
                      </div>
                      {course.error ? (
                        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
                          课程统计抓取告警: {course.error}
                        </div>
                      ) : null}
                      {course.url ? (
                        <div className="break-all text-xs text-slate-400">{course.url}</div>
                      ) : null}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          </WorkbenchSection>
        </div>

        <div className="grid gap-4">
          <WorkbenchSection title="课程情况概览" description="只围绕学习通课程自身的数据做统计。">
            <div className="grid gap-4 md:grid-cols-2">
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">课程重复情况</div>
                  <div className="mt-4 space-y-3">
                    {duplicateTitleStats.length === 0 ? (
                      <div className="text-sm text-slate-400">暂无数据</div>
                    ) : (
                      duplicateTitleStats.map((item) => {
                        const width = Math.max(10, Math.round((item.count / Math.max(...duplicateTitleStats.map((x) => x.count), 1)) * 100));
                        return (
                          <div key={item.title} className="space-y-1">
                            <div className="flex items-center justify-between text-sm text-slate-700">
                              <span>{item.title}</span>
                              <span>{item.count}</span>
                            </div>
                            <div className="h-2 rounded-full bg-slate-200">
                              <div className="h-2 rounded-full bg-emerald-600" style={{ width: `${width}%` }} />
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </CardContent>
              </Card>
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">课程状态分布</div>
                  <div className="mt-4 space-y-3">
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
                      <div className="flex items-center justify-between text-sm text-emerald-900">
                        <span>已完成课程</span>
                        <span>{courseSummary.completedCourses}</span>
                      </div>
                    </div>
                    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
                      <div className="flex items-center justify-between text-sm text-amber-900">
                        <span>学习中课程</span>
                        <span>{courseSummary.inProgressCourses}</span>
                      </div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="flex items-center justify-between text-sm text-slate-700">
                        <span>待识别课程</span>
                        <span>{Math.max(0, visualCourses.length - courseSummary.completedCourses - courseSummary.inProgressCourses)}</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="教师分布" description="只保留高频教师，减少噪音。">
            <div className="space-y-3">
              {teacherStats.length === 0 ? (
                <WorkbenchEmpty title="暂无教师统计" description="等课程抓取完成后，这里会自动生成。" />
              ) : (
                teacherStats.map((item) => {
                  const width = Math.max(12, Math.round((item.count / Math.max(...teacherStats.map((x) => x.count), 1)) * 100));
                  return (
                    <Card key={item.teacher} className="border-slate-200 shadow-none">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium text-slate-900">{item.teacher}</div>
                            <div className="text-xs text-slate-500">{item.count} 门课程</div>
                          </div>
                          <div className="h-2 w-28 rounded-full bg-slate-200">
                            <div className="h-2 rounded-full bg-amber-500" style={{ width: `${width}%` }} />
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })
              )}
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="说明" description="边界收紧，避免现在又把自动化和登录混成一团。">
            <div className="space-y-3 text-sm text-slate-600">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-800">
                <div className="flex items-center gap-2 font-medium">
                  <BookMarked className="h-4 w-4" />
                  当前启用
                </div>
                <div className="mt-2 leading-6">二维码登录、状态轮询、课程页抓取，以及章节/作业/考试/课程进度统计。</div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="font-medium text-slate-900">当前不启用</div>
                <div className="mt-2 leading-6">自动跳课、runner 注入、刷课执行面板。相关代码保留，但本页面不开放入口。</div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="flex items-center gap-2 font-medium text-slate-900">
                  <CircleDashed className="h-4 w-4" />
                  当前统计口径
                </div>
                <div className="mt-2 leading-6">
                  后端会在登录成功后逐门课抓课程主页、章节页、作业页、考试页，并汇总成统一课程指标。
                </div>
              </div>
            </div>
          </WorkbenchSection>
        </div>
      </div>
    </WorkbenchShell>
  );
}
