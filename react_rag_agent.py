"""
自省式React RAG Agent - 重构为两个核心工具
模版搜索工具（ElasticSearch + LLM重排序） + search_document工具（自省式搜索，动态调整参数）
"""
import os
import json
import yaml
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import time
from datetime import datetime
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, NotFoundError
import pymysql  # 添加MySQL连接支持

# 加载环境变量
load_dotenv()

# 导入组件
from llm_client import LLMClient, LLMConfig, format_prompt
from rag_tool_chroma import RAGTool, ChromaVectorStore
from hybrid_search_engine import HybridSearchEngine

logger = logging.getLogger(__name__)

class SimplifiedSearchTool(Enum):
    """简化搜索工具枚举 - 两个核心工具"""
    # 模版搜索工具：ElasticSearch + LLM重排序，一次性完成
    TEMPLATE_SEARCH = "template_search_tool"
    
    # 文档搜索工具：自省式搜索，动态调整参数
    SEARCH_DOCUMENT = "search_document"

@dataclass
class ReactStep:
    """React步骤"""
    step_number: int
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: str
    timestamp: str

@dataclass
class AgentResponse:
    """Agent响应"""
    success: bool
    final_answer: str
    react_steps: List[ReactStep]
    total_steps: int
    execution_time: float
    metadata: Dict[str, Any]

import hashlib
from functools import lru_cache
from mysql_connection_manager import mysql_manager

class QueryCache:
    """查询结果缓存"""
    
    def __init__(self, max_size=100):
        self.cache = {}
        self.max_size = max_size
        self.enabled = os.getenv("ENABLE_QUERY_CACHE", "false").lower() == "true"
    
    def get_cache_key(self, query: str) -> str:
        """生成缓存键"""
        return hashlib.md5(query.encode('utf-8')).hexdigest()
    
    def get(self, query: str):
        """获取缓存结果"""
        if not self.enabled:
            return None
        
        key = self.get_cache_key(query)
        return self.cache.get(key)
    
    def set(self, query: str, result: Any):
        """设置缓存结果"""
        if not self.enabled:
            return
        
        key = self.get_cache_key(query)
        
        # 如果缓存已满，删除最旧的条目
        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[key] = {
            'result': result,
            'timestamp': time.time()
        }
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
class SimplifiedReactAgent:
    """自省式React Agent - 两个核心工具 (template_search_tool + search_document)"""
    
    def __init__(self, storage_dir: str = None):
        """初始化简化版React Agent"""
        # 使用pdf_embedding_storage作为默认存储目录
        self.storage_dir = storage_dir or os.getenv("RAG_STORAGE_DIR", "pdf_embedding_storage")
        
        # 初始化组件
        self.llm_client = LLMClient(LLMConfig())
        
        # 初始化内置MySQL连接（替代外部mysql_retriever）
        self._init_mysql_connection()
        
        # 初始化ElasticSearch客户端
        self.es_client = None
        self.es_index_name = "template_search_index"
        self._init_elasticsearch()
        
        # 初始化RAG工具和混合搜索，使用pdf_embedding_storage
        self.rag_tool = RAGTool(self.storage_dir, self.llm_client)
        self.hybrid_searcher = HybridSearchEngine(
            self.rag_tool.vector_store, 
            self.llm_client
        )
        
        # 配置参数 - 极简为1步
        self.max_steps = int(os.getenv("MAX_REACT_STEPS", "1"))
        
        # 加载所有prompt模板
        self.rerank_prompt_template = self._load_rerank_prompt()
        self.step_prompts = self._load_step_prompts()
        
        logger.info("✅ 简化版React Agent初始化完成 - 极简版 (DeepSeek+Qwen + 1步循环)")
        logger.info(f"📊 最大步骤数: {self.max_steps} (极简配置)")
        logger.info("🧠 支持工具: template_search_tool (ElasticSearch+LLM) + search_document (自省式搜索)")
        logger.info("🚀 优化特性: DeepSeek+Qwen混合API + 智能终止 + 缓存机制")
    
    def _load_rerank_prompt(self) -> str:
        """从YAML文件加载LLM重排序prompt模板"""
        try:
            prompt_file = os.path.join(os.path.dirname(__file__), "prompt", "template_rerank.yaml")
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_data = yaml.safe_load(f)
                template = prompt_data.get('template_rerank_prompt', '')
                if not template:
                    raise ValueError("template_rerank_prompt not found in yaml file")
                logger.info("✅ 成功加载LLM重排序prompt模板")
                return template
        except Exception as e:
            logger.error(f"❌ 加载LLM重排序prompt失败: {e}")
            raise RuntimeError(f"无法加载LLM重排序prompt模板: {e}")
    
    def _load_step_prompts(self) -> Dict[str, str]:
        """从YAML文件加载React步骤prompt模板"""
        try:
            prompt_file = os.path.join(os.path.dirname(__file__), "prompt", "react_step_prompts.yaml")
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_data = yaml.safe_load(f)
                required_prompts = ['first_step_prompt', 'continue_step_prompt', 'final_answer_format']
                for prompt_name in required_prompts:
                    if not prompt_data.get(prompt_name):
                        raise ValueError(f"{prompt_name} not found in yaml file")
                logger.info("✅ 成功加载React步骤prompt模板")
                return prompt_data
        except Exception as e:
            logger.error(f"❌ 加载React步骤prompt失败: {e}")
            raise RuntimeError(f"无法加载React步骤prompt模板: {e}")
    
    def process_query(self, user_query: str) -> str:
        """
        处理用户查询 - 智能选择两个核心工具
        
        Args:
            user_query: 用户查询
            
        Returns:
            包含完整React过程的JSON字符串
        """
        start_time = time.time()
        
        # 保存当前用户查询供智能参数提取使用
        self._current_user_query = user_query
        
        print(f"\n🚀 ===== 简化版React Agent启动 (两个核心工具) =====")
        print(f"📝 用户查询: {user_query}")
        print(f"🧠 即将开始AI智能工具选择...")
        
        logger.info(f"🚀 开始处理查询: {user_query}")
        
        # 初始化响应
        response = AgentResponse(
            success=False,
            final_answer="",
            react_steps=[],
            total_steps=0,
            execution_time=0.0,
            metadata={}
        )
        
        try:
            # React循环 - 智能工具选择和自动放宽策略
            for step_num in range(1, self.max_steps + 1):
                print(f"\n🔄 ===== React步骤 {step_num} =====")
                logger.info(f"🔄 开始React步骤 {step_num}")
                
                # 1. 思考阶段 - AI智能分析工具选择
                print(f"🤔 思考阶段...")
                logger.info(f"🤔 THOUGHT 阶段开始 - 步骤{step_num}")
                thought, action, action_input = self._think_step(user_query, response.react_steps, step_num)
                
                print(f"💭 AI思考: {thought}")
                print(f"🎯 决定行动: {action}")
                print(f"📝 行动参数: {action_input}")
                
                # 详细记录思考过程
                logger.info(f"💭 THOUGHT: {thought}")
                logger.info(f"🎯 ACTION: {action}")
                logger.info(f"📝 ACTION_INPUT: {json.dumps(action_input, ensure_ascii=False)}")
                
                # 2. 行动阶段 - 执行工具
                print(f"⚡ 行动阶段...")
                logger.info(f"⚡ ACTION 执行阶段开始 - 工具: {action}")
                observation = self._action_step(action, action_input)
                
                print(f"👀 观察结果: {observation}")
                logger.info(f"👀 OBSERVATION: {observation}")
                
                # 3. 记录步骤
                react_step = ReactStep(
                    step_number=step_num,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation=observation,
                    timestamp=datetime.now().isoformat()
                )
                response.react_steps.append(react_step)
                
                # 4. 检查是否完成
                if self._should_finish(thought, action, observation, step_num):
                    print(f"✅ React循环完成，共执行{step_num}步")
                    break
                    
                print(f"➡️ 继续下一步...")
            
            # 生成最终答案
            response.final_answer = self._generate_final_answer(user_query, response.react_steps)
            response.success = True
            response.total_steps = len(response.react_steps)
            response.execution_time = time.time() - start_time
            
            print(f"\n🎯 ===== React Agent完成 =====")
            print(f"📊 总步骤: {response.total_steps}")
            print(f"⏱️ 执行时间: {response.execution_time:.2f}秒")
            print(f"✅ 最终答案长度: {len(response.final_answer)}字符")
            
            # 构建详细响应
            detailed_response = {
                "status": "success",
                "query": user_query,
                "react_process": {
                    "total_steps": response.total_steps,
                    "steps": [
                        {
                            "step_number": step.step_number,
                            "thought": step.thought,
                            "action": step.action,
                            "action_input": step.action_input,
                            "observation": step.observation,
                            "timestamp": step.timestamp
                        } for step in response.react_steps
                    ]
                },
                "final_answer": response.final_answer,
                "execution_time": response.execution_time,
                "metadata": {
                    "max_steps_reached": response.total_steps >= self.max_steps,
                    "tools_used": list(set([step.action for step in response.react_steps])),
                    "success": response.success
                }
            }
            
            return json.dumps(detailed_response, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"❌ React Agent处理失败: {e}")
            error_response = {
                "status": "error",
                "query": user_query,
                "error": str(e),
                "react_process": {
                    "total_steps": len(response.react_steps),
                    "steps": [asdict(step) for step in response.react_steps]
                },
                "execution_time": time.time() - start_time
            }
            return json.dumps(error_response, ensure_ascii=False, indent=2)
    
    def _think_step(self, user_query: str, previous_steps: List[ReactStep], step_num: int) -> tuple:
        """
        思考步骤 - AI智能选择工具和放宽策略
        
        Args:
            user_query: 用户查询
            previous_steps: 之前的步骤
            step_num: 当前步骤号
            
        Returns:
            (thought, action, action_input) 元组
        """
        try:
            # 🔒 记录工具路径锁定状态
            if previous_steps and previous_steps[0].action != "FINISH":
                locked_tool = previous_steps[0].action
                logger.info(f"🔒 步骤{step_num}: 工具路径已锁定为 {locked_tool}")
                logger.info(f"📝 第1步选择: {locked_tool}, 当前步骤: {step_num}")
            else:
                logger.info(f"🆕 步骤{step_num}: 这是首次工具选择步骤")
            
            # 构建思考prompt
            if step_num == 1:
                # 第一步：AI首次分析选择工具
                prompt = self._build_first_step_prompt(user_query)
            else:
                # 检查上一步使用的工具类型
                last_action = previous_steps[-1].action if previous_steps else ""
                
                # 如果使用的是template_search_tool，直接结束，不需要重试
                if last_action == SimplifiedSearchTool.TEMPLATE_SEARCH.value:
                    logger.info("🚀 template_search_tool已完成，无需重试，直接结束")
                    return "template_search_tool已完成一次性ElasticSearch + LLM搜索，直接返回最佳结果", "FINISH", {}
                
                # 只有chapter_content_search_tool需要多轮优化
                prompt = self._build_continue_step_prompt(user_query, previous_steps)
            
            logger.info(f"🤔 AI开始思考步骤{step_num}")
            logger.info(f"📝 发送给AI的PROMPT:\n{prompt}")
            
            # 让AI进行思考
            response = self.llm_client.chat([{"role": "user", "content": prompt}])
            
            logger.info(f"🤖 AI原始回复:\n{response}")
            
            # 解析AI的思考结果
            thought, action, action_input = self._parse_thinking_response(response, previous_steps)
            
            logger.info(f"✅ 思考解析完成: action={action}")
            logger.info(f"📊 解析结果 - thought: {thought}")
            logger.info(f"📊 解析结果 - action: {action}")
            logger.info(f"📊 解析结果 - action_input: {action_input}")
            return thought, action, action_input
            
        except Exception as e:
            logger.error(f"❌ 思考步骤失败: {e}")
            # 默认回退到模版搜索
            return (
                f"思考出错，使用默认模版搜索策略: {str(e)}",
                SimplifiedSearchTool.TEMPLATE_SEARCH.value,
                {"queries": [user_query]}
            )
    
    def _build_first_step_prompt(self, user_query: str) -> str:
        """构建第一步思考prompt"""
        try:
            template = self.step_prompts.get('first_step_prompt', '')
            if not template:
                raise RuntimeError("first_step_prompt模板未找到")
            return template.format(user_query=user_query)
        except Exception as e:
            logger.error(f"❌ 构建第一步prompt失败: {e}")
            raise RuntimeError(f"无法构建第一步prompt: {e}")

    def _build_continue_step_prompt(self, user_query: str, previous_steps: List[ReactStep]) -> str:
        """构建后续步骤思考prompt"""
        try:
            # 分析上一步的结果
            last_step = previous_steps[-1]
            last_action = last_step.action
            last_observation = last_step.observation
            
            # 构建执行历史
            history = []
            for step in previous_steps:
                history.append(f"步骤{step.step_number}:")
                history.append(f"  思考: {step.thought}")
                history.append(f"  行动: {step.action}")
                history.append(f"  参数: {step.action_input}")
                history.append(f"  观察: {step.observation[:200]}...")
                history.append("")
            
            history_text = "\n".join(history)
            
            # 使用yaml模板
            template = self.step_prompts.get('continue_step_prompt', '')
            if not template:
                raise RuntimeError("continue_step_prompt模板未找到")
            
            return template.format(
                user_query=user_query,
                history_text=history_text,
                last_action=last_action,
                last_observation=last_observation[:300] + "..." if len(last_observation) > 300 else last_observation
            )
        except Exception as e:
            logger.error(f"❌ 构建后续步骤prompt失败: {e}")
            raise RuntimeError(f"无法构建后续步骤prompt: {e}")

    def _parse_thinking_response(self, response: str, previous_steps: List[ReactStep]) -> tuple:
        """
        解析AI的思考响应，强制执行工具路径排他性原则
        
        Args:
            response: AI的思考响应
            previous_steps: 之前的步骤
            
        Returns:
            (thought, action, action_input) 元组
        """
        try:
            thought = ""
            action = ""
            action_input = {}
            
            # 🔒 强制执行工具路径排他性检查
            locked_tool = None
            if previous_steps:
                # 获取第一步选择的工具
                first_tool = previous_steps[0].action
                if first_tool != "FINISH":
                    locked_tool = first_tool
                    logger.info(f"🔒 工具路径已锁定: {locked_tool} (步骤1选择)")
                    logger.info(f"🚫 禁止切换工具，强制使用: {locked_tool}")
            
            # 解析Thought
            if "Thought:" in response:
                thought_start = response.find("Thought:") + len("Thought:")
                if "Action:" in response:
                    thought_end = response.find("Action:")
                else:
                    thought_end = len(response)
                thought = response[thought_start:thought_end].strip()
            
            # 解析Action
            if "Action:" in response:
                action_start = response.find("Action:") + len("Action:")
                if "Action Input:" in response:
                    action_end = response.find("Action Input:")
                else:
                    action_end = response.find("\n", action_start)
                    if action_end == -1:
                        action_end = len(response)
                
                action = response[action_start:action_end].strip()
                
                # 处理结束指令
                if action.upper() == "FINISH":
                    return thought, "FINISH", {}
                
                # 🔒 工具路径排他性强制执行
                if locked_tool and action != locked_tool:
                    logger.warning(f"⚠️ AI尝试切换工具: {action} → {locked_tool}")
                    logger.info(f"🔒 强制覆盖为锁定工具: {locked_tool}")
                    original_action = action
                    action = locked_tool
                    thought = f"[系统强制执行工具路径排他性] 尝试切换到{original_action}被阻止，继续使用{locked_tool}。{thought}"
                
                # 验证action是否有效
                valid_actions = [tool.value for tool in SimplifiedSearchTool]
                if action not in valid_actions:
                    # 智能修正action
                    if any(keyword in action.lower() for keyword in ["template", "模板", "报告", "指南"]):
                        action = SimplifiedSearchTool.TEMPLATE_SEARCH.value
                    elif any(keyword in action.lower() for keyword in ["search_document", "document", "内容", "章节", "搜索", "背景", "历史"]):
                        action = SimplifiedSearchTool.SEARCH_DOCUMENT.value
                    else:
                        # 如果有前一步，保持一致性
                        if previous_steps:
                            action = previous_steps[0].action
                        else:
                            action = SimplifiedSearchTool.TEMPLATE_SEARCH.value  # 默认
            
            # 解析Action Input
            input_text = ""  # 初始化变量避免UnboundLocalError
            action_input = {}
            
            if "Action Input:" in response:
                input_start = response.find("Action Input:") + len("Action Input:")
                input_text = response[input_start:].strip()
                
                # 🎯 智能参数解析 - 支持多种格式
                try:
                    # 先尝试直接解析
                    action_input = json.loads(input_text)
                except json.JSONDecodeError:
                    # JSON解析失败，尝试提取JSON片段
                    logger.info("📝 JSON解析失败，尝试智能提取")
                    
                    # 尝试从复杂文本中提取JSON
                    import re
                    json_pattern = r'\{[^{}]*\}'
                    json_matches = re.findall(json_pattern, input_text)
                    
                    action_input = None
                    for match in json_matches:
                        try:
                            action_input = json.loads(match)
                            logger.info(f"✅ 成功提取JSON: {action_input}")
                            break
                        except json.JSONDecodeError:
                            continue
                    
                    # 如果仍然失败，智能构造参数
                    if not action_input:
                        logger.info("📝 智能构造默认参数")
                        # 使用当前用户查询作为默认查询
                        default_query = getattr(self, '_current_user_query', '用户查询')
                        logger.info(f"📝 获取到用户查询: '{default_query}'")
                        action_input = {
                            "query_text": default_query,
                            "content_type": "all", 
                            "project_name": "越秀公园",
                            "top_k": 5
                        }
                        logger.info(f"✅ 智能构造参数: {action_input}")
            
            # 初始化action_input如果为空
            if not action_input:
                action_input = {}
            
            # 🎯 智能参数提取和优化
            if action == SimplifiedSearchTool.TEMPLATE_SEARCH.value:
                # template_search_tool使用原有的queries参数格式
                if "queries" not in action_input or not action_input["queries"]:
                    action_input["queries"] = self._extract_intelligent_query(
                        getattr(self, '_current_user_query', ''), 
                        input_text
                    )
                    
            elif action == SimplifiedSearchTool.SEARCH_DOCUMENT.value:
                # search_document使用新的query_text参数格式
                current_user_query = getattr(self, '_current_user_query', '')
                logger.info(f"📝 当前用户查询: '{current_user_query}'")
                
                if "query_text" not in action_input or not action_input["query_text"]:
                    # 提取查询文本
                    if "queries" in action_input:
                        queries = action_input["queries"]
                        action_input["query_text"] = " ".join(queries) if isinstance(queries, list) else str(queries)
                    elif current_user_query:
                        # 优先使用用户原始查询
                        action_input["query_text"] = current_user_query
                        logger.info(f"✅ 使用用户原始查询: '{current_user_query}'")
                    else:
                        action_input["query_text"] = self._extract_intelligent_query_text(
                            current_user_query, 
                            input_text
                        )
                
                # 确保必要参数存在
                if "content_type" not in action_input:
                    action_input["content_type"] = "all"
                if "project_name" not in action_input:
                    action_input["project_name"] = "越秀公园"
                if "top_k" not in action_input:
                    action_input["top_k"] = 5
                
                # 移除不支持的参数
                unsupported_params = ["metadata_filter", "queries"]
                for param in unsupported_params:
                    if param in action_input:
                        logger.info(f"🗑️ 移除不支持的参数: {param}")
                        del action_input[param]
            
            logger.info(f"🎯 最终优化参数: {action_input}")
            
            # 如果没有解析到有效内容，使用智能默认值
            if not thought:
                thought = f"智能分析查询类型，选择{action}工具执行搜索"
            
            if not action:
                # 工具路径排他性：如果有锁定工具，必须使用
                if locked_tool:
                    action = locked_tool
                    logger.info(f"🔒 使用锁定工具: {action}")
                else:
                    action = SimplifiedSearchTool.TEMPLATE_SEARCH.value
                    logger.info(f"🆕 首次选择默认工具: {action}")
            
            return thought, action, action_input
            
        except Exception as e:
            logger.error(f"❌ 解析思考响应失败: {e}")
            
            # 异常情况下的工具路径排他性处理
            if previous_steps and previous_steps[0].action != "FINISH":
                locked_tool = previous_steps[0].action
                logger.error(f"❌ 解析失败，使用锁定工具: {locked_tool}")
                return (
                    f"[解析异常，强制使用锁定工具] {str(e)}",
                    locked_tool,
                    {"queries": ["解析失败的查询"]}
                )
            else:
                logger.error(f"❌ 解析失败，使用默认工具: {SimplifiedSearchTool.TEMPLATE_SEARCH.value}")
            return (
                f"解析失败，使用默认策略: {str(e)}",
                    SimplifiedSearchTool.TEMPLATE_SEARCH.value,
                    {"queries": ["解析失败的查询"]}
                )
    

    
    def _action_step(self, action: str, action_input: Dict[str, Any]) -> str:
        """
        执行行动步骤 - 简化为两个核心工具
        
        Args:
            action: 工具名称
            action_input: 工具参数
            
        Returns:
            观察结果
        """
        try:
            if action == "FINISH":
                return "React循环结束，准备生成最终答案"
            
            logger.info(f"⚡ 开始执行工具: {action}")
            logger.info(f"📝 工具参数详情: {json.dumps(action_input, ensure_ascii=False, indent=2)}")
            
            start_time = time.time()
            
            if action == SimplifiedSearchTool.TEMPLATE_SEARCH.value:
                result = self._execute_template_search(action_input)
            elif action == SimplifiedSearchTool.SEARCH_DOCUMENT.value:
                result = self._execute_chapter_content_search(action_input)
            else:
                result = f"❌ 未知工具: {action}"
            
            execution_time = time.time() - start_time
            logger.info(f"✅ 工具执行完成 - 耗时: {execution_time:.2f}秒")
            logger.info(f"📊 工具执行结果长度: {len(result)}字符")
            logger.info(f"🔍 工具执行结果预览: {result[:200]}...")
            
            return result
                
        except Exception as e:
            logger.error(f"❌ 工具执行异常: {action} - {e}")
            import traceback
            logger.error(f"❌ 异常堆栈:\n{traceback.format_exc()}")
            return f"工具执行失败: {str(e)}"
    
    def _init_elasticsearch(self):
        """初始化ElasticSearch客户端并刷新模板索引"""
        try:
            # ElasticSearch配置
            es_host = os.getenv("ELASTICSEARCH_HOST", "localhost")
            es_port = int(os.getenv("ELASTICSEARCH_PORT", "9200"))
            es_scheme = os.getenv("ELASTICSEARCH_SCHEME", "http")
            
            # 创建ES客户端 - 使用8.x推荐的连接方式
            es_url = f"{es_scheme}://{es_host}:{es_port}"
            self.es_client = Elasticsearch(
                hosts=[es_url],
                verify_certs=False,
                ssl_show_warn=False,
                request_timeout=30
            )
            
            # 测试连接
            if self.es_client.ping():
                logger.info("✅ ElasticSearch连接成功")
                
                # 每次初始化时都刷新索引
                self._refresh_template_index()
            else:
                logger.warning("⚠️ ElasticSearch连接失败")
                self.es_client = None
                
        except Exception as e:
            logger.error(f"❌ ElasticSearch初始化失败: {e}")
            self.es_client = None
    
    def _refresh_template_index(self):
        """刷新模板索引 - 每次系统初始化时运行"""
        try:
            logger.info("🔄 开始刷新模板索引...")
            
            # 1. 删除现有索引（如果存在）
            if self.es_client.indices.exists(index=self.es_index_name):
                logger.info(f"🗑️ 删除现有索引: {self.es_index_name}")
                self.es_client.indices.delete(index=self.es_index_name)
            
            # 2. 创建新索引
            logger.info(f"🔨 创建新索引: {self.es_index_name}")
            mapping = {
                "mappings": {
                    "properties": {
                        "guide_id": {"type": "keyword"},
                        "template_name": {
                            "type": "text",
                            "analyzer": "standard",
                            "search_analyzer": "standard"
                        },
                        "guide_summary": {
                            "type": "text",
                            "analyzer": "standard",
                            "search_analyzer": "standard"
                        },
                        "usage_frequency": {"type": "integer"},
                        "created_at": {"type": "date"}
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                }
            }
            
            self.es_client.indices.create(index=self.es_index_name, body=mapping)
            logger.info("✅ 索引创建完成")
                
            # 3. 从MySQL同步最新数据
            self._sync_latest_templates_to_es()
                
        except Exception as e:
            logger.error(f"❌ 刷新模板索引失败: {e}")
    
    def _sync_latest_templates_to_es(self):
        """从MySQL同步最新模板数据到ElasticSearch"""
        try:
            logger.info("📥 开始同步最新模板数据...")
            
            # 确保MySQL连接可用后再获取模板数据
            try:
                self._ensure_mysql_connection()
                templates = self._mysql_search_report_guides("", limit=1000)
            except Exception as mysql_error:
                logger.error(f"❌ MySQL连接失败，跳过数据同步: {mysql_error}")
                return
            
            if not templates:
                logger.warning("⚠️ MySQL中没有找到模板数据")
                return
            
            # 准备批量索引数据（只保留核心字段）
            actions = []
            for template in templates:
                doc = {
                    "guide_id": template.get("guide_id"),
                    "template_name": template.get("template_name", ""),
                    "guide_summary": template.get("guide_summary", ""),
                    "usage_frequency": template.get("usage_frequency", 0),
                    "created_at": template.get("created_at", "")
                }
                
                action = {
                    "_index": self.es_index_name,
                    "_id": template.get("guide_id"),
                    "_source": doc
                }
                actions.append(action)
            
            # 执行批量索引
            if actions:
                from elasticsearch.helpers import bulk
                bulk(self.es_client, actions)
                logger.info(f"✅ 成功同步 {len(actions)} 个模板到ElasticSearch")
                
                # 强制刷新索引，确保数据立即可搜索
                self.es_client.indices.refresh(index=self.es_index_name)
                logger.info("✅ 索引刷新完成，数据已可搜索")
            else:
                logger.warning("⚠️ 没有数据需要同步")
            
        except Exception as e:
            logger.error(f"❌ 同步最新模板数据失败: {e}")
    
    def _search_templates_with_es(self, query: str, size: int = 3) -> List[Dict[str, Any]]:
        """使用ElasticSearch搜索模板（召回阶段）- 只搜索核心字段"""
        try:
            # 构建双字段查询：只搜索template_name和guide_summary
            search_body = {
                "size": size,
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "template_name^2",    # 模板名称权重较高
                            "guide_summary^3"     # 指南总结权重最高（更重要）
                        ],
                        "type": "best_fields",
                        "fuzziness": "AUTO"
                    }
                },
                "sort": [
                    {"_score": {"order": "desc"}},
                    {"usage_frequency": {"order": "desc"}}
                ]
            }
            
            response = self.es_client.search(index=self.es_index_name, body=search_body)
            
            results = []
            for hit in response['hits']['hits']:
                result = hit['_source']
                result['es_score'] = hit['_score']
                results.append(result)
            
            logger.info(f"🔍 ElasticSearch召回 {len(results)} 个候选模板")
            return results
            
        except Exception as e:
            logger.error(f"❌ ElasticSearch搜索失败: {e}")
            return []
    
    def _llm_rerank_templates(self, query: str, candidates: List[Dict[str, Any]]) -> Optional[str]:
        """使用LLM对候选模板进行语义重排序，返回最佳匹配的report_guide内容"""
        if not candidates:
            return None
        
        try:
            # 从MySQL获取每个候选模板的完整report_guide内容
            enriched_candidates = []
            for candidate in candidates:
                guide_id = candidate.get('guide_id')
                if guide_id:
                    full_template = self._mysql_get_report_guide_by_id(guide_id)
                    if full_template:
                        enriched_candidates.append({
                            'guide_id': guide_id,
                            'template_name': full_template.get('template_name', ''),
                            'report_guide': full_template.get('report_guide', {}),
                            'es_score': candidate.get('es_score', 0)
                        })
            
            if not enriched_candidates:
                logger.warning("⚠️ 无法获取候选模板的完整数据")
                return None
            
            # 构建候选模板文本（只包含核心三个字段）
            candidates_text = ""
            for i, candidate in enumerate(enriched_candidates, 1):
                # 格式化report_guide内容，截取合理长度
                report_guide_str = str(candidate.get('report_guide', {}))
                if len(report_guide_str) > 500:
                    report_guide_preview = report_guide_str[:500] + "..."
                else:
                    report_guide_preview = report_guide_str
                
                candidates_text += f"{i}. 模板ID: {candidate.get('guide_id', '')}\n"
                candidates_text += f"   模板名称: {candidate.get('template_name', '')}\n"
                candidates_text += f"   报告指南内容: {report_guide_preview}\n\n"
            
            # 使用从yaml加载的prompt模板
            rerank_prompt = self.rerank_prompt_template.format(
                query=query,
                candidates_text=candidates_text
            )
            
            # 调用LLM
            response = self.llm_client.chat(
                messages=[{"role": "user", "content": rerank_prompt}]
            )
            
            # 解析LLM响应，获取选中的模板
            llm_choice = response.strip()
            try:
                choice_idx = int(llm_choice) - 1
                if 0 <= choice_idx < len(enriched_candidates):
                    # 返回LLM选择的模板的report_guide内容
                    selected = enriched_candidates[choice_idx]
                    logger.info(f"🤖 LLM选择模板: {selected.get('template_name')}")
                    
                    # 更新使用频率统计
                    try:
                        self._mysql_update_report_guide_usage(selected.get('guide_id'))
                    except:
                        pass  # 忽略统计更新错误
                    
                    return selected.get('report_guide')
                else:
                    logger.warning(f"⚠️ LLM返回无效选择: {llm_choice}")
                    # 返回第一个候选的report_guide
                    return enriched_candidates[0].get('report_guide') if enriched_candidates else None
            except ValueError:
                logger.warning(f"⚠️ LLM返回格式错误: {llm_choice}")
                # 返回第一个候选的report_guide
                return enriched_candidates[0].get('report_guide') if enriched_candidates else None
            
        except Exception as e:
            logger.error(f"❌ LLM重排序失败: {e}")
            # 回退：返回第一个候选的report_guide
            try:
                if candidates:
                    guide_id = candidates[0].get('guide_id')
                    if guide_id:
                        full_template = self._mysql_get_report_guide_by_id(guide_id)
                        return full_template.get('report_guide') if full_template else None
            except:
                pass
            return None
    
    def _execute_template_search(self, params: Dict[str, Any]) -> str:
        """
        执行模版搜索工具 - ElasticSearch召回 + LLM语义重排序
        
        Args:
            params: 包含queries(查询列表)
            
        Returns:
            搜索结果字符串
        """
        try:
            queries = params.get("queries", [])
            
            logger.info(f"🔍 模版搜索工具开始执行 - ElasticSearch + LLM重排序")
            logger.info(f"📝 查询列表: {queries}")
            
            # 合并所有查询为一个综合查询
            combined_query = " ".join(queries) if isinstance(queries, list) else str(queries)
            logger.info(f"🔗 合并查询: {combined_query}")
            
            # 尝试使用ElasticSearch + LLM重排序
            if self.es_client:
                logger.info("🚀 使用ElasticSearch + LLM重排序模式")
                
                # 第一阶段：ElasticSearch召回top3候选
                es_candidates = self._search_templates_with_es(combined_query, size=3)
                
                if es_candidates:
                    # 第二阶段：LLM语义重排序，直接返回最佳匹配的report_guide内容
                    best_report_guide = self._llm_rerank_templates(combined_query, es_candidates)
                    
                    if best_report_guide:
                        # 构建返回结果 - 只返回report_guide内容
                        result_text = f"✅ 模版搜索成功 (ElasticSearch + LLM重排序)，已找到最佳匹配的报告指南：\n\n"
                        result_text += f"📋 **报告指南内容**：\n{best_report_guide}\n"
                        
                        logger.info(f"✅ ElasticSearch + LLM模式成功找到最佳报告指南")
                        return result_text
                    else:
                        logger.warning("⚠️ LLM重排序未返回结果")
                else:
                    logger.info("📭 ElasticSearch未找到候选模板")
                
                # ElasticSearch模式未找到结果时的提示
                return f"❌ 模版搜索 (ElasticSearch + LLM重排序): 未找到匹配模板，建议尝试不同的查询词"
            
            else:
                # ElasticSearch不可用
                logger.error("❌ ElasticSearch不可用")
                return f"❌ 模版搜索失败: ElasticSearch服务不可用"
                
        except Exception as e:
            logger.error(f"❌ 模版搜索执行失败: {e}")
            return f"❌ 模版搜索失败: {str(e)}"
    

    

    

    

    

    
    def _deduplicate_template_results(self, results: List[Dict]) -> List[Dict]:
        """去重和排序模板结果"""
        seen = set()
        unique_results = []
        
        for result in results:
            template_name = result.get('template_name', '')
            if template_name and template_name not in seen:
                seen.add(template_name)
                unique_results.append(result)
        
        # 按匹配度和使用频率排序
        return sorted(unique_results, 
                     key=lambda x: (x.get('matched_score', 0), x.get('usage_frequency', 0)), 
                     reverse=True)
    
    def _unified_content_search(self, project_name: str, query: str, top_k: int = 5, chunk_type: str = "text_chunk") -> List[Dict]:
        """
        统一的搜索函数 - 支持文本、图片、表格的统一搜索逻辑
        
        Args:
            project_name: 项目名称
            query: 自然语言查询
            top_k: 返回结果数量
            chunk_type: 内容类型 ("text_chunk", "image_chunk", "table_chunk")
            
        Returns:
            搜索结果列表
        """
        logger.info(f"🔍 执行统一搜索: project={project_name}, query='{query}', type={chunk_type}, top_k={top_k}")
        
        try:
            # 1. 构建元数据过滤条件
            metadata_filter = {
                "type": chunk_type  # 修复：使用正确的字段名"type"而不是"chunk_type"
            }
            
            # 如果有项目名称，添加到过滤条件
            if project_name and project_name != "all":
                metadata_filter["project_name"] = project_name
            
                        # 2. 使用混合搜索引擎进行搜索
            search_results = self.hybrid_searcher.search(
                query=query,
                top_k=top_k,
                filters=metadata_filter,
                search_strategy="hybrid"
            )
            
            # 3. 转换为标准格式
            results = []
            for result in search_results:
                # 基础字段
                formatted_result = {
                    "content": result.content,
                    "metadata": result.metadata,
                    "similarity_score": result.vector_score,  # 修复：使用similarity_score而不是vector_score
                    "bm25_score": result.bm25_score,
                    "final_score": result.final_score
                }
                
                # 根据chunk_type添加特定字段
                if chunk_type == "text_chunk":
                    formatted_result["content_type"] = "text"
                elif chunk_type == "image_chunk":
                    formatted_result["content_type"] = "image"
                    formatted_result["image_path"] = result.metadata.get("image_path", "")
                    formatted_result["caption"] = result.metadata.get("caption", "")
                    formatted_result["page_context"] = result.metadata.get("page_context", "")
                    formatted_result["detailed_description"] = result.metadata.get("detailed_description", "")
                elif chunk_type == "table_chunk":
                    formatted_result["content_type"] = "table"
                    formatted_result["table_path"] = result.metadata.get("table_path", "")
                    formatted_result["caption"] = result.metadata.get("caption", "")
                    formatted_result["page_context"] = result.metadata.get("page_context", "")
                    formatted_result["detailed_description"] = result.metadata.get("detailed_description", "")
                
                results.append(formatted_result)
            
            logger.info(f"✅ {chunk_type}搜索完成，找到{len(results)}个结果")
            return results
            
        except Exception as e:
            logger.error(f"❌ {chunk_type}搜索失败: {e}")
            return []

    def _execute_chapter_content_search(self, params: Dict[str, Any]) -> str:
        """
        执行章节内容搜索 - 重构后的统一搜索逻辑
        
        Args:
            params: 包含以下参数:
                - query_text 或 query: 查询文本
                - project_name: 项目名称 (默认"all")
                - top_k: 返回结果数量 (默认5)
                - content_type: 内容类型 (默认"all")
                
        Returns:
            标准化的JSON响应
        """
        try:
            # 提取参数 - 支持多种参数格式
            query_text = params.get("query_text", "") or params.get("query", "")
            
            # 如果没有query_text，尝试从queries参数中提取
            if not query_text and "queries" in params:
                queries = params["queries"]
                if isinstance(queries, list) and queries:
                    query_text = " ".join(queries)
                elif isinstance(queries, str):
                    query_text = queries
                logger.info(f"✅ 从queries参数转换得到query_text: '{query_text}'")
            
            project_name = params.get("project_name", "all")
            top_k = params.get("top_k", 5)
            content_type = params.get("content_type", "all")
            
            # 调试日志
            logger.info(f"🔍 参数提取结果:")
            logger.info(f"   📝 原始参数: {params}")
            logger.info(f"   🔍 提取的query_text: '{query_text}'")
            logger.info(f"   📊 提取的project_name: '{project_name}'")
            logger.info(f"   📊 提取的top_k: {top_k}")
            logger.info(f"   🎯 提取的content_type: '{content_type}'")
            
            if not query_text:
                error_msg = f"查询文本不能为空。原始参数: {params}"
                logger.error(f"❌ {error_msg}")
                return json.dumps({
                    "status": "error",
                    "message": error_msg,
                    "retrieved_text": [],
                    "retrieved_image": [],
                    "retrieved_table": []
                }, ensure_ascii=False, indent=2)
            
            logger.info(f"🔍 开始章节内容搜索:")
            logger.info(f"   📝 项目: {project_name}")
            logger.info(f"   🔍 查询: {query_text}")
            logger.info(f"   📊 数量: {top_k}")
            logger.info(f"   🎯 类型: {content_type}")
            
            # 根据content_type决定搜索策略
            if content_type == "text":
                # 只搜索文本
                text_results = self._unified_content_search(project_name, query_text, top_k, "text_chunk")
                image_results = []
                table_results = []
                # 格式化结果
                formatted_text = [self._format_text_chunk(result) for result in text_results[:3]]  # 取top3
                formatted_image = []
                formatted_table = []
                
            elif content_type == "image":
                # 只搜索图片
                text_results = []
                image_results = self._unified_content_search(project_name, query_text, top_k, "image_chunk")
                table_results = []
                # 格式化结果
                formatted_text = []
                formatted_image = [self._format_image_chunk(result) for result in image_results[:3]]  # 取top3
                formatted_table = []
                
            elif content_type == "table":
                # 只搜索表格
                text_results = []
                image_results = []
                table_results = self._unified_content_search(project_name, query_text, top_k, "table_chunk")
                # 格式化结果
                formatted_text = []
                formatted_image = []
                formatted_table = [self._format_table_chunk(result) for result in table_results[:3]]  # 取top3
                
            else:
                # content_type="all": 搜索所有类型，每种类型返回top3
                logger.info("🔄 执行统一混合搜索 - 所有内容类型")
                
                # 1. 搜索所有类型的内容（每种类型取top_k，确保有足够的候选）
                # 搜索文本内容
                text_candidates = self._unified_content_search(project_name, query_text, top_k, "text_chunk")
                
                # 搜索图片内容  
                image_candidates = self._unified_content_search(project_name, query_text, top_k, "image_chunk")
                
                # 搜索表格内容
                table_candidates = self._unified_content_search(project_name, query_text, top_k, "table_chunk") 
                
                logger.info(f"📊 统一搜索候选结果: text({len(text_candidates)}) + image({len(image_candidates)}) + table({len(table_candidates)})")
                
                # 2. 每种类型取top3最佳结果（而不是全局top3）
                top_text_results = text_candidates[:3]  # 文本取top3
                top_image_results = image_candidates[:3]  # 图片取top3
                top_table_results = table_candidates[:3]  # 表格取top3
                
                # 3. 按类型格式化结果
                formatted_text = [self._format_text_chunk(result) for result in top_text_results]
                formatted_image = [self._format_image_chunk(result) for result in top_image_results]
                formatted_table = [self._format_table_chunk(result) for result in top_table_results]
                
                logger.info(f"🎯 最终结果分布: text({len(formatted_text)}) + image({len(formatted_image)}) + table({len(formatted_table)})")
                
                # 计算实际结果数量用于后续统计
                text_results = top_text_results
                image_results = top_image_results
                table_results = top_table_results
            
            # 生成响应
            response = {
                "status": "success",
                "message": f"search_document执行完成",
                "query_text": query_text,
                "project_name": project_name,
                "content_type": content_type,
                "total_results": len(text_results) + len(image_results) + len(table_results),
                "retrieved_text": formatted_text,
                "retrieved_image": formatted_image,
                "retrieved_table": formatted_table,
                "search_metadata": {
                    "search_timestamp": datetime.now().isoformat(),
                    "search_strategy": "统一混合搜索 (embedding + BM25)",
                    "top_k": top_k,
                    "project_filter": project_name != "all"
                }
            }
            
            logger.info(f"📊 搜索完成:")
            logger.info(f"   📝 文本片段: {len(formatted_text)}个")
            logger.info(f"   🖼️ 图片片段: {len(formatted_image)}个")
            logger.info(f"   📊 表格片段: {len(formatted_table)}个")
            
            return json.dumps(response, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"❌ 章节内容搜索失败: {e}")
            return json.dumps({
                "status": "error",
                "message": f"搜索失败: {str(e)}",
                "retrieved_text": [],
                "retrieved_image": [],
                "retrieved_table": []
            }, ensure_ascii=False, indent=2)
    
    def _format_text_chunk(self, result: Dict) -> Dict[str, Any]:
        """格式化文本块数据"""
        return {
            "content_id": result.get("content_id", ""),
            "content": result.get("content", ""),
            "chunk_type": result.get("chunk_type", "paragraph"),
            "document_id": result.get("document_id", ""),
            "chapter_id": result.get("chapter_id", ""),
            "chapter_title": result.get("chapter_title", ""),
            "paragraph_index": result.get("paragraph_index", 0),
            "position_in_chapter": result.get("position_in_chapter", 0),
            "word_count": result.get("word_count", len(result.get("content", ""))),
            "similarity_score": result.get("similarity_score", 0.0),
            "bm25_score": result.get("bm25_score", 0.0),
            "final_score": result.get("final_score", 0.0)  # 添加final_score字段
        }
    
    def _format_image_chunk(self, result: Dict) -> Dict[str, Any]:
        """格式化图片块数据"""
        image_path = result.get("image_path", "")
        return {
            "content_id": result.get("content_id", ""),
            "image_url": self._generate_minio_url(image_path),
            "image_path": image_path,
            "caption": result.get("caption", ""),
            "ai_description": result.get("ai_description", ""),
            "detailed_description": result.get("detailed_description", ""),
            "page_number": result.get("page_number", 0),
            "page_context": result.get("page_context", ""),
            "document_id": result.get("document_id", ""),
            "chapter_id": result.get("chapter_id", ""),
            "chapter_title": result.get("chapter_title", ""),
            "width": result.get("width", 0),
            "height": result.get("height", 0),
            "aspect_ratio": result.get("aspect_ratio", 0.0),
            "similarity_score": result.get("similarity_score", 0.0),
            "bm25_score": result.get("bm25_score", 0.0),  # 添加bm25_score字段
            "final_score": result.get("final_score", 0.0)  # 添加final_score字段
        }
    
    def _format_table_chunk(self, result: Dict) -> Dict[str, Any]:
        """格式化表格块数据"""
        table_path = result.get("table_path", "")
        return {
            "content_id": result.get("content_id", ""),
            "table_url": self._generate_minio_url(table_path),
            "table_path": table_path,
            "caption": result.get("caption", ""),
            "ai_description": result.get("ai_description", ""),
            "detailed_description": result.get("detailed_description", ""),
            "page_number": result.get("page_number", 0),
            "page_context": result.get("page_context", ""),
            "document_id": result.get("document_id", ""),
            "chapter_id": result.get("chapter_id", ""),
            "chapter_title": result.get("chapter_title", ""),
            "similarity_score": result.get("similarity_score", 0.0),
            "bm25_score": result.get("bm25_score", 0.0),  # 添加bm25_score字段
            "final_score": result.get("final_score", 0.0)  # 添加final_score字段
        }
    
    def _generate_minio_url(self, file_path: str) -> str:
        """
        生成MinIO访问URL
        
        Args:
            file_path: 文件路径
            
        Returns:
            完整的MinIO访问URL
        """
        if not file_path:
            return ""
            
        # 从环境变量获取MinIO配置
        minio_endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        minio_bucket = os.getenv("MINIO_BUCKET", "document-storage")
        
        # 确保路径格式正确
        clean_path = file_path.lstrip("/")
        
        return f"{minio_endpoint}/{minio_bucket}/{clean_path}"
    

    

    

    
    def _format_structured_response_for_display(self, structured_response: Dict[str, Any]) -> str:
        """
        将结构化响应转换为用户友好的展示格式
        
        Args:
            structured_response: 标准化的JSON响应
            
        Returns:
            用户友好的展示文本，包含JSON数据
        """
        try:
            status = structured_response.get("status", "unknown")
            message = structured_response.get("message", "")
            
            if status == "error":
                return f"❌ {message}\n```json\n{json.dumps(structured_response, ensure_ascii=False, indent=2)}\n```"
            
            elif status == "no_results":
                display_message = "未找到相关内容，建议尝试不同的查询词或使用模版搜索"
                
                return f"❌ {display_message}\n```json\n{json.dumps(structured_response, ensure_ascii=False, indent=2)}\n```"
            
            else:  # success
                # 生成摘要
                text_count = len(structured_response.get("retrieved_text", []))
                image_count = len(structured_response.get("retrieved_image", []))
                table_count = len(structured_response.get("retrieved_table", []))
                
                summary = f"✅ 章节内容搜索成功\n"
                summary += f"📊 找到内容: 文本{text_count}个, 图片{image_count}个, 表格{table_count}个\n\n"
                
                # 显示部分文本内容预览
                if text_count > 0:
                    summary += "📝 文本内容预览:\n"
                    for i, text_item in enumerate(structured_response["retrieved_text"][:3], 1):
                        content_preview = text_item.get("content", "")[:150]
                        if len(text_item.get("content", "")) > 150:
                            content_preview += "..."
                        summary += f"   {i}. {content_preview}\n"
                    
                    if text_count > 3:
                        summary += f"   ... 还有{text_count - 3}个文本片段\n"
                    summary += "\n"
                
                # 显示图片信息
                if image_count > 0:
                    summary += f"🖼️ 图片内容: {image_count}个相关图片\n\n"
                
                # 显示表格信息 
                if table_count > 0:
                    summary += f"📊 表格内容: {table_count}个相关表格\n\n"
                
                summary += "📋 完整结构化数据:\n"
                summary += f"```json\n{json.dumps(structured_response, ensure_ascii=False, indent=2)}\n```"
                
                return summary
                
        except Exception as e:
            logger.error(f"❌ 格式化展示失败: {e}")
            return f"❌ 格式化失败: {str(e)}\n```json\n{json.dumps(structured_response, ensure_ascii=False, indent=2)}\n```"
    

    
    def _should_finish(self, thought: str, action: str, observation: str, step_num: int) -> bool:
        """判断是否应该结束React循环"""
        # 如果收到结束指令
        if action == "FINISH":
            return True
        
        # 如果达到最大步骤数
        if step_num >= self.max_steps:
            return True
        
        return False
    
    def _generate_final_answer(self, user_query: str, react_steps: List[ReactStep]) -> str:
        """生成最终答案 - 根据工具类型返回对应格式"""
        try:
            if not react_steps:
                logger.warning("⚠️ 没有React步骤，返回空结果")
                return json.dumps({
                    "retrieved_text": [],
                    "retrieved_image": [],
                    "retrieved_table": []
                }, ensure_ascii=False, indent=2)
            
            # 检测使用的工具类型（基于第一步的action）
            first_tool = react_steps[0].action
            logger.info(f"🔍 检测到使用的工具: {first_tool}")
            
            if first_tool == SimplifiedSearchTool.TEMPLATE_SEARCH.value:
                # template_search_tool: 返回模板文本内容
                return self._extract_template_content(react_steps)
                
            elif first_tool == SimplifiedSearchTool.SEARCH_DOCUMENT.value:
                # search_document: 合并所有步骤的JSON结果
                return self._merge_document_search_results(react_steps)
                
            else:
                logger.warning(f"⚠️ 未知工具类型: {first_tool}")
                return json.dumps({
                    "retrieved_text": [],
                    "retrieved_image": [],
                    "retrieved_table": []
                }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"❌ 生成最终答案失败: {e}")
            # 返回空的结构化结果
            empty_result = {
                "retrieved_text": [],
                "retrieved_image": [],
                "retrieved_table": []
            }
            return json.dumps(empty_result, ensure_ascii=False, indent=2)
    
    def _deduplicate_results(self, results: List[Dict], key_field: str) -> List[Dict]:
        """根据指定字段去重结果"""
        seen = set()
        unique_results = []
        
        for result in results:
            identifier = result.get(key_field, "") or result.get("content_id", "") 
            if identifier and identifier not in seen:
                seen.add(identifier)
                # 移除技术细节字段，只保留用户需要的信息
                cleaned_result = self._clean_result_for_user(result)
                unique_results.append(cleaned_result)
                
        return unique_results[:10]  # 限制最多10个结果
    
    def _clean_result_for_user(self, result: Dict) -> Dict:
        """清洗结果，移除技术细节，只保留用户关心的信息"""
        # 定义需要保留的字段
        if "image_path" in result or "image_url" in result:
            # 图片结果
            return {
                "content_id": result.get("content_id", ""),
                "image_url": result.get("image_url", ""),
                "caption": result.get("caption", ""),
                "ai_description": result.get("ai_description", ""),
                "chapter_title": result.get("chapter_title", ""),
                "page_number": result.get("page_number", 0)
            }
        elif "table_path" in result or "table_url" in result:
            # 表格结果
            return {
                "content_id": result.get("content_id", ""),
                "table_url": result.get("table_url", ""),
                "caption": result.get("caption", ""),
                "ai_description": result.get("ai_description", ""),
                "chapter_title": result.get("chapter_title", ""),
                "page_number": result.get("page_number", 0)
            }
        else:
            # 文本结果
            return {
                "content_id": result.get("content_id", ""),
                "content": result.get("content", ""),
                "chapter_title": result.get("chapter_title", ""),
                "word_count": result.get("word_count", 0)
            }
    
    def _extract_intelligent_query(self, user_query: str, input_text: str) -> List[str]:
        """
        智能提取查询内容，支持多种输入格式（用于template_search_tool）
        
        Args:
            user_query: 原始用户查询
            input_text: Action Input中的文本
            
        Returns:
            优化后的查询列表
        """
        try:
            # 1. 优先使用用户原始查询
            if user_query and user_query.strip():
                primary_query = user_query.strip()
            else:
                primary_query = None
            
            # 2. 从input_text中提取有效查询
            if input_text:
                # 移除常见的JSON包装
                clean_input = input_text.strip()
                
                # 移除引号包装
                if clean_input.startswith('"') and clean_input.endswith('"'):
                    clean_input = clean_input[1:-1]
                elif clean_input.startswith("'") and clean_input.endswith("'"):
                    clean_input = clean_input[1:-1]
                
                # 提取第一行作为主要查询
                lines = clean_input.split('\n')
                if lines and lines[0].strip():
                    secondary_query = lines[0].strip()
                else:
                    secondary_query = None
            else:
                secondary_query = None
            
            # 3. 智能组合查询
            queries = []
            
            if primary_query:
                queries.append(primary_query)
            
            if secondary_query and secondary_query != primary_query:
                queries.append(secondary_query)
            
            # 4. 确保有查询内容
            if not queries:
                queries = ["智能搜索查询"]
            
            logger.info(f"🎯 智能查询提取结果: {queries}")
            return queries
            
        except Exception as e:
            logger.error(f"❌ 智能查询提取失败: {e}")
            return [user_query if user_query else "默认查询"]
    
    def _extract_intelligent_query_text(self, user_query: str, input_text: str) -> str:
        """
        智能提取查询文本，支持多种输入格式（用于search_document）
        
        Args:
            user_query: 原始用户查询
            input_text: Action Input中的文本
            
        Returns:
            优化后的查询文本
        """
        try:
            # 1. 优先使用用户原始查询
            if user_query and user_query.strip():
                return user_query.strip()
            
            # 2. 从input_text中提取有效查询
            if input_text:
                # 移除常见的JSON包装
                clean_input = input_text.strip()
                
                # 移除引号包装
                if clean_input.startswith('"') and clean_input.endswith('"'):
                    clean_input = clean_input[1:-1]
                elif clean_input.startswith("'") and clean_input.endswith("'"):
                    clean_input = clean_input[1:-1]
                
                # 提取第一行作为主要查询
                lines = clean_input.split('\n')
                if lines and lines[0].strip():
                    return lines[0].strip()
            
            # 3. 默认值
            return "智能文档搜索"
            
        except Exception as e:
            logger.error(f"❌ 智能查询文本提取失败: {e}")
            return user_query if user_query else "默认查询"
    

    
    def _extract_template_content(self, react_steps: List[ReactStep]) -> str:
        """提取template_search_tool的模板内容"""
        try:
            # 查找最后一个包含模板内容的步骤
            template_content = ""
            
            for step in react_steps:
                if step.action == SimplifiedSearchTool.TEMPLATE_SEARCH.value:
                    # 查找包含模板内容的observation
                    if "✅" in step.observation and ("模版搜索成功" in step.observation or "最佳匹配" in step.observation):
                        # 提取报告指南内容
                        if "📋 **报告指南内容**：" in step.observation:
                            content_start = step.observation.find("📋 **报告指南内容**：") + len("📋 **报告指南内容**：")
                            content = step.observation[content_start:].strip()
                            if content:
                                template_content = content
                                logger.info(f"✅ 提取到模板内容，长度: {len(template_content)}字符")
                                break
            
            if template_content:
                return template_content
            else:
                logger.warning("⚠️ 未找到模板内容，返回未找到信息")
                return "未找到匹配的模板内容"
                
        except Exception as e:
            logger.error(f"❌ 提取模板内容失败: {e}")
            return "模板内容提取失败"
    
    def _merge_document_search_results(self, react_steps: List[ReactStep]) -> str:
        """合并search_document的JSON结果"""
        try:
            all_text_results = []
            all_image_results = []
            all_table_results = []
            
            for step in react_steps:
                if step.action == SimplifiedSearchTool.SEARCH_DOCUMENT.value:
                    try:
                        # 直接解析observation中的JSON（现在是纯JSON格式）
                        step_data = json.loads(step.observation)
                        
                        logger.info(f"📊 成功解析步骤{step.step_number}的JSON数据")
                        
                        # 合并搜索结果
                        if "retrieved_text" in step_data:
                            all_text_results.extend(step_data["retrieved_text"])
                            logger.info(f"🔤 添加{len(step_data['retrieved_text'])}个文本结果")
                        if "retrieved_image" in step_data:
                            all_image_results.extend(step_data["retrieved_image"])
                            logger.info(f"🖼️ 添加{len(step_data['retrieved_image'])}个图片结果")
                        if "retrieved_table" in step_data:
                            all_table_results.extend(step_data["retrieved_table"])
                            logger.info(f"📊 添加{len(step_data['retrieved_table'])}个表格结果")
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"步骤{step.step_number}的JSON解析失败: {e}")
                        logger.debug(f"观察内容预览: {step.observation[:200]}...")
                        continue
            
            # 去重和清洗结果
            unique_text_results = self._deduplicate_results(all_text_results, "content")
            unique_image_results = self._deduplicate_results(all_image_results, "image_path")
            unique_table_results = self._deduplicate_results(all_table_results, "table_path")
            
            # 生成最终的简洁JSON答案
            final_json = {
                "retrieved_text": unique_text_results,
                "retrieved_image": unique_image_results,
                "retrieved_table": unique_table_results
            }
            
            logger.info(f"📊 最终答案统计: 文本{len(unique_text_results)}个, "
                       f"图片{len(unique_image_results)}个, 表格{len(unique_table_results)}个")
            
            return json.dumps(final_json, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"❌ 合并文档搜索结果失败: {e}")
            return json.dumps({
                "retrieved_text": [],
                "retrieved_image": [],
                "retrieved_table": []
            }, ensure_ascii=False, indent=2)

    def _init_mysql_connection(self):
        """初始化内置MySQL连接"""
        try:
            self.mysql_connection = None
            self.mysql_config = {
                'host': os.getenv('MYSQL_HOST', 'localhost'),
                'port': int(os.getenv('MYSQL_PORT', 3306)),
                'user': os.getenv('MYSQL_USER', 'root'),
                'password': os.getenv('MYSQL_PASSWORD', ''),
                'database': os.getenv('MYSQL_DATABASE', 'mysql_templates'),
                'charset': os.getenv('MYSQL_CHARSET', 'utf8mb4'),
                'autocommit': True,
                'connect_timeout': 60,  # 增加连接超时
                'read_timeout': 60,     # 增加读取超时
                'write_timeout': 60     # 增加写入超时
            }
            
            # 尝试连接MySQL
            self._create_mysql_connection()
            
        except Exception as e:
            logger.error(f"❌ MySQL连接初始化失败: {e}")
            self.mysql_connection = None

    def _create_mysql_connection(self):
        """创建MySQL连接"""
        try:
            self.mysql_connection = pymysql.connect(**self.mysql_config)
            logger.info(f"✅ MySQL连接成功: {self.mysql_config['database']}")
        except Exception as e:
            logger.error(f"❌ MySQL连接失败: {e}")
            self.mysql_connection = None
            raise

    def _ensure_mysql_connection(self):
        """确保MySQL连接可用，如果断开则重连"""
        try:
            if self.mysql_connection is None:
                logger.info("🔄 MySQL连接为空，尝试重新连接...")
                self._create_mysql_connection()
                return
            
            # 检查连接是否仍然活跃
            self.mysql_connection.ping(reconnect=False)
            
        except Exception as e:
            logger.warning(f"⚠️ MySQL连接检查失败: {e}")
            logger.info("🔄 尝试重新建立MySQL连接...")
            try:
                self._create_mysql_connection()
                logger.info("✅ MySQL重连成功")
            except Exception as reconnect_error:
                logger.error(f"❌ MySQL重连失败: {reconnect_error}")
                self.mysql_connection = None
                raise

    def _mysql_search_report_guides(self, query: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
        """内置方法：从MySQL搜索报告指南模板"""
        try:
            # 使用连接管理器的上下文管理器
            with mysql_manager.get_cursor() as cursor:
                # 构建搜索SQL（包含guide_summary字段）
                base_sql = """
                SELECT rgt.guide_id, rgt.document_type_id, rgt.template_name, rgt.project_category,
                       rgt.target_objects, rgt.report_guide, rgt.guide_summary, rgt.usage_frequency, rgt.created_at,
                       dt.type_name, dt.category
                FROM report_guide_templates rgt
                LEFT JOIN document_types dt ON rgt.document_type_id = dt.type_id
                WHERE 1=1
                """
                
                params = []
                
                # 基础查询过滤
                if query:
                    base_sql += " AND (rgt.template_name LIKE %s OR rgt.project_category LIKE %s OR dt.type_name LIKE %s)"
                    search_pattern = f"%{query}%"
                    params.extend([search_pattern, search_pattern, search_pattern])
                
                base_sql += " ORDER BY rgt.usage_frequency DESC, rgt.created_at DESC LIMIT %s"
                params.append(limit)
                
                cursor.execute(base_sql, params)
                results = cursor.fetchall()
                
                report_guides = []
                for result in results:
                    guide = {
                        'guide_id': result[0],
                        'document_type_id': result[1],
                        'template_name': result[2],
                        'project_category': result[3],
                        'target_objects': json.loads(result[4]) if result[4] else [],
                        'report_guide': json.loads(result[5]) if result[5] else {},
                        'guide_summary': result[6] if result[6] else "",
                        'usage_frequency': result[7],
                        'created_at': result[8].isoformat() if result[8] else "",
                        'document_type_name': result[9],
                        'document_category': result[10]
                    }
                    report_guides.append(guide)
                
                logger.info(f"从MySQL搜索到 {len(report_guides)} 个报告指南")
                return report_guides
            
        except Exception as e:
            logger.error(f"MySQL搜索报告指南失败: {e}")
            return []

    def _mysql_get_report_guide_by_id(self, guide_id: str) -> Optional[Dict[str, Any]]:
        """内置方法：根据ID获取报告指南"""
        try:
            # 使用连接管理器的上下文管理器
            with mysql_manager.get_cursor() as cursor:
                sql = """
                SELECT rgt.guide_id, rgt.document_type_id, rgt.template_name, rgt.project_category,
                       rgt.target_objects, rgt.report_guide, rgt.guide_summary, rgt.usage_frequency, rgt.created_at,
                       dt.type_name, dt.category
                FROM report_guide_templates rgt
                LEFT JOIN document_types dt ON rgt.document_type_id = dt.type_id
                WHERE rgt.guide_id = %s
                """
                
                cursor.execute(sql, (guide_id,))
                result = cursor.fetchone()
                
                if result:
                    return {
                        'guide_id': result[0],
                        'document_type_id': result[1],
                        'template_name': result[2],
                        'project_category': result[3],
                        'target_objects': json.loads(result[4]) if result[4] else [],
                        'report_guide': json.loads(result[5]) if result[5] else {},
                        'guide_summary': result[6] if result[6] else "",
                        'usage_frequency': result[7],
                        'created_at': result[8].isoformat() if result[8] else "",
                        'document_type_name': result[9],
                        'document_category': result[10]
                    }
                
                return None
            
        except Exception as e:
            logger.error(f"根据ID获取报告指南失败: {e}")
            return None

    def _mysql_update_report_guide_usage(self, guide_id: str) -> bool:
        """内置方法：更新报告指南使用频率"""
        try:
            # 使用连接管理器的上下文管理器
            with mysql_manager.get_cursor() as cursor:
                sql = """
                UPDATE report_guide_templates 
                SET usage_frequency = usage_frequency + 1, last_updated = NOW()
                WHERE guide_id = %s
                """
                
                cursor.execute(sql, (guide_id,))
                
                if cursor.rowcount > 0:
                    logger.info(f"成功更新报告指南 {guide_id} 的使用频率")
                    return True
                else:
                    logger.warning(f"报告指南 {guide_id} 不存在")
                    return False
            
        except Exception as e:
            logger.error(f"更新报告指南使用频率失败: {e}")
            return False

    def close(self):
        """关闭所有连接"""
        try:
            if hasattr(self, 'mysql_connection') and self.mysql_connection:
                self.mysql_connection.close()
                logger.info("MySQL连接已关闭")
        except Exception as e:
            logger.error(f"关闭MySQL连接失败: {e}")

    def __del__(self):
        """析构函数，确保连接被关闭"""
        self.close()

# 为了向后兼容，保留原接口
class ReactRAGAgent(SimplifiedReactAgent):
    """向后兼容的React RAG Agent"""
    
    def __init__(self, storage_dir: str = None, templates_db: str = None):
        super().__init__(storage_dir)
    
    def process_input(self, user_query: str) -> str:
        """处理输入（向后兼容）"""
        return self.process_query(user_query)
    
    def query(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        """查询方法（向后兼容）"""
        result_json = self.process_query(user_query)
        result_data = json.loads(result_json)
        
        # 转换为AgentResponse格式
        react_steps = []
        if "react_process" in result_data and "steps" in result_data["react_process"]:
            for step_data in result_data["react_process"]["steps"]:
                react_step = ReactStep(
                    step_number=step_data["step_number"],
                    thought=step_data["thought"],
                    action=step_data["action"],
                    action_input=step_data["action_input"],
                    observation=step_data["observation"],
                    timestamp=step_data["timestamp"]
                )
                react_steps.append(react_step)
        
        return AgentResponse(
            success=result_data.get("status") == "success",
            final_answer=result_data.get("final_answer", ""),
            react_steps=react_steps,
            total_steps=result_data.get("react_process", {}).get("total_steps", 0),
            execution_time=result_data.get("execution_time", 0.0),
            metadata=result_data.get("metadata", {})
        )