"""
总监Agent (Orchestrator Agent)

负责最高层的规划，特别是生成目标文档的大纲。
"""

import json
from typing import List, Dict, Any

from .mock_retrieval_tool import MockKnowledgeSearchTool
# from ..deepseek_client import DeepSeekClient # 假设你有一个LLM客户端

class OrchestratorAgent:
    """
    规划和编排整个长文生成流程的Agent。
    """
    def __init__(self):
        # 在真实场景中，这里会注入一个真正的LLM客户端
        # self.llm_client = DeepSeekClient()
        self.retrieval_tool = MockKnowledgeSearchTool()
        self.system_prompt = """
你是一位顶级的项目总监和规划师，擅长高屋建瓴地进行结构设计。
你的任务是基于源文档的核心结构，为一份新的、主题相关的文档设计一个专业、详细、逻辑清晰的章节大纲。
你必须严格按照指定的JSON格式输出。
"""
        print("👨‍💼 [OrchestratorAgent] 初始化成功。")

    def generate_outline(self, source_document_id: str, target_document_description: str) -> List[Dict[str, Any]]:
        """
        生成目标文档的大纲。

        Args:
            source_document_id: 源文档的ID，用于检索。
            target_document_description: 对目标文档的简单描述，如“一份关于医灵古庙的文物评估方案”。

        Returns:
            一个代表大纲的字典列表，例如 [{'chapter': '1.0', 'title': '...'}, ...]。
        """
        print(f"👨‍💼 [OrchestratorAgent] 开始为 '{target_document_description}' 生成大纲...")

        # 1. 调用检索工具，获取源文档的整体结构
        print("👨‍💼 [OrchestratorAgent] 步骤1: 检索源文档的核心结构...")
        retrieval_result_json = self.retrieval_tool.execute(
            queries=["文档目录", "文档结构"],
            filters={"document_id": source_document_id}
        )
        retrieval_result = json.loads(retrieval_result_json)
        source_structure = retrieval_result.get("retrieved_items", [])

        if not source_structure:
            print("👨‍💼 [OrchestratorAgent] 警告: 未能从源文档检索到结构信息。将尝试生成通用大纲。")

        # 2. 构建Prompt，请求LLM生成大纲
        print("👨‍💼 [OrchestratorAgent] 步骤2: 请求LLM设计新大纲...")
        generation_prompt = f"""
源文档的核心章节结构如下:
{json.dumps(source_structure, indent=2, ensure_ascii=False)}

请基于以上源文档结构，为一份新的文档《{target_document_description}》设计一个专业、详细的大纲。

请以JSON格式返回一个包含章节号和标题的列表。例如:
[
  {{"chapter": "1.0", "title": "引言"}},
  {{"chapter": "2.0", "title": "文物价值评估"}},
  {{"chapter": "2.1", "title": "历史价值"}}
]
"""
        
        # --- 真实LLM调用发生在这里 ---
        # response = self.llm_client.generate(self.system_prompt, generation_prompt)
        # return json.loads(response)
        
        # --- 使用硬编码的模拟输出来进行开发 ---
        print("👨‍💼 [OrchestratorAgent] (模拟LLM) 生成大纲...")
        mock_outline = [
            {"chapter": "1.0", "title": "项目概况与评估依据"},
            {"chapter": "2.0", "title": "文物本体现状评估"},
            {"chapter": "3.0", "title": "核心价值评估"},
            {"chapter": "3.1", "title": "历史与艺术价值评估"},
            {"chapter": "3.2", "title": "结构安全性评估"},
            {"chapter": "4.0", "title": "保护建议与结论"}
        ]
        print(f"👨‍💼 [OrchestratorAgent] 大纲生成成功，包含 {len(mock_outline)} 个章节。")
        return mock_outline

