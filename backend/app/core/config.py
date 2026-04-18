"""
后端核心配置常量。
"""

JWXT_BASE_URL = "http://jwxt.gdufe.edu.cn/jsxsd/"
VERIFY_CODE_URL = f"{JWXT_BASE_URL}verifycode.servlet"
LOGIN_URL = f"{JWXT_BASE_URL}xk/LoginToXkLdap"

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

