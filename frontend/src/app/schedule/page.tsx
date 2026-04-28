'use client';

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarDays, ChevronLeft, ChevronRight, RefreshCcw } from "lucide-react";

import { PlatformSidebarFooter, PlatformSidebarHeader, createPlatformNav } from "@/components/workspace/app-sidebar";
import { WorkbenchBadge, WorkbenchSection, WorkbenchShell } from "@/components/workspace/workbench-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { normalizeScheduleData, resolveDefaultSemester } from "@/lib/education-cache";

type ScheduleCourse = Record<string, unknown>;
type ScheduleEntry = {
  courseName: string;
  location: string;
  teacher: string;
  weeks: string;
  weekday: string;
  period: string;
  raw: ScheduleCourse;
};

type ScheduleResponse = {
  success?: boolean;
  data?: {
    学期?: string;
    课程列表?: ScheduleCourse[];
    按学期?: Record<string, ScheduleCourse[]>;
  } | ScheduleCourse[];
  freshness?: string;
  cached_at?: string | null;
};

type EducationStatus = {
  freshness?: string;
  cached_at?: string | null;
  sync?: {
    status?: string;
    message?: string;
  };
};

const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const PERIODS = ["1-2", "3-4", "5-6", "7-8", "9-10", "11-12"];

function extractText(item: ScheduleCourse, keys: string[]) {
  for (const key of keys) {
    const value = String(item[key] ?? "").trim();
    if (value) return value;
  }
  return "";
}

function normalizeWeekday(value: string) {
  const text = value.replace(/星期/g, "周").trim();
  const mapping: Record<string, string> = {
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
  return mapping[text] || text || "未分配";
}

function detectPeriodLabel(value: string) {
  const normalizedText = value.replace(/\s+/g, "");
  const chinesePeriodMap: Array<[string, string]> = [
    ["第一二节", "1-2"],
    ["一二节", "1-2"],
    ["第三四节", "3-4"],
    ["三四节", "3-4"],
    ["第五六节", "5-6"],
    ["五六节", "5-6"],
    ["第七八节", "7-8"],
    ["七八节", "7-8"],
    ["第九十节", "9-10"],
    ["九十节", "9-10"],
    ["第十一十二节", "11-12"],
    ["十一十二节", "11-12"],
  ];
  for (const [token, mapped] of chinesePeriodMap) {
    if (normalizedText.includes(token)) {
      return mapped;
    }
  }
  const raw = value
    .replace(/第/g, "")
    .replace(/节/g, "")
    .replace(/[\[\]]/g, "")
    .replace(/\s+/g, "")
    .trim();
  const match = raw.match(/(\d+)\D+(\d+)/);
  if (match) {
    return `${Number(match[1])}-${Number(match[2])}`;
  }
  const single = raw.match(/^(\d+)$/);
  if (single) {
    const num = Number(single[1]);
    if (num >= 1 && num <= 2) return "1-2";
    if (num >= 3 && num <= 4) return "3-4";
    if (num >= 5 && num <= 6) return "5-6";
    if (num >= 7 && num <= 8) return "7-8";
    if (num >= 9 && num <= 10) return "9-10";
    if (num >= 11 && num <= 12) return "11-12";
    return String(num);
  }
  return raw || "未分配";
}

function splitCourseField(value: string) {
  return (value || "")
    .split(/-{10,}/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function explodeCourse(course: ScheduleCourse): ScheduleEntry[] {
  const names = splitCourseField(extractText(course, ["课程名称", "课程名", "课程"]));
  const teachers = splitCourseField(extractText(course, ["教师", "老师"]));
  const locations = splitCourseField(extractText(course, ["地点", "教室"]));
  const weeks = splitCourseField(extractText(course, ["周次", "weeks"]));
  const period = detectPeriodLabel(extractText(course, ["节次信息", "节次", "period", "上课时间"]));
  const weekday = normalizeWeekday(extractText(course, ["星期", "weekday"]));

  const size = Math.max(names.length, teachers.length, locations.length, weeks.length, 1);
  return Array.from({ length: size }, (_, index) => ({
    courseName: names[index] || names[0] || "未命名课程",
    location: locations[index] || locations[0] || "",
    teacher: teachers[index] || teachers[0] || "",
    weeks: weeks[index] || weeks[0] || "",
    weekday,
    period,
    raw: course,
  }));
}

function parseWeekTokens(value: string) {
  const text = (value || "")
    .replace(/\s+/g, "")
    .replace(/（/g, "(")
    .replace(/）/g, ")");
  if (!text) return [];
  const normalized = text
    .replace(/第/g, "")
    .replace(/周次?/g, "")
    .replace(/\(周\)/g, "")
    .replace(/单周/g, "|odd")
    .replace(/双周/g, "|even")
    .replace(/\((odd|even)\)/g, "|$1")
    .replace(/[()]/g, "")
    .replace(/周/g, "");

  return normalized
    .split(/[，,；;]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function matchesWeek(value: string, weekIndex: number) {
  const tokens = parseWeekTokens(value);
  if (tokens.length === 0) return true;

  for (const token of tokens) {
    const odd = token.includes("|odd");
    const even = token.includes("|even");
    const cleaned = token.replace(/\|odd|\|even/g, "");

    let matched = false;
    const range = cleaned.match(/^(\d+)-(\d+)$/);
    if (range) {
      const start = Number(range[1]);
      const end = Number(range[2]);
      matched = weekIndex >= start && weekIndex <= end;
    } else {
      const single = cleaned.match(/^(\d+)$/);
      if (single) {
        matched = weekIndex === Number(single[1]);
      }
    }

    if (!matched) continue;
    if (odd && weekIndex % 2 === 0) continue;
    if (even && weekIndex % 2 !== 0) continue;
    return true;
  }

  return false;
}

function getFreshnessMeta(status: EducationStatus | null) {
  if (!status?.cached_at) {
    return { label: "暂无缓存", badge: "outline" as const };
  }
  const cachedAt = new Date(status.cached_at).getTime();
  const deltaHours = Math.max(0, (Date.now() - cachedAt) / 3600000);
  if (status.freshness === "fresh") {
    return { label: deltaHours < 1 ? "更新于 1 小时内" : `更新于 ${Math.floor(deltaHours)} 小时前`, badge: "success" as const };
  }
  if (status.freshness === "stale") {
    return { label: `更新于 ${Math.floor(deltaHours / 24)} 天前`, badge: "warning" as const };
  }
  return { label: `更新于 ${Math.floor(deltaHours / 24)} 天前`, badge: "destructive" as const };
}

export default function SchedulePage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [semester, setSemester] = useState("");
  const [availableSemesters, setAvailableSemesters] = useState<string[]>([]);
  const [weekIndex, setWeekIndex] = useState(1);
  const [courses, setCourses] = useState<ScheduleCourse[]>([]);
  const [allCourses, setAllCourses] = useState<ScheduleCourse[]>([]);
  const [coursesBySemester, setCoursesBySemester] = useState<Record<string, ScheduleCourse[]>>({});
  const [status, setStatus] = useState<EducationStatus | null>(null);

  const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const API_BASE = RAW_API_BASE.endsWith("/api") ? RAW_API_BASE.slice(0, -4) : RAW_API_BASE;

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

        const [scheduleRes, statusRes] = await Promise.all([
          fetch(`${API_BASE}/api/schedule/db?username=${encodeURIComponent(uname)}`, { credentials: "include" }),
          fetch(`${API_BASE}/api/education/status?username=${encodeURIComponent(uname)}`, { credentials: "include" }),
        ]);

        const scheduleJson: ScheduleResponse | null = scheduleRes.ok ? await scheduleRes.json() : null;
        const statusJson = statusRes.ok ? await statusRes.json() : null;
        const normalized = normalizeScheduleData(scheduleJson?.data || []);
        const defaultSemester = resolveDefaultSemester(normalized.semester, normalized.semesters);
        setAllCourses(normalized.courses);
        setCoursesBySemester(normalized.bySemester);
        setAvailableSemesters(normalized.semesters);
        setSemester(defaultSemester);
        setCourses(defaultSemester ? normalized.bySemester[defaultSemester] || normalized.courses : normalized.courses);
        setStatus(statusJson || null);
      } catch {
        router.replace("/");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [API_BASE, router]);

  const freshness = useMemo(() => getFreshnessMeta(status), [status]);
  const visibleCourseCount = useMemo(() => {
    if (semester && coursesBySemester[semester]) return coursesBySemester[semester].length;
    return courses.length;
  }, [courses, coursesBySemester, semester]);

  const grid = useMemo(() => {
    const map = new Map<string, ScheduleEntry[]>();
    for (const course of courses) {
      for (const entry of explodeCourse(course)) {
        if (entry.weeks && !matchesWeek(entry.weeks, weekIndex)) {
          continue;
        }
        const key = `${entry.weekday}__${entry.period}`;
        const existing = map.get(key) || [];
        existing.push(entry);
        map.set(key, existing);
      }
    }
    return map;
  }, [courses, weekIndex]);

  const handleRefresh = async () => {
    if (!username || refreshing) return;
    try {
      setRefreshing(true);
      await fetch(`${API_BASE}/api/refresh?username=${encodeURIComponent(username)}`, {
        method: "POST",
        credentials: "include",
      });
      const [scheduleRes, statusRes] = await Promise.all([
        fetch(`${API_BASE}/api/schedule/db?username=${encodeURIComponent(username)}`, { credentials: "include" }),
        fetch(`${API_BASE}/api/education/status?username=${encodeURIComponent(username)}`, { credentials: "include" }),
      ]);
      const scheduleJson: ScheduleResponse | null = scheduleRes.ok ? await scheduleRes.json() : null;
      const statusJson = statusRes.ok ? await statusRes.json() : null;
      const normalized = normalizeScheduleData(scheduleJson?.data || []);
      const defaultSemester = resolveDefaultSemester(semester || normalized.semester, normalized.semesters);
      setAllCourses(normalized.courses);
      setCoursesBySemester(normalized.bySemester);
      setAvailableSemesters(normalized.semesters);
      setSemester(defaultSemester);
      setCourses(defaultSemester ? normalized.bySemester[defaultSemester] || normalized.courses : normalized.courses);
      setStatus(statusJson || null);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (!semester) {
      setCourses(allCourses);
      return;
    }
    if (coursesBySemester[semester]) {
      setCourses(coursesBySemester[semester]);
      return;
    }
    setCourses(allCourses);
  }, [allCourses, coursesBySemester, semester]);

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">加载中...</div>;
  }

  return (
    <WorkbenchShell
      badge={
        <WorkbenchBadge>
          <CalendarDays className="h-3.5 w-3.5" />
          SCHEDULE
        </WorkbenchBadge>
      }
      title="我的课表"
      description="完整课表页直接读取缓存课表数据，支持快速刷新和周视图浏览。"
      sidebarTitle="课表导航"
      sidebarDescription="当前先做缓存驱动的周视图，后续再补课程详情弹窗和统计面板。"
      sidebarHeader={<PlatformSidebarHeader />}
      navItems={createPlatformNav("schedule")}
      footer={<PlatformSidebarFooter username={username} detail="当前登录用户" />}
      topActions={
        <>
          <Button variant="outline" onClick={() => router.push("/")}>返回首页</Button>
          <Button onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? <RefreshCcw className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
            刷新
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <WorkbenchSection
          title="周视图课表"
          description={`学期 ${semester || "未知"} · ${freshness.label} · 当前第 ${weekIndex} 周 · 共 ${visibleCourseCount} 条课程`}
          actions={
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setWeekIndex((prev) => Math.max(1, prev - 1))}>
                <ChevronLeft className="h-4 w-4" />
                上一周
              </Button>
              <div className="min-w-[96px] text-center text-sm font-medium text-slate-700">第 {weekIndex} 周</div>
              <Button variant="outline" size="sm" onClick={() => setWeekIndex((prev) => prev + 1)}>
                下一周
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          }
        >
          <div className="mb-4 flex flex-wrap gap-2">
            {availableSemesters.length > 0 ? (
              availableSemesters.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => {
                    setSemester(item);
                    setWeekIndex(1);
                  }}
                  className={
                    item === semester
                      ? "rounded-full border border-[hsl(var(--primary))] bg-[hsla(var(--primary),0.08)] px-3 py-1 text-xs font-medium text-slate-900"
                      : "rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
                  }
                >
                  {item}
                </button>
              ))
            ) : (
              <Badge variant="outline">暂无学期缓存</Badge>
            )}
          </div>
          <div className="overflow-x-auto">
            <div className="min-w-[940px] rounded-2xl border border-slate-200 bg-white">
              <div className="grid grid-cols-[88px_repeat(7,minmax(0,1fr))] border-b border-slate-200 bg-slate-50/80 text-sm font-medium text-slate-700">
                <div className="border-r border-slate-200 px-4 py-3">节次</div>
                {WEEKDAYS.map((day) => (
                  <div key={day} className="border-r border-slate-200 px-4 py-3 last:border-r-0">
                    {day}
                  </div>
                ))}
              </div>

              {PERIODS.map((period) => (
                <div key={period} className="grid grid-cols-[88px_repeat(7,minmax(0,1fr))] border-b border-slate-200 last:border-b-0">
                  <div className="border-r border-slate-200 bg-slate-50/60 px-4 py-4 text-sm font-medium text-slate-700">
                    {period}
                  </div>
                  {WEEKDAYS.map((day) => {
                    const items = grid.get(`${day}__${period}`) || [];
                    return (
                      <div key={`${day}-${period}`} className="min-h-[108px] border-r border-slate-200 p-2.5 last:border-r-0">
                        <div className="space-y-2">
                          {items.length === 0 ? (
                            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 px-3 py-3 text-center text-xs text-slate-400">
                              暂无课程
                            </div>
                          ) : (
                            items.map((item, index) => (
                              <Card key={`${day}-${period}-${index}`} className="border-blue-100 bg-blue-50/70 shadow-none">
                                <CardContent className="space-y-1.5 p-3">
                                  <div className="text-sm font-medium text-slate-900">{item.courseName}</div>
                                  <div className="text-xs text-slate-500">{item.location || "地点待定"}</div>
                                  <div className="text-xs text-slate-500">{item.teacher || "教师待定"}</div>
                                  <div className="text-[11px] text-slate-400">{item.weeks || "周次待定"}</div>
                                </CardContent>
                              </Card>
                            ))
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </WorkbenchSection>
      </div>
    </WorkbenchShell>
  );
}
