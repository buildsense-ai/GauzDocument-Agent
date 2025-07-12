#!/usr/bin/env python3
"""
Advanced Long Document Generator Tool
高级长文档生成工具 - 基于long_generator模块

这是一个集成了long_generator的高级文档生成工具，具有以下特点：
- 状态机驱动的多阶段生成流程
- 智能大纲生成与精炼
- 向量数据库知识检索
- 多格式输出(JSON/DOCX)
- 云存储支持
- 完整的错误处理和状态管理
"""

import os
import sys
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

# 添加long_generator到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'long_generator'))

from base_tool import Tool

# 导入long_generator模块
try:
    from long_generator.generator import LongDocumentGenerator, TaskState
    from long_generator.config import Config
    LONG_GENERATOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  无法导入long_generator: {e}")
    LONG_GENERATOR_AVAILABLE = False

class AdvancedLongDocumentGeneratorTool(Tool):
    """高级长文档生成工具"""
    
    def __init__(self):
        super().__init__()
        self.name = "advanced_long_document_generator"
        self.description = """🚀 高级长文档生成工具 - AI驱动的专业文档创建系统

✨ **核心特性:**
- 🧠 智能大纲生成与多轮精炼
- 🔍 向量数据库知识检索整合
- 📝 多阶段内容生成流程
- 🎯 状态机驱动的稳定执行
- 📊 多格式输出 (JSON/DOCX)
- ☁️  云存储自动上传
- 🔧 完整的错误处理和状态管理

🎮 **支持的操作 (action):**

1. **generate_document** - 生成长文档 📄
   参数: {"action": "generate_document", "chat_history": "对话历史", "request": "生成要求"}
   示例: {"action": "generate_document", "chat_history": "我们讨论了医灵古庙", "request": "生成古庙保护报告"}

2. **check_status** - 检查任务状态 🔍
   参数: {"action": "check_status", "task_id": "任务ID"}
   示例: {"action": "check_status", "task_id": "abc123-def456"}

3. **list_tasks** - 列出所有任务 📋
   参数: {"action": "list_tasks"}

4. **get_task_result** - 获取任务结果 📄
   参数: {"action": "get_task_result", "task_id": "任务ID"}
   示例: {"action": "get_task_result", "task_id": "abc123-def456"}

5. **delete_task** - 删除任务 🗑️
   参数: {"action": "delete_task", "task_id": "任务ID"}
   示例: {"action": "delete_task", "task_id": "abc123-def456"}

🔧 **生成流程:**
用户请求 → 创作指令分析 → 初始大纲生成 → 多轮大纲精炼 → 分章节内容生成 → 文档整合 → 格式转换 → 云端上传

⚡ **技术优势:**
- 使用DeepSeek AI进行内容生成
- 集成向量数据库进行知识检索
- 状态机保证流程稳定性
- 支持任务断点续传
- 自动云端备份

💡 **适用场景:**
- 专业报告生成 (文物评估、工程报告等)
- 技术文档创建
- 研究报告撰写
- 项目方案制定
- 知识整合文档

📊 **输出格式:**
- JSON任务状态文件
- DOCX格式文档
- MinIO云存储链接
- 完整的执行日志
"""
        
        # 检查依赖是否可用
        if not LONG_GENERATOR_AVAILABLE:
            self.description += "\n\n❌ **警告**: long_generator模块不可用，请检查依赖安装"
        
        # 确保任务目录存在
        self.tasks_dir = getattr(Config, 'TASKS_DIR', 'tasks')
        os.makedirs(self.tasks_dir, exist_ok=True)
    
    def execute(self, action: str, **kwargs) -> str:
        """执行工具操作"""
        if not LONG_GENERATOR_AVAILABLE:
            return json.dumps({
                "status": "error",
                "message": "long_generator模块不可用，请检查依赖安装"
            }, ensure_ascii=False)
        
        try:
            if action == "generate_document":
                return self._generate_document(**kwargs)
            elif action == "check_status":
                return self._check_status(**kwargs)
            elif action == "list_tasks":
                return self._list_tasks()
            elif action == "get_task_result":
                return self._get_task_result(**kwargs)
            elif action == "delete_task":
                return self._delete_task(**kwargs)
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"不支持的操作: {action}",
                    "supported_actions": [
                        "generate_document",
                        "check_status", 
                        "list_tasks",
                        "get_task_result",
                        "delete_task"
                    ]
                }, ensure_ascii=False)
                
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"操作执行失败: {str(e)}"
            }, ensure_ascii=False)
    
    def _generate_document(self, chat_history: str = "", request: str = "", **kwargs) -> str:
        """生成长文档"""
        if not chat_history and not request:
            return json.dumps({
                "status": "error",
                "message": "请提供chat_history或request参数"
            }, ensure_ascii=False)
        
        try:
            # 创建生成器实例
            generator = LongDocumentGenerator()
            
            # 启动生成任务
            task_id = generator.start_new_job(
                chathistory=chat_history,
                request=request
            )
            
            # 获取任务状态
            task_state = TaskState(task_id)
            if task_state.load():
                result = {
                    "status": "success",
                    "message": "文档生成任务已完成",
                    "task_id": task_id,
                    "task_status": task_state.data.get('status', 'unknown'),
                    "progress": task_state.data.get('progressPercentage', 0),
                    "current_message": task_state.data.get('currentStatusMessage', ''),
                    "last_updated": task_state.data.get('lastUpdatedTimestamp', ''),
                    "created_at": datetime.now().isoformat()
                }
                
                # 如果任务完成，添加结果信息
                if task_state.data.get('status') == 'completed':
                    result.update({
                        "markdown_url": task_state.data.get('markdownPublicUrl', ''),
                        "docx_url": task_state.data.get('docxPublicUrl', ''),
                        "project_name": task_state.data.get('projectName', ''),
                        "final_document": task_state.data.get('finalDocument', '')[:500] + "..." if len(task_state.data.get('finalDocument', '')) > 500 else task_state.data.get('finalDocument', '')
                    })
                
                return json.dumps(result, ensure_ascii=False)
            else:
                return json.dumps({
                    "status": "error",
                    "message": "任务创建失败，无法加载任务状态"
                }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"文档生成失败: {str(e)}"
            }, ensure_ascii=False)
    
    def _check_status(self, task_id: str, **kwargs) -> str:
        """检查任务状态"""
        if not task_id:
            return json.dumps({
                "status": "error",
                "message": "请提供task_id参数"
            }, ensure_ascii=False)
        
        try:
            task_state = TaskState(task_id)
            if task_state.load():
                result = {
                    "status": "success",
                    "task_id": task_id,
                    "task_status": task_state.data.get('status', 'unknown'),
                    "progress": task_state.data.get('progressPercentage', 0),
                    "current_message": task_state.data.get('currentStatusMessage', ''),
                    "last_updated": task_state.data.get('lastUpdatedTimestamp', ''),
                    "project_name": task_state.data.get('projectName', ''),
                    "markdown_url": task_state.data.get('markdownPublicUrl', ''),
                    "docx_url": task_state.data.get('docxPublicUrl', ''),
                    "error_log": task_state.data.get('errorLog', [])
                }
                return json.dumps(result, ensure_ascii=False)
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"任务 {task_id} 不存在"
                }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"检查任务状态失败: {str(e)}"
            }, ensure_ascii=False)
    
    def _list_tasks(self, **kwargs) -> str:
        """列出所有任务"""
        try:
            tasks = []
            
            # 扫描任务目录
            if os.path.exists(self.tasks_dir):
                for filename in os.listdir(self.tasks_dir):
                    if filename.startswith('task_') and filename.endswith('.json'):
                        task_id = filename[5:-5]  # 去掉 'task_' 前缀和 '.json' 后缀
                        
                        try:
                            task_state = TaskState(task_id)
                            if task_state.load():
                                tasks.append({
                                    "task_id": task_id,
                                    "status": task_state.data.get('status', 'unknown'),
                                    "progress": task_state.data.get('progressPercentage', 0),
                                    "project_name": task_state.data.get('projectName', ''),
                                    "last_updated": task_state.data.get('lastUpdatedTimestamp', ''),
                                    "has_docx": bool(task_state.data.get('docxPublicUrl', '')),
                                    "has_markdown": bool(task_state.data.get('markdownPublicUrl', ''))
                                })
                        except Exception as e:
                            print(f"读取任务 {task_id} 失败: {e}")
                            continue
            
            # 按最后更新时间排序
            tasks.sort(key=lambda x: x.get('last_updated', ''), reverse=True)
            
            return json.dumps({
                "status": "success",
                "total_tasks": len(tasks),
                "tasks": tasks
            }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"列出任务失败: {str(e)}"
            }, ensure_ascii=False)
    
    def _get_task_result(self, task_id: str, **kwargs) -> str:
        """获取任务结果"""
        if not task_id:
            return json.dumps({
                "status": "error",
                "message": "请提供task_id参数"
            }, ensure_ascii=False)
        
        try:
            task_state = TaskState(task_id)
            if task_state.load():
                # 只返回已完成的任务结果
                if task_state.data.get('status') != 'completed':
                    return json.dumps({
                        "status": "error",
                        "message": f"任务 {task_id} 尚未完成，当前状态: {task_state.data.get('status', 'unknown')}"
                    }, ensure_ascii=False)
                
                result = {
                    "status": "success",
                    "task_id": task_id,
                    "project_name": task_state.data.get('projectName', ''),
                    "creative_brief": task_state.data.get('creativeBrief', ''),
                    "outline": task_state.data.get('outline', {}),
                    "final_document": task_state.data.get('finalDocument', ''),
                    "markdown_url": task_state.data.get('markdownPublicUrl', ''),
                    "docx_url": task_state.data.get('docxPublicUrl', ''),
                    "completion_time": task_state.data.get('lastUpdatedTimestamp', ''),
                    "initial_request": task_state.data.get('initialRequest', {})
                }
                
                return json.dumps(result, ensure_ascii=False)
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"任务 {task_id} 不存在"
                }, ensure_ascii=False)
                
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"获取任务结果失败: {str(e)}"
            }, ensure_ascii=False)
    
    def _delete_task(self, task_id: str, **kwargs) -> str:
        """删除任务"""
        if not task_id:
            return json.dumps({
                "status": "error",
                "message": "请提供task_id参数"
            }, ensure_ascii=False)
                
        try:
            task_file = os.path.join(self.tasks_dir, f"task_{task_id}.json")
            docx_file = os.path.join(self.tasks_dir, f"task_{task_id}.docx")
            
            deleted_files = []
            
            # 删除JSON文件
            if os.path.exists(task_file):
                os.remove(task_file)
                deleted_files.append("JSON状态文件")
            
            # 删除DOCX文件
            if os.path.exists(docx_file):
                os.remove(docx_file)
                deleted_files.append("DOCX文档文件")
            
            if deleted_files:
                return json.dumps({
                    "status": "success",
                    "message": f"任务 {task_id} 删除成功",
                    "deleted_files": deleted_files
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"任务 {task_id} 不存在"
                }, ensure_ascii=False)
                
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"删除任务失败: {str(e)}"
            }, ensure_ascii=False)

# 工具实例化函数
def create_advanced_long_document_generator_tool():
    """创建高级长文档生成工具实例"""
    return AdvancedLongDocumentGeneratorTool() 

# 测试函数
def test_tool():
    """测试工具功能"""
    tool = AdvancedLongDocumentGeneratorTool()
    
    print("🔧 测试高级长文档生成工具")
    print("=" * 50)
    
    # 测试生成文档
    print("\n📝 测试生成文档...")
    result = tool.execute(
        action="generate_document",
        chat_history="我们讨论了医灵古庙的历史和现状",
        request="请生成一份关于医灵古庙的详细保护报告"
    )
    print(f"生成结果: {result}")
    
    # 解析结果获取task_id
    try:
        result_data = json.loads(result)
        if result_data.get("status") == "success":
            task_id = result_data.get("task_id")
            
            # 测试检查状态
            print(f"\n🔍 测试检查状态 (Task ID: {task_id})...")
            status_result = tool.execute(
                action="check_status",
                task_id=task_id
            )
            print(f"状态结果: {status_result}")
            
            # 测试列出任务
            print("\n📋 测试列出任务...")
            list_result = tool.execute(action="list_tasks")
            print(f"任务列表: {list_result}")
            
    except Exception as e:
        print(f"测试过程中出错: {e}")

if __name__ == "__main__":
    test_tool() 