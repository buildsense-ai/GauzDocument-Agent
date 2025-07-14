"""
PDF Document Parser

专门负责PDF文档解析的组件，使用Docling进行解析并按页输出文本内容
"""

import os
import re
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from .config import PDFProcessingConfig, DoclingConfig

# 导入docling相关组件
try:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    DOCLING_AVAILABLE = True
    print("✅ Docling组件可用")
except ImportError as e:
    DOCLING_AVAILABLE = False
    print(f"❌ Docling组件不可用: {e}")
    
    # 创建占位符类型，避免类型错误
    class DocumentConverter:
        pass
    
    class PdfPipelineOptions:
        pass


class PDFDocumentParser:
    """
    PDF文档解析器 - 专门负责PDF文档的解析
    
    核心功能：
    1. 使用Docling进行PDF解析
    2. 按页提取文本内容
    3. 支持配置化的解析参数
    4. 输出原始解析结果和按页文本
    """
    
    def __init__(self, config: Optional[PDFProcessingConfig] = None):
        """
        初始化PDF文档解析器
        
        Args:
            config: PDF处理配置，如果为None则使用默认配置
        """
        self.config = config or PDFProcessingConfig.from_env()
        self.doc_converter = None
        
        if not DOCLING_AVAILABLE:
            print("⚠️ Docling不可用，PDFDocumentParser功能受限")
            return
            
        self._init_docling_converter()
    
    def _init_docling_converter(self) -> None:
        """初始化Docling转换器"""
        try:
            # 设置本地模型路径
            models_cache_dir = Path("models_cache")
            artifacts_path = None
            if models_cache_dir.exists():
                artifacts_path = str(models_cache_dir.absolute())
            elif self.config.docling.artifacts_path:
                artifacts_path = self.config.docling.artifacts_path
            
            # 创建OCR选项
            ocr_options = EasyOcrOptions() if self.config.docling.ocr_enabled else None
            
            # 创建管道选项
            pipeline_options = PdfPipelineOptions(
                ocr_options=ocr_options,
                artifacts_path=artifacts_path
            )
            
            # 设置解析选项
            pipeline_options.images_scale = self.config.docling.images_scale
            pipeline_options.generate_page_images = self.config.docling.generate_page_images
            pipeline_options.generate_picture_images = self.config.docling.generate_picture_images
            
            # 创建文档转换器
            self.doc_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
            
            print("✅ Docling转换器初始化成功")
            
        except Exception as e:
            print(f"❌ Docling转换器初始化失败: {e}")
            self.doc_converter = None
    
    def parse_pdf(self, pdf_path: str) -> Tuple[Any, Dict[int, str]]:
        """
        解析PDF文件
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            Tuple[Any, Dict[int, str]]: (raw_result, page_texts)
            - raw_result: Docling原始解析结果
            - page_texts: 页码到页面文本的映射
        """
        if not DOCLING_AVAILABLE:
            raise RuntimeError("Docling不可用，无法解析PDF")
        
        if not self.doc_converter:
            raise RuntimeError("Docling转换器未初始化")
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        print(f"🔄 开始解析PDF: {pdf_path}")
        
        try:
            # 使用Docling解析PDF
            raw_result = self.doc_converter.convert(Path(pdf_path))
            print("✅ Docling解析完成")
            
            # 提取按页文本
            page_texts = self._extract_page_texts(raw_result)
            print(f"📄 提取到 {len(page_texts)} 页文本")
            
            return raw_result, page_texts
            
        except Exception as e:
            print(f"❌ PDF解析失败: {e}")
            raise RuntimeError(f"PDF解析失败: {str(e)}")
    
    def _extract_page_texts(self, raw_result: Any) -> Dict[int, str]:
        """
        从Docling解析结果中提取按页文本
        
        Args:
            raw_result: Docling解析结果
            
        Returns:
            Dict[int, str]: 页码到页面文本的映射
        """
        try:
            # 导出为markdown格式
            raw_markdown = raw_result.document.export_to_markdown()
            
            # 清理markdown内容（移除HTML注释）
            markdown_clean_pattern = re.compile(r"<!--[\s\S]*?-->")
            cleaned_markdown = markdown_clean_pattern.sub("", raw_markdown)
            
            # 按页分割文本
            page_texts = self._split_text_by_pages(cleaned_markdown, raw_result)
            
            return page_texts
            
        except Exception as e:
            print(f"❌ 页面文本提取失败: {e}")
            return {}
    
    def _split_text_by_pages(self, text_content: str, raw_result: Any) -> Dict[int, str]:
        """
        将文本按页分割
        
        Args:
            text_content: 清理后的文本内容
            raw_result: Docling解析结果
            
        Returns:
            Dict[int, str]: 页码到页面文本的映射
        """
        try:
            # 尝试从Docling结果中获取页面信息
            page_texts = {}
            
            # 方法1：尝试从文档结构中按页提取 (document.pages是字典)
            if hasattr(raw_result, 'document') and hasattr(raw_result.document, 'pages'):
                pages_dict = raw_result.document.pages
                print(f"📄 发现 {len(pages_dict)} 个页面")
                
                # pages是字典，key是页码
                for page_num, page in pages_dict.items():
                    page_text = ""
                    
                    # 尝试多种方式提取页面文本
                    try:
                        # 方式1：使用export_to_text方法（如果存在）
                        if hasattr(raw_result.document, 'export_to_text'):
                            # 获取该页面的文本
                            full_text = raw_result.document.export_to_text()
                            # 这里我们使用一个简单的方法：将全文按页面数量分割
                            lines = full_text.split('\n')
                            lines_per_page = len(lines) // len(pages_dict)
                            start_idx = (page_num - 1) * lines_per_page
                            end_idx = start_idx + lines_per_page if page_num < len(pages_dict) else len(lines)
                            page_text = '\n'.join(lines[start_idx:end_idx])
                        
                        # 方式2：如果有elements属性
                        elif hasattr(page, 'elements'):
                            for element in page.elements:
                                if hasattr(element, 'text') and element.text:
                                    page_text += element.text + "\n"
                        
                        # 方式3：如果page有text属性
                        elif hasattr(page, 'text'):
                            page_text = page.text
                        
                        # 方式4：其他可能的文本属性
                        else:
                            # 尝试从page对象中提取任何可能的文本
                            for attr in dir(page):
                                if not attr.startswith('_') and 'text' in attr.lower():
                                    try:
                                        attr_value = getattr(page, attr)
                                        if isinstance(attr_value, str) and attr_value.strip():
                                            page_text += attr_value + "\n"
                                    except:
                                        continue
                    
                    except Exception as e:
                        print(f"⚠️ 页面 {page_num} 文本提取失败: {e}")
                        continue
                    
                    if page_text.strip():
                        page_texts[page_num] = page_text.strip()
            
            # 方法2：如果方法1失败，尝试从raw_result.pages列表中提取
            if not page_texts and hasattr(raw_result, 'pages'):
                print("🔄 尝试从raw_result.pages提取页面文本...")
                pages_list = raw_result.pages
                if pages_list:
                    for page_num, page in enumerate(pages_list, 1):
                        page_text = ""
                        
                        # 尝试提取页面文本
                        if hasattr(page, 'text'):
                            page_text = page.text
                        elif hasattr(page, 'content'):
                            page_text = page.content
                        
                        if page_text.strip():
                            page_texts[page_num] = page_text.strip()
            
            # 方法3：如果仍然没有分页，按markdown结构智能分割
            if not page_texts and text_content.strip():
                print("🔄 尝试智能分割文本...")
                # 使用更智能的分割方法
                page_texts = self._smart_split_text(text_content)
            
            # 方法4：如果所有方法都失败，将所有文本作为第一页
            if not page_texts and text_content.strip():
                page_texts[1] = text_content.strip()
                print("⚠️ 无法识别页面分割，将所有文本作为第一页")
            
            return page_texts
            
        except Exception as e:
            print(f"❌ 文本分页失败: {e}")
            # 作为最后的备选方案
            if text_content.strip():
                return {1: text_content.strip()}
            return {}
    
    def _smart_split_text(self, text_content: str) -> Dict[int, str]:
        """
        智能分割文本，基于内容结构
        
        Args:
            text_content: 文本内容
            
        Returns:
            Dict[int, str]: 页码到页面文本的映射
        """
        # 按照学术论文的结构特征进行分割
        # 寻找章节标题、图表标题等作为分割点
        
        lines = text_content.split('\n')
        page_texts = {}
        current_page = 1
        current_page_text = []
        
        # 估算每页的行数（基于总行数和预期页面数）
        estimated_pages = max(1, len(lines) // 100)  # 假设每页约100行
        lines_per_page = len(lines) // estimated_pages
        
        for i, line in enumerate(lines):
            current_page_text.append(line)
            
            # 每达到预估行数，或遇到明显的分割标识，就分页
            if (len(current_page_text) >= lines_per_page and 
                (self._is_page_break(line) or self._is_section_start(line))):
                
                if current_page_text:
                    page_texts[current_page] = '\n'.join(current_page_text).strip()
                current_page += 1
                current_page_text = []
        
        # 保存最后一页
        if current_page_text:
            page_texts[current_page] = '\n'.join(current_page_text).strip()
        
        return page_texts
    
    def _is_section_start(self, line: str) -> bool:
        """
        判断是否是章节开始
        
        Args:
            line: 文本行
            
        Returns:
            bool: 是否是章节开始
        """
        # 检查是否是章节标题
        section_patterns = [
            r'^\s*#+\s+',  # Markdown标题
            r'^\s*\d+\.\s+',  # 数字标题
            r'^\s*[A-Z][A-Z\s]+$',  # 全大写标题
            r'^\s*Figure\s+\d+',  # 图表标题
            r'^\s*Table\s+\d+',  # 表格标题
        ]
        
        for pattern in section_patterns:
            if re.match(pattern, line):
                return True
        
        return False
    
    def _is_page_break(self, line: str) -> bool:
        """
        判断是否是页面分割标识
        
        Args:
            line: 文本行
            
        Returns:
            bool: 是否是页面分割标识
        """
        # 常见的页面分割标识
        page_break_patterns = [
            r'^\s*---+\s*$',  # 连续的破折号
            r'^\s*===+\s*$',  # 连续的等号
            r'^\s*Page\s+\d+\s*$',  # Page 数字
            r'^\s*第\s*\d+\s*页\s*$',  # 第X页
            r'^\s*\d+\s*$',  # 纯数字（可能的页码）
        ]
        
        for pattern in page_break_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        
        return False
    
    def get_raw_text(self, pdf_path: str) -> str:
        """
        获取PDF的原始文本内容（不分页）
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            str: 原始文本内容
        """
        raw_result, _ = self.parse_pdf(pdf_path)
        
        try:
            # 导出为markdown格式
            raw_markdown = raw_result.document.export_to_markdown()
            
            # 清理markdown内容
            markdown_clean_pattern = re.compile(r"<!--[\s\S]*?-->")
            cleaned_text = markdown_clean_pattern.sub("", raw_markdown)
            
            return cleaned_text.strip()
            
        except Exception as e:
            print(f"❌ 原始文本提取失败: {e}")
            return ""
    
    def get_document_info(self, pdf_path: str) -> Dict[str, Any]:
        """
        获取PDF文档信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            Dict[str, Any]: 文档信息
        """
        if not DOCLING_AVAILABLE or not self.doc_converter:
            return {
                "error": "Docling不可用",
                "file_path": pdf_path,
                "file_size": os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
            }
        
        try:
            raw_result, page_texts = self.parse_pdf(pdf_path)
            
            # 计算文档统计信息
            total_text_length = sum(len(text) for text in page_texts.values())
            
            return {
                "file_path": pdf_path,
                "file_name": os.path.basename(pdf_path),
                "file_size": os.path.getsize(pdf_path),
                "total_pages": len(page_texts),
                "total_text_length": total_text_length,
                "average_text_per_page": total_text_length / len(page_texts) if page_texts else 0,
                "config": {
                    "images_scale": self.config.docling.images_scale,
                    "ocr_enabled": self.config.docling.ocr_enabled,
                    "generate_page_images": self.config.docling.generate_page_images,
                    "generate_picture_images": self.config.docling.generate_picture_images
                }
            }
            
        except Exception as e:
            return {
                "error": f"文档信息获取失败: {str(e)}",
                "file_path": pdf_path,
                "file_size": os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
            } 