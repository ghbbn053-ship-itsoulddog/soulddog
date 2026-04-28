"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BookMarked,
  CheckCircle2,
  GraduationCap,
  QrCode,
  RefreshCcw,
  ScanLine,
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
import { normalizeScheduleData, resolveDefaultSemester } from "@/lib/education-cache";

type ScheduleCourse = Record<string, unknown>;

type CurrentSemesterResponse = {
  success?: boolean;
  data?: {
    code?: string;
    name?: string;
  };
};

type ScheduleResponse = {
  success?: boolean;
  data?:
    | {
        学期?: string;
        课程列表?: ScheduleCourse[];
        按学期?: Record<string, ScheduleCourse[]>;
      }
    | ScheduleCourse[];
};

type CourseCatalogItem = {
  title: string;
  url: string;
  teacher?: string;
  course_id?: string;
  class_id?: string;
  cpi?: string;
  image?: string;
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
    course_base_url?: string;
    course_home_url?: string;
    business_landing_url?: string;
    last_auth_status?: Record<string, unknown>;
  };
};

type VisualCourse = {
  title: string;
  teacher: string;
  weekday: string;
  period: string;
  location: string;
  matchedFrom: "qr" | "schedule";
  url?: string;
};

const QR_POLL_MS = 3000;
const WEEKDAY_ORDER = ["周一", "周二", "周三", "周四", "周五", "周六", "周日", "未知"];

function text(value: unknown) {
  return String(value ?? "").trim();
}

function normalizeName(value: string) {
  return value.replace(/\s+/g, "").replace(/[（）()]/g, "").toLowerCase();
}

function extractCourseField(course: ScheduleCourse, keys: string[]) {
  for (const key of keys) {
    const value = text(course[key]);
    if (value) return value;
  }
  return "";
}

function normalizeWeekday(value: string) {
  const raw = value.replace(/星期/g, "周").trim();
  const map: Record<string, string> = {
    "1": "周一",
    "2": "周二",
    "3": "周三",
    "4": "周四",
    "5": "周五",
    "6": "周六",
    "7": "周日",
    周1: "周一",
    周2: "周二",
    周3: "周三",
    周4: "周四",
    周5: "周五",
    周6: "周六",
    周7: "周日",
    周天: "周日",
  };
  return map[raw] || raw || "未知";
}

function normalizePeriod(value: string) {
  const raw = value.replace(/\s+/g, "");
  if (!raw) return "待定";
  const match = raw.match(/(\d+)\D+(\d+)/);
  if (match) return `${match[1]}-${match[2]}`;
  return raw.replace(/第|节/g, "") || "待定";
}

function buildVisualCourses(scheduleCourses: ScheduleCourse[], catalog: CourseCatalogItem[]) {
  const scheduleItems = scheduleCourses.map((course) => ({
    title: extractCourseField(course, ["课程名称", "课程名", "课程"]),
    teacher: extractCourseField(course, ["教师", "老师"]),
    weekday: normalizeWeekday(extractCourseField(course, ["星期", "weekday"])),
    period: normalizePeriod(extractCourseField(course, ["节次信息", "节次", "period", "上课时间"])),
    location: extractCourseField(course, ["地点", "教室"]),
  }));

  const scheduleMap = new Map(scheduleItems.map((item) => [normalizeName(item.title), item]));
  const merged: VisualCourse[] = [];

  for (const course of catalog) {
    const key = normalizeName(course.title || "");
    const matched = scheduleMap.get(key);
    merged.push({
      title: course.title,
      teacher: matched?.teacher || course.teacher || "",
      weekday: matched?.weekday || "未知",
      period: matched?.period || "待定",
      location: matched?.location || "",
      matchedFrom: matched ? "qr" : "schedule",
      url: course.url,
    });
  }

  const existing = new Set(merged.map((item) => normalizeName(item.title)));
  for (const item of scheduleItems) {
    if (!item.title || existing.has(normalizeName(item.title))) continue;
    merged.push({
      title: item.title,
      teacher: item.teacher,
      weekday: item.weekday,
      period: item.period,
      location: item.location,
      matchedFrom: "schedule",
    });
  }

  return merged;
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
  const [currentSemester, setCurrentSemester] = useState("");
  const [allScheduleCourses, setAllScheduleCourses] = useState<ScheduleCourse[]>([]);
  const [scheduleBySemester, setScheduleBySemester] = useState<Record<string, ScheduleCourse[]>>({});
  const [qrSession, setQrSession] = useState<QrLoginSession | null>(null);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

  const currentSemesterCourses = useMemo(() => {
    if (currentSemester && scheduleBySemester[currentSemester]) return scheduleBySemester[currentSemester];
    const fallbackSemester = resolveDefaultSemester(currentSemester, Object.keys(scheduleBySemester));
    if (fallbackSemester && scheduleBySemester[fallbackSemester]) return scheduleBySemester[fallbackSemester];
    return allScheduleCourses;
  }, [allScheduleCourses, currentSemester, scheduleBySemester]);

  const visualCourses = useMemo(
    () => buildVisualCourses(currentSemesterCourses, qrSession?.browser_meta?.course_catalog || []),
    [currentSemesterCourses, qrSession]
  );

  const weekdayStats = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of visualCourses) {
      const key = item.weekday || "未知";
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return WEEKDAY_ORDER.map((weekday) => ({
      weekday,
      count: counts.get(weekday) || 0,
    })).filter((item) => item.count > 0 || item.weekday !== "未知");
  }, [visualCourses]);

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

  const periodStats = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of visualCourses) {
      const key = item.period || "待定";
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([period, count]) => ({ period, count }))
      .sort((a, b) => a.period.localeCompare(b.period, "zh-CN"));
  }, [visualCourses]);

  const stopPolling = () => {
    if (pollTimerRef.current) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const refreshSchedule = async (uname: string) => {
    const [scheduleRes, currentSemesterRes] = await Promise.all([
      fetch(`${API_BASE}/api/schedule/db?username=${encodeURIComponent(uname)}`, { credentials: "include" }),
      fetch(`${API_BASE}/api/options/current-semester`, { credentials: "include" }),
    ]);
    const scheduleJson: ScheduleResponse | null = scheduleRes.ok ? await scheduleRes.json() : null;
    const currentSemesterJson: CurrentSemesterResponse | null = currentSemesterRes.ok ? await currentSemesterRes.json() : null;
    const normalized = normalizeScheduleData(scheduleJson?.data || []);
    const backendCurrentSemester = text(currentSemesterJson?.data?.code);
    const resolved = resolveDefaultSemester(backendCurrentSemester || normalized.semester, normalized.semesters);
    setAllScheduleCourses(normalized.courses);
    setScheduleBySemester(normalized.bySemester);
    setCurrentSemester(resolved);
  };

  const loadLatestSession = async (uname: string, sessionToken: string) => {
    const qs = new URLSearchParams({ username: uname, session_token: sessionToken });
    const res = await fetch(`${API_BASE}/api/chaoxing/qr-login/session?${qs.toString()}`, { credentials: "include" });
    const data = res.ok ? await res.json() : null;
    if (data?.session) setQrSession(data.session);
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
    if (nextSession.status === "confirmed") {
      stopPolling();
      setMessage("扫码登录成功，课程列表已抓取。");
      await refreshSchedule(uname);
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
      ensurePolling(username, data.session.session_token);
      setMessage("二维码已生成，请使用手机扫码并在手机上确认登录。");
    } finally {
      setSubmitting(false);
    }
  };

  const refreshAll = async () => {
    if (!username) return;
    setMessage("");
    await refreshSchedule(username);
    if (qrSession?.session_token) {
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
        await refreshSchedule(uname);
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
      description="当前页面只做后端托管扫码登录、课程抓取、当前学期筛选和轻量可视化。不暴露自动化执行入口。"
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
            <WorkbenchStatCard label="Current Term" value={currentSemester || "-"} hint="当前只看这一学期" />
            <WorkbenchStatCard label="Courses" value={visualCourses.length} hint="当前学期合并后的课程数" />
            <WorkbenchStatCard
              label="QR Catalog"
              value={qrSession?.browser_meta?.course_catalog?.length || 0}
              hint="扫码后抓到的课程条目"
            />
            <WorkbenchStatCard label="Teachers" value={teacherStats.length} hint="当前学期涉及教师数" />
          </div>

          {message ? (
            <Card className="border-slate-200 bg-slate-50 shadow-none">
              <CardContent className="whitespace-pre-line p-4 text-sm text-slate-700">{message}</CardContent>
            </Card>
          ) : null}

          <WorkbenchSection
            title="扫码登录"
            description="后端生成二维码、轮询登录状态、拿到课程页并抽取课程列表。前端只展示会话状态和结果。"
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
                    <div className="flex justify-center rounded-2xl bg-white p-4">
                      <img src={qrSession.qr_image_data} alt="学习通登录二维码" className="h-56 w-56 rounded-xl object-contain" />
                    </div>
                    <div className="text-center text-xs text-slate-500">
                      二维码有效期通常较短。若扫码无响应，直接重新生成。
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
                    <div>4. 页面只显示当前学期课程概览，不做自动化操作。</div>
                  </div>
                </div>

                {qrSession?.status === "confirmed" ? (
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                    <div className="flex items-center gap-2 font-medium">
                      <CheckCircle2 className="h-4 w-4" />
                      已完成课程抓取
                    </div>
                    <div className="mt-2 leading-6">
                      当前会话已经登录成功，并已从课程页提取课程入口。下面的课程列表和统计已可直接使用。
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="当前学期课程列表" description="优先用教务课表提供时序信息，再合并扫码抓到的课程标题和入口。">
            <ScrollArea className="h-[500px] pr-3">
              <div className="space-y-3">
                {visualCourses.length === 0 ? (
                  <WorkbenchEmpty title="还没有当前学期课程" description="先完成扫码登录，或者确认课表缓存里已有当前学期课程。" />
                ) : null}
                {visualCourses.map((course) => (
                  <Card key={`${course.title}-${course.weekday}-${course.period}`} className="border-slate-200 shadow-none">
                    <CardContent className="space-y-2 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="text-sm font-medium text-slate-900">{course.title}</div>
                        <Badge variant={course.matchedFrom === "qr" ? "success" : "outline"}>
                          {course.matchedFrom === "qr" ? "已匹配扫码课程" : "仅课表缓存"}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                        <span>{course.weekday}</span>
                        <span>{course.period}</span>
                        <span>{course.location || "地点待定"}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <UserRound className="h-3.5 w-3.5" />
                        {course.teacher || "教师待定"}
                      </div>
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
          <WorkbenchSection title="课程情况概览" description="只展示当前学期，不展开成独立详情页。">
            <div className="grid gap-4 md:grid-cols-2">
              <Card className="border-slate-200 bg-slate-50 shadow-none">
                <CardContent className="p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">按星期分布</div>
                  <div className="mt-4 space-y-3">
                    {weekdayStats.length === 0 ? (
                      <div className="text-sm text-slate-400">暂无数据</div>
                    ) : (
                      weekdayStats.map((item) => {
                        const width = Math.max(10, Math.round((item.count / Math.max(...weekdayStats.map((x) => x.count), 1)) * 100));
                        return (
                          <div key={item.weekday} className="space-y-1">
                            <div className="flex items-center justify-between text-sm text-slate-700">
                              <span>{item.weekday}</span>
                              <span>{item.count}</span>
                            </div>
                            <div className="h-2 rounded-full bg-slate-200">
                              <div className="h-2 rounded-full bg-slate-900" style={{ width: `${width}%` }} />
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
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">按节次分布</div>
                  <div className="mt-4 space-y-3">
                    {periodStats.length === 0 ? (
                      <div className="text-sm text-slate-400">暂无数据</div>
                    ) : (
                      periodStats.map((item) => {
                        const width = Math.max(10, Math.round((item.count / Math.max(...periodStats.map((x) => x.count), 1)) * 100));
                        return (
                          <div key={item.period} className="space-y-1">
                            <div className="flex items-center justify-between text-sm text-slate-700">
                              <span>{item.period}</span>
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
            </div>
          </WorkbenchSection>

          <WorkbenchSection title="教师分布" description="只保留高频教师，减少噪音。">
            <div className="space-y-3">
              {teacherStats.length === 0 ? (
                <WorkbenchEmpty title="暂无教师统计" description="等课程抓取和当前学期匹配完成后，这里会自动生成。" />
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
                <div className="mt-2 leading-6">二维码登录、状态轮询、课程页抓取、当前学期筛选、课程列表与轻量统计。</div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="font-medium text-slate-900">当前不启用</div>
                <div className="mt-2 leading-6">自动跳课、runner 注入、刷课执行面板。相关代码保留，但本页面不开放入口。</div>
              </div>
            </div>
          </WorkbenchSection>
        </div>
      </div>
    </WorkbenchShell>
  );
}
