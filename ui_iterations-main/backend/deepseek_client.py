"""
DeepSeek API客户端
用于与DeepSeek API进行交互
"""

import os
import json
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional

class DeepSeekClient:
    """DeepSeek API客户端"""
    
    def __init__(self, api_key: str = None, base_url: str = "https://api.deepseek.com"):
        """
        初始化DeepSeek客户端
        
        Args:
            api_key: DeepSeek API密钥，如果不提供则从环境变量DEEPSEEK_API_KEY获取
            base_url: API基础URL
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url
        
        if not self.api_key:
            raise ValueError("DeepSeek API密钥未设置，请设置环境变量DEEPSEEK_API_KEY或传入api_key参数")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        调用DeepSeek聊天完成API
        
        Args:
            messages: 对话消息列表
            model: 使用的模型名称
            temperature: 温度参数，控制随机性
            max_tokens: 最大token数
            stream: 是否使用流式响应
            
        Returns:
            API响应结果
        """
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        url = f"{self.base_url}/v1/chat/completions"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)  # 2分钟超时
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        return result
                    else:
                        error_text = await response.text()
                        raise Exception(f"DeepSeek API调用失败: 状态码={response.status}, 错误={error_text}")
                        
        except aiohttp.ClientError as e:
            raise Exception(f"网络连接错误: {str(e)}")
        except asyncio.TimeoutError:
            raise Exception("DeepSeek API调用超时")
        except Exception as e:
            raise Exception(f"DeepSeek API调用异常: {str(e)}")
    
    async def simple_chat(self, user_message: str, system_message: str = None) -> str:
        """
        简单的聊天接口
        
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
            response = await self.chat_completion(messages)
            
            if "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"]
            else:
                raise Exception("DeepSeek API返回格式异常：缺少choices字段")
                
        except Exception as e:
            raise Exception(f"简单聊天调用失败: {str(e)}")
    
    def chat_completion_sync(
        self,
        messages: List[Dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        同步版本的聊天完成API
        
        Args:
            messages: 对话消息列表
            model: 使用的模型名称
            temperature: 温度参数，控制随机性
            max_tokens: 最大token数
            stream: 是否使用流式响应
            
        Returns:
            API响应结果
        """
        import asyncio
        
        # 创建新的事件循环来运行异步方法
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                self.chat_completion(messages, model, temperature, max_tokens, stream)
            )
            
            loop.close()
            return result
            
        except Exception as e:
            raise Exception(f"同步聊天完成调用失败: {str(e)}")
    
    def get_models(self) -> List[str]:
        """
        获取可用模型列表
        
        Returns:
            模型名称列表
        """
        return [
            "deepseek-chat",
            "deepseek-coder"
        ]
    
    def test_connection(self) -> bool:
        """
        测试连接是否正常
        
        Returns:
            连接是否成功
        """
        try:
            # 使用同步方式进行简单测试
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                self.simple_chat("测试连接", "你是一个助手，请简短回复。")
            )
            
            loop.close()
            return True
            
        except Exception as e:
            print(f"DeepSeek连接测试失败: {e}")
            return False

# 创建全局客户端实例的工厂函数
def create_deepseek_client() -> DeepSeekClient:
    """
    创建DeepSeek客户端实例
    
    Returns:
        DeepSeek客户端实例
    """
    try:
        client = DeepSeekClient()
        print("✅ DeepSeek客户端初始化成功")
        return client
    except Exception as e:
        print(f"❌ DeepSeek客户端初始化失败: {e}")
        raise e

# 测试函数
async def test_deepseek_client():
    """测试DeepSeek客户端功能"""
    try:
        client = create_deepseek_client()
        
        # 测试简单聊天
        response = await client.simple_chat(
            "你好，请用一句话介绍DeepSeek。",
            "你是一个简洁的助手。"
        )
        
        print(f"✅ DeepSeek测试成功")
        print(f"📝 回复: {response}")
        
        return True
        
    except Exception as e:
        print(f"❌ DeepSeek测试失败: {e}")
        return False

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_deepseek_client()) 