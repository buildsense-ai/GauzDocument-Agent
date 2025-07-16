#!/usr/bin/env python3
"""
Final Metadata Schema - V2版本

定义渐进式填充的最终元数据结构
支持阶段性更新、中断恢复、进度跟踪
"""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass
class ProcessingStatus:
    """处理状态信息"""
    current_stage: str
    completion_percentage: int
    last_updated: datetime
    stage_start_time: Optional[datetime] = None
    stage_duration: Optional[float] = None  # 秒
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_stage": self.current_stage,
            "completion_percentage": self.completion_percentage,
            "last_updated": self.last_updated.isoformat(),
            "stage_start_time": self.stage_start_time.isoformat() if self.stage_start_time else None,
            "stage_duration": self.stage_duration,
            "error_message": self.error_message
        }


@dataclass 
class DocumentSummaryChunk:
    """文档摘要chunk - 包含完整文档文本和AI摘要"""
    content_id: str
    document_id: str
    content: str  # full_raw_text，用于后续处理和恢复
    content_type: str = "document_summary"
    content_level: str = "document"
    
    # AI增强信息
    ai_summary: Optional[str] = None  # AI生成的文档摘要
    
    # 文档基础信息
    source_file_path: str = ""
    file_name: str = ""
    file_size: int = 0
    
    # 页面文本信息 - V2新增
    page_texts: Optional[Dict[str, str]] = None  # 页码 -> 完整页面原始文本，用于精确的上下文提取
    
    # 统计信息
    total_pages: int = 0
    total_word_count: Optional[int] = None
    chapter_count: Optional[int] = None
    image_count: int = 0
    table_count: int = 0
    
    # 处理信息
    processing_time: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ImageChunk:
    """图片chunk"""
    content_id: str
    document_id: str
    content_type: str = "image_chunk"
    content_level: str = "chunk"
    
    # 核心内容
    content: Optional[str] = None  # AI生成的图片描述
    
    # 文件信息
    image_path: str = ""
    page_number: int = 0
    caption: str = ""
    
    # 位置信息
    chapter_id: Optional[str] = None
    page_context: str = ""
    
    # 尺寸信息
    width: int = 0
    height: int = 0
    size: int = 0
    aspect_ratio: float = 0.0
    
    # AI增强信息
    ai_description: Optional[str] = None
    
    # 处理信息
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TableChunk:
    """表格chunk"""
    content_id: str
    document_id: str
    content_type: str = "table_chunk"
    content_level: str = "chunk"
    
    # 核心内容
    content: Optional[str] = None  # AI生成的表格描述
    
    # 文件信息
    table_path: str = ""
    page_number: int = 0
    caption: str = ""
    
    # 位置信息
    chapter_id: Optional[str] = None
    page_context: str = ""
    
    # 尺寸信息
    width: int = 0
    height: int = 0
    size: int = 0
    aspect_ratio: float = 0.0
    
    # AI增强信息
    ai_description: Optional[str] = None
    
    # 处理信息
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TextChunk:
    """文本chunk"""
    content_id: str
    document_id: str
    content: str = ""
    content_type: str = "text_chunk"
    content_level: str = "chunk"
    
    # 位置信息
    chapter_id: str = ""
    chunk_type: str = ""  # paragraph, list_item, title, etc.
    position_in_chapter: int = 0
    
    # 统计信息
    word_count: int = 0
    
    # 上下文信息
    preceding_chunk_id: Optional[str] = None
    following_chunk_id: Optional[str] = None
    
    # 处理信息
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ChapterSummaryChunk:
    """章节摘要chunk"""
    content_id: str
    document_id: str
    content: str = ""  # AI生成的章节摘要
    content_type: str = "chapter_summary"
    content_level: str = "chapter"
    
    # 章节信息
    chapter_id: str = ""
    chapter_title: str = ""
    chapter_order: int = 0
    
    # 统计信息
    word_count: int = 0
    paragraph_count: int = 0
    text_chunk_count: int = 0
    image_count: int = 0
    table_count: int = 0
    
    # 处理信息
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class DerivedQuestionChunk:
    """衍生问题chunk"""
    content_id: str
    document_id: str
    content: str = ""  # 问题内容
    content_type: str = "derived_question"
    content_level: str = "question"
    
    # 生成信息
    chapter_id: str = ""
    question_category: str = ""
    generated_from_chunk_id: str = ""
    
    # 处理信息
    created_at: datetime = field(default_factory=datetime.now)


class FinalMetadataSchema:
    """
    Final Metadata Schema管理类
    
    支持渐进式填充、阶段性保存、中断恢复
    """
    
    def __init__(self, document_id: Optional[str] = None):
        """
        初始化Final Schema
        
        Args:
            document_id: 文档ID，如果为None则自动生成
        """
        self.document_id = document_id or self._generate_document_id()
        
        # 初始化空的schema结构
        self.document_summary: Optional[DocumentSummaryChunk] = None
        self.image_chunks: List[ImageChunk] = []
        self.table_chunks: List[TableChunk] = []
        self.text_chunks: List[TextChunk] = []
        self.chapter_summaries: List[ChapterSummaryChunk] = []
        self.derived_questions: List[DerivedQuestionChunk] = []
        
        # 处理状态
        self.processing_status = ProcessingStatus(
            current_stage="initialized",
            completion_percentage=0,
            last_updated=datetime.now()
        )
    
    def _generate_document_id(self) -> str:
        """生成文档ID"""
        return f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "document_id": self.document_id,
            "document_summary": asdict(self.document_summary) if self.document_summary else None,
            "image_chunks": [asdict(chunk) for chunk in self.image_chunks],
            "table_chunks": [asdict(chunk) for chunk in self.table_chunks],
            "text_chunks": [asdict(chunk) for chunk in self.text_chunks],
            "chapter_summaries": [asdict(chunk) for chunk in self.chapter_summaries],
            "derived_questions": [asdict(chunk) for chunk in self.derived_questions],
            "processing_status": self.processing_status.to_dict(),
            "schema_version": "2.0.0",
            "last_updated": datetime.now().isoformat()
        }
    
    def save(self, file_path: str):
        """保存schema到文件"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2, default=str)
    
    @classmethod
    def load(cls, file_path: str) -> 'FinalMetadataSchema':
        """从文件加载schema"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 创建实例
        schema = cls(document_id=data["document_id"])
        
        # 恢复processing_status
        status_data = data["processing_status"]
        schema.processing_status = ProcessingStatus(
            current_stage=status_data["current_stage"],
            completion_percentage=status_data["completion_percentage"],
            last_updated=datetime.fromisoformat(status_data["last_updated"]),
            stage_start_time=datetime.fromisoformat(status_data["stage_start_time"]) if status_data.get("stage_start_time") else None,
            stage_duration=status_data.get("stage_duration"),
            error_message=status_data.get("error_message")
        )
        
        # 恢复document_summary
        if data["document_summary"]:
            ds_data = data["document_summary"]
            schema.document_summary = DocumentSummaryChunk(
                content_id=ds_data["content_id"],
                document_id=ds_data["document_id"],
                content=ds_data["content"],
                ai_summary=ds_data.get("ai_summary"),
                source_file_path=ds_data.get("source_file_path", ""),
                file_name=ds_data.get("file_name", ""),
                file_size=ds_data.get("file_size", 0),
                total_pages=ds_data.get("total_pages", 0),
                total_word_count=ds_data.get("total_word_count"),
                chapter_count=ds_data.get("chapter_count"),
                image_count=ds_data.get("image_count", 0),
                table_count=ds_data.get("table_count", 0),
                processing_time=ds_data.get("processing_time"),
                created_at=datetime.fromisoformat(ds_data["created_at"])
            )
        
        # 恢复image_chunks
        for img_data in data.get("image_chunks", []):
            image_chunk = ImageChunk(
                content_id=img_data["content_id"],
                document_id=img_data["document_id"],
                image_path=img_data["image_path"],
                page_number=img_data["page_number"],
                caption=img_data.get("caption", ""),
                chapter_id=img_data.get("chapter_id"),
                page_context=img_data.get("page_context", ""),
                width=img_data.get("width", 0),
                height=img_data.get("height", 0),
                size=img_data.get("size", 0),
                aspect_ratio=img_data.get("aspect_ratio", 0.0),
                ai_description=img_data.get("ai_description"),
                created_at=datetime.fromisoformat(img_data["created_at"])
            )
            schema.image_chunks.append(image_chunk)
        
        # 恢复table_chunks
        for table_data in data.get("table_chunks", []):
            table_chunk = TableChunk(
                content_id=table_data["content_id"],
                document_id=table_data["document_id"],
                table_path=table_data["table_path"],
                page_number=table_data["page_number"],
                caption=table_data.get("caption", ""),
                chapter_id=table_data.get("chapter_id"),
                page_context=table_data.get("page_context", ""),
                width=table_data.get("width", 0),
                height=table_data.get("height", 0),
                size=table_data.get("size", 0),
                aspect_ratio=table_data.get("aspect_ratio", 0.0),
                ai_description=table_data.get("ai_description"),
                created_at=datetime.fromisoformat(table_data["created_at"])
            )
            schema.table_chunks.append(table_chunk)
        
        # 恢复text_chunks
        for text_data in data.get("text_chunks", []):
            text_chunk = TextChunk(
                content_id=text_data["content_id"],
                document_id=text_data["document_id"],
                content=text_data["content"],
                chapter_id=text_data.get("chapter_id", ""),
                chunk_type=text_data.get("chunk_type", ""),
                position_in_chapter=text_data.get("position_in_chapter", 0),
                word_count=text_data.get("word_count", 0),
                preceding_chunk_id=text_data.get("preceding_chunk_id"),
                following_chunk_id=text_data.get("following_chunk_id"),
                created_at=datetime.fromisoformat(text_data["created_at"])
            )
            schema.text_chunks.append(text_chunk)
        
        # 恢复chapter_summaries
        for chapter_data in data.get("chapter_summaries", []):
            chapter_chunk = ChapterSummaryChunk(
                content_id=chapter_data["content_id"],
                document_id=chapter_data["document_id"],
                content=chapter_data["content"],
                chapter_id=chapter_data.get("chapter_id", ""),
                chapter_title=chapter_data.get("chapter_title", ""),
                chapter_order=chapter_data.get("chapter_order", 0),
                word_count=chapter_data.get("word_count", 0),
                paragraph_count=chapter_data.get("paragraph_count", 0),
                text_chunk_count=chapter_data.get("text_chunk_count", 0),
                image_count=chapter_data.get("image_count", 0),
                table_count=chapter_data.get("table_count", 0),
                created_at=datetime.fromisoformat(chapter_data["created_at"])
            )
            schema.chapter_summaries.append(chapter_chunk)
        
        # 恢复derived_questions
        for question_data in data.get("derived_questions", []):
            question_chunk = DerivedQuestionChunk(
                content_id=question_data["content_id"],
                document_id=question_data["document_id"],
                content=question_data["content"],
                chapter_id=question_data.get("chapter_id", ""),
                question_category=question_data.get("question_category", ""),
                generated_from_chunk_id=question_data.get("generated_from_chunk_id", ""),
                created_at=datetime.fromisoformat(question_data["created_at"])
            )
            schema.derived_questions.append(question_chunk)
        
        return schema
    
    def update_processing_status(self, stage: str, completion: int, 
                               error_message: Optional[str] = None):
        """更新处理状态"""
        self.processing_status.current_stage = stage
        self.processing_status.completion_percentage = completion
        self.processing_status.last_updated = datetime.now()
        if error_message:
            self.processing_status.error_message = error_message
    
    def get_completion_percentage(self) -> int:
        """计算实际完成百分比"""
        total_fields = 0
        completed_fields = 0
        
        # 检查document_summary
        if self.document_summary:
            total_fields += 2  # content和ai_summary
            completed_fields += 1  # content总是有的
            if self.document_summary.ai_summary:
                completed_fields += 1
        
        # 检查image_chunks的AI描述
        for img in self.image_chunks:
            total_fields += 1
            if img.ai_description:
                completed_fields += 1
        
        # 检查table_chunks的AI描述
        for table in self.table_chunks:
            total_fields += 1
            if table.ai_description:
                completed_fields += 1
        
        # 检查其他chunks
        total_fields += 3  # text_chunks, chapter_summaries, derived_questions
        if self.text_chunks:
            completed_fields += 1
        if self.chapter_summaries:
            completed_fields += 1
        if self.derived_questions:
            completed_fields += 1
        
        return int(completed_fields / total_fields * 100) if total_fields > 0 else 0
    
    def is_stage_complete(self, stage: str) -> bool:
        """检查指定阶段是否完成"""
        if stage == "stage1":
            return (self.document_summary is not None and 
                   bool(self.document_summary.content) and
                   (len(self.image_chunks) > 0 or len(self.table_chunks) > 0))
        elif stage == "stage2":
            ai_descriptions_complete = all(bool(img.ai_description) for img in self.image_chunks)
            ai_descriptions_complete &= all(bool(table.ai_description) for table in self.table_chunks)
            return (ai_descriptions_complete and 
                   self.document_summary is not None and 
                   self.document_summary.ai_summary is not None)
        # 其他阶段的检查逻辑...
        return False
    
    def can_resume_from_stage(self, stage: str) -> bool:
        """检查是否可以从指定阶段恢复"""
        if stage == "stage2":
            return self.is_stage_complete("stage1")
        elif stage == "stage3":
            return self.is_stage_complete("stage2")
        # 其他阶段的检查逻辑...
        return True 