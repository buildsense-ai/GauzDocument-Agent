"""
经理Agent (Section Writer Agent)

负责为大纲中的某一个具体章节，搜集所有必要的资料。
"""

import json
from typing import List, Dict, Any

from .mock_retrieval_tool import MockKnowledgeSearchTool
# from ..deepseek_client import DeepSeekClient

class SectionWriterAgent:
    """
    为一个章节的写作搜集和准备上下文的Agent。
    """
    def __init__(self, source_document_id: str):
        # self.llm_client = DeepSeekClient()
        self.retrieval_tool = MockKnowledgeSearchTool()
        self.source_document_id = source_document_id
        self.system_prompt = """
你是一位极其勤奋和聪明的首席研究员。
你的任务是为一个特定的章节标题，思考所有可能需要的信息，然后使用检索工具，从知识库中搜集所有相关的文本、图片和表格。
"""
        print("🧑‍🔬 [SectionWriterAgent] 初始化成功。")

    def gather_context_for_section(self, section_title: str) -> List[Dict[str, Any]]:
        """
        为一个章节搜集所有相关的上下文。

        Args:
            section_title: 章节的标题，例如 "3.2 结构安全性评估"。

        Returns:
            一个包含所有检索到的项目（文本、图片、表格）的列表。
        """
        print(f"🧑‍🔬 [SectionWriterAgent] 开始为章节 '{section_title}' 收集资料...")

        # 1. (Reasoning) 请求LLM进行“查询扩展”，思考需要哪些具体信息
        print(f"🧑‍🔬 [SectionWriterAgent] 步骤1: 思考需要哪些具体信息...")
        expansion_prompt = f"""
为了撰写关于“{section_title}”的章节，我需要从源文档中查找哪些具体的关键词或主题？
请列出3-5个最核心的搜索查询，每个一行。
"""
        # --- 真实LLM调用 ---
        # expanded_queries_str = self.llm_client.generate(self.system_prompt, expansion_prompt)
        # expanded_queries = expanded_queries_str.strip().split('\n')

        # --- 模拟LLM输出 ---
        print(f"🧑‍🔬 [SectionWriterAgent] (模拟LLM) 生成扩展查询...")
        if "结构" in section_title:
            expanded_queries = ["承重结构体系", "木材材料规格", "历史维修记录", "结构连接方式"]
        else:
            expanded_queries = [section_title] # 默认使用原标题
        
        print(f"🧑‍🔬 [SectionWriterAgent] 扩展查询为: {expanded_queries}")

        # 2. (Acting) 使用扩展后的查询，多次调用检索工具
        print(f"🧑‍🔬 [SectionWriterAgent] 步骤2: 使用扩展查询进行检索...")
        all_retrieved_items = []
        
        # 检索文本
        text_results_json = self.retrieval_tool.execute(
            queries=expanded_queries,
            search_mode="text_only",
            filters={"document_id": self.source_document_id}
        )
        all_retrieved_items.extend(json.loads(text_results_json).get("retrieved_items", []))

        # 检索媒体
        media_results_json = self.retrieval_tool.execute(
            queries=expanded_queries,
            search_mode="media_only", # 假设有这个模式
            filters={"document_id": self.source_document_id}
        )
        all_retrieved_items.extend(json.loads(media_results_json).get("retrieved_items", []))

        print(f"🧑‍🔬 [SectionWriterAgent] 资料收集完毕，共找到 {len(all_retrieved_items)} 条相关信息。")
        return all_retrieved_items

