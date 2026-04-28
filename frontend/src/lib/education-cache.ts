export type CachedEducationResponse<T> = {
  success?: boolean;
  data?: T;
  freshness?: string;
  cached_at?: string | null;
  status?: {
    cached_at?: string | null;
    freshness?: string;
  };
};

export type EducationStatus = {
  success?: boolean;
  has_cache?: boolean;
  freshness?: string;
  cached_at?: string | null;
  connection?: {
    binding_status?: string;
    auth_type?: string;
    last_verified_at?: string | null;
    has_active_session?: boolean;
    has_live_session?: boolean;
    has_cache?: boolean;
    mode?: string;
    label?: string;
  };
  sync?: {
    status?: string;
    message?: string;
    timestamp?: number;
  };
};

export type EducationCourse = Record<string, unknown>;
export type EducationGrade = Record<string, unknown>;
export type EducationExam = Record<string, unknown>;
export type EducationRecord = Record<string, unknown>;

export type ScheduleData = {
  学期?: string;
  课程列表?: EducationCourse[];
  按学期?: Record<string, EducationCourse[]>;
};

export type GradeData = {
  成绩列表?: EducationGrade[];
  按学期?: Record<string, EducationGrade[]>;
  统计信息?: Record<string, unknown>;
};

export type ExamData = {
  学期?: string;
  考试列表?: EducationExam[];
  按学期?: Record<string, EducationExam[]>;
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function toText(value: unknown) {
  return String(value ?? "").trim();
}

function parseSemesterParts(semester: string) {
  const match = semester.match(/^(\d{4})-(\d{4})-(\d+)$/);
  if (!match) return null;
  return {
    startYear: Number(match[1]),
    endYear: Number(match[2]),
    term: Number(match[3]),
  };
}

export function sortSemesters(semesters: string[]) {
  return [...new Set(semesters.filter(Boolean))].sort((left, right) => {
    const a = parseSemesterParts(left);
    const b = parseSemesterParts(right);
    if (a && b) {
      if (a.startYear !== b.startYear) return b.startYear - a.startYear;
      if (a.endYear !== b.endYear) return b.endYear - a.endYear;
      return b.term - a.term;
    }
    return right.localeCompare(left, "zh-CN");
  });
}

export function resolveDefaultSemester(preferred: string, semesters: string[]) {
  if (preferred && semesters.includes(preferred)) return preferred;
  return semesters[0] || "";
}

export function extractDisplayText(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = toText(record[key]);
    if (value) return value;
  }
  return "";
}

export function normalizeScheduleData(raw: unknown) {
  if (Array.isArray(raw)) {
    const courses = asArray<EducationCourse>(raw);
    const bySemester = groupBySemester(courses, ["学期", "开课学期"]);
    const semesters = sortSemesters(Object.keys(bySemester));
    return {
      semester: semesters[0] || "",
      courses,
      bySemester,
      semesters,
    };
  }

  const data = asRecord(raw);
  const courses = asArray<EducationCourse>(data["课程列表"]);
  const bySemesterRaw = asRecord(data["按学期"]);
  const bySemester: Record<string, EducationCourse[]> = {};
  for (const [semester, items] of Object.entries(bySemesterRaw)) {
    const list = asArray<EducationCourse>(items);
    if (list.length) bySemester[semester] = list;
  }
  if (Object.keys(bySemester).length === 0) {
    Object.assign(bySemester, groupBySemester(courses, ["学期", "开课学期"]));
  }
  const semesters = sortSemesters(Object.keys(bySemester));
  return {
    semester: toText(data["学期"]),
    courses,
    bySemester,
    semesters,
  };
}

export function normalizeGradeData(raw: unknown) {
  const data = asRecord(raw);
  const list = asArray<EducationGrade>(data["成绩列表"]);
  const stats = asRecord(data["统计信息"]);
  const bySemesterRaw = asRecord(data["按学期"]);
  const bySemester: Record<string, EducationGrade[]> = {};
  for (const [semester, items] of Object.entries(bySemesterRaw)) {
    const grades = asArray<EducationGrade>(items);
    if (grades.length) bySemester[semester] = grades;
  }
  if (Object.keys(bySemester).length === 0) {
    Object.assign(bySemester, groupBySemester(list, ["开课学期", "学期"]));
  }
  const semesters = sortSemesters(Object.keys(bySemester));
  return { list, stats, bySemester, semesters };
}

export function normalizeExamData(raw: unknown) {
  const data = asRecord(raw);
  const list = asArray<EducationExam>(data["考试列表"]);
  const bySemesterRaw = asRecord(data["按学期"]);
  const bySemester: Record<string, EducationExam[]> = {};
  for (const [semester, items] of Object.entries(bySemesterRaw)) {
    const exams = asArray<EducationExam>(items);
    if (exams.length) bySemester[semester] = exams;
  }
  if (Object.keys(bySemester).length === 0) {
    Object.assign(bySemester, groupBySemester(list, ["学期", "开课学期"]));
  }
  const semesters = sortSemesters(Object.keys(bySemester));
  return {
    semester: toText(data["学期"]),
    list,
    bySemester,
    semesters,
  };
}

export function summarizeAcademicProgress(raw: unknown) {
  const data = asRecord(raw);
  const items = asArray<EducationRecord>(data["课程列表"] ?? data["模块进度"]);
  return {
    studyType: toText(data["修读类型"]),
    totalRequired: toText(data["总学分要求"] ?? data["总学分"]),
    earned: toText(data["已获学分"] ?? data["已修学分"]),
    remaining: toText(data["还需学分"] ?? data["未修学分"]),
    items,
  };
}

export function summarizeTrainingPlan(raw: unknown) {
  const data = asRecord(raw);
  const basicInfo = asRecord(data["基本信息"]);
  const stats = asRecord(data["学分统计"]);
  const courses = asArray<EducationRecord>(data["课程列表"]);
  const byType = new Map<string, number>();
  const bySemester = new Map<string, number>();

  for (const course of courses) {
    const type = extractDisplayText(course, ["课程类型", "课程性质", "课程类别"]) || "其他";
    const semester = extractDisplayText(course, ["建议修读学期", "学期"]);
    byType.set(type, (byType.get(type) || 0) + 1);
    if (semester) {
      bySemester.set(semester, (bySemester.get(semester) || 0) + 1);
    }
  }

  return {
    name: toText(basicInfo["方案名称"] ?? basicInfo["页面标题"]),
    totalRequired: toText(stats["总学分要求"] ?? data["总学分要求"]),
    courses,
    typeSummary: Array.from(byType.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4),
    semesterSummary: Array.from(bySemester.entries())
      .sort((a, b) => a[0].localeCompare(b[0], "zh-CN"))
      .slice(0, 6),
  };
}

export function groupBySemester<T extends Record<string, unknown>>(items: T[], keys: string[]) {
  const grouped: Record<string, T[]> = {};
  for (const item of items) {
    const semester = extractDisplayText(item, keys);
    if (!semester) continue;
    if (!grouped[semester]) grouped[semester] = [];
    grouped[semester].push(item);
  }
  return grouped;
}
