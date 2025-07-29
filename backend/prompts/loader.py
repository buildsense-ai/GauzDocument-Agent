"""
Prompt加载器
从YAML配置文件加载prompt模板
"""

import yaml
import os
from typing import Dict, Any, Optional

class PromptLoader:
    """Prompt加载器"""
    
    def __init__(self, config_path: str = "react_agent.yaml", few_shot_path: str = "few_shot_examples.yaml"):
        self.config_path = config_path
        self.few_shot_path = few_shot_path
        self.config = None
        self.few_shot_examples = None
        self.load_config()
        self.load_few_shot_examples()
        
    def load_config(self):
        """加载配置文件"""
        try:
            # 🆕 修正路径配置 - react_agent.yaml现在在prompts目录中
            config_paths = [
                self.config_path,                                              # 当前工作目录
                os.path.join(os.path.dirname(__file__), self.config_path),    # prompts目录（同级）
                os.path.join(os.path.dirname(__file__), "..", self.config_path),  # backend目录（上级）
                os.path.join(os.path.dirname(__file__), "..", "..", self.config_path)  # 项目根目录
            ]
            
            for path in config_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        self.config = yaml.safe_load(f)
                    print(f"✅ 加载prompt配置: {path}")
                    return
                    
            # 如果找不到配置文件，使用默认配置
            print(f"⚠️ 未找到配置文件 {self.config_path}，使用默认配置")
            self.config = self._get_default_config()
            
        except Exception as e:
            print(f"❌ 加载prompt配置失败: {e}")
            self.config = self._get_default_config()
    
    def load_few_shot_examples(self):
        """加载few-shot示例"""
        try:
            # 查找few-shot示例文件
            few_shot_paths = [
                self.few_shot_path,                                              # 当前工作目录
                os.path.join(os.path.dirname(__file__), self.few_shot_path),    # prompts目录（同级）
                os.path.join(os.path.dirname(__file__), "..", self.few_shot_path),  # backend目录（上级）
                os.path.join(os.path.dirname(__file__), "..", "..", self.few_shot_path)  # 项目根目录
            ]
            
            for path in few_shot_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        self.few_shot_examples = yaml.safe_load(f)
                    print(f"✅ 加载few-shot示例: {path}")
                    return
                    
            # 如果找不到few-shot文件，使用默认示例
            print(f"⚠️ 未找到few-shot示例文件 {self.few_shot_path}，使用默认示例")
            self.few_shot_examples = self._get_default_few_shot_examples()
            
        except Exception as e:
            print(f"❌ 加载few-shot示例失败: {e}")
            self.few_shot_examples = self._get_default_few_shot_examples()
    
    def _get_default_few_shot_examples(self) -> Dict[str, Any]:
        """获取默认few-shot示例"""
        return {
            "pdf_processing_examples": "📌 **PDF处理示例模板**：\n\n用户提问: \"请解析这个PDF文件\"\n\nThought: 用户明确要求解析PDF文件，我直接调用pdf_parser工具进行解析。\nAction: pdf_parser\nAction Input: {\"project_name\": \"医灵古庙\", \"minio_url\": \"minio://yiling_ancient_temple/文物概况调查.pdf\"}\n\nObservation: {\"success\": true, \"message\": \"PDF解析成功完成\"}\n\nThought: PDF解析已完成，现在可以处理用户的具体问题。\nFinal Answer: PDF文件已成功解析，内容已添加到项目知识库中。您现在可以询问关于PDF内容的问题。",
            "semantic_search_examples": "📌 **语义检索示例模板**：\n\n用户提问: \"医灵古庙的历史背景是什么？\"\n\nThought: 用户询问历史背景，这是知识性问题，需要检索已有文档。\nAction: rag_tool\nAction Input: {\"query\": \"医灵古庙 历史背景 历史沿革\", \"project_name\": \"医灵古庙\", \"top_k\": 5}\n\nObservation: {\"success\": true, \"results\": [{\"content\": \"医灵古庙始建于明朝...\", \"relevance\": 0.95}]}\n\nThought: 检索到相关文档片段，内容与历史背景相关，信息充足。\nFinal Answer: 根据检索到的资料，医灵古庙始建于明朝，具有深厚的历史文化底蕴。",
            "document_generation_examples": "📌 **文档生成示例模板**：\n\n用户: \"帮我生成一份医灵古庙的历史分析报告\"\n\nThought: 用户需要生成历史分析报告。我需要先检索相关历史信息，然后基于检索结果生成文档。\nAction: rag_tool\nAction Input: {\"query\": \"医灵古庙 历史 沿革 建筑特色\", \"project_name\": \"医灵古庙\", \"top_k\": 5}\n\nObservation: {\"success\": true, \"results\": [{\"content\": \"医灵古庙始建于唐贞观年间，历经宋元明清多次重修...\"}]}\n\nThought: 已获取到历史信息，现在调用文档生成工具创建分析报告。\nAction: document_generator\nAction Input: {\"query\": \"基于检索到的历史资料，生成医灵古庙历史分析报告，包含历史沿革、建筑特色、文化价值等内容\", \"project_name\": \"医灵古庙\"}\n\nObservation: {\"success\": true, \"task_id\": \"doc_20241201_001\", \"status\": \"completed\", \"message\": \"历史分析报告生成成功\", \"files\": {\"report\": \"医灵古庙历史分析报告.pdf\"}, \"minio_urls\": {\"report\": \"http://43.139.19.144:9000/documents/yiling_ancient_temple/医灵古庙历史分析报告.pdf\"}}\n\nThought: 文档生成成功！工具返回了完整的文档信息，包括下载链接。我需要在Final Answer中包含这些下载链接。\nFinal Answer: ✅ 医灵古庙历史分析报告生成完成！\n\n**📋 报告内容：**\n- 历史沿革：从唐贞观年间的始建到历代重修\n- 建筑特色：大殿、钟楼、藏经阁的建筑风格分析\n- 文化价值：宗教文化与历史文物价值评估\n- 保护建议：针对古建筑保护的专业建议\n\n**📄 文档下载：**\n**下载链接：** http://43.139.19.144:9000/documents/yiling_ancient_temple/医灵古庙历史分析报告.pdf\n\n报告已成功生成并保存，您可以点击上方链接下载完整的PDF文档。",
            "error_handling_examples": "📌 **错误处理示例模板**：\n\n用户提问: \"解析这个PDF文件\"\n\nThought: 用户明确要求解析PDF文件，我直接调用pdf_parser工具进行解析。\nAction: pdf_parser\nAction Input: {\"project_name\": \"医灵古庙\", \"minio_url\": \"minio://yiling_ancient_temple/文档.pdf\"}\n\nObservation: {\"success\": false, \"error_type\": \"api_error\", \"http_status\": 500, \"error_message\": \"PDF processing service unavailable\"}\n\nThought: PDF解析服务出现错误，我需要告知用户服务暂时不可用。\nFinal Answer: 抱歉，PDF解析服务暂时不可用。请稍后重试，或联系系统管理员检查服务状态。"
        }
    
    def get_few_shot_examples(self) -> str:
        """获取所有few-shot示例"""
        if not self.few_shot_examples:
            return ""
        
        examples = []
        for key, value in self.few_shot_examples.items():
            if isinstance(value, str):
                examples.append(value)
        
        return "\n\n".join(examples)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "system_prompt_template": """你是一个ReAct (Reasoning and Acting) 智能代理。你需要通过交替进行推理(Thought)和行动(Action)来解决问题。

⚠️ **重要：你必须优先使用工具来解决问题，而不是直接给出答案！**

可用工具:
{tools_description}

🎯 **核心工具使用指南:**

**工具1: 📄 PDF解析处理 - `pdf_parser`**
- 🔍 **使用条件**: 用户需要解析PDF文件、提取PDF内容、分析PDF结构
- 📋 **功能**: 智能提取PDF中的文本、图片、表格并结构化重组
- 🎯 **关键词**: 解析pdf、提取pdf、pdf解析、pdf内容、pdf文本、pdf分析
- ⚙️ **参数**: pdf_path="文件路径", action="parse"

**工具2: 🔍 RAG智能检索 - `rag_tool`**
- 🔍 **使用条件**: 用户询问知识、查找信息、需要检索相关内容
- 📋 **功能**: 基于项目的智能检索，自动过滤项目相关内容
- 🎯 **关键词**: 查询、搜索、检索、相关信息、知识库
- ⚙️ **参数**: query="查询内容", top_k=5, project_name="项目名"

**工具3: 📝 文档生成 - `document_generator`**
- 🔍 **使用条件**: 用户需要生成文档、报告、总结等
- 📋 **功能**: 生成各种格式的文档
- 🎯 **关键词**: 生成文档、创建报告、输出文件、导出
- ⚙️ **参数**: content="内容", format="pdf", template="default"

**执行格式要求:**
每次回复必须严格按照以下格式：

Thought: [详细分析问题和决策过程]
Action: [工具名称]
Action Input: [JSON格式的参数]
Observation: [等待工具执行结果]

如果需要继续，重复上述循环。
当获得足够信息后，给出：
Final Answer: [最终回答]

**🚫 严禁编造结果** - 只有当工具返回"success": true, "status": "completed"时，才能给出Final Answer！"""
        }
    
    def get_system_prompt(self, 
                         project_context: Optional[Dict[str, Any]] = None,
                         agent=None) -> str:
        """获取系统提示词，包含动态项目状态上下文"""
        if not self.config:
            return "系统提示词加载失败"
            
        # 从agent获取工具描述
        tools_description = ""
        if agent and hasattr(agent, 'tool_registry'):
            tools_description = agent.tool_registry.get_tools_description()
        else:
            tools_description = "工具加载中..."
        
        # 获取few-shot示例
        few_shot_examples = self.get_few_shot_examples()
        
        # 🆕 动态注入项目状态上下文
        project_status_context = ""
        if agent and hasattr(agent, 'project_state_manager'):
            project_id = self._get_current_project_id(project_context)
            if project_id:
                project_status_context = agent.project_state_manager.get_project_context_for_prompt(project_id)
        
        # 如果没有项目状态，使用默认提示
        if not project_status_context:
            project_status_context = "📁 当前项目状态: 项目信息获取中..."
        
        # 获取系统提示词模板
        template = self.config.get("system_prompt_template", "")
        
        # 格式化系统提示词
        formatted_prompt = template.format(
            tools_description=tools_description,
            few_shot_examples=few_shot_examples,
            max_iterations=getattr(agent, 'max_iterations', 10) if agent else 10
        )
        
        # 在系统提示词开头注入项目状态
        final_prompt = f"{project_status_context}\n\n{formatted_prompt}"
        
        return final_prompt
    
    def _get_current_project_id(self, project_context: Optional[Dict[str, Any]]) -> str:
        """获取当前项目ID"""
        if not project_context:
            return None
        return project_context.get('project_id') or project_context.get('id')
    
    def get_prompt(self, category: str, template_name: str) -> str:
        """
        获取特定的prompt模板
        
        Args:
            category: 模板类别 (如 "system")
            template_name: 模板名称 (如 "memory_context_template")
        
        Returns:
            str: 模板内容
        """
        if not self.config:
            return ""
            
        # 直接从配置中获取模板
        template = self.config.get(template_name, "")
        
        if not template:
            # 如果模板不存在，返回默认模板
            if template_name == "memory_context_template":
                return "相关历史经验:\n{context}"
            elif template_name == "user_question_template":
                return "问题: {problem}"
            else:
                return ""
        
        return template
    
    def get_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self.config

# 全局实例
_prompt_loader = None

def get_prompt_loader() -> PromptLoader:
    """获取全局prompt加载器实例"""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader 