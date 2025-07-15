"""
PDF Page Splitter

负责将PDF按自然页面切割成单页PDF文件，然后每页单独调用docling处理
这解决了页面标注漂移问题，确保每页的处理都是独立和准确的
"""

import os
import tempfile
import shutil
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .config import PDFProcessingConfig
from .data_models import PageData, ImageWithContext, TableWithContext
from .media_extractor import MediaExtractor

# 导入PDF处理库
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
    print("✅ PyMuPDF (fitz) 可用")
except ImportError:
    FITZ_AVAILABLE = False
    print("❌ PyMuPDF (fitz) 不可用，请安装: pip install PyMuPDF")

# 导入docling组件
try:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    DOCLING_AVAILABLE = True
    print("✅ Docling组件可用")
except ImportError as e:
    DOCLING_AVAILABLE = False
    print(f"❌ Docling组件不可用: {e}")
    
    # 创建占位符类型
    class DocumentConverter:
        pass
    
    class PdfPipelineOptions:
        pass


class PDFPageSplitter:
    """
    PDF页面分割器
    
    核心功能：
    1. 将PDF按自然页面切割成单页PDF文件
    2. 每页单独调用docling处理
    3. 异步并行处理所有页面
    4. 合并所有页面结果
    """
    
    def __init__(self, config: Optional[PDFProcessingConfig] = None):
        """
        初始化PDF页面分割器
        
        Args:
            config: PDF处理配置
        """
        self.config = config or PDFProcessingConfig()
        self.doc_converter = None
        self.media_extractor = MediaExtractor()
        
        if not FITZ_AVAILABLE:
            raise RuntimeError("PyMuPDF不可用，无法进行页面分割")
        
        if not DOCLING_AVAILABLE:
            raise RuntimeError("Docling不可用，无法进行页面处理")
        
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
    
    def split_and_process_pdf(self, pdf_path: str, output_dir: str) -> List[PageData]:
        """
        分割PDF并处理每一页
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            List[PageData]: 所有页面的处理结果
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        print(f"🔄 开始分割和处理PDF: {pdf_path}")
        start_time = time.time()
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 步骤1: 分割PDF为单页文件
        single_page_files = self._split_pdf_to_pages(pdf_path)
        print(f"📄 PDF分割完成，共 {len(single_page_files)} 页")
        
        try:
            # 步骤2: 并行处理所有页面
            if self.config.media_extractor.parallel_processing:
                pages_data = self._process_pages_parallel(single_page_files, output_dir)
            else:
                pages_data = self._process_pages_sequential(single_page_files, output_dir)
            
            # 步骤3: 清理临时文件
            self._cleanup_temp_files(single_page_files)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            print(f"✅ PDF处理完成，耗时: {processing_time:.2f} 秒")
            print(f"📊 成功处理 {len(pages_data)} 页")
            
            return pages_data
            
        except Exception as e:
            # 确保清理临时文件
            self._cleanup_temp_files(single_page_files)
            raise e
    
    def _split_pdf_to_pages(self, pdf_path: str) -> List[Tuple[int, str]]:
        """
        将PDF分割为单页文件
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            List[Tuple[int, str]]: [(页码, 单页PDF文件路径), ...]
        """
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix="pdf_pages_")
        single_page_files = []
        
        try:
            for page_num in range(total_pages):
                # 创建新的PDF文档，只包含当前页
                single_page_doc = fitz.open()
                single_page_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                
                # 保存单页PDF
                single_page_path = os.path.join(temp_dir, f"page_{page_num + 1}.pdf")
                single_page_doc.save(single_page_path)
                single_page_doc.close()
                
                single_page_files.append((page_num + 1, single_page_path))
                
        finally:
            doc.close()
        
        return single_page_files
    
    def _process_pages_parallel(self, 
                               single_page_files: List[Tuple[int, str]], 
                               output_dir: str) -> List[PageData]:
        """并行处理所有页面"""
        print(f"⚡ 启用并行处理模式，最大工作线程数: {self.config.media_extractor.max_workers}")
        
        pages_data = [None] * len(single_page_files)
        
        with ThreadPoolExecutor(max_workers=self.config.media_extractor.max_workers) as executor:
            # 提交所有任务
            future_to_page = {
                executor.submit(
                    self._process_single_page, 
                    page_num, 
                    single_page_path, 
                    output_dir
                ): page_num
                for page_num, single_page_path in single_page_files
            }
            
            # 收集结果
            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    page_data = future.result()
                    pages_data[page_num - 1] = page_data  # 页码从1开始，索引从0开始
                    print(f"✅ 页面 {page_num} 处理完成")
                except Exception as e:
                    print(f"❌ 页面 {page_num} 处理失败: {e}")
                    # 创建空的页面数据
                    pages_data[page_num - 1] = PageData(
                        page_number=page_num,
                        raw_text=f"页面 {page_num} 处理失败: {str(e)}",
                        images=[],
                        tables=[]
                    )
        
        # 过滤None值
        return [page for page in pages_data if page is not None]
    
    def _process_pages_sequential(self, 
                                 single_page_files: List[Tuple[int, str]], 
                                 output_dir: str) -> List[PageData]:
        """顺序处理所有页面"""
        print("🔄 使用顺序处理模式")
        
        pages_data = []
        for page_num, single_page_path in single_page_files:
            try:
                page_data = self._process_single_page(page_num, single_page_path, output_dir)
                pages_data.append(page_data)
                print(f"✅ 页面 {page_num} 处理完成")
            except Exception as e:
                print(f"❌ 页面 {page_num} 处理失败: {e}")
                # 创建空的页面数据
                pages_data.append(PageData(
                    page_number=page_num,
                    raw_text=f"页面 {page_num} 处理失败: {str(e)}",
                    images=[],
                    tables=[]
                ))
        
        return pages_data
    
    def _process_single_page(self, 
                            page_num: int, 
                            single_page_path: str, 
                            output_dir: str) -> PageData:
        """
        处理单页PDF
        
        Args:
            page_num: 页码
            single_page_path: 单页PDF文件路径
            output_dir: 输出目录
            
        Returns:
            PageData: 页面数据
        """
        # 创建页面专用的输出目录
        page_output_dir = os.path.join(output_dir, f"page_{page_num}")
        os.makedirs(page_output_dir, exist_ok=True)
        
        # 使用Docling处理单页PDF
        raw_result = self.doc_converter.convert(Path(single_page_path))
        
        # 提取页面文本
        page_text = self._extract_page_text(raw_result)
        
        # 创建页面数据
        page_data = PageData(
            page_number=page_num,
            raw_text=page_text,
            images=[],
            tables=[]
        )
        
        # 提取图片和表格 - 由于是单页PDF，所有媒体都属于当前页
        self._extract_media_for_single_page(raw_result, page_data, page_output_dir)
        
        return page_data
    
    def _extract_page_text(self, raw_result: Any) -> str:
        """从单页PDF的docling结果中提取文本"""
        try:
            # 导出为markdown格式
            raw_markdown = raw_result.document.export_to_markdown()
            
            # 清理markdown内容
            import re
            markdown_clean_pattern = re.compile(r"<!--[\s\S]*?-->")
            cleaned_text = markdown_clean_pattern.sub("", raw_markdown)
            
            return cleaned_text.strip()
            
        except Exception as e:
            print(f"⚠️ 页面文本提取失败: {e}")
            return ""
    
    def _extract_media_for_single_page(self, 
                                      raw_result: Any, 
                                      page_data: PageData, 
                                      page_output_dir: str):
        """为单页PDF提取图片和表格"""
        try:
            # 由于是单页PDF，所有媒体都属于当前页
            image_counter = 0
            table_counter = 0
            
            # 提取图片
            for picture in raw_result.document.pictures:
                image_counter += 1
                try:
                    # 获取图片
                    picture_image = picture.get_image(raw_result.document)
                    if picture_image is None:
                        continue
                    
                    # 保存图片
                    image_filename = f"picture-{image_counter}.png"
                    image_path = os.path.join(page_output_dir, image_filename)
                    with open(image_path, "wb") as fp:
                        picture_image.save(fp, "PNG")
                    
                    # 获取图片信息
                    from PIL import Image
                    image_img = Image.open(image_path)
                    caption = picture.caption_text(raw_result.document) if hasattr(picture, 'caption_text') else ""
                    
                    # 创建ImageWithContext对象
                    image_with_context = ImageWithContext(
                        image_path=image_path,
                        page_number=page_data.page_number,
                        page_context=page_data.raw_text,
                        caption=caption or f"图片 {image_counter}",
                        metadata={
                            'width': image_img.width,
                            'height': image_img.height,
                            'size': image_img.width * image_img.height,
                            'aspect_ratio': image_img.width / image_img.height
                        }
                    )
                    
                    page_data.images.append(image_with_context)
                    
                except Exception as e:
                    print(f"❌ 页面 {page_data.page_number} 图片 {image_counter} 处理失败: {e}")
            
            # 提取表格
            for table in raw_result.document.tables:
                table_counter += 1
                try:
                    # 获取表格图片
                    table_image = table.get_image(raw_result.document)
                    if table_image is None:
                        continue
                    
                    # 保存表格图片
                    table_filename = f"table-{table_counter}.png"
                    table_path = os.path.join(page_output_dir, table_filename)
                    with open(table_path, "wb") as fp:
                        table_image.save(fp, "PNG")
                    
                    # 获取表格信息
                    from PIL import Image
                    table_img = Image.open(table_path)
                    caption = table.caption_text(raw_result.document) if hasattr(table, 'caption_text') else ""
                    
                    # 创建TableWithContext对象
                    table_with_context = TableWithContext(
                        table_path=table_path,
                        page_number=page_data.page_number,
                        page_context=page_data.raw_text,
                        caption=caption or f"表格 {table_counter}",
                        metadata={
                            'width': table_img.width,
                            'height': table_img.height,
                            'size': table_img.width * table_img.height,
                            'aspect_ratio': table_img.width / table_img.height
                        }
                    )
                    
                    page_data.tables.append(table_with_context)
                    
                except Exception as e:
                    print(f"❌ 页面 {page_data.page_number} 表格 {table_counter} 处理失败: {e}")
            
            print(f"📊 页面 {page_data.page_number}: {len(page_data.images)} 个图片, {len(page_data.tables)} 个表格")
            
        except Exception as e:
            print(f"❌ 页面 {page_data.page_number} 媒体提取失败: {e}")
    
    def _cleanup_temp_files(self, single_page_files: List[Tuple[int, str]]):
        """清理临时文件"""
        if not single_page_files:
            return
        
        # 获取临时目录
        temp_dir = os.path.dirname(single_page_files[0][1])
        
        try:
            shutil.rmtree(temp_dir)
            print(f"🧹 清理临时文件: {temp_dir}")
        except Exception as e:
            print(f"⚠️ 清理临时文件失败: {e}")
    
    def get_pdf_info(self, pdf_path: str) -> Dict[str, Any]:
        """
        获取PDF基本信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            Dict[str, Any]: PDF信息
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        doc = fitz.open(pdf_path)
        
        try:
            info = {
                "file_path": pdf_path,
                "file_name": os.path.basename(pdf_path),
                "file_size": os.path.getsize(pdf_path),
                "total_pages": len(doc),
                "metadata": doc.metadata,
                "processing_config": {
                    "parallel_processing": self.config.parallel_processing,
                    "max_workers": self.config.max_workers,
                    "images_scale": self.config.docling.images_scale,
                    "ocr_enabled": self.config.docling.ocr_enabled
                }
            }
            
            return info
            
        finally:
            doc.close() 