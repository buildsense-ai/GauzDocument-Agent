"""
模拟的知识检索工具 (Mock Knowledge Search Tool)

这个工具是并行开发的关键，它模拟了真实的RAG检索工具的行为。
它的输出格式是我们与长文生成Agent签订的“合同”。
"""

import json
from typing import List, Dict, Any, Optional

class MockKnowledgeSearchTool:
    """
    一个模拟的知识检索工具，用于在真实RAG系统完成前，支持生成Agent的开发。
    """
    def __init__(self):
        print("🤖 [Mock Tool] 初始化成功。我将返回预设的、结构正确的假数据。")

    def execute(self, queries: List[str], search_mode: str = "text_and_media", filters: Optional[Dict] = None, **kwargs) -> str:
        """
        执行模拟的检索操作。

        Args:
            queries: 搜索查询列表。
            search_mode: 搜索模式 ('text_only', 'images_only', 'text_and_media').
            filters: 元数据过滤器。

        Returns:
            str: JSON格式的检索结果。
        """
        print(f"🤖 [Mock Tool] 收到请求: queries={queries}, mode={search_mode}, filters={filters}")

        # 场景1：查询文档结构或目录
        if any("目录" in q or "结构" in q or "大纲" in q for q in queries):
            print("🤖 [Mock Tool] 模拟命中'目录'查询...")
            mock_response = {
                "status": "success",
                "retrieved_items": [
                    {
                        "type": "chapter_summary",
                        "relevance_score": 0.95,
                        "content": {
                            "chapter_id": "1.0",
                            "chapter_title": "项目背景与目标",
                            "content_summary": "本章主要介绍了医灵古庙的历史背景、现状及其保护与修复的设计目标。"
                        },
                        "metadata": {}
                    },
                    {
                        "type": "chapter_summary",
                        "relevance_score": 0.94,
                        "content": {
                            "chapter_id": "2.0",
                            "chapter_title": "建筑设计理念",
                            "content_summary": "本章阐述了本次修复工程遵循的'修旧如旧'与'最小干预'原则，并结合了现代安全标准。"
                        },
                        "metadata": {}
                    },
                    {
                        "type": "chapter_summary",
                        "relevance_score": 0.93,
                        "content": {
                            "chapter_id": "3.0",
                            "chapter_title": "结构与材料",
                            "content_summary": "本章详细分析了古庙的木结构体系，并提出了传统材料的选型与处理方案。"
                        },
                        "metadata": {}
                    }
                ],
                "search_summary": "找到了3个核心章节摘要。"
            }
            return json.dumps(mock_response, ensure_ascii=False)

        # 场景2：查询具体的技术细节，如“承重结构”
        if any("承重" in q or "材料" in q for q in queries):
            print("🤖 [Mock Tool] 模拟命中'承重结构'查询...")
            mock_response = {
                "status": "success",
                "retrieved_items": [
                    {
                        "type": "text_chunk",
                        "relevance_score": 0.92,
                        "content": "医灵古庙的核心承重结构采用传统的抬梁式木构架，主要材料为本地产的优质杉木。所有替换木料均需经过严格的防腐防蛀处理。",
                        "metadata": {"chunk_id": 101, "chapter_title": "3.1 承重结构体系"}
                    },
                    {
                        "type": "image",
                        "relevance_score": 0.88,
                        "content": {
                            "image_path": "mock/images/structure_diagram.png",
                            "ai_description": "医灵古庙木构架抬梁式结构示意图。"
                        },
                        "metadata": {"page_number": 25, "chapter_title": "3.1 承重结构体系"}
                    },
                    {
                        "type": "table",
                        "relevance_score": 0.85,
                        "content": {
                            "table_path": "mock/tables/materials_spec.png",
                            "ai_description": "主要木材规格与力学性能参数表。"
                        },
                        "metadata": {"page_number": 28, "chapter_title": "3.2 材料选型"}
                    }
                ],
                "search_summary": "找到了1个文本块，1张图片和1个表格。"
            }
            return json.dumps(mock_response, ensure_ascii=False)

        # 默认场景：未命中
        print("🤖 [Mock Tool] 未命中特定场景，返回空结果。")
        return json.dumps({"status": "success", "retrieved_items": [], "search_summary": "未找到相关内容。"}, ensure_ascii=False)

