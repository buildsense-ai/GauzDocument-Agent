# 文件名: main.py
# -*- coding: utf-8 -*-

"""
main.py

项目的执行入口。
负责启动生成任务并演示如何轮询任务状态。
"""

import json
import os
from typing import Dict, Any, Optional

# --- 从其他模块导入依赖 ---
from generator import LongDocumentGenerator, TaskState
from config import Config


def get_task_status(task_id_to_check: str) -> Optional[Dict[str, Any]]:
    """
    模拟轮询API `GET /api/tasks/{taskId}/status` 的后端实现。
    它从任务状态文件中读取并返回一个简化的状态摘要。
    """
    task_state = TaskState(task_id_to_check)
    if task_state.load():
        # [变更] 在返回数据中也加入URL
        return {
            "taskId": task_state.data['taskId'],
            "overallStatus": task_state.data['status'],
            "progressPercentage": task_state.data['progressPercentage'],
            "message": task_state.data['currentStatusMessage'],
            "lastUpdated": task_state.data.get('lastUpdatedTimestamp', 'N/A'),
            "mdPublicUrl": task_state.data.get('mdPublicUrl', '')
        }
    return None


if __name__ == "__main__":

    print(">>> 启动一个新的长文生成任务...")
    generator = LongDocumentGenerator()
    initial_chathistory = "我们之前讨论了医伶古庙。"
    initial_request = "请帮我，并生成关于此古庙一份详细的保护报告。"

    # 在真实服务中，`start_new_job` 会被后台任务队列执行。
    # 这里我们直接同步运行以完成整个流程。
    task_id = generator.start_new_job(initial_chathistory, initial_request)
    print(f"\n>>> 任务执行完毕。任务ID: {task_id}")

    print("\n\n>>> 模拟客户端轮询最终状态...")
    final_status = get_task_status(task_id)

    if final_status:
        print("轮询API返回的最终状态:")
        print(json.dumps(final_status, indent=2, ensure_ascii=False))

    task_file_path = os.path.join(Config.TASKS_DIR, f"task_{task_id}.json")
    print(f"\n完整的任务状态和最终文档内容已保存在: {task_file_path}")

