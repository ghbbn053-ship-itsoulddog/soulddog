"""
MCP Server - 教务系统助手
可被OpenClaw、Claude Desktop等支持MCP的AI Agent调用

使用方式:
1. stdio模式（本地调用）:
   python mcp_server.py

2. OpenClaw集成:
   在OpenClaw配置中添加此MCP服务
"""

import sys
from pathlib import Path
import logging

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.mcp.tools import mcp


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("启动教务系统 MCP Server (stdio mode)")
    # 启动MCP服务（stdio模式）
    mcp.run()
