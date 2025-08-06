"""AI编辑器工具路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import httpx
import json
from deepseek_client import DeepSeekClient
from qwen_client import QwenClient

# 创建路由器
router = APIRouter(prefix="/api/ai-editor", tags=["ai-editor"])

@router.get("/test")
async def test_route():
    """测试路由是否工作"""
    return {"message": "ai_editor路由工作正常!"}

# 请求模型
class AIEditorRequest(BaseModel):
    plain_text: List[str]
    request: str
    project_name: str
    search_type: str = "hybrid"
    top_k: int = 5

# 响应模型
class AIEditorResponse(BaseModel):
    success: bool
    result: str
    error: str = None

@router.post("/process", response_model=AIEditorResponse)
async def ai_editor_process(data: AIEditorRequest):
    """
    AI编辑器处理端点
    
    Args:
        data: 包含plain_text、request、rag_info的请求数据
    
    Returns:
        处理结果
    """
    try:
        # 调用ai_editor函数处理
        result = await ai_editor(
            plain_text=data.plain_text,
            request=data.request,
            project_name=data.project_name,
            search_type=data.search_type,
            top_k=data.top_k
        )
        
        return AIEditorResponse(
            success=True,
            result=result
        )
    
    except Exception as e:
        return AIEditorResponse(
            success=False,
            result="",
            error=str(e)
        )

async def ai_editor(plain_text: List[str], request: str, project_name: str, search_type: str = "hybrid", top_k: int = 5) -> str:
    """
    AI编辑器核心函数
    
    Args:
        plain_text: 要编辑的纯文本内容列表
        request: 用户的编辑请求
        project_name: 项目名称
        search_type: 搜索类型，默认为"hybrid"
        top_k: 返回结果数量，默认为5
    
    Returns:
        编辑后的结果
    """
    try:
        # 1. 使用DeepSeek客户端提取关键词
        deepseek_client = DeepSeekClient()
        keywords = await extract_keywords_from_request(deepseek_client, request)
        
        # 2. 进行两次RAG搜索
        # 第一次：使用关键词搜索
        rag_info_keywords = await get_rag_info(keywords, project_name, search_type, 5)
        
        # 第二次：使用原始request搜索
        rag_info_original = await get_rag_info(request, project_name, search_type, 5)
        
        # 3. 使用Qwen-long模型生成优化后的文本
        qwen_client = QwenClient()
        optimized_text = await generate_optimized_text(
            qwen_client=qwen_client,
            plain_text=plain_text,
            request=request,
            keywords=keywords,
            rag_info_keywords=rag_info_keywords,
            rag_info_original=rag_info_original
        )

        result = f"""
{optimized_text}
"""        
#         result = f"""AI编辑器处理结果：
# 原文本数量: {len(plain_text)}
# 用户请求: {request}
# 提取的关键词: {keywords}
# 项目名称: {project_name}

# === 优化后的文本 ===
# {optimized_text}

# === 参考资料摘要 ===
# 关键词搜索结果: {rag_info_keywords[:200]}...
# 原始请求搜索结果: {rag_info_original[:200]}..."""
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI编辑器处理失败: {str(e)}")


async def get_rag_info(query: str, project_name: str, search_type: str = "hybrid", top_k: int = 5) -> str:
    """
    调用RAG搜索API获取相关信息
    
    Args:
        query: 搜索查询
        project_name: 项目名称
        search_type: 搜索类型
        top_k: 返回结果数量
    
    Returns:
        RAG搜索结果的字符串表示
    """
    try:
        # 构建请求数据
        request_data = {
            "query": query,
            "project_name": project_name,
            "search_type": search_type,
            "top_k": top_k
        }
        
        # 调用外部RAG API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://43.139.19.144:8001/api/v1/search",
                headers={
                    "accept": "application/json",
                    "Content-Type": "application/json"
                },
                json=request_data
            )
            
            if response.status_code == 200:
                result = response.json()
                # 将结果转换为字符串格式
                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                return f"RAG API调用失败: HTTP {response.status_code} - {response.text}"
                
    except Exception as e:
        return f"RAG API调用异常: {str(e)}"


async def generate_optimized_text(
    qwen_client: QwenClient,
    plain_text: List[str],
    request: str,
    keywords: str,
    rag_info_keywords: str,
    rag_info_original: str
) -> str:
    """
    使用Qwen-long模型生成优化后的文本
    
    Args:
        qwen_client: Qwen客户端实例
        plain_text: 原始文本列表
        request: 用户请求
        keywords: 提取的关键词
        rag_info_keywords: 关键词RAG搜索结果
        rag_info_original: 原始请求RAG搜索结果
    
    Returns:
        优化后的文本
    """
    try:
        # 构建系统提示词
        system_prompt = """你是一个专业的文档编辑助手。你的任务是根据用户的要求和提供的参考资料，对原始文本进行优化和改进。
"""
        
        # 构建用户提示词
        user_prompt = f"""请根据以下信息优化文本：

【用户要求】
{request}

【提取的关键词】
{keywords}

【原始文本】
{chr(10).join(f"{i+1}. {text}" for i, text in enumerate(plain_text))}

【参考资料1 - 关键词搜索结果】
{rag_info_keywords[:1000]}

【参考资料2 - 原始请求搜索结果】
{rag_info_original[:1000]}

请基于上述信息，生成优化后的文本段落，直接给结果，不要加问候语和任何解释。"""
        
        # 调用Qwen-long模型
        print(f"开始调用Qwen模型，用户提示词长度: {len(user_prompt)}")
        print(f"系统提示词: {system_prompt[:100]}...")
        
        optimized_result = await qwen_client.simple_chat(
            user_message=user_prompt,
            system_message=system_prompt
        )
        
        print(f"Qwen模型返回结果长度: {len(optimized_result)}")
        print(f"返回结果前100字符: {optimized_result[:100]}...")
        
        return optimized_result.strip()
        
    except Exception as e:
        # 如果AI生成失败，抛出异常让用户知道真正的错误原因
        print(f"文本优化失败: {e}")
        raise Exception(f"AI文本生成失败: {str(e)}。请检查AI模型配置和网络连接。")


async def extract_keywords_from_request(deepseek_client: DeepSeekClient, request: str) -> str:
    """
    使用DeepSeek客户端从用户请求中提取关键词
    
    Args:
        deepseek_client: DeepSeek客户端实例
        request: 用户的原始请求
    
    Returns:
        提取的关键词字符串
    """
    try:
        system_prompt = """你是一个专业的关键词提取助手。请从用户的请求中提取最重要的关键词，用于文档搜索。

要求：
1. 提取3-5个最核心的关键词
2. 关键词应该是名词或关键概念
3. 去除停用词和无意义的词汇
4. 用空格分隔关键词
5. 只返回关键词，不要其他解释

示例：
用户请求："请帮我优化这些关于医疗设备管理的文档内容"
关键词：医疗设备 管理 文档 优化"""
        
        user_prompt = f"请从以下用户请求中提取关键词：\n{request}"
        
        # 调用DeepSeek API提取关键词
        keywords = await deepseek_client.simple_chat(
            user_message=user_prompt,
            system_message=system_prompt
        )
        
        # 清理返回的关键词（去除可能的多余字符）
        keywords = keywords.strip().replace('\n', ' ').replace('\t', ' ')
        
        # 如果提取失败，返回原始请求的前几个词作为备选
        if not keywords or len(keywords) < 2:
            # 简单的备选方案：取原始请求的前几个有意义的词
            words = request.split()[:3]
            keywords = ' '.join(words)
        
        return keywords
        
    except Exception as e:
        # 如果关键词提取失败，返回原始请求作为备选
        print(f"关键词提取失败: {e}")
        return request