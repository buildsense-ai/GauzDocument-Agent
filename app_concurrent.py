#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 服务 - 并发优化版
支持上游agent的并行调用，优化资源管理和并发处理
"""

import sys
import os
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import threading

# FastAPI 相关导入
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 加载环境变量 - 修复：显式指定.env文件路径
env_path = Path(__file__).parent / '.env'
print(f"🔧 [app_concurrent] 加载环境文件: {env_path}")
if env_path.exists():
    load_dotenv(env_path)
    print("✅ [app_concurrent] .env文件加载成功")
    # 验证关键配置是否加载
    max_steps = os.getenv('MAX_REACT_STEPS')
    deepseek_key = os.getenv('DEEPSEEK_API_KEY')
    if max_steps and deepseek_key:
        print(f"✅ [app_concurrent] 配置验证: MAX_REACT_STEPS={max_steps}, API密钥已加载")
    else:
        print("⚠️ [app_concurrent] 警告: 部分配置可能未正确加载")
else:
    print(f"❌ [app_concurrent] 错误: .env文件不存在于 {env_path}")
    load_dotenv()  # 回退到默认行为

# 确保日志目录存在
os.makedirs('logs', exist_ok=True)

# 配置日志
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/fastapi_concurrent.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

def setup_environment():
    """设置环境"""
    # 从环境变量获取目录配置
    storage_dir = os.getenv("RAG_STORAGE_DIR", "pdf_embedding_storage")
    
    # 创建必要的目录
    os.makedirs(storage_dir, exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # 设置环境变量（如果需要）
    os.environ.setdefault("PYTHONPATH", ".")
    
    # 检查必要的环境变量
    # 检查DeepSeek API密钥（用于对话）
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        logger.error("缺少DeepSeek API密钥")
        raise RuntimeError("缺少DeepSeek API密钥，请在环境变量中设置 DEEPSEEK_API_KEY")
    
    # 检查Qwen API密钥（用于embedding）
    qwen_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    if not qwen_key:
        logger.error("缺少Qwen API密钥")
        raise RuntimeError("缺少Qwen API密钥，请在环境变量中设置 QWEN_API_KEY 或 DASHSCOPE_API_KEY")
    
    print("✅ 环境变量检查完成：DeepSeek用于对话，Qwen用于embedding")
    
    logger.info("环境设置完成")

# 在导入React Agent之前设置环境
setup_environment()

try:
    from react_rag_agent import SimplifiedReactAgent
    logger.info("✅ React Agent组件导入成功")
except ImportError as e:
    logger.error(f"❌ 组件导入失败: {e}")
    raise

# Pydantic 模型定义
class QueryRequest(BaseModel):
    """查询请求模型"""
    query: str = Field(..., description="用户的自然语言查询", example="请全面介绍中山纪念堂")

class FinalAnswerResponse(BaseModel):
    """最终答案响应模型"""
    retrieved_text: str = Field(..., description="检索到的文本内容")

class QueryResponse(BaseModel):
    """查询响应模型"""
    final_answer: FinalAnswerResponse = Field(..., description="最终答案")

class ConcurrencyManager:
    """并发管理器 - 优化并发处理"""
    
    def __init__(self, max_concurrent: int = 10, max_workers: int = 5):
        self.max_concurrent = max_concurrent
        self.max_workers = max_workers
        
        # 并发控制
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        
        # React Agent池 - 避免单例问题
        self.agent_pool = []
        self.agent_lock = threading.Lock()
        
        # 统计信息
        self.active_requests = 0
        self.total_requests = 0
        self.request_lock = threading.Lock()
        
        logger.info(f"🔧 并发管理器初始化: 最大并发={max_concurrent}, 工作线程={max_workers}")
    
    def initialize_agent_pool(self, pool_size: int = 3):
        """初始化React Agent池"""
        logger.info(f"🤖 初始化React Agent池: {pool_size}个实例")
        
        storage_dir = os.getenv("RAG_STORAGE_DIR", "pdf_embedding_storage")
        
        for i in range(pool_size):
            try:
                agent = SimplifiedReactAgent(storage_dir=storage_dir)
                self.agent_pool.append(agent)
                logger.info(f"✅ Agent {i+1} 初始化成功")
            except Exception as e:
                logger.error(f"❌ Agent {i+1} 初始化失败: {e}")
                raise
        
        logger.info(f"🎉 React Agent池初始化完成: {len(self.agent_pool)}个可用实例")
    
    def get_agent(self):
        """获取一个可用的React Agent"""
        with self.agent_lock:
            if not self.agent_pool:
                raise RuntimeError("没有可用的React Agent实例")
            
            # 简单的轮询策略
            agent = self.agent_pool.pop(0)
            return agent
    
    def return_agent(self, agent):
        """归还React Agent到池中"""
        with self.agent_lock:
            self.agent_pool.append(agent)
    
    def update_stats(self, increment: bool = True):
        """更新统计信息"""
        with self.request_lock:
            if increment:
                self.active_requests += 1
                self.total_requests += 1
            else:
                self.active_requests -= 1
    
    async def process_query_async(self, query: str) -> str:
        """异步处理查询"""
        # 并发控制
        async with self.semaphore:
            self.update_stats(True)
            
            try:
                # 在线程池中执行同步的React Agent处理
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.thread_pool, 
                    self._process_query_sync, 
                    query
                )
                return result
            
            finally:
                self.update_stats(False)
    
    def _process_query_sync(self, query: str) -> str:
        """同步处理查询 - 在线程池中执行"""
        agent = None
        try:
            # 获取Agent实例
            agent = self.get_agent()
            
            # 处理查询
            result = agent.process_query(query)
            return result
            
        except Exception as e:
            logger.error(f"❌ 查询处理异常: {e}")
            raise
        
        finally:
            # 归还Agent实例
            if agent:
                self.return_agent(agent)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.request_lock:
            return {
                "active_requests": self.active_requests,
                "total_requests": self.total_requests,
                "available_agents": len(self.agent_pool),
                "max_concurrent": self.max_concurrent,
                "max_workers": self.max_workers
            }

# 创建FastAPI应用
app = FastAPI(
    title="ReAct Agent 文档查询API - 并发优化版",
    description="支持并发处理的智能文档检索系统，适用于上游agent并行调用",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局并发管理器
concurrency_manager = None

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    global concurrency_manager
    try:
        logger.info("🚀 FastAPI并发优化版服务启动中...")
        
        # 获取并发配置
        max_concurrent = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
        max_workers = int(os.getenv("MAX_WORKER_THREADS", "5"))
        agent_pool_size = int(os.getenv("AGENT_POOL_SIZE", "3"))
        
        # 初始化并发管理器
        concurrency_manager = ConcurrencyManager(max_concurrent, max_workers)
        concurrency_manager.initialize_agent_pool(agent_pool_size)
        
        logger.info("✅ FastAPI并发优化版服务启动完成！")
        logger.info("🎯 API文档地址: http://localhost:8000/docs")
        logger.info(f"⚡ 并发配置: 最大并发={max_concurrent}, 线程池={max_workers}, Agent池={agent_pool_size}")
        
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    global concurrency_manager
    logger.info("👋 FastAPI服务正在关闭...")
    
    if concurrency_manager:
        # 关闭线程池
        concurrency_manager.thread_pool.shutdown(wait=True)
        logger.info("✅ 线程池已关闭")

@app.get("/")
async def root():
    """根路径 - 服务状态检查"""
    global concurrency_manager
    
    stats = concurrency_manager.get_stats() if concurrency_manager else {}
    
    return {
        "service": "ReAct Agent 文档查询API - 并发优化版",
        "status": "running",
        "version": "2.0.0",
        "concurrent_stats": stats,
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    """健康检查接口"""
    global concurrency_manager
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "concurrency_manager": concurrency_manager is not None,
            "deepseek_api": os.getenv("DEEPSEEK_API_KEY") is not None,
            "qwen_api": os.getenv("QWEN_API_KEY") is not None or os.getenv("DASHSCOPE_API_KEY") is not None,
            "environment": os.getenv("DEEPSEEK_API_KEY") is not None and (os.getenv("QWEN_API_KEY") is not None or os.getenv("DASHSCOPE_API_KEY") is not None)
        }
    }
    
    if concurrency_manager:
        stats = concurrency_manager.get_stats()
        health_status["concurrent_stats"] = stats
        
        # 检查是否有可用的Agent
        if stats["available_agents"] == 0 and stats["active_requests"] == 0:
            health_status["status"] = "degraded"
            health_status["warning"] = "No available agents"
    
    # 检查所有组件是否正常
    all_healthy = all(health_status["components"].values())
    if not all_healthy:
        health_status["status"] = "unhealthy"
        return JSONResponse(
            status_code=503,
            content=health_status
        )
    
    return health_status

@app.get("/stats")
async def get_stats():
    """获取并发统计信息"""
    global concurrency_manager
    
    if not concurrency_manager:
        raise HTTPException(status_code=503, detail="并发管理器未初始化")
    
    return {
        "concurrent_stats": concurrency_manager.get_stats(),
        "timestamp": datetime.now().isoformat()
    }

def extract_retrieved_text(final_answer: str) -> str:
    """提取retrieved_text内容"""
    try:
        if isinstance(final_answer, str):
            # 尝试解析JSON
            try:
                final_answer_data = json.loads(final_answer)
                if isinstance(final_answer_data, dict):
                    # 处理多种可能的格式
                    if "retrieved_text" in final_answer_data:
                        retrieved_text_data = final_answer_data["retrieved_text"]
                        if isinstance(retrieved_text_data, list):
                            # 如果是列表，提取所有内容
                            contents = []
                            for item in retrieved_text_data:
                                if isinstance(item, dict) and "content" in item:
                                    contents.append(item["content"])
                                elif isinstance(item, str):
                                    contents.append(item)
                            return "\n\n".join(contents)
                        elif isinstance(retrieved_text_data, str):
                            return retrieved_text_data
                    else:
                        # 如果没有retrieved_text字段，返回整个内容的字符串表示
                        return json.dumps(final_answer_data, ensure_ascii=False, indent=2)
                else:
                    return str(final_answer_data)
            except json.JSONDecodeError:
                # 如果不是JSON，直接返回原始字符串
                return final_answer
        else:
            return str(final_answer)
    except Exception as e:
        logger.error(f"❌ 提取retrieved_text失败: {e}")
        return str(final_answer)

@app.post("/react_agent", response_model=QueryResponse)
async def react_agent_query(request: QueryRequest):
    """
    ReAct Agent 文档查询接口 - 并发优化版
    
    支持上游agent的并行调用，通过Agent池和线程池实现高并发处理
    """
    global concurrency_manager
    
    try:
        logger.info(f"📝 收到查询请求: {request.query}")
        
        # 检查并发管理器是否已初始化
        if concurrency_manager is None:
            logger.error("❌ 并发管理器未初始化")
            raise HTTPException(
                status_code=503, 
                detail="并发管理器未可用，请稍后重试"
            )
        
        # 使用并发管理器处理查询
        start_time = datetime.now()
        logger.info(f"🚀 开始并发处理查询: {request.query}")
        
        # 异步调用React Agent
        result_json = await concurrency_manager.process_query_async(request.query)
        
        # 解析结果
        result_data = json.loads(result_json)
        logger.info(f"✅ React Agent处理完成")
        
        # 检查处理结果
        if result_data.get("status") != "success":
            error_msg = result_data.get("error", "处理失败")
            logger.error(f"❌ React Agent处理失败: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"查询处理失败: {error_msg}"
            )
        
        # 提取最终答案
        final_answer_raw = result_data.get("final_answer", "")
        
        # 处理最终答案，确保符合要求的格式
        retrieved_text = extract_retrieved_text(final_answer_raw)
        
        # 构建响应
        response = QueryResponse(
            final_answer=FinalAnswerResponse(
                retrieved_text=retrieved_text
            )
        )
        
        # 记录处理时间
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"📊 查询处理完成 - 耗时: {processing_time:.2f}秒")
        logger.info(f"📄 返回内容长度: {len(retrieved_text)}字符")
        
        return response
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"❌ 接口处理异常: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部服务错误: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    
    # 从环境变量获取配置
    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", "8000"))
    
    logger.info(f"🌐 启动FastAPI并发优化版服务: http://{host}:{port}")
    logger.info(f"📚 API文档: http://{host}:{port}/docs")
    
    uvicorn.run(
        "app_concurrent:app",
        host=host,
        port=port,
        reload=False,  # 生产模式，关闭热重载
        log_level="info",
        workers=1  # 使用单进程，通过内部线程池处理并发
    ) 