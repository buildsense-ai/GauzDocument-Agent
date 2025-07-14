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

# 导入备用PDF处理库
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
    print("✅ PyMuPDF可用作备用解析器")
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("❌ PyMuPDF不可用")


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
        """初始化Docling转换器（智能设备适配版本）"""
        try:
            import torch
            import os
            import platform
            import multiprocessing
            
            # 检测硬件能力
            system_info = platform.system()
            cpu_count = multiprocessing.cpu_count()
            
            # 设备检测和优化
            device = "cpu"
            use_gpu = False
            use_mps = False
            
            if torch.cuda.is_available():
                device = "cuda:0"
                use_gpu = True
                # CUDA GPU优化设置
                torch.backends.cudnn.benchmark = True
                os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:128'
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
                print(f"🚀 CUDA GPU检测成功 - 设备: {torch.cuda.get_device_name(0)}")
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "mps"
                use_mps = True
                print("🍎 Apple Silicon MPS检测成功")
            else:
                print(f"💻 使用CPU模式 - 系统: {system_info}, CPU核心: {cpu_count}")
            
            # 根据硬件设置线程数
            if use_gpu:
                # GPU模式：适中的线程数避免CPU-GPU竞争
                optimal_threads = min(16, cpu_count)
            else:
                # CPU模式：充分利用CPU核心
                optimal_threads = max(1, cpu_count - 1)  # 保留一个核心给系统
            
            torch.set_num_threads(optimal_threads)
            
            # 设置本地模型路径
            models_cache_dir = Path("models_cache")
            artifacts_path = None
            if models_cache_dir.exists():
                artifacts_path = str(models_cache_dir.absolute())
            elif self.config.docling.artifacts_path:
                artifacts_path = self.config.docling.artifacts_path
            
            # 智能加速器选项
            from docling.datamodel.accelerator_options import AcceleratorOptions
            accelerator_options = AcceleratorOptions(
                device=device,
                num_threads=optimal_threads,
                cuda_use_flash_attention2=use_gpu  # 仅在GPU模式下启用
            )
            
            # 智能OCR选项
            ocr_options = None
            if self.config.docling.ocr_enabled:
                # 根据EasyOCR支持的语言列表选择安全的语言组合
                supported_langs = ["en"]  # 英语是最稳定支持的
                if not use_gpu:  # CPU模式下添加更多语言支持
                    supported_langs.extend(["fr", "de"])  # 法语和德语通常支持较好
                
                ocr_options = EasyOcrOptions(
                    confidence_threshold=0.4,
                    lang=supported_langs
                    # 注意：不再使用已弃用的use_gpu参数，设备选择由accelerator_options控制
                )
            
            # 智能表格结构选项
            from docling.datamodel.pipeline_options import TableStructureOptions, TableFormerMode
            # 根据硬件能力选择模式
            table_mode = TableFormerMode.FAST if (use_gpu or use_mps) else TableFormerMode.ACCURATE
            table_options = TableStructureOptions(
                mode=table_mode,
                do_cell_matching=True
            )
            
            # 创建智能管道选项
            pipeline_options = PdfPipelineOptions(
                # 核心处理选项
                do_table_structure=True,
                do_ocr=self.config.docling.ocr_enabled,
                do_picture_description=use_gpu or use_mps,  # 仅在有加速器时启用
                do_picture_classification=True,
                
                # 配置选项
                ocr_options=ocr_options,
                table_structure_options=table_options,
                
                # 加速器选项
                accelerator_options=accelerator_options,
                
                # 图像生成选项
                images_scale=self.config.docling.images_scale,
                generate_page_images=self.config.docling.generate_page_images,
                generate_picture_images=self.config.docling.generate_picture_images,
                
                # 性能选项（根据硬件调整超时）
                document_timeout=600.0 if device == "cpu" else 300.0,
                artifacts_path=artifacts_path
            )
            
            # 创建文档转换器
            self.doc_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
            
            # 输出优化信息
            device_name = {
                "cuda:0": f"CUDA GPU ({torch.cuda.get_device_name(0)})",
                "mps": "Apple Silicon MPS",
                "cpu": f"CPU ({system_info})"
            }.get(device, device)
            
            print(f"✅ Docling转换器初始化成功 - 设备: {device_name}")
            print(f"📊 线程数: {optimal_threads}, 表格模式: {table_mode.value}")
            print(f"🔧 图片描述: {'启用' if (use_gpu or use_mps) else '禁用'}, OCR GPU: {'启用' if use_gpu else '禁用'}")
            
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
            - raw_result: 解析结果（Docling或PyMuPDF）
            - page_texts: 页码到页面文本的映射
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        print(f"🔄 开始解析PDF: {pdf_path}")
        
        # 优先使用Docling
        if DOCLING_AVAILABLE and self.doc_converter:
            try:
                # 使用Docling解析PDF
                raw_result = self.doc_converter.convert(Path(pdf_path))
                print("✅ Docling解析完成")
                
                # 提取按页文本
                page_texts = self._extract_page_texts(raw_result)
                print(f"📄 提取到 {len(page_texts)} 页文本")
                
                return raw_result, page_texts
                
            except Exception as e:
                print(f"⚠️ Docling解析失败，尝试降级处理: {e}")
        
        # 降级到PyMuPDF
        if PYMUPDF_AVAILABLE:
            try:
                return self._parse_with_pymupdf(pdf_path)
            except Exception as e:
                print(f"❌ PyMuPDF解析也失败: {e}")
                raise RuntimeError(f"所有PDF解析方法都失败: {str(e)}")
        
        # 如果所有方法都不可用
        raise RuntimeError("没有可用的PDF解析器（Docling和PyMuPDF都不可用）")
    
    def _parse_with_pymupdf(self, pdf_path: str) -> Tuple[Any, Dict[int, str]]:
        """
        使用PyMuPDF解析PDF文件（降级处理）
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            Tuple[Any, Dict[int, str]]: (raw_result, page_texts)
        """
        print("🔄 使用PyMuPDF进行降级解析...")
        
        try:
            # 打开PDF文档
            doc = fitz.open(pdf_path)
            page_texts = {}
            
            # 逐页提取文本
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                
                if text.strip():
                    page_texts[page_num + 1] = text.strip()
            
            doc.close()
            
            print(f"✅ PyMuPDF解析完成，提取到 {len(page_texts)} 页文本")
            
            # 创建一个简单的结果对象
            class PyMuPDFResult:
                def __init__(self, page_texts):
                    self.page_texts = page_texts
                    self.source = "PyMuPDF"
            
            raw_result = PyMuPDFResult(page_texts)
            return raw_result, page_texts
            
        except Exception as e:
            print(f"❌ PyMuPDF解析失败: {e}")
            raise RuntimeError(f"PyMuPDF解析失败: {str(e)}")
    
    def _extract_page_texts(self, raw_result: Any) -> Dict[int, str]:
        """
        从解析结果中提取按页文本
        
        Args:
            raw_result: 解析结果（Docling或PyMuPDF）
            
        Returns:
            Dict[int, str]: 页码到页面文本的映射
        """
        try:
            # 检查是否是PyMuPDF结果
            if hasattr(raw_result, 'source') and raw_result.source == "PyMuPDF":
                return raw_result.page_texts
            
            # Docling结果处理
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