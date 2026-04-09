"""
测试登录功能 - 检查验证码和登录服务器问题
"""
import requests
import base64

# 外网教务系统
JWXT_BASE_URL = "http://jwxt.gdufe.edu.cn"
VERIFY_CODE_URL = f"{JWXT_BASE_URL}/jsxsd/verifycode.servlet"
LOGIN_URL = f"{JWXT_BASE_URL}/jsxsd/xk/LoginToXkLdap"

# 内网服务器列表
SERVERS = [
    "http://172.19.13.60:80/jsxsd/",
    "http://172.19.13.62:80/jsxsd/",
    "http://172.19.13.61:80/jsxsd/",
]

def test_login_external():
    """测试使用外网服务器登录"""
    print("=" * 50)
    print("测试1: 使用外网服务器登录")
    print("=" * 50)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    # 1. 获取验证码
    print(f"\n1. 获取验证码: {VERIFY_CODE_URL}")
    response = session.get(VERIFY_CODE_URL, timeout=10)
    print(f"   状态码: {response.status_code}")
    print(f"   Cookies: {dict(session.cookies)}")
    
    # 保存验证码图片
    with open("captcha_test.png", "wb") as f:
        f.write(response.content)
    print(f"   验证码已保存到 captcha_test.png")
    
    # 2. 手动输入验证码进行测试
    code = input("\n请输入验证码（查看 captcha_test.png）: ")
    username = input("请输入学号: ")
    password = input("请输入密码: ")
    
    # 3. 登录
    print(f"\n2. 登录: {LOGIN_URL}")
    login_data = {
        "USERNAME": username,
        "PASSWORD": password,
        "RANDOMCODE": code
    }
    
    response = session.post(LOGIN_URL, data=login_data, timeout=10)
    print(f"   状态码: {response.status_code}")
    print(f"   响应URL: {response.url}")
    print(f"   Cookies: {dict(session.cookies)}")
    
    # 检查结果
    content = response.text
    print(f"\n3. 检查结果:")
    print(f"   内容长度: {len(content)}")
    print(f"   包含 'framework': {'framework' in content}")
    print(f"   包含 'LoginToXkLdap': {'LoginToXkLdap' in content}")
    print(f"   包含 '密码错误': {'密码错误' in content}")
    print(f"   包含 '验证码错误': {'验证码错误' in content}")
    
    if "framework" in response.url or "/jsxsd/framework/" in content:
        print("\n✅ 登录成功！")
    else:
        print("\n❌ 登录失败！")
        # 输出部分内容用于调试
        print(f"\n响应内容预览 (前500字符):\n{content[:500]}")


def test_login_internal():
    """测试使用内网服务器登录"""
    print("\n" + "=" * 50)
    print("测试2: 使用内网服务器登录")
    print("=" * 50)
    
    # 选择第一个内网服务器
    server_url = SERVERS[1]  # 172.19.13.62
    verify_url = f"{server_url}verifycode.servlet"
    login_url = f"{server_url}xk/LoginToXkLdap"
    
    print(f"\n使用服务器: {server_url}")
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    # 1. 获取验证码
    print(f"\n1. 获取验证码: {verify_url}")
    try:
        response = session.get(verify_url, timeout=10)
        print(f"   状态码: {response.status_code}")
        print(f"   Cookies: {dict(session.cookies)}")
        
        # 保存验证码图片
        with open("captcha_internal.png", "wb") as f:
            f.write(response.content)
        print(f"   验证码已保存到 captcha_internal.png")
    except Exception as e:
        print(f"   错误: {e}")
        print("   内网服务器可能无法访问，尝试下一个服务器...")
        return
    
    # 2. 手动输入验证码进行测试
    code = input("\n请输入验证码（查看 captcha_internal.png）: ")
    username = input("请输入学号: ")
    password = input("请输入密码: ")
    
    # 3. 登录
    print(f"\n2. 登录: {login_url}")
    login_data = {
        "USERNAME": username,
        "PASSWORD": password,
        "RANDOMCODE": code
    }
    
    response = session.post(login_url, data=login_data, timeout=10)
    print(f"   状态码: {response.status_code}")
    print(f"   响应URL: {response.url}")
    print(f"   Cookies: {dict(session.cookies)}")
    
    # 检查结果
    content = response.text
    print(f"\n3. 检查结果:")
    print(f"   内容长度: {len(content)}")
    print(f"   包含 'framework': {'framework' in content}")
    print(f"   包含 'LoginToXkLdap': {'LoginToXkLdap' in content}")
    
    if "framework" in response.url or "/jsxsd/framework/" in content:
        print("\n✅ 登录成功！")
    else:
        print("\n❌ 登录失败！")


if __name__ == "__main__":
    print("教务系统登录测试")
    print("=" * 50)
    
    # 先测试外网
    test_login_external()
    
    # 询问是否测试内网
    # test_internal = input("\n是否测试内网服务器? (y/n): ")
    # if test_internal.lower() == 'y':
    #     test_login_internal()
