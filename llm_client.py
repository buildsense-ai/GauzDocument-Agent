#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM客户端 - 支持Qwen v4的1024维embedding
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import requests
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class LLMConfig:
    """LLM配置类"""
    # Qwen API配置
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"
    qwen_max_tokens: int = 1500
    qwen_temperature: float = 0.0
    qwen_timeout: int = 25
    
    # Qwen embedding配置 - v4支持1024维度
    qwen3_embedding_model: str = "text-embedding-v4"
    qwen3_embedding_dimension: int = 1024
    
    def __post_init__(self):
        """初始化后处理，从环境变量读取配置"""
        self.qwen_api_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or self.qwen_api_key
        self.qwen_base_url = os.getenv("QWEN_BASE_URL") or self.qwen_base_url
        self.qwen_model = os.getenv("QWEN_MODEL") or self.qwen_model
        self.qwen_max_tokens = int(os.getenv("QWEN_MAX_TOKENS", self.qwen_max_tokens))
        self.qwen_temperature = float(os.getenv("QWEN_TEMPERATURE", self.qwen_temperature))
        self.qwen_timeout = int(os.getenv("QWEN_TIMEOUT", self.qwen_timeout))
        
        self.qwen3_embedding_model = os.getenv("QWEN3_EMBEDDING_MODEL") or self.qwen3_embedding_model
        self.qwen3_embedding_dimension = int(os.getenv("QWEN3_EMBEDDING_DIMENSION", self.qwen3_embedding_dimension))

class LLMClient:
    """LLM客户端类"""
    
    def __init__(self, config: LLMConfig = None):
        """初始化LLM客户端"""
        self.config = config or LLMConfig()
        
        if not self.config.qwen_api_key:
            raise ValueError("❌ 缺少QWEN API密钥，请设置QWEN_API_KEY或DASHSCOPE_API_KEY环境变量")
        
        logger.info(f"✅ LLM客户端初始化成功")
        logger.info(f"🔧 Qwen模型: {self.config.qwen_model}")
        logger.info(f"🔧 Embedding模型: {self.config.qwen3_embedding_model} ({self.config.qwen3_embedding_dimension}维)")
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        获取文本的embedding向量
        
        Args:
            texts: 待处理的文本列表
            
        Returns:
            List[List[float]]: embedding向量列表，每个向量为1024维
        """
        if not texts:
            return []
        
        try:
            # 构建请求
            headers = {
                "Authorization": f"Bearer {self.config.qwen_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.config.qwen3_embedding_model,
                "input": texts
            }
            
            # 发送请求
            response = requests.post(
                f"{self.config.qwen_base_url}/embeddings",
                headers=headers,
                json=data,
                timeout=self.config.qwen_timeout
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Embedding API请求失败: {response.status_code} - {response.text}")
                return []
            
            result = response.json()
            
            # 提取embedding向量
            embeddings = []
            if "data" in result:
                for item in result["data"]:
                    if "embedding" in item:
                        embedding = item["embedding"]
                        if len(embedding) == self.config.qwen3_embedding_dimension:
                            embeddings.append(embedding)
                        else:
                            logger.warning(f"⚠️ Embedding维度不匹配: 期望{self.config.qwen3_embedding_dimension}，实际{len(embedding)}")
                            embeddings.append(embedding)
            
            if embeddings:
                logger.debug(f"✅ 成功获取{len(embeddings)}个embedding向量，维度: {len(embeddings[0])}")
            else:
                logger.warning("⚠️ 未获取到embedding向量")
            
            return embeddings
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ Embedding请求超时 ({self.config.qwen_timeout}s)")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Embedding请求失败: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"❌ 解析embedding响应失败: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ 获取embedding时发生未知错误: {e}")
            return []
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
        """
        聊天完成接口（如果需要的话）
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            Optional[str]: 回复内容
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.config.qwen_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.config.qwen_model,
                "messages": messages,
                "max_tokens": self.config.qwen_max_tokens,
                "temperature": self.config.qwen_temperature,
                **kwargs
            }
            
            response = requests.post(
                f"{self.config.qwen_base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=self.config.qwen_timeout
            )
            
            if response.status_code != 200:
                logger.error(f"❌ 聊天API请求失败: {response.status_code} - {response.text}")
                return None
            
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                logger.debug(f"✅ 获取聊天回复成功")
                return content
            else:
                logger.warning("⚠️ 未获取到聊天回复")
                return None
                
        except Exception as e:
            logger.error(f"❌ 聊天请求失败: {e}")
            return None
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            # 测试embedding功能
            test_embeddings = self.get_embeddings(["测试连接"])
            if test_embeddings and len(test_embeddings) > 0:
                logger.info(f"✅ LLM客户端连接测试成功，embedding维度: {len(test_embeddings[0])}")
                return True
            else:
                logger.error("❌ LLM客户端连接测试失败")
                return False
        except Exception as e:
            logger.error(f"❌ LLM客户端连接测试异常: {e}")
            return False

def test_llm_client():
    """测试LLM客户端"""
    print("🧪 测试LLM客户端...")
    
    try:
        # 创建配置和客户端
        config = LLMConfig()
        client = LLMClient(config)
        
        # 测试连接
        if client.test_connection():
            print("✅ LLM客户端测试通过")
            
            # 测试embedding
            test_texts = ["这是一个测试文本", "测试embedding功能"]
            embeddings = client.get_embeddings(test_texts)
            
            if embeddings:
                print(f"✅ Embedding测试成功:")
                print(f"   - 文本数量: {len(test_texts)}")
                print(f"   - 向量数量: {len(embeddings)}")
                print(f"   - 向量维度: {len(embeddings[0])}")
            else:
                print("❌ Embedding测试失败")
        else:
            print("❌ LLM客户端测试失败")
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")

if __name__ == "__main__":
    test_llm_client() 