"""
教务系统选项数据与查询工具
包含所有下拉选项数据，供AI调用工具使用
"""

from datetime import datetime
from typing import List, Dict, Optional


# ============== 院系数据 ==============
DEPARTMENTS = [
    {"code": "01", "name": "工商管理学院（粤商学院、创新创业学院）", "full_code": "20100"},
    {"code": "02", "name": "会计学院", "full_code": "20300"},
    {"code": "03", "name": "财政税务学院（税务师学院）", "full_code": "20700"},
    {"code": "05", "name": "金融学院", "full_code": "20600"},
    {"code": "06", "name": "经济学院", "full_code": "20400"},
    {"code": "07", "name": "法学院", "full_code": "20200"},
    {"code": "08", "name": "文化旅游学院", "full_code": "20900"},
    {"code": "09", "name": "外国语学院", "full_code": "21100"},
    {"code": "10", "name": "统计与数据科学学院", "full_code": "21400"},
    {"code": "11", "name": "大数据与人工智能学院", "full_code": "20500"},
    {"code": "12", "name": "人文与传播学院（网络传播学院、出版学院）", "full_code": "21200"},
    {"code": "13", "name": "体育学院", "full_code": "21700"},
    {"code": "14", "name": "马克思主义学院", "full_code": "21500"},
    {"code": "15", "name": "公共管理学院", "full_code": "20800"},
    {"code": "17", "name": "艺术与设计学院", "full_code": "21300"},
    {"code": "36", "name": "经济与管理实验教学中心", "full_code": "21800"},
    {"code": "21000", "name": "地理与环境经济学院", "full_code": "21000"},
    {"code": "22300", "name": "国际商学院", "full_code": "22300"},
    {"code": "22400", "name": "湾区影视产业学院", "full_code": "22400"},
    {"code": "22700", "name": "数字经济学院", "full_code": "22700"},
    {"code": "22800", "name": "人力资源学院", "full_code": "22800"},
]

# 职能部门（通常不需要查询）
ADMIN_DEPARTMENTS = [
    {"code": "10100", "name": "党委办公室、校长办公室（法制办公室、档案馆、校史馆）"},
    {"code": "11000", "name": "国际交流与合作部（港澳台事务办公室）"},
    {"code": "30800", "name": "旅游管理与规划设计研究院、岭南旅游研究院（合署）"},
    {"code": "31000", "name": "发展与改革研究院", "full_code": "31000"},
    {"code": "39", "name": "校团委", "full_code": "40200"},
]

# 联合培养学院（高职）
VOCATIONAL_COLLEGES = [
    {"code": "lVmobpvXTd", "name": "广东食品药品职业学院"},
    {"code": "rzzhe4mTSY", "name": "东莞职业技术学院"},
    {"code": "cxFYqCqIjg", "name": "广东工贸职业技术学院"},
    {"code": "mLdTtgT8eu", "name": "广东科学技术职业学院"},
    {"code": "8bYdL0jiUL", "name": "广东轻工职业技术学院"},
    {"code": "fextKrl5hV", "name": "广东水利电力职业技术学院"},
]


# ============== 年级数据 ==============
GRADES = ["2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018"]


# ============== 学期数据 ==============
SEMESTERS = [
    {"code": "2024-2025-1", "name": "2024-2025学年第一学期"},
    {"code": "2024-2025-2", "name": "2024-2025学年第二学期"},
    {"code": "2023-2024-1", "name": "2023-2024学年第一学期"},
    {"code": "2023-2024-2", "name": "2023-2024学年第二学期"},
    {"code": "2022-2023-1", "name": "2022-2023学年第一学期"},
    {"code": "2022-2023-2", "name": "2022-2023学年第二学期"},
]


# ============== 课程性质 ==============
COURSE_NATURES = [
    {"code": "", "name": "全部"},
    {"code": "01", "name": "必修"},
    {"code": "02", "name": "选修"},
    {"code": "03", "name": "通识必修"},
    {"code": "04", "name": "通识选修"},
    {"code": "05", "name": "专业必修"},
    {"code": "06", "name": "专业选修"},
    {"code": "07", "name": "实践环节"},
]


# ============== 修读类别 ==============
STUDY_TYPES = [
    {"code": "0", "name": "主修课程", "description": "查询主修专业课程"},
    {"code": "1", "name": "辅修课程", "description": "查询辅修专业课程"},
]


# ============== 成绩显示方式 ==============
GRADE_DISPLAY_MODES = [
    {"code": "all", "name": "显示全部成绩", "description": "显示所有修读记录"},
    {"code": "max", "name": "显示最好成绩", "description": "只显示最高成绩记录"},
]


# ============== 考核方式 ==============
ASSESSMENT_METHODS = [
    {"code": "", "name": "全部"},
    {"code": "01", "name": "考试"},
    {"code": "02", "name": "考查"},
]


# ============== 星期映射 ==============
WEEKDAYS = [
    {"code": "1", "name": "周一"},
    {"code": "2", "name": "周二"},
    {"code": "3", "name": "周三"},
    {"code": "4", "name": "周四"},
    {"code": "5", "name": "周五"},
    {"code": "6", "name": "周六"},
    {"code": "7", "name": "周日"},
]


# ============== 节次 ==============
PERIODS = [
    {"code": "1-2", "name": "第一二节", "time": "08:00-09:40"},
    {"code": "3-4", "name": "第三四节", "time": "10:00-11:40"},
    {"code": "5-6", "name": "第五六节", "time": "14:00-15:40"},
    {"code": "7-8", "name": "第七八节", "time": "16:00-17:40"},
    {"code": "9-10", "name": "第九十节", "time": "19:00-20:40"},
    {"code": "11-12", "name": "第十一十二节", "time": "20:50-22:30"},
]

# ============== 周次 ==============
WEEKS = [{"code": str(i), "name": f"第{i}周"} for i in range(1, 31)]


class EducationOptions:
    """教务系统选项查询工具类，供AI调用"""

    @staticmethod
    def _format_semester(start_year: int, term: int) -> str:
        return f"{start_year}-{start_year + 1}-{term}"

    @staticmethod
    def _shift_semester(semester_code: str, offset: int) -> str:
        try:
            start_year, _, term = semester_code.split("-")
            start_year_int = int(start_year)
            term_int = int(term)
        except Exception:
            return semester_code

        current_index = start_year_int * 2 + (term_int - 1)
        shifted_index = current_index + offset
        shifted_start_year = shifted_index // 2
        shifted_term = 1 if shifted_index % 2 == 0 else 2
        return EducationOptions._format_semester(shifted_start_year, shifted_term)

    @staticmethod
    def _semester_year_hint(raw: str, current_semester: str) -> Optional[int]:
        import re

        explicit = re.search(r"(20\d{2})[-年]?(20\d{2})?", raw)
        if explicit:
            start_year = explicit.group(1)
            end_year = explicit.group(2)
            if start_year and end_year:
                try:
                    return int(start_year)
                except Exception:
                    return None
            if start_year:
                try:
                    year = int(start_year)
                    if year >= 2000:
                        current_start = int(current_semester.split("-")[0])
                        if year == current_start or year == current_start + 1:
                            return current_start
                        return year
                except Exception:
                    return None
        return None

    @staticmethod
    def get_departments(include_admin: bool = False, include_vocational: bool = False) -> List[Dict]:
        """
        获取院系列表
        
        Args:
            include_admin: 是否包含职能部门
            include_vocational: 是否包含联合培养学院（高职）
        
        Returns:
            院系列表，包含code和name
        """
        result = DEPARTMENTS.copy()
        if include_admin:
            result.extend(ADMIN_DEPARTMENTS)
        if include_vocational:
            result.extend(VOCATIONAL_COLLEGES)
        return result

    @staticmethod
    def get_department_by_name(name: str) -> Optional[Dict]:
        """
        根据名称查找院系（支持模糊匹配）
        
        Args:
            name: 院系名称关键词
        
        Returns:
            匹配的院系信息，未找到返回None
        """
        all_depts = DEPARTMENTS + ADMIN_DEPARTMENTS + VOCATIONAL_COLLEGES
        for dept in all_depts:
            if name in dept["name"] or dept["name"] in name:
                return dept
        return None

    @staticmethod
    def get_department_by_code(code: str) -> Optional[Dict]:
        """
        根据代码查找院系
        
        Args:
            code: 院系代码
        
        Returns:
            匹配的院系信息，未找到返回None
        """
        all_depts = DEPARTMENTS + ADMIN_DEPARTMENTS + VOCATIONAL_COLLEGES
        for dept in all_depts:
            if dept["code"] == code or dept.get("full_code") == code:
                return dept
        return None

    @staticmethod
    def get_grades() -> List[str]:
        """获取年级列表"""
        return GRADES

    @staticmethod
    def get_semesters() -> List[Dict]:
        """获取学期列表（动态生成，避免年份写死失效）"""
        current = EducationOptions.get_current_semester()
        result = []
        for offset in range(1, -7, -1):
            code = EducationOptions._shift_semester(current, offset)
            try:
                _, _, term = code.split("-")
            except Exception:
                term = "1"
            name = code.replace("-", "-").rsplit("-", 1)[0] + ("学年第一学期" if term == "1" else "学年第二学期")
            result.append({"code": code, "name": name})
        return result

    @staticmethod
    def get_current_semester() -> str:
        """获取当前学期（根据当前时间推断）"""
        now = datetime.now()
        year = now.year
        month = now.month
        
        # 2-7月为第二学期，8-次年1月为第一学期
        if 2 <= month <= 7:
            return f"{year-1}-{year}-2"
        else:
            return f"{year}-{year+1}-1"

    @staticmethod
    def get_relative_semester(offset: int = 0) -> str:
        current = EducationOptions.get_current_semester()
        return EducationOptions._shift_semester(current, offset)

    @staticmethod
    def resolve_semester_reference(text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""

        import re

        explicit = re.search(r"(20\d{2}-20\d{2}-[12])", raw)
        if explicit:
            return explicit.group(1)

        current = EducationOptions.get_current_semester()
        lowered = raw.lower()
        if any(token in lowered for token in ["上上学期", "前两学期"]):
            return EducationOptions.get_relative_semester(-2)
        if any(token in lowered for token in ["下下学期", "后两学期"]):
            return EducationOptions.get_relative_semester(2)
        if any(token in lowered for token in ["本学期", "这学期", "当前学期", "最近学期"]):
            return current
        if any(token in lowered for token in ["上学期", "上一学期"]):
            return EducationOptions.get_relative_semester(-1)
        if any(token in lowered for token in ["下学期", "下一学期"]):
            return EducationOptions.get_relative_semester(1)
        if any(token in lowered for token in ["本学年第一学期", "这学年第一学期", "当前学年第一学期"]):
            try:
                start_year = int(current.split("-")[0])
            except Exception:
                return ""
            return EducationOptions._format_semester(start_year, 1)
        if any(token in lowered for token in ["本学年第二学期", "这学年第二学期", "当前学年第二学期"]):
            try:
                start_year = int(current.split("-")[0])
            except Exception:
                return ""
            return EducationOptions._format_semester(start_year, 2)

        year_hint = EducationOptions._semester_year_hint(raw, current)
        if "第一学期" in raw:
            try:
                start_year = year_hint if year_hint is not None else int(current.split("-")[0])
            except Exception:
                return ""
            if current.endswith("-1"):
                return current
            return EducationOptions._format_semester(start_year, 1)
        if "第二学期" in raw:
            try:
                start_year = year_hint if year_hint is not None else int(current.split("-")[0])
            except Exception:
                return ""
            return EducationOptions._format_semester(start_year, 2)
        return ""

    @staticmethod
    def get_time_context() -> Dict[str, str]:
        today = datetime.now()
        current = EducationOptions.get_current_semester()
        return {
            "today": today.strftime("%Y-%m-%d"),
            "current_semester": current,
            "previous_semester": EducationOptions.get_relative_semester(-1),
            "next_semester": EducationOptions.get_relative_semester(1),
        }

    @staticmethod
    def get_course_natures() -> List[Dict]:
        """获取课程性质列表"""
        return COURSE_NATURES

    @staticmethod
    def get_study_types() -> List[Dict]:
        """获取修读类别列表"""
        return STUDY_TYPES

    @staticmethod
    def get_grade_display_modes() -> List[Dict]:
        """获取成绩显示方式列表"""
        return GRADE_DISPLAY_MODES

    @staticmethod
    def get_assessment_methods() -> List[Dict]:
        """获取考核方式列表"""
        return ASSESSMENT_METHODS

    @staticmethod
    def get_weekdays() -> List[Dict]:
        """获取星期列表"""
        return WEEKDAYS

    @staticmethod
    def get_periods() -> List[Dict]:
        """获取节次列表"""
        return PERIODS

    @staticmethod
    def get_weeks() -> List[Dict]:
        """获取周次列表"""
        return WEEKS

    @staticmethod
    def get_all_options() -> Dict:
        """获取所有选项数据（用于AI初始化）"""
        return {
            "院系": EducationOptions.get_departments(),
            "年级": EducationOptions.get_grades(),
            "学期": EducationOptions.get_semesters(),
            "课程性质": EducationOptions.get_course_natures(),
            "修读类别": EducationOptions.get_study_types(),
            "成绩显示方式": EducationOptions.get_grade_display_modes(),
            "考核方式": EducationOptions.get_assessment_methods(),
            "星期": EducationOptions.get_weekdays(),
            "节次": EducationOptions.get_periods(),
            "周次": EducationOptions.get_weeks(),
        }


# ============== AI工具函数 ==============

def query_departments(keyword: str = "") -> List[Dict]:
    """
    AI工具：查询院系信息
    
    当用户询问"有哪些学院"、"XX学院是哪个"等问题时调用
    
    Args:
        keyword: 搜索关键词，为空返回所有院系
    
    Returns:
        匹配的院系列表
    """
    if not keyword:
        return EducationOptions.get_departments()
    
    result = []
    all_depts = EducationOptions.get_departments(include_admin=True, include_vocational=True)
    
    for dept in all_depts:
        if keyword in dept["name"] or dept["name"] in keyword or keyword == dept["code"]:
            result.append(dept)
    
    return result


def query_semesters(include_past: bool = True, include_future: bool = False) -> List[Dict]:
    """
    AI工具：查询学期信息
    
    当用户询问"有哪些学期"、"当前学期是什么"等问题时调用
    
    Args:
        include_past: 是否包含过去的学期
        include_future: 是否包含未来的学期
    
    Returns:
        学期列表
    """
    semesters = EducationOptions.get_semesters()
    current = EducationOptions.get_current_semester()
    
    if not include_past and not include_future:
        # 只返回当前学期
        for sem in semesters:
            if sem["code"] == current:
                return [sem]
        return []
    
    if include_past and include_future:
        return semesters
    
    # 根据当前学期筛选
    result = []
    current_idx = None
    for i, sem in enumerate(semesters):
        if sem["code"] == current:
            current_idx = i
            break
    
    if current_idx is not None:
        if include_past:
            result = semesters[current_idx:]
        elif include_future:
            result = semesters[:current_idx+1]
    
    return result


def query_course_options() -> Dict:
    """
    AI工具：查询课程相关选项
    
    当用户询问课程性质、修读类别等问题时调用
    
    Returns:
        课程相关选项
    """
    return {
        "课程性质": EducationOptions.get_course_natures(),
        "修读类别": EducationOptions.get_study_types(),
        "考核方式": EducationOptions.get_assessment_methods(),
    }


def query_schedule_options() -> Dict:
    """
    AI工具：查询课表相关选项
    
    当用户询问上课时间、课表安排等问题时调用
    
    Returns:
        课表相关选项
    """
    return {
        "星期": EducationOptions.get_weekdays(),
        "节次": EducationOptions.get_periods(),
        "学期": EducationOptions.get_semesters(),
    }


def query_grade_options() -> Dict:
    """
    AI工具：查询成绩查询相关选项
    
    当用户询问如何查询成绩、成绩显示方式等问题时调用
    
    Returns:
        成绩查询相关选项
    """
    return {
        "成绩显示方式": EducationOptions.get_grade_display_modes(),
        "修读类别": EducationOptions.get_study_types(),
        "学期": EducationOptions.get_semesters(),
    }


def get_option_description(option_type: str, code: str) -> str:
    """
    获取选项的详细描述
    
    Args:
        option_type: 选项类型，如"department", "semester", "course_nature"等
        code: 选项代码
    
    Returns:
        选项描述
    """
    if option_type == "department":
        dept = EducationOptions.get_department_by_code(code)
        return dept["name"] if dept else "未知院系"
    
    elif option_type == "semester":
        for sem in EducationOptions.get_semesters():
            if sem["code"] == code:
                return sem["name"]
        return code
    
    elif option_type == "course_nature":
        for nature in COURSE_NATURES:
            if nature["code"] == code:
                return nature["name"]
        return "全部"
    
    elif option_type == "study_type":
        for st in STUDY_TYPES:
            if st["code"] == code:
                return st["name"]
        return "主修课程"
    
    elif option_type == "grade_display":
        for mode in GRADE_DISPLAY_MODES:
            if mode["code"] == code:
                return mode["name"]
        return "显示全部成绩"
    
    return code
