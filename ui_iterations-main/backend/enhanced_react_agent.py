"""
Enhanced ReAct Agent with Memory
增强版ReAct Agent，支持记忆功能，所有请求都通过ReAct循环处理
"""
import re
import json
import pickle
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from colorama import init, Fore, Style
from dataclasses import dataclass

from deepseek_client import DeepSeekClient
from tools import ToolRegistry, create_core_tool_registry
from prompts.loader import get_prompt_loader
# 移除 log_thought 导入，现在使用直接 print + ThoughtLogger 拦截

# 初始化colorama
init(autoreset=True)

@dataclass
class AgentResult:
    """Agent执行结果"""
    response: str
    thinking_process: List[Dict[str, Any]]
    total_iterations: int
    success: bool = True

class MemoryManager:
    """记忆管理器"""
    
    def __init__(self, memory_file: str = "agent_memory.pkl"):
        self.memory_file = memory_file
        self.conversation_history: List[Dict[str, Any]] = []
        self.session_summaries: List[Dict[str, Any]] = []
        self.load_memory()
    
    def load_memory(self):
        """加载记忆"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'rb') as f:
                    data = pickle.load(f)
                    self.conversation_history = data.get("conversation_history", [])
                    self.session_summaries = data.get("session_summaries", [])
                    print(f"加载记忆: {len(self.conversation_history)} 条对话, {len(self.session_summaries)} 个会话摘要")
            except Exception as e:
                print(f"加载记忆失败: {e}")
                self.conversation_history = []
                self.session_summaries = []
    
    def save_memory(self):
        """保存记忆"""
        try:
            data = {
                "conversation_history": self.conversation_history,
                "session_summaries": self.session_summaries
            }
            with open(self.memory_file, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"保存记忆失败: {e}")
    
    def add_session(self, problem: str, solution: str, conversation: List[Dict[str, Any]]):
        """添加会话"""
        session = {
            "timestamp": datetime.now().isoformat(),
            "problem": problem,
            "solution": solution,
            "conversation": conversation,
            "tokens_used": sum(len(msg["content"]) for msg in conversation)
        }
        self.session_summaries.append(session)
        self.conversation_history.extend(conversation)
        
        # 限制记忆大小
        if len(self.session_summaries) > 100:
            self.session_summaries = self.session_summaries[-50:]
        if len(self.conversation_history) > 1000:
            self.conversation_history = self.conversation_history[-500:]
        
        self.save_memory()
    
    def get_relevant_context(self, problem: str, max_sessions: int = 3) -> str:
        """获取相关上下文"""
        if not self.session_summaries:
            return ""
        
        # 简单的关键词匹配（可以改进为语义搜索）
        relevant_sessions = []
        problem_keywords = set(problem.lower().split())
        
        for session in self.session_summaries:
            session_keywords = set(session["problem"].lower().split())
            overlap = len(problem_keywords & session_keywords)
            if overlap > 0:
                relevant_sessions.append((overlap, session))
        
        # 按相关性排序
        relevant_sessions.sort(key=lambda x: x[0], reverse=True)
        
        context = ""
        for i, (score, session) in enumerate(relevant_sessions[:max_sessions]):
            context += f"历史问题{i+1}: {session['problem']}\n解决方案: {session['solution']}\n\n"
        
        return context
    
    def get_memory_summary(self) -> str:
        """获取记忆摘要"""
        if not self.session_summaries:
            return "暂无记忆记录"
        
        total_sessions = len(self.session_summaries)
        total_tokens = sum(session.get("tokens_used", 0) for session in self.session_summaries)
        recent_session = self.session_summaries[-1]
        
        return f"""
记忆统计:
- 总会话数: {total_sessions}
- 总Token使用量: {total_tokens}
- 最近问题: {recent_session['problem'][:100]}...
- 最近时间: {recent_session['timestamp']}
        """

class ProjectStateManager:
    """项目状态管理器 - 文件持久化存储"""
    
    def __init__(self, state_file: str = "project_states.pkl"):
        self.state_file = state_file
        self.project_states: Dict[str, Dict[str, Any]] = {}
        self.load_states()
    
    def load_states(self):
        """加载项目状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'rb') as f:
                    self.project_states = pickle.load(f)
                    print(f"📁 加载项目状态: {len(self.project_states)} 个项目")
            except Exception as e:
                print(f"❌ 加载项目状态失败: {e}")
                self.project_states = {}
    
    def save_states(self):
        """保存项目状态"""
        try:
            with open(self.state_file, 'wb') as f:
                pickle.dump(self.project_states, f)
        except Exception as e:
            print(f"❌ 保存项目状态失败: {e}")
    
    def get_project_state(self, project_id: str) -> Dict[str, Any]:
        """获取项目状态"""
        if project_id not in self.project_states:
            from datetime import datetime
            self.project_states[project_id] = {
                "pdf_files_parsed": [],
                "documents_generated": [],
                "created_time": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat()
            }
        return self.project_states[project_id]
    
    def update_project_state(self, project_id: str, **updates):
        """更新项目状态"""
        from datetime import datetime
        state = self.get_project_state(project_id)
        state.update(updates)
        state["last_activity"] = datetime.now().isoformat()
        self.project_states[project_id] = state
        self.save_states()
    
    def get_project_context_for_prompt(self, project_id: str) -> str:
        """获取项目状态上下文，用于prompt"""
        if not project_id:
            return "📁 当前项目状态: 未指定项目"
            
        state = self.get_project_state(project_id)
        pdf_files = state.get("pdf_files_parsed", [])
        documents = state.get("documents_generated", [])
        
        context = f"📁 当前项目状态:\n\n"
        context += f"项目ID: {project_id}\n"
        context += f"PDF解析状态: {'已完成 ✅' if pdf_files else '未完成 ❌'}\n"
        
        if pdf_files:
            context += f"已解析PDF文件: {len(pdf_files)}个\n"
            for pdf in pdf_files[-3:]:  # 只显示最近3个
                context += f"  - {pdf.get('name', 'unknown')} ({pdf.get('time', '未知时间')[:10]})\n"
        
        context += f"生成文档数量: {len(documents)}个\n"
        if documents:
            latest_doc = documents[-1]
            context += f"最新文档: {latest_doc.get('title', 'unknown')} ({latest_doc.get('time', '未知时间')[:10]})\n"
        
        context += f"最后活动: {state.get('last_activity', '未知')[:16]}\n"
        
        return context

class EnhancedReActAgent:
    """增强版ReAct Agent"""
    
    def __init__(
        self,
        deepseek_client: DeepSeekClient,
        tool_registry: ToolRegistry,
        max_iterations: int = 10,
        verbose: bool = True,
        enable_memory: bool = True
    ):
        self.client = deepseek_client
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations
        self.verbose = verbose
        
        # 记忆管理
        self.memory_manager = MemoryManager() if enable_memory else None
        
        # 📁 项目状态管理器 - 文件持久化存储
        self.project_state_manager = ProjectStateManager()
        
        # 当前状态
        self.current_problem = None
        self.conversation_history = []
        
        # 构建系统提示词
        self.system_prompt = self._build_system_prompt()
        
        if self.verbose:
            print(f"Enhanced ReAct Agent 初始化完成")
            print(f"可用工具: {len(self.tool_registry.tools)}")
            if self.memory_manager:
                print(f"记忆功能: 启用 ({len(self.memory_manager.session_summaries)} 个会话)")
            print(f"📁 项目状态管理: 已初始化 ({len(self.project_state_manager.project_states)} 个项目)")
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        try:
            from prompts.loader import PromptLoader
            prompt_loader = PromptLoader()
            project_context = getattr(self.tool_registry, 'project_context', None)
            
            # 传递agent实例给prompt loader以获取项目状态
            system_prompt = prompt_loader.get_system_prompt(
                project_context=project_context,
                agent=self  # 🆕 传递agent实例
            )
            
            return system_prompt
            
        except Exception as e:
            print(f"❌ 构建系统提示词失败: {e}")
            return "你是一个智能助手，请帮助用户解决问题。"
    
    def _parse_response(self, response: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """解析LLM响应 - 修复多轮生成问题"""
        
        # 🔧 关键修复：检测LLM是否一次性生成了多轮对话
        observation_count = len(re.findall(r'Observation:', response))
        if observation_count > 0:
            print(f"⚠️ 检测到LLM生成了假的Observation ({observation_count}个)，这是错误的行为！")
            print("🔧 将只解析第一轮的Thought和Action，忽略后续伪造内容")
            
            # 分割成行，只处理第一个完整的Thought+Action周期
            lines = response.split('\n')
            first_cycle_lines = []
            found_first_action = False
            
            for line in lines:
                line = line.strip()
                first_cycle_lines.append(line)
                
                # 如果遇到Observation，说明LLM开始生成假内容，停止解析
                if line.startswith('Observation:'):
                    print("🛑 遇到伪造的Observation，停止解析")
                    break
                    
                # 如果找到第一个Action Input后，停止收集
                if found_first_action and (line.startswith('Thought:') or line.startswith('Action:') or line.startswith('Final Answer:')):
                    if not line.startswith('Action Input:'):
                        break
                        
                if line.startswith('Action:'):
                    found_first_action = True
            
            # 重新组合第一周期的响应
            response = '\n'.join(first_cycle_lines)
            print(f"🔧 清理后的响应: {response}")
        
        # 标准解析逻辑
        # 查找 Thought
        thought_match = re.search(r'Thought:\s*(.*?)(?=\n(?:Action|Final Answer)|\Z)', response, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else None
        
        # 查找 Final Answer - 但只在没有Action时才认为是最终答案
        final_answer_match = re.search(r'Final Answer:\s*(.*?)(?:\n|$)', response, re.DOTALL)
        action_exists = re.search(r'Action:\s*(\w+)', response)
        
        if final_answer_match and not action_exists:
            # 真正的最终答案（没有伴随Action）
            return thought, None, final_answer_match.group(1).strip()
        
        # 查找 Action（优先执行Action）
        action_match = re.search(r'Action:\s*(\w+)', response)
        action = action_match.group(1) if action_match else None
        
        # 查找 Action Input
        action_input_match = re.search(r'Action Input:\s*(.*?)(?=\n(?:Thought|Action|Final Answer|Observation)|\Z)', response, re.DOTALL)
        action_input = action_input_match.group(1).strip() if action_input_match else None
        
        return thought, action, action_input
    
    def analyze_tool_error(self, action: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        简化错误分析，让主Agent自己决策
        
        Args:
            action: 工具名称
            result: 工具执行结果
            
        Returns:
            基础错误信息，供主Agent分析
        """
        # 🧠 简化错误处理，让主Agent自己分析
        return {
            "tool_name": action,
            "error_type": result.get("error_type", "unknown_error"),
            "error_message": result.get("error_message", result.get("error", "未知错误")),
            "http_status": result.get("http_status"),
            "api_url": result.get("api_url"),
            "sent_params": result.get("sent_params"),
            "tool_parameters": result.get("tool_parameters"),
            "instruction": result.get("instruction", "请分析此错误并决定如何处理"),
            "raw_result": result
        }
    
    def format_error_for_ai(self, action: str, result: Dict[str, Any], error_analysis: Dict[str, Any]) -> str:
        """
        简化错误格式化，让主Agent自己分析
        
        Args:
            action: 工具名称
            result: 工具执行结果
            error_analysis: 错误分析结果
            
        Returns:
            格式化的错误信息供主Agent分析
        """
        # 🧠 简化错误格式化，让主Agent自己分析
        formatted_error = {
            "success": False,
            "tool_name": action,
            "error_type": error_analysis.get("error_type", "unknown_error"),
            "error_message": error_analysis.get("error_message", "未知错误"),
            "http_status": error_analysis.get("http_status"),
            "api_url": error_analysis.get("api_url"),
            "sent_params": error_analysis.get("sent_params"),
            "tool_parameters": error_analysis.get("tool_parameters"),
            "instruction": error_analysis.get("instruction", "请分析此错误并决定如何处理"),
            "raw_result": error_analysis.get("raw_result", result)
        }
        
        return json.dumps(formatted_error, ensure_ascii=False, indent=2)
    
    async def execute_with_retry(self, action: str, action_input: str, max_retries: int = 2) -> str:
        """
        执行工具并支持智能重试
        
        Args:
            action: 工具名称
            action_input: 工具输入参数
            max_retries: 最大重试次数
            
        Returns:
            工具执行结果
        """
        retry_count = 0
        original_params = None
        
        while retry_count <= max_retries:
            if retry_count > 0:
                print(f"🔄 第 {retry_count} 次重试 {action}...")
            
            # 解析参数
            if action_input.strip().startswith('{'):
                try:
                    params = json.loads(action_input)
                except json.JSONDecodeError:
                    return f"无法解析Action Input JSON格式: {action_input}"
            else:
                params = {"query": action_input}
            
            if original_params is None:
                original_params = params.copy()
            
            # 执行工具
            result = await self.tool_registry.execute_tool(action, **params)
            
            # 如果成功，直接返回
            if result.get("success", False):
                if retry_count > 0:
                    print(f"✅ {action} 重试成功！")
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            # 分析错误
            error_analysis = self.analyze_tool_error(action, result)
            
            # 如果不建议重试，直接返回错误
            if not error_analysis["retry_recommended"] or retry_count >= max_retries:
                if retry_count >= max_retries:
                    print(f"❌ {action} 达到最大重试次数 ({max_retries})，停止重试")
                
                # 格式化错误信息给AI
                return self.format_error_for_ai(action, result, error_analysis)
            
            # 如果可以自动修正，尝试修正参数
            if error_analysis["can_auto_fix"] and "corrected_params" in error_analysis:
                corrected_params = error_analysis["corrected_params"]
                print(f"🔧 自动修正参数: {corrected_params}")
                
                # 使用修正后的参数更新action_input
                action_input = json.dumps(corrected_params, ensure_ascii=False)
                retry_count += 1
                continue
            
            # 如果无法自动修正，返回错误信息供AI分析
            return self.format_error_for_ai(action, result, error_analysis)
        
        # 不应该到达这里
        return f"工具 {action} 执行失败，已达到最大重试次数"
    
    async def _execute_action(self, action: str, action_input: str) -> str:
        """执行工具 - 增加智能重试机制"""
        try:
            # 🧠 短期记忆检查 - 在工具执行前检查是否需要跳过
            project_id = self._get_current_project_id()
            if project_id:
                should_skip, skip_message = self._should_skip_pdf_parsing(action, project_id)
                if should_skip:
                    # 返回跳过解析的模拟成功结果
                    skip_result = {
                        "success": True,
                        "message": skip_message,
                        "skipped": True,
                        "project_id": project_id,
                        "cached_state": self._get_project_state(project_id)
                    }
                    return json.dumps(skip_result, ensure_ascii=False, indent=2)
            
            # 🔄 使用智能重试执行工具
            result = await self.execute_with_retry(action, action_input, max_retries=2)
            
            # 🧠 短期记忆更新 - 处理PDF解析结果
            if project_id and action == "pdf_parser":
                try:
                    result_data = json.loads(result)
                    if result_data.get("success", False):
                        # 尝试从参数中提取文件名
                        filename = None
                        if 'minio_url' in params:
                            # 从minio://bucket/file.pdf中提取文件名
                            minio_url = params['minio_url']
                            filename = minio_url.split('/')[-1] if '/' in minio_url else minio_url
                            # 移除minio://前缀如果存在
                            if filename.startswith('minio://'):
                                filename = filename[8:].split('/')[-1]
                        
                        self._handle_pdf_parse_result(project_id, result_data, filename)
                except json.JSONDecodeError:
                    pass  # 如果不是JSON格式，忽略
            
            # 🧠 短期记忆更新 - 处理文档生成结果
            if project_id and action == "document_generator":
                try:
                    result_data = json.loads(result)
                    if result_data.get("success", False):
                        # 尝试从参数中提取文档信息
                        title = params.get('title')
                        doc_type = params.get('action') or params.get('type')
                        
                        self._handle_document_generation_result(project_id, result_data, title, doc_type)
                except json.JSONDecodeError:
                    pass
                
            return result
                
        except Exception as e:
            return f"执行工具 '{action}' 时发生错误: {str(e)}"
    
    def _execute_action_sync(self, action: str, action_input: str) -> str:
        """执行工具 - 同步版本，支持智能重试"""
        try:
            # 🧠 短期记忆检查 - 在工具执行前检查是否需要跳过
            project_id = self._get_current_project_id()
            if project_id:
                should_skip, skip_message = self._should_skip_pdf_parsing(action, project_id)
                if should_skip:
                    # 返回跳过解析的模拟成功结果
                    skip_result = {
                        "success": True,
                        "message": skip_message,
                        "skipped": True,
                        "project_id": project_id,
                        "cached_state": self._get_project_state(project_id)
                    }
                    return json.dumps(skip_result, ensure_ascii=False, indent=2)
            
            # 🔄 使用异步重试机制的同步版本
            import asyncio
            try:
                # 在新的事件循环中执行异步重试
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self.execute_with_retry(action, action_input, max_retries=2))
                loop.close()
            except Exception as e:
                return f"工具执行失败: {str(e)}"
            

            
            return result
                
        except Exception as e:
            return f"执行工具 '{action}' 时发生错误: {str(e)}"
    
    def _print_step(self, step_type: str, content: str, color: str = Fore.WHITE):
        """打印步骤信息"""
        if self.verbose:
            print(f"{color}{step_type}: {content}")
    
    def solve(self, problem: str, use_enhanced_framework: bool = False) -> str:
        """
        解决问题的主要方法
        
        Args:
            problem: 用户问题
            use_enhanced_framework: 是否使用增强版三步骤框架（已弃用，统一使用ReAct循环）
        
        Returns:
            解决方案和结果
        """
        self.current_problem = problem
        self.conversation_history.append({"role": "user", "content": problem})
        
        # 统一使用ReAct循环处理所有请求
        # Agent会通过Thought → Action的方式自己决定调用哪个工具
        return self._react_loop(problem)
    
    async def solve_problem_async(self, problem: str) -> AgentResult:
        """
        异步解决问题的方法 - 用于FastAPI集成
        
        Args:
            problem: 用户问题
        
        Returns:
            AgentResult包含响应、思考过程和迭代次数
        """
        self.current_problem = problem
        self.conversation_history.append({"role": "user", "content": problem})
        
        return await self._react_loop_async(problem)
    
# solve_problem_stream方法已移除，现在使用ThoughtInterceptor实现真正的实时流式输出
    
    def _react_loop(self, problem: str) -> str:
        """ReAct循环逻辑 - 处理所有类型的请求"""
        if self.verbose:
            print(f"{Fore.CYAN}{'='*50}")
            print(f"{Fore.CYAN}ReAct Agent 开始解决问题")
            print(f"{Fore.CYAN}问题: {problem}")
            print(f"{Fore.CYAN}{'='*50}")
        
        # 构建对话历史
        conversation = []
        conversation.append({"role": "system", "content": self.system_prompt})
        
        # 添加历史上下文（如果启用记忆）
        if self.memory_manager:
            context = self.memory_manager.get_relevant_context(problem)
            if context:
                try:
                    prompt_loader = get_prompt_loader()
                    memory_template = prompt_loader.get_prompt("system", "memory_context_template")
                    memory_content = memory_template.format(context=context)
                except Exception as e:
                    # 如果模板加载失败，使用默认格式
                    memory_content = f"相关历史经验:\n{context}"
                
                conversation.append({"role": "system", "content": memory_content})
                if self.verbose:
                    print(f"{Fore.YELLOW}📚 找到相关历史经验")
        
        # 添加用户问题
        try:
            prompt_loader = get_prompt_loader()
            question_template = prompt_loader.get_prompt("system", "user_question_template")
            user_question = question_template.format(problem=problem)
        except Exception as e:
            # 如果模板加载失败，使用默认格式
            user_question = f"问题: {problem}"
        
        conversation.append({"role": "user", "content": user_question})
        
        for iteration in range(self.max_iterations):
            # 直接 print，会被 ThoughtLogger 拦截
            print(f"\n--- 第 {iteration + 1} 轮 ---")
            
            # 获取LLM响应
            result = self.client.chat_completion_sync(conversation)
            response = result["choices"][0]["message"]["content"]
            usage_info = result.get("usage", {})
            conversation.append({"role": "assistant", "content": response})
            
            # 🔍 调试：显示LLM原始响应
            print(f"🤖 LLM响应: {response}")
            print(f"🔍 响应长度: {len(response)} 字符")
            
            # 解析响应
            thought, action, action_input_or_final = self._parse_response(response)
            
            # 🔍 调试：显示解析结果
            print(f"🔍 解析结果: thought={thought is not None}, action={action}, action_input={action_input_or_final is not None}")
            
            # 🔧 修复：强制显示思考内容，即使解析失败
            if thought:
                print(f"Thought: {thought}")
            else:
                # 如果没有解析到标准的Thought，尝试显示响应的第一部分
                lines = response.strip().split('\n')
                first_meaningful_line = ""
                for line in lines:
                    if line.strip() and not line.strip().startswith('```'):
                        first_meaningful_line = line.strip()
                        break
                if first_meaningful_line:
                    print(f"Thought: {first_meaningful_line}")
                else:
                    print(f"Thought: [未解析到标准格式] {response[:100]}...")
            
            # 检查是否是最终答案
            if action is None and action_input_or_final:
                print(f"Final Answer: {action_input_or_final}")
                
                # 保存到记忆
                if self.memory_manager:
                    self.memory_manager.add_session(problem, action_input_or_final, conversation)
                    if self.verbose:
                        print("💾 已保存到记忆")
                
                return action_input_or_final
            
            # 执行行动
            if action:
                print(f"Action: {action}")
                if action_input_or_final:
                    print(f"Action Input: {action_input_or_final}")
                
                # 执行工具 - 同步版本
                observation = self._execute_action_sync(action, action_input_or_final or "")
                print(f"Observation: {observation}")
                
                # 添加到对话历史
                conversation.append({"role": "user", "content": f"Observation: {observation}"})
            else:
                # 🔧 如果没有解析到Action，显示原始响应以便调试
                if not action_input_or_final:  # 也不是Final Answer
                    print(f"⚠️ 未检测到Action或Final Answer，原始响应: {response}")
        
        # 如果达到最大迭代次数
        final_answer = "抱歉，在最大迭代次数内未能完成任务。"
        if self.memory_manager:
            self.memory_manager.add_session(problem, final_answer, conversation)
        
        return final_answer
    
    async def _react_loop_async(self, problem: str) -> AgentResult:
        """异步ReAct循环逻辑"""
        thinking_process = []
        
        if self.verbose:
            print(f"{Fore.CYAN}{'='*50}")
            print(f"{Fore.CYAN}ReAct Agent 开始解决问题")
            print(f"{Fore.CYAN}问题: {problem}")
            print(f"{Fore.CYAN}{'='*50}")
        
        # 构建对话历史
        conversation = []
        conversation.append({"role": "system", "content": self.system_prompt})
        
        # 添加历史上下文（如果启用记忆）
        if self.memory_manager:
            context = self.memory_manager.get_relevant_context(problem)
            if context:
                try:
                    prompt_loader = get_prompt_loader()
                    memory_template = prompt_loader.get_prompt("system", "memory_context_template")
                    memory_content = memory_template.format(context=context)
                except Exception as e:
                    memory_content = f"相关历史经验:\n{context}"
                
                conversation.append({"role": "system", "content": memory_content})
                if self.verbose:
                    print(f"{Fore.YELLOW}📚 找到相关历史经验")
        
        # 添加用户问题
        try:
            prompt_loader = get_prompt_loader()
            question_template = prompt_loader.get_prompt("system", "user_question_template")
            user_question = question_template.format(problem=problem)
        except Exception as e:
            user_question = f"问题: {problem}"
        
        conversation.append({"role": "user", "content": user_question})
        
        for iteration in range(self.max_iterations):
            # 直接 print，会被 ThoughtLogger 拦截
            print(f"\n--- 第 {iteration + 1} 轮 ---")
            
            # 获取LLM响应
            result = await self.client.chat_completion(conversation)
            response = result["choices"][0]["message"]["content"]
            usage_info = result.get("usage", {})
            conversation.append({"role": "assistant", "content": response})
            
            # 🔍 调试：显示LLM原始响应
            print(f"🤖 LLM响应: {response}")
            print(f"🔍 响应长度: {len(response)} 字符")
            
            # 解析响应
            thought, action, action_input_or_final = self._parse_response(response)
            
            # 🔍 调试：显示解析结果
            print(f"🔍 解析结果: thought={thought is not None}, action={action}, action_input={action_input_or_final is not None}")
            
            # 记录思考过程
            step_info = {
                "iteration": iteration + 1,
                "thought": thought,
                "action": action,
                "action_input": action_input_or_final if action else None
            }
            
            # 🔧 修复：强制显示思考内容，即使解析失败
            if thought:
                print(f"Thought: {thought}")
            else:
                # 如果没有解析到标准的Thought，尝试显示响应的第一部分
                lines = response.strip().split('\n')
                first_meaningful_line = ""
                for line in lines:
                    if line.strip() and not line.strip().startswith('```'):
                        first_meaningful_line = line.strip()
                        break
                if first_meaningful_line:
                    print(f"Thought: {first_meaningful_line}")
                else:
                    print(f"Thought: [未解析到标准格式] {response[:100]}...")
            
            # 检查是否是最终答案
            if action is None and action_input_or_final:
                print(f"Final Answer: {action_input_or_final}")
                
                step_info["final_answer"] = action_input_or_final
                thinking_process.append(step_info)
                
                # 保存到记忆
                if self.memory_manager:
                    self.memory_manager.add_session(problem, action_input_or_final, conversation)
                    if self.verbose:
                        print("💾 已保存到记忆")
                
                return AgentResult(
                    response=action_input_or_final,
                    thinking_process=thinking_process,
                    total_iterations=iteration + 1,
                    success=True
                )
            
            # 执行行动
            if action:
                print(f"Action: {action}")
                if action_input_or_final:
                    print(f"Action Input: {action_input_or_final}")
                
                # 执行工具
                observation = await self._execute_action(action, action_input_or_final or "")
                print(f"Observation: {observation}")
                
                step_info["observation"] = observation
                thinking_process.append(step_info)
                
                # 添加到对话历史
                conversation.append({"role": "user", "content": f"Observation: {observation}"})
            else:
                # 🔧 如果没有解析到Action，显示原始响应以便调试
                if not action_input_or_final:  # 也不是Final Answer
                    print(f"⚠️ 未检测到Action或Final Answer，原始响应: {response}")
                thinking_process.append(step_info)
        
        # 如果达到最大迭代次数
        final_answer = "抱歉，在最大迭代次数内未能完成任务。"
        if self.memory_manager:
            self.memory_manager.add_session(problem, final_answer, conversation)
        
        return AgentResult(
            response=final_answer,
            thinking_process=thinking_process,
            total_iterations=self.max_iterations,
            success=False
        )
# _react_loop_stream方法已移除，现在使用ThoughtInterceptor捕获真实的terminal输出
    
    def interactive_mode(self):
        """交互模式"""
        print(f"{Fore.GREEN}Enhanced ReAct Agent 交互模式")
        print(f"{Fore.YELLOW}输入 'quit', 'exit' 或 '退出' 来结束对话")
        print(f"{Fore.YELLOW}输入 'memory' 查看长期记忆摘要")
        print(f"{Fore.YELLOW}输入 'short_memory' 查看短期记忆状态")
        print(f"{Fore.YELLOW}输入 'clear_short' 清除所有短期记忆")
        print(f"{Fore.YELLOW}输入 'clear_project <project_id>' 清除指定项目的短期记忆")
        print(f"{Fore.CYAN}{'='*50}")
        
        while True:
            try:
                problem = input(f"{Fore.WHITE}请输入问题: ").strip()
                if problem.lower() in ['quit', 'exit', '退出']:
                    print(f"{Fore.GREEN}再见！")
                    break
                
                if problem.lower() == 'memory' and self.memory_manager:
                    print(f"\n{Fore.CYAN}📚 长期记忆摘要:")
                    print(self.memory_manager.get_memory_summary())
                    print()
                    continue
                
                if problem.lower() == 'short_memory':
                    print(f"\n{Fore.CYAN}{self.get_short_term_memory_summary()}")
                    print()
                    continue
                
                if problem.lower() == 'clear_short':
                    self.clear_all_short_term_memory()
                    print(f"\n{Fore.GREEN}✅ 所有短期记忆已清除\n")
                    continue
                
                if problem.lower().startswith('clear_project '):
                    project_id = problem.split(' ', 1)[1].strip()
                    if project_id:
                        self.clear_project_memory(project_id)
                        print(f"\n{Fore.GREEN}✅ 项目 {project_id} 的短期记忆已清除\n")
                    else:
                        print(f"\n{Fore.RED}❌ 请指定项目ID\n")
                    continue
                
                if problem:
                    answer = self.solve(problem)
                    print(f"\n{Fore.GREEN}{'='*50}")
                    print(f"{Fore.GREEN}最终答案: {answer}")
                    print(f"{Fore.GREEN}{'='*50}\n")
                
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}程序被中断")
                break
            except Exception as e:
                print(f"{Fore.RED}发生错误: {str(e)}")
    
    def clear_memory(self):
        """清除记忆"""
        if self.memory_manager:
            self.memory_manager.conversation_history.clear()
            self.memory_manager.session_summaries.clear()
            self.memory_manager.save_memory()
            print("记忆已清除") 

    def _get_current_project_id(self) -> Optional[str]:
        """获取当前项目ID"""
        if hasattr(self.tool_registry, 'project_context') and self.tool_registry.project_context:
            return self.tool_registry.project_context.get('project_id')
        return None
    
    def _get_current_project_name(self) -> Optional[str]:
        """获取当前项目名称"""
        if hasattr(self.tool_registry, 'project_context') and self.tool_registry.project_context:
            return self.tool_registry.project_context.get('project_name')
        return None
    
    def _get_project_state(self, project_id: str) -> Dict[str, Any]:
        """获取项目的短期记忆状态"""
        return self.project_state_manager.get_project_state(project_id)
    
    def _update_project_state(self, project_id: str, **updates):
        """更新项目的短期记忆状态"""
        self.project_state_manager.update_project_state(project_id, **updates)
        
        if self.verbose:
            print(f"📁 项目状态更新 - 项目 {project_id}: {updates}")
    
    def _check_pdf_parsed(self, project_id: str, filename: str = None) -> bool:
        """检查项目的PDF是否已解析"""
        project_state = self._get_project_state(project_id)
        pdf_files_parsed = project_state.get("pdf_files_parsed", [])
        
        if filename:
            # 检查特定文件是否已解析
            return any(f.get("name") == filename and f.get("status") == "success" for f in pdf_files_parsed)
        else:
            # 检查是否有任何PDF已解析
            return len(pdf_files_parsed) > 0
    
    def _should_skip_pdf_parsing(self, action: str, project_id: str) -> Tuple[bool, str]:
        """检查是否应该跳过PDF解析"""
        if action == "pdf_parser" and project_id:
            if self._check_pdf_parsed(project_id):
                project_state = self._get_project_state(project_id)
                message = f"✅ 项目 {project_id} 的PDF已解析过 (时间: {project_state.get('last_parse_time', '未知')}), 跳过重复解析"
                return True, message
        return False, ""
    
    def _handle_pdf_parse_result(self, project_id: str, result: Dict[str, Any], filename: str = None):
        """处理PDF解析结果，更新短期记忆"""
        if result.get("success", False):
            from datetime import datetime
            project_state = self._get_project_state(project_id)
            
            # 提取文件名（从结果或参数中获取）
            if not filename:
                filename = result.get("filename") or result.get("file_name") or "unknown.pdf"
            
            # 添加到已解析文件列表
            from datetime import datetime
            parsed_file = {
                "name": filename,
                "status": "success",
                "time": datetime.now().isoformat(),
                "message": result.get("message", "PDF解析成功")
            }
            
            # 避免重复添加
            pdf_files_parsed = project_state.get("pdf_files_parsed", [])
            if not any(f.get("name") == filename for f in pdf_files_parsed):
                pdf_files_parsed.append(parsed_file)
                self._update_project_state(project_id, pdf_files_parsed=pdf_files_parsed)
                
                if self.verbose:
                    print(f"📄 PDF解析完成 - 项目 {project_id}, 文件: {filename}")
            else:
                if self.verbose:
                    print(f"📄 PDF文件 {filename} 已在解析列表中")
    
    def _handle_document_generation_result(self, project_id: str, result: Dict[str, Any], title: str = None, doc_type: str = None):
        """处理文档生成结果，更新短期记忆"""
        if result.get("success", False):
            from datetime import datetime
            project_state = self._get_project_state(project_id)
            
            # 提取文档信息
            if not title:
                title = result.get("title") or result.get("document_title") or "未命名文档"
            if not doc_type:
                doc_type = result.get("type") or result.get("document_type") or "unknown"
            
            # 添加到生成文档列表
            from datetime import datetime
            generated_doc = {
                "title": title,
                "type": doc_type,
                "time": datetime.now().isoformat(),
                "message": result.get("message", "文档生成成功"),
                "file_path": result.get("file_path") or result.get("output_file")
            }
            
            documents_generated = project_state.get("documents_generated", [])
            documents_generated.append(generated_doc)
            self._update_project_state(project_id, documents_generated=documents_generated)
            
            if self.verbose:
                print(f"📄 文档生成完成 - 项目 {project_id}, 标题: {title}, 类型: {doc_type}")

    def get_short_term_memory_summary(self) -> str:
        """获取短期记忆摘要"""
        if not self.project_state_manager.project_states:
            return "📁 短期记忆: 暂无项目状态记录"
        
        summary = "📁 短期记忆状态:\n"
        for project_id, state in self.project_state_manager.project_states.items():
            pdf_files = state.get("pdf_files_parsed", [])
            documents = state.get("documents_generated", [])
            
            summary += f"  📁 项目 {project_id}:\n"
            summary += f"    - PDF文件: {len(pdf_files)}个已解析\n"
            if pdf_files:
                for pdf in pdf_files:
                    summary += f"      ✅ {pdf.get('name', 'unknown')} ({pdf.get('time', '未知时间')})\n"
            
            summary += f"    - 生成文档: {len(documents)}个\n"
            if documents:
                for doc in documents:
                    summary += f"      📄 {doc.get('title', 'unknown')} ({doc.get('time', '未知时间')})\n"
        
        return summary
    
    def get_project_status_for_frontend(self, project_id: str) -> Dict[str, Any]:
        """获取项目状态，供前端显示用"""
        project_state = self._get_project_state(project_id)
        
        return {
            "project_id": project_id,
            "pdf_files_parsed": project_state.get("pdf_files_parsed", []),
            "documents_generated": project_state.get("documents_generated", []),
            "total_pdf_files": len(project_state.get("pdf_files_parsed", [])),
            "total_documents": len(project_state.get("documents_generated", [])),
            "last_activity": self._get_last_activity_time(project_state)
        }
    
    def _get_last_activity_time(self, project_state: Dict[str, Any]) -> str:
        """获取项目最后活动时间"""
        times = []
        
        # 收集PDF解析时间
        for pdf in project_state.get("pdf_files_parsed", []):
            if pdf.get("time"):
                times.append(pdf["time"])
        
        # 收集文档生成时间
        for doc in project_state.get("documents_generated", []):
            if doc.get("time"):
                times.append(doc["time"])
        
        if times:
            return max(times)  # 返回最新时间
        return "无活动记录"

    def clear_project_memory(self, project_id: str):
        """清除指定项目的短期记忆"""
        if project_id in self.project_state_manager.project_states:
            del self.project_state_manager.project_states[project_id]
            if self.verbose:
                print(f"📁 已清除项目 {project_id} 的短期记忆")
    
    async def auto_parse_pdfs(self, files: List[Dict[str, Any]] = None) -> bool:
        """
        自动解析PDF文件
        
        Args:
            files: 上传的文件列表，格式：[{"name": "file.pdf", "path": "/path/to/file.pdf"}]
        
        Returns:
            bool: 是否有PDF被解析
        """
        if not files:
            if self.verbose:
                print("📄 没有文件需要处理")
            return False
        
        project_id = self._get_current_project_id()
        if not project_id:
            if self.verbose:
                print("⚠️ 未找到项目ID，跳过自动PDF解析")
            return False
        
        # 筛选PDF文件
        pdf_files = [f for f in files if f.get('name', '').lower().endswith('.pdf')]
        if not pdf_files:
            if self.verbose:
                print("📄 没有PDF文件需要解析")
            return False
        
        if self.verbose:
            print(f"📄 发现 {len(pdf_files)} 个PDF文件，检查是否需要解析...")
        
        # 检查是否已经解析过
        if self._check_pdf_parsed(project_id):
            project_state = self._get_project_state(project_id)
            if self.verbose:
                print(f"✅ 项目 {project_id} 的PDF已解析过 (时间: {project_state.get('last_parse_time', '未知')})")
                print(f"📋 已解析文件: {project_state.get('pdf_files', [])}")
            return False
        
        # 执行自动解析
        if self.verbose:
            print(f"🚀 开始自动解析项目 {project_id} 的PDF文件...")
        
        try:
            # 构建解析参数
            pdf_paths = [f.get('path', '') for f in pdf_files if f.get('path')]
            if not pdf_paths:
                if self.verbose:
                    print("❌ PDF文件路径信息缺失")
                return False
            
            # 调用PDF解析工具
            parse_params = {
                "pdf_path": pdf_paths[0] if len(pdf_paths) == 1 else pdf_paths,
                "action": "parse",
                "project_id": project_id
            }
            
            if self.verbose:
                print(f"📋 解析参数: {parse_params}")
                print("⏳ 正在解析PDF，预计需要2分钟...")
            
            # 执行解析
            result = await self.tool_registry.execute_tool("pdf_parser", **parse_params)
            
            if result.get("success", False):
                # 更新短期记忆
                self._handle_pdf_parse_result(project_id, result)
                
                if self.verbose:
                    print(f"✅ PDF自动解析完成！项目 {project_id}")
                    print(f"📄 解析结果: {result.get('message', '解析成功')}")
                
                return True
            else:
                if self.verbose:
                    print(f"❌ PDF自动解析失败: {result.get('error', '未知错误')}")
                return False
                
        except Exception as e:
            if self.verbose:
                print(f"❌ PDF自动解析异常: {str(e)}")
            return False
    
    def auto_parse_pdfs_sync(self, files: List[Dict[str, Any]] = None) -> bool:
        """
        自动解析PDF文件 - 同步版本
        
        Args:
            files: 上传的文件列表
        
        Returns:
            bool: 是否有PDF被解析
        """
        import asyncio
        
        try:
            # 在新的事件循环中执行异步解析
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.auto_parse_pdfs(files))
            loop.close()
            return result
        except Exception as e:
            if self.verbose:
                print(f"❌ 同步PDF解析失败: {str(e)}")
            return False 