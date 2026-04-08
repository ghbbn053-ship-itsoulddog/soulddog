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
        """
        登录教务系统（内网版本，明文密码）
        
        参数:
        - username: 学号
        - password: 密码（明文）
        - captcha: 验证码
        """
        try:
            data = {
                "USERNAME": username,
                "PASSWORD": password,
                "RANDOMCODE": captcha
            }
            
            response = self.session.post(self.login_url, data=data, timeout=10)
            response.encoding = "utf-8"
            
            # 检查登录结果
            if "密码错误" in response.text or "验证码错误" in response.text:
                return {"success": False, "message": "用户名、密码或验证码错误"}
            
            if "xsMain.jsp" in response.text or "framework" in response.url:
                logger.info(f"用户 {username} 登录成功")
                return {"success": True, "message": "登录成功"}
            
            # 检查是否在登录页（失败）
            if "LoginToXkLdap" in response.text:
                return {"success": False, "message": "登录失败，请检查账号密码"}
            
            # 其他情况，默认成功（可能已经登录）
            logger.info(f"登录响应: {response.url}")
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
            response.encoding = "utf-8"

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
            response.encoding = "utf-8"

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
            response.encoding = "utf-8"

            soup = BeautifulSoup(response.text, 'html.parser')

            # 解析成绩表格
            grade_table = soup.find('table', class_='Nsb_table')

            if not grade_table:
                logger.warning("未找到成绩表格")
                return {
                    "success": True,
                    "data": []
                }

            # 提取表头
            headers = []
            thead = grade_table.find('thead')
            if thead:
                header_row = thead.find('tr')
                if header_row:
                    headers = [th.get_text(strip=True) for th in header_row.find_all('th')]

            # 提取数据行
            grades = []
            tbody = grade_table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if cells:
                        grade_data = {}
                        for i, cell in enumerate(cells):
                            if i < len(headers):
                                key = headers[i]
                            else:
                                key = f"col_{i}"
                            grade_data[key] = cell.get_text(strip=True)
                        grades.append(grade_data)

            logger.info(f"成功获取 {len(grades)} 条成绩记录")

            return {
                "success": True,
                "data": grades,
                "count": len(grades)
            }

        except Exception as e:
            logger.error(f"获取成绩失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取成绩失败: {str(e)}"
            }

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
