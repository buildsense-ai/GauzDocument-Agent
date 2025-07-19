#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 启动脚本
简化版启动脚本，用于快速启动API服务
"""

import os
import sys
import uvicorn
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

if __name__ == "__main__":
    # 配置服务参数
    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", "8000"))
    
    print("🚀 启动ReAct Agent FastAPI服务")
    print(f"🌐 服务地址: http://{host}:{port}")
    print(f"📚 API文档: http://{host}:{port}/docs")
    print(f"🔍 ReAct Agent接口: POST http://{host}:{port}/react_agent")
    print("=" * 60)
    
    # 启动服务
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=False,  # 生产模式，关闭热重载
        log_level="info",
        access_log=True
    ) 