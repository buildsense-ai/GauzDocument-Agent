"""
Qwen (通义千问) API Client
支持阿里云通义千问模型，包括批处理模式
"""

import os
import json
import time
from typing import List, Dict, Any, Optional, Union
from openai import OpenAI
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

class QwenClient:
    """阿里云通义千问API客户端，兼容OpenAI API接口"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "qwen-turbo-latest",
        max_tokens: int = 4000,
        temperature: float = 0.1,
        timeout: int = 60,
        max_retries: int = 3,
        enable_batch_mode: bool = False
    ):
        """
        初始化Qwen客户端
        
        Args:
            api_key: API密钥
            base_url: API基础URL
            model: 模型名称
            max_tokens: 最大tokens数
            temperature: 温度参数
            timeout: 请求超时时间
            max_retries: 最大重试次数
            enable_batch_mode: 是否启用批处理模式
        """
        self.api_key = api_key or os.getenv("QWEN_API_KEY")
        self.base_url = base_url or os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.enable_batch_mode = enable_batch_mode
        
        # 请求统计
        self.request_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "timeout_errors": 0,
            "api_errors": 0
        }
        
        if not self.api_key:
            raise ValueError("Qwen API key is required. Set QWEN_API_KEY environment variable.")
        
        # 初始化OpenAI兼容客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )
        
        print(f"✅ Qwen客户端初始化成功")
        print(f"🎯 模型: {self.model}")
        print(f"🔗 基础URL: {self.base_url}")
        print(f"⚡ 批处理模式: {'启用' if self.enable_batch_mode else '禁用'}")
    
    def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        生成单个响应
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示（可选）
            
        Returns:
            str: 模型响应
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        return self._call_api(messages)
    
    def call_api(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        调用API的通用方法（兼容现有接口）
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示（可选）
            
        Returns:
            str: 模型响应
        """
        return self.generate_response(prompt, system_prompt)
    
    def batch_generate_responses(self, prompts: List[str], system_prompt: Optional[str] = None, max_workers: int = 10) -> List[str]:
        """
        批量生成响应（并行处理）
        
        Args:
            prompts: 提示列表
            system_prompt: 系统提示（可选）
            max_workers: 最大并行工作数
            
        Returns:
            List[str]: 响应列表
        """
        if not prompts:
            return []
        
        print(f"🚀 启动批量处理：{len(prompts)} 个请求，最大并行数: {max_workers}")
        
        results = [None] * len(prompts)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_index = {
                executor.submit(self.generate_response, prompt, system_prompt): i
                for i, prompt in enumerate(prompts)
            }
            
            # 收集结果
            completed_count = 0
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    results[index] = result
                    completed_count += 1
                    print(f"✅ 批量处理进度: {completed_count}/{len(prompts)}")
                except Exception as e:
                    print(f"❌ 批量处理失败 (索引 {index}): {e}")
                    results[index] = f"处理失败: {e}"
        
        print(f"🎉 批量处理完成: {completed_count}/{len(prompts)} 成功")
        return results
    
    def _call_api(self, messages: List[Dict[str, str]]) -> str:
        """
        调用API的核心方法
        
        Args:
            messages: 消息列表
            
        Returns:
            str: 模型响应
        """
        for attempt in range(self.max_retries):
            try:
                self.request_stats["total_requests"] += 1
                
                # 调用API
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
                )
                
                # 提取响应内容
                content = response.choices[0].message.content
                
                # 更新统计信息
                self.request_stats["successful_requests"] += 1
                if hasattr(response, 'usage') and response.usage:
                    self.request_stats["total_tokens"] += response.usage.total_tokens
                
                return content
                
            except Exception as e:
                self.request_stats["failed_requests"] += 1
                error_msg = str(e)
                
                # 分类错误类型
                if "timeout" in error_msg.lower():
                    self.request_stats["timeout_errors"] += 1
                    print(f"⏱️ 请求超时 (尝试 {attempt + 1}/{self.max_retries}): {error_msg}")
                else:
                    self.request_stats["api_errors"] += 1
                    print(f"❌ API错误 (尝试 {attempt + 1}/{self.max_retries}): {error_msg}")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 指数退避
                    print(f"⏳ 等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    # 最后一次尝试失败，抛出异常
                    raise Exception(f"API调用失败，已重试 {self.max_retries} 次: {error_msg}")
        
        return ""
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取请求统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            **self.request_stats,
            "success_rate": (
                self.request_stats["successful_requests"] / max(1, self.request_stats["total_requests"])
            ) * 100,
            "timeout_rate": (
                self.request_stats["timeout_errors"] / max(1, self.request_stats["total_requests"])
            ) * 100,
            "api_error_rate": (
                self.request_stats["api_errors"] / max(1, self.request_stats["total_requests"])
            ) * 100
        }
    
    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        print("\n📊 Qwen客户端统计信息:")
        print(f"总请求数: {stats['total_requests']}")
        print(f"成功请求: {stats['successful_requests']}")
        print(f"失败请求: {stats['failed_requests']}")
        print(f"成功率: {stats['success_rate']:.1f}%")
        print(f"超时率: {stats['timeout_rate']:.1f}%")
        print(f"API错误率: {stats['api_error_rate']:.1f}%")
        print(f"总tokens: {stats['total_tokens']}") 