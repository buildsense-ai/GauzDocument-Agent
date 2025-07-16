#!/usr/bin/env python3
"""
PDF Parser Tool - 重构版本
整合所有PDF处理组件，提供统一的工具接口
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import os

from .config import PDFProcessingConfig
from .pdf_document_parser import PDFDocumentParser
from .media_extractor import MediaExtractor
from .ai_content_reorganizer import AIContentReorganizer
from .toc_extractor import TOCExtractor
from .ai_chunker import AIChunker
from .text_chunker import TextChunker
from .data_models import ProcessingResult, PageData, ImageWithContext, TableWithContext
try:
    from ..base_tool import Tool
except ImportError:
    from base_tool import Tool

logger = logging.getLogger(__name__)


class PDFParserTool(Tool):
    """
    PDF解析工具 - 重构版本
    
    支持两种处理模式：
    1. 基础模式：页面级解析、媒体提取、AI内容重组
    2. 高级模式：包含文档结构分析、智能分块、元数据增强
    """
    
    def __init__(self, config: PDFProcessingConfig = None):
        super().__init__(
            name="pdf_parser",
            description="🚀 PDF解析工具 - 智能提取PDF中的文本、图片、表格，支持结构化分析和智能分块"
        )
        
        self.config = config or PDFProcessingConfig()
        
        # 初始化组件
        self._init_components()
        
        logger.info("✅ PDF解析工具初始化完成")
    
    def _init_components(self):
        """初始化所有组件"""
        try:
            # 基础处理组件
            self.document_parser = PDFDocumentParser(self.config)
            self.media_extractor = MediaExtractor(
                parallel_processing=self.config.media_extractor.parallel_processing,
                max_workers=self.config.media_extractor.max_workers
            )
            self.ai_reorganizer = AIContentReorganizer(self.config)
            
            # TOC和分块组件
            self.toc_extractor = TOCExtractor()
            self.ai_chunker = AIChunker()
            self.text_chunker = TextChunker()
            
            # Metadata处理组件
            from .metadata_extractor import MetadataExtractor
            from .document_summary_generator import DocumentSummaryGenerator
            from .chapter_summary_generator import ChapterSummaryGenerator
            from .question_generator import QuestionGenerator
            
            project_name = getattr(self.config, 'project_name', "default_project")
            self.metadata_extractor = MetadataExtractor(project_name)
            self.document_summary_generator = DocumentSummaryGenerator()
            self.chapter_summary_generator = ChapterSummaryGenerator()
            self.question_generator = QuestionGenerator()
            
        except Exception as e:
            logger.error(f"组件初始化失败: {e}")
            raise
    
    def execute(self, **kwargs) -> str:
        """
        执行PDF解析
        
        Args:
            action: 操作类型
                - "parse_basic": 基础解析模式（使用现有逻辑）
                - "parse_page_split": 页面分割解析模式（新增，解决页面标注漂移）
                - "parse_advanced": 高级解析模式（包含结构分析）
            pdf_path: PDF文件路径
            output_dir: 输出目录（可选）
            enable_ai_enhancement: 是否启用AI增强处理
            parallel_processing: 是否启用并行处理
            
        Returns:
            str: 解析结果的JSON字符串
        """
        action = kwargs.get("action", "parse_basic")
        
        if action == "parse_basic":
            return self._parse_basic(**kwargs)
        elif action == "parse_page_split":
            return self._parse_page_split(**kwargs)
        elif action == "parse_advanced":
            return json.dumps({
                "status": "error",
                "message": "高级解析模式暂时不可用，请使用 parse_basic 或 parse_page_split"
            }, indent=2, ensure_ascii=False)
        else:
            return json.dumps({
                "status": "error",
                "message": f"不支持的操作: {action}。支持的操作: parse_basic, parse_page_split"
            }, indent=2, ensure_ascii=False)
    
    def _parse_basic(self, pdf_path: str, output_dir: str = None, enable_ai_enhancement: bool = True) -> str:
        """
        基础解析模式
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            enable_ai_enhancement: 是否启用AI增强
            
        Returns:
            str: JSON格式的处理结果
        """
        start_time = time.time()
        
        logger.info(f"🚀 开始基础解析: {pdf_path}")
        
        try:
            # 验证输入
            if not Path(pdf_path).exists():
                return json.dumps({
                    "status": "error",
                    "message": f"PDF文件不存在: {pdf_path}"
                }, ensure_ascii=False)
            
            # 设置输出目录
            if output_dir is None:
                from .config import create_output_directory
                output_dir = create_output_directory(self.config)
            
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 第一步：解析PDF文档
            logger.info("📄 第一步：解析PDF文档")
            raw_result, page_texts = self.document_parser.parse_pdf(pdf_path)
            
            # 第二步：提取媒体文件
            logger.info("🖼️ 第二步：提取媒体文件")
            pages = self.media_extractor.extract_media_from_pages(
                raw_result=raw_result,
                page_texts=page_texts,
                output_dir=str(output_path)
            )
            
            # 保存媒体信息
            self.media_extractor.save_media_info(pages, str(output_path))
            
            # 构建ProcessingResult对象
            from .data_models import ProcessingResult
            media_result = ProcessingResult(
                source_file=pdf_path,
                pages=pages
            )
            
            # 第三步：AI内容重组（可选）
            if enable_ai_enhancement:
                logger.info("🧠 第三步：AI内容重组")
                enhanced_pages = self.ai_reorganizer.process_pages(
                    pages, 
                    parallel_processing=self.config.ai_content.enable_parallel_processing
                )
                # 更新处理结果
                media_result.pages = enhanced_pages
            
            # 构建处理结果
            final_result = media_result
            
            # 计算处理时间
            processing_time = time.time() - start_time
            final_result.summary["processing_time"] = processing_time
            
            # 保存结果
            result_file = output_path / "basic_processing_result.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(final_result.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 基础解析完成，耗时: {processing_time:.2f}秒")
            
            return json.dumps({
                "status": "success",
                "message": "基础解析完成",
                "result": final_result.to_dict(),
                "output_files": {
                    "result_file": str(result_file),
                    "output_directory": str(output_path)
                }
            }, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"基础解析失败: {e}")
            return json.dumps({
                "status": "error",
                "message": f"基础解析失败: {str(e)}"
            }, ensure_ascii=False)
    
    def _parse_page_split(self, **kwargs) -> str:
        """
        使用页面分割方法解析PDF（解决页面标注漂移问题）
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            enable_ai_enhancement: 是否启用AI增强处理
            parallel_processing: 是否启用并行处理
            
        Returns:
            str: 解析结果的JSON字符串
        """
        import time
        import tempfile
        import fitz  # PyMuPDF
        from pathlib import Path
        
        # 检查必需参数
        pdf_path = kwargs.get("pdf_path")
        if not pdf_path:
            return json.dumps({
                "status": "error",
                "message": "缺少必需参数: pdf_path"
            }, indent=2, ensure_ascii=False)
        
        if not os.path.exists(pdf_path):
            return json.dumps({
                "status": "error", 
                "message": f"PDF文件不存在: {pdf_path}"
            }, indent=2, ensure_ascii=False)
        
        # 获取配置
        output_dir = kwargs.get("output_dir")
        if not output_dir:
            # 创建基于时间戳的输出目录
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"parser_output/{timestamp}_page_split"
            os.makedirs(output_dir, exist_ok=True)
        
        enable_ai_enhancement = kwargs.get("enable_ai_enhancement", True)
        
        # 区分两种并行处理
        docling_parallel_processing = kwargs.get("docling_parallel_processing", False)  # docling并行处理，Mac上禁用
        ai_parallel_processing = kwargs.get("ai_parallel_processing", True)  # AI并行处理，可独立启用
        
        # 向后兼容：如果使用旧的parallel_processing参数
        if "parallel_processing" in kwargs:
            docling_parallel_processing = kwargs.get("parallel_processing", False)
            # AI并行处理保持启用，除非显式禁用
            ai_parallel_processing = kwargs.get("ai_parallel_processing", True)
        
        print(f"🔄 开始页面分割解析: {pdf_path}")
        print(f"📁 输出目录: {output_dir}")
        print(f"🧠 AI增强: {'启用' if enable_ai_enhancement else '禁用'}")
        print(f"⚡ Docling并行处理: {'启用' if docling_parallel_processing else '禁用'}")
        print(f"🚀 AI并行处理: {'启用' if ai_parallel_processing else '禁用'}")
        
        start_time = time.time()
        
        try:
            # 步骤1: 分割PDF为单页文件
            pages_data = self._split_and_process_pdf_pages(pdf_path, output_dir, docling_parallel_processing)
            
            # 步骤2: AI增强处理（如果启用）
            if enable_ai_enhancement:
                print("🧠 开始AI增强处理...")
                pages_data = self.ai_reorganizer.process_pages(pages_data, ai_parallel_processing)
            
            # 步骤3: 生成处理结果
            from .data_models import ProcessingResult
            result = ProcessingResult(
                source_file=pdf_path,
                pages=pages_data
            )
            
            # 步骤4: 保存结果
            result_file = os.path.join(output_dir, "page_split_processing_result.json")
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            
            # 步骤5: TOC提取（基于缝合后的完整文本）
            print("📖 开始TOC提取...")
            try:
                full_text = self.toc_extractor.stitch_full_text(result_file)
                toc_items, reasoning_content = self.toc_extractor.extract_toc_with_reasoning(full_text)
                
                # 保存TOC结果
                toc_result = {
                    "toc": [item.__dict__ for item in toc_items],
                    "reasoning_content": reasoning_content
                }
                toc_file = os.path.join(output_dir, "toc_extraction_result.json")
                with open(toc_file, 'w', encoding='utf-8') as f:
                    json.dump(toc_result, f, ensure_ascii=False, indent=2)
                
                print(f"✅ TOC提取完成，共找到 {len(toc_items)} 个章节")
                
            except Exception as e:
                print(f"❌ TOC提取失败: {e}")
                toc_items = []
                toc_result = {"toc": [], "reasoning_content": ""}
            
            # 步骤6: AI分块（基于TOC结果）
            print("🔪 开始AI分块...")
            chunks_result = None
            try:
                if toc_items:
                    chunks_result = self.text_chunker.chunk_text_with_toc(full_text, toc_result)
                    
                    # 保存分块结果
                    chunks_file = os.path.join(output_dir, "chunks_result.json")
                    chunks_dict = {
                        "first_level_chapters": [
                            {
                                "chapter_id": chapter.chapter_id,
                                "title": chapter.title,
                                "content": chapter.content,
                                "start_pos": chapter.start_pos,
                                "end_pos": chapter.end_pos,
                                "word_count": chapter.word_count,
                                "has_images": chapter.has_images,
                                "has_tables": chapter.has_tables
                            }
                            for chapter in chunks_result.first_level_chapters
                        ],
                        "minimal_chunks": [
                            {
                                "chunk_id": chunk.chunk_id,
                                "content": chunk.content,
                                "chunk_type": chunk.chunk_type,
                                "belongs_to_chapter": chunk.belongs_to_chapter,
                                "chapter_title": chunk.chapter_title,
                                "start_pos": chunk.start_pos,
                                "end_pos": chunk.end_pos,
                                "word_count": chunk.word_count
                            }
                            for chunk in chunks_result.minimal_chunks
                        ],
                        "total_chapters": chunks_result.total_chapters,
                        "total_chunks": chunks_result.total_chunks,
                        "processing_metadata": chunks_result.processing_metadata
                    }
                    with open(chunks_file, 'w', encoding='utf-8') as f:
                        json.dump(chunks_dict, f, ensure_ascii=False, indent=2)
                    
                    print(f"✅ AI分块完成，共生成 {chunks_result.total_chunks} 个分块")
                else:
                    print("⚠️ 没有TOC信息，跳过分块步骤")
                    
            except Exception as e:
                print(f"❌ AI分块失败: {e}")
            
            # 步骤7: Metadata处理（基于前面的所有结果）
            print("📊 开始Metadata处理...")
            try:
                metadata_dir = os.path.join(output_dir, "metadata")
                os.makedirs(metadata_dir, exist_ok=True)
                
                # 7.1 提取基础metadata
                basic_metadata = self.metadata_extractor.extract_from_page_split_result(result_file)
                document_id = basic_metadata["document_info"]["document_id"]
                
                # 处理TOC metadata（需要使用TOC文件路径）
                if toc_result and toc_result.get("toc"):
                    toc_metadata = self.metadata_extractor.extract_from_toc_result(toc_file, document_id)
                    # 这里需要合并元数据，由于extract_from_toc_result返回tuple，需要处理
                    doc_toc, chapter_mapping = toc_metadata
                    basic_metadata["toc"] = doc_toc.__dict__
                
                # 提取图片和表格metadata并分配章节ID
                if chunks_result:
                    image_metadata = self.metadata_extractor._extract_image_metadata(result.to_dict(), document_id)
                    table_metadata = self.metadata_extractor._extract_table_metadata(result.to_dict(), document_id)
                    
                    chunking_metadata = self.metadata_extractor.extract_from_chunking_result(chunks_result, image_metadata, table_metadata)
                    basic_metadata.update(chunking_metadata)
                
                # 保存基础metadata（使用metadata_extractor的正确序列化方法）
                self.metadata_extractor.save_extracted_metadata(
                    metadata_dir,
                    basic=basic_metadata
                )
                
                # 7.2 生成文档摘要
                if chunks_result:
                    document_summary = self.document_summary_generator.generate_document_summary(
                        document_info=basic_metadata["document_info"],
                        chunking_result=chunks_result,
                        toc_data=toc_result,
                        image_count=len(basic_metadata.get("image_metadata", [])),
                        table_count=len(basic_metadata.get("table_metadata", []))
                    )
                    
                    # 保存文档摘要（document_summary是tuple）
                    doc_summary_file = os.path.join(metadata_dir, "document_summary.json")
                    with open(doc_summary_file, 'w', encoding='utf-8') as f:
                        json.dump(document_summary[0].__dict__, f, ensure_ascii=False, indent=2, default=str)
                
                # 7.3 生成章节摘要
                if chunks_result and chunks_result.first_level_chapters and 'chapter_mapping' in locals():
                    chapter_summaries = self.chapter_summary_generator.generate_chapter_summaries(
                        document_id=document_id,
                        chunking_result=chunks_result,
                        toc_data=toc_result,
                        image_metadata=basic_metadata.get("image_metadata", []),
                        table_metadata=basic_metadata.get("table_metadata", [])
                    )
                    
                    # 保存章节摘要（chapter_summaries是list of tuples）
                    chapter_summary_file = os.path.join(metadata_dir, "chapter_summaries.json")
                    chapter_summaries_data = [summary[0].__dict__ for summary in chapter_summaries]
                    with open(chapter_summary_file, 'w', encoding='utf-8') as f:
                        json.dump(chapter_summaries_data, f, ensure_ascii=False, indent=2, default=str)
                
                # 7.4 生成衍生问题
                if chunks_result and chunks_result.minimal_chunks and 'chapter_mapping' in locals():
                    derived_questions = self.question_generator.generate_questions_from_chunks(
                        document_id=document_id,
                        chunking_result=chunks_result,
                        chapter_mapping=chapter_mapping
                    )
                    
                    # 保存衍生问题（derived_questions是list of tuples）
                    questions_file = os.path.join(metadata_dir, "derived_questions.json")
                    questions_data = [question[0].__dict__ for question in derived_questions]
                    with open(questions_file, 'w', encoding='utf-8') as f:
                        json.dump(questions_data, f, ensure_ascii=False, indent=2, default=str)
                
                print(f"✅ Metadata处理完成，结果保存在: {metadata_dir}")
                
            except Exception as e:
                print(f"❌ Metadata处理失败: {e}")
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            print(f"✅ 完整流程处理完成（包含Metadata），耗时: {processing_time:.2f} 秒")
            
            # 构建完整的返回结果
            response_data = {
                "status": "success",
                "message": "页面分割解析完成",
                "output_directory": output_dir,
                "processing_time": processing_time,
                "pages": [page.to_dict() for page in pages_data],
                "pages_count": len(pages_data),
                "toc_count": len(toc_items),
                "chunks_count": chunks_result.total_chunks if chunks_result else 0
            }
            
            return json.dumps(response_data, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"页面分割解析失败: {e}")
            return json.dumps({
                "status": "error",
                "message": f"页面分割解析失败: {str(e)}"
            }, indent=2, ensure_ascii=False)
    
    def _split_and_process_pdf_pages(self, pdf_path: str, output_dir: str, parallel_processing: bool) -> List[PageData]:
        """
        分割PDF并处理每一页
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            parallel_processing: 是否启用并行处理
            
        Returns:
            List[PageData]: 所有页面的处理结果
        """
        import fitz  # PyMuPDF
        import tempfile
        import shutil
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # 步骤1: 分割PDF为单页文件
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
        
        print(f"📄 PDF分割完成，共 {len(single_page_files)} 页")
        
        # 步骤2: 处理所有页面
        try:
            if parallel_processing and len(single_page_files) > 1:
                pages_data = self._process_pages_parallel_split(single_page_files, output_dir)
            else:
                pages_data = self._process_pages_sequential_split(single_page_files, output_dir)
            
            # 步骤3: 清理临时文件
            shutil.rmtree(temp_dir)
            print(f"🧹 清理临时文件: {temp_dir}")
            
            return pages_data
            
        except Exception as e:
            # 确保清理临时文件
            shutil.rmtree(temp_dir)
            raise e
    
    def _process_pages_parallel_split(self, single_page_files: List[Tuple[int, str]], output_dir: str) -> List[PageData]:
        """并行处理分割后的页面"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        max_workers = self.config.media_extractor.max_workers
        print(f"⚡ 启用并行处理模式，最大工作线程数: {max_workers}")
        
        pages_data = [None] * len(single_page_files)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_page = {
                executor.submit(
                    self._process_single_page_split, 
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
    
    def _process_pages_sequential_split(self, single_page_files: List[Tuple[int, str]], output_dir: str) -> List[PageData]:
        """顺序处理分割后的页面"""
        print("🔄 使用顺序处理模式")
        
        pages_data = []
        for page_num, single_page_path in single_page_files:
            try:
                page_data = self._process_single_page_split(page_num, single_page_path, output_dir)
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
    
    def _process_single_page_split(self, page_num: int, single_page_path: str, output_dir: str) -> PageData:
        """
        处理单页PDF
        
        Args:
            page_num: 页码
            single_page_path: 单页PDF文件路径
            output_dir: 输出目录
            
        Returns:
            PageData: 页面数据
        """
        from pathlib import Path
        
        # 创建页面专用的输出目录
        page_output_dir = os.path.join(output_dir, f"page_{page_num}")
        os.makedirs(page_output_dir, exist_ok=True)
        
        # 使用现有的PDF解析器处理单页PDF
        raw_result, page_texts = self.document_parser.parse_pdf(single_page_path)
        
        # 由于是单页PDF，应该只有一页文本
        page_text = ""
        if page_texts:
            page_text = next(iter(page_texts.values()))  # 获取第一个（也是唯一一个）页面的文本
        
        # 创建页面数据
        page_data = PageData(
            page_number=page_num,
            raw_text=page_text,
            images=[],
            tables=[]
        )
        
        # 提取图片和表格 - 由于是单页PDF，所有媒体都属于当前页
        self._extract_media_for_single_page_split(raw_result, page_data, page_output_dir)
        
        return page_data
    
    def _extract_media_for_single_page_split(self, raw_result: Any, page_data: PageData, page_output_dir: str):
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
    
    def _parse_advanced_disabled(self, pdf_path: str, output_dir: str = None, enable_ai_enhancement: bool = True) -> str:
        """
        高级解析模式（暂时禁用）
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            enable_ai_enhancement: 是否启用AI增强
            
        Returns:
            str: JSON格式的处理结果
        """
        return json.dumps({
            "status": "error",
            "message": "高级解析模式暂时不可用，相关组件正在重构中。请使用 parse_basic 或 parse_page_split 模式。"
        }, indent=2, ensure_ascii=False)
    
    def _get_config(self) -> str:
        """获取配置信息"""
        from .config import create_output_directory
        
        output_dir = create_output_directory(self.config)
        
        return json.dumps({
            "status": "success",
            "config": {
                "output_dir": output_dir,
                "default_llm_model": self.config.ai_content.default_llm_model,
                "default_vlm_model": self.config.ai_content.default_vlm_model,
                "supported_models": self.config.supported_models,
                "max_concurrent_tasks": self.config.ai_content.max_workers,
                "enable_parallel_processing": self.config.ai_content.enable_parallel_processing,
                "enable_text_cleaning": self.config.ai_content.enable_text_cleaning,
                "enable_image_description": self.config.ai_content.enable_image_description,
                "enable_table_description": self.config.ai_content.enable_table_description,
                "base_output_dir": self.config.output.base_output_dir,
                "create_timestamped_dirs": self.config.output.create_timestamped_dirs,
                "custom_output_path": self.config.output.custom_output_path
            }
        }, ensure_ascii=False)
    
    # 保持向后兼容的接口
    def parse_pdf(self, pdf_path: str, output_dir: str = None, use_advanced: bool = False) -> Dict[str, Any]:
        """
        解析PDF文件（向后兼容接口）
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            use_advanced: 是否使用高级解析
            
        Returns:
            Dict[str, Any]: 解析结果
        """
        action = "parse_advanced" if use_advanced else "parse_basic"
        result_json = self.execute(action, pdf_path=pdf_path, output_dir=output_dir)
        return json.loads(result_json) 