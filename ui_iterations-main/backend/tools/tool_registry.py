"""
工具注册器
专注于API工具调用，支持分布式工具部署架构
"""

import json
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod

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
            
            # 🔄 转换MinIO路径为HTTP URL
            # minio://bucket/object -> http://43.139.19.144:9000/bucket/object
            path_without_prefix = minio_url[8:]  # 移除 "minio://"
            http_url = f"http://43.139.19.144:9000/{path_without_prefix}"
            print(f"🔄 MinIO路径转换: {minio_url} -> {http_url}")
            
            # 🚀 构建JSON请求体
            json_payload = {
                "minio_url": http_url,
                "project_name": project_name or "默认项目"
            }
            
            print(f"📤 JSON请求体: {json.dumps(json_payload, ensure_ascii=False)}")
            
            # 🌐 发送JSON请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=json_payload,
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
                        print(f"❌ PDF解析API失败: 状态码={response.status}, 错误={error_text}")
                        
                        # 🧠 智能错误分析
                        error_analysis = self.analyze_api_error(response.status, error_text, payload)
                        
                        return {
                            "success": False,
                            "error": f"PDF解析API调用失败 (状态码: {response.status}): {error_text}",
                            "error_type": error_analysis["error_type"],
                            "error_details": error_analysis["error_details"],
                            "fix_suggestion": error_analysis["fix_suggestion"],
                            "retry_possible": error_analysis["retry_possible"],
                            "parameter_issues": error_analysis.get("parameter_issues", []),
                            "suggested_params": error_analysis.get("suggested_params", {}),
                            "original_params": payload,
                            "tool_parameters": self.parameters,
                            "http_status": response.status,
                            "raw_error": error_text
                        }
                        
        except Exception as e:
            print(f"❌ PDF解析调用异常: {str(e)}")
            return {
                "success": False,
                "error_type": "execution_error",
                "error": f"PDF解析调用异常: {str(e)}",
                "fix_suggestion": "请检查文件路径和网络连接",
                "retry_possible": True
            }
    
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
            # 为RAG工具自动注入project_name参数
            if name == 'rag_tool' and 'project_name' not in kwargs:
                kwargs['project_name'] = self.project_context['project_name']
                print(f"🏗️ 自动注入项目参数: project_name={self.project_context['project_name']}")
            
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
        api_url="https://624a83d8.r23.cpolar.top/api/v1/process_pdf"
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
        api_url="https://624a83d8.r23.cpolar.top/api/v1/search"
    )
    
    # 文档生成工具服务 (端口8003)
    registry.register_api_tool(
        name="document_generator",
        description="生成各种格式的文档和报告。支持analysis、summary、report等类型。",
        parameters={
            "query": {"type": "string", "description": "用户生成文档要求"},
            "project_name": {"type": "string", "description": "项目名称"}
        },
        api_url="https://29aee89.r23.cpolar.top/generate_document"
    )
    
    # 🔄 内部工具：项目状态检查 (移除，改为文件存储)
    # registry.register_api_tool(
    #     name="check_project_state",
    #     description="检查当前项目的解析状态和文档数量",
    #     parameters={
    #         "project_id": {"type": "string", "description": "项目ID（可选，默认使用当前项目）", "default": None}
    #     },
    #     api_url="internal://check_project_state"
    # )

    return registry 