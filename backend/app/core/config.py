"""
后端核心配置常量。
"""

import os

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

PUBLIC_SERVERS = [
    JWXT_BASE_URL,
]


def normalize_jwxt_base_url(raw_url: str) -> str:
    normalized = (raw_url or "").strip()
    if not normalized:
        return ""
    if not normalized.endswith("/"):
        normalized = f"{normalized}/"
    if "/jsxsd/" not in normalized:
        normalized = f"{normalized}jsxsd/"
    return normalized


def get_server_candidates(preferred_index: int | None = None) -> list[str]:
    """
    返回教务入口候选列表。
    优先顺序：
    1. 显式环境变量 `EDUCATION_SYSTEM_URL`
    2. 学号映射到的内网地址
    3. 其余内网地址
    4. 公网 JWXT_BASE_URL
    """
    candidates: list[str] = []
    configured = normalize_jwxt_base_url(os.getenv("EDUCATION_SYSTEM_URL", "") or "")
    if configured:
        candidates.append(configured)

    ordered_servers = list(SERVERS)
    if preferred_index is not None and 0 <= preferred_index < len(SERVERS):
        preferred = SERVERS[preferred_index]
        ordered_servers = [preferred] + [server for server in SERVERS if server != preferred]

    for server in ordered_servers + PUBLIC_SERVERS:
        if server not in candidates:
            candidates.append(server)
    return candidates
