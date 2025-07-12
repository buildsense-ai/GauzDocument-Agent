"""
Tools for ReAct Agent - 核心五工具架构
专注于文档处理和图片RAG的五个核心工具
"""
import os
import json
from typing import Dict, Any, List, Optional

# 导入工具基类
from base_tool import Tool

# 核心五工具架构

class ToolRegistry:
    """工具注册表 - 核心五工具"""
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._register_core_tools()
    
    def _register_core_tools(self):
        """注册核心工具"""
        core_tools = []
        
        # 1. RAG工具 - 文档embedding处理和智能搜索
        if RAGTool:
            try:
                rag_tool = RAGTool()
                core_tools.append(rag_tool)
                print("✅ RAG工具加载成功")
            except Exception as e:
                print(f"❌ RAG工具加载失败: {e}")
        else:
            print("❌ RAG工具类不可用")
        
        # 2. 图片上传功能已整合到RAG工具中
        
        # 3. PDF解析工具 - 智能提取PDF中的文本、图片和表格
        if PDFParserTool:
            try:
                pdf_parser_tool = PDFParserTool()
                core_tools.append(pdf_parser_tool)
                print("✅ PDF解析工具加载成功")
            except Exception as e:
                print(f"❌ PDF解析工具加载失败: {e}")
        else:
            print("❌ PDF解析工具类不可用")
        
        # 4. PDF Embedding功能已整合到RAG工具中
        
        # 5. 高级长文档生成工具 - AI驱动的专业长篇文档智能生成器
        if AdvancedLongDocumentGeneratorTool:
            try:
                advanced_long_document_generator_tool = AdvancedLongDocumentGeneratorTool()
                core_tools.append(advanced_long_document_generator_tool)
                print("✅ 高级长文档生成工具加载成功")
            except Exception as e:
                print(f"❌ 高级长文档生成工具加载失败: {e}")
        else:
            print("❌ 高级长文档生成工具类不可用")
        
        # 注册所有工具
        for tool in core_tools:
            self.register_tool(tool)
        
        print(f"🎯 核心工具架构初始化完成，共加载 {len(core_tools)} 个工具")
    
    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[Dict[str, str]]:
        """列出所有工具"""
        return [
            {"name": tool.name, "description": tool.description}
            for tool in self.tools.values()
        ]
    
    def execute_tool(self, name: str, **kwargs) -> str:
        """执行工具"""
        tool = self.get_tool(name)
        if tool:
            return tool.execute(**kwargs)
        else:
            return f"❌ 未找到工具: {name}"
    
    def get_tool_summary(self) -> str:
        """获取工具摘要"""
        summary = "🔧 ReactAgent系统全套工具:\n\n"
        
        tool_descriptions = {
            "rag_tool": "📚 统一RAG工具 - 文档/图片向量化存储和智能检索",
            "pdf_parser": "📄 PDF智能解析 - 提取文本、图片、表格并结构化重组",
            "advanced_long_document_generator": "🚀 高级长文档生成工具 - AI驱动的专业长篇文档智能生成器",
        }
        
        for tool_name, description in tool_descriptions.items():
            if tool_name in self.tools:
                summary += f"✅ {description}\n"
            else:
                summary += f"❌ {description} (未加载)\n"
        
        summary += f"\n📊 总计: {len(self.tools)} 个工具已加载"
        summary += "\n\n🎯 系统核心功能："
        summary += "\n🖼️ 图片RAG管理 → 📄 PDF智能解析 → 📚 知识库检索"
        summary += "\n\n✅ 全套工具已启用，ReactAgent系统完全就绪！"
        return summary

def create_core_tool_registry(deepseek_client=None) -> ToolRegistry:
    """创建核心工具注册表"""
    registry = ToolRegistry()
    
    # 如果提供了deepseek_client，为RAG工具设置AI客户端 (暂时注释，专注测试PDF解析)
    # if deepseek_client:
    #     rag_tool = registry.get_tool("rag_tool")
    #     if rag_tool and hasattr(rag_tool, 'field_processor'):
    #         field_processor = getattr(rag_tool, 'field_processor')
    #         if hasattr(field_processor, 'deepseek_client'):
    #             field_processor.deepseek_client = deepseek_client
    #             print("🤖 RAG工具已配置AI客户端")
    print("⚠️ PDF解析测试模式，RAG工具配置已暂时跳过")
    
    return registry

# 系统核心功能使用指南
SYSTEM_FUNCTIONS_GUIDE = """
🎯 ReactAgent系统三大核心工具架构:

**工具1: 📄 PDF解析工具**
工具名: pdf_parser
- 参数: pdf_path="PDF文件路径", action="parse/list_models/get_stats", output_dir="输出目录", model_name="模型名称"
- 功能: 智能提取PDF中的文本、图片、表格，并重新组织为结构化数据
- 处理逻辑:
  * PDF解析 → 文本提取 → 图片/表格识别 → LLM内容重组 → 结构化JSON输出
- 适用场景: PDF文档内容提取、学术论文分析、技术文档处理、图片表格提取

**工具2: 📚 统一RAG工具**
工具名: rag_tool
- 参数: action="upload/upload_image/search/search_images/search_tables", file_path="文档路径", query="搜索内容"
- 功能: 文档和图片的统一向量化存储、语义搜索、专门检索
- 处理逻辑:
  * 文档上传 → 向量化存储 → 语义检索
  * 图片上传 → AI描述生成 → 向量化存储 → 文本查询检索相关图片
- 适用场景: 统一知识库管理、多模态内容检索、专业搜索

**工具3: 🚀 高级长文档生成工具**
工具名: advanced_long_document_generator
- 参数: action="generate_document/check_status/list_tasks/get_task_result/delete_task", chat_history="对话历史", request="生成要求", task_id="任务ID"
- 功能: AI驱动的专业长篇文档智能生成器、状态机驱动的多阶段生成流程、向量数据库知识检索整合
- 处理逻辑:
  * 创作指令分析 → 初始大纲生成 → 多轮大纲精炼 → 分章节内容生成 → 文档整合 → 格式转换 → 云端上传
- 适用场景: 专业报告生成、技术文档创建、研究报告撰写、项目方案制定

🔄 **工具间协作流程:**
PDF解析 → 统一RAG(向量化存储) → 文档生成(知识检索+AI创作)
"""

try:
    from rag_tool_chroma import RAGTool
except ImportError:
    try:
        from .rag_tool_chroma import RAGTool
    except ImportError:
        RAGTool = None

try:
    from pdf_parser_tool import PDFParserTool
except ImportError:
    try:
        from .pdf_parser_tool import PDFParserTool
    except ImportError:
        PDFParserTool = None

# 已删除的工具：
# - image_rag_tool: 图片上传功能已整合到RAG工具中
# - pdf_embedding_tool: PDF embedding功能已整合到RAG工具中

try:
    from advanced_long_document_generator_tool import AdvancedLongDocumentGeneratorTool
except ImportError:
    try:
        from .advanced_long_document_generator_tool import AdvancedLongDocumentGeneratorTool
    except ImportError:
        AdvancedLongDocumentGeneratorTool = None

def register_tools(agent):
    """注册所有工具到ReAct Agent"""
    tools = [
        {
            "name": "rag_tool",
            "description": """📚 RAG文档处理工具 - 专业知识库embedding和检索系统

核心功能：
- 文档embedding向量化（支持DOC/DOCX/PDF/TXT等格式）
- 基于Chroma向量数据库的语义检索  
- 多模态内容提取和索引
- 智能文档相似度搜索
- 🆕 PDF解析后文件夹处理（parsed_content.json自动embedding）

适用场景：当需要对大量文档进行知识管理、语义搜索或构建专业知识库时使用""",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["upload", "search", "fill_fields", "list", "clear", "process_parsed_folder"],
                        "description": "操作类型：upload(上传文档), search(搜索), fill_fields(填充模板字段), list(列出文档), clear(清空), process_parsed_folder(处理PDF解析文件夹)"
                    },
                    "file_path": {
                        "type": "string", 
                        "description": "文档文件路径（upload时需要）"
                    },
                    "query": {
                        "type": "string",
                        "description": "搜索查询语句（search时需要）"
                    },
                    "folder_path": {
                        "type": "string",
                        "description": "PDF解析后的文件夹路径（process_parsed_folder时需要）"
                    },
                    "project_name": {
                        "type": "string",
                        "description": "项目名称（process_parsed_folder时可选）"
                    },
                    "template_fields_json": {
                        "type": "object",
                        "description": "模板字段JSON（fill_fields时需要）"
                    },
                    "filename": {
                        "type": "string",
                        "description": "文件名（upload时可选）"
                    }
                },
                "required": ["action"]
            },
            "function": lambda **kwargs: RAGTool().execute(**kwargs)
        },

        {
            "name": "pdf_parser",
            "description": """📄 PDF智能解析工具 - 提取文本、图片、表格并结构化重组

核心功能：
- 📄 智能PDF解析：使用Docling和LLM技术提取PDF内容
- 🖼️ 图片识别和保存：自动识别并保存PDF中的图片
- 📊 表格识别和保存：自动识别并保存PDF中的表格
- 🧠 内容重组：使用LLM重新组织内容为结构化数据
- 📋 多模型支持：支持GPT-4o、Claude-3.5等多种AI模型
- 📊 统计信息：提供详细的解析统计和内容分析

输出文件：
- parsed_content.json: 结构化文本内容
- images.json: 图片信息
- tables.json: 表格信息
- summary.json: 汇总信息
- picture-*.png: 提取的图片文件
- table-*.png: 提取的表格文件

适用场景：PDF文档内容提取、学术论文分析、技术文档处理、图片表格提取""",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_path": {
                        "type": "string",
                        "description": "PDF文件路径"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["parse", "list_models", "get_stats"],
                        "default": "parse",
                        "description": "操作类型：parse(解析PDF), list_models(列出可用模型), get_stats(获取统计信息)"
                    },
                    "output_dir": {
                        "type": "string",
                        "default": "parser_output",
                        "description": "输出目录路径"
                    },
                    "model_name": {
                        "type": "string",
                        "default": "gpt-4o",
                        "description": "使用的AI模型名称"
                    }
                },
                "required": []
            },
            "function": lambda **kwargs: PDFParserTool().execute(**kwargs)
        },

        # 已删除的工具：
        # - image_rag_tool: 图片上传功能已整合到统一RAG工具中
        # - pdf_embedding: PDF embedding功能已整合到统一RAG工具中
        
        {
            "name": "advanced_long_document_generator",
            "description": """🚀 高级长文档生成工具 - AI驱动的专业长篇文档智能生成器

核心功能：
- 🧠 智能大纲生成与多轮精炼：AI自动规划文档结构，多轮迭代优化
- 🔍 向量数据库知识检索整合：实时检索相关知识丰富内容
- 📝 多阶段内容生成流程：分章节逐步生成，确保逻辑连贯
- 🎯 状态机驱动的稳定执行：完整的流程控制，支持断点续传
- 📊 多格式输出 (JSON/DOCX)：同时输出JSON状态和DOCX文档
- ☁️ 云存储自动上传：自动上传到MinIO云存储并生成访问链接
- 🔧 完整的错误处理和状态管理：可靠的任务管理和错误恢复

工作流程：
1. 创作指令分析 → 初始大纲生成 → 多轮大纲精炼
2. 分章节内容生成 → 文档整合 → 格式转换 → 云端上传

适用场景：专业报告生成、技术文档创建、研究报告撰写、项目方案制定""",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["generate_document", "check_status", "list_tasks", "get_task_result", "delete_task"],
                        "description": "操作类型：generate_document(生成文档), check_status(查询状态), list_tasks(列出任务), get_task_result(获取结果), delete_task(删除任务)"
                    },
                    "chat_history": {
                        "type": "string",
                        "description": "对话历史上下文（生成操作时提供）"
                    },
                    "request": {
                        "type": "string",
                        "description": "生成要求描述（生成操作必需）"
                    },
                    "task_id": {
                        "type": "string",
                        "description": "任务ID（状态查询、获取结果、删除任务时需要）"
                    }
                },
                "required": ["action"]
            },
            "function": lambda **kwargs: AdvancedLongDocumentGeneratorTool().execute(**kwargs)
        }
    ]
    
    for tool in tools:
        agent.register_tool(
            name=tool["name"],
            description=tool["description"], 
            parameters=tool["parameters"],
            function=tool["function"]
        )
    
    print(f"✅ 已注册{len(tools)}个核心工具：")
    print("   📚 rag_tool - 统一RAG工具（文档/图片向量化和检索）")
    print("   📄 pdf_parser - PDF智能解析工具")
    print("   🚀 advanced_long_document_generator - 高级长文档生成工具（AI驱动专业创作）") 