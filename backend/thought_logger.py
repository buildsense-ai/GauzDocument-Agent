import sys
import asyncio
import json
import re
from typing import Optional

# 全局异步队列
thought_queue = asyncio.Queue()

class ThoughtLogger:
    """拦截 stdout 输出，同时保持终端显示和推送到队列"""
    
    def __init__(self, queue: asyncio.Queue):
        self._original_stdout = sys.stdout
        self.queue = queue
        self._buffer = ""
        # 🆕 添加状态跟踪
        self._collecting_final_answer = False
        self._final_answer_content = []
    
    def write(self, message: str):
        """重写 write 方法来拦截所有输出"""
        # 保留原本 terminal 输出
        self._original_stdout.write(message)
        self._original_stdout.flush()
        
        # 分析输出内容并推送到队列
        self._analyze_and_push(message)
        
        return len(message)
    
    def flush(self):
        """刷新输出"""
        self._original_stdout.flush()
        
        # 🆕 在flush时检查是否有未推送的Final Answer
        if self._collecting_final_answer and self._final_answer_content:
            self._push_complete_final_answer()
            self._collecting_final_answer = False
            self._final_answer_content = []
            self._original_stdout.write("🎯 在flush时推送了Final Answer\n")
    
    def _analyze_and_push(self, message: str):
        """分析输出内容并推送到队列"""
        message = message.strip()
        if not message:
            return
            
        # 移除ANSI颜色代码
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_message = ansi_escape.sub('', message)
        
        try:
            # 调试输出
            if any(keyword in clean_message for keyword in ["Thought:", "Action:", "Final Answer:", "Observation:"]):
                self._original_stdout.write(f"🔍 分析消息: '{clean_message}'\n")
            
            # 🆕 处理多行Final Answer收集
            if self._collecting_final_answer:
                # 检查是否遇到新的标记，如果是则结束Final Answer收集
                if any(clean_message.startswith(marker) for marker in ["Thought:", "Action:", "Observation:", "--- 第"]):
                    # 推送完整的Final Answer
                    self._push_complete_final_answer()
                    # 重置收集状态
                    self._collecting_final_answer = False
                    self._final_answer_content = []
                    # 继续处理当前消息
                else:
                    # 继续收集Final Answer内容
                    self._final_answer_content.append(clean_message)
                    self._original_stdout.write(f"📝 收集Final Answer内容: {len(self._final_answer_content)}行\n")
                    return  # 不再进行其他处理
            
            # 检测不同类型的输出
            if clean_message.startswith("Thought:"):
                content = clean_message.replace("Thought:", "").strip()
                self._push_to_queue({
                    "type": "thought",
                    "content": content
                })
            elif clean_message.startswith("Action:"):
                content = clean_message.replace("Action:", "").strip()
                self._push_to_queue({
                    "type": "action", 
                    "content": content
                })
            elif clean_message.startswith("Action Input:"):
                content = clean_message.replace("Action Input:", "").strip()
                self._push_to_queue({
                    "type": "action_input",
                    "content": content
                })
            elif clean_message.startswith("Observation:"):
                content = clean_message.replace("Observation:", "").strip()
                self._push_to_queue({
                    "type": "observation",
                    "content": content
                })
            elif clean_message.startswith("Final Answer:"):
                # 🆕 开始收集Final Answer
                content = clean_message.replace("Final Answer:", "").strip()
                self._collecting_final_answer = True
                self._final_answer_content = [content] if content else []
                self._original_stdout.write(f"🎯 开始收集Final Answer，初始内容: '{content}'\n")
            elif clean_message.startswith("--- 第") and clean_message.endswith("轮 ---"):
                # 捕获迭代轮次
                match = re.search(r"第 (\d+) 轮", clean_message)
                if match:
                    iteration = int(match.group(1))
                    self._push_to_queue({
                        "type": "iteration",
                        "round": iteration,
                        "content": f"第 {iteration} 轮"
                    })
                    
        except Exception as e:
            self._original_stdout.write(f"⚠️ ThoughtLogger 分析错误: {e}\n")
    
    def _push_complete_final_answer(self):
        """推送完整的Final Answer内容"""
        if self._final_answer_content:
            complete_content = "\n".join(self._final_answer_content)
            self._original_stdout.write(f"🎯 推送完整Final Answer ({len(self._final_answer_content)}行，{len(complete_content)}字符)\n")
            self._push_to_queue({
                "type": "final_answer",
                "content": complete_content
            })
    
    def _push_to_queue(self, data: dict):
        """推送数据到队列"""
        try:
            import time
            data["timestamp"] = time.time()
            
            # 使用线程安全的方式推送
            try:
                # 获取当前事件循环
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果在事件循环中，使用线程安全的方式
                    loop.call_soon_threadsafe(self.queue.put_nowait, data)
                else:
                    # 如果不在事件循环中，直接放入
                    self.queue.put_nowait(data)
            except RuntimeError:
                # 如果没有事件循环，尝试同步方式放入队列
                try:
                    # 使用同步方式处理，避免协程警告
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                    self.queue.put_nowait(data)
                except Exception as e:
                    # 如果队列操作完全失败，至少记录一下
                    self._original_stdout.write(f"⚠️ 队列操作失败: {e}, 数据类型: {data.get('type', 'unknown')}\n")
                    
            self._original_stdout.write(f"📤 已推送到队列: {data['type']}\n")
            
        except Exception as e:
            self._original_stdout.write(f"⚠️ 队列推送失败: {e}\n")

# 全局 ThoughtLogger 实例
thought_logger = None

def setup_thought_logger():
    """设置 ThoughtLogger 拦截 stdout"""
    global thought_logger
    if thought_logger is None:
        thought_logger = ThoughtLogger(thought_queue)
        sys.stdout = thought_logger
        print("🌊 ThoughtLogger 已启动，开始拦截输出")

def restore_stdout():
    """恢复原始 stdout"""
    global thought_logger
    if thought_logger is not None:
        # 🆕 在停止前，推送任何未完成的Final Answer
        if thought_logger._collecting_final_answer and thought_logger._final_answer_content:
            thought_logger._push_complete_final_answer()
            print("🎯 在停止时推送了未完成的Final Answer")
        
        sys.stdout = thought_logger._original_stdout
        thought_logger = None
        print("🌊 ThoughtLogger 已停止")

async def get_thought_data() -> Optional[dict]:
    """异步获取思考数据"""
    try:
        return await asyncio.wait_for(thought_queue.get(), timeout=0.1)
    except asyncio.TimeoutError:
        return None

def has_thought_data() -> bool:
    """检查是否有待处理的思考数据"""
    return not thought_queue.empty()

def clear_thought_queue():
    """清空思考队列"""
    while not thought_queue.empty():
        try:
            thought_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

# 显式推送函数（用于确保重要数据被推送）
def push_final_answer(content: str, total_iterations: int = 1):
    """显式推送 Final Answer"""
    global thought_logger
    if thought_logger:
        data = {
            "type": "final_answer",
            "content": content,
            "total_iterations": total_iterations
        }
        thought_logger._push_to_queue(data)

def push_thought(content: str):
    """显式推送 Thought"""
    global thought_logger
    if thought_logger:
        data = {
            "type": "thought",
            "content": content
        }
        thought_logger._push_to_queue(data)

def push_action(action: str, action_input: str = ""):
    """显式推送 Action"""
    global thought_logger
    if thought_logger:
        thought_logger._push_to_queue({
            "type": "action",
            "content": action
        })
        if action_input:
            thought_logger._push_to_queue({
                "type": "action_input", 
                "content": action_input
            }) 