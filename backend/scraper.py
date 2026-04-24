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
        # 确保 base_url 以斜杠结尾，用于URL拼接
        self.base_url = base_url.rstrip('/') + '/'
        self.captcha_url = f"{self.base_url}verifycode.servlet"
        self.login_url = f"{self.base_url}xk/LoginToXkLdap"

    def _fix_encoding(self, response) -> str:
        """自动修正响应编码，适配教务系统 GBK/UTF-8 混合场景
        返回正确解码的文本
        
        策略：先尝试 UTF-8（严格模式），成功就用 UTF-8；
        UTF-8 解码失败才用 GB18030。
        不能先试 GB18030，因为 UTF-8 字节用 GB18030 解码不会报错但会产生乱码。
        """
        import re
        raw_bytes = response.content
        
        # 1. 先尝试 UTF-8（严格模式，不允许错误）
        try:
            text_utf8 = raw_bytes.decode('utf-8')
            response.encoding = 'utf-8'
            return text_utf8
        except (UnicodeDecodeError, ValueError):
            pass
        
        # 2. UTF-8 失败，用 GB18030（兼容 GBK/GB2312）
        text_gb18030 = raw_bytes.decode('gb18030', errors='ignore')
        response.encoding = 'gb18030'
        logger.info("【编码】UTF-8 解码失败，使用 GB18030")
        return text_gb18030

    def _check_session_valid(self, html_text: str) -> bool:
        """检查响应内容是否表示 Session 已失效（被踢回登录页）"""
        # 强智教务系统 Session 过期特征
        if 'LoginToXk' in html_text and 'USERNAME' in html_text and 'PASSWORD' in html_text:
            logger.warning("【Session】会话已过期，响应为登录页面")
            return False
        return True

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
            html_text = self._fix_encoding(response)
            
            if "密码错误" in html_text or "验证码错误" in html_text:
                return {"success": False, "message": "用户名、密码或验证码错误"}
            
            if "xsMain.jsp" in html_text or "framework" in response.url:
                logger.info(f"用户 {username} 登录成功")
                return {"success": True, "message": "登录成功"}
            
            if "LoginToXkLdap" in html_text:
                return {"success": False, "message": "登录失败，请检查账号密码"}
            
            return {"success": True, "message": "登录成功"}
            
        except Exception as e:
            logger.error(f"登录失败: {str(e)}")
            return {"success": False, "message": f"登录异常: {str(e)}"}

    def get_personal_info(self) -> Dict:
        """
        获取个人信息
        从学籍卡片页面解析详细信息
        基于深度爬取真实HTML修复
        """
        try:
            # 先访问主页获取基本信息（参考登陆界面.txt: /jsxsd/framework/main.jsp）
            main_url = f"{self.base_url}framework/main.jsp"
            response = self.session.get(main_url, timeout=10)
            html_text = self._fix_encoding(response)
            
            if not self._check_session_valid(html_text):
                return {"success": False, "message": "会话已过期，请重新登录"}
            
            soup = BeautifulSoup(html_text, 'html.parser')
            
            name = ""
            student_id = ""
            
            # 方法1: 从 Top1_divLoginName 提取
            login_name_div = soup.find(id="Top1_divLoginName")
            if login_name_div:
                login_name = login_name_div.get_text(strip=True)
                if '(' in login_name and ')' in login_name:
                    name = login_name.split('(')[0]
                    student_id = login_name.split('(')[1].split(')')[0]
            
            # 方法2: 从 block1text 提取
            if not name:
                block1text = soup.find('div', class_='block1text')
                if block1text:
                    text = block1text.get_text()
                    import re
                    name_match = re.search(r'姓名[：:](.+)', text)
                    if name_match:
                        name = name_match.group(1).strip()
                    sid_match = re.search(r'学号[：:](\d+)', text)
                    if sid_match:
                        student_id = sid_match.group(1).strip()
            
            # 尝试获取学籍卡片详细信息
            major = ""
            class_name = ""
            department = ""
            
            try:
                card_url = f"{self.base_url}grxx/xsxx?Ves632DSdyV=NEW_XSD_XJCJ"
                logger.info(f"【个人信息调试】请求学籍卡片URL: {card_url}")
                card_resp = self.session.get(card_url, timeout=10)
                logger.info(f"【个人信息调试】学籍卡片响应状态: {card_resp.status_code}")
                logger.info(f"【个人信息调试】学籍卡片响应URL: {card_resp.url}")
                card_html = self._fix_encoding(card_resp)
                logger.info(f"【个人信息调试】学籍卡片HTML长度: {len(card_html)}")
                # 保存HTML到文件用于调试
                import tempfile, os
                debug_path = os.path.join(tempfile.gettempdir(), 'debug_personal_info.html')
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(card_html)
                logger.info(f"【个人信息调试】HTML已保存到 {debug_path}")
                card_soup = BeautifulSoup(card_html, 'html.parser')
                
                # 打印前500个字符用于调试
                logger.info(f"【个人信息调试】HTML前500字符: {card_html[:500]}")
                
                # 从学籍卡片提取详细信息
                card_text = card_soup.get_text()
                import re

                def extract_labeled_value(text: str, labels, next_labels):
                    label_pattern = "|".join(re.escape(label) for label in labels)
                    next_pattern = "|".join(re.escape(label) for label in next_labels)
                    pattern = rf"(?:{label_pattern})[：:]\s*(.+?)(?=(?:{next_pattern})[：:]|$)"
                    match = re.search(pattern, text, re.S)
                    if match:
                        return " ".join(match.group(1).split()).strip()
                    return ""

                # 优先按学籍卡片表格键值抽取，避免正则截断“计算机科学与技术”这类值
                detail_map = {}
                for table in card_soup.find_all('table'):
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['th', 'td'])
                        texts = [c.get_text(" ", strip=True).replace('\xa0', ' ').strip() for c in cells]
                        texts = [t for t in texts if t]
                        if len(texts) < 2:
                            continue
                        for i in range(0, len(texts) - 1, 2):
                            key = texts[i].rstrip('：:').strip()
                            value = texts[i + 1].strip()
                            if key and value and key not in detail_map:
                                detail_map[key] = value

                def pick_detail(*keywords):
                    for key, value in detail_map.items():
                        if any(word in key for word in keywords):
                            return value.strip()
                    return ""

                major = (
                    pick_detail("专业名称", "所学专业", "专业")
                    or major
                )
                class_name = (
                    pick_detail("行政班", "班级名称", "班级")
                    or class_name
                )
                department = (
                    pick_detail("学院名称", "学院", "院系", "系别")
                    or department
                )

                # 表格未命中或结果明显过短时，再退回更稳的标签提取
                if not major or len(major) <= 4:
                    major = extract_labeled_value(
                        card_text,
                        ["专业名称", "所学专业", "专业"],
                        ["班级名称", "班级", "行政班", "学院名称", "学院", "院系", "系别", "学号", "姓名", "入学时间", "学制", "培养层次"]
                    ) or major
                if not class_name:
                    class_name = extract_labeled_value(
                        card_text,
                        ["班级名称", "行政班", "班级"],
                        ["学院名称", "学院", "院系", "系别", "专业名称", "专业", "学号", "姓名", "入学时间", "学制"]
                    ) or class_name
                if not department:
                    department = extract_labeled_value(
                        card_text,
                        ["学院名称", "学院", "院系", "系别"],
                        ["专业名称", "专业", "班级名称", "班级", "行政班", "学号", "姓名", "入学时间", "学制"]
                    ) or department

                logger.info(f"【个人信息调试】专业匹配: {major if major else '未找到'}")
                logger.info(f"【个人信息调试】班级匹配: {class_name if class_name else '未找到'}")
                logger.info(f"【个人信息调试】院系匹配: {department if department else '未找到'}")
            except Exception as e:
                logger.warning(f"获取学籍卡片失败: {e}")

            personal_info = {
                "name": name,
                "student_id": student_id,
                "major": major,
                "class": class_name,
                "department": department
            }

            logger.info(f"【个人信息】解析成功: {personal_info}")

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
            url = f"{self.base_url}grxx/xsxx"
            response = self.session.get(url, timeout=10)
            html_text = self._fix_encoding(response)

            soup = BeautifulSoup(html_text, 'html.parser')

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
        基于深度爬取真实HTML修复
        参数:
        - kksj: 开课时间（学期），如 "2024-2025-1"
        - kcxz: 课程性质，如 "01"(必修), "02"(选修)
        - kcmc: 课程名称（模糊搜索）
        - fxkc: 修读类别 (0=主修课程, 1=辅修课程)
        - xsfs: 显示方式 (all=显示全部成绩, max=显示最好成绩)
        """
        try:
            # 根据深度爬取HTML第723行：查询表单提交到 /jsxsd/kscj/cjcx_list
            query_url = f"{self.base_url}kscj/cjcx_query"
            result_url = f"{self.base_url}kscj/cjcx_list"
            
            logger.info(f"【成绩调试】查询页面URL: {query_url}")
            logger.info(f"【成绩调试】结果提交URL: {result_url}")
            
            # 构建表单数据
            data = {
                "kksj": kksj,
                "kcxz": kcxz,
                "kcmc": kcmc,
                "fxkc": fxkc,
                "xsfs": xsfs
            }

            # POST提交查询表单到cjcx_list获取成绩结果
            response = self.session.post(result_url, data=data, timeout=10)
            logger.info(f"【成绩调试】响应状态: {response.status_code}")
            logger.info(f"【成绩调试】响应URL: {response.url}")
            html_text = self._fix_encoding(response)
            
            if not self._check_session_valid(html_text):
                return {"success": False, "message": "会话已过期，请重新登录"}
            
            logger.info(f"【成绩调试】HTML长度: {len(html_text)}")

            soup = BeautifulSoup(html_text, 'html.parser')
            
            # 保存HTML到文件用于调试
            import tempfile, os
            debug_path_grades = os.path.join(tempfile.gettempdir(), 'debug_grades.html')
            with open(debug_path_grades, 'w', encoding='utf-8') as f:
                f.write(html_text)
            logger.info(f"【成绩调试】HTML已保存到 {debug_path_grades}")

            # 查找所有表格
            all_tables = soup.find_all('table')
            logger.info(f"【成绩调试】找到 {len(all_tables)} 个表格")
            
            # 解析成绩表格 - 尝试多种选择器
            grade_table = None
            for table in all_tables:
                # 方法1：查找id='dataList'
                if table.get('id') == 'dataList':
                    grade_table = table
                    logger.info(f"【成绩调试】通过id='dataList'找到表格")
                    break
                # 方法2：查找包含成绩表头的表格
                headers = table.find_all('th')
                for th in headers:
                    header_text = th.get_text()
                    if (
                        '课程名称' in header_text
                        or ('成绩' in header_text and '学分' in table.get_text())
                        or ('开课学期' in table.get_text() and '课程编号' in table.get_text())
                    ):
                        grade_table = table
                        logger.info(f"【成绩调试】通过表头找到表格")
                        break
                if grade_table:
                    break
            
            logger.info(f"【成绩调试】最终找到表格: {grade_table is not None}")

            if not grade_table:
                logger.warning("未找到成绩表格")
                return {
                    "success": True,
                    "data": [],
                    "count": 0
                }

            # 提取数据行
            grades = []
            rows = grade_table.find_all('tr')
            logger.info(f"【成绩调试】表格共有 {len(rows)} 行")
            
            # 跳过表头行（第一行通常是th）
            for row_idx, row in enumerate(rows):
                # 跳过表头
                if row.find('th'):
                    logger.info(f"【成绩调试】第{row_idx}行是表头，跳过")
                    continue
                    
                cells = row.find_all('td')
                logger.info(f"【成绩调试】第{row_idx}行有 {len(cells)} 个单元格")
                
                if cells and len(cells) >= 9:
                    try:
                        # 兼容列偏移：有些页面会多一列“实验成绩”，有些不会
                        # 基准：序号,开课学期,课程编号,课程名称,平时,实验?,期末,成绩,学分,总学时...
                        has_experiment_col = len(cells) >= 17
                        final_col_idx = 6 if has_experiment_col else 5
                        score_col_idx = 7 if has_experiment_col else 6
                        credit_col_idx = 8 if has_experiment_col else 7
                        hours_col_idx = 9 if has_experiment_col else 8

                        grade_data = {
                            "序号": cells[0].get_text(strip=True),
                            "开课学期": cells[1].get_text(strip=True),
                            "课程编号": cells[2].get_text(strip=True),
                            "课程名称": cells[3].get_text(strip=True),
                            "平时成绩": cells[4].get_text(strip=True),
                            "实验成绩": cells[5].get_text(strip=True) if has_experiment_col else "",
                            "期末成绩": cells[final_col_idx].get_text(strip=True) if len(cells) > final_col_idx else "",
                            "成绩": cells[score_col_idx].get_text(strip=True) if len(cells) > score_col_idx else "",
                            "学分": cells[credit_col_idx].get_text(strip=True) if len(cells) > credit_col_idx else "",
                            "总学时": cells[hours_col_idx].get_text(strip=True) if len(cells) > hours_col_idx else "",
                            "考核方式": cells[hours_col_idx + 1].get_text(strip=True) if len(cells) > hours_col_idx + 1 else "",
                            "课程属性": cells[hours_col_idx + 2].get_text(strip=True) if len(cells) > hours_col_idx + 2 else "",
                            "课程性质": cells[hours_col_idx + 3].get_text(strip=True) if len(cells) > hours_col_idx + 3 else "",
                            "通选课分类": cells[hours_col_idx + 4].get_text(strip=True) if len(cells) > hours_col_idx + 4 else "",
                            "考试性质": cells[hours_col_idx + 5].get_text(strip=True) if len(cells) > hours_col_idx + 5 else "",
                            "成绩标识": cells[hours_col_idx + 6].get_text(strip=True) if len(cells) > hours_col_idx + 6 else "",
                            "备注": cells[hours_col_idx + 7].get_text(strip=True) if len(cells) > hours_col_idx + 7 else ""
                        }
                        grades.append(grade_data)
                        logger.info(f"【成绩调试】成功解析第{row_idx}行: {grade_data.get('课程名称', '未知')}")
                    except Exception as e:
                        logger.warning(f"【成绩调试】第{row_idx}行解析失败: {str(e)}")
                        continue
                else:
                    logger.info(f"【成绩调试】第{row_idx}行单元格不足9个({len(cells)}个)，跳过")

            # 提取统计信息（传入grades用于计算）
            stats = self._extract_grade_stats(soup, grades)

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

    def _extract_grade_stats(self, soup: BeautifulSoup, grades: list = None) -> Dict:
        """
        从成绩页面提取统计信息
        如果HTML中提取失败，则从成绩列表计算
        """
        import re
        stats = {
            "total_credits_required": 0,
            "credits_exempted": 0,
            "credits_completed": 0,
            "credits_remaining": 0,
            "gpa_major": 0.0,
            "rank": "",
            "gpa_minor": 0.0,
            "course_count": 0  # 添加课程数量统计
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

        # 如果HTML中提取失败，从成绩列表计算
        if grades and stats["credits_completed"] == 0:
            logger.info("【成绩统计】从HTML提取失败，从成绩列表计算学分")
            try:
                total_credits = 0.0
                course_count = 0
                for grade in grades:
                    credit_str = grade.get("学分", "0")
                    try:
                        credit = float(credit_str)
                        total_credits += credit
                        course_count += 1
                    except:
                        pass
                
                stats["credits_completed"] = int(total_credits)
                stats["course_count"] = course_count
                logger.info(f"【成绩统计】计算结果：{course_count}门课程，{total_credits}学分")
            except Exception as e:
                logger.warning(f"【成绩统计】从成绩列表计算失败: {str(e)}")

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
        基于深度爬取真实HTML修复
        参数:
        - semester: 学期，如 "2024-2025-2"，为空则获取当前学期
        - week: 周次，如 "1", "5"，为空则获取全部周次
        返回: 课程列表，包含课程名称、时间、地点、教师等信息
        """
        try:
            # 课表查询URL（根据深度爬取crawl_tree.json）
            url = f"{self.base_url}xskb/xskb_list.do"
            logger.info(f"【课表调试】请求URL: {url}")

            # 构建表单数据（根据真实HTML表单结构）
            # 注意：当semester为空时，不传递xnxq01id参数，服务器会返回默认学期（当前学期）
            data = {
                "cj0701id": "",
                "demo": "",
                "sfFD": "1"
            }
            if semester:
                data["xnxq01id"] = semester
                logger.info(f"【课表调试】查询学期: {semester}")
            else:
                logger.info(f"【课表调试】未指定学期，将返回默认学期")
            if week:
                data["zc"] = week
                logger.info(f"【课表调试】查询周次: {week}")
            else:
                logger.info(f"【课表调试】未指定周次，将返回全部周次")

            # POST提交查询（课表必须POST）
            response = self.session.post(url, data=data if data else {}, timeout=10)
            logger.info(f"【课表调试】响应状态: {response.status_code}")
            logger.info(f"【课表调试】响应URL: {response.url}")

            html_text = self._fix_encoding(response)
            logger.info(f"【课表调试】HTML长度: {len(html_text)}")
            
            if not self._check_session_valid(html_text):
                return {"success": False, "message": "会话已过期，请重新登录"}
            
            # 保存HTML到文件用于调试
            import tempfile, os
            debug_path = os.path.join(tempfile.gettempdir(), 'debug_schedule.html')
            try:
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(html_text)
                logger.info(f"【课表调试】HTML已保存到 {debug_path}")
            except Exception as e:
                logger.warning(f"【课表调试】保存HTML失败: {e}")
            
            # 检查HTML中是否包含关键信息
            if 'kbtable' not in html_text:
                logger.error("【课表调试】HTML中不包含'kbtable'表格ID")
                # 检查是否有错误信息
                if '登录' in html_text or 'login' in html_text.lower():
                    logger.error("【课表调试】可能需要重新登录")
                if '学期' in html_text:
                    # 提取页面中显示的学期信息
                    import re as _re
                    semester_match = _re.search(r'20\d{2}-20\d{2}-\d', html_text)
                    if semester_match:
                        logger.info(f"【课表调试】页面显示学期: {semester_match.group()}")
            
            soup = BeautifulSoup(html_text, 'html.parser')

            # 查找课表表格（真实HTML中表格ID为kbtable）
            schedule_table = soup.find('table', id='kbtable')
            
            # 提取实际查询的学期（从HTML中的select选项）
            actual_semester = semester
            if not actual_semester:
                # 从HTML中提取默认选中的学期
                import re as _re
                selected_match = _re.search(r'<option[^>]+value="(20\d{2}-20\d{2}-\d)"[^>]*selected="selected"', html_text)
                if selected_match:
                    actual_semester = selected_match.group(1)
                    logger.info(f"【课表调试】默认学期: {actual_semester}")
            
            if not schedule_table:
                logger.error("【课表调试】未找到id='kbtable'的表格")
                # 输出HTML的前1000个字符用于诊断
                logger.error(f"【课表调试】HTML开头: {html_text[:1000]}")
                # 备用策略：查找所有表格
                all_tables = soup.find_all('table')
                logger.info(f"【课表调试】找到 {len(all_tables)} 个表格")
                for table_idx, table in enumerate(all_tables):
                    rows = table.find_all('tr')
                    logger.info(f"【课表调试】表格{table_idx}有 {len(rows)} 行")
                    if len(rows) > 5:  # 假设有数据的表格至少有5行
                        schedule_table = table
                        logger.info(f"【课表调试】选择表格{table_idx}作为课表")
                        break

            if not schedule_table:
                logger.warning("未找到课表表格")
                return {
                    "success": True,
                    "data": [],
                    "count": 0,
                    "semester": semester
                }
            
            logger.info(f"【课表调试】找到课表表格，开始解析")

            # 解析课表
            courses = []
            rows = schedule_table.find_all('tr')

            # 节次映射
            period_map = {
                "第一二节": "1-2",
                "第三四节": "3-4",
                "第五六节": "5-6",
                "第七八节": "7-8",
                "第九十节": "9-10",
                "第十一十二节": "11-12"
            }

            # 跳过表头行（第一行是星期标题）
            for row_idx, row in enumerate(rows):
                # 只跳过第一行（表头：星期一、星期二...）
                if row_idx == 0:
                    continue
                    
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 8:
                    # 节次信息 (第一二节、第三四节等)
                    period_text = cells[0].get_text(strip=True)
                    period = period_map.get(period_text, period_text)

                    # 遍历每天的课程 (周一到周日)
                    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                    for i, cell in enumerate(cells[1:8], 1):
                        # 使用 kbcontent 解析（含教师信息），按 HTML 块切分支持多课程单元格
                        import re as _kb_re
                        course_divs = cell.find_all('div', class_='kbcontent')

                        for div in course_divs:
                            # 跳过空单元格
                            if not div.get_text(strip=True):
                                continue

                            # kbcontent 多课程分隔符：21 个短横线
                            inner_html = div.decode_contents()
                            course_blocks_html = _kb_re.split(r'-{21,22}', inner_html)

                            for block_html in course_blocks_html:
                                block_html = block_html.strip()
                                if not block_html:
                                    continue

                                # 用 BeautifulSoup 解析单个课程块
                                block_soup = BeautifulSoup(
                                    '<div>' + block_html + '</div>', 'html.parser'
                                )
                                if not block_soup.get_text(strip=True):
                                    continue

                                lines = [
                                    l.strip()
                                    for l in block_soup.get_text(separator='\n').splitlines()
                                    if l.strip()
                                ]
                                if not lines:
                                    continue

                                course_name = lines[0]

                                # 用 font[title] 精确提取各字段
                                teacher_font = block_soup.find('font', title='老师')
                                teacher = teacher_font.get_text(strip=True) if teacher_font else ""

                                weeks_font = block_soup.find('font', title='周次(节次)')
                                weeks = weeks_font.get_text(strip=True) if weeks_font else ""

                                location_font = block_soup.find('font', title='教室')
                                location = location_font.get_text(strip=True) if location_font else ""

                                # 节次信息（[XX-XX]节）
                                sections = ""
                                for line in lines:
                                    if '节' in line and '[' in line:
                                        sections = line
                                        break

                                course_data = {
                                    "学期": actual_semester or semester or "",
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
            # 备注行的 th 内含"备注:"，td colspan="7" 包含课程列表
            remarks = []
            import re as _re
            for row in schedule_table.find_all('tr'):
                th_cell = row.find('th')
                if th_cell and '备注' in th_cell.get_text():
                    td_cell = row.find('td')
                    if td_cell:
                        remark_text = td_cell.get_text(strip=True)
                        if '：' in remark_text:
                            after_colon = remark_text.split('：', 1)[1]
                            remarks = [c.strip() for c in _re.split(r'[;\uff1b]', after_colon) if c.strip()]
                    break

            logger.info(f"成功获取 {len(courses)} 门课程")

            # 如果没有课程，提供更详细的诊断信息
            if len(courses) == 0:
                logger.warning(f"【课表调试】{actual_semester}学期无课程数据")
                # 检查备注信息
                if remarks:
                    logger.info(f"【课表调试】备注信息: {remarks}")

            return {
                "success": True,
                "data": courses,
                "count": len(courses),
                "semester": actual_semester,
                "week": week,
                "未安排时间课程": remarks,
                "raw_html": html_text  # 保存原始HTML供分析
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
                url = f"{self.base_url}jspyfa/zypyfa_query"
                data = {
                    "xsyx": department,
                    "xsnj": grade,
                    "xszy": major
                }
                response = self.session.post(url, data=data, timeout=10)
            else:
                # 否则获取查询页面
                url = f"{self.base_url}jspyfa/pyfa_find"
                response = self.session.get(url, timeout=10)

            html_text = self._fix_encoding(response)
            soup = BeautifulSoup(html_text, 'html.parser')

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
        基于教务系统导出的“指导培养方案”页面解析。
        """
        try:
            import re

            url = f"{self.base_url}pyfa/pyfazd_query"
            logger.info(f"【培养方案调试】请求URL: {url}")
            response = self.session.get(url, timeout=10)
            logger.info(f"【培养方案调试】响应状态: {response.status_code}")
            logger.info(f"【培养方案调试】响应URL: {response.url}")
            html_text = self._fix_encoding(response)
            logger.info(f"【培养方案调试】HTML长度: {len(html_text)}")

            if not self._check_session_valid(html_text):
                return {"success": False, "message": "会话已过期，请重新登录"}
            
            # 保存HTML到文件用于调试
            import tempfile, os
            debug_path_plan = os.path.join(tempfile.gettempdir(), 'debug_training_plan.html')
            with open(debug_path_plan, 'w', encoding='utf-8') as f:
                f.write(html_text)
            logger.info(f"【培养方案调试】HTML已保存到 {debug_path_plan}")
            
            # 输出HTML前500字符用于调试
            logger.info(f"【培养方案调试】HTML前500字符: {html_text[:500]}")

            soup = BeautifulSoup(html_text, 'html.parser')

            plan_data = {
                "基本信息": {},
                "学分统计": {},
                "课程列表": []
            }

            title = soup.find("title")
            plan_title = soup.find("font", style=lambda x: x and "font-size:16px" in x)
            if title:
                plan_data["基本信息"]["页面标题"] = title.get_text(strip=True)
            if plan_title:
                plan_data["基本信息"]["方案名称"] = plan_title.get_text(strip=True)

            page_text = soup.get_text("\n", strip=True)
            credit_match = re.search(r"修满\s*(\d+)\s*学分", page_text)
            if credit_match:
                plan_data["学分统计"]["总学分要求"] = int(credit_match.group(1))

            target_table = soup.find("table", id="mxh")
            if not target_table:
                logger.warning("【培养方案调试】未找到 id='mxh' 的课程表格")
            else:
                logger.info("【培养方案调试】找到 id='mxh' 课程表格")
                current_category = ""
                current_nature = ""
                current_module = ""
                tbody = target_table.find("tbody") or target_table
                rows = tbody.find_all("tr")

                for row in rows:
                    if row.find("th"):
                        continue

                    cells = row.find_all("td")
                    values = [cell.get_text(" ", strip=True).replace("\xa0", " ").strip() for cell in cells]
                    if not values:
                        continue

                    code_idx = next((i for i, value in enumerate(values) if re.fullmatch(r"\d{8}", value)), -1)
                    if code_idx < 0:
                        continue

                    prefix = values[:code_idx]
                    suffix = values[code_idx:]
                    if len(suffix) < 12:
                        continue

                    non_empty_prefix = [value for value in prefix if value]
                    if len(non_empty_prefix) >= 1:
                        current_category = non_empty_prefix[0]
                    if len(non_empty_prefix) >= 2:
                        current_nature = non_empty_prefix[1]
                    if len(non_empty_prefix) >= 3:
                        current_module = non_empty_prefix[2]

                    course = {
                        "课程类别": current_category,
                        "课程性质": current_nature,
                        "课程模块": current_module,
                        "课程代码": suffix[0].strip(),
                        "课程名称": suffix[1].strip(),
                        "学分": suffix[2].strip(),
                        "授课周数": suffix[3].strip(),
                        "总学时": suffix[4].strip(),
                        "理论学时": suffix[5].strip(),
                        "实验学时": suffix[6].strip(),
                        "实习学时": suffix[7].strip(),
                        "其他学时": suffix[8].strip(),
                        "建议修读学期": suffix[9].strip(),
                        "是否适用辅修专业": suffix[10].strip(),
                        "建议考核方式": suffix[11].strip(),
                    }
                    plan_data["课程列表"].append(course)

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
            url = f"{self.base_url}pyfa/xyjdcx"
            logger.info(f"【学业进度调试】请求URL: {url}")

            # 如果有study_type参数，提交表单查询（根据深度爬取HTML第405行）
            if study_type:
                data = {"xdlx": study_type}
                result_url = f"{url}?type=cx"
                logger.info(f"【学业进度调试】POST提交到: {result_url}")
                logger.info(f"【学业进度调试】表单数据: {data}")
                response = self.session.post(result_url, data=data, timeout=10)
            else:
                response = self.session.get(url, timeout=10)
            
            logger.info(f"【学业进度调试】响应状态: {response.status_code}")
            logger.info(f"【学业进度调试】响应URL: {response.url}")

            html_text = self._fix_encoding(response)
            logger.info(f"【学业进度调试】HTML长度: {len(html_text)}")
            
            # 保存HTML到文件用于调试
            import tempfile, os
            debug_path_progress = os.path.join(tempfile.gettempdir(), 'debug_academic_progress.html')
            with open(debug_path_progress, 'w', encoding='utf-8') as f:
                f.write(html_text)
            logger.info(f"【学业进度调试】HTML已保存到 {debug_path_progress}")
            
            # 输出HTML前500字符用于调试
            logger.info(f"【学业进度调试】HTML前500字符: {html_text[:500]}")
            
            soup = BeautifulSoup(html_text, 'html.parser')

            progress_data = {
                "修读类型": "主修" if study_type == "0" else "辅修" if study_type == "1" else "未知",
                "总学分要求": 0,
                "已获学分": 0,
                "还需学分": 0,
                "课程列表": []
            }

            # 查找课程表格 - 以表头字段为锚点，避免不同修读类型列偏移
            progress_table = None
            expected_headers = ["课程性质", "课程代码", "课程名称", "学分", "建议修读学期", "免听、免修", "已获学分"]
            for table_idx, table in enumerate(soup.find_all('table')):
                text = table.get_text(" ", strip=True)
                if all(header in text for header in expected_headers):
                    progress_table = table
                    logger.info(f"【学业进度调试】通过表头匹配找到表格{table_idx}")
                    break
            
            if progress_table:
                rows = progress_table.find_all('tr')
                logger.info(f"【学业进度调试】学业进度表格共有 {len(rows)} 行")
                page_text = soup.get_text(" ", strip=True)

                # 先从标题提取总学分，再从表头做动态列映射
                import re
                credit_match = re.search(r'需修读总学分[:：]\s*(\d+(?:\.\d+)?)', page_text)
                if credit_match:
                    progress_data["总学分要求"] = float(credit_match.group(1))

                header_row = None
                headers = []
                for row in rows:
                    th_cells = row.find_all('th')
                    th_texts = [th.get_text(" ", strip=True).replace('\xa0', ' ').strip() for th in th_cells]
                    if th_texts and "课程代码" in th_texts and "课程名称" in th_texts:
                        header_row = row
                        headers = th_texts
                        break

                if headers:
                    logger.info(f"【学业进度调试】识别表头: {headers}")

                for row_idx, row in enumerate(rows):
                    if row is header_row:
                        continue

                    cells = row.find_all('td')
                    if not cells:
                        continue

                    values = [cell.get_text(" ", strip=True).replace('\xa0', ' ').strip() for cell in cells]
                    logger.info(f"【学业进度调试】第{row_idx}行有 {len(values)} 个单元格")

                    row_text = ''.join(value for value in values if value)
                    if '合计' in row_text:
                        logger.info(f"【学业进度调试】找到合计行，{len(values)}个单元格")
                        non_empty_values = [value for value in values if value]
                        earned_text = non_empty_values[-1].strip() if non_empty_values else ""
                        if earned_text:
                            try:
                                progress_data["已获学分"] = float(earned_text)
                                logger.info(f"【学业进度调试】从合计行提取已获学分: {progress_data['已获学分']}")
                            except Exception as e:
                                logger.warning(f"【学业进度调试】合计行解析失败: {str(e)}")
                        continue

                    code_idx = next((i for i, value in enumerate(values) if re.fullmatch(r"\d{8}", value)), -1)
                    if code_idx >= 0 and code_idx + 3 < len(values):
                        row_map = {
                            "课程类别": values[code_idx - 2].strip() if code_idx - 2 >= 0 else "",
                            "课程性质": values[code_idx - 1].strip() if code_idx - 1 >= 0 else "",
                            "课程代码": values[code_idx].strip(),
                            "课程名称": values[code_idx + 1].strip() if code_idx + 1 < len(values) else "",
                            "学分": values[code_idx + 2].strip() if code_idx + 2 < len(values) else "",
                            "建议修读学期": values[code_idx + 3].strip() if code_idx + 3 < len(values) else "",
                            "免听、免修": values[code_idx + 4].strip() if code_idx + 4 < len(values) else "",
                            "已获学分": values[code_idx + 5].strip() if code_idx + 5 < len(values) else "",
                        }
                    elif headers and len(values) >= len(headers):
                        row_map = dict(zip(headers, values[:len(headers)]))
                    else:
                        row_map = {}

                    course_name = row_map.get("课程名称", "")
                    course_code = row_map.get("课程代码", "")
                    if not course_name and not course_code:
                        continue

                    course_data = {
                        "课程类别": row_map.get("课程类别", ""),
                        "课程性质": row_map.get("课程性质", values[0].strip() if len(values) > 0 else ""),
                        "课程代码": course_code or (values[1].strip() if len(values) > 1 else ""),
                        "课程名称": course_name or (values[2].strip() if len(values) > 2 else ""),
                        "学分": row_map.get("学分", values[3].strip() if len(values) > 3 else ""),
                        "建议修读学期": row_map.get("建议修读学期", values[4].strip() if len(values) > 4 else ""),
                        "免听免修": row_map.get("免听、免修", values[5].strip() if len(values) > 5 else ""),
                        "已获学分": row_map.get("已获学分", next((value for value in reversed(values) if value), "")),
                    }

                    if not course_data["课程名称"] and course_data["课程代码"]:
                        course_data["课程名称"] = course_data["课程代码"]

                    progress_data["课程列表"].append(course_data)
                    logger.info(f"【学业进度调试】成功解析第{row_idx}行: {course_data.get('课程名称', '未知')}")

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
            url = f"{self.base_url}xsks/xsksap_query"
            params = {}
            if semester:
                params["xnxqid"] = semester

            response = self.session.get(url, params=params, timeout=10)
            html_text = self._fix_encoding(response)

            soup = BeautifulSoup(html_text, 'html.parser')

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
        - name: 教师姓名（支持模糊查询，不能为空）
        - department: 所属院系代码（可选）
        返回: 教师列表
        """
        try:
            # 教务系统要求教师姓名不能为空（参考教师信息查询.txt JavaScript校验）
            if not name or not name.strip():
                return {
                    "success": False,
                    "message": "教师姓名不能为空，请至少输入一个字"
                }

            # 构建查询参数
            data = {"jsxm": name.strip()}
            if department:
                data["kkyx"] = department

            # 提交查询
            url = f"{self.base_url}jsxx/jsxx_list"
            response = self.session.post(url, data=data, timeout=10)
            html_text = self._fix_encoding(response)

            soup = BeautifulSoup(html_text, 'html.parser')

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
                        # 处理相对链接中的 /jsxsd/ 前缀（避免与base_url重复）
                        if href.startswith('http'):
                            detail_url = href
                        elif href.startswith('/jsxsd/'):
                            detail_url = f"{self.base_url}{href[len('/jsxsd/'):]}"
                        else:
                            detail_url = f"{self.base_url}{href.lstrip('/')}"
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
            # 参考教师信息查询.txt: /jsxsd/jsxx/jsxx_query_detail
            url = f"{self.base_url}jsxx/jsxx_query_detail"
            params = {"jg0101id": teacher_id}

            response = self.session.get(url, params=params, timeout=10)
            html_text = self._fix_encoding(response)

            soup = BeautifulSoup(html_text, 'html.parser')

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
            url = f"{self.base_url}kbcx/kbxx_kc"

            data = {}
            if course_name:
                data["kcmc"] = course_name
            if course_code:
                data["kch"] = course_code
            if department:
                data["kkyx"] = department

            response = self.session.post(url, data=data, timeout=10)
            html_text = self._fix_encoding(response)

            soup = BeautifulSoup(html_text, 'html.parser')

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
            url = f"{self.base_url}xsxk/xklc_list"
            response = self.session.get(url, timeout=10)
            html_text = self._fix_encoding(response)

            soup = BeautifulSoup(html_text, 'html.parser')

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
            # 修复URL双前缀：base_url已含/jsxsd/，不需要再拼接
            url = f"{self.base_url}pyfa/pyfa_query"
            response = self.session.get(url, timeout=10)
            html_text = self._fix_encoding(response)

            soup = BeautifulSoup(html_text, 'html.parser')

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

            # 获取成绩（按学期分组）
            grades = self.get_all_grades()
            if grades.get("success"):
                grade_list = grades.get("data", [])
                # 按学期分组
                grades_by_semester = {}
                for g in grade_list:
                    sem = g.get("开课学期", "未知学期")
                    if sem not in grades_by_semester:
                        grades_by_semester[sem] = []
                    grades_by_semester[sem].append(g)
                all_data["成绩信息"] = {
                    "按学期": grades_by_semester,
                    "统计信息": grades.get("stats", {})
                }

            # 获取课表（附带学期信息）
            schedule = self.get_schedule()
            if schedule.get("success"):
                all_data["课表信息"] = {
                    "学期": schedule.get("semester", ""),
                    "课程列表": schedule.get("data", [])
                }

            # 获取我的培养方案
            plan = self.get_my_training_plan()
            if plan.get("success"):
                all_data["培养方案"] = plan.get("data", {})

            # 获取学业进度
            progress = self.get_academic_progress()
            if progress.get("success"):
                all_data["学业进度"] = progress.get("data", {})

            # 获取考试安排（附带学期信息）
            exams = self.get_exam_schedule()
            if exams.get("success"):
                all_data["考试安排"] = {
                    "学期": exams.get("semester", ""),
                    "考试列表": exams.get("data", [])
                }

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
