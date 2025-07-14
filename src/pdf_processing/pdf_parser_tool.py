#!/usr/bin/env python3
"""
PDF Parser Tool - 重构版本
整合所有PDF处理组件，提供统一的工具接口
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

from .config import PDFProcessingConfig
from .pdf_document_parser import PDFDocumentParser
from .media_extractor import MediaExtractor
from .ai_content_reorganizer import AIContentReorganizer
from .document_structure_analyzer import DocumentStructureAnalyzer, MinimalChunk
from .metadata_enricher import MetadataEnricher, EnrichedChunk, ChapterSummary
from .data_models import ProcessingResult, AdvancedProcessingResult
from ..base_tool import Tool

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
            
            # 高级处理组件
            self.structure_analyzer = DocumentStructureAnalyzer(self.config)
            self.metadata_enricher = MetadataEnricher(self.config)
            
        except Exception as e:
            logger.error(f"组件初始化失败: {e}")
            raise
    
    def execute(self, action: str, **kwargs) -> str:
        """
        执行PDF处理操作
        
        Args:
            action: 操作类型
                - "parse_basic": 基础解析
                - "parse_advanced": 高级解析（包含结构分析）
                - "get_config": 获取配置信息
            **kwargs: 其他参数
                - pdf_path: PDF文件路径
                - output_dir: 输出目录
                - enable_ai_enhancement: 是否启用AI增强
                
        Returns:
            str: JSON格式的处理结果
        """
        try:
            if action == "parse_basic":
                return self._parse_basic(**kwargs)
            elif action == "parse_advanced":
                return self._parse_advanced(**kwargs)
            elif action == "get_config":
                return self._get_config()
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"不支持的操作类型: {action}",
                    "supported_actions": ["parse_basic", "parse_advanced", "get_config"]
                }, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"执行操作失败: {e}")
            return json.dumps({
                "status": "error", 
                "message": f"执行失败: {str(e)}"
            }, ensure_ascii=False)
    
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
    
    def _parse_advanced(self, pdf_path: str, output_dir: str = None, enable_ai_enhancement: bool = True) -> str:
        """
        高级解析模式
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            enable_ai_enhancement: 是否启用AI增强
            
        Returns:
            str: JSON格式的处理结果
        """
        start_time = time.time()
        
        logger.info(f"🚀 开始高级解析: {pdf_path}")
        
        try:
            # 首先执行基础解析
            basic_result_json = self._parse_basic(pdf_path, output_dir, enable_ai_enhancement)
            basic_result_data = json.loads(basic_result_json)
            
            if basic_result_data["status"] != "success":
                return basic_result_json
            
            # 获取基础处理结果
            basic_result = ProcessingResult(
                source_file=pdf_path,
                pages=[]  # 这里需要从basic_result_data重建PageData对象
            )
            
            # 重建PageData对象（简化版本）
            for page_data in basic_result_data["result"]["pages"]:
                from .data_models import PageData, ImageWithContext, TableWithContext
                
                images = []
                for img_data in page_data["images"]:
                    image = ImageWithContext(
                        image_path=img_data["image_path"],
                        page_number=img_data["page_number"],
                        page_context=img_data["page_context"],
                        ai_description=img_data.get("ai_description"),
                        caption=img_data.get("caption"),
                        metadata=img_data.get("metadata", {})
                    )
                    images.append(image)
                
                tables = []
                for table_data in page_data["tables"]:
                    table = TableWithContext(
                        table_path=table_data["table_path"],
                        page_number=table_data["page_number"],
                        page_context=table_data["page_context"],
                        ai_description=table_data.get("ai_description"),
                        caption=table_data.get("caption"),
                        metadata=table_data.get("metadata", {})
                    )
                    tables.append(table)
                
                page = PageData(
                    page_number=page_data["page_number"],
                    raw_text=page_data["raw_text"],
                    cleaned_text=page_data.get("cleaned_text"),
                    images=images,
                    tables=tables
                )
                basic_result.pages.append(page)
            
            # 设置输出目录
            if output_dir is None:
                from .config import create_output_directory
                output_dir = create_output_directory(self.config)
            output_path = Path(output_dir)
            
            # 第四步：文档结构分析和智能分块
            logger.info("📊 第四步：文档结构分析和智能分块")
            
            # 合并所有页面的清洗文本
            full_text = ""
            for page in basic_result.pages:
                page_text = page.cleaned_text if page.cleaned_text else page.raw_text
                full_text += page_text + "\n\n"
            
            document_structure, minimal_chunks = self.structure_analyzer.analyze_and_chunk(
                full_text, 
                basic_result.summary["total_pages"]
            )
            
            # 第五步：元数据增强
            logger.info("🔍 第五步：元数据增强")
            index_structure = self.metadata_enricher.enrich_metadata(
                document_structure,
                minimal_chunks,
                basic_result
            )
            
            # 构建高级处理结果
            processing_time = time.time() - start_time
            processing_metadata = {
                "total_processing_time": processing_time,
                "basic_processing_time": basic_result_data["result"]["summary"]["processing_time"],
                "advanced_processing_time": processing_time - basic_result_data["result"]["summary"]["processing_time"],
                "cache_optimization_enabled": True,
                "chunks_generated": len(minimal_chunks),
                "chapters_identified": len(document_structure.toc)
            }
            
            advanced_result = AdvancedProcessingResult(
                basic_result=basic_result,
                document_structure=document_structure,
                index_structure=index_structure,
                processing_metadata=processing_metadata
            )
            
            # 保存高级结果
            advanced_result_file = output_path / "advanced_processing_result.json"
            with open(advanced_result_file, 'w', encoding='utf-8') as f:
                json.dump(advanced_result.to_dict(), f, ensure_ascii=False, indent=2)
            
            # 保存索引结构
            index_file = output_path / "index_structure.json"
            self.metadata_enricher.save_index_structure(index_structure, str(index_file))
            
            logger.info(f"✅ 高级解析完成，耗时: {processing_time:.2f}秒")
            
            return json.dumps({
                "status": "success",
                "message": "高级解析完成",
                "result": advanced_result.to_dict(),
                "output_files": {
                    "advanced_result_file": str(advanced_result_file),
                    "index_file": str(index_file),
                    "output_directory": str(output_path)
                },
                "performance_metrics": {
                    "total_time": processing_time,
                    "chunks_generated": len(minimal_chunks),
                    "chapters_identified": len(document_structure.toc),
                    "cache_optimization": "enabled"
                }
            }, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"高级解析失败: {e}")
            return json.dumps({
                "status": "error",
                "message": f"高级解析失败: {str(e)}"
            }, ensure_ascii=False)
    
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