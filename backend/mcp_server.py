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

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.mcp.tools import mcp

if __name__ == "__main__":
    print("🚀 启动教务系统 MCP Server...")
    print("📋 可用工具:")
    print("  - query_grades: 查询成绩")
    print("  - query_schedule: 查询课表")
    print("  - query_academic_progress: 查询学业进度")
    print("  - query_training_plan: 查询培养方案")
    print("  - query_exam_schedule: 查询考试安排")
    print("  - query_personal_info: 查询个人信息")
    print()
    
    # 启动MCP服务（stdio模式）
    mcp.run()
