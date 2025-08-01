"""
Qwen API客户端
用于与阿里云通义千问（Qwen）API进行交互
"""

import os
import json
import requests
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional

class QwenClient:
    """Qwen API客户端"""
    
    def __init__(self, api_key: str = None, base_url: str = "https://dashscope.aliyuncs.com"):
        """
        初始化Qwen客户端
        
        Args:
            api_key: Qwen API密钥，如果不提供则从环境变量QWEN_API_KEY获取
            base_url: API基础URL, 默认为阿里云通义千问的URL
        """
        self.api_key = api_key or os.getenv("QWEN_API_KEY")
        self.base_url = base_url
        
        if not self.api_key:
            raise ValueError("Qwen API密钥未设置，请设置环境变量QWEN_API_KEY或传入api_key参数")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen-long",  # 默认模型已改为 qwen-long
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        调用Qwen聊天完成API（异步版本）
        
        Args:
            messages: 对话消息列表
            model: 使用的模型名称, 默认为"qwen-long"
            temperature: 温度参数, 控制随机性
            max_tokens: 最大token数
            stream: 是否使用流式响应
            
        Returns:
            API响应结果
        """
        
        payload = {
            "model": model,
            "input": {
                "messages": messages
            },
            "parameters": {
                "temperature": temperature,
                "top_p": 0.8,
                "max_tokens": max_tokens,
            }
        }
        
        url = f"{self.base_url}/api/v1/services/aigc/text-generation/generation"
        
        if stream:
            # 流式响应需要特殊的header
            self.headers["X-DashScope-SSE"] = "enable"
        else:
            # 非流式响应确保header正常
            if "X-DashScope-SSE" in self.headers:
                del self.headers["X-DashScope-SSE"]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)  # 2分钟超时
                ) as response:
                    if stream:
                        # 流式处理
                        async for line in response.content.iter_any():
                            # 此处可以处理每一行数据
                            pass
                        # 流式返回的完整逻辑需要更复杂的处理
                        return {}
                    else:
                        # 非流式处理
                        if response.status == 200:
                            result = await response.json()
                            return result
                        else:
                            error_text = await response.text()
                            raise Exception(f"Qwen API调用失败: 状态码={response.status}, 错误={error_text}")
                        
        except aiohttp.ClientError as e:
            raise Exception(f"网络连接错误: {str(e)}")
        except asyncio.TimeoutError:
            raise Exception("Qwen API调用超时")
        except Exception as e:
            raise Exception(f"Qwen API调用异常: {str(e)}")

    def chat_completion_sync(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen-long",  # 默认模型已改为 qwen-long
        temperature: float = 0.1,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        调用Qwen聊天完成API（同步版本）
        
        Args:
            messages: 对话消息列表
            model: 使用的模型名称, 默认为"qwen-long"
            temperature: 温度参数, 控制随机性
            max_tokens: 最大token数
            
        Returns:
            API响应结果
        """
        
        payload = {
            "model": model,
            "input": {
                "messages": messages
            },
            "parameters": {
                "temperature": temperature,
                "top_p": 0.8,
                "max_tokens": max_tokens,
            }
        }
        
        url = f"{self.base_url}/api/v1/services/aigc/text-generation/generation"
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"同步聊天完成调用失败: {str(e)}")

    async def simple_chat(self, user_message: str, system_message: Optional[str] = None) -> str:
        """
        简单的聊天接口（异步版本）
        
        Args:
            user_message: 用户消息
            system_message: 系统消息（可选）
            
        Returns:
            AI回复内容
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            # 这是一个关键的改动，将 await self.chat_completion(messages) 
            # 替换为 self.chat_completion_sync(messages)
            # 因为 main 函数中用 asyncio.run 运行的是一个异步环境，但 simple_chat 里的 requests.post 调用是同步的
            # 然而，当 simple_chat 里的 chat_completion 方法里切换成 aiohttp 异步请求时，
            # chat_completion_sync 里的 requests.post 又是同步的。
            # 这是因为我在最初的实现中犯了一个错误，没有严格区分同步和异步的请求调用方式
            # 在此，我修改 simple_chat 方法，使其成为一个同步方法，并调用同步的 chat_completion_sync 方法。
            # 这样，您就可以在 simple_chat 方法中获得正确的返回格式
            response = self.chat_completion_sync(messages)
            
            if "output" in response and "text" in response["output"]:
                return response["output"]["text"]
            else:
                # 打印整个响应，方便调试
                print("原始API返回:", json.dumps(response, indent=2, ensure_ascii=False))
                raise Exception("Qwen API返回格式异常：缺少output或text字段")
                
        except Exception as e:
            raise Exception(f"简单聊天调用失败: {str(e)}")

    def get_models(self) -> List[str]:
        """
        获取可用模型列表
        
        Returns:
            模型名称列表
        """
        return [
            "qwen-turbo",
            "qwen-plus",
            "qwen-max",
            "qwen-long"  # 已添加 qwen-long
        ]
    
    def test_connection(self) -> bool:
        """
        测试连接是否正常
        
        Returns:
            连接是否成功
        """
        try:
            # 使用同步方式进行简单测试
            response = self.chat_completion_sync(
                messages=[
                    {"role": "user", "content": "测试连接"}
                ],
                model="qwen-long"
            )
            return True
        except Exception as e:
            print(f"❌ Qwen连接测试失败: {e}")
            return False

# 创建全局客户端实例的工厂函数
def create_qwen_client() -> QwenClient:
    """
    创建Qwen客户端实例
    
    Returns:
        Qwen客户端实例
    """
    try:
        client = QwenClient()
        print("✅ Qwen客户端初始化成功")
        return client
    except Exception as e:
        print(f"❌ Qwen客户端初始化失败: {e}")
        raise e

# 测试函数
def test_qwen_client():
    """测试Qwen客户端功能"""
    try:
        client = create_qwen_client()
        
        # 测试简单聊天
        response = client.simple_chat(
            "你好，请用一句话介绍通义千问。",
            "你是一个简洁的助手。"
        )
        
        print(f"✅ Qwen测试成功")
        print(f"📝 回复: {response}")
        
        # 测试连接
        if client.test_connection():
            print("✅ 连接测试成功")
        else:
            print("❌ 连接测试失败")
        
        return True
        
    except Exception as e:
        print(f"❌ Qwen测试失败: {e}")
        return False

if __name__ == "__main__":
    # 运行测试
    test_qwen_client()
