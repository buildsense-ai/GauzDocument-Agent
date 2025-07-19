"""
混合LLM客户端 - DeepSeek用于对话决策，Qwen用于向量检索
整合了Prompt管理器功能
"""
import os
import json
import logging
import requests
import yaml
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import time
from pathlib import Path
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class LLMConfig:
    """混合LLM API配置 - DeepSeek用于对话，Qwen用于embedding"""
    # DeepSeek配置（用于对话）
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    
    # Qwen配置（用于embedding）
    qwen_api_key: str = os.getenv("QWEN_API_KEY", "") or os.getenv("DASHSCOPE_API_KEY", "")
    qwen_base_url: str = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    
    # 对话配置（DeepSeek）
    chat_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    max_tokens: int = int(os.getenv("DEEPSEEK_MAX_TOKENS", "1500"))
    temperature: float = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.0"))
    timeout: int = int(os.getenv("DEEPSEEK_TIMEOUT", "25"))
    
    # Embedding配置（Qwen）
    embedding_model: str = os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v4")
    embedding_dimension: int = int(os.getenv("QWEN_EMBEDDING_DIMENSION", "1024"))

class PromptManager:
    """
    Prompt管理器 - 加载prompt目录下的所有YAML配置文件
    """
    
    def __init__(self, prompt_dir: str = "prompt"):
        self.prompt_dir = Path(prompt_dir)
        self.prompts = {}
        self.yaml_configs = {}
        self._load_prompts()
    
    def _load_prompts(self):
        """加载prompt文件"""
        if not self.prompt_dir.exists():
            logger.error(f"Prompt目录不存在: {self.prompt_dir}")
            return
        
        # 加载YAML配置文件
        self._load_yaml_configs()
    
    def _load_yaml_configs(self):
        """加载YAML配置文件"""
        yaml_files = list(self.prompt_dir.glob("*.yaml")) + list(self.prompt_dir.glob("*.yml"))
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                    
                config_name = yaml_file.stem
                self.yaml_configs[config_name] = config_data
                
                # 将YAML中的所有模板加载到prompts字典中
                for key, value in config_data.items():
                    if isinstance(value, str) and len(value) > 50:  # 假设长字符串是模板
                        self.prompts[key] = value
                        logger.info(f"已加载prompt: {key}")
                        
            except Exception as e:
                logger.error(f"加载YAML文件失败: {yaml_file}, 错误: {e}")
    
    def get_prompt(self, prompt_name: str) -> str:
        """获取指定的prompt"""
        if prompt_name in self.prompts:
            return self.prompts[prompt_name]
        else:
            logger.warning(f"Prompt不存在: {prompt_name}，可用的prompts: {list(self.prompts.keys())}")
            return ""
    
    def get_config(self, config_name: str) -> Dict[str, Any]:
        """获取YAML配置"""
        if config_name in self.yaml_configs:
            return self.yaml_configs[config_name]
        else:
            logger.warning(f"配置不存在: {config_name}")
            return {}
    
    def format_prompt(self, prompt_name: str, **kwargs) -> str:
        """格式化prompt模板"""
        template = self.get_prompt(prompt_name)
        if not template:
            logger.error(f"Prompt模板不存在: {prompt_name}")
            return ""
        
        try:
            return template.format(**kwargs)
        except Exception as e:
            logger.error(f"格式化prompt失败 {prompt_name}: {e}")
            return template
    
    def list_prompts(self) -> Dict[str, str]:
        """列出所有可用的prompts"""
        return {
            name: content[:100] + "..." if len(content) > 100 else content 
            for name, content in self.prompts.items()
        }

class LLMClient:
    """混合LLM客户端 - DeepSeek用于对话，Qwen用于embedding"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        
        # 验证DeepSeek API密钥
        if not self.config.deepseek_api_key:
            raise ValueError("DeepSeek API密钥未设置。请在环境变量中设置DEEPSEEK_API_KEY。")
        
        # 验证Qwen API密钥（用于embedding）
        if not self.config.qwen_api_key:
            raise ValueError("Qwen API密钥未设置。请在环境变量中设置QWEN_API_KEY或DASHSCOPE_API_KEY。")
        
        # DeepSeek headers（用于对话）
        self.deepseek_headers = {
            "Authorization": f"Bearer {self.config.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        
        # Qwen headers（用于embedding）
        self.qwen_headers = {
            "Authorization": f"Bearer {self.config.qwen_api_key}",
            "Content-Type": "application/json"
        }
        
        # 初始化Prompt管理器
        self.prompt_manager = PromptManager()
        
    def chat(self, messages: List[Dict[str, str]], model: str = None) -> str:
        """
        与DeepSeek LLM进行对话
        
        Args:
            messages: 对话消息列表
            model: 模型名称（可选）
            
        Returns:
            AI回复内容
        """
        try:
            model = model or self.config.chat_model
            
            logger.info(f"🔵 DeepSeek API 调用开始")
            logger.info(f"   📡 API URL: {self.config.deepseek_base_url}/chat/completions")
            logger.info(f"   🤖 模型: {model}")
            
            # 只显示第一条消息的简要内容
            if messages:
                first_msg = messages[0].get('content', '')
                # 不显示完整的prompt内容，只显示前100字符
                preview = first_msg[:100] + "..." if len(first_msg) > 100 else first_msg
                logger.info(f"   📋 消息1 [user]: {preview}")
            
            # 构建请求数据
            data = {
                "model": model,
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens
            }
            
            response = requests.post(
                f"{self.config.deepseek_base_url}/chat/completions",
                headers=self.deepseek_headers,
                json=data,
                timeout=self.config.timeout
            )
            
            logger.info(f"✅ DeepSeek API 调用成功 (HTTP {response.status_code})")
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Token使用统计（保留）
                usage = result.get('usage', {})
                logger.info(f"📊 Token使用: 输入{usage.get('prompt_tokens', 0)} + 输出{usage.get('completion_tokens', 0)} = 总计{usage.get('total_tokens', 0)}")
                
                return content
            else:
                logger.error(f"❌ DeepSeek API错误: HTTP {response.status_code}")
                logger.error(f"❌ 错误内容: {response.text}")
                return "API调用失败"
                
        except Exception as e:
            logger.error(f"❌ DeepSeek API调用异常: {e}")
            return "API调用异常"
    
    def get_embeddings(self, texts: Union[str, List[str]], model: Optional[str] = None) -> List[List[float]]:
        """
        调用Qwen Embedding API
        
        Args:
            texts: 文本或文本列表
            model: 模型名称（可选）
            
        Returns:
            向量列表
        """
        # 检查Qwen API配置
        if not self.config.qwen_api_key:
            logger.error("❌ Qwen API密钥未设置，无法使用embedding功能")
            return []
        
        model = model or self.config.embedding_model
        
        if isinstance(texts, str):
            texts = [texts]
        
        # 使用你提供的API格式
        data = {
            "model": model,
            "input": texts,
            "dimensions": self.config.embedding_dimension,  # 指定向量维度
            "encoding_format": "float"
        }
        
        logger.info(f"🔵 Qwen Embedding API 调用开始")
        logger.info(f"   📡 API URL: {self.config.qwen_base_url}/embeddings")
        logger.info(f"   🤖 模型: {model}")
        logger.info(f"   📝 文本数量: {len(texts)}")
        logger.info(f"   📊 向量维度: {self.config.embedding_dimension}")
        
        try:
            import time
            start_time = time.time()
            
            response = requests.post(
                f"{self.config.qwen_base_url}/embeddings",
                headers=self.qwen_headers,
                json=data,
                timeout=self.config.timeout
            )
            
            request_time = time.time() - start_time
            
            # 打印HTTP状态码（用户要求的格式）
            api_url = f"{self.config.qwen_base_url}/embeddings"
            print(f"http api {api_url} status = {response.status_code}")
            
            if response.status_code == 200:
                logger.info(f"✅ Qwen Embedding API 调用成功 (HTTP 200) - 用时: {request_time:.2f}秒")
                result = response.json()
                embeddings = [item["embedding"] for item in result["data"]]
                logger.info(f"✅ 成功获取 {len(embeddings)} 个向量，每个向量维度: {len(embeddings[0]) if embeddings else 0}")
                return embeddings
            else:
                logger.error(f"❌ Qwen Embedding API 调用失败 (HTTP {response.status_code}) - 用时: {request_time:.2f}秒")
                logger.error(f"   ❌ 错误详情: {response.text}")
                error_msg = f"Embedding API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return []
                
        except Exception as e:
            # 网络异常时也打印状态信息
            api_url = f"{self.config.qwen_base_url}/embeddings"
            print(f"http api {api_url} status = EXCEPTION ({str(e)})")
            error_msg = f"Embedding API调用异常: {str(e)}"
            logger.error(error_msg)
            return []
    
    # 旧的方法已被React Agent的三大核心工具替代
    # 保留向后兼容但不再使用
    
    def format_prompt(self, prompt_name: str, **kwargs) -> str:
        """格式化prompt的便捷方法"""
        return self.prompt_manager.format_prompt(prompt_name, **kwargs)

# 全局prompt管理器实例
global_prompt_manager = PromptManager()

def get_prompt(prompt_name: str) -> str:
    """便捷函数：获取prompt"""
    return global_prompt_manager.get_prompt(prompt_name)

def format_prompt(prompt_name: str, **kwargs) -> str:
    """便捷函数：格式化prompt"""
    return global_prompt_manager.format_prompt(prompt_name, **kwargs)

def get_config(config_name: str) -> Dict[str, Any]:
    """便捷函数：获取配置"""
    return global_prompt_manager.get_config(config_name)

# 使用示例
if __name__ == "__main__":
    # 测试混合LLM客户端
    client = LLMClient()
    
    # 测试Prompt管理器
    print("📋 所有可用的prompts:")
    for name, preview in client.prompt_manager.list_prompts().items():
        print(f"  {name}: {preview}")
    
    # 测试DeepSeek对话API调用
    messages = [{"role": "user", "content": "你好"}]
    response = client.chat(messages)
    print(f"\n🤖 DeepSeek聊天测试结果: {response}") 