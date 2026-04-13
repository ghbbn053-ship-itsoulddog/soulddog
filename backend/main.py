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
from education_options import (
    EducationOptions,
    query_departments,
    query_semesters,
    query_course_options,
    query_schedule_options,
    query_grade_options,
    get_option_description,
)

# 导入 API 路由
try:
    from app.api import chat
    CHAT_API_AVAILABLE = True
except ImportError:
    CHAT_API_AVAILABLE = False
    print("⚠️ Chat API 未启用")

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

# 注册 Chat API 路由（如果可用）
if CHAT_API_AVAILABLE:
    app.include_router(chat.router)
    print("✅ Chat API 已启用")


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
    endpoints = {
        "captcha": "/api/captcha - 获取验证码",
        "login": "/api/login - 登录",
        "user_info": "/api/user/info - 个人信息",
        "grades": "/api/grades - 成绩查询",
        "schedule": "/api/schedule - 课表查询",
        "training_plan": "/api/training-plan/my - 培养方案",
        "academic_progress": "/api/academic-progress - 学业进度",
        "exam_schedule": "/api/exam-schedule - 考试安排",
        "teacher_search": "/api/teacher/search - 教师查询",
        "course_search": "/api/course/search - 课程查询",
        "all_data": "/api/all-data - 所有数据（用于向量化）",
        "health": "/api/health - 健康检查"
    }
    
    # 添加 Chat API
    if CHAT_API_AVAILABLE:
        endpoints["chat"] = "/api/chat/send - AI对话"
        endpoints["conversations"] = "/api/chat/conversations/{username} - 对话列表"
    
    return {
        "message": "教务系统 AI 助手 API",
        "version": "1.0.0",
        "docs": "/api - 查看完整 API 列表",
        "endpoints": endpoints
    }


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


# 验证码 session 存储
CAPTCHA_SESSIONS = {}

@app.get("/api/captcha")
async def get_captcha(username: str = None):
    """
    获取验证码图片
    返回 base64 编码的图片
    参数: username - 用于选择服务器（可选）
    """
    try:
        # 根据学号选择服务器，确保验证码和登录使用同一服务器
        if username and username.isdigit():
            server_index = int(username) % len(SERVERS)
            server_url = SERVERS[server_index]
        else:
            # 默认使用第一个服务器
            server_index = 0
            server_url = SERVERS[0]
        
        captcha_url = f"{server_url}verifycode.servlet"
        logger.info(f"【验证码】使用服务器: {server_url}")

        # 请求验证码图片
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        })
        
        response = session.get(
            captcha_url,
            timeout=10
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"获取验证码失败: {response.status_code}"
            )

        # 将图片转换为 base64
        image_base64 = base64.b64encode(response.content).decode("utf-8")
        
        # 生成临时验证码 session ID，包含服务器信息
        import time
        timestamp = time.time()
        captcha_session_id = f"captcha_{timestamp}_{server_index}"
        CAPTCHA_SESSIONS[captcha_session_id] = session
        logger.info(f"【验证码】生成 session: {captcha_session_id}")

        return {
            "success": True,
            "image": f"data:image/jpeg;base64,{image_base64}",
            "captcha_session_id": captcha_session_id
        }

    except Exception as e:
        logger.error(f"【验证码】获取失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取验证码失败: {str(e)}")


@app.post("/api/login")
async def login(request: Request):
    """
    登录接口
    参数: username, password, code (验证码), captcha_session_id
    """
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        code = data.get("code")
        captcha_session_id = data.get("captcha_session_id")

        # 验证参数
        if not all([username, password, code]):
            raise HTTPException(status_code=400, detail="缺少必要参数")

        # 获取验证码 session
        # 从 captcha_session_id 中提取服务器索引
        server_index = None
        if captcha_session_id:
            parts = captcha_session_id.split('_')
            if len(parts) >= 3:
                try:
                    server_index = int(parts[2])
                    logger.info(f"【登录】从 session 提取服务器索引: {server_index}")
                except ValueError:
                    pass
        
        if captcha_session_id and captcha_session_id in CAPTCHA_SESSIONS:
            session = CAPTCHA_SESSIONS[captcha_session_id]
            # 清理已使用的验证码 session
            del CAPTCHA_SESSIONS[captcha_session_id]
            logger.info(f"【登录】使用验证码 session: {captcha_session_id}")
        else:
            # 验证码 session 不存在或已过期
            logger.warning(f"【登录】验证码 session 不存在: {captcha_session_id}")
            logger.warning(f"【登录】当前可用 sessions: {list(CAPTCHA_SESSIONS.keys())}")
            return {
                "success": False,
                "message": "验证码已过期，请刷新验证码后重试"
            }

        # 选择服务器（优先使用验证码时选择的服务器）
        if server_index is not None and 0 <= server_index < len(SERVERS):
            server_url = SERVERS[server_index]
            logger.info(f"【登录】使用验证码时的服务器: {server_url}")
        else:
            server_url = select_server(username)
            logger.info(f"【登录】根据学号选择服务器: {server_url}")
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

        logger.info(f"【登录】响应内容长度: {len(response.content)}")

        # 尝试多种编码解析响应内容
        # 教务系统通常使用 GBK/GB2312 编码
        for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
            try:
                response.encoding = encoding
                content = response.text
                # 如果能正常解码且包含中文，就使用这个编码
                if any(c in content for c in ['用户', '密码', '验证', '登录', 'framework']):
                    logger.info(f"【登录】使用编码: {encoding}")
                    break
            except Exception:
                continue
        else:
            response.encoding = response.apparent_encoding
            content = response.text
        
        logger.info(f"【登录】响应编码: {response.encoding}")
        logger.info(f"【登录】响应内容预览: {content[:200]}")

        # 检查登录失败的明确标志
        if "密码错误" in content or "验证码错误" in content or "用户名不存在" in content:
            logger.warning(f"【登录】登录失败: 密码错误或验证码错误")
            return {
                "success": False,
                "message": "用户名、密码或验证码错误"
            }

        # 检查是否停留在登录页面（说明登录失败）
        # 登录页面特征：包含登录表单且 URL 不是 framework
        is_login_page = (
            ("LoginToXkLdap" in content or ("用户名" in content and "密码" in content and "验证码" in content))
            and "framework" not in response.url
        )
        if is_login_page:
            logger.warning(f"【登录】登录失败: 仍在登录页面")
            # 尝试提取具体错误信息
            error_msg = "登录失败，请检查用户名、密码或验证码"
            if "密码错误" in content:
                error_msg = "密码错误"
            elif "验证码错误" in content:
                error_msg = "验证码错误"
            elif "用户名不存在" in content:
                error_msg = "用户名不存在"
            return {
                "success": False,
                "message": error_msg
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


@app.get("/api/schedule")
async def get_schedule_api(username: str, semester: str = "", week: str = ""):
    """
    获取学期课表
    参数:
    - semester: 学期，如 "2024-2025-2"
    - week: 周次，如 "1", "5"，为空则获取全部周次
    """
    try:
        if username not in SESSIONS:
            raise HTTPException(status_code=401, detail="未登录，请先登录")

        session = SESSIONS[username]
        scraper = JwxtScraper(session, JWXT_BASE_URL)

        result = scraper.get_schedule(semester=semester, week=week)

        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "count": result.get("count", 0),
                "semester": result.get("semester", ""),
                "week": result.get("week", ""),
                "未安排时间课程": result.get("未安排时间课程", [])
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "获取课表失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取课表失败: {str(e)}")


@app.get("/api/training-plan/my")
async def get_my_training_plan_api(username: str):
    """
    获取我的培养方案
    """
    try:
        if username not in SESSIONS:
            raise HTTPException(status_code=401, detail="未登录，请先登录")

        session = SESSIONS[username]
        scraper = JwxtScraper(session, JWXT_BASE_URL)

        result = scraper.get_my_training_plan()

        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "count": result.get("count", 0)
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "获取培养方案失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取培养方案失败: {str(e)}")


@app.get("/api/academic-progress")
async def get_academic_progress_api(username: str, study_type: str = "0"):
    """
    获取学业进度
    参数:
    - study_type: 修读类型 (0=主修, 1=辅修)
    """
    try:
        if username not in SESSIONS:
            raise HTTPException(status_code=401, detail="未登录，请先登录")

        session = SESSIONS[username]
        scraper = JwxtScraper(session, JWXT_BASE_URL)

        result = scraper.get_academic_progress(study_type=study_type)

        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "count": result.get("count", 0)
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "获取学业进度失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取学业进度失败: {str(e)}")


@app.get("/api/exam-schedule")
async def get_exam_schedule_api(username: str, semester: str = ""):
    """
    获取考试安排
    参数:
    - semester: 学期，如 "2024-2025-1"
    """
    try:
        if username not in SESSIONS:
            raise HTTPException(status_code=401, detail="未登录，请先登录")

        session = SESSIONS[username]
        scraper = JwxtScraper(session, JWXT_BASE_URL)

        result = scraper.get_exam_schedule(semester=semester)

        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "count": result.get("count", 0),
                "semester": result.get("semester", "")
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "获取考试安排失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取考试安排失败: {str(e)}")


@app.get("/api/teacher/search")
async def search_teacher_api(name: str = "", department: str = ""):
    """
    查询教师信息
    参数:
    - name: 教师姓名（支持模糊查询）
    - department: 所属院系代码
    """
    try:
        # 教师查询不需要登录
        scraper = JwxtScraper(None, JWXT_BASE_URL)

        result = scraper.search_teacher(name=name, department=department)

        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "count": result.get("count", 0)
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "查询教师失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询教师失败: {str(e)}")


@app.get("/api/course/search")
async def search_course_api(course_name: str = "", course_code: str = "", department: str = ""):
    """
    查询课程信息
    参数:
    - course_name: 课程名称
    - course_code: 课程代码
    - department: 开课院系
    """
    try:
        # 课程查询不需要登录
        scraper = JwxtScraper(None, JWXT_BASE_URL)

        result = scraper.search_course(course_name=course_name, course_code=course_code, department=department)

        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "count": result.get("count", 0)
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "查询课程失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询课程失败: {str(e)}")


@app.get("/api/course-selection")
async def get_course_selection_api(username: str):
    """
    获取选课信息
    """
    try:
        if username not in SESSIONS:
            raise HTTPException(status_code=401, detail="未登录，请先登录")

        session = SESSIONS[username]
        scraper = JwxtScraper(session, JWXT_BASE_URL)

        result = scraper.get_course_selection_info()

        if result["success"]:
            return {
                "success": True,
                "data": result["data"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "获取选课信息失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取选课信息失败: {str(e)}")


@app.get("/api/execution-plan")
async def get_execution_plan_api(username: str):
    """
    获取执行计划
    """
    try:
        if username not in SESSIONS:
            raise HTTPException(status_code=401, detail="未登录，请先登录")

        session = SESSIONS[username]
        scraper = JwxtScraper(session, JWXT_BASE_URL)

        result = scraper.get_execution_plan()

        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "count": result.get("count", 0)
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "获取执行计划失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取执行计划失败: {str(e)}")


@app.get("/api/all-data")
async def get_all_data_api(username: str):
    """
    获取所有数据（用于向量化/RAG）
    聚合所有类型的数据，便于一次性存储到向量数据库
    """
    try:
        if username not in SESSIONS:
            raise HTTPException(status_code=401, detail="未登录，请先登录")

        session = SESSIONS[username]
        scraper = JwxtScraper(session, JWXT_BASE_URL)

        result = scraper.get_all_data_for_vectorization()

        if result["success"]:
            return {
                "success": True,
                "data": result["data"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "获取数据失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


# ============== 选项查询接口（AI工具）==============

@app.get("/api/options/departments")
async def get_departments_api(keyword: str = "", include_admin: bool = False, include_vocational: bool = False):
    """
    获取院系列表
    参数:
    - keyword: 搜索关键词
    - include_admin: 是否包含职能部门
    - include_vocational: 是否包含联合培养学院
    """
    try:
        if keyword:
            result = query_departments(keyword)
        else:
            result = EducationOptions.get_departments(include_admin, include_vocational)
        return {"success": True, "data": result, "count": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询院系失败: {str(e)}")


@app.get("/api/options/semesters")
async def get_semesters_api(include_past: bool = True, include_future: bool = False):
    """
    获取学期列表
    参数:
    - include_past: 是否包含过去的学期
    - include_future: 是否包含未来的学期
    """
    try:
        result = query_semesters(include_past, include_future)
        return {"success": True, "data": result, "count": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询学期失败: {str(e)}")


@app.get("/api/options/current-semester")
async def get_current_semester_api():
    """获取当前学期"""
    try:
        result = EducationOptions.get_current_semester()
        return {"success": True, "data": {"code": result, "name": get_option_description("semester", result)}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取当前学期失败: {str(e)}")


@app.get("/api/options/course")
async def get_course_options_api():
    """获取课程相关选项"""
    try:
        result = query_course_options()
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询课程选项失败: {str(e)}")


@app.get("/api/options/schedule")
async def get_schedule_options_api():
    """获取课表相关选项"""
    try:
        result = query_schedule_options()
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询课表选项失败: {str(e)}")


@app.get("/api/options/grade")
async def get_grade_options_api():
    """获取成绩查询相关选项"""
    try:
        result = query_grade_options()
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询成绩选项失败: {str(e)}")


@app.get("/api/options/all")
async def get_all_options_api():
    """获取所有选项数据"""
    try:
        result = EducationOptions.get_all_options()
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询所有选项失败: {str(e)}")


@app.get("/api")
async def api_list():
    """
    API 列表
    """
    return {
        "message": "教务系统 AI 助手 API 列表",
        "apis": {
            "验证码": "/api/captcha - 获取验证码",
            "登录": "/api/login - 登录",
            "个人信息": "/api/user/info?username=xxx",
            "学籍卡片": "/api/user/card?username=xxx",
            "成绩查询": "/api/grades?username=xxx",
            "所有成绩": "/api/grades/all?username=xxx",
            "课表查询": "/api/schedule?username=xxx&semester=2024-2025-2",
            "我的培养方案": "/api/training-plan/my?username=xxx",
            "学业进度": "/api/academic-progress?username=xxx",
            "考试安排": "/api/exam-schedule?username=xxx&semester=2024-2025-1",
            "教师查询": "/api/teacher/search?name=xxx",
            "课程查询": "/api/course/search?course_name=xxx",
            "选课信息": "/api/course-selection?username=xxx",
            "执行计划": "/api/execution-plan?username=xxx",
            "所有数据": "/api/all-data?username=xxx - 用于向量化/RAG",
            "选项查询": {
                "院系列表": "/api/options/departments",
                "学期列表": "/api/options/semesters",
                "当前学期": "/api/options/current-semester",
                "课程选项": "/api/options/course",
                "课表选项": "/api/options/schedule",
                "成绩选项": "/api/options/grade",
                "所有选项": "/api/options/all",
            },
            "健康检查": "/api/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
