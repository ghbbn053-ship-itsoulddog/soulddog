"""
教务系统 AI 助手 - 后端 API
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import requests
import io
import base64
from typing import Optional
import random
import logging

# 导入爬虫模块
from scraper import JwxtScraper

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="教务系统 AI 助手 API", version="1.0.0")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源，生产环境需要限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 教务系统配置
JWXT_BASE_URL = "http://jwxt.gdufe.edu.cn"
VERIFY_CODE_URL = f"{JWXT_BASE_URL}/jsxsd/verifycode.servlet"
LOGIN_URL = f"{JWXT_BASE_URL}/jsxsd/xk/LoginToXkLdap"

# 服务器列表（根据学号选择）
SERVERS = [
    "http://172.19.13.60:80/jsxsd/",
    "http://172.19.13.62:80/jsxsd/",
    "http://172.19.13.61:80/jsxsd/",
    "http://172.19.13.63:80/jsxsd/",
    "http://172.19.13.101:80/jsxsd/",
    "http://172.19.13.102:80/jsxsd/",
    "http://172.19.13.103:80/jsxsd/",
    "http://172.19.13.104:80/jsxsd/",
    "http://172.19.13.105:80/jsxsd/",
    "http://172.19.13.106:80/jsxsd/",
    "http://172.19.13.100:8380/jsxsd/",
    "http://172.19.13.100:80/jsxsd/",
    "http://172.19.13.108:80/jsxsd/",
    "http://172.19.13.109:80/jsxsd/",
]

# Session 存储（生产环境应使用 Redis）
SESSIONS = {}


def select_server(username: str) -> str:
    """
    根据学号选择服务器
    如果学号是数字，使用学号 % 14 选择服务器
    否则使用第一个服务器
    """
    if username.isdigit():
        server_index = int(username) % len(SERVERS)
        return SERVERS[server_index]
    else:
        return SERVERS[0]


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "教务系统 AI 助手 API",
        "version": "1.0.0",
        "endpoints": {
            "captcha": "/api/captcha - 获取验证码",
            "login": "/api/login - 登录",
            "health": "/api/health - 健康检查"
        }
    }


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


@app.get("/api/captcha")
async def get_captcha():
    """
    获取验证码图片
    返回 base64 编码的图片
    """
    try:
        # 添加随机参数避免缓存
        timestamp = random.random()
        captcha_url = f"{VERIFY_CODE_URL}?t={timestamp}"

        # 请求验证码图片
        response = requests.get(
            captcha_url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            }
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"获取验证码失败: {response.status_code}"
            )

        # 将图片转换为 base64
        image_base64 = base64.b64encode(response.content).decode("utf-8")

        return {
            "success": True,
            "image": f"data:image/jpeg;base64,{image_base64}",
            "session_id": response.cookies.get("JSESSIONID", "")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取验证码失败: {str(e)}")


@app.post("/api/login")
async def login(request: Request):
    """
    登录接口
    参数: username, password, code (验证码)
    """
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        code = data.get("code")

        # 验证参数
        if not all([username, password, code]):
            raise HTTPException(status_code=400, detail="缺少必要参数")

        # 创建 Session
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        })

        # 选择服务器
        server_url = select_server(username)
        login_url = f"{server_url}xk/LoginToXkLdap"

        # 登录表单数据
        login_data = {
            "USERNAME": username,
            "PASSWORD": password,
            "RANDOMCODE": code
        }

        # 发送登录请求
        logger.info(f"【登录】正在尝试登录，用户名: {username}")
        logger.info(f"【登录】使用服务器: {server_url}")
        response = session.post(
            login_url,
            data=login_data,
            timeout=10
        )

        logger.info(f"【登录】响应状态码: {response.status_code}")
        logger.info(f"【登录】响应 URL: {response.url}")

        # 检查登录结果
        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"登录请求失败: {response.status_code}"
            )

        # 检查是否登录成功（根据教务系统返回的页面判断）
        response.encoding = "utf-8"
        content = response.text

        logger.info(f"【登录】响应内容长度: {len(content)}")

        # 检查登录失败的明确标志
        if "密码错误" in content or "验证码错误" in content or "用户名不存在" in content:
            logger.warning(f"【登录】登录失败: 密码错误或验证码错误")
            return {
                "success": False,
                "message": "用户名、密码或验证码错误"
            }

        # 检查是否停留在登录页面（说明登录失败）
        if "LoginToXkLdap" in content or "教务管理系统" in content and "framework" not in response.url:
            logger.warning(f"【登录】登录失败: 仍在登录页面")
            return {
                "success": False,
                "message": "登录失败，请检查用户名、密码或验证码"
            }

        # 检查是否成功跳转到主页
        if "/jsxsd/framework/" in content or "framework" in response.url:
            # 保存 session
            SESSIONS[username] = session
            logger.info(f"【登录】登录成功，session 已保存，当前 session 数量: {len(SESSIONS)}")

            return {
                "success": True,
                "message": "登录成功",
                "username": username,
                "session_id": session.cookies.get("JSESSIONID", "")
            }

        # 默认返回失败
        return {
            "success": False,
            "message": "登录失败，请重试"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


# ===== 数据爬取接口 =====

@app.get("/api/user/info")
async def get_user_info(username: str):
    """
    获取用户个人信息
    """
    try:
        logger.info(f"【个人信息】收到请求，用户名: {username}")
        logger.info(f"【个人信息】当前 session 数量: {len(SESSIONS)}")
        logger.info(f"【个人信息】当前 session keys: {list(SESSIONS.keys())}")

        # 检查 session 是否存在
        if username not in SESSIONS:
            logger.warning(f"【个人信息】用户 {username} 未登录")
            raise HTTPException(status_code=401, detail="未登录，请先登录")

        session = SESSIONS[username]
        logger.info(f"【个人信息】找到用户 {username} 的 session，开始爬取...")

        scraper = JwxtScraper(session, JWXT_BASE_URL)

        result = scraper.get_personal_info()

        logger.info(f"【个人信息】爬取结果: {result}")

        if result["success"]:
            return {
                "success": True,
                "data": result["data"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "获取信息失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取个人信息失败: {str(e)}")


@app.get("/api/user/card")
async def get_user_card(username: str):
    """
    获取学籍卡片详细信息
    """
    try:
        if username not in SESSIONS:
            raise HTTPException(status_code=401, detail="未登录，请先登录")

        session = SESSIONS[username]
        scraper = JwxtScraper(session, JWXT_BASE_URL)

        result = scraper.get_student_card()

        if result["success"]:
            return {
                "success": True,
                "data": result["data"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "获取学籍卡片失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取学籍卡片失败: {str(e)}")


@app.get("/api/grades")
async def get_grades(
    username: str,
    kksj: str = "",
    kcxz: str = "",
    kcmc: str = "",
    fxkc: str = "0",
    xsfs: str = "all"
):
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
        if username not in SESSIONS:
            raise HTTPException(status_code=401, detail="未登录，请先登录")

        session = SESSIONS[username]
        scraper = JwxtScraper(session, JWXT_BASE_URL)

        result = scraper.get_grades(kksj=kksj, kcxz=kcxz, kcmc=kcmc, fxkc=fxkc, xsfs=xsfs)

        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "count": result.get("count", 0)
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "获取成绩失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取成绩失败: {str(e)}")


@app.get("/api/grades/all")
async def get_all_grades(username: str):
    """
    获取所有成绩（快捷接口）
    """
    return await get_grades(
        username=username,
        kksj="",
        kcxz="",
        kcmc="",
        fxkc="0",
        xsfs="all"
    )


# ===== 教务系统绑定接口（新） =====

@app.get("/api/education/captcha")
async def get_education_captcha():
    """获取教务系统验证码（新绑定流程）"""
    try:
        scraper = JwxtScraper()
        captcha_bytes = scraper.get_captcha()
        captcha_b64 = base64.b64encode(captcha_bytes).decode()
        session_id = str(id(scraper.session))
        SESSIONS[session_id] = scraper.session
        
        return {
            "success": True,
            "image": f"data:image/jpeg;base64,{captcha_b64}",
            "session_id": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取验证码失败: {str(e)}")


@app.post("/api/education/bind")
async def bind_education(request: Request):
    """绑定教务系统并同步数据（内网版本）"""
    try:
        data = await request.json()
        student_id = data.get("student_id")
        password = data.get("password")
        captcha = data.get("captcha")
        
        if not all([student_id, password, captcha]):
            raise HTTPException(status_code=400, detail="缺少必要参数")
        
        scraper = JwxtScraper()
        
        # 登录（内网明文密码）
        login_result = scraper.login(
            username=student_id,
            password=password,
            captcha=captcha
        )
        
        if not login_result["success"]:
            return {
                "success": False,
                "message": login_result["message"],
                "courses_count": 0,
                "grades_count": 0
            }
        
        # 获取个人信息和成绩
        personal_info = scraper.get_personal_info()
        grades_result = scraper.get_all_grades()
        grades_count = grades_result.get("count", 0) if grades_result.get("success") else 0
        
        SESSIONS[student_id] = scraper.session
        
        return {
            "success": True,
            "message": f"绑定成功！欢迎 {personal_info.get('data', {}).get('name', student_id)}",
            "courses_count": 0,
            "grades_count": grades_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"绑定失败: {str(e)}")
        return {
            "success": False,
            "message": f"绑定失败: {str(e)}",
            "courses_count": 0,
            "grades_count": 0
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
