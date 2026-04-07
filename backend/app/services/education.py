import uuid
import base64
from typing import Optional
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page

from app.core.config import settings
from app.core.redis import redis_client


class EducationService:
    """教务系统爬虫服务"""
    
    def __init__(self):
        self.base_url = settings.EDUCATION_SYSTEM_URL
        self.browser: Optional[Browser] = None
        self.sessions: dict = {}
    
    async def _ensure_browser(self):
        if self.browser is None:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
    
    async def get_captcha(self) -> tuple[str, str]:
        """获取验证码图片，返回: (session_id, base64_image)"""
        await self._ensure_browser()
        
        context = await self.browser.new_context()
        page = await context.new_page()
        
        try:
            await page.goto(f"{self.base_url}/login", wait_until="networkidle")
            
            captcha_element = await page.query_selector("#captcha-img")
            if captcha_element:
                screenshot = await captcha_element.screenshot()
                captcha_base64 = base64.b64encode(screenshot).decode("utf-8")
            else:
                screenshot = await page.screenshot()
                captcha_base64 = base64.b64encode(screenshot).decode("utf-8")
            
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = (context, page)
            await redis_client.set_captcha(session_id, captcha_base64)
            
            logger.info(f"获取验证码成功, session_id: {session_id}")
            return session_id, captcha_base64
            
        except Exception as e:
            await context.close()
            logger.error(f"获取验证码失败: {e}")
            raise
    
    async def login(
        self,
        student_id: str,
        password: str,
        captcha: str,
        session_id: str,
    ) -> dict:
        """登录教务系统"""
        session_data = self.sessions.get(session_id)
        if not session_data:
            return {"success": False, "message": "会话已过期，请重新获取验证码"}
        
        context, page = session_data
        
        try:
            await page.fill('input[name="username"]', student_id)
            await page.fill('input[name="password"]', password)
            await page.fill('input[name="captcha"]', captcha)
            
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            
            current_url = page.url
            if "login" not in current_url:
                try:
                    student_name = await page.text_content(".user-name")
                except:
                    student_name = None
                
                logger.info(f"用户 {student_id} 登录教务系统成功")
                return {"success": True, "message": "登录成功", "student_name": student_name}
            else:
                error_msg = await page.text_content(".error-message")
                return {"success": False, "message": error_msg or "登录失败，请检查账号密码和验证码"}
                
        except Exception as e:
            logger.error(f"登录过程出错: {e}")
            return {"success": False, "message": f"登录过程出错: {str(e)}"}
        finally:
            await context.close()
            if session_id in self.sessions:
                del self.sessions[session_id]
    
    async def fetch_grades(self, student_id: str, password: str) -> list[dict]:
        """获取成绩信息"""
        await self._ensure_browser()
        context = await self.browser.new_context()
        page = await context.new_page()
        
        try:
            await page.goto(f"{self.base_url}/login", wait_until="networkidle")
            await page.fill('input[name="username"]', student_id)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            
            await page.goto(f"{self.base_url}/grades", wait_until="networkidle")
            
            grades = []
            rows = await page.query_selector_all("table.grades tbody tr")
            
            for row in rows:
                cells = await row.query_selector_all("td")
                if len(cells) >= 5:
                    grade = {
                        "course_name": await cells[0].text_content(),
                        "credit": float(await cells[1].text_content()),
                        "grade": await cells[2].text_content(),
                        "semester": await cells[3].text_content(),
                        "academic_year": await cells[4].text_content(),
                    }
                    grades.append(grade)
            
            logger.info(f"获取成绩成功，共 {len(grades)} 条记录")
            return grades
            
        except Exception as e:
            logger.error(f"获取成绩失败: {e}")
            return []
        finally:
            await context.close()
    
    async def fetch_schedule(self, student_id: str, password: str) -> list[dict]:
        """获取课程表"""
        await self._ensure_browser()
        context = await self.browser.new_context()
        page = await context.new_page()
        
        try:
            await page.goto(f"{self.base_url}/login", wait_until="networkidle")
            await page.fill('input[name="username"]', student_id)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            
            await page.goto(f"{self.base_url}/schedule", wait_until="networkidle")
            
            schedule = []
            logger.info(f"获取课程表成功，共 {len(schedule)} 条记录")
            return schedule
            
        except Exception as e:
            logger.error(f"获取课程表失败: {e}")
            return []
        finally:
            await context.close()
    
    async def close(self):
        if self.browser:
            await self.browser.close()
            self.browser = None
