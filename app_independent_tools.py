#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立工具API服务 - 无React Agent版本
直接提供两个独立工具的API接口，无需AI决策步骤
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
from contextlib import asynccontextmanager

# FastAPI 相关导入
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 加载环境变量
env_path = Path(__file__).parent / '.env'
print(f"🔧 [app_independent] 加载环境文件: {env_path}")
if env_path.exists():
    load_dotenv(env_path)
    print("✅ [app_independent] .env文件加载成功")
else:
    print(f"❌ [app_independent] 错误: .env文件不存在于 {env_path}")
    load_dotenv()

# 设置默认环境变量（确保正确的并发配置）
def setup_default_environment():
    """设置默认环境变量"""
    default_configs = {
        "MAX_CONCURRENT_REQUESTS": "15",
        "MAX_WORKER_THREADS": "10", 
        "TOOL_POOL_SIZE": "12",
        "RAG_STORAGE_DIR": "final_chromadb",
        "FASTAPI_HOST": "0.0.0.0",
        "FASTAPI_PORT": "8001"
    }
    
    for key, value in default_configs.items():
        if not os.getenv(key):
            os.environ[key] = value
            print(f"🔧 设置环境变量: {key}={value}")

# 设置环境变量
setup_default_environment()

# 确保日志目录存在
os.makedirs('logs', exist_ok=True)

# 配置日志
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/fastapi_independent.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

def setup_environment():
    """设置环境"""
    storage_dir = os.getenv("RAG_STORAGE_DIR", "final_chromadb")
    os.makedirs(storage_dir, exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.environ.setdefault("PYTHONPATH", ".")
    
    print("✅ 环境设置完成：独立工具模式，无需LLM")
    logger.info("环境设置完成")

# 在导入工具之前设置环境
setup_environment()

# 工具导入 - 现在应该可以正常导入
template_tool_available = False
document_tool_available = False

try:
    from template_search_tool import TemplateSearchTool
    template_tool_available = True
    logger.info("✅ 模板搜索工具导入成功")
except ImportError as e:
    logger.warning(f"⚠️ 模板搜索工具导入失败: {e}")
    logger.info("🔄 将禁用模板搜索功能")
    TemplateSearchTool = None

try:
    from document_search_tool import DocumentSearchTool
    document_tool_available = True
    logger.info("✅ 文档搜索工具导入成功")
except ImportError as e:
    logger.warning(f"⚠️ 文档搜索工具导入失败: {e}")
    logger.info("🔄 将禁用文档搜索功能")
    DocumentSearchTool = None

# 检查至少有一个工具可用
if not template_tool_available and not document_tool_available:
    logger.error("❌ 所有工具都不可用，服务将无法正常工作")
    raise RuntimeError("没有可用的搜索工具")

logger.info(f"✅ 工具状态: 模板搜索={template_tool_available}, 文档搜索={document_tool_available}")

# Pydantic 模型定义
class TemplateSearchRequest(BaseModel):
    """模版搜索请求模型"""
    query: str = Field(..., description="自然语言查询", example="古庙修缮评估报告模板")

class DocumentSearchRequest(BaseModel):
    """文档搜索请求模型"""
    query_text: str = Field(..., description="查询文本", example="古庙历史背景")
    project_name: str = Field(default="all", description="项目名称", example="越秀公园")
    top_k: int = Field(default=5, description="返回结果数量", example=5)
    content_type: str = Field(default="all", description="内容类型", example="all")

class TemplateSearchResponse(BaseModel):
    """模版搜索响应模型"""
    template_content: str = Field(..., description="模版内容")

class DocumentSearchResponse(BaseModel):
    """文档搜索响应模型"""
    retrieved_text: list = Field(..., description="文本内容列表")
    retrieved_image: list = Field(..., description="图片内容列表") 
    retrieved_table: list = Field(..., description="表格内容列表")

class ConcurrencyManager:
    """并发管理器 - 优化并发处理"""
    
    def __init__(self, max_concurrent: int = 20, max_workers: int = 15):
        self.max_concurrent = max_concurrent
        self.max_workers = max_workers
        
        # 文档搜索并发控制（需要线程池和工具池）
        self.document_semaphore = asyncio.Semaphore(max_concurrent)
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        
        # 模板搜索：直接初始化一个实例（使用MySQL连接池，无需并发限制）
        self.template_tool = None
        
        # 文档搜索工具池
        self.document_tools = []
        self.tool_lock = threading.Lock()
        
        # 统计信息
        self.active_requests = 0
        self.total_requests = 0
        self.request_lock = threading.Lock()
        
        logger.info(f"🔧 并发管理器初始化: 文档搜索最大并发={max_concurrent}, 工作线程={max_workers}")
    
    def initialize_tool_pools(self, document_pool_size: int = 8):
        """初始化工具池"""
        logger.info(f"🛠️ 初始化工具池...")
        
        # 初始化单个模板搜索工具（直接使用MySQL连接池）
        if template_tool_available and TemplateSearchTool:
            try:
                self.template_tool = TemplateSearchTool()
                logger.info("✅ 模板搜索工具初始化成功（单实例，使用MySQL连接池）")
            except Exception as e:
                logger.error(f"❌ 模板搜索工具初始化失败: {e}")
                self.template_tool = None
        else:
            logger.info("⚠️ 模板搜索工具不可用")
        
        # 初始化文档搜索工具池（需要多实例处理并发）
        storage_dir = os.getenv("RAG_STORAGE_DIR", "final_chromadb")
        
        for i in range(document_pool_size):
            try:
                if document_tool_available and DocumentSearchTool:
                    logger.info(f"🔧 正在初始化文档搜索工具实例 {i+1}...")
                    document_tool = DocumentSearchTool(storage_dir=storage_dir)
                    self.document_tools.append(document_tool)
                    logger.info(f"✅ 文档搜索工具实例 {i+1} 初始化成功")
                else:
                    logger.warning(f"⚠️ 跳过文档搜索工具实例 {i+1} (工具不可用)")
                    logger.warning(f"   document_tool_available: {document_tool_available}")
                    logger.warning(f"   DocumentSearchTool: {DocumentSearchTool is not None}")
                    
            except Exception as e:
                logger.error(f"❌ 文档搜索工具实例 {i+1} 初始化失败: {e}")
                import traceback
                logger.error(f"   完整错误: {traceback.format_exc()}")
                continue
        
        logger.info(f"🎉 工具池初始化完成: 模板工具={'1个' if self.template_tool else '0个'}, 文档工具={len(self.document_tools)}个")
        
        # 检查是否有可用的工具实例
        if not self.template_tool and len(self.document_tools) == 0:
            logger.warning("⚠️ 警告: 没有可用的工具实例，服务功能将受限")
        else:
            logger.info("✅ 至少有一种工具可用，服务可以正常启动")
    
    def get_template_tool(self):
        """获取模版搜索工具 - 直接返回单实例"""
        if not self.template_tool:
            raise RuntimeError("没有可用的模版搜索工具实例")
        return self.template_tool
    
    def return_template_tool(self, tool):
        """归还模版搜索工具 - 模板搜索无需归还（单实例+连接池）"""
        pass  # 无需操作，因为使用的是单实例+MySQL连接池
    
    def get_document_tool(self, timeout: float = 10.0):
        """获取文档搜索工具，支持等待机制"""
        import time
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self.tool_lock:
                if self.document_tools:
                    tool = self.document_tools.pop(0)
                    logger.debug(f"🔧 获取文档工具成功，剩余{len(self.document_tools)}个")
                    return tool
            
            # 短暂等待后重试
            logger.debug("⏳ 等待文档工具实例可用...")
            time.sleep(0.1)
        
        # 超时后抛出异常
        raise RuntimeError(f"等待{timeout}秒后仍无可用的文档搜索工具实例，当前活跃请求: {self.active_requests}")
    
    def return_document_tool(self, tool):
        """归还文档搜索工具"""
        with self.tool_lock:
            if tool:  # 确保工具不为None再归还
                self.document_tools.append(tool)
                logger.debug(f"🔄 归还文档工具成功，当前可用{len(self.document_tools)}个")
            else:
                logger.warning("⚠️ 尝试归还None工具实例")
    
    def update_stats(self, increment: bool = True):
        """更新统计信息"""
        with self.request_lock:
            if increment:
                self.active_requests += 1
                self.total_requests += 1
            else:
                self.active_requests -= 1
    
    async def process_template_search_async(self, query: str) -> str:
        """异步处理模版搜索 - 直接使用MySQL连接池，无需线程池"""
        self.update_stats(True)
        
        try:
            # 直接调用同步方法，MySQL连接池会处理并发
            result = self._process_template_search_sync(query)
            return result
        finally:
            self.update_stats(False)
    
    def _process_template_search_sync(self, query: str) -> str:
        """同步处理模版搜索"""
        tool = None
        try:
            tool = self.get_template_tool()
            result = tool.search_templates(query)
            return result
        except Exception as e:
            logger.error(f"❌ 模版搜索异常: {e}")
            raise
        finally:
            if tool:
                self.return_template_tool(tool)
    
    async def process_document_search_async(self, query_text: str, project_name: str, 
                                          top_k: int, content_type: str) -> str:
        """异步处理文档搜索 - 使用工具池和线程池"""
        async with self.document_semaphore:
            self.update_stats(True)
            
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.thread_pool, 
                    self._process_document_search_sync, 
                    query_text, project_name, top_k, content_type
                )
                return result
            finally:
                self.update_stats(False)
    
    def _process_document_search_sync(self, query_text: str, project_name: str, 
                                    top_k: int, content_type: str) -> str:
        """同步处理文档搜索"""
        tool = None
        try:
            tool = self.get_document_tool()
            result = tool.search_documents(query_text, project_name, top_k, content_type)
            return result
        except Exception as e:
            logger.error(f"❌ 文档搜索异常: {e}")
            raise
        finally:
            if tool:
                self.return_document_tool(tool)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.request_lock:
            with self.tool_lock:
                return {
                    "active_requests": self.active_requests,
                    "total_requests": self.total_requests,
                    "available_template_tools": 1 if self.template_tool else 0,
                    "available_document_tools": len(self.document_tools),
                    "max_concurrent": self.max_concurrent,
                    "max_workers": self.max_workers,
                    "template_search_mode": "单实例+MySQL连接池",
                    "document_search_mode": f"工具池({len(self.document_tools)}个可用)+线程池",
                    "pool_utilization": f"{((12 - len(self.document_tools)) / 12 * 100):.1f}%"  # 总池大小为12
                }

# 全局并发管理器
concurrency_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时的初始化
    global concurrency_manager
    try:
        logger.info("🚀 独立工具API服务启动中...")
        
        # 获取并发配置
        max_concurrent = int(os.getenv("MAX_CONCURRENT_REQUESTS", "15"))
        max_workers = int(os.getenv("MAX_WORKER_THREADS", "10"))
        tool_pool_size = int(os.getenv("TOOL_POOL_SIZE", "12"))
        
        # 检查工具可用性
        logger.info(f"🔍 检查工具可用性:")
        logger.info(f"   📝 模板搜索工具: {'可用' if template_tool_available else '不可用'}")
        logger.info(f"   📄 文档搜索工具: {'可用' if document_tool_available else '不可用'}")
        
        if not template_tool_available and not document_tool_available:
            logger.error("❌ 所有工具都不可用，服务无法正常启动")
            raise RuntimeError("没有可用的工具，服务无法启动")
        
        # 初始化并发管理器
        logger.info("🔧 初始化并发管理器...")
        concurrency_manager = ConcurrencyManager(max_concurrent, max_workers)
        
        logger.info(f"🛠️ 初始化工具池 (大小: {tool_pool_size})...")
        concurrency_manager.initialize_tool_pools(tool_pool_size)
        
        # 检查初始化结果
        stats = concurrency_manager.get_stats()
        logger.info("✅ 独立工具API服务启动完成！")
        logger.info("🎯 API文档地址: http://localhost:8001/docs")
        logger.info(f"⚡ 并发配置: 最大并发={max_concurrent}, 线程池={max_workers}, 工具池={tool_pool_size}")
        logger.info(f"📊 工具池状态: 模板工具={stats['available_template_tools']}个, 文档工具={stats['available_document_tools']}个")
        
        yield  # 应用运行期间
        
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        raise
    finally:
        # 关闭时的清理
        logger.info("👋 独立工具API服务正在关闭...")
        
        if concurrency_manager:
            concurrency_manager.thread_pool.shutdown(wait=True)
            logger.info("✅ 线程池已关闭")

# 创建FastAPI应用
app = FastAPI(
    title="独立工具API - 无React Agent版本",
    description="直接提供模版搜索和文档搜索工具的API接口",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """根路径 - 服务状态检查"""
    global concurrency_manager
    
    stats = concurrency_manager.get_stats() if concurrency_manager else {}
    
    # 检查工具可用性 - 只有在需要时才导入
    template_available = template_tool_available
    document_available = document_tool_available
    
    return {
        "service": "独立工具API - 无React Agent版本",
        "status": "running",
        "version": "3.0.0",
        "tools": {
            "template_search": {
                "available": template_available,
                "instances": 1 if concurrency_manager and concurrency_manager.template_tool else 0
            },
            "document_search": {
                "available": document_available, 
                "instances": len(concurrency_manager.document_tools) if concurrency_manager else 0
            }
        },
        "concurrent_stats": stats,
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    """健康检查接口"""
    global concurrency_manager
    
    # 检查工具可用性 - 只有在需要时才导入
    template_available = template_tool_available
    document_available = document_tool_available
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "concurrency_manager": concurrency_manager is not None,
            "storage_directory": os.path.exists(os.getenv("RAG_STORAGE_DIR", "final_chromadb")),
            "template_search_tool": template_available,
            "document_search_tool": document_available,
            "environment": True  # 独立工具模式，无特殊环境要求
        },
        "tools_status": {
                    "template_search": {
            "imported": template_available,
            "instances": 1 if (concurrency_manager and concurrency_manager.template_tool) else 0
        },
            "document_search": {
                "imported": document_available,
                "instances": len(concurrency_manager.document_tools) if concurrency_manager else 0
            }
        }
    }
    
    if concurrency_manager:
        stats = concurrency_manager.get_stats()
        health_status["concurrent_stats"] = stats
        
        # 检查是否有可用的工具
        if stats["available_template_tools"] == 0 and stats["available_document_tools"] == 0 and stats["active_requests"] == 0:
            health_status["status"] = "degraded"
            health_status["warning"] = "No available tools"
    
    # 如果没有任何工具可用，标记为降级状态
    if not template_available and not document_available:
        health_status["status"] = "degraded"
        health_status["warning"] = "All tools unavailable due to import failures"
    
    # 检查所有组件是否正常
    critical_components = ["concurrency_manager", "storage_directory", "environment"]
    critical_healthy = all(health_status["components"][comp] for comp in critical_components)
    
    if not critical_healthy:
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

@app.post("/template_search", response_model=TemplateSearchResponse)
async def template_search(request: TemplateSearchRequest):
    """
    模版搜索接口 - ElasticSearch搜索
    
    输入自然语言query，输出模版内容
    """
    global concurrency_manager
    
    try:
        logger.info(f"📝 收到模版搜索请求: {request.query}")
        
        # 检查模板搜索工具是否可用
        if not template_tool_available:
            logger.error("❌ 模板搜索工具不可用")
            raise HTTPException(
                status_code=503, 
                detail="模板搜索服务不可用，工具导入失败"
            )
        
        # 检查并发管理器
        if concurrency_manager is None:
            logger.error("❌ 并发管理器未初始化")
            raise HTTPException(
                status_code=503, 
                detail="并发管理器未可用，请稍后重试"
            )
        
        # 检查是否有可用的模板工具实例
        if not concurrency_manager.template_tool:
            logger.error("❌ 没有可用的模板搜索工具实例")
            raise HTTPException(
                status_code=503, 
                detail="模板搜索服务暂时不可用，没有可用的工具实例"
            )
        
        # 使用并发管理器处理搜索
        start_time = datetime.now()
        logger.info(f"🚀 开始处理模版搜索: {request.query}")
        
        # 异步调用模版搜索工具
        template_content = await concurrency_manager.process_template_search_async(request.query)
        
        # 记录处理时间
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"📊 模版搜索完成 - 耗时: {processing_time:.2f}秒")
        logger.info(f"📄 返回模版内容长度: {len(template_content)}字符")
        
        return TemplateSearchResponse(
            template_content=template_content
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 模版搜索接口异常: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"模版搜索失败: {str(e)}"
        )

@app.post("/document_search", response_model=DocumentSearchResponse)
async def document_search(request: DocumentSearchRequest):
    """
    文档搜索接口 - 统一内容搜索
    
    输入query_text等参数，输出JSON格式的retrieved text/image/table
    """
    global concurrency_manager
    
    try:
        logger.info(f"📝 收到文档搜索请求: {request.query_text}")
        
        # 检查文档搜索工具是否可用
        if not document_tool_available:
            logger.error("❌ 文档搜索工具不可用")
            raise HTTPException(
                status_code=503, 
                detail="文档搜索服务不可用，工具导入失败"
            )
        
        # 检查并发管理器
        if concurrency_manager is None:
            logger.error("❌ 并发管理器未初始化")
            raise HTTPException(
                status_code=503, 
                detail="并发管理器未可用，请稍后重试"
            )
        
        # 检查是否有可用的文档工具实例
        if len(concurrency_manager.document_tools) == 0:
            logger.error("❌ 没有可用的文档搜索工具实例")
            raise HTTPException(
                status_code=503, 
                detail="文档搜索服务暂时不可用，没有可用的工具实例"
            )
        
        # 使用并发管理器处理搜索
        start_time = datetime.now()
        logger.info(f"🚀 开始处理文档搜索: {request.query_text}")
        
        # 异步调用文档搜索工具
        search_result_json = await concurrency_manager.process_document_search_async(
            request.query_text, request.project_name, request.top_k, request.content_type
        )
        
        # 解析JSON结果
        search_result = json.loads(search_result_json)
        
        # 检查搜索结果
        if search_result.get("status") != "success":
            error_msg = search_result.get("message", "搜索失败")
            logger.error(f"❌ 文档搜索失败: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"文档搜索失败: {error_msg}"
            )
        
        # 记录处理时间
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"📊 文档搜索完成 - 耗时: {processing_time:.2f}秒")
        
        retrieved_text = search_result.get("retrieved_text", [])
        retrieved_image = search_result.get("retrieved_image", [])
        retrieved_table = search_result.get("retrieved_table", [])
        
        logger.info(f"📄 返回结果: 文本{len(retrieved_text)}个, 图片{len(retrieved_image)}个, 表格{len(retrieved_table)}个")
        
        return DocumentSearchResponse(
            retrieved_text=retrieved_text,
            retrieved_image=retrieved_image,
            retrieved_table=retrieved_table
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 文档搜索接口异常: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"文档搜索失败: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    
    # 从环境变量获取配置
    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", "8001"))  # 使用不同端口避免冲突
    
    logger.info(f"🌐 启动独立工具API服务: http://{host}:{port}")
    logger.info(f"📚 API文档: http://{host}:{port}/docs")
    
    uvicorn.run(
        "app_independent_tools:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
        workers=1
    ) 