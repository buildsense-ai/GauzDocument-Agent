#!/usr/bin/env python3
"""
文档结构分析器（重构版）
基于Docling HierarchicalChunker的无幻觉文档结构分析和分块
专注于文本处理，极速分块
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from .config import PDFProcessingConfig

# 导入Docling组件
try:
    from docling.document_converter import DocumentConverter
    from docling.chunking import HierarchicalChunker
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
    from docling.document_converter import PdfFormatOption
    DOCLING_AVAILABLE = True
    print("✅ Docling组件可用（DocumentStructureAnalyzer）")
except ImportError as e:
    DOCLING_AVAILABLE = False
    print(f"❌ Docling组件不可用（DocumentStructureAnalyzer）: {e}")

logger = logging.getLogger(__name__)

@dataclass
class ChapterInfo:
    """章节信息"""
    chapter_id: str  # 如 "1", "2.1", "3.2.1"
    level: int  # 层级：1, 2, 3...
    title: str  # 章节标题
    content_summary: str  # 章节内容概要
    
@dataclass
class DocumentStructure:
    """文档结构数据类"""
    toc: List[ChapterInfo]  # 目录结构
    total_pages: int  # 总页数（来源于基础处理）
    
@dataclass
class MinimalChunk:
    """最小颗粒度分块信息"""
    chunk_id: int
    content: str  # 实际内容（段落、列表项等）
    chunk_type: str  # 类型：paragraph, list_item, heading等
    belongs_to_chapter: str  # 所属章节ID，如 "1", "2.1", "3.2.1"
    chapter_title: str  # 所属章节标题
    chapter_level: int  # 所属章节层级

class DocumentStructureAnalyzer:
    """
    文档结构分析器（重构版）
    
    基于Docling HierarchicalChunker的无幻觉文档结构分析和分块
    专注于文本处理，极速分块（~0.02秒）
    """
    
    def __init__(self, config: PDFProcessingConfig = None):
        """
        初始化文档结构分析器
        
        Args:
            config: PDF处理配置
        """
        self.config = config or PDFProcessingConfig()
        
        # 初始化Docling组件
        self.doc_converter = self._init_docling_converter()
        self.chunker = self._init_chunker()
        
        logger.info("📊 文档结构分析器已初始化")
    
    def _init_docling_converter(self):
        """初始化Docling转换器"""
        if not DOCLING_AVAILABLE:
            logger.warning("Docling不可用，将使用降级处理")
            return None
        
        try:
            # 配置PDF处理选项
            pdf_options = PdfPipelineOptions(
                do_ocr=False,  # 禁用OCR以提高速度
                do_table_structure=False,  # 禁用表格结构识别
                ocr_options=EasyOcrOptions(lang=["en"])
            )
            
            # 创建文档转换器
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)
                }
            )
            
            logger.info("✅ Docling转换器初始化完成")
            return converter
            
        except Exception as e:
            logger.error(f"Docling转换器初始化失败: {e}")
            return None
    
    def _init_chunker(self):
        """初始化分块器"""
        if not DOCLING_AVAILABLE:
            return None
            
        try:
            # 使用HierarchicalChunker进行层次化分块
            chunker = HierarchicalChunker(
                tokenizer=None,  # 使用默认分词器
                max_tokens=512,  # 最大token数
                overlap_token_count=50,  # 重叠token数
                include_metadata=True  # 包含元数据
            )
            
            logger.info("✅ Docling分块器初始化完成")
            return chunker
            
        except Exception as e:
            logger.error(f"分块器初始化失败: {e}")
            return None
    
    def analyze_and_chunk(self, pdf_path: str, output_dir: str) -> Tuple[DocumentStructure, List[MinimalChunk]]:
        """
        基于Docling的文档结构分析和分块
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            Tuple[DocumentStructure, List[MinimalChunk]]: 文档结构和最小分块
        """
        logger.info(f"📊 开始Docling文档结构分析: {pdf_path}")
        
        if not self.doc_converter or not self.chunker:
            logger.warning("Docling组件不可用，使用降级处理")
            return self._fallback_analysis(pdf_path, output_dir)
        
        try:
            # 1. 解析PDF文档
            logger.info("🔄 解析PDF文档...")
            raw_result = self.doc_converter.convert(Path(pdf_path))
            document = raw_result.document
            
            # 2. 使用HierarchicalChunker进行分块
            logger.info("🔪 使用Docling分块器进行结构化分块...")
            chunks = list(self.chunker.chunk(document))
            logger.info(f"✅ 完成分块: {len(chunks)} 个分块")
            
            # 3. 提取文档结构（TOC）
            document_structure = self._extract_document_structure(chunks, pdf_path)
            
            # 4. 转换为MinimalChunk格式
            minimal_chunks = self._convert_to_minimal_chunks(chunks, document_structure)
            
            # 5. 保存结果
            self._save_results(document_structure, minimal_chunks, output_dir)
            
            logger.info(f"✅ 文档结构分析完成: {len(minimal_chunks)} 个分块")
            
            return document_structure, minimal_chunks
            
        except Exception as e:
            logger.error(f"Docling分析失败: {e}")
            return self._fallback_analysis(pdf_path, output_dir)
    
    def _extract_document_structure(self, chunks: List, pdf_path: str) -> DocumentStructure:
        """从Docling分块中提取文档结构（TOC）"""
        try:
            toc = []
            
            # 从分块中提取标题层次
            for chunk in chunks:
                if hasattr(chunk, 'meta') and hasattr(chunk.meta, 'headings'):
                    headings = chunk.meta.headings
                    
                    for heading in headings:
                        # heading是字符串，不是对象
                        if isinstance(heading, str) and heading.strip():
                            # 简单的层级判断
                            level = 1
                            title = heading.strip()
                            
                            # 尝试从标题中提取层级
                            import re
                            # 匹配 "1. Introduction" 或 "2.1. Task specification" 格式
                            number_match = re.match(r'^(\d+(?:\.\d+)*)\.\s*(.+)$', title)
                            if number_match:
                                number_part = number_match.group(1)
                                title_part = number_match.group(2)
                                level = len(number_part.split('.'))  # 根据点的数量确定层级
                                title = title_part
                            
                            # 生成章节ID
                            chapter_id = f"section_{len(toc) + 1}"
                            
                            # 创建章节信息
                            chapter_info = ChapterInfo(
                                chapter_id=chapter_id,
                                level=level,
                                title=title,
                                content_summary=title[:100] + "..." if len(title) > 100 else title
                            )
                            
                            toc.append(chapter_info)
            
            # 如果没有找到标题，创建一个默认结构
            if not toc:
                toc = [ChapterInfo(
                    chapter_id="section_1",
                    level=1,
                    title="文档内容",
                    content_summary="文档的主要内容"
                )]
            
            # 获取总页数（从文档信息中获取）
            total_pages = getattr(chunks[0].meta, 'page_count', 1) if chunks else 1
            
            return DocumentStructure(
                toc=toc,
                total_pages=total_pages
            )
            
        except Exception as e:
            logger.error(f"提取文档结构失败: {e}")
            return DocumentStructure(
                toc=[ChapterInfo(
                    chapter_id="section_1",
                    level=1,
                    title="文档内容",
                    content_summary="文档的主要内容"
                )],
                total_pages=1
            )
    
    def _convert_to_minimal_chunks(self, chunks: List, document_structure: DocumentStructure) -> List[MinimalChunk]:
        """将Docling分块转换为MinimalChunk格式"""
        minimal_chunks = []
        
        for i, chunk in enumerate(chunks):
            try:
                # 提取内容
                content = chunk.text if hasattr(chunk, 'text') else str(chunk)
                
                # 确定分块类型
                chunk_type = "paragraph"  # 默认类型
                if hasattr(chunk, 'meta') and hasattr(chunk.meta, 'doc_items'):
                    # 根据文档项目类型确定分块类型
                    doc_items = chunk.meta.doc_items
                    if doc_items:
                        first_item = doc_items[0]
                        if hasattr(first_item, 'label'):
                            chunk_type = first_item.label.lower()
                
                # 确定所属章节
                belongs_to_chapter = "section_1"  # 默认章节
                chapter_title = "文档内容"  # 默认标题
                chapter_level = 1  # 默认层级
                
                # 尝试从文档结构中找到匹配的章节
                if document_structure.toc:
                    # 简单的章节归属：基于位置比例
                    chapter_index = min(i // max(1, len(chunks) // len(document_structure.toc)), len(document_structure.toc) - 1)
                    chapter = document_structure.toc[chapter_index]
                    belongs_to_chapter = chapter.chapter_id
                    chapter_title = chapter.title
                    chapter_level = chapter.level
                
                # 创建MinimalChunk
                minimal_chunk = MinimalChunk(
                    chunk_id=i + 1,
                    content=content,
                    chunk_type=chunk_type,
                    belongs_to_chapter=belongs_to_chapter,
                    chapter_title=chapter_title,
                    chapter_level=chapter_level
                )
                
                minimal_chunks.append(minimal_chunk)
                
            except Exception as e:
                logger.error(f"转换分块 {i} 失败: {e}")
                continue
        
        return minimal_chunks
    
    def _save_results(self, document_structure: DocumentStructure, minimal_chunks: List[MinimalChunk], output_dir: str):
        """保存分析结果"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存文档结构
            structure_file = os.path.join(output_dir, "document_structure.json")
            with open(structure_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "total_pages": document_structure.total_pages,
                    "toc": [
                        {
                            "chapter_id": chapter.chapter_id,
                            "level": chapter.level,
                            "title": chapter.title,
                            "content_summary": chapter.content_summary
                        }
                        for chapter in document_structure.toc
                    ]
                }, f, ensure_ascii=False, indent=2)
            
            # 保存分块结果
            chunks_file = os.path.join(output_dir, "chunks.json")
            with open(chunks_file, 'w', encoding='utf-8') as f:
                json.dump([
                    {
                        "chunk_id": chunk.chunk_id,
                        "content": chunk.content,
                        "chunk_type": chunk.chunk_type,
                        "belongs_to_chapter": chunk.belongs_to_chapter,
                        "chapter_title": chunk.chapter_title,
                        "chapter_level": chunk.chapter_level
                    }
                    for chunk in minimal_chunks
                ], f, ensure_ascii=False, indent=2)
            
            logger.info(f"📄 结果已保存到: {output_dir}")
            
        except Exception as e:
            logger.error(f"保存结果失败: {e}")
    
    def _fallback_analysis(self, pdf_path: str, output_dir: str) -> Tuple[DocumentStructure, List[MinimalChunk]]:
        """降级分析：当Docling不可用时的简单处理"""
        logger.info("🔄 使用降级文档结构分析")
        
        try:
            # 创建基本的文档结构
            document_structure = DocumentStructure(
                toc=[ChapterInfo(
                    chapter_id="section_1",
                    level=1,
                    title="文档内容",
                    content_summary="文档的主要内容"
                )],
                total_pages=1
            )
            
            # 创建基本的分块
            minimal_chunks = [MinimalChunk(
                chunk_id=1,
                content="降级处理：无法进行详细的文档结构分析",
                chunk_type="paragraph",
                belongs_to_chapter="section_1",
                chapter_title="文档内容",
                chapter_level=1
            )]
            
            # 保存结果
            self._save_results(document_structure, minimal_chunks, output_dir)
            
            return document_structure, minimal_chunks
            
        except Exception as e:
            logger.error(f"降级分析失败: {e}")
            return DocumentStructure(toc=[], total_pages=0), [] 