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
        response = session.post(
            login_url,
            data=login_data,
            timeout=10
        )

        # 检查登录结果
        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"登录请求失败: {response.status_code}"
            )

        # 检查是否登录成功（根据教务系统返回的页面判断）
        response.encoding = "utf-8"
        content = response.text

        # 简单判断：如果返回的页面包含错误信息，说明登录失败
        if "密码错误" in content or "验证码错误" in content or "用户名不存在" in content:
            return {
                "success": False,
                "message": "用户名、密码或验证码错误"
            }

        # 如果成功跳转到主页，说明登录成功
        if "/jsxsd/framework/" in content or "首页" in content:
            # 保存 session
            SESSIONS[username] = session

            return {
                "success": True,
                "message": "登录成功",
                "username": username,
                "session_id": session.cookies.get("JSESSIONID", "")
            }
        else:
            return {
                "success": False,
                "message": "登录失败，请检查用户名和密码"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
