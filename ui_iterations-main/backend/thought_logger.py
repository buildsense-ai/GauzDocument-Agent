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
                content = clean_message.replace("Final Answer:", "").strip()
                self._push_to_queue({
                    "type": "final_answer",
                    "content": content
                })
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
                # 如果没有事件循环，尝试创建任务
                try:
                    asyncio.create_task(self.queue.put(data))
                except RuntimeError:
                    # 最后的兜底：直接用 put_nowait
                    self.queue.put_nowait(data)
                    
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