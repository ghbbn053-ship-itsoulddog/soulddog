"""
教务系统数据爬虫模块
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class JwxtScraper:
    """教务系统爬虫"""

    def __init__(self, session: requests.Session = None, base_url: str = "http://jwxt.gdufe.edu.cn"):
        self.session = session or requests.Session()
        self.base_url = base_url
        self.captcha_url = f"{base_url}/jsxsd/verifycode.servlet"
        self.login_url = f"{base_url}/jsxsd/xk/LoginToXkLdap"

    def get_captcha(self) -> bytes:
        """获取验证码图片"""
        try:
            response = self.session.get(self.captcha_url, timeout=10)
            response.raise_for_status()
            logger.info("成功获取验证码")
            return response.content
        except Exception as e:
            logger.error(f"获取验证码失败: {str(e)}")
            raise

    def login(self, username: str, password: str, captcha: str) -> Dict:
        """登录教务系统（内网版本，明文密码）"""
        try:
            data = {
                "USERNAME": username,
                "PASSWORD": password,
                "RANDOMCODE": captcha
            }
            
            response = self.session.post(self.login_url, data=data, timeout=10)
            response.encoding = response.apparent_encoding
            
            if "密码错误" in response.text or "验证码错误" in response.text:
                return {"success": False, "message": "用户名、密码或验证码错误"}
            
            if "xsMain.jsp" in response.text or "framework" in response.url:
                logger.info(f"用户 {username} 登录成功")
                return {"success": True, "message": "登录成功"}
            
            if "LoginToXkLdap" in response.text:
                return {"success": False, "message": "登录失败，请检查账号密码"}
            
            return {"success": True, "message": "登录成功"}
            
        except Exception as e:
            logger.error(f"登录失败: {str(e)}")
            return {"success": False, "message": f"登录异常: {str(e)}"}

    def get_personal_info(self) -> Dict:
        """
        获取个人信息
        从主页面解析姓名、学号等基本信息
        """
        try:
            url = f"{self.base_url}/jsxsd/framework/xsMain.jsp"
            response = self.session.get(url, timeout=10)
            # 自动检测编码
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取姓名和学号
            login_name_div = soup.find(id="Top1_divLoginName")
            if login_name_div:
                login_name = login_name_div.get_text(strip=True)
                # 格式：张靖(24251102121)
                if '(' in login_name and ')' in login_name:
                    name = login_name.split('(')[0]
                    student_id = login_name.split('(')[1].split(')')[0]
                else:
                    name = login_name
                    student_id = ""
            else:
                name = ""
                student_id = ""

            # 提取主页面的个人信息块
            personal_info = {
                "name": name,
                "student_id": student_id,
                "major": "",
                "class": "",
                "department": ""
            }

            # 从个人信息块提取更多信息
            info_text = soup.get_text()
            logger.info(f"成功获取基本信息: {personal_info}")

            return {
                "success": True,
                "data": personal_info
            }

        except Exception as e:
            logger.error(f"获取个人信息失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取个人信息失败: {str(e)}"
            }

    def get_student_card(self) -> Dict:
        """
        获取学籍卡片详细信息
        URL: /jsxsd/grxx/xsxx
        """
        try:
            url = f"{self.base_url}/jsxsd/grxx/xsxx"
            response = self.session.get(url, timeout=10)
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')

            # 解析学籍卡片信息
            # 查找包含学籍信息的表格
            info_table = soup.find('table', class_='Nsb_table_r')
            student_card = {}

            if info_table:
                rows = info_table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        student_card[key] = value

            logger.info(f"成功获取学籍卡片: {student_card}")

            return {
                "success": True,
                "data": student_card
            }

        except Exception as e:
            logger.error(f"获取学籍卡片失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取学籍卡片失败: {str(e)}"
            }

    def get_grades(self, kksj: str = "", kcxz: str = "", kcmc: str = "",
                   fxkc: str = "0", xsfs: str = "all") -> Dict:
        """
        获取成绩列表
        参数:
        - kksj: 开课时间
        - kcxz: 课程性质
        - kcmc: 课程名称
        - fxkc: 修读类别 (0=主修课程, 1=辅修课程)
        - xsfs: 显示方式 (all=显示全部成绩, max=显示最好成绩)
        """
        try:
            # 构建查询参数
            params = {
                "kksj": kksj,
                "kcxz": kcxz,
                "kcmc": kcmc,
                "fxkc": fxkc,
                "xsfs": xsfs
            }

            # 提交成绩查询
            url = f"{self.base_url}/jsxsd/kscj/cjcx_list"
            response = self.session.post(url, data=params, timeout=10)
            # 自动检测编码
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')

            # 解析成绩表格 - 根据实际HTML结构，表格ID为dataList
            grade_table = soup.find('table', id='dataList')

            if not grade_table:
                logger.warning("未找到成绩表格")
                return {
                    "success": True,
                    "data": [],
                    "count": 0
                }

            # 提取数据行
            grades = []
            rows = grade_table.find_all('tr')[1:]  # 跳过表头行
            for row in rows:
                cells = row.find_all('td')
                if cells and len(cells) >= 10:
                    grade_data = {
                        "序号": cells[0].get_text(strip=True),
                        "开课学期": cells[1].get_text(strip=True),
                        "课程编号": cells[2].get_text(strip=True),
                        "课程名称": cells[3].get_text(strip=True),
                        "平时成绩": cells[4].get_text(strip=True),
                        "实验成绩": cells[5].get_text(strip=True),
                        "期末成绩": cells[6].get_text(strip=True),
                        "成绩": cells[7].get_text(strip=True),
                        "学分": cells[8].get_text(strip=True),
                        "总学时": cells[9].get_text(strip=True),
                        "考核方式": cells[10].get_text(strip=True) if len(cells) > 10 else "",
                        "课程属性": cells[11].get_text(strip=True) if len(cells) > 11 else "",
                        "课程性质": cells[12].get_text(strip=True) if len(cells) > 12 else "",
                        "通选课分类": cells[13].get_text(strip=True) if len(cells) > 13 else "",
                        "考试性质": cells[14].get_text(strip=True) if len(cells) > 14 else "",
                        "成绩标识": cells[15].get_text(strip=True) if len(cells) > 15 else "",
                        "备注": cells[16].get_text(strip=True) if len(cells) > 16 else ""
                    }
                    grades.append(grade_data)

            # 提取统计信息
            stats = self._extract_grade_stats(soup)

            logger.info(f"成功获取 {len(grades)} 条成绩记录")

            return {
                "success": True,
                "data": grades,
                "count": len(grades),
                "stats": stats
            }

        except Exception as e:
            logger.error(f"获取成绩失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取成绩失败: {str(e)}"
            }

    def _extract_grade_stats(self, soup: BeautifulSoup) -> Dict:
        """
        从成绩页面提取统计信息
        """
        import re
        stats = {
            "total_credits_required": 0,
            "credits_exempted": 0,
            "credits_completed": 0,
            "credits_remaining": 0,
            "gpa_major": 0.0,
            "rank": "",
            "gpa_minor": 0.0
        }

        try:
            page_text = soup.get_text()

            match = re.search(r'一共需要修读\s*(\d+)\s*学分', page_text)
            if match:
                stats["total_credits_required"] = int(match.group(1))

            match = re.search(r'免修\s*(\d+)\s*学分', page_text)
            if match:
                stats["credits_exempted"] = int(match.group(1))

            match = re.search(r'已修读\s*(\d+)\s*学分', page_text)
            if match:
                stats["credits_completed"] = int(match.group(1))

            match = re.search(r'还需修读\s*(\d+)\s*学分', page_text)
            if match:
                stats["credits_remaining"] = int(match.group(1))

            match = re.search(r'主修课程平均学分绩点\s*([\d.]+)', page_text)
            if match:
                stats["gpa_major"] = float(match.group(1))

            match = re.search(r'在专业\s*(\d+)\s*名学生中排名\s*(\d+)', page_text)
            if match:
                stats["rank"] = f"{match.group(2)}/{match.group(1)}"

            match = re.search(r'辅修课程平均学分绩点\s*([\d.]+)', page_text)
            if match:
                stats["gpa_minor"] = float(match.group(1))

        except Exception as e:
            logger.warning(f"提取成绩统计信息失败: {str(e)}")

        return stats

    def get_all_grades(self) -> Dict:
        """
        获取所有成绩（不限条件）
        """
        return self.get_grades(
            kksj="",
            kcxz="",
            kcmc="",
            fxkc="0",
            xsfs="all"
        )

    def get_schedule(self, semester: str = "", week: str = "") -> Dict:
        """
        获取学期课表
        参数:
        - semester: 学期，如 "2024-2025-2"，为空则获取当前学期
        - week: 周次，如 "1", "2"，为空则获取全部
        返回: 课程列表，包含课程名称、时间、地点、教师等信息
        """
        try:
            # 课表查询页面
            url = f"{self.base_url}/jsxsd/xskb/xskb_list.do"

            # 构建表单数据
            data = {}
            if semester:
                data["xnxq01id"] = semester
            if week:
                data["zc"] = week

            # 提交查询
            if data:
                response = self.session.post(url, data=data, timeout=10)
            else:
                response = self.session.get(url, timeout=10)

            # 自动检测编码
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找课表表格
            schedule_table = soup.find('table', id='kbtable')

            if not schedule_table:
                logger.warning("未找到课表表格")
                return {
                    "success": True,
                    "data": [],
                    "count": 0,
                    "semester": semester,
                    "week": week
                }

            # 解析课表
            courses = []
            rows = schedule_table.find_all('tr')[1:]  # 跳过表头

            # 节次映射
            period_map = {
                "第一二节": "1-2",
                "第三四节": "3-4",
                "第五六节": "5-6",
                "第七八节": "7-8",
                "第九十节": "9-10",
                "第十一十二节": "11-12"
            }

            for row in rows:
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 8:
                    # 节次信息 (第一二节、第三四节等)
                    period_text = cells[0].get_text(strip=True)
                    period = period_map.get(period_text, period_text)

                    # 遍历每天的课程 (周一到周日)
                    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                    for i, cell in enumerate(cells[1:8], 1):
                        # 查找课程div - 使用kbcontent1（简略版）
                        course_divs = cell.find_all('div', class_='kbcontent1')

                        for div in course_divs:
                            # 获取HTML内容
                            html_content = str(div)

                            # 跳过空课程
                            if '&nbsp;' in html_content or not div.get_text(strip=True):
                                continue

                            # 解析课程信息
                            # 课程可能有多门，用----------------------分隔
                            courses_text = div.get_text(separator='\n', strip=True)

                            # 分割多门课程
                            course_blocks = courses_text.split('----------------------')

                            for block in course_blocks:
                                if not block.strip():
                                    continue

                                # 解析单个课程
                                lines = [line.strip() for line in block.strip().split('\n') if line.strip()]

                                if not lines:
                                    continue

                                course_name = lines[0] if lines else ""

                                # 提取周次、教室、节次
                                weeks = ""
                                location = ""
                                sections = ""

                                for line in lines[1:]:
                                    if '周)' in line or '(周)' in line:
                                        # 周次信息: 1-16(周) 或 1-16(双周) 或 6,8,11,13(周)
                                        weeks = line.replace('(周)', '').replace('周)', '').strip()
                                    elif '教室' in line or '楼' in line or '(' in line:
                                        # 教室信息: 笃行楼(SJ2)114
                                        location = line.strip()
                                    elif '节' in line and '[' in line:
                                        # 节次信息: [01-02]节
                                        sections = line.strip()

                                # 查找对应的详细div获取教师信息
                                teacher = ""
                                # 获取div的id
                                div_id = div.get('id', '')
                                if div_id:
                                    # 详细版div的id类似，但class是kbcontent
                                    detailed_div = soup.find('div', id=div_id, class_='kbcontent')
                                    if detailed_div:
                                        detailed_text = detailed_div.get_text()
                                        # 提取教师信息
                                        import re
                                        teacher_match = re.search(r'老师[：:]([^\n]+)', detailed_text)
                                        if teacher_match:
                                            teacher = teacher_match.group(1).strip()

                                course_data = {
                                    "课程名称": course_name,
                                    "星期": days[i-1],
                                    "星期代码": i,
                                    "节次": period,
                                    "教师": teacher,
                                    "地点": location,
                                    "周次": weeks,
                                    "节次信息": sections
                                }
                                courses.append(course_data)

            # 提取备注信息（未安排时间的课程）
            remark_row = schedule_table.find('tr')
            remarks = []
            if remark_row:
                remark_cells = remark_row.find_all('td', colspan='7')
                if remark_cells:
                    remark_text = remark_cells[0].get_text(strip=True)
                    if '未安排时间课程' in remark_text:
                        import re
                        # 提取课程名称
                        courses_match = re.findall(r'：([^；]+)', remark_text)
                        if courses_match:
                            remarks = [c.strip() for c in courses_match[0].split('；') if c.strip()]

            logger.info(f"成功获取 {len(courses)} 门课程")

            return {
                "success": True,
                "data": courses,
                "count": len(courses),
                "semester": semester,
                "week": week,
                "未安排时间课程": remarks
            }

        except Exception as e:
            logger.error(f"获取课表失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取课表失败: {str(e)}"
            }

    def get_training_plan(self, department: str = "", grade: str = "", major: str = "") -> Dict:
        """
        获取专业培养方案
        参数:
        - department: 院系代码 (xsyx)
        - grade: 年级 (xsnj)，如 "2024"
        - major: 专业代码 (xszy)
        返回: 培养方案详情，包含课程列表和学分要求
        """
        try:
            # 如果提供了完整参数，直接查询结果
            if department and grade and major:
                url = f"{self.base_url}/jsxsd/jspyfa/zypyfa_query"
                data = {
                    "xsyx": department,
                    "xsnj": grade,
                    "xszy": major
                }
                response = self.session.post(url, data=data, timeout=10)
            else:
                # 否则获取查询页面
                url = f"{self.base_url}/jsxsd/jspyfa/pyfa_find"
                response = self.session.get(url, timeout=10)

            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')

            # 解析培养方案信息
            plan_info = {
                "专业名称": "",
                "年级": grade,
                "院系": "",
                "总学分要求": 0,
                "课程列表": []
            }

            # 提取标题信息
            title = soup.find('font', style=lambda x: x and 'font-size:16px' in x)
            if title:
                plan_info["专业名称"] = title.get_text(strip=True)

            # 查找课程表格
            course_table = soup.find('table', id='mxh')
            if course_table:
                rows = course_table.find_all('tr')[3:]  # 跳过表头

                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 10:
                        course_data = {
                            "课程类别": cells[0].get_text(strip=True),
                            "课程性质": cells[1].get_text(strip=True),
                            "课程模块": cells[2].get_text(strip=True),
                            "课程代码": cells[3].get_text(strip=True),
                            "课程名称": cells[4].get_text(strip=True),
                            "学分": cells[5].get_text(strip=True),
                            "授课周数": cells[6].get_text(strip=True),
                            "总学时": cells[7].get_text(strip=True),
                            "理论学时": cells[8].get_text(strip=True),
                            "实验学时": cells[9].get_text(strip=True) if len(cells) > 9 else "",
                            "建议修读学期": cells[12].get_text(strip=True) if len(cells) > 12 else "",
                            "是否辅修": cells[13].get_text(strip=True) if len(cells) > 13 else "",
                            "考核方式": cells[14].get_text(strip=True) if len(cells) > 14 else ""
                        }
                        plan_info["课程列表"].append(course_data)

            # 提取学分统计
            stats_text = soup.get_text()
            import re
            credit_match = re.search(r'应修满\s*(\d+)\s*学分', stats_text)
            if credit_match:
                plan_info["总学分要求"] = int(credit_match.group(1))

            logger.info(f"成功获取培养方案，共 {len(plan_info['课程列表'])} 门课程")

            return {
                "success": True,
                "data": plan_info,
                "count": len(plan_info["课程列表"])
            }

        except Exception as e:
            logger.error(f"获取培养方案失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取培养方案失败: {str(e)}"
            }

    def get_my_training_plan(self) -> Dict:
        """
        获取"我的培养方案"（当前登录学生）
         URL: /jsxsd/pyfa/pyfazd_query
        返回详细的培养方案，包括课程类别、模块、学分要求等
        """
        try:
            url = f"{self.base_url}/jsxsd/pyfa/pyfazd_query"
            response = self.session.get(url, timeout=10)
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')

            # 解析个人培养方案
            plan_data = {
                "基本信息": {},
                "课程列表": [],
                "学分统计": {
                    "总学分要求": 0,
                    "已修学分": 0,
                    "还需学分": 0
                }
            }

            # 提取专业名称和版本
            title_font = soup.find('font', style=lambda x: x and 'font-size:16px' in x)
            if title_font:
                plan_data["基本信息"]["专业版本"] = title_font.get_text(strip=True)

            # 提取学院名称
            college_match = soup.find('span', style=lambda x: x and 'font-size: 20pt' in x)
            if college_match:
                plan_data["基本信息"]["学院"] = college_match.get_text(strip=True).replace('学院', '').strip()

            # 查找课程表格 - 使用id='mxh'的表格
            course_table = soup.find('table', id='mxh')
            if course_table:
                rows = course_table.find_all('tr')

                current_category = ""  # 当前课程类别
                current_nature = ""    # 当前课程性质
                current_module = ""    # 当前课程模块

                for row in rows:
                    cells = row.find_all(['td', 'th'])

                    # 检查是否是表头行
                    if row.find('th'):
                        continue

                    # 检查是否有rowspan（表示新的类别）
                    category_cell = row.find('td', style=lambda x: x and 'width:1%' in x if x else False)
                    if category_cell and category_cell.get('rowspan'):
                        current_category = category_cell.get_text(strip=True)

                    # 提取课程数据
                    if len(cells) >= 12:
                        # 尝试提取各个字段
                        try:
                            # 课程代码通常在第4个位置（索引3）
                            course_code = cells[3].get_text(strip=True) if len(cells) > 3 else ""

                            # 如果这一行有课程代码，说明是课程数据行
                            if course_code and len(course_code) > 5:
                                course = {
                                    "课程类别": current_category,
                                    "课程性质": cells[1].get_text(strip=True) if len(cells) > 1 and cells[1].get('rowspan') else current_nature,
                                    "课程模块": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                                    "课程代码": course_code,
                                    "课程名称": cells[4].get_text(strip=True) if len(cells) > 4 else "",
                                    "学分": cells[5].get_text(strip=True) if len(cells) > 5 else "",
                                    "授课周数": cells[6].get_text(strip=True) if len(cells) > 6 else "",
                                    "总学时": cells[7].get_text(strip=True) if len(cells) > 7 else "",
                                    "理论学时": cells[8].get_text(strip=True) if len(cells) > 8 else "",
                                    "实验学时": cells[9].get_text(strip=True) if len(cells) > 9 else "",
                                    "实习学时": cells[10].get_text(strip=True) if len(cells) > 10 else "",
                                    "其他学时": cells[11].get_text(strip=True) if len(cells) > 11 else "",
                                    "建议修读学期": cells[12].get_text(strip=True) if len(cells) > 12 else "",
                                    "是否适用辅修": cells[13].get_text(strip=True) if len(cells) > 13 else "",
                                    "考核方式": cells[14].get_text(strip=True) if len(cells) > 14 else ""
                                }
                                plan_data["课程列表"].append(course)
                        except Exception as e:
                            logger.warning(f"解析课程行失败: {str(e)}")
                            continue

            # 提取学分统计信息
            page_text = soup.get_text()
            import re

            # 查找学分统计
            credit_patterns = [
                r'应修满\s*(\d+)\s*学分',
                r'总学分[:：]\s*(\d+)',
                r'最低毕业学分[:：]\s*(\d+)'
            ]
            for pattern in credit_patterns:
                match = re.search(pattern, page_text)
                if match:
                    plan_data["学分统计"]["总学分要求"] = int(match.group(1))
                    break

            # 计算已修学分（从课程列表中统计）
            total_credits = 0
            for course in plan_data["课程列表"]:
                try:
                    credit = float(course.get("学分", 0) or 0)
                    total_credits += credit
                except:
                    pass
            plan_data["学分统计"]["计划学分"] = total_credits

            logger.info(f"成功获取我的培养方案，共 {len(plan_data['课程列表'])} 门课程")

            return {
                "success": True,
                "data": plan_data,
                "count": len(plan_data["课程列表"])
            }

        except Exception as e:
            logger.error(f"获取我的培养方案失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取我的培养方案失败: {str(e)}"
            }

    def get_academic_progress(self, study_type: str = "0") -> Dict:
        """
        获取学业进度查询
        参数:
        - study_type: 修读类型 (0=主修, 1=辅修)
        返回: 学业完成情况，包括各模块学分要求与已修学分
        """
        try:
            url = f"{self.base_url}/jsxsd/pyfa/xyjdcx"

            # 如果有study_type参数，提交表单查询
            if study_type:
                data = {"xdlx": study_type}
                response = self.session.post(f"{url}?type=cx", data=data, timeout=10)
            else:
                response = self.session.get(url, timeout=10)

            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')

            progress_data = {
                "修读类型": "主修" if study_type == "0" else "辅修" if study_type == "1" else "未知",
                "总学分要求": 0,
                "已获学分": 0,
                "还需学分": 0,
                "课程列表": []
            }

            # 提取标题中的学分信息
            title_th = soup.find('th', colspan="7")
            if title_th:
                import re
                credit_match = re.search(r'需修读总学分[:：]\s*(\d+)', title_th.get_text())
                if credit_match:
                    progress_data["总学分要求"] = int(credit_match.group(1))

            # 查找课程表格 - 使用class='Nsb_r_list Nsb_table'
            progress_table = soup.find('table', class_=lambda x: x and 'Nsb_r_list' in x if x else False)
            if progress_table:
                rows = progress_table.find_all('tr')[2:]  # 跳过表头（2行表头）

                total_earned = 0

                for row in rows:
                    cells = row.find_all('td')

                    # 检查是否是合计行
                    if len(cells) == 3 and '合计' in cells[0].get_text():
                        try:
                            progress_data["已获学分"] = float(cells[2].get_text(strip=True) or 0)
                        except:
                            pass
                        continue

                    # 解析课程行
                    if len(cells) >= 7:
                        try:
                            course_data = {
                                "课程性质": cells[0].get_text(strip=True),
                                "课程代码": cells[1].get_text(strip=True),
                                "课程名称": cells[2].get_text(strip=True),
                                "学分": cells[3].get_text(strip=True),
                                "建议修读学期": cells[4].get_text(strip=True),
                                "免听免修": cells[5].get_text(strip=True),
                                "已获学分": cells[6].get_text(strip=True)
                            }

                            # 累加已获学分
                            earned = cells[6].get_text(strip=True)
                            if earned:
                                try:
                                    total_earned += float(earned)
                                except:
                                    pass

                            progress_data["课程列表"].append(course_data)
                        except Exception as e:
                            logger.warning(f"解析课程行失败: {str(e)}")
                            continue

                # 计算还需学分
                if progress_data["总学分要求"] > 0:
                    progress_data["还需学分"] = progress_data["总学分要求"] - progress_data["已获学分"]

            logger.info(f"成功获取学业进度({progress_data['修读类型']})，共 {len(progress_data['课程列表'])} 门课程")

            return {
                "success": True,
                "data": progress_data,
                "count": len(progress_data["课程列表"])
            }

        except Exception as e:
            logger.error(f"获取学业进度失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取学业进度失败: {str(e)}"
            }

    def get_exam_schedule(self, semester: str = "") -> Dict:
        """
        获取考试安排
        参数:
        - semester: 学期，如 "2024-2025-1"
        返回: 考试安排列表
        """
        try:
            url = f"{self.base_url}/jsxsd/xsks/xsksap_query"
            params = {}
            if semester:
                params["xnxqid"] = semester

            response = self.session.get(url, params=params, timeout=10)
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找考试安排表格
            exam_table = soup.find('table', id='dataList')

            if not exam_table:
                logger.warning("未找到考试安排表格")
                return {
                    "success": True,
                    "data": [],
                    "count": 0,
                    "semester": semester
                }

            exams = []
            rows = exam_table.find_all('tr')[1:]  # 跳过表头

            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 8:
                    exam_data = {
                        "序号": cells[0].get_text(strip=True),
                        "课程名称": cells[1].get_text(strip=True),
                        "考试时间": cells[2].get_text(strip=True),
                        "考试地点": cells[3].get_text(strip=True),
                        "座位号": cells[4].get_text(strip=True),
                        "考试方式": cells[5].get_text(strip=True),
                        "考试性质": cells[6].get_text(strip=True),
                        "状态": cells[7].get_text(strip=True)
                    }
                    exams.append(exam_data)

            logger.info(f"成功获取 {len(exams)} 条考试安排")

            return {
                "success": True,
                "data": exams,
                "count": len(exams),
                "semester": semester
            }

        except Exception as e:
            logger.error(f"获取考试安排失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取考试安排失败: {str(e)}"
            }

    def search_teacher(self, name: str = "", department: str = "") -> Dict:
        """
        查询教师信息（增强版）
        参数:
        - name: 教师姓名（支持模糊查询，为空则查询所有）
        - department: 所属院系代码（可选）
        返回: 教师列表
        """
        try:
            # 构建查询参数
            data = {}
            if name:
                data["jsxm"] = name
            if department:
                data["kkyx"] = department

            # 提交查询
            url = f"{self.base_url}/jsxsd/jsxx/jsxx_list"
            response = self.session.post(url, data=data, timeout=10)
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找教师列表表格
            teacher_table = soup.find('table', class_='Nsb_r_list')

            if not teacher_table:
                logger.warning("未找到教师列表表格")
                return {
                    "success": True,
                    "data": [],
                    "count": 0
                }

            # 提取教师数据
            teachers = []
            rows = teacher_table.find_all('tr')[1:]  # 跳过表头

            for row in rows:
                cells = row.find_all('td')
                if cells and len(cells) >= 4:
                    # 提取详情链接中的教师ID
                    detail_link = cells[4].find('a') if len(cells) > 4 else None
                    teacher_id = ""
                    detail_url = ""
                    if detail_link and 'href' in detail_link.attrs:
                        href = detail_link['href']
                        detail_url = href if href.startswith('http') else f"{self.base_url}{href}"
                        if 'jg0101id=' in href:
                            teacher_id = href.split('jg0101id=')[1].split('&')[0]

                    teacher_data = {
                        "序号": cells[0].get_text(strip=True),
                        "教职工号": cells[1].get_text(strip=True),
                        "教师姓名": cells[2].get_text(strip=True),
                        "所属院系": cells[3].get_text(strip=True),
                        "教师ID": teacher_id,
                        "详情链接": detail_url
                    }
                    teachers.append(teacher_data)

            logger.info(f"成功获取 {len(teachers)} 条教师记录")

            return {
                "success": True,
                "data": teachers,
                "count": len(teachers)
            }

        except Exception as e:
            logger.error(f"查询教师信息失败: {str(e)}")
            return {
                "success": False,
                "message": f"查询教师信息失败: {str(e)}"
            }

    def get_teacher_detail(self, teacher_id: str) -> Dict:
        """
        获取教师详细信息
        参数:
        - teacher_id: 教师ID (jg0101id)
        返回: 教师详细信息
        """
        try:
            url = f"{self.base_url}/jsxsd/jsxx/jsxx_detail"
            params = {"jg0101id": teacher_id}

            response = self.session.get(url, params=params, timeout=10)
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')

            # 解析教师详细信息
            teacher_detail = {}

            info_table = soup.find('table', class_='Nsb_table')
            if info_table:
                rows = info_table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    for i in range(0, len(cells) - 1, 2):
                        if i + 1 < len(cells):
                            key = cells[i].get_text(strip=True)
                            value = cells[i+1].get_text(strip=True)
                            teacher_detail[key] = value

            logger.info(f"成功获取教师详情: {teacher_id}")

            return {
                "success": True,
                "data": teacher_detail
            }

        except Exception as e:
            logger.error(f"获取教师详情失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取教师详情失败: {str(e)}"
            }

    def search_course(self, course_name: str = "", course_code: str = "", department: str = "") -> Dict:
        """
        查询课程信息
        参数:
        - course_name: 课程名称（支持模糊查询）
        - course_code: 课程代码
        - department: 开课院系
        返回: 课程列表
        """
        try:
            # 课程课表查询页面
            url = f"{self.base_url}/jsxsd/kbcx/kbxx_kc"

            data = {}
            if course_name:
                data["kcmc"] = course_name
            if course_code:
                data["kch"] = course_code
            if department:
                data["kkyx"] = department

            response = self.session.post(url, data=data, timeout=10)
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找课程列表表格
            course_table = soup.find('table', class_='Nsb_r_list')

            if not course_table:
                logger.warning("未找到课程列表表格")
                return {
                    "success": True,
                    "data": [],
                    "count": 0
                }

            courses = []
            rows = course_table.find_all('tr')[1:]  # 跳过表头

            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 6:
                    # 提取课程详情链接
                    detail_link = cells[0].find('a')
                    course_id = ""
                    if detail_link and 'href' in detail_link.attrs:
                        href = detail_link['href']
                        if 'kch=' in href:
                            course_id = href.split('kch=')[1].split('&')[0]

                    course_data = {
                        "课程代码": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                        "课程名称": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                        "学分": cells[3].get_text(strip=True) if len(cells) > 3 else "",
                        "总学时": cells[4].get_text(strip=True) if len(cells) > 4 else "",
                        "课程性质": cells[5].get_text(strip=True) if len(cells) > 5 else "",
                        "开课院系": cells[6].get_text(strip=True) if len(cells) > 6 else "",
                        "课程ID": course_id
                    }
                    courses.append(course_data)

            logger.info(f"成功获取 {len(courses)} 条课程记录")

            return {
                "success": True,
                "data": courses,
                "count": len(courses)
            }

        except Exception as e:
            logger.error(f"查询课程信息失败: {str(e)}")
            return {
                "success": False,
                "message": f"查询课程信息失败: {str(e)}"
            }

    def get_course_selection_info(self) -> Dict:
        """
        获取选课信息（选课中心）
        返回: 可选课程列表和选课状态
        """
        try:
            url = f"{self.base_url}/jsxsd/xsxk/xklc_list"
            response = self.session.get(url, timeout=10)
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')

            selection_data = {
                "当前选课轮次": [],
                "可选课程": []
            }

            # 查找选课轮次
            round_table = soup.find('table', id='dataList')
            if round_table:
                rows = round_table.find_all('tr')[1:]
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 5:
                        round_info = {
                            "轮次名称": cells[1].get_text(strip=True),
                            "开始时间": cells[2].get_text(strip=True),
                            "结束时间": cells[3].get_text(strip=True),
                            "状态": cells[4].get_text(strip=True)
                        }
                        selection_data["当前选课轮次"].append(round_info)

            logger.info(f"成功获取选课信息")

            return {
                "success": True,
                "data": selection_data
            }

        except Exception as e:
            logger.error(f"获取选课信息失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取选课信息失败: {str(e)}"
            }

    def get_execution_plan(self) -> Dict:
        """
        获取执行计划（已选课程计划）
        返回: 执行计划详情
        """
        try:
            url = f"{self.base_url}/jsxsd/pyfa/pyfa_query"
            response = self.session.get(url, timeout=10)
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')

            plan_data = {
                "计划信息": {},
                "课程列表": []
            }

            # 查找计划信息
            info_table = soup.find('table', class_='Nsb_table')
            if info_table:
                rows = info_table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    for i in range(0, len(cells) - 1, 2):
                        if i + 1 < len(cells):
                            key = cells[i].get_text(strip=True)
                            value = cells[i+1].get_text(strip=True)
                            plan_data["计划信息"][key] = value

            # 查找课程列表
            course_table = soup.find('table', id='dataList')
            if course_table:
                rows = course_table.find_all('tr')[1:]
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 8:
                        course = {
                            "学年学期": cells[1].get_text(strip=True),
                            "课程代码": cells[2].get_text(strip=True),
                            "课程名称": cells[3].get_text(strip=True),
                            "学分": cells[4].get_text(strip=True),
                            "课程性质": cells[5].get_text(strip=True),
                            "考核方式": cells[6].get_text(strip=True),
                            "是否选课": cells[7].get_text(strip=True)
                        }
                        plan_data["课程列表"].append(course)

            logger.info(f"成功获取执行计划")

            return {
                "success": True,
                "data": plan_data,
                "count": len(plan_data["课程列表"])
            }

        except Exception as e:
            logger.error(f"获取执行计划失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取执行计划失败: {str(e)}"
            }

    def get_all_data_for_vectorization(self) -> Dict:
        """
        获取所有可用于向量化的数据
        这是为RAG系统准备的数据聚合接口
        返回: 包含所有类型数据的字典
        """
        try:
            logger.info("开始获取所有向量化数据...")

            all_data = {
                "个人信息": {},
                "成绩信息": {},
                "课表信息": {},
                "培养方案": {},
                "学业进度": {},
                "考试安排": {},
                "教师信息": [],
                "课程信息": []
            }

            # 获取个人信息
            personal_info = self.get_personal_info()
            if personal_info.get("success"):
                all_data["个人信息"] = personal_info.get("data", {})

            # 获取成绩
            grades = self.get_all_grades()
            if grades.get("success"):
                all_data["成绩信息"] = {
                    "成绩列表": grades.get("data", []),
                    "统计信息": grades.get("stats", {})
                }

            # 获取课表
            schedule = self.get_schedule()
            if schedule.get("success"):
                all_data["课表信息"] = schedule.get("data", [])

            # 获取我的培养方案
            plan = self.get_my_training_plan()
            if plan.get("success"):
                all_data["培养方案"] = plan.get("data", {})

            # 获取学业进度
            progress = self.get_academic_progress()
            if progress.get("success"):
                all_data["学业进度"] = progress.get("data", {})

            # 获取考试安排
            exams = self.get_exam_schedule()
            if exams.get("success"):
                all_data["考试安排"] = exams.get("data", [])

            logger.info("所有向量化数据获取完成")

            return {
                "success": True,
                "data": all_data
            }

        except Exception as e:
            logger.error(f"获取向量化数据失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取向量化数据失败: {str(e)}"
            }
