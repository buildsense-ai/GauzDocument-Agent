"""
PDF解析工具 - 基于Paper2Poster的智能PDF解析功能
支持多种AI模型，智能提取PDF中的文本、图片和表格
利用Paper2Poster项目中的现有资源和库
"""

import os
import json
import sys
import random
import re
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 定义默认的解析输出目录
DEFAULT_PARSER_OUTPUT_DIR = project_root / "parser_output"

# 添加Paper2Poster路径
paper2poster_dir = project_root / "Paper2Poster" / "Paper2Poster"
if paper2poster_dir.exists():
    # 添加Paper2Poster主目录
    p2p_path = str(paper2poster_dir)
    if p2p_path not in sys.path:
        sys.path.insert(0, p2p_path)
    print(f"✅ 添加Paper2Poster路径: {p2p_path}")
    
    # 检查是否存在现成的解析器
    openrouter_parser = paper2poster_dir / "parser_agent_openrouter.py"
    simple_parser = paper2poster_dir / "simple_docling_parser.py"
    
    if openrouter_parser.exists():
        print(f"✅ 发现OpenRouter解析器: {openrouter_parser}")
    if simple_parser.exists():
        print(f"✅ 发现简单解析器: {simple_parser}")
else:
    print("❌ 未找到Paper2Poster目录")

# 尝试导入Paper2Poster的依赖
try:
    # 首先尝试从Paper2Poster导入现有的解析器
    sys.path.insert(0, str(paper2poster_dir))
    
    # 导入基础依赖
    from dotenv import load_dotenv
    from pathlib import Path
    import subprocess
    
    # 尝试导入camel和docling（来自Paper2Poster）
    from camel.models import ModelFactory
    from camel.agents import ChatAgent
    from camel.types import ModelPlatformType
    from docling_core.types.doc.document import PictureItem, TableItem
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from PIL import Image
    
    DEPENDENCIES_AVAILABLE = True
    print("✅ PDF解析依赖库检查通过（使用Paper2Poster本地库）")
    
    # 尝试导入Paper2Poster的现有解析器
    try:
        import importlib.util
        
        # 动态导入parser_agent_openrouter
        if (paper2poster_dir / "parser_agent_openrouter.py").exists():
            spec = importlib.util.spec_from_file_location(
                "parser_agent_openrouter", 
                paper2poster_dir / "parser_agent_openrouter.py"
            )
            parser_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(parser_module)
            
            # 获取OpenRouterParserAgent类
            OpenRouterParserAgent = getattr(parser_module, 'OpenRouterParserAgent', None)
            if OpenRouterParserAgent:
                print("✅ 成功导入Paper2Poster的OpenRouterParserAgent")
            else:
                print("❌ 未找到OpenRouterParserAgent类")
        
        # 动态导入simple_docling_parser
        if (paper2poster_dir / "simple_docling_parser.py").exists():
            spec_simple = importlib.util.spec_from_file_location(
                "simple_docling_parser", 
                paper2poster_dir / "simple_docling_parser.py"
            )
            simple_module = importlib.util.module_from_spec(spec_simple)
            spec_simple.loader.exec_module(simple_module)
            
            # 获取简单解析函数
            parse_pdf_simple = getattr(simple_module, 'parse_pdf_simple', None)
            if parse_pdf_simple:
                print("✅ 成功导入Paper2Poster的parse_pdf_simple")
        
        PAPER2POSTER_PARSERS_AVAILABLE = True
    except Exception as e:
        print(f"⚠️ Paper2Poster解析器导入失败: {e}")
        PAPER2POSTER_PARSERS_AVAILABLE = False
        OpenRouterParserAgent = None
        parse_pdf_simple = None
        
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    PAPER2POSTER_PARSERS_AVAILABLE = False
    print(f"❌ PDF解析依赖库不可用: {e}")
    print("提示：请确认Paper2Poster目录存在且包含camel和docling库")
    OpenRouterParserAgent = None
    parse_pdf_simple = None

# 尝试导入torch（可选）
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("PyTorch不可用，某些高级功能可能受限")

from src.base_tool import Tool
# --- Import the embedding service ---
try:
    from src.pdf_embedding_service import PDFEmbeddingService
    EMBEDDING_SERVICE_AVAILABLE = True
    print("✅ PDF Embedding Service可用")
except ImportError as e:
    EMBEDDING_SERVICE_AVAILABLE = False
    print(f"⚠️ PDF Embedding Service不可用: {e}")

# --- Import the OpenRouter client for image description ---
try:
    from src.openrouter_client import OpenRouterClient
    OPENROUTER_CLIENT_AVAILABLE = True
    print("✅ OpenRouter Client可用")
except ImportError as e:
    OPENROUTER_CLIENT_AVAILABLE = False
    print(f"⚠️ OpenRouter Client不可用: {e}")

# 导入prompt加载器
try:
    from src.prompts.loader import get_prompt_loader
    PROMPT_LOADER_AVAILABLE = True
except ImportError:
    PROMPT_LOADER_AVAILABLE = False


# 加载环境变量
if DEPENDENCIES_AVAILABLE:
    load_dotenv()

# 配置常量
IMAGE_RESOLUTION_SCALE = 5.0

# 支持的模型列表（从Paper2Poster继承）
SUPPORTED_MODELS = [
    "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo",
    "claude-3.5-sonnet", "claude-3-haiku", 
    "llama-3.1-8b", "llama-3.1-70b",
    "gemini-pro", "qwen2.5-7b", "qwen2.5-32b"
]

class OpenRouterParserAgent:
    """支持OpenRouter的解析智能体类"""
    
    def __init__(self, model_name: str = "gpt-4o"):
        """
        初始化解析智能体
        
        Args:
            model_name: 使用的模型名称，支持OpenRouter上的多种模型
        """
        self.model_name = model_name
        self.actor_model = None
        self.actor_agent = None
        self.doc_converter = None
        
        if DEPENDENCIES_AVAILABLE:
            self._init_components()
    
    def _init_components(self):
        """初始化组件"""
        try:
            # 初始化Docling转换器
            self._init_docling_converter()
            
            # 初始化AI模型
            self._init_ai_model()
            
            print(f"✅ OpenRouter解析智能体初始化成功，使用模型: {self.model_name}")
        except Exception as e:
            print(f"❌ OpenRouter解析智能体初始化失败: {e}")
    
    def _init_docling_converter(self):
        """初始化Docling转换器"""
        try:
            # 设置本地模型路径
            models_cache_dir = Path("models_cache")
            if models_cache_dir.exists():
                artifacts_path = str(models_cache_dir.absolute())
            else:
                artifacts_path = None

            pipeline_options = PdfPipelineOptions(
                ocr_options=EasyOcrOptions(),
                artifacts_path=artifacts_path
            )
            pipeline_options.images_scale = IMAGE_RESOLUTION_SCALE
            pipeline_options.generate_page_images = True
            pipeline_options.generate_picture_images = True

            self.doc_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
            print("✅ Docling转换器初始化成功")
        except Exception as e:
            print(f"❌ Docling转换器初始化失败: {e}")
            self.doc_converter = None
    
    def _init_ai_model(self):
        """初始化AI模型"""
        try:
            # 检查API密钥
            openrouter_api_key = os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENAI_API_KEY')
            if not openrouter_api_key:
                print("⚠️ 未设置OPENROUTER_API_KEY或OPENAI_API_KEY，AI功能将不可用")
                return
            
            # 创建模型
            from camel.configs.openai_config import ChatGPTConfig
            
            # 临时设置环境变量连接到OpenRouter
            original_base_url = os.environ.get('OPENAI_API_BASE_URL')
            original_api_key = os.environ.get('OPENAI_API_KEY')
            
            os.environ['OPENAI_API_BASE_URL'] = 'https://openrouter.ai/api/v1'
            os.environ['OPENAI_API_KEY'] = openrouter_api_key
            
            try:
                self.actor_model = ModelFactory.create(
                    model_platform=ModelPlatformType.OPENAI,
                    model_type=self.model_name,
                    model_config_dict=ChatGPTConfig().as_dict(),
                )
                
                # 创建聊天智能体
                actor_sys_msg = 'You are a document content divider and extractor specialist, expert in reorganizing document content into structured format.'
                
                self.actor_agent = ChatAgent(
                    system_message=actor_sys_msg,
                    model=self.actor_model,
                    message_window_size=10,
                    token_limit=None
                )
                
                print(f"✅ AI模型初始化成功: {self.model_name}")
                
            finally:
                # 恢复原始环境变量
                if original_base_url:
                    os.environ['OPENAI_API_BASE_URL'] = original_base_url
                elif 'OPENAI_API_BASE_URL' in os.environ:
                    del os.environ['OPENAI_API_BASE_URL']
                
                if original_api_key:
                    os.environ['OPENAI_API_KEY'] = original_api_key
                elif original_api_key is None and 'OPENAI_API_KEY' in os.environ:
                    del os.environ['OPENAI_API_KEY']
            
        except Exception as e:
            print(f"❌ AI模型初始化失败: {e}")
            self.actor_model = None
            self.actor_agent = None
    
    def parse_raw(self, pdf_path: str, output_dir: str = None) -> Tuple[Dict, Dict, Dict]:
        """
        解析PDF文件
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录，默认为项目根目录下的parser_output
            
        Returns:
            Tuple[Dict, Dict, Dict]: (content_json, images, tables)
        """
        if output_dir is None:
            output_dir = str(DEFAULT_PARSER_OUTPUT_DIR)

        print(f"🔄 开始解析PDF: {pdf_path}")
        print(f"📊 使用模型: {self.model_name}")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        if not self.doc_converter:
            raise Exception("Docling转换器未初始化")
        
        # 第一步：使用Docling解析PDF
        print("📄 使用Docling解析PDF...")
        raw_result = self.doc_converter.convert(pdf_path)
        raw_markdown = raw_result.document.export_to_markdown()
        
        # 清理markdown内容
        markdown_clean_pattern = re.compile(r"<!--[\s\S]*?-->")
        text_content = markdown_clean_pattern.sub("", raw_markdown)
        
        print(f"📝 解析得到文本长度: {len(text_content)} 字符")
        
        # 第二步：使用LLM重新组织内容（如果可用）
        content_json = {}
        if self.actor_agent and len(text_content.strip()) > 0:
            print("🧠 使用LLM重新组织内容...")
            try:
                content_json = self._reorganize_content_with_llm(text_content)
            except Exception as e:
                print(f"⚠️ LLM重组失败，使用基础结构: {e}")
                content_json = self._create_basic_structure(text_content)
        else:
            print("⚠️ AI模型不可用，使用基础结构化处理")
            content_json = self._create_basic_structure(text_content)
        
        # 第三步：提取图片和表格
        print("🖼️ 提取图片和表格...")
        images, tables = self._extract_images_and_tables(raw_result, output_dir)
        
        # 保存结果
        self._save_results(content_json, images, tables, output_dir)
        
        return content_json, images, tables
    
    def _create_basic_structure(self, text_content: str) -> Dict:
        """创建基础文档结构（当AI不可用时）- 保留更多原始文本"""
        # 按行分割，保留所有非空行
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        # 基础结构
        content_json = {
            "sections": []
        }
        
        # 将文本按逻辑分组，每个section包含更多内容
        current_section = []
        current_page = 0
        
        for line in lines:
            current_section.append(line)
            
            # 每约3000字符或遇到明显的分页标志时创建新section
            if (len('\n'.join(current_section)) > 3000 or 
                any(keyword in line.lower() for keyword in ['page ', '第', '页', '---', '==='])):
                
                if current_section:
                    section_content = '\n'.join(current_section)
                    content_json["sections"].append({
                        "content": section_content,
                        "source_page": current_page
                    })
                    current_section = []
                    current_page += 1
        
        # 添加最后一个section
        if current_section:
            section_content = '\n'.join(current_section)
            content_json["sections"].append({
                "content": section_content,
                "source_page": current_page
            })
        
        return content_json
    
    def _reorganize_content_with_llm(self, text_content: str) -> Dict:
        """使用LLM重新组织内容"""
        # 使用prompt模板
        try:
            if PROMPT_LOADER_AVAILABLE:
                prompt_loader = get_prompt_loader()
                template_content = prompt_loader.get_prompt("pdf_processing", "content_reorganization_template")
            else:
                # 备用模板
                template_content = """You are a document content divider and extractor specialist, expert in dividing and extracting content from various types of documents and reorganizing it into a two-level json format.

Based on given markdown document, generate a JSON output, make sure the output is concise and focused.

Step-by-Step Instructions:
1. Identify Sections and Subsections in document and identify sections and subsections based on the heading levels and logical structure.

2. Divide Content: Reorganize the content into sections and subsections, ensuring that each subsection contains approximately 500 words.

3. Refine Titles: Create titles for each section with at most 3 words.

4. Remove Unwanted Elements: Eliminate any unwanted elements such as headers, footers, text surrounded by `~~` indicating deletion.

5. Refine Text: For content, you should keep as much raw text as possible. Do not include citations.

6. Length: you should control the length of each section, according to their importance according to your understanding of the document. For important sections, their content should be long.

7. Make sure there is a document title section at the beginning, and it should contain information like document title, author, organization etc.

8. The "meta" key contains the meta information of the document, where the title should be the raw title of the document and is not summarized.

9. There **must** be a section for the document title.

Example Output:
{{
    "meta": {{
        "poster_title": "raw title of the document",
        "authors": "authors of the document",
        "affiliations": "affiliations of the authors"
    }},
    "sections": [
        {{
            "title": "Document Title",
            "content": "content of document title and author"
        }},
        {{
            "title": "Introduction",
            "content": "content of introduction section"
        }},
        {{
            "title": "Methods",
            "content": "content of methods section"
        }}
    ]
}}

Give your output in JSON format
Input:
{markdown_document}
Output:"""
        except Exception as e:
            print(f"警告：加载内容重组prompt模板失败，使用备用模板: {e}")
            # 备用模板
            template_content = """You are a document content divider and extractor specialist, expert in dividing and extracting content from various types of documents and reorganizing it into a two-level json format.

Based on given markdown document, generate a JSON output, make sure the output is concise and focused.

Step-by-Step Instructions:
1. Identify Sections and Subsections in document and identify sections and subsections based on the heading levels and logical structure.

2. Divide Content: Reorganize the content into sections and subsections, ensuring that each subsection contains approximately 500 words.

3. Refine Titles: Create titles for each section with at most 3 words.

4. Remove Unwanted Elements: Eliminate any unwanted elements such as headers, footers, text surrounded by `~~` indicating deletion.

5. Refine Text: For content, you should keep as much raw text as possible. Do not include citations.

6. Length: you should control the length of each section, according to their importance according to your understanding of the document. For important sections, their content should be long.

7. Make sure there is a document title section at the beginning, and it should contain information like document title, author, organization etc.

8. The "meta" key contains the meta information of the document, where the title should be the raw title of the document and is not summarized.

9. There **must** be a section for the document title.

Example Output:
{{
    "meta": {{
        "poster_title": "raw title of the document",
        "authors": "authors of the document",
        "affiliations": "affiliations of the authors"
    }},
    "sections": [
        {{
            "title": "Document Title",
            "content": "content of document title and author"
        }},
        {{
            "title": "Introduction",
            "content": "content of introduction section"
        }},
        {{
            "title": "Methods",
            "content": "content of methods section"
        }}
    ]
}}

Give your output in JSON format
Input:
{markdown_document}
Output:"""
        
        from jinja2 import Template
        template = Template(template_content)
        prompt = template.render(markdown_document=text_content[:50000])  # 限制长度防止超限
        
        # 调用LLM
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.actor_agent.reset()
                response = self.actor_agent.step(prompt)
                
                # 提取JSON
                content_json = self._get_json_from_response(response.msgs[0].content)
                
                if len(content_json.get("sections", [])) > 0:
                    # 验证和优化结果
                    content_json = self._validate_and_optimize_content(content_json)
                    return content_json
                else:
                    print(f"⚠️ LLM返回空结果，重试... ({attempt + 1}/{max_retries})")
                    
            except Exception as e:
                print(f"⚠️ LLM调用失败 ({attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise e
        
        raise Exception("LLM处理失败，已达到最大重试次数")
    
    def _get_json_from_response(self, content: str) -> Dict:
        """从响应中提取JSON"""
        try:
            # 尝试直接解析JSON
            return json.loads(content)
        except:
            # 尝试提取JSON代码块
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            else:
                # 尝试提取{}包围的内容
                brace_match = re.search(r'\{.*\}', content, re.DOTALL)
                if brace_match:
                    return json.loads(brace_match.group(0))
                else:
                    raise ValueError("Could not extract JSON from response")
    
    def _validate_and_optimize_content(self, content_json: Dict) -> Dict:
        """验证和优化内容"""
        # 检查必要字段
        if 'sections' not in content_json:
            raise ValueError("Missing 'sections' field in response")
        
        # 验证每个section的格式
        valid_sections = []
        for section in content_json['sections']:
            if isinstance(section, dict) and 'title' in section and 'content' in section:
                valid_sections.append(section)
        
        content_json['sections'] = valid_sections
        
        if len(valid_sections) == 0:
            raise ValueError("No valid sections found")
        
        # 如果section过多，进行智能选择
        if len(content_json['sections']) > 9:
            print(f"⚠️ Section数量过多({len(content_json['sections'])}个)，进行智能选择...")
            selected_sections = (
                content_json['sections'][:2] + 
                random.sample(content_json['sections'][2:-2], min(5, len(content_json['sections'][2:-2]))) + 
                content_json['sections'][-2:]
            )
            content_json['sections'] = selected_sections
            print(f"✅ 选择后剩余{len(content_json['sections'])}个sections")
        
        return content_json
    
    def _extract_images_and_tables(self, raw_result, output_dir: str) -> Tuple[Dict, Dict]:
        """提取图片和表格"""
        images = {}
        tables = {}
        
        # 提取表格
        table_counter = 0
        for element, _level in raw_result.document.iterate_items():
            if isinstance(element, TableItem):
                table_counter += 1
                caption = element.caption_text(raw_result.document)
                table_img_path = os.path.join(output_dir, f"table-{table_counter}.png")
                
                # 保存表格图片
                try:
                    table_image = element.get_image(raw_result.document)
                    if table_image is not None:
                        with open(table_img_path, "wb") as fp:
                            table_image.save(fp, "PNG")
                        
                        # 获取图片信息
                        table_img = Image.open(table_img_path)
                        tables[str(table_counter)] = {
                            'caption': caption if caption else f"表格 {table_counter}",
                            'table_path': table_img_path,
                            'width': table_img.width,
                            'height': table_img.height,
                            'figure_size': table_img.width * table_img.height,
                            'figure_aspect': table_img.width / table_img.height,
                        }
                        print(f"✅ 保存表格 {table_counter}: {table_img_path}")
                    else:
                        print(f"⚠️ 表格 {table_counter} 图像为空")
                except Exception as e:
                    print(f"❌ 保存表格 {table_counter} 失败: {e}")
        
        # 提取图片
        picture_counter = 0
        # 收集所有元素，便于定位图片和文本
        all_elements = list(raw_result.document.iterate_items())
        for idx, (element, _level) in enumerate(all_elements):
            if isinstance(element, PictureItem):
                picture_counter += 1
                caption = element.caption_text(raw_result.document)
                image_img_path = os.path.join(output_dir, f"picture-{picture_counter}.png")
                try:
                    picture_image = element.get_image(raw_result.document)
                    if picture_image is not None:
                        with open(image_img_path, "wb") as fp:
                            picture_image.save(fp, "PNG")
                        image_img = Image.open(image_img_path)
                        
                        # [已移除] 不再提取context字段，使用VLM进行图片描述
                        
                        images[str(picture_counter)] = {
                            'caption': caption if caption else f"图片 {picture_counter}",
                            'image_path': image_img_path,
                            'width': image_img.width,
                            'height': image_img.height,
                            'figure_size': image_img.width * image_img.height,
                            'figure_aspect': image_img.width / image_img.height,
                            # [已移除] 'context': context, - 不再使用context字段，由VLM生成描述
                        }
                        print(f"✅ 保存图片 {picture_counter}: {image_img_path}")
                    else:
                        print(f"⚠️ 图片 {picture_counter} 图像为空")
                except Exception as e:
                    print(f"❌ 保存图片 {picture_counter} 失败: {e}")
        
        print(f"📊 提取了 {len(tables)} 个表格和 {len(images)} 个图片")
        return images, tables
    
    def _save_results(self, content_json: Dict, images: Dict, tables: Dict, output_dir: str):
        """保存解析结果"""
        # 保存结构化内容
        content_path = os.path.join(output_dir, "parsed_content.json")
        with open(content_path, 'w', encoding='utf-8') as f:
            json.dump(content_json, f, indent=4, ensure_ascii=False)
        print(f"📄 结构化内容已保存到: {content_path}")
        
        # 保存图片信息
        images_path = os.path.join(output_dir, "images.json")
        with open(images_path, 'w', encoding='utf-8') as f:
            json.dump(images, f, indent=4, ensure_ascii=False)
        print(f"🖼️ 图片信息已保存到: {images_path}")
        
        # 保存表格信息
        tables_path = os.path.join(output_dir, "tables.json")
        with open(tables_path, 'w', encoding='utf-8') as f:
            json.dump(tables, f, indent=4, ensure_ascii=False)
        print(f"📊 表格信息已保存到: {tables_path}")
        
        # 保存汇总信息
        summary = {
            "total_sections": len(content_json.get("sections", [])),
            "total_images": len(images),
            "total_tables": len(tables),
            "meta_info": content_json.get("meta", {}),
            "section_titles": [section.get("title", "") for section in content_json.get("sections", [])],
            "model_used": self.model_name
        }
        
        summary_path = os.path.join(output_dir, "summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=4, ensure_ascii=False)
        print(f"📋 汇总信息已保存到: {summary_path}")
    
    def get_parsing_stats(self, content_json: Dict, images: Dict, tables: Dict) -> Dict:
        """获取解析结果的统计信息"""
        # 计算总文本长度
        total_text_length = 0
        sections = content_json.get('sections', [])
        for section in sections:
            total_text_length += len(section.get('content', ''))
        
        stats = {
            'title': content_json.get('metadata', {}).get('title', content_json.get('title', 'N/A')),
            'sections_count': len(sections),
            'images_count': len(images),
            'tables_count': len(tables),
            'total_text_length': total_text_length,
            'model_used': getattr(self, 'model_name', 'unknown')
        }
        return stats

    def parse_without_llm(self, pdf_path: str, output_dir: str = None) -> tuple[dict, dict, dict]:
        """
        直接使用Docling进行解析，不通过LLM重组内容。
        这对于结构化较好的文档或不需要智能重组的场景更高效。
        """
        if output_dir is None:
            output_dir = str(DEFAULT_PARSER_OUTPUT_DIR)

        print(f"📄 跳过LLM重组，执行原始解析...")
        if not self.doc_converter:
            raise RuntimeError("Docling转换器未初始化。")

        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        print(f"📄 使用Docling进行原始解析...")
        # 使用docling转换器处理PDF - 修复参数格式
        raw_result = self.doc_converter.convert(source=Path(pdf_path))
        print("✅ Docling原始解析完成。")

        # 使用与parse_raw相同的逻辑：导出为markdown然后处理
        raw_markdown = raw_result.document.export_to_markdown()
        
        # 清理markdown内容
        import re
        markdown_clean_pattern = re.compile(r"<!--[\s\S]*?-->")
        text_content = markdown_clean_pattern.sub("", raw_markdown)
        
        print(f"📝 解析得到文本长度: {len(text_content)} 字符")

        # 使用基础结构化处理（不使用LLM）
        content_json = self._create_basic_structure(text_content)
        
        # 添加源文件信息到metadata
        if "meta" in content_json:
            content_json["meta"]["source_file"] = pdf_path
        else:
            content_json["metadata"] = {
                "title": Path(pdf_path).stem,
                "source_file": pdf_path
            }
        
        # 提取图片和表格
        images, tables = self._extract_images_and_tables(raw_result, output_dir)
        
        # 保存结果
        self._save_results(content_json, images, tables, output_dir)

        print("✅ 原始解析完成，已跳过LLM重组步骤。")
        return content_json, images, tables


class PDFParserTool(Tool):
    """PDF解析工具 - 基于OpenRouter的智能PDF解析"""
    
    def __init__(self):
        super().__init__(
            name="pdf_parser",
            description="📄 PDF智能解析工具 - 提取文本、图片、表格并结构化重组。支持多种AI模型，智能内容重组。"
        )
        self.parser_agent = None
        self._init_parser()
    
    def _init_parser(self):
        """初始化PDF解析器"""
        if not DEPENDENCIES_AVAILABLE:
            print("❌ PDF解析依赖库不可用，工具功能受限")
            return
        
        try:
            # 创建默认解析器
            self.parser_agent = OpenRouterParserAgent(model_name="gpt-4o")
            print("✅ PDF解析工具初始化成功")
        except Exception as e:
            print(f"❌ PDF解析工具初始化失败: {e}")
            self.parser_agent = None
    
    def execute(self, **kwargs) -> str:
        """
        执行PDF解析
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录（可选，默认为 'parser_output/YYYYMMDD_HHMMSS_random'）
            model_name: 使用的模型名称（可选，默认为gpt-4o）
            action: 操作类型（parse/list_models）
            
        Returns:
            str: 包含解析结果（如输出目录）的JSON字符串
        """
        action = kwargs.get("action", "parse")
        
        if action == "list_models":
            return self._list_available_models()
        elif action == "parse":
            return self._parse_pdf(**kwargs)
        else:
            return json.dumps({
                "status": "error",
                "message": f"不支持的操作: {action}。支持的操作: parse, list_models"
            }, indent=2, ensure_ascii=False)
    
    def _list_available_models(self) -> str:
        """列出所有可用的AI模型"""
        return json.dumps({"supported_models": SUPPORTED_MODELS}, indent=2)
    
    def _parse_pdf(self, **kwargs) -> str:
        """解析PDF文件并返回结构化结果"""
        pdf_path = kwargs.get("pdf_path")
        
        if not pdf_path:
            return json.dumps({"status": "error", "message": "请提供PDF文件路径 (pdf_path参数)"}, indent=2)
        
        if not os.path.exists(pdf_path):
            return json.dumps({"status": "error", "message": f"PDF文件不存在: {pdf_path}"}, indent=2)

        if not DEPENDENCIES_AVAILABLE:
            return json.dumps({"status": "error", "message": "PDF解析依赖库不可用，请安装必要的依赖库"}, indent=2)

        # 为每个解析任务创建一个唯一的输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_id = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
        
        # --- FIX: Use the absolute default path as the base ---
        base_output_dir = kwargs.get("output_dir", DEFAULT_PARSER_OUTPUT_DIR)
        output_dir = os.path.join(base_output_dir, f"{timestamp}_{random_id}")
        
        # 确保基础目录存在
        os.makedirs(base_output_dir, exist_ok=True)

        model_name = kwargs.get("model_name", "gpt-4o")
        
        try:
            # 如果指定了不同的模型，重新创建解析器
            if (not self.parser_agent or 
                (hasattr(self.parser_agent, 'model_name') and 
                 self.parser_agent.model_name != model_name)):
                print(f"🔄 切换到模型: {model_name}")
                self.parser_agent = OpenRouterParserAgent(model_name=model_name)
            
            if not self.parser_agent:
                raise Exception("PDF解析器未正确初始化")
            
            print(f"🚀 开始解析PDF: {pdf_path}")
            
            # 新增参数控制是否使用LLM
            use_llm = kwargs.get('use_llm_reorganization', False)
            
            if use_llm:
                print("🧠 使用LLM进行内容重组...")
                content_json, images, tables = self.parser_agent.parse_raw(pdf_path, output_dir)
            else:
                print("📄 跳过LLM重组，执行原始解析...")
                content_json, images, tables = self.parser_agent.parse_without_llm(pdf_path, output_dir)

            # 获取统计信息
            stats = self.parser_agent.get_parsing_stats(content_json, images, tables)
            
            # --- 统一的PDF内容embedding处理 ---
            embedding_stats = {}
            if EMBEDDING_SERVICE_AVAILABLE:
                try:
                    print("💡 开始统一的PDF内容embedding处理...")
                    embedding_service = PDFEmbeddingService(enable_vlm_description=True)
                    
                    # 使用统一的embedding服务处理parsed_content.json和images.json
                    content_file_path = os.path.join(output_dir, "parsed_content.json")
                    images_file_path = os.path.join(output_dir, "images.json")
                    
                    # 调用统一的embedding方法
                    embedding_result = embedding_service.embed_parsed_pdf(
                        parsed_content_path=content_file_path,
                        images_json_path=images_file_path,
                        parser_output_dir=output_dir
                    )
                    
                    # 统一的结果处理
                    if not embedding_result.get("errors"):
                        embedding_stats = {
                            "status": "success",
                            "text_embeddings": embedding_result.get("text_embeddings", 0),
                            "image_embeddings": embedding_result.get("image_embeddings", 0),
                            "total_embeddings": embedding_result.get("total_embeddings", 0),
                            "method": "unified_embedding_service"
                        }
                        print(f"✅ 统一embedding完成: 文本{embedding_stats['text_embeddings']}项, 图片{embedding_stats['image_embeddings']}项")
                    else:
                        embedding_stats = {
                            "status": "partial_success",
                            "text_embeddings": embedding_result.get("text_embeddings", 0),
                            "image_embeddings": embedding_result.get("image_embeddings", 0),
                            "total_embeddings": embedding_result.get("total_embeddings", 0),
                            "errors": embedding_result.get("errors", []),
                            "method": "unified_embedding_service"
                        }
                        print(f"⚠️ 统一embedding部分成功: 文本{embedding_stats['text_embeddings']}项, 图片{embedding_stats['image_embeddings']}项")
                        for error in embedding_result.get("errors", []):
                            print(f"  - 错误: {error}")
                    
                except Exception as e:
                    print(f"❌ 统一embedding处理失败: {e}")
                    embedding_stats = {"status": "error", "message": str(e)}
            else:
                embedding_stats = {"status": "skipped", "message": "Embedding service not available."}


            # 准备结构化输出
            result = {
                "status": "success",
                "message": "PDF解析完成",
                "output_directory": output_dir,
                "embedding_info": embedding_stats,
                "statistics": {
                    "model_used": stats.get('model_used', 'unknown'),
                    "sections_count": stats.get('sections_count', 0),
                    "images_count": stats.get('images_count', 0),
                    "tables_count": stats.get('tables_count', 0),
                    "total_text_length": stats.get('total_text_length', 0)
                },
                "content_file": os.path.join(output_dir, "parsed_content.json"),
                "images_file": os.path.join(output_dir, "images.json") if images else None,
                "tables_file": os.path.join(output_dir, "tables.json") if tables else None
            }
            
            # 返回JSON字符串
            return json.dumps(result, indent=2, ensure_ascii=False)
            
        except Exception as e:
            # 错误时也返回JSON
            error_result = {
                "status": "error",
                "message": f"PDF解析失败: {str(e)}",
                "output_directory": None
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)
    
    def get_usage_guide(self) -> str:
        """获取使用指南"""
        return """
📄 PDF解析工具使用指南

🔧 基本用法:
1. 解析PDF: pdf_parser(pdf_path="path/to/file.pdf", action="parse")
2. 列出模型: pdf_parser(action="list_models")
3. 获取统计: pdf_parser(action="get_stats", output_dir="parser_output")

📋 参数说明:
- pdf_path: PDF文件路径（必填，用于parse操作）
- action: 操作类型（parse/list_models/get_stats）
- output_dir: 输出目录（可选，默认为parser_output）
- model_name: AI模型名称（可选，默认为gpt-4o）
- use_llm_reorganization: 是否使用LLM进行内容重组（可选，默认为False，以提高速度）

🧠 支持的AI模型:
- OpenAI: gpt-4o, gpt-4o-mini, gpt-3.5-turbo
- Anthropic: claude-3.5-sonnet, claude-3-haiku
- Meta: llama-3.1-8b, llama-3.1-70b
- Google: gemini-pro
- 开源: qwen2.5-7b, qwen2.5-32b

📁 输出文件:
- parsed_content.json: 结构化文本内容
- images.json: 图片信息
- tables.json: 表格信息
- summary.json: 汇总信息
- picture-*.png: 提取的图片文件
- table-*.png: 提取的表格文件

⚙️ 环境要求:
- 设置 OPENROUTER_API_KEY 或 OPENAI_API_KEY 环境变量
- 安装必要依赖: camel-ai, docling, jinja2, pillow
""" 