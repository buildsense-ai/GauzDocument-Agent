"""
FastAPI主服务
实现ReactAgent的Web API接口，支持项目ID锁定机制和流式思考输出
"""

import os
import urllib.parse
import asyncio
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi import UploadFile, File

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ 已加载 .env 文件")
except ImportError:
    print("⚠️ python-dotenv 未安装，将直接从系统环境变量读取")

# 导入核心组件
from deepseek_client import DeepSeekClient
from enhanced_react_agent import EnhancedReActAgent
from tools import create_core_tool_registry
from minio_client import upload_pdf_to_minio, get_minio_uploader
from thought_logger import get_thought_data, clear_thought_queue, setup_thought_logger, restore_stdout

# 🆕 导入数据库组件
from database import get_db, Project, ChatSession, ChatMessage, ProjectFile
from database.crud import (
    create_project, get_project, get_all_projects, get_project_summary, update_project_stats,
    delete_project, get_current_session, create_new_session, save_message, get_session_messages,
    get_recent_messages, save_file_record, get_project_files, update_file_minio_path, get_project_by_name,
    delete_file_record
)
from database.utils import setup_database, check_database_health
from fastapi import Depends
from sqlalchemy.orm import Session

# 🆕 导入路由模块
from routers import ai_editor, upload_with_version

# 全局会话管理
active_sessions: Dict[str, Dict[str, Any]] = {}

# 数据模型
class ChatRequest(BaseModel):
    problem: str
    files: List[Dict[str, Any]] = []
    project_context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    success: bool
    content: List[Dict[str, str]]
    thinking_process: List[Dict[str, Any]] = []
    total_iterations: int = 1
    isError: bool = False

class HealthResponse(BaseModel):
    status: str
    react_agent_ready: bool
    tools_count: int
    uptime: float

class ToolsResponse(BaseModel):
    tools: List[Dict[str, Any]]

class StreamRequest(BaseModel):
    problem: str
    files: List[Dict[str, Any]] = []
    project_context: Optional[Dict[str, Any]] = None

class StreamStartResponse(BaseModel):
    session_id: str
    stream_url: str

# 🆕 新增数据模型
class ProjectCreateRequest(BaseModel):
    name: str
    type: Optional[str] = None
    description: Optional[str] = None

class ProjectResponse(BaseModel):
    success: bool
    project: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ProjectListResponse(BaseModel):
    success: bool
    projects: List[Dict[str, Any]] = []
    total: int = 0

class ProjectSummaryResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None

class SessionMessagesResponse(BaseModel):
    success: bool
    messages: List[Dict[str, Any]] = []
    total: int = 0
    page: int = 1

# 初始化FastAPI应用
app = FastAPI(
    title="ReactAgent API Server",
    description="带项目ID锁定机制的ReAct Agent API服务",
    version="1.0.0"
)

# 🆕 增加请求体大小限制，支持大文件上传
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_size: int = 50 * 1024 * 1024):  # 50MB
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: StarletteRequest, call_next):
        # 检查Content-Length头
        content_length = request.headers.get('content-length')
        if content_length and int(content_length) > self.max_size:
            return Response(
                content=f"Request body too large. Maximum size: {self.max_size} bytes",
                status_code=413
            )
        return await call_next(request)

# 添加请求大小限制中间件
app.add_middleware(RequestSizeLimitMiddleware, max_size=50 * 1024 * 1024)  # 50MB限制

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🆕 注册路由
app.include_router(ai_editor.router)
app.include_router(upload_with_version.router)

# 全局变量
deepseek_client = None
tool_registry = None
start_time = None

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    global deepseek_client, tool_registry, start_time
    import time
    start_time = time.time()
    
    print("🚀 ReactAgent API服务启动中...")
    
    # 初始化DeepSeek客户端
    try:
        # 从环境变量获取API key
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            print("❌ 错误: DEEPSEEK_API_KEY 环境变量未设置")
            print("📝 请设置环境变量:")
            print("   方式1: export DEEPSEEK_API_KEY='your_api_key_here'")
            print("   方式2: 创建 .env 文件，内容: DEEPSEEK_API_KEY=your_api_key_here")
            raise ValueError("DeepSeek API密钥未设置")
        
        deepseek_client = DeepSeekClient(
            api_key=api_key
        )
        print("✅ DeepSeek客户端初始化成功")
        
    except Exception as e:
        print(f"❌ DeepSeek客户端初始化失败: {e}")
        deepseek_client = None
    
    # 初始化工具注册器
    try:
        tool_registry = create_core_tool_registry()
        print(f"✅ 工具注册器初始化成功，共 {len(tool_registry.tools)} 个工具")
        
    except Exception as e:
        print(f"❌ 工具注册器初始化失败: {e}")
        tool_registry = None
    
    # 🆕 初始化数据库
    try:
        print("🗄️ 初始化数据库...")
        if setup_database():
            print("✅ 数据库初始化成功")
        else:
            print("❌ 数据库初始化失败")
    except Exception as e:
        print(f"❌ 数据库初始化错误: {e}")
    
    print("🎉 ReactAgent API服务启动完成！")

@app.post("/react_solve", response_model=ChatResponse)
async def react_solve(request: Request, db: Session = Depends(get_db)):
    """处理ReactAgent请求，包含项目上下文，支持数据库存储"""
    try:
        # 🆕 第一步：提取请求头中的项目信息
        project_id = request.headers.get('x-project-id')
        project_name_encoded = request.headers.get('x-project-name')
        
        # 🆕 第二步：解码项目名称（处理中文字符）
        project_name = None
        if project_name_encoded:
            project_name = urllib.parse.unquote(project_name_encoded)
            
        print(f"🏗️ ReactAgent接收项目上下文: ID={project_id}, Name={project_name}")
        
        # 解析请求体
        body = await request.json()
        problem = body.get('problem', '')
        files = body.get('files', [])
        project_context = body.get('project_context', {})
        
        # 🆕 检查是否应该启用ThoughtLogger（只有流式请求才启用）
        enable_thought_logger = body.get('enable_streaming', False)
        print(f"🌊 ThoughtLogger启用状态: {enable_thought_logger}")
        
        if not problem:
            raise HTTPException(status_code=400, detail="问题内容不能为空")
        
        # 🆕 第三步：合并项目信息到上下文，并记录原始用户查询，供下游工具使用
        if project_id:
            project_context.update({
                'project_id': project_id,
                'project_name': project_name
            })
        # 记录原始用户查询，确保文档生成工具使用用户意图而非few-shot示例
        if problem:
            project_context['original_query'] = problem
            
        print(f"🔄 最终项目上下文: {project_context}")
        print(f"💬 用户问题: {problem}")
        if files:
            print(f"📎 包含文件: {[f.get('name', 'unknown') for f in files]}")
        
        # 检查必要组件
        if not deepseek_client:
            return ChatResponse(
                success=False,
                content=[{"text": "DeepSeek客户端未初始化，请检查API密钥配置"}],
                isError=True
            )
            
        if not tool_registry:
            return ChatResponse(
                success=False,
                content=[{"text": "工具注册器未初始化"}],
                isError=True
            )
        
        # 🆕 第四步：创建带项目上下文的Agent实例
        # 为工具注册器设置项目上下文
        tool_registry.set_project_context(project_context)
        
        # 🆕 创建agent实例
        agent = EnhancedReActAgent(
            deepseek_client=deepseek_client,
            tool_registry=tool_registry,
            max_iterations=5,  # 🔧 减少最大迭代次数，避免无限循环
            verbose=True,
            enable_memory=True
        )
        
        # 构建完整问题文本
        full_problem = problem
        if files:
            files_description = "\n".join([
                f"- {f.get('name', 'unknown')}: {f.get('path', 'unknown path')}"
                for f in files
            ])
            full_problem += f"\n\n上传的文件:\n{files_description}"
        
        try:
            # 🔧 关键修改：只在流式模式下启用ThoughtLogger
            if enable_thought_logger:
                setup_thought_logger()
                print("🌊 为流式请求启用ThoughtLogger")
            else:
                print("📞 普通API调用，不启用ThoughtLogger")
            
            result = await agent.solve_problem_async(full_problem)
            
            # 🧹 如果启用了ThoughtLogger，需要恢复
            if enable_thought_logger:
                restore_stdout()
                print("🌊 ThoughtLogger已恢复")
            
            # 🆕 保存消息到数据库 - 支持project_name
            if project_id or project_name:
                try:
                    # 获取或创建当前会话
                    if project_name:
                        print(f"💾 使用项目名称保存消息: {project_name}")
                        current_session = get_current_session(db, project_name=project_name)
                        if not current_session:
                            current_session = create_new_session(db, project_name=project_name)
                        # 获取实际的project_id用于保存
                        actual_project = get_project_by_name(db, project_name)
                        actual_project_id = actual_project.id if actual_project else project_id
                    else:
                        current_session = get_current_session(db, project_id=project_id)
                        if not current_session:
                            current_session = create_new_session(db, project_id=project_id)
                        actual_project_id = project_id
                    
                    # 保存用户消息
                    save_message(
                        db=db,
                        project_id=actual_project_id,
                        session_id=current_session.id,
                        role="user",
                        content=problem,
                        extra_data={"files": files, "project_context": project_context, "project_name": project_name}
                    )
                    
                    # 保存AI回复
                    save_message(
                        db=db,
                        project_id=actual_project_id,
                        session_id=current_session.id,
                        role="assistant",
                        content=result.response,
                        thinking_data=result.thinking_process,
                        extra_data={"total_iterations": result.total_iterations, "project_name": project_name}
                    )
                    
                    print(f"💾 消息已保存到数据库: {project_name or project_id}")
                except Exception as save_error:
                    print(f"⚠️ 保存消息到数据库失败: {save_error}")
                    # 不影响正常响应，只记录错误
            
            return ChatResponse(
                success=True,
                content=[{"text": result.response}],
                thinking_process=result.thinking_process,
                total_iterations=result.total_iterations,
                isError=False
            )
            
        except Exception as e:
            # 🧹 确保在异常情况下也恢复stdout
            if enable_thought_logger:
                restore_stdout()
            print(f"❌ Agent执行失败: {e}")
            return ChatResponse(
                success=False,
                content=[{"text": f"处理请求时发生错误: {str(e)}"}],
                isError=True
            )
        
    except Exception as e:
        print(f"❌ react_solve接口异常: {e}")
        raise HTTPException(status_code=500, detail=f"处理请求失败: {str(e)}")

@app.post("/api/upload")
async def upload_file(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    文件上传API - 自动上传PDF到MinIO，支持数据库记录
    """
    try:
        # 🔍 提取项目信息
        project_id = request.headers.get('x-project-id')
        project_name_encoded = request.headers.get('x-project-name')
        project_name = None
        if project_name_encoded:
            project_name = urllib.parse.unquote(project_name_encoded)
        
        # 🆕 如果有项目名称但没有ID，从数据库获取ID
        if project_name and not project_id:
            try:
                project = get_project_by_name(db, project_name)
                if project:
                    project_id = project.id
                    print(f"🔍 从数据库获取项目ID: {project_name} -> {project_id}")
                else:
                    print(f"⚠️ 数据库中未找到项目: {project_name}")
            except Exception as e:
                print(f"❌ 获取项目ID失败: {e}")
        
        # 🔧 确保项目ID有值，否则使用项目名称作为标识
        effective_project_id = project_id or project_name or 'default'
        
        print(f"📤 接收文件上传: {file.filename}")
        print(f"🏗️ 项目信息: ID={project_id}, Name={project_name}, Effective={effective_project_id}")
        
        # 验证文件类型
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="只支持PDF文件上传")
        
        # 创建临时本地文件
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            # 读取并保存文件内容
            file_content = await file.read()
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        print(f"📁 临时文件保存到: {temp_file_path}")
        
        # 🚀 上传到MinIO (增强版验证)
        minio_path, upload_error = upload_pdf_to_minio(
            file_path=temp_file_path,
            original_filename=file.filename,
            project_id=effective_project_id,
            verify_checksum=True  # 启用校验和验证以确保完整性
        )
        
        if not minio_path:
            # 清理临时文件
            import os
            os.unlink(temp_file_path)
            error_detail = f"MinIO上传失败: {upload_error}" if upload_error else "MinIO上传失败"
            print(f"❌ {error_detail}")
            raise HTTPException(status_code=500, detail=error_detail)
        
        print(f"✅ MinIO上传并验证成功: {minio_path}")
        
        # 🆕 保存文件记录到数据库 - 支持project_name
        file_record = None
        if effective_project_id and effective_project_id != 'default':
            try:
                print(f"💾 开始保存文件记录到数据库...")
                print(f"💾 项目信息: ID={project_id}, Name={project_name}, Effective={effective_project_id}")
                
                # 获取或创建当前会话
                if project_name:
                    print(f"💾 使用项目名称保存文件记录: {project_name}")
                    # 先验证项目是否存在
                    actual_project = get_project_by_name(db, project_name)
                    if not actual_project:
                        raise Exception(f"项目不存在: {project_name}")
                    actual_project_id = actual_project.id
                    print(f"💾 找到项目: {actual_project_id}")
                    
                    current_session = get_current_session(db, project_name=project_name)
                    if not current_session:
                        print(f"💾 创建新会话...")
                        current_session = create_new_session(db, project_name=project_name)
                    print(f"💾 使用会话: {current_session.id}")
                else:
                    print(f"💾 使用项目ID保存文件记录: {effective_project_id}")
                    actual_project_id = effective_project_id
                    current_session = get_current_session(db, project_id=effective_project_id)
                    if not current_session:
                        print(f"💾 创建新会话...")
                        current_session = create_new_session(db, project_id=effective_project_id)
                    print(f"💾 使用会话: {current_session.id}")
                
                # 准备文件记录数据
                file_data = {
                    "project_id": actual_project_id,
                    "session_id": current_session.id,
                    "original_name": file.filename,
                    "local_path": None,  # 不保存临时路径，因为会被删除
                    "minio_path": minio_path,
                    "file_size": len(file_content),
                    "mime_type": file.content_type,
                    "extra_data": {
                        "upload_source": "api",
                        "project_name": project_name,
                        "project_id": actual_project_id,
                        "frontend_source": "web",
                        "upload_timestamp": datetime.now().isoformat()
                    }
                }
                
                print(f"💾 准备保存文件记录: {file_data}")
                
                # 保存文件记录
                file_record = save_file_record(db=db, **file_data)
                
                print(f"💾 文件记录已保存到数据库: {file.filename} -> {project_name or actual_project_id}")
                print(f"💾 文件记录ID: {file_record.id}")
                
            except Exception as save_error:
                print(f"⚠️ 保存文件记录到数据库失败: {save_error}")
                print(f"⚠️ 错误详情: {type(save_error).__name__}: {str(save_error)}")
                import traceback
                print(f"⚠️ 完整错误堆栈:")
                traceback.print_exc()
                
                # 尝试回滚数据库事务
                try:
                    db.rollback()
                    print(f"💾 数据库事务已回滚")
                except Exception as rollback_error:
                    print(f"⚠️ 回滚失败: {rollback_error}")
                    
                # 虽然数据库保存失败，但MinIO上传成功，文件仍然可用
                # 不影响正常响应，只记录错误
        else:
            print(f"⚠️ 跳过数据库保存: effective_project_id={effective_project_id}")
        
        # 🧹 清理临时文件
        import os
        try:
            os.unlink(temp_file_path)
            print(f"🧹 已清理临时文件: {temp_file_path}")
        except Exception as cleanup_error:
            print(f"⚠️ 清理临时文件失败: {cleanup_error}")
        
        # 返回文件信息
        response_data = {
            "success": True,
            "message": "文件上传并验证成功",
            "originalName": file.filename,
            "minio_path": minio_path,  # 这是AI agent将使用的路径
            "project_id": effective_project_id,
            "project_name": project_name,
            "size": len(file_content),
            "mimetype": file.content_type,
            "verified": True,  # 标记为已验证
            "verification_details": {
                "size_verified": True,
                "existence_verified": True,
                "checksum_verified": True,
                "verification_timestamp": datetime.now().isoformat()
            }
        }
        
        # 如果有数据库记录，添加记录ID
        if file_record:
            response_data["file_id"] = file_record.id
            response_data["database_saved"] = True
        else:
            response_data["database_saved"] = False
            response_data["database_error"] = "文件记录未保存到数据库，但MinIO上传成功"
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    import time
    uptime = time.time() - start_time if start_time else 0
    
    return HealthResponse(
        status="healthy",
        react_agent_ready=bool(deepseek_client and tool_registry),
        tools_count=len(tool_registry.tools) if tool_registry else 0,
        uptime=uptime
    )

@app.get("/tools", response_model=ToolsResponse)
async def list_tools():
    """获取可用工具列表"""
    if not tool_registry:
        raise HTTPException(status_code=503, detail="工具注册器未初始化")
    
    return ToolsResponse(
        tools=tool_registry.list_tools()
    )

@app.post("/start_stream", response_model=StreamStartResponse)
async def start_stream(request: Request, db: Session = Depends(get_db)):
    """启动流式思考会话"""
    try:
        # 🆕 第一步：提取请求头中的项目信息（与react_solve相同逻辑）
        project_id = request.headers.get('x-project-id')
        project_name_encoded = request.headers.get('x-project-name')
        
        # 🆕 第二步：解码项目名称
        project_name = None
        if project_name_encoded:
            project_name = urllib.parse.unquote(project_name_encoded)
            
        print(f"🌊 启动流式会话: ID={project_id}, Name={project_name}")
        
        # 解析请求体
        body = await request.json()
        problem = body.get('problem', '')
        files = body.get('files', [])
        project_context = body.get('project_context', {})
        
        if not problem:
            raise HTTPException(status_code=400, detail="问题内容不能为空")
        
        # 🆕 第三步：合并项目信息到上下文，并记录原始用户查询，供下游工具使用
        if project_id:
            project_context.update({
                'project_id': project_id,
                'project_name': project_name
            })
        if problem:
            project_context['original_query'] = problem
        
        # 生成唯一会话ID
        session_id = str(uuid.uuid4())
        
        # 存储会话信息
        session_data = {
            'problem': problem,
            'files': files,
            'project_context': project_context,
            'created_at': asyncio.get_event_loop().time()
        }
        
        # 🆕 保存用户消息到数据库（与react_solve相同逻辑）
        db_session_id = None
        actual_project_id = None
        project_name_for_save = None
        
        if project_id or project_name:
            try:
                # 获取或创建当前会话
                if project_name:
                    print(f"💾 使用项目名称保存消息: {project_name}")
                    current_session = get_current_session(db, project_name=project_name)
                    if not current_session:
                        current_session = create_new_session(db, project_name=project_name)
                    # 获取实际的project_id用于保存
                    actual_project = get_project_by_name(db, project_name)
                    actual_project_id = actual_project.id if actual_project else project_id
                    project_name_for_save = project_name
                else:
                    current_session = get_current_session(db, project_id=project_id)
                    if not current_session:
                        current_session = create_new_session(db, project_id=project_id)
                    actual_project_id = project_id
                    # 获取项目名称
                    actual_project = get_project(db, project_id=project_id)
                    project_name_for_save = actual_project.name if actual_project else None
                
                # 保存用户消息
                save_message(
                    db=db,
                    project_id=actual_project_id,
                    session_id=current_session.id,
                    role="user",
                    content=problem,
                    extra_data={"files": files, "project_context": project_context, "project_name": project_name_for_save, "stream_session_id": session_id}
                )
                
                # 将数据库会话信息添加到流式会话数据中，用于后续保存AI回复
                db_session_id = current_session.id
                
                print(f"💾 用户消息已保存到数据库: {project_name_for_save or actual_project_id}")
            except Exception as save_error:
                print(f"⚠️ 保存用户消息到数据库失败: {save_error}")
                # 不影响正常响应，只记录错误
        
        # 🔧 确保总是设置数据库字段到session_data中
        session_data['db_session_id'] = db_session_id
        session_data['actual_project_id'] = actual_project_id
        session_data['project_name'] = project_name_for_save
        
        print(f"🔍 Session_data设置完成: db_session_id={db_session_id}, actual_project_id={actual_project_id}, project_name={project_name_for_save}")
        
        active_sessions[session_id] = session_data
        print(f"🆔 创建流式会话: {session_id}")
        
        return StreamStartResponse(
            session_id=session_id,
            stream_url=f"/stream/thoughts/{session_id}"
        )
        
    except Exception as e:
        print(f"❌ 启动流式会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动流式会话失败: {str(e)}")

@app.get("/stream/live_thoughts")
async def stream_live_thoughts():
    """实时监听ThoughtLogger的输出 - 用于/react_solve端点的配套功能"""
    async def thought_stream():
        try:
            print("🌊 开始实时监听thought数据...")
            
            # 发送开始信号
            start_data = {
                "type": "start",
                "message": "开始监听实时思考..."
            }
            yield f"data: {json.dumps(start_data, ensure_ascii=False)}\n\n"
            
            # 持续监听thought数据
            data_count = 0
            timeout_count = 0
            max_timeout = 300  # 最多等待5分钟
            
            while timeout_count < max_timeout:
                # 实时获取思考数据
                thought_data = await get_thought_data()
                if thought_data:
                    data_count += 1
                    timeout_count = 0  # 重置超时计数
                    print(f"📤 实时发送thought数据 {data_count}: {thought_data['type']}")
                    yield f"data: {json.dumps(thought_data, ensure_ascii=False)}\n\n"
                else:
                    timeout_count += 1
                    # 发送心跳信号
                    if timeout_count % 50 == 0:  # 每1秒发送一次心跳
                        heartbeat = {
                            "type": "heartbeat",
                            "message": f"等待数据中... ({timeout_count}s)"
                        }
                        yield f"data: {json.dumps(heartbeat, ensure_ascii=False)}\n\n"
                
                await asyncio.sleep(0.02)  # 20ms检查间隔
            
            # 发送结束信号
            end_data = {
                "type": "end",
                "message": f"监听结束，共发送 {data_count} 条数据"
            }
            yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            print(f"❌ 实时thought监听异常: {e}")
            error_data = {
                "type": "error",
                "message": f"监听过程发生错误: {str(e)}"
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        thought_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.get("/stream/thoughts/{session_id}")
async def stream_thoughts(session_id: str):
    """流式输出AI思考过程 - SSE端点"""
    try:
        # 检查会话是否存在
        if session_id not in active_sessions:
            # 返回会话已结束的信号，而不是404错误
            import time
            async def session_ended_stream():
                end_data = {
                    "type": "session_ended",
                    "message": "会话已结束或已过期",
                    "timestamp": time.time()
                }
                yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"
            
            return StreamingResponse(
                session_ended_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        session_data = active_sessions[session_id]
        print(f"🌊 开始流式思考: {session_id}")
        
        # 🆕 清理旧的思考队列数据，避免发送上一个会话的残留数据
        print("🧹 清理队列中的旧数据...")
        clear_thought_queue()
        
        # 检查必要组件
        if not deepseek_client or not tool_registry:
            async def error_stream():
                yield f"data: {{\"type\": \"error\", \"message\": \"服务未就绪\"}}\n\n"
            
            return StreamingResponse(
                error_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # 🆕 创建带项目上下文的Agent实例
        tool_registry.set_project_context(session_data['project_context'])
        
        agent = EnhancedReActAgent(
            deepseek_client=deepseek_client,
            tool_registry=tool_registry,
            max_iterations=5,  # 🔧 减少最大迭代次数，避免无限循环
            verbose=True  # 保持terminal输出
        )
        
        # 构建完整的问题描述
        full_problem = session_data['problem']
        if session_data['files']:
            file_info = "上传的文件:\n" + "\n".join([f"- {f.get('name', 'unknown')}: {f.get('path', 'unknown path')}" for f in session_data['files']])
            full_problem += f"\n\n{file_info}"
        
        async def thought_stream():
            """异步生成思考流"""
            data_sent_count = 0
            final_result = None
            
            try:
                # 设置思考记录器
                setup_thought_logger()
                
                # 获取会话数据
                session_data = active_sessions.get(session_id, {})
                problem = session_data.get('problem', '未知问题')
                print(f"🌊 Agent开始处理问题: {problem[:100]}...")
                
                # 使用线程池执行同步的Agent方法
                import asyncio
                import concurrent.futures
                import time  # 确保time在正确位置导入
                
                # 使用线程池执行Agent，避免阻塞主事件循环
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(agent._react_loop, full_problem)
                    
                    # 在Agent运行期间实时获取思考数据
                    while not future.done():
                        thought_data = await get_thought_data()
                        
                        if thought_data:
                            data_sent_count += 1
                            print(f"📤 实时发送数据 {data_sent_count}: {thought_data['type']}")
                            yield f"data: {json.dumps(thought_data, ensure_ascii=False)}\n\n"
                        
                        # 短暂休眠避免CPU占用过高
                        await asyncio.sleep(0.02)  # 减少延迟，提高响应性
                
                    # 获取Agent的最终结果
                    final_result = future.result()
                    print(f"🎯 Agent完成，最终结果长度: {len(final_result) if final_result else 0}")
                
                # Agent完成后，处理队列中可能的剩余数据
                print("🔄 Agent完成，检查剩余数据...")
                remaining_count = 0
                for _ in range(10):  # 最多检查10次
                    thought_data = await get_thought_data()
                    if thought_data:
                        remaining_count += 1
                        print(f"📤 发送剩余数据 {remaining_count}: {thought_data['type']}")
                        yield f"data: {json.dumps(thought_data, ensure_ascii=False)}\n\n"
                    else:
                        break
                    await asyncio.sleep(0.02)
                
                # 发送最终完成信号
                if final_result:
                    # 🔍 验证final_result是否为有效的Final Answer
                    if final_result and len(final_result.strip()) > 0:
                        print(f"📤 准备发送Final Result给前端:")
                        print(f"   - 发送长度: {len(final_result)} 字符")
                        print(f"   - 内容预览: {final_result[:100]}...")
                        
                        final_data = {
                            "type": "final_answer",
                            "content": final_result,
                            "timestamp": time.time()
                        }
                        yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                        
                        # 🆕 保存AI回复到数据库
                        try:
                            print(f"💾 开始保存AI回复到数据库...")
                            current_session_data = active_sessions.get(session_id, {})
                            project_context = current_session_data.get('project_context', {})
                            project_id = project_context.get('project_id')
                            project_name = project_context.get('project_name')
                            
                            if project_id or project_name:
                                from database.database import SessionLocal
                                from database.crud import get_current_session, save_message, get_project_by_name
                                
                                db = SessionLocal()
                                try:
                                    # 获取当前会话
                                    if project_name:
                                        current_session = get_current_session(db, project_name=project_name)
                                        # 获取实际的project_id
                                        actual_project = get_project_by_name(db, project_name)
                                        actual_project_id = actual_project.id if actual_project else project_id
                                    else:
                                        current_session = get_current_session(db, project_id=project_id)
                                        actual_project_id = project_id
                                    
                                    if current_session:
                                        # 保存AI回复
                                        save_message(
                                            db=db,
                                            project_id=actual_project_id,
                                            session_id=current_session.id,
                                            role="assistant",
                                            content=final_result,
                                            thinking_data={"iterations": data_sent_count},  # 保存思考轮数
                                            extra_data={
                                                "stream_session_id": session_id,
                                                "project_name": project_name,
                                                "response_type": "stream_final"
                                            }
                                        )
                                        
                                        print(f"💾 AI回复已保存到数据库: {project_name or actual_project_id}")
                                    else:
                                        print(f"⚠️ 未找到当前会话，无法保存AI回复")
                                        
                                except Exception as db_save_error:
                                    print(f"⚠️ 保存AI回复到数据库失败: {db_save_error}")
                                    import traceback
                                    traceback.print_exc()
                                finally:
                                    db.close()
                            else:
                                print(f"⚠️ 没有项目信息，跳过数据库保存")
                                
                        except Exception as save_error:
                            print(f"⚠️ 保存AI回复过程出错: {save_error}")
                    else:
                        print("⚠️ Final Result为空，跳过发送")
                        empty_result_data = {
                            "type": "warning",
                            "content": "AI未能生成有效回复",
                            "timestamp": time.time()
                        }
                        yield f"data: {json.dumps(empty_result_data, ensure_ascii=False)}\n\n"
                
                # 🔚 发送流结束信号
                end_stream_data = {
                    "type": "stream_end",
                    "message": f"对话完成，共处理 {data_sent_count} 条思考数据",
                    "timestamp": time.time()
                }
                yield f"data: {json.dumps(end_stream_data, ensure_ascii=False)}\n\n"
                
                print(f"🎯 流式对话完成: {session_id}")
                print(f"   - 总数据条数: {data_sent_count}")
                print(f"   - 最终回复长度: {len(final_result) if final_result else 0}")
                
                # 延迟清理会话数据，避免前端重连时出现404错误
                async def delayed_cleanup():
                    await asyncio.sleep(30)  # 30秒后清理
                    if session_id in active_sessions:
                        del active_sessions[session_id]
                        print(f"🧹 延迟清理会话数据: {session_id}")
                
                # 启动延迟清理任务
                asyncio.create_task(delayed_cleanup())
                    
            except Exception as e:
                # 确保time模块可用
                import time
                print(f"❌ 流式思考过程异常: {e}")
                import traceback
                traceback.print_exc()
                
                error_data = {
                    "type": "error",
                    "message": f"处理过程发生错误: {str(e)}",
                    "timestamp": time.time()
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            
            finally:
                # 确保恢复原始 stdout
                restore_stdout()
                print(f"🧹 已恢复stdout: {session_id}")
        
        return StreamingResponse(
            thought_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 流式端点异常: {e}")
        raise HTTPException(status_code=500, detail=f"流式思考失败: {str(e)}")

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "ReactAgent API服务运行中",
        "version": "1.0.0",
        "endpoints": [
            "/react_solve - 主要的ReAct Agent处理接口",
            "/start_stream - 启动流式思考会话",
            "/stream/thoughts/{session_id} - SSE流式思考输出",
            "/health - 健康检查",
            "/tools - 工具列表",
            "/docs - API文档"
        ]
    }

# ======================== 🆕 项目管理API ========================

@app.post("/api/projects", response_model=ProjectResponse)
async def create_project_api(request: ProjectCreateRequest, db: Session = Depends(get_db)):
    """创建新项目"""
    try:
        project = create_project(
            db=db,
            name=request.name,
            project_type=request.type,
            description=request.description
        )
        return ProjectResponse(success=True, project=project.to_dict())
    except Exception as e:
        print(f"❌ 创建项目失败: {e}")
        return ProjectResponse(success=False, error=str(e))

@app.get("/api/projects", response_model=ProjectListResponse)
async def get_projects_api(status: Optional[str] = None, db: Session = Depends(get_db)):
    """获取项目列表"""
    try:
        projects = get_all_projects(db, status=status)
        return ProjectListResponse(
            success=True,
            projects=[p.to_dict() for p in projects],
            total=len(projects)
        )
    except Exception as e:
        print(f"❌ 获取项目列表失败: {e}")
        return ProjectListResponse(success=False, projects=[], total=0)

@app.get("/api/projects/{project_identifier}/summary", response_model=ProjectSummaryResponse)
async def get_project_summary_api(project_identifier: str, by_name: bool = False, db: Session = Depends(get_db)):
    """获取项目概要信息 - 用于快速加载，支持按ID或名称查询"""
    try:
        if by_name:
            summary = get_project_summary(db, project_name=project_identifier)
        else:
            summary = get_project_summary(db, project_id=project_identifier)
        
        if not summary:
            raise HTTPException(status_code=404, detail="项目不存在")
        return ProjectSummaryResponse(success=True, data=summary)
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 获取项目概要失败: {e}")
        return ProjectSummaryResponse(success=False, data=None)

@app.get("/api/projects/{project_identifier}/files")
async def get_project_files_api(
    project_identifier: str, 
    by_name: bool = False, 
    db: Session = Depends(get_db)
):
    """获取项目的所有文件列表 - 支持按ID或名称查询"""
    try:
        # 🆕 支持按项目名称或ID查询
        if by_name:
            files = get_project_files(db, project_name=project_identifier)
        else:
            files = get_project_files(db, project_id=project_identifier)
        
        return {
            "success": True,
            "files": [f.to_dict() for f in files],
            "total": len(files)
        }
    except Exception as e:
        print(f"❌ 获取项目文件列表失败: {e}")
        return {
            "success": False,
            "files": [],
            "total": 0,
            "error": str(e)
        }


@app.get("/api/projects/{project_identifier}/current-session", response_model=SessionMessagesResponse)
async def get_current_session_api(project_identifier: str, by_name: bool = False, limit: int = 20, db: Session = Depends(get_db)):
    """获取项目当前会话的最近消息 - 支持按ID或名称查询"""
    try:
        # 🆕 支持按项目名称或ID查询
        if by_name:
            current_session = get_current_session(db, project_name=project_identifier)
            if not current_session:
                current_session = create_new_session(db, project_name=project_identifier)
            files = get_project_files(db, project_name=project_identifier, session_id=current_session.id)
        else:
            current_session = get_current_session(db, project_id=project_identifier)
            if not current_session:
                current_session = create_new_session(db, project_id=project_identifier)
            files = get_project_files(db, project_id=project_identifier, session_id=current_session.id)
        
        messages, total = get_session_messages(db, current_session.id, limit=limit)
        
        return SessionMessagesResponse(
            success=True,
            messages=[{
                **msg.to_dict(),
                "session_info": current_session.to_dict(),
                "files": [f.to_dict() for f in files]
            } for msg in messages],
            total=total,
            page=1
        )
    except Exception as e:
        print(f"❌ 获取当前会话失败: {e}")
        return SessionMessagesResponse(success=False, messages=[], total=0)

@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages_api(
    session_id: str, 
    page: int = 1, 
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """获取会话消息（分页）"""
    try:
        messages, total = get_session_messages(db, session_id, page, limit)
        return {
            "success": True,
            "messages": [msg.to_dict() for msg in messages],
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": (page * limit) < total
        }
    except Exception as e:
        print(f"❌ 获取会话消息失败: {e}")
        return {"success": False, "error": str(e)}

@app.delete("/api/projects/{project_identifier}")
async def delete_project_api(project_identifier: str, by_name: bool = False, db: Session = Depends(get_db)):
    """删除项目 - 支持按ID或名称删除"""
    try:
        # 🆕 支持按项目名称或ID删除
        if by_name:
            project = get_project(db, project_name=project_identifier)
        else:
            project = get_project(db, project_id=project_identifier)
        
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        project_name = project.name
        success = delete_project(db, project.id)
        
        if success:
            return {"success": True, "message": f"项目 '{project_name}' 已成功删除"}
        else:
            return {"success": False, "error": "删除项目失败"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 删除项目失败: {e}")
        return {"success": False, "error": str(e)}

@app.delete("/api/files/{file_id}")
async def delete_file_api(file_id: str, db: Session = Depends(get_db)):
    """删除单个文件：优先尝试删除MinIO对象，然后删除数据库记录"""
    try:
        # 获取文件记录（拿到 minio_path）
        file_record = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
        if not file_record:
            raise HTTPException(status_code=404, detail="文件不存在")

        # 删除 MinIO 对象（如果存在）
        if file_record.minio_path:
            uploader = get_minio_uploader()
            if uploader:
                ok, err = uploader.delete_object_by_path(file_record.minio_path)
                if not ok:
                    # 打印警告但不阻断数据库删除
                    print(f"⚠️ 删除MinIO对象失败: {err}")

        # 删除数据库记录
        if delete_file_record(db, file_id):
            return {"success": True}
        else:
            return {"success": False, "error": "删除文件记录失败"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 删除文件失败: {e}")
        return {"success": False, "error": str(e)}

# 🆕 保存消息请求模型
class SaveMessageRequest(BaseModel):
    session_id: Optional[str] = None
    role: str  # user/assistant/system
    content: str
    thinking_data: Optional[Dict] = None
    extra_data: Optional[Dict] = None

class SaveMessageResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None

@app.post("/api/projects/by-name/{project_name}/messages", response_model=SaveMessageResponse)
async def save_message_by_name_api(project_name: str, body: SaveMessageRequest, db: Session = Depends(get_db)):
    """保存消息到指定项目（按项目名称）"""
    try:
        print(f"💾 保存消息API调用: 项目={project_name}, 角色={body.role}, 内容长度={len(body.content)}")
        
        # 获取项目
        project = get_project_by_name(db, project_name)
        if not project:
            raise HTTPException(status_code=404, detail=f"项目 '{project_name}' 不存在")
        
        # 获取或创建当前会话
        current_session = get_current_session(db, project_name=project_name)
        if not current_session:
            current_session = create_new_session(db, project_name=project_name)
        
        # 如果指定了session_id，使用指定的会话
        session_id = body.session_id or current_session.id
        
        # 保存消息
        message = save_message(
            db=db,
            project_id=project.id,
            session_id=session_id,
            role=body.role,
            content=body.content,
            thinking_data=body.thinking_data,
            extra_data=body.extra_data
        )
        
        print(f"✅ 消息保存成功: ID={message.id}, 项目={project_name}")
        
        return SaveMessageResponse(
            success=True,
            message_id=message.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 保存消息失败: {e}")
        return SaveMessageResponse(
            success=False,
            error=str(e)
        )

@app.post("/api/projects/{project_id}/messages", response_model=SaveMessageResponse)
async def save_message_by_id_api(project_id: str, body: SaveMessageRequest, db: Session = Depends(get_db)):
    """保存消息到指定项目（按项目ID）"""
    try:
        print(f"💾 保存消息API调用: 项目ID={project_id}, 角色={body.role}, 内容长度={len(body.content)}")
        
        # 获取项目
        project = get_project(db, project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"项目ID '{project_id}' 不存在")
        
        # 获取或创建当前会话
        current_session = get_current_session(db, project_id=project_id)
        if not current_session:
            current_session = create_new_session(db, project_id=project_id)
        
        # 如果指定了session_id，使用指定的会话
        session_id = body.session_id or current_session.id
        
        # 保存消息
        message = save_message(
            db=db,
            project_id=project.id,
            session_id=session_id,
            role=body.role,
            content=body.content,
            thinking_data=body.thinking_data,
            extra_data=body.extra_data
        )
        
        print(f"✅ 消息保存成功: ID={message.id}, 项目={project.name}")
        
        return SaveMessageResponse(
            success=True,
            message_id=message.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 保存消息失败: {e}")
        return SaveMessageResponse(
            success=False,
            error=str(e)
        )

@app.get("/api/database/health")
async def database_health_api():
    """数据库健康检查"""
    try:
        health = check_database_health()
        return health
    except Exception as e:
        return {
            "status": "error",
            "connection": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 启动ReactAgent API服务...")
    print("📋 端点信息:")
    print("   🔧 主服务: http://localhost:8000/react_solve")
    print("   💚 健康检查: http://localhost:8000/health") 
    print("   🔧 工具列表: http://localhost:8000/tools")
    print("   📖 API文档: http://localhost:8000/docs")
    print("")
    print("⚠️ 请确保已设置环境变量 DEEPSEEK_API_KEY")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["./"],
        timeout_keep_alive=300,  # 保持连接5分钟
        timeout_graceful_shutdown=300,  # 优雅关闭超时5分钟
        limit_max_requests=None,  # 不限制最大请求数
        limit_concurrency=None   # 不限制并发数
    )