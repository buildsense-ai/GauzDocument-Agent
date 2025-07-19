#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
React Agent 并发优化版启动脚本
支持15个章节并行处理的FastAPI服务
"""

import os
import sys
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量 - 修复：显式指定.env文件路径
env_path = Path(__file__).parent / '.env'
print(f"🔧 加载环境文件: {env_path}")
if env_path.exists():
    load_dotenv(env_path)
    print("✅ .env文件加载成功")
    # 验证关键配置是否加载
    max_steps = os.getenv('MAX_REACT_STEPS')
    deepseek_key = os.getenv('DEEPSEEK_API_KEY')
    if max_steps and deepseek_key:
        print(f"✅ 配置验证: MAX_REACT_STEPS={max_steps}, API密钥已加载")
    else:
        print("⚠️ 警告: 部分配置可能未正确加载")
else:
    print(f"❌ 错误: .env文件不存在于 {env_path}")
    load_dotenv()  # 回退到默认行为

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

def setup_concurrent_environment():
    """设置并发优化环境变量"""
    
    # 并发配置优化
    concurrent_configs = {
        # React Agent配置 (已优化)
        "MAX_REACT_STEPS": "1",                    # 1步循环
        "QWEN_MODEL": "qwen-plus",                 # 高性能模型  
        "QWEN_MAX_TOKENS": "1500",                 # 优化令牌数
        "QWEN_TEMPERATURE": "0.0",                 # 提高确定性
        "QWEN_TIMEOUT": "25",                      # 快速超时
        
        # 并发控制配置 (新增)
        "MAX_CONCURRENT_REQUESTS": "15",           # 最大并发请求数 (适合上游15个章节)
        "MAX_WORKER_THREADS": "8",                 # 线程池大小
        "AGENT_POOL_SIZE": "5",                    # React Agent池大小
        
        # 搜索优化配置
        "VECTOR_SIMILARITY_WEIGHT": "0.5",         # 平衡向量计算
        "BM25_SCORE_WEIGHT": "0.5",                # 平衡BM25计算
        "ENABLE_QUERY_CACHE": "true",              # 启用缓存
        "SMART_TERMINATION": "true",               # 智能终止
        
        # 日志优化
        "LOG_LEVEL": "WARNING",                    # 减少日志输出
        
        # FastAPI配置
        "FASTAPI_HOST": "0.0.0.0",
        "FASTAPI_PORT": "8000"
    }
    
    print("🔧 设置并发优化环境变量...")
    for key, value in concurrent_configs.items():
        if not os.getenv(key):  # 只设置未配置的环境变量
            os.environ[key] = value
            print(f"  ✅ {key}={value}")
        else:
            print(f"  ↪️ {key}={os.getenv(key)} (已配置)")

if __name__ == "__main__":
    print("🚀 启动React Agent并发优化版服务")
    print("🎯 支持15个章节并行处理") 
    print("="*50)
    
    # 设置并发优化环境
    setup_concurrent_environment()
    
    # 获取配置
    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", "8000"))
    max_concurrent = os.getenv("MAX_CONCURRENT_REQUESTS", "15")
    max_workers = os.getenv("MAX_WORKER_THREADS", "8")
    agent_pool = os.getenv("AGENT_POOL_SIZE", "5")
    
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
    print(f"  Agent池: {agent_pool}个实例")
    print(f"  React步骤: {os.getenv('MAX_REACT_STEPS', '1')}步")
    
    print(f"\n🔍 主要接口:")
    print(f"  POST /react_agent - 文档查询")
    print("="*50)
    print("✅ 启动服务...")
    
    # 启动并发优化版服务
    uvicorn.run(
        "app_concurrent:app",
        host=host,
        port=port,
        reload=False,           # 生产模式
        log_level="info",
        access_log=True,
        workers=1               # 单进程多线程模式
    ) 