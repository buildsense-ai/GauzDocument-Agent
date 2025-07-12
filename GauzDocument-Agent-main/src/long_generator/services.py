# 文件名: services.py
# -*- coding: utf-8 -*-

"""
services.py

封装了所有对外部服务的调用接口。
AI模型调用已从模拟数据更新为对接真实的DeepSeek API。
RAG相关功能已更新为使用本地的RAG工具。
"""

import json
import sys
import os
from typing import Dict, Any, List

# 导入requests和urllib库
import requests
import urllib.parse

# 导入openai库
import openai
# 从我们自己的模块导入配置
from config import Config

# 🆕 导入本地RAG工具 - 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from src.rag_tool_chroma import RAGTool
    from src.pdf_embedding_service import PDFEmbeddingService
    print("✅ 本地RAG工具导入成功")
    RAG_TOOL_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ 本地RAG工具导入失败: {e}")
    RAG_TOOL_AVAILABLE = False

# 🆕 全局RAG工具实例
_rag_tool = None
_pdf_embedding_service = None

def _get_rag_tool():
    """获取RAG工具实例（单例模式）"""
    global _rag_tool
    if _rag_tool is None and RAG_TOOL_AVAILABLE:
        try:
            _rag_tool = RAGTool()
            print("✅ RAG工具实例化成功")
        except Exception as e:
            print(f"❌ RAG工具实例化失败: {e}")
            _rag_tool = None
    return _rag_tool

def _get_pdf_embedding_service():
    """获取PDF嵌入服务实例（单例模式）"""
    global _pdf_embedding_service
    if _pdf_embedding_service is None and RAG_TOOL_AVAILABLE:
        try:
            _pdf_embedding_service = PDFEmbeddingService()
            print("✅ PDF嵌入服务实例化成功")
        except Exception as e:
            print(f"❌ PDF嵌入服务实例化失败: {e}")
            _pdf_embedding_service = None
    return _pdf_embedding_service


def call_ai_model(prompt: str, context: str | None = None, expect_json: bool = False) -> Dict[str, Any]:
    """
    [已更新] 调用DeepSeek AI模型。

    Args:
        prompt (str): 发送给AI的核心指令。
        context (str, optional): 补充的上下文信息。
        expect_json (bool): 是否强制要求AI返回JSON对象。默认为False。

    Returns:
        Dict[str, Any]: AI的响应。如果expect_json为True，则为解析后的JSON对象；
                        如果为False，则为格式如 {'text': '...'} 的字典。
    """
    if not Config.DEEPSEEK_API_KEY:
        raise ValueError("错误：DEEPSEEK_API_KEY 环境变量未设置。请在运行脚本前设置您的API密钥。")

    try:
        client = openai.OpenAI(
            api_key=Config.DEEPSEEK_API_KEY,
            base_url=Config.DEEPSEEK_API_BASE
        )
    except Exception as e:
        raise Exception(f"初始化AI客户端时发生错误: {e}")

    messages = []
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": prompt})

    print(f"\n===== [调用 DeepSeek AI] =====")
    print(f"模型: {Config.AI_MODEL_NAME}")
    print(f"要求JSON: {expect_json}")
    # 注释：为了避免日志过长，只打印部分提示
    print(f"提示 (Prompt): {prompt[:200]}...")

    api_params = {
        "model": Config.AI_MODEL_NAME,
        "messages": messages
    }
    if expect_json:
        api_params['response_format'] = {'type': 'json_object'}

    try:
        response = client.chat.completions.create(**api_params)
        response_content = response.choices[0].message.content

        print("===== [DeepSeek 响应成功] =====")

        if expect_json:
            return json.loads(response_content)
        else:
            return {'text': response_content}

    except openai.APIStatusError as e:
        # [已优化] 尝试解析并包含更详细的API错误信息
        try:
            error_details = e.response.json()
            error_message = error_details.get('error', {}).get('message', e.response.text)
        except json.JSONDecodeError:
            error_message = e.response.text
        raise Exception(f"DeepSeek API返回错误状态码 {e.status_code}: {error_message}")
    except Exception as e:
        raise Exception(f"调用AI模型时发生未知错误: {e}")


def search_vectordata(query: str, top_k: int) -> List[str]:
    """
    [已更新] 使用本地RAG工具搜索向量知识库。
    
    Args:
        query (str): 搜索查询
        top_k (int): 返回结果数量
        
    Returns:
        List[str]: 搜索结果文本列表
    """
    print(f"🔍 [本地RAG] 搜索向量数据库")
    print(f"查询: {query}, Top_K: {top_k}")
    
    if not RAG_TOOL_AVAILABLE:
        print("⚠️ 本地RAG工具不可用，返回空结果")
        return []
    
    try:
        rag_tool = _get_rag_tool()
        if not rag_tool:
            print("❌ 无法获取RAG工具实例")
            return []
        
        # 使用RAG工具搜索文档
        result = rag_tool.execute(
            action="search",
            query=query,
            top_k=top_k
        )
        
        # 解析JSON结果
        if isinstance(result, str):
            try:
                data = json.loads(result)
                if data.get("status") == "success":
                    results = data.get("results", [])
                    # 提取内容文本
                    content_list = []
                    for item in results:
                        content = item.get("content", "").strip()
                        if content:
                            content_list.append(content)
                    
                    print(f"✅ [本地RAG] 搜索成功，获得 {len(content_list)} 条结果")
                    return content_list
                else:
                    print(f"❌ [本地RAG] 搜索失败: {data.get('message', 'Unknown error')}")
                    return []
            except json.JSONDecodeError:
                print(f"❌ [本地RAG] 解析搜索结果失败")
                return []
        else:
            print(f"❌ [本地RAG] 搜索返回非字符串结果: {type(result)}")
            return []
            
    except Exception as e:
        print(f"❌ [本地RAG] 搜索时发生错误: {e}")
        return []


def get_info(query: str = "", top_k: int = 5) -> str:
    """
    [新增] 获取详细信息，使用本地RAG工具搜索相关信息。
    
    Args:
        query (str): 搜索查询，默认为空
        top_k (int): 返回结果数量，默认为5
        
    Returns:
        str: 搜索到的信息文本
    """
    print(f"📋 [本地RAG] 获取信息")
    print(f"查询: {query}, Top_K: {top_k}")
    
    if not query:
        query = "项目概况 基本信息"  # 默认查询
    
    try:
        # 使用search_vectordata获取信息
        content_list = search_vectordata(query, top_k)
        
        if content_list:
            # 合并所有搜索结果
            combined_info = "\n\n".join(content_list)
            print(f"✅ [本地RAG] 信息获取成功，总长度: {len(combined_info)} 字符")
            return combined_info
        else:
            print("⚠️ [本地RAG] 未找到相关信息")
            return ""
            
    except Exception as e:
        print(f"❌ [本地RAG] 获取信息时发生错误: {e}")
        return ""


def get_summary(query: str = "", top_k: int = 3) -> str:
    """
    [新增] 获取总结信息，使用本地RAG工具搜索核心要点。
    
    Args:
        query (str): 搜索查询，默认为空
        top_k (int): 返回结果数量，默认为3
        
    Returns:
        str: 搜索到的总结文本
    """
    print(f"📝 [本地RAG] 获取总结")
    print(f"查询: {query}, Top_K: {top_k}")
    
    if not query:
        query = "总结 概述 核心要点"  # 默认查询
    
    try:
        # 使用search_vectordata获取总结信息
        content_list = search_vectordata(query, top_k)
        
        if content_list:
            # 选择最相关的结果作为总结
            summary = content_list[0] if content_list else ""
            print(f"✅ [本地RAG] 总结获取成功，长度: {len(summary)} 字符")
            return summary
        else:
            print("⚠️ [本地RAG] 未找到总结信息")
            return ""
            
    except Exception as e:
        print(f"❌ [本地RAG] 获取总结时发生错误: {e}")
        return ""


def get_image_info_from_local(query: str, top_k: int = 5) -> List[str]:
    """
    [新增] 使用本地RAG工具搜索图片信息。
    
    Args:
        query (str): 搜索查询
        top_k (int): 返回结果数量
        
    Returns:
        List[str]: 图片URL列表
    """
    print(f"🖼️ [本地RAG] 搜索图片信息")
    print(f"查询: {query}, Top_K: {top_k}")
    
    if not RAG_TOOL_AVAILABLE:
        print("⚠️ 本地RAG工具不可用，返回空结果")
        return []
    
    try:
        rag_tool = _get_rag_tool()
        if not rag_tool:
            print("❌ 无法获取RAG工具实例")
            return []
        
        # 使用RAG工具搜索图片
        result = rag_tool.execute(
            action="search_images",
            query=query,
            top_k=top_k
        )
        
        # 解析JSON结果
        if isinstance(result, str):
            try:
                data = json.loads(result)
                if data.get("status") == "success":
                    results = data.get("results", [])
                    # 提取图片URL
                    image_urls = []
                    for item in results:
                        metadata = item.get("metadata", {})
                        # 优先使用MinIO URL
                        minio_url = metadata.get("minio_url", "")
                        if minio_url:
                            image_urls.append(minio_url)
                        else:
                            # 如果没有MinIO URL，尝试使用本地路径
                            image_path = metadata.get("image_path", "")
                            if image_path:
                                image_urls.append(image_path)
                    
                    print(f"✅ [本地RAG] 图片搜索成功，获得 {len(image_urls)} 个图片URL")
                    return image_urls
                else:
                    print(f"❌ [本地RAG] 图片搜索失败: {data.get('message', 'Unknown error')}")
                    return []
            except json.JSONDecodeError:
                print(f"❌ [本地RAG] 解析图片搜索结果失败")
                return []
        else:
            print(f"❌ [本地RAG] 图片搜索返回非字符串结果: {type(result)}")
            return []
            
    except Exception as e:
        print(f"❌ [本地RAG] 图片搜索时发生错误: {e}")
        return []
