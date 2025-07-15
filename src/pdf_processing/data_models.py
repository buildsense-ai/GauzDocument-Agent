"""
PDF Processing Data Models

定义PDF处理过程中使用的标准化数据结构
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImageWithContext:
    """图片及其上下文信息"""
    image_path: str
    page_number: int
    page_context: str  # 该页面的所有文字
    ai_description: Optional[str] = None
    caption: Optional[str] = None  # 原始caption（可选，很多图片没有有意义的caption）
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "image_path": self.image_path,
            "page_number": self.page_number,
            "page_context": self.page_context,
            "ai_description": self.ai_description,
            "caption": self.caption,
            "metadata": self.metadata
        }


@dataclass
class TableWithContext:
    """表格及其上下文信息"""
    table_path: str
    page_number: int
    page_context: str  # 该页面的所有文字
    ai_description: Optional[str] = None
    caption: Optional[str] = None  # 原始caption（可选，很多表格没有有意义的caption）
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "table_path": self.table_path,
            "page_number": self.page_number,
            "page_context": self.page_context,
            "ai_description": self.ai_description,
            "caption": self.caption,
            "metadata": self.metadata
        }


@dataclass
class PageData:
    """单页数据"""
    page_number: int
    raw_text: str
    cleaned_text: Optional[str] = None
    images: List[ImageWithContext] = None
    tables: List[TableWithContext] = None
    
    def __post_init__(self):
        if self.images is None:
            self.images = []
        if self.tables is None:
            self.tables = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "page_number": self.page_number,
            "raw_text": self.raw_text,
            "cleaned_text": self.cleaned_text,
            "images": [img.to_dict() for img in self.images],
            "tables": [table.to_dict() for table in self.tables]
        }


@dataclass
class ProcessingResult:
    """完整的PDF处理结果"""
    source_file: str
    pages: List[PageData]
    summary: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.summary is None:
            self.summary = {
                "total_pages": len(self.pages),
                "total_images": sum(len(page.images) for page in self.pages),
                "total_tables": sum(len(page.tables) for page in self.pages),
                "processing_time": 0
            }
    
    def get_all_images(self) -> List[ImageWithContext]:
        """获取所有图片"""
        all_images = []
        for page in self.pages:
            all_images.extend(page.images)
        return all_images
    
    def get_all_tables(self) -> List[TableWithContext]:
        """获取所有表格"""
        all_tables = []
        for page in self.pages:
            all_tables.extend(page.tables)
        return all_tables
    
    def get_page_by_number(self, page_number: int) -> Optional[PageData]:
        """根据页码获取页面数据"""
        for page in self.pages:
            if page.page_number == page_number:
                return page
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，便于序列化"""
        return {
            "source_file": self.source_file,
            "pages": [
                {
                    "page_number": page.page_number,
                    "raw_text": page.raw_text,
                    "cleaned_text": page.cleaned_text,
                    "images": [
                        {
                            "image_path": img.image_path,
                            "page_number": img.page_number,
                            "page_context": img.page_context,
                            "ai_description": img.ai_description,
                            "caption": img.caption,
                            "metadata": img.metadata
                        }
                        for img in page.images
                    ],
                    "tables": [
                        {
                            "table_path": table.table_path,
                            "page_number": table.page_number,
                            "page_context": table.page_context,
                            "ai_description": table.ai_description,
                            "caption": table.caption,
                            "metadata": table.metadata
                        }
                        for table in page.tables
                    ]
                }
                for page in self.pages
            ],
            "summary": self.summary
        }


@dataclass 
class AdvancedProcessingResult:
    """高级处理结果，包含结构化索引"""
    basic_result: ProcessingResult
    document_structure: Any  # DocumentStructure
    index_structure: Any  # IndexStructure
    processing_metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "basic_result": self.basic_result.to_dict(),
            "document_structure": self.document_structure.__dict__ if hasattr(self.document_structure, '__dict__') else {},
            "index_structure": {
                "minimal_chunks_count": len(self.index_structure.minimal_chunks) if self.index_structure else 0,
                "chapter_summaries_count": len(self.index_structure.chapter_summaries) if self.index_structure else 0,
                "hypothetical_questions_count": len(self.index_structure.hypothetical_questions) if self.index_structure else 0
            },
            "processing_metadata": self.processing_metadata
        } 


@dataclass
class ChapterContent:
    """第一级章节内容"""
    chapter_id: str
    title: str
    content: str
    start_pos: int
    end_pos: int
    word_count: int
    has_images: bool
    has_tables: bool


@dataclass
class MinimalChunk:
    """最小颗粒度分块"""
    chunk_id: str
    content: str
    chunk_type: str  # title, paragraph, list_item, image_desc, table_desc
    belongs_to_chapter: str
    chapter_title: str
    start_pos: int
    end_pos: int
    word_count: int 