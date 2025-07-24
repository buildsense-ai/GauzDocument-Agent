#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立工具版本启动脚本
直接提供模版搜索和文档搜索工具，无需React Agent决策
"""

import os
import sys
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parent / '.env'
print(f"🔧 加载环境文件: {env_path}")
if env_path.exists():
    load_dotenv(env_path)
    print("✅ .env文件加载成功")
    max_steps = os.getenv('MAX_REACT_STEPS')
    deepseek_key = os.getenv('DEEPSEEK_API_KEY')
    if max_steps and deepseek_key:
        print(f"✅ 配置验证: MAX_REACT_STEPS={max_steps}, API密钥已加载")
    else:
        print("⚠️ 警告: 部分配置可能未正确加载")
else:
    print(f"❌ 错误: .env文件不存在于 {env_path}")
    load_dotenv()

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

def setup_independent_environment():
    """设置独立工具环境变量"""
    
    independent_configs = {
        # 工具配置
        "QWEN_MODEL": "qwen-plus",
        "QWEN_MAX_TOKENS": "1500",
        "QWEN_TEMPERATURE": "0.0",
        "QWEN_TIMEOUT": "25",
        
        # 并发控制配置
        "MAX_CONCURRENT_REQUESTS": "12",
        "MAX_WORKER_THREADS": "8", 
        "TOOL_POOL_SIZE": "10",  # 工具池大小 - 增加到10个以应对并发需求
        
        # 搜索优化配置
        "VECTOR_SIMILARITY_WEIGHT": "0.7",
        "BM25_SCORE_WEIGHT": "0.3",
        "ENABLE_QUERY_CACHE": "true",
        
        # 日志配置
        "LOG_LEVEL": "INFO",
        
        # FastAPI配置
        "FASTAPI_HOST": "0.0.0.0",
        "FASTAPI_PORT": "8001"  # 使用不同端口
    }
    
    print("🔧 设置独立工具环境变量...")
    for key, value in independent_configs.items():
        if not os.getenv(key):
            os.environ[key] = value
            print(f"  ✅ {key}={value}")
        else:
            print(f"  ↪️ {key}={os.getenv(key)} (已配置)")

if __name__ == "__main__":
    print("🚀 启动独立工具API服务")
    print("🛠️ 无React Agent，直接提供工具接口")
    print("="*50)
    
    # 设置独立工具环境
    setup_independent_environment()
    
    # 获取配置
    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", "8001"))
    max_concurrent = os.getenv("MAX_CONCURRENT_REQUESTS", "15")
    max_workers = os.getenv("MAX_WORKER_THREADS", "8")
    tool_pool = os.getenv("TOOL_POOL_SIZE", "5")
    
    # 检查API密钥
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    qwen_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    
    if deepseek_key and qwen_key:
        print(f"✅ DeepSeek API密钥已配置: {deepseek_key[:8]}***")
        print(f"✅ Qwen API密钥已配置: {qwen_key[:8]}***")
        print("🔧 混合配置: DeepSeek用于对话，Qwen用于embedding")
    else:
        missing = []
        if not deepseek_key:
            missing.append("DEEPSEEK_API_KEY")
        if not qwen_key:
            missing.append("QWEN_API_KEY/DASHSCOPE_API_KEY")
        print(f"⚠️ 警告: 缺少API密钥 {missing}，某些功能可能受限")
    
    print(f"\n🌐 服务配置:")
    print(f"  地址: http://{host}:{port}")
    print(f"  文档: http://{host}:{port}/docs")
    print(f"  状态: http://{host}:{port}/stats")
    print(f"  健康: http://{host}:{port}/health")
    
    print(f"\n⚡ 并发配置:")
    print(f"  最大并发: {max_concurrent}个请求")
    print(f"  线程池: {max_workers}个线程")
    print(f"  工具池: {tool_pool}个实例")
    
    print(f"\n🔍 主要接口:")
    print(f"  POST /template_search - 模版搜索 (ElasticSearch + LLM重排序)")
    print(f"  POST /document_search - 文档搜索 (统一内容搜索)")
    print(f"  POST /react_agent - 兼容性接口 (重定向到文档搜索)")
    
    print("="*50)
    print("✅ 启动服务...")
    
    # 启动独立工具API服务
    uvicorn.run(
        "app_independent_tools:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
        access_log=True,
        workers=1
    ) 