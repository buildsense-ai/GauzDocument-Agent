"""
DeepSeek API Client for ReAct Agent
"""
import os
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DeepSeekClient:
    """DeepSeek API客户端，用于与DeepSeek模型交互"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "deepseek-chat",
        max_tokens: int = 4000,
        temperature: float = 0.1,
        enable_cache_monitoring: bool = True
    ):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.enable_cache_monitoring = enable_cache_monitoring
        
        # 缓存统计
        self.cache_stats = {
            "total_requests": 0,
            "total_prompt_tokens": 0,
            "cache_hit_tokens": 0,
            "cache_miss_tokens": 0,
            "total_cost_saved": 0.0
        }
        
        if not self.api_key:
            raise ValueError("DeepSeek API key is required. Set DEEPSEEK_API_KEY environment variable.")
        
        # 创建httpx客户端，禁用代理以避免连接问题
        try:
            import httpx
            # 通过环境变量方式禁用代理
            if 'ALL_PROXY' in os.environ:
                # 临时移除代理环境变量
                old_proxy = os.environ.pop('ALL_PROXY', None)
            http_client = httpx.Client(timeout=30.0)
        except ImportError:
            # 如果httpx不可用，使用默认配置
            http_client = None
        
        # 初始化OpenAI客户端（兼容DeepSeek API）
        if http_client:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                http_client=http_client
            )
        else:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """发送聊天完成请求到DeepSeek API，返回内容和使用统计"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                stop=stop_sequences
            )
            
            content = response.choices[0].message.content
            result_content = content.strip() if content else ""
            
            # 提取使用统计信息
            usage_info = {}
            if hasattr(response, 'usage') and response.usage:
                usage_info = {
                    "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0),
                    "completion_tokens": getattr(response.usage, 'completion_tokens', 0),
                    "total_tokens": getattr(response.usage, 'total_tokens', 0),
                    "prompt_cache_hit_tokens": getattr(response.usage, 'prompt_cache_hit_tokens', 0),
                    "prompt_cache_miss_tokens": getattr(response.usage, 'prompt_cache_miss_tokens', 0)
                }
                
                # 更新缓存统计
                if self.enable_cache_monitoring:
                    self._update_cache_stats(usage_info)
            
            return result_content, usage_info
        
        except Exception as e:
            raise Exception(f"DeepSeek API 请求失败: {str(e)}")
    
    def _update_cache_stats(self, usage_info: Dict[str, Any]):
        """更新缓存统计信息"""
        self.cache_stats["total_requests"] += 1
        self.cache_stats["total_prompt_tokens"] += usage_info.get("prompt_tokens", 0)
        
        cache_hit = usage_info.get("prompt_cache_hit_tokens", 0)
        cache_miss = usage_info.get("prompt_cache_miss_tokens", 0)
        
        self.cache_stats["cache_hit_tokens"] += cache_hit
        self.cache_stats["cache_miss_tokens"] += cache_miss
        
        # 计算节省的成本 (假设正常价格为 $0.14/M tokens，缓存价格为 $0.014/M tokens)
        if cache_hit > 0:
            cost_saved = (cache_hit / 1_000_000) * (0.14 - 0.014)
            self.cache_stats["total_cost_saved"] += cost_saved
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self.enable_cache_monitoring:
            return {"message": "缓存监控未启用"}
        
        stats = self.cache_stats.copy()
        
        # 计算缓存命中率
        total_cache_tokens = stats["cache_hit_tokens"] + stats["cache_miss_tokens"]
        if total_cache_tokens > 0:
            cache_hit_rate = (stats["cache_hit_tokens"] / total_cache_tokens) * 100
            stats["cache_hit_rate"] = round(cache_hit_rate, 2)
        else:
            stats["cache_hit_rate"] = 0
        
        # 格式化成本节省
        stats["total_cost_saved"] = round(stats["total_cost_saved"], 4)
        
        return stats
    
    def print_cache_stats(self):
        """打印缓存统计信息"""
        stats = self.get_cache_stats()
        
        if "message" in stats:
            print(stats["message"])
            return
        
        print("\n📊 DeepSeek Context Caching 统计信息")
        print("=" * 50)
        print(f"📈 总请求次数: {stats['total_requests']}")
        print(f"🎯 缓存命中率: {stats['cache_hit_rate']}%")
        print(f"✅ 缓存命中 tokens: {stats['cache_hit_tokens']:,}")
        print(f"❌ 缓存未命中 tokens: {stats['cache_miss_tokens']:,}")
        print(f"💰 预估节省成本: ${stats['total_cost_saved']}")
        print("=" * 50)
        
        if stats['cache_hit_tokens'] > 0:
            print("🎉 您正在受益于DeepSeek的Context Caching功能！")
        else:
            print("💡 提示：当有重复内容时，缓存功能会自动激活")
    
    def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """生成单个响应（兼容性方法，只返回内容）"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        content, _ = self.chat_completion(messages)
        return content 