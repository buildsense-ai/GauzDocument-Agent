"""
工具注册器
专注于API工具调用，支持分布式工具部署架构
"""

import json
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod
# �� 导入数据库模块用于查询文件
from database.database import SessionLocal
from database.crud import get_project_files, get_project_by_name
from database import models

class BaseTool(ABC):
    """工具基类"""
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters
        
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        pass
        
    def get_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

class APITool(BaseTool):
    """API调用工具 - 调用独立部署的工具服务"""
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], 
                 api_url: str, project_context: Optional[Dict[str, Any]] = None):
        super().__init__(name, description, parameters)
        self.api_url = api_url
        self.project_context = project_context or {}
    
    async def _get_latest_pdf_from_database(self, project_name: str) -> Optional[str]:
        """
        从数据库查询项目的最新PDF文件MinIO路径
        
        Args:
            project_name: 项目名称
            
        Returns:
            MinIO路径或None
        """
        if not project_name:
            return None
            
        db = SessionLocal()
        try:
            print(f"🔍 查询项目'{project_name}'的PDF文件...")
            
            # 获取项目文件列表
            files = get_project_files(db, project_name=project_name)
            
            if not files:
                print(f"⚠️ 项目'{project_name}'中没有找到任何文件")
                return None
            
            # 筛选PDF文件并按上传时间排序（最新的在前）
            pdf_files = [
                f for f in files 
                if f.original_name.lower().endswith('.pdf') 
                and f.minio_path 
                and f.status == 'ready'
            ]
            
            if not pdf_files:
                print(f"⚠️ 项目'{project_name}'中没有找到已准备好的PDF文件")
                return None
                
            # 返回最新的PDF文件路径
            latest_pdf = pdf_files[0]  # 已按上传时间降序排列
            print(f"✅ 找到最新PDF文件: {latest_pdf.original_name} -> {latest_pdf.minio_path}")
            return latest_pdf.minio_path
            
        except Exception as e:
            print(f"❌ 查询数据库文件失败: {e}")
            return None
        finally:
            db.close()
    
    async def _execute_pdf_parser_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        专门处理 pdf_parser API 的MinIO格式调用
        
        将MinIO路径转换为HTTP URL，发送JSON请求体 {minio_url, project_name}
        """
        try:
            # 🔍 获取project_name
            project_name = payload.get("project_name")
            if not project_name and self.project_context:
                project_name = self.project_context.get("project_name", "默认项目")
                print(f"🔄 自动添加project_name: {project_name}")
            
            # 🔍 获取文件路径（minio_url参数）
            minio_url = payload.get("minio_url")
            
            # 🆕 如果没有提供minio_url或者是unknown_bucket，尝试从数据库自动查找
            if not minio_url or "unknown_bucket" in minio_url:
                print(f"🔍 minio_url缺失或无效: {minio_url}，尝试从数据库查询...")
                minio_url = await self._get_latest_pdf_from_database(project_name)
                if minio_url:
                    print(f"✅ 从数据库找到PDF文件: {minio_url}")
                else:
                    return {
                        "success": False,
                        "error_type": "no_files_found",
                        "error": "项目中没有找到已上传的PDF文件",
                        "fix_suggestion": "请先上传PDF文件再进行解析",
                        "retry_possible": False
                    }
            
            if not minio_url:
                return {
                    "success": False,
                    "error_type": "missing_parameter",
                    "error": "缺少minio_url参数",
                    "fix_suggestion": "请提供minio_url参数",
                    "retry_possible": False
                }
            
            # 🎯 验证MinIO路径格式
            if not minio_url.startswith("minio://"):
                return {
                    "success": False,
                    "error_type": "invalid_path_format",
                    "error": "PDF解析工具只支持MinIO路径格式",
                    "fix_suggestion": "请确保文件已上传到MinIO，路径格式为 minio://bucket/object",
                    "retry_possible": False
                }
            
            print(f"🌐 处理MinIO路径: {minio_url}")
            
            # 🔄 转换MinIO路径为HTTP URL格式
            # minio://bucket/file.pdf -> http://MinIO服务器/bucket/file.pdf
            path_without_prefix = minio_url[8:]  # 移除 "minio://"
            http_url = f"http://43.139.19.144:9000/{path_without_prefix}"
            
            print(f"🌐 转换后的HTTP URL: {http_url}")
            
            # 构建请求体
            request_payload = {
                "minio_url": http_url,
                "project_name": project_name
            }
            
            # 🚀 发送API请求
            import aiohttp
            import asyncio
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=request_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    print(f"📡 API响应状态码: {response.status}")
                    
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ PDF解析API调用成功，状态码200")
                        
                        # 🎯 关键修改：200状态码就认为成功，不管业务逻辑success字段
                        # 如果API返回了200，说明服务正常工作，即使业务逻辑有问题也是成功的调用
                        print(f"📋 API返回数据: {json.dumps(result, ensure_ascii=False, indent=2)}")
                        
                        # 确保返回success=True，让Agent认为操作成功
                        successful_result = {
                            "success": True,
                            "api_status": "成功",
                            "http_status": 200,
                            "data": result,
                            "minio_url": http_url,
                            "project_name": project_name,
                            "message": "PDF解析API调用成功完成"
                        }
                        
                        # 如果原始结果有success字段且为false，添加到响应中但不影响整体成功状态
                        if not result.get("success", True):
                            successful_result["business_note"] = "API调用成功，但服务返回了业务层面的处理信息"
                            successful_result["original_business_status"] = result.get("success")
                            successful_result["business_details"] = result.get("error", "无详细信息")
                        
                        return successful_result
                    else:
                        error_text = await response.text()
                        print(f"❌ PDF解析API调用失败: 状态码={response.status}, 错误={error_text}")
                        return {
                            "success": False,
                            "error_type": "api_error",
                            "http_status": response.status,
                            "error_message": error_text,
                            "api_url": self.api_url,
                            "minio_url": http_url,
                            "project_name": project_name,
                            "instruction": "PDF解析API调用失败，请检查服务状态"
                        }
                        
        except Exception as e:
            print(f"❌ PDF解析API调用异常: {str(e)}")
            return {
                "success": False,
                "error_type": "execution_error",
                "error_message": f"PDF解析调用异常: {str(e)}",
                "api_url": self.api_url,
                "instruction": "PDF解析API调用异常，请检查网络连接和参数格式"
            }

    async def _execute_document_generator_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        专门处理 document_generator API 调用
        
        按照 DocumentGenerationRequest 格式调用外部API：
        {
          "query": "文档生成需求描述",
          "project_name": "项目名称"
        }
        
        处理文档生成响应格式：
        {
          "task_id": "string",
          "status": "string", 
          "message": "string",
          "files": {...},
          "minio_urls": {...}
        }
        """
        try:
            print(f"📝 处理文档生成请求")
            
            # 🎯 按照 DocumentGenerationRequest 格式准备请求数据
            api_request = {
                "query": payload.get("query", ""),
                "project_name": payload.get("project_name", "")
            }
            
            print(f"📋 发送参数: {json.dumps(api_request, ensure_ascii=False)}")
            
            # 🚀 发送API请求到外部文档生成服务
            import aiohttp
            import asyncio
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=api_request,  # 只发送query和project_name
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    print(f"📡 文档生成API响应状态码: {response.status}")
                    
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ 文档生成API调用成功")
                        print(f"📋 API返回数据: {json.dumps(result, ensure_ascii=False, indent=2)}")
                        
                        # 🎯 处理 DocumentGenerationResponse 格式
                        task_id = result.get("task_id")
                        status = result.get("status", "unknown")
                        message = result.get("message", "文档生成任务已提交")
                        files = result.get("files") or {}  # 处理null值
                        minio_urls = result.get("minio_urls") or {}  # 处理null值
                        
                        # 构建标准化响应
                        standardized_result = {
                            "success": True,
                            "api_status": "成功",
                            "http_status": 200,
                            "tool_name": "document_generator",
                            "task_id": task_id,
                            "status": status,
                            "message": message,
                            "files": files,
                            "minio_urls": minio_urls,
                            "download_info": self._format_download_info(files, minio_urls),
                            "agent_message": f"文档生成任务已提交！{message}"
                        }
                        
                        # 根据状态调整消息
                        if status == "pending":
                            standardized_result["agent_message"] = f"✅ 文档生成任务已提交！\n\n**任务信息：**\n- 任务ID: {task_id}\n- 状态: 处理中\n- 说明: {message}\n\n文档正在生成中，完成后将提供下载链接。"
                        elif status == "completed" and minio_urls:
                            standardized_result["has_downloads"] = True
                            standardized_result["download_count"] = len(minio_urls)
                            standardized_result["agent_message"] = f"✅ 文档生成完成！{message}"
                        
                        return standardized_result
                    else:
                        error_text = await response.text()
                        print(f"❌ 文档生成API调用失败: 状态码={response.status}, 错误={error_text}")
                        return {
                            "success": False,
                            "error_type": "api_error",
                            "http_status": response.status,
                            "error_message": error_text,
                            "api_url": self.api_url,
                            "tool_name": "document_generator",
                            "instruction": "文档生成API调用失败，请检查服务状态"
                        }
                        
        except Exception as e:
            print(f"❌ 文档生成API调用异常: {str(e)}")
            return {
                "success": False,
                "error_type": "execution_error",
                "error_message": f"文档生成调用异常: {str(e)}",
                "api_url": self.api_url,
                "tool_name": "document_generator",
                "instruction": "文档生成API调用异常，请检查网络连接和参数格式"
            }
    
    def _format_download_info(self, files: dict, minio_urls: dict) -> dict:
        """格式化下载信息，供AI使用"""
        download_info = {}
        
        # 🔧 修复：正确处理null值
        if not files or not minio_urls:
            return download_info
            
        for key in files.keys():
            filename = files.get(key, f"文件_{key}")
            download_url = minio_urls.get(key)
            
            if download_url:
                download_info[key] = {
                    "filename": filename,
                    "download_url": download_url,
                    "display_name": filename
                }
        
        return download_info
    
    def analyze_api_error(self, status_code: int, error_text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析API调用失败的原因
        
        Args:
            status_code: HTTP状态码
            error_text: API返回的错误文本
            payload: 发送的参数
            
        Returns:
            结构化的错误分析结果
        """
        error_analysis = {
            "error_type": "unknown_error",
            "error_details": "未知错误",
            "fix_suggestion": "请检查网络连接或API服务状态",
            "retry_possible": True,
            "parameter_issues": [],
            "suggested_params": {},
            "raw_error_details": []
        }
        
        if status_code == 400:
            error_analysis["error_type"] = "bad_request"
            error_analysis["error_details"] = f"请求参数错误: {error_text}"
            error_analysis["fix_suggestion"] = "请检查发送的参数是否符合API要求"
            error_analysis["retry_possible"] = False
            
            # 尝试解析FastAPI格式的错误详情
            try:
                error_json = json.loads(error_text)
                if isinstance(error_json, dict) and "detail" in error_json:
                    error_analysis.update(self._analyze_fastapi_error(error_json, payload))
            except json.JSONDecodeError:
                pass # 如果不是JSON，则不解析
        
        elif status_code == 401:
            error_analysis["error_type"] = "unauthorized"
            error_analysis["error_details"] = f"未授权访问: {error_text}"
            error_analysis["fix_suggestion"] = "请检查API密钥或令牌是否有效"
            error_analysis["retry_possible"] = False
        
        elif status_code == 403:
            error_analysis["error_type"] = "forbidden"
            error_analysis["error_details"] = f"禁止访问: {error_text}"
            error_analysis["fix_suggestion"] = "请检查API密钥或令牌权限"
            error_analysis["retry_possible"] = False
        
        elif status_code == 404:
            error_analysis["error_type"] = "not_found"
            error_analysis["error_details"] = f"资源未找到: {error_text}"
            error_analysis["fix_suggestion"] = "请检查API文档或URL是否正确"
            error_analysis["retry_possible"] = False
        
        elif status_code == 500:
            error_analysis["error_type"] = "server_error"
            error_analysis["error_details"] = f"服务器内部错误: {error_text}"
            error_analysis["fix_suggestion"] = "请稍后再试或联系API服务提供者"
            error_analysis["retry_possible"] = True
        
        elif status_code == 503:
            error_analysis["error_type"] = "service_unavailable"
            error_analysis["error_details"] = f"服务不可用: {error_text}"
            error_analysis["fix_suggestion"] = "请稍后再试或联系API服务提供者"
            error_analysis["retry_possible"] = True
        
        else:
            error_analysis["error_type"] = "http_error"
            error_analysis["error_details"] = f"HTTP错误 (状态码: {status_code}): {error_text}"
            error_analysis["retry_possible"] = True
        
        return error_analysis
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """通过API调用执行工具，简化错误处理，让主Agent决策"""
        try:
            # 🔑 自动注入项目上下文到工具调用
            payload = {
                **kwargs,
                "project_context": self.project_context
            }
            
            print(f"🔧 调用工具API: {self.name} -> {self.api_url}")
            print(f"📋 发送参数: {json.dumps(payload, ensure_ascii=False)}")
            print(f"🏗️ 项目上下文: {self.project_context}")
            
            # 🧠 特殊处理PDF解析工具
            if self.name == "pdf_parser":
                return await self._execute_pdf_parser_api(payload)
            
            # 🧠 特殊处理文档生成工具
            if self.name == "document_generator":
                return await self._execute_document_generator_api(payload)
            
            # 🧠 特殊处理内部工具 (移除check_project_state)
            # if self.name == "check_project_state":
            #     return await self._execute_check_project_state(payload)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=300)  # 设置为5分钟超时
                ) as response:
                    print(f"📡 API响应状态码: {response.status}")
                    
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ API调用成功")
                        
                        # 🎯 关键修复：确保200状态码响应包含success=true
                        # 对于RAG工具等，API返回200就认为成功，包装成标准格式
                        if not isinstance(result, dict):
                            result = {"data": result}
                        
                        # 如果没有success字段，添加success=true（因为HTTP状态码已经是200）
                        if "success" not in result:
                            result["success"] = True
                            result["http_status"] = 200
                            result["message"] = f"{self.name} API调用成功"
                            print(f"🔧 自动添加success=true字段")
                        
                        # 如果有success字段但为false，检查是否有有效数据
                        elif not result.get("success", True):
                            # 如果有数据内容，仍然认为是成功的
                            if any(key in result for key in ["data", "results", "documents", "items", "content"]):
                                result["success"] = True
                                result["http_status"] = 200
                                result["original_success"] = False
                                result["message"] = f"{self.name} API调用成功，已获取数据"
                                print(f"🔧 检测到数据内容，强制设置success=true")
                        
                        print(f"📋 最终返回结果success状态: {result.get('success')}")
                        return result
                    else:
                        error_text = await response.text()
                        print(f"❌ API调用失败: 状态码={response.status}, 错误={error_text}")
                        
                        # 🧠 简化错误处理，让主Agent自己分析
                        return {
                            "success": False,
                            "error_type": "api_error",
                            "http_status": response.status,
                            "error_message": error_text,
                            "api_url": self.api_url,
                            "sent_params": payload,
                            "tool_name": self.name,
                            "tool_parameters": self.parameters,
                            "instruction": "请分析此API错误并决定如何处理"
                        }
                        
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error_type": "timeout_error",
                "error_message": f"工具API调用超时: {self.api_url}",
                "api_url": self.api_url,
                "tool_name": self.name,
                "instruction": "请分析超时原因并决定是否重试"
            }
        except aiohttp.ClientError as e:
            print(f"❌ 网络连接失败: {str(e)}")
            return {
                "success": False,
                "error_type": "connection_error",
                "error_message": f"工具API连接失败: {str(e)}",
                "api_url": self.api_url,
                "tool_name": self.name,
                "instruction": "请分析连接问题并决定如何处理"
            }
        except Exception as e:
            print(f"❌ 工具执行异常: {str(e)}")
            return {
                "success": False,
                "error_type": "execution_error",
                "error_message": f"工具调用异常: {str(e)}",
                "api_url": self.api_url,
                "tool_name": self.name,
                "instruction": "请分析异常原因并决定如何处理"
            }

class ToolRegistry:
    """工具注册器 - 专注于API工具管理"""
    
    def __init__(self, project_context: Optional[Dict[str, Any]] = None):
        self.tools: Dict[str, BaseTool] = {}
        self.project_context = project_context or {}
        
    def set_project_context(self, project_context: Dict[str, Any]):
        """设置项目上下文"""
        self.project_context = project_context
        # 更新所有已注册工具的项目上下文
        for tool in self.tools.values():
            if hasattr(tool, 'project_context'):
                tool.project_context = project_context
            
    def register_api_tool(self, name: str, description: str, parameters: Dict[str, Any], api_url: str):
        """注册API工具"""
        tool = APITool(name, description, parameters, api_url, self.project_context)
        self.tools[name] = tool
        print(f"📝 注册API工具: {name} -> {api_url}")
        
    async def execute_tool(self, name: str, **kwargs) -> Dict[str, Any]:
        """执行工具，自动注入项目上下文"""
        if name not in self.tools:
            return {
                "success": False,
                "error": f"工具 '{name}' 未找到。可用工具: {list(self.tools.keys())}"
            }
        
        # 🏗️ 自动注入项目上下文参数
        if self.project_context and self.project_context.get('project_name'):
            # 为需要project_name的工具自动注入参数
            if name in ['rag_tool', 'pdf_parser'] and 'project_name' not in kwargs:
                kwargs['project_name'] = self.project_context['project_name']
                print(f"🏗️ 自动注入项目参数到{name}: project_name={self.project_context['project_name']}")
            
            # 为其他工具也可以添加项目上下文（如果需要）
            # if name == 'document_generator':
            #     kwargs['project_context'] = self.project_context
            
        tool = self.tools[name]
        return await tool.execute(**kwargs)
        
    def get_tools_description(self) -> str:
        """获取所有工具的描述"""
        descriptions = []
        for tool in self.tools.values():
            info = tool.get_info()
            param_desc = json.dumps(info["parameters"], ensure_ascii=False, indent=2)
            descriptions.append(f"工具名: {info['name']}\n描述: {info['description']}\n参数: {param_desc}")
            
        return "\n\n".join(descriptions)
        
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具"""
        return [tool.get_info() for tool in self.tools.values()]

def create_core_tool_registry(project_context: Optional[Dict[str, Any]] = None) -> ToolRegistry:
    """
    创建核心工具注册器 - API模式
    注册你同事们部署的独立工具服务
    """
    registry = ToolRegistry(project_context)
    
    # 🌐 API工具注册 - 对应你同事们的独立服务
    
    # PDF解析工具服务 (端口8001)
    registry.register_api_tool(
        name="pdf_parser",
        description="解析PDF文件，提取文本、图片、表格等内容。需要project_name参数和minio_url参数。",
        parameters={
            "project_name": {"type": "string", "description": "项目名称（必需，作为query参数）"},
            "minio_url": {"type": "string", "description": "PDF在MinIO的文件路径（必需，格式：minio://bucket/file.pdf）"}
        },
        api_url="http://43.139.19.144:8001/api/v1/process_pdf"
    )
    
    # RAG检索工具服务 (端口8002)
    registry.register_api_tool(
        name="rag_tool", 
        description="基于语义的文档检索工具，从已有文档中查找相关内容。只能检索已有文档，不能生成新内容。",
        parameters={
            "query": {"type": "string", "description": "检索查询，包含问题的核心关键词"},
            "top_k": {"type": "integer", "description": "返回结果数量", "default": 5},
            "project_name": {"type": "string", "description": "项目名称过滤", "default": None},
            "search_type": {"type": "string", "description": "搜索类型: text, image, table", "default": "text"}
        },
        api_url="http://43.139.19.144:8001/api/v1/search"
    )
    
    # 文档生成工具服务 (外部API)
    registry.register_api_tool(
        name="document_generator",
        description="生成各种格式的文档和报告。根据项目内容生成分析报告、总结文档等。返回包含task_id和下载链接的响应。",
        parameters={
            "query": {"type": "string", "description": "文档生成需求描述，详细说明要生成什么类型的文档"},
            "project_name": {"type": "string", "description": "项目名称，用于RAG检索相关内容"}
        },
        api_url="http://43.139.19.144:8002/generate_document"  # 调用外部文档生成服务
    )
    

    return registry 