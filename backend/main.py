"""
FastAPI主服务
实现ReactAgent的Web API接口，支持项目ID锁定机制和流式思考输出
"""

import os
import urllib.parse
import asyncio
import uuid
import json
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

# 初始化FastAPI应用
app = FastAPI(
    title="ReactAgent API Server",
    description="带项目ID锁定机制的ReAct Agent API服务",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    
    print("🎉 ReactAgent API服务启动完成！")

@app.post("/react_solve", response_model=ChatResponse)
async def react_solve(request: Request):
    """处理ReactAgent请求，包含项目上下文"""
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
        
        # 🆕 第三步：合并项目信息到上下文
        if project_id:
            project_context.update({
                'project_id': project_id,
                'project_name': project_name
            })
            
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
            max_iterations=10,
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
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    文件上传API - 自动上传PDF到MinIO
    """
    try:
        # 🔍 提取项目信息
        project_id = request.headers.get('x-project-id', 'default')
        project_name_encoded = request.headers.get('x-project-name')
        project_name = None
        if project_name_encoded:
            project_name = urllib.parse.unquote(project_name_encoded)
        
        print(f"📤 接收文件上传: {file.filename}")
        print(f"🏗️ 项目信息: ID={project_id}, Name={project_name}")
        
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
        
        # 🚀 上传到MinIO
        minio_path = upload_pdf_to_minio(
            file_path=temp_file_path,
            original_filename=file.filename,
            project_id=project_id
        )
        
        if not minio_path:
            # 清理临时文件
            import os
            os.unlink(temp_file_path)
            raise HTTPException(status_code=500, detail="MinIO上传失败")
        
        print(f"✅ MinIO上传成功: {minio_path}")
        
        # 🧹 清理临时文件
        import os
        os.unlink(temp_file_path)
        
        # 返回文件信息
        return {
            "success": True,
            "message": "文件上传成功",
            "originalName": file.filename,
            "minio_path": minio_path,  # 这是AI agent将使用的路径
            "project_id": project_id,
            "project_name": project_name,
            "size": len(file_content),
            "mimetype": file.content_type
        }
        
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
async def start_stream(request: Request):
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
        
        # 🆕 第三步：合并项目信息到上下文
        if project_id:
            project_context.update({
                'project_id': project_id,
                'project_name': project_name
            })
        
        # 生成唯一会话ID
        session_id = str(uuid.uuid4())
        
        # 存储会话信息
        active_sessions[session_id] = {
            'problem': problem,
            'files': files,
            'project_context': project_context,
            'created_at': asyncio.get_event_loop().time()
        }
        
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
            raise HTTPException(status_code=404, detail="会话不存在或已过期")
        
        session_data = active_sessions[session_id]
        print(f"🌊 开始流式思考: {session_id}")
        
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
            max_iterations=10,
            verbose=True  # 保持terminal输出
        )
        
        # 构建完整的问题描述
        full_problem = session_data['problem']
        if session_data['files']:
            file_info = "上传的文件:\n" + "\n".join([f"- {f.get('name', 'unknown')}: {f.get('path', 'unknown path')}" for f in session_data['files']])
            full_problem = f"{full_problem}\n\n{file_info}"
        
        # 🌊 使用 ThoughtLogger 的流式思考生成器
        async def thought_stream():
            try:
                # 清空旧的思考队列
                clear_thought_queue()
                
                # 启动 ThoughtLogger 拦截输出
                setup_thought_logger()
                
                # 发送开始信号
                start_data = {
                    "type": "start",
                    "message": "开始实时思考..."
                }
                yield f"data: {json.dumps(start_data, ensure_ascii=False)}\n\n"
                
                # 在线程池中运行Agent求解，避免阻塞事件循环
                import asyncio
                import concurrent.futures
                
                # 使用线程池执行Agent，避免阻塞主事件循环
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # 提交Agent任务到线程池
                    agent_future = executor.submit(agent.solve, full_problem)
                    
                    # 实时监听思考数据
                    agent_completed = False
                    final_result = None
                    data_sent_count = 0
                    
                    while not agent_completed:
                        # 检查Agent是否完成
                        if agent_future.done():
                            agent_completed = True
                            try:
                                final_result = agent_future.result()
                                print(f"🎯 Agent执行完成，结果: {final_result[:50]}...")
                                # 🔍 添加完整性验证信息
                                print(f"📊 Final Result完整信息:")
                                print(f"   - 总长度: {len(final_result)} 字符")
                                newline_char = '\n'
                                print(f"   - 行数: {len(final_result.split(newline_char))} 行")
                                print(f"   - 开头50字符: {final_result[:50]}")
                                print(f"   - 结尾50字符: {final_result[-50:]}")
                            except Exception as e:
                                final_result = None
                                error_data = {
                                    "type": "error",
                                    "message": f"Agent执行错误: {str(e)}"
                                }
                                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                        
                        # 实时获取思考数据并立即发送
                        thought_data = await get_thought_data()
                        if thought_data:
                            data_sent_count += 1
                            print(f"📤 实时发送数据 {data_sent_count}: {thought_data['type']}")
                            yield f"data: {json.dumps(thought_data, ensure_ascii=False)}\n\n"
                        
                        # 短暂休眠避免CPU占用过高
                        await asyncio.sleep(0.02)  # 减少延迟，提高响应性
                
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
                    # 🔍 验证发送前的数据完整性
                    print(f"📤 准备发送Final Result给前端:")
                    print(f"   - 发送长度: {len(final_result)} 字符")
                    newline_char = '\n'
                    print(f"   - 发送行数: {len(final_result.split(newline_char))} 行")
                    
                    final_data = {
                        "type": "complete",
                        "message": "思考完成",
                        "final_result": final_result,  # 直接使用结果，因为现在是字符串
                        "data_sent_total": data_sent_count + remaining_count
                    }
                    
                    # 🔍 验证JSON序列化后的大小
                    json_data = json.dumps(final_data, ensure_ascii=False)
                    print(f"   - JSON大小: {len(json_data)} 字符")
                    print(f"   - JSON中final_result长度: {len(final_data['final_result'])} 字符")
                    
                    yield f"data: {json_data}\n\n"
                    
                # 完成后清理会话
                if session_id in active_sessions:
                    del active_sessions[session_id]
                    print(f"🧹 清理会话: {session_id}")
                    
            except Exception as e:
                print(f"❌ 流式思考异常: {e}")
                error_data = {
                    "type": "error",
                    "message": f"思考过程发生错误: {str(e)}"
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            finally:
                # 确保恢复原始 stdout
                restore_stdout()
        
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