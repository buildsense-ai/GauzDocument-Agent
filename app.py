#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 服务 - RAG检索工具系统
React Agent API 服务，提供自然语言查询接口
"""

import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# FastAPI 相关导入
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 加载环境变量
load_dotenv()

# 确保日志目录存在
os.makedirs('logs', exist_ok=True)

# 配置日志
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/fastapi_service.log'),
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
    required_env_vars = ["QWEN_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var) and not os.getenv("DASHSCOPE_API_KEY")]
    
    if missing_vars:
        logger.error(f"缺少必要的环境变量: {missing_vars}")
        raise RuntimeError(f"缺少必要的环境变量: {missing_vars}，请设置 QWEN_API_KEY 或 DASHSCOPE_API_KEY")
    
    logger.info("环境设置完成")

# 导入React Agent
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

# 创建FastAPI应用
app = FastAPI(
    title="ReAct Agent 文档查询API",
    description="基于ReAct Agent的智能文档检索系统，支持自然语言查询",
    version="1.0.0",
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

# 全局变量：React Agent实例
react_agent = None

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    global react_agent
    try:
        logger.info("🚀 FastAPI服务启动中...")
        
        # 设置环境
        setup_environment()
        
        # 初始化React Agent
        logger.info("🤖 初始化React Agent...")
        storage_dir = os.getenv("RAG_STORAGE_DIR", "pdf_embedding_storage")
        react_agent = SimplifiedReactAgent(storage_dir=storage_dir)
        
        logger.info("✅ FastAPI服务启动完成！")
        logger.info("🎯 API文档地址: http://localhost:8000/docs")
        
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    logger.info("👋 FastAPI服务正在关闭...")

@app.get("/")
async def root():
    """根路径 - 服务状态检查"""
    return {
        "service": "ReAct Agent 文档查询API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    """健康检查接口"""
    global react_agent
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "react_agent": react_agent is not None,
            "environment": os.getenv("DEEPSEEK_API_KEY") is not None
        }
    }
    
    # 检查所有组件是否正常
    all_healthy = all(health_status["components"].values())
    if not all_healthy:
        health_status["status"] = "unhealthy"
        return JSONResponse(
            status_code=503,
            content=health_status
        )
    
    return health_status

@app.post("/react_agent", response_model=QueryResponse)
async def react_agent_query(request: QueryRequest):
    """
    ReAct Agent 文档查询接口
    
    接收自然语言查询，使用ReAct Agent进行智能检索，返回结构化结果
    """
    global react_agent
    
    try:
        logger.info(f"📝 收到查询请求: {request.query}")
        
        # 检查React Agent是否已初始化
        if react_agent is None:
            logger.error("❌ React Agent未初始化")
            raise HTTPException(
                status_code=503, 
                detail="React Agent服务未可用，请稍后重试"
            )
        
        # 使用React Agent处理查询
        start_time = datetime.now()
        logger.info(f"🚀 开始处理查询: {request.query}")
        
        # 调用React Agent
        result_json = react_agent.process_query(request.query)
        
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

def extract_retrieved_text(final_answer: str) -> str:
    """
    从final_answer中提取retrieved_text内容
    
    Args:
        final_answer: React Agent返回的最终答案
        
    Returns:
        处理后的检索文本内容
    """
    try:
        # 尝试解析为JSON
        if final_answer.strip().startswith('{'):
            try:
                answer_data = json.loads(final_answer)
                
                # 提取所有检索到的内容
                retrieved_parts = []
                
                # 处理文本内容
                text_results = answer_data.get("retrieved_text", [])
                if text_results:
                    for i, text_item in enumerate(text_results, 1):
                        content = text_item.get("content", "")
                        chapter_title = text_item.get("chapter_title", "")
                        
                        if content:
                            if chapter_title:
                                retrieved_parts.append(f"【{chapter_title}】\n{content}")
                            else:
                                retrieved_parts.append(content)
                
                # 处理图片内容
                image_results = answer_data.get("retrieved_image", [])
                if image_results:
                    retrieved_parts.append("\n--- 相关图片信息 ---")
                    for i, img_item in enumerate(image_results, 1):
                        caption = img_item.get("caption", "")
                        description = img_item.get("ai_description", "")
                        chapter_title = img_item.get("chapter_title", "")
                        
                        img_info = f"图片{i}："
                        if chapter_title:
                            img_info += f"【{chapter_title}】"
                        if caption:
                            img_info += f"图片说明：{caption} "
                        if description:
                            img_info += f"AI描述：{description}"
                        
                        if img_info.strip() != f"图片{i}：":
                            retrieved_parts.append(img_info)
                
                # 处理表格内容
                table_results = answer_data.get("retrieved_table", [])
                if table_results:
                    retrieved_parts.append("\n--- 相关表格信息 ---")
                    for i, table_item in enumerate(table_results, 1):
                        caption = table_item.get("caption", "")
                        description = table_item.get("ai_description", "")
                        chapter_title = table_item.get("chapter_title", "")
                        
                        table_info = f"表格{i}："
                        if chapter_title:
                            table_info += f"【{chapter_title}】"
                        if caption:
                            table_info += f"表格说明：{caption} "
                        if description:
                            table_info += f"AI描述：{description}"
                        
                        if table_info.strip() != f"表格{i}：":
                            retrieved_parts.append(table_info)
                
                # 如果有内容，组合返回
                if retrieved_parts:
                    return "\n\n".join(retrieved_parts)
                
                # 如果JSON中没有找到内容，返回原始响应
                return final_answer
                
            except json.JSONDecodeError:
                # JSON解析失败，直接返回原始文本
                logger.warning("⚠️ final_answer不是有效的JSON，直接返回原始内容")
                return final_answer
        else:
            # 不是JSON格式，直接返回
            return final_answer
            
    except Exception as e:
        logger.error(f"❌ 提取retrieved_text失败: {e}")
        # 异常情况下返回原始内容
        return final_answer or "检索内容提取失败"

if __name__ == "__main__":
    import uvicorn
    
    # 从环境变量获取配置
    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", "8000"))
    
    logger.info(f"🌐 启动FastAPI服务: http://{host}:{port}")
    logger.info(f"📚 API文档: http://{host}:{port}/docs")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=True,  # 开发模式下启用热重载
        log_level="info"
    ) 