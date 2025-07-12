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

from deepseek_client import DeepSeekClient
from tools import ToolRegistry, create_core_tool_registry
from prompts.loader import get_prompt_loader

# 初始化colorama
init(autoreset=True)

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
                    memory_data = pickle.load(f)
                    self.conversation_history = memory_data.get('conversation_history', [])
                    self.session_summaries = memory_data.get('session_summaries', [])
            except Exception as e:
                print(f"加载记忆失败: {e}")
    
    def save_memory(self):
        """保存记忆"""
        try:
            memory_data = {
                'conversation_history': self.conversation_history,
                'session_summaries': self.session_summaries
            }
            with open(self.memory_file, 'wb') as f:
                pickle.dump(memory_data, f)
        except Exception as e:
            print(f"保存记忆失败: {e}")
    
    def add_session(self, problem: str, solution: str, conversation: List[Dict[str, str]]):
        """添加会话记录"""
        session = {
            'timestamp': datetime.now().isoformat(),
            'problem': problem,
            'solution': solution,
            'conversation_length': len(conversation)
        }
        self.session_summaries.append(session)
        
        # 保存完整对话历史（限制数量以避免内存过大）
        if len(self.conversation_history) > 50:  # 保留最近50次对话
            self.conversation_history = self.conversation_history[-50:]
        
        self.conversation_history.extend(conversation)
        self.save_memory()
    
    def get_relevant_context(self, current_problem: str, max_context: int = 3) -> str:
        """获取相关的历史上下文"""
        if not self.session_summaries:
            return ""
        
        # 简单的关键词匹配来找相关历史
        relevant_sessions = []
        problem_keywords = set(current_problem.lower().split())
        
        for session in self.session_summaries[-10:]:  # 检查最近10次会话
            session_keywords = set(session['problem'].lower().split())
            # 计算关键词重叠度
            overlap = len(problem_keywords & session_keywords)
            if overlap > 0:
                relevant_sessions.append((session, overlap))
        
        # 按相关性排序
        relevant_sessions.sort(key=lambda x: x[1], reverse=True)
        
        if not relevant_sessions:
            return ""
        
        context_parts = []
        for session, _ in relevant_sessions[:max_context]:
            context_parts.append(f"历史问题: {session['problem']}")
            context_parts.append(f"解决方案: {session['solution']}")
            context_parts.append(f"时间: {session['timestamp'][:19].replace('T', ' ')}")
            context_parts.append("---")
        
        return "\n".join(context_parts)
    
    def get_memory_summary(self) -> str:
        """获取记忆摘要"""
        if not self.session_summaries:
            return "暂无历史记录"
        
        total_sessions = len(self.session_summaries)
        recent_sessions = self.session_summaries[-5:]
        
        summary = f"总共处理了 {total_sessions} 个问题\n\n最近的问题:\n"
        for i, session in enumerate(recent_sessions, 1):
            summary += f"{i}. {session['problem'][:50]}{'...' if len(session['problem']) > 50 else ''}\n"
            summary += f"   时间: {session['timestamp'][:19].replace('T', ' ')}\n"
        
        return summary

class EnhancedReActAgent:
    """增强版ReAct Agent - 支持记忆功能，所有请求都通过ReAct循环处理"""
    
    def __init__(
        self,
        deepseek_client: DeepSeekClient,
        tool_registry: Optional[ToolRegistry] = None,
        max_iterations: int = 10,
        verbose: bool = True,
        enable_memory: bool = True,
        memory_file: str = "agent_memory.pkl"
    ):
        self.client = deepseek_client
        # 使用create_core_tool_registry确保所有工具都被正确加载
        self.tool_registry = tool_registry or create_core_tool_registry(deepseek_client)
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.enable_memory = enable_memory
        
        # 初始化记忆管理器
        self.memory_manager = MemoryManager(memory_file) if enable_memory else None
        
        # 持久化对话历史（跨会话）
        self.persistent_conversation: List[Dict[str, str]] = []
        
        # 当前会话的对话历史
        self.conversation_history: List[Dict[str, str]] = []
        
        # 当前问题
        self.current_problem: str = ""
        
        # ReAct 系统提示词
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        try:
            # 从yaml文件加载prompt模板
            prompt_loader = get_prompt_loader()
            prompt_template = prompt_loader.get_prompt("system", "system_prompt_template")
            
            # 构建工具描述
            tools_description = "\n".join([
                f"- {tool['name']}: {tool['description']}"
                for tool in self.tool_registry.list_tools()
            ])
            
            # 使用模板替换变量
            base_prompt = prompt_template.format(
                tools_description=tools_description,
                max_iterations=self.max_iterations
            )
            
            return base_prompt
            
        except Exception as e:
            # 如果加载失败，记录错误并使用备用prompt
            print(f"警告：加载prompt失败，使用备用prompt: {e}")
            return self._build_fallback_system_prompt()
    
    def _build_fallback_system_prompt(self) -> str:
        """备用系统提示词（当yaml加载失败时使用）"""
        tools_description = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in self.tool_registry.list_tools()
        ])
        
        return f"""你是一个ReAct (Reasoning and Acting) 智能代理。你需要通过交替进行推理(Thought)和行动(Action)来解决问题。

⚠️ **重要：你必须优先使用工具来解决问题，而不是直接给出答案！**

可用工具:
{tools_description}

你必须严格按照以下格式进行推理和行动:

Thought: [你的推理过程，分析当前情况和下一步需要做什么]
Action: [工具名称]
Action Input: [工具的输入参数]
Observation: [工具执行结果，这部分由系统自动填充]

当你有了最终答案时，使用:
Thought: [最终推理]
Final Answer: [你的最终答案]

开始解决问题吧！"""
    
    def _parse_response(self, response: str) -> Tuple[str, Optional[str], Optional[str]]:
        """解析LLM响应，提取推理、行动和输入"""
        # 查找Thought
        thought_match = re.search(r'Thought:\s*(.*?)(?=\n(?:Action|Final Answer):|$)', response, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else ""
        
        # 查找Final Answer
        final_answer_match = re.search(r'Final Answer:\s*(.*)', response, re.DOTALL)
        if final_answer_match:
            final_answer = final_answer_match.group(1).strip()
            return thought, None, final_answer
        
        # 查找Action和Action Input
        action_match = re.search(r'Action:\s*(.*?)(?=\n|$)', response)
        action = action_match.group(1).strip() if action_match else None
        
        action_input_match = re.search(r'Action Input:\s*(.*?)(?=\n(?:Thought|Action|Final Answer):|$)', response, re.DOTALL)
        action_input = action_input_match.group(1).strip() if action_input_match else ""
        
        return thought, action, action_input
    
    def _execute_action(self, action: str, action_input: str) -> str:
        """执行工具行动"""
        try:
            tool = self.tool_registry.get_tool(action)
            if not tool:
                return f"错误：工具 '{action}' 不存在。可用工具: {', '.join([t['name'] for t in self.tool_registry.list_tools()])}"
            
            # 尝试解析JSON格式的输入
            try:
                if action_input.startswith('{') and action_input.endswith('}'):
                    params = json.loads(action_input)
                    return tool.execute(**params)
                else:
                    # 对于文档生成工具，如果输入是简单字符串，将其作为request参数
                    if action == "document_generator":
                        return tool.execute(action="generate_long_document", title="AI生成文档", requirements=action_input)
                    else:
                        # 其他工具尝试作为单个参数传递
                        return tool.execute(action_input)
            except json.JSONDecodeError:
                # JSON解析失败，根据工具类型处理
                if action == "document_generator":
                    return tool.execute(action="generate_long_document", title="AI生成文档", requirements=action_input)
                else:
                    return tool.execute(action_input)
        
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
            if self.verbose:
                print(f"\n{Fore.YELLOW}--- 第 {iteration + 1} 轮 ---")
            
            # 获取LLM响应
            response, usage_info = self.client.chat_completion(conversation)
            conversation.append({"role": "assistant", "content": response})
            
            # 解析响应
            thought, action, action_input_or_final = self._parse_response(response)
            
            # 打印推理过程
            if thought:
                self._print_step("Thought", thought, Fore.BLUE)
            
            # 检查是否是最终答案
            if action is None and action_input_or_final:
                self._print_step("Final Answer", action_input_or_final, Fore.GREEN)
                
                # 保存到记忆
                if self.memory_manager:
                    self.memory_manager.add_session(problem, action_input_or_final, conversation)
                    if self.verbose:
                        print(f"{Fore.YELLOW}💾 已保存到记忆")
                
                return action_input_or_final
            
            # 执行行动
            if action:
                self._print_step("Action", action, Fore.MAGENTA)
                if action_input_or_final:
                    self._print_step("Action Input", action_input_or_final, Fore.MAGENTA)
                
                # 执行工具
                observation = self._execute_action(action, action_input_or_final or "")
                self._print_step("Observation", observation, Fore.CYAN)
                
                # 将观察结果添加到对话
                conversation.append({"role": "user", "content": f"Observation: {observation}"})
            else:
                # 如果没有明确的action，可能是格式错误
                error_msg = "响应格式不正确，请按照 Thought -> Action -> Action Input 的格式"
                self._print_step("Error", error_msg, Fore.RED)
                conversation.append({"role": "user", "content": f"Error: {error_msg}"})
        
        # 达到最大迭代次数
        final_msg = f"达到最大迭代次数 ({self.max_iterations})，未能找到最终答案。"
        if self.verbose:
            print(f"{Fore.RED}{final_msg}")
        
        # 即使未完成也保存到记忆
        if self.memory_manager:
            self.memory_manager.add_session(problem, final_msg, conversation)
        
        return final_msg
    
    def interactive_mode(self):
        """增强的交互模式，支持记忆"""
        print(f"{Fore.GREEN}欢迎使用增强版 ReAct Agent 交互模式！")
        print(f"{Fore.YELLOW}可用工具: {', '.join([tool['name'] for tool in self.tool_registry.list_tools()])}")
        
        if self.memory_manager:
            print(f"{Fore.YELLOW}记忆功能: 已启用")
            print(f"{Fore.YELLOW}特殊命令: 输入 'memory' 查看历史记录")
        
        print(f"{Fore.YELLOW}输入 'quit' 或 'exit' 退出\n")
        
        while True:
            try:
                problem = input(f"{Fore.WHITE}请输入问题: ").strip()
                if problem.lower() in ['quit', 'exit', '退出']:
                    print(f"{Fore.GREEN}再见！")
                    break
                
                if problem.lower() == 'memory' and self.memory_manager:
                    print(f"\n{Fore.CYAN}📚 记忆摘要:")
                    print(self.memory_manager.get_memory_summary())
                    print()
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