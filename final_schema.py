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
class DocumentSummary:
    content_id: str
    document_id: str
    content_type: str = "document_summary"
    content_level: str = "document"
    
    # 原始数据字段
    full_raw_text: Optional[str] = None      # 重命名：完整原始文本
    ai_summary: Optional[str] = None         # AI生成的文档摘要
    
    # 文档元信息
    source_file_path: str = ""
    file_name: str = ""
    file_size: int = 0
    
    # 页面文本数据
    page_texts: Optional[Dict[str, str]] = None          # Stage1: 原始页面文本
    cleaned_page_texts: Optional[Dict[str, str]] = None  # Stage2: 清洗后的页面文本
    
    # 文档结构数据 - 新增字段
    toc: Optional[List[Dict[str, Any]]] = None           # Stage2: TOC结构（直接存储）
    metadata: Optional[Dict[str, Any]] = None            # Stage2: 其他文档结构信息
    
    # 文档统计
    total_pages: int = 0
    total_word_count: Optional[int] = None
    chapter_count: Optional[int] = None
    image_count: int = 0
    table_count: int = 0
    
    # 处理信息
    processing_time: float = 0.0
    created_at: Optional[str] = None
    
    # 要被embedding的内容（优先使用ai_summary，如果没有则使用full_raw_text的开头）
    @property
    def content(self) -> str:
        """返回要被embedding的内容"""
        if self.ai_summary:
            return self.ai_summary
        elif self.full_raw_text:
            # 如果没有AI摘要，返回原文前2000字符作为fallback
            return self.full_raw_text[:2000] + "..." if len(self.full_raw_text) > 2000 else self.full_raw_text
        else:
            return ""

@dataclass
class ImageChunk:
    content_id: str
    document_id: str
    content_type: str = "image_chunk"
    content_level: str = "chunk"
    
    # 图片文件信息
    image_path: str = ""
    page_number: int = 0
    caption: str = ""
    chapter_id: Optional[str] = None
    page_context: str = ""
    
    # 图片尺寸信息
    width: int = 0
    height: int = 0
    size: int = 0
    aspect_ratio: float = 0.0
    
    # AI生成的描述信息
    search_summary: Optional[str] = None        # 简述 - 15字以内的搜索关键词
    detailed_description: Optional[str] = None  # 详细描述 - 完整的图片内容描述
    engineering_details: Optional[str] = None   # 工程技术细节（仅技术图纸）
    
    # 处理信息
    created_at: Optional[str] = field(default_factory=lambda: datetime.now().isoformat())
    
    # 要被embedding的内容
    @property 
    def content(self) -> str:
        """返回要被embedding的内容 - 使用search_summary + detailed_description + engineering_details组合"""
        parts = []
        
        # 优先使用三个主要描述字段的组合
        if self.search_summary:
            parts.append(f"概述: {self.search_summary}")
        
        if self.detailed_description:
            parts.append(f"详情: {self.detailed_description}")
            
        if self.engineering_details:
            parts.append(f"技术细节: {self.engineering_details}")
        
        # 如果上述三个字段都为空，才使用page_context作为回退
        if not parts and self.page_context:
            parts.append(f"上下文: {self.page_context}")
            
        return " | ".join(parts) if parts else f"图片: {self.caption or '无标题'}"

@dataclass 
class TableChunk:
    content_id: str
    document_id: str
    content_type: str = "table_chunk"
    content_level: str = "chunk"
    
    # 表格文件信息
    table_path: str = ""
    page_number: int = 0
    caption: str = ""
    chapter_id: Optional[str] = None
    page_context: str = ""
    
    # 表格尺寸信息
    width: int = 0
    height: int = 0
    size: int = 0
    aspect_ratio: float = 0.0
    
    # AI生成的描述信息
    search_summary: Optional[str] = None        # 简述 - 表格类型和关键信息
    detailed_description: Optional[str] = None  # 详细描述 - 表格结构和内容
    engineering_details: Optional[str] = None   # 技术分析 - 数据含义和技术解读
    
    # 处理信息
    created_at: Optional[str] = field(default_factory=lambda: datetime.now().isoformat())
    
    # 要被embedding的内容
    @property
    def content(self) -> str:
        """返回要被embedding的内容 - 使用search_summary + detailed_description + engineering_details组合"""
        parts = []
        
        # 优先使用三个主要描述字段的组合
        if self.search_summary:
            parts.append(f"概述: {self.search_summary}")
        
        if self.detailed_description:
            parts.append(f"详情: {self.detailed_description}")
            
        if self.engineering_details:
            parts.append(f"技术分析: {self.engineering_details}")
        
        # 如果上述三个字段都为空，才使用page_context作为回退
        if not parts and self.page_context:
            parts.append(f"上下文: {self.page_context}")
            
        return " | ".join(parts) if parts else f"表格: {self.caption or '无标题'}"

@dataclass
class TextChunk:
    content_id: str
    document_id: str
    content_type: str = "text_chunk"
    content_level: str = "chunk"
    
    # 要被embedding的内容 - 这是核心字段
    content: str = ""
    
    # 元信息
    chapter_id: Optional[str] = ""
    page_number: Optional[int] = None
    chunk_index: int = 0
    word_count: int = 0
    
    # 处理信息
    created_at: Optional[str] = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class ChapterSummary:
    content_id: str
    document_id: str
    content_type: str = "chapter_summary"
    content_level: str = "chapter"
    
    # 章节信息
    chapter_id: str = ""
    chapter_title: str = ""
    page_range: Optional[str] = None
    
    # 原始和处理后的内容
    raw_content: Optional[str] = None       # 章节原始文本
    ai_summary: Optional[str] = None        # AI生成的章节摘要
    
    # 统计信息
    word_count: int = 0
    
    # 处理信息
    created_at: Optional[str] = field(default_factory=lambda: datetime.now().isoformat())
    
    # 要被embedding的内容
    @property
    def content(self) -> str:
        """返回要被embedding的内容 - 优先使用raw_content"""
        return self.raw_content or self.ai_summary or ""

@dataclass
class DerivedQuestion:
    content_id: str
    document_id: str
    content_type: str = "derived_question"
    content_level: str = "document"
    
    # 要被embedding的内容 - 问题本身
    content: str = ""  # 这就是问题文本
    
    # 问题元信息
    question_type: str = ""
    source_context: Optional[str] = None
    confidence_score: Optional[float] = None
    
    # 处理信息
    created_at: Optional[str] = field(default_factory=lambda: datetime.now().isoformat())


class MultiProjectMetadataSchema:
    """
    多项目元数据管理器
    
    支持在单个metadata文件中管理多个项目，每个项目可以包含多个文档
    格式: {"project_name": "项目名", "project_documents": {"doc1_id": {...}, "doc2_id": {...}}}
    """
    
    def __init__(self, metadata_file_path: str):
        self.metadata_file_path = metadata_file_path
        self.project_name: Optional[str] = None
        self.project_documents: Dict[str, Dict[str, Any]] = {}  # {doc_id: document_data}
        self.schema_version = "2.1.0"
        self.last_updated = datetime.now().isoformat()
        
        # 如果文件存在，加载现有数据
        if os.path.exists(metadata_file_path):
            self._load_existing_data()
    
    def _load_existing_data(self):
        """加载现有的metadata数据"""
        try:
            with open(self.metadata_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查格式并加载数据
            if "project_name" in data and "project_documents" in data:
                # 正确的格式: {"project_name": "项目名", "project_documents": {"doc_id": {...}}}
                self.project_name = data["project_name"]
                self.project_documents = data["project_documents"]
                self.schema_version = data.get("schema_version", "2.1.0")
                self.last_updated = data.get("last_updated", datetime.now().isoformat())
            else:
                # 其他格式，创建新的空结构
                print(f"⚠️ 不支持的数据格式，将创建新的metadata文件")
                self.project_name = None
                self.project_documents = {}
                        
        except Exception as e:
            print(f"⚠️ 加载现有数据失败: {e}，将创建新的metadata文件")
            self.project_name = None
            self.project_documents = {}
    
    def set_project_name(self, project_name: str):
        """设置项目名称"""
        if self.project_name is None:
            self.project_name = project_name
        elif self.project_name != project_name:
            # 项目名不同，需要保存当前数据并切换到新项目
            print(f"⚠️ 项目名从 '{self.project_name}' 变更为 '{project_name}'，将保存当前数据")
            self.save()
            # 重新加载或创建新项目
            self.project_name = project_name
            self.project_documents = {}
            self.last_updated = datetime.now().isoformat()
    
    def add_document(self, document_id: str, document_data: Dict[str, Any]):
        """添加文档到当前项目"""
        if self.project_name is None:
            raise ValueError("项目名称未设置，请先调用set_project_name")
        
        self.project_documents[document_id] = document_data
        self.last_updated = datetime.now().isoformat()
    
    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """获取指定文档的数据"""
        return self.project_documents.get(document_id)
    
    def list_documents(self) -> List[str]:
        """列出当前项目中的所有文档ID"""
        return list(self.project_documents.keys())
    
    def has_project(self, project_name: str) -> bool:
        """检查是否已存在指定项目"""
        return self.project_name == project_name and bool(self.project_documents)
    
    def save(self):
        """保存到文件"""
        if self.project_name is None:
            print("⚠️ 项目名称未设置，无法保存")
            return
            
        os.makedirs(os.path.dirname(self.metadata_file_path), exist_ok=True)
        
        # 转换为可序列化的格式
        data = {
            "project_name": self.project_name,
            "project_documents": self.project_documents,
            "schema_version": self.schema_version,
            "last_updated": self.last_updated
        }
        
        with open(self.metadata_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    def create_single_project_schema(self, project_name: str, document_id: Optional[str] = None) -> 'FinalMetadataSchema':
        """为指定项目创建单项目Schema对象（兼容性接口）"""
        # 设置项目名称
        self.set_project_name(project_name)
        
        return FinalMetadataSchema(
            document_id=document_id,
            project_name=project_name,
            multi_project_manager=self
        )


class FinalMetadataSchema:
    """
    Final Metadata Schema管理类
    
    支持渐进式填充、阶段性保存、中断恢复
    现在支持多项目管理
    """
    
    def __init__(self, document_id: Optional[str] = None, project_name: Optional[str] = None, multi_project_manager: Optional[MultiProjectMetadataSchema] = None):
        """
        初始化Final Schema
        
        Args:
            document_id: 文档ID，如果为None则自动生成
            project_name: 项目名称，用于项目隔离
            multi_project_manager: 多项目管理器，如果提供则使用多项目模式
        """
        self.project_name = project_name or "default_project"
        self.document_id = document_id or self._generate_document_id()
        self.multi_project_manager = multi_project_manager
        
        # 初始化空的schema结构
        self.document_summary: Optional[DocumentSummary] = None
        self.image_chunks: List[ImageChunk] = []
        self.table_chunks: List[TableChunk] = []
        self.text_chunks: List[TextChunk] = []
        self.chapter_summaries: List[ChapterSummary] = []
        self.derived_questions: List[DerivedQuestion] = []
        
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
            "project_name": self.project_name,
            "project_documents": {
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
        }
    
    def save(self, file_path: str):
        """保存schema到文件"""
        # 如果使用多项目管理器，则通过管理器保存
        if self.multi_project_manager:
            # 创建文档数据字典
            document_data = {
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
            
            # 通过多项目管理器保存
            self.multi_project_manager.add_document(self.document_id, document_data)
            self.multi_project_manager.save()
            print(f"✅ 项目 '{self.project_name}' 的数据已保存到: {self.multi_project_manager.metadata_file_path}")
        else:
            # 传统的单项目保存方式
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2, default=str)
    
    @classmethod
    def load(cls, file_path: str) -> 'FinalMetadataSchema':
        """从文件加载schema"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查数据结构：新格式（project_name + project_documents）还是旧格式
        if "project_name" in data and "project_documents" in data:
            # 新格式：project_name作为字段，project_documents包含多个文档
            project_name = data["project_name"]
            project_documents = data["project_documents"]
            
            # 如果有多个文档，取第一个文档作为示例
            if isinstance(project_documents, dict) and project_documents:
                first_doc_id = list(project_documents.keys())[0]
                project_data = project_documents[first_doc_id]
            else:
                raise ValueError("project_documents格式错误或为空")
        elif "project_name" in data:
            # 旧格式：project_name与其他字段平行
            project_name = data["project_name"]
            project_data = data
        else:
            # 更旧格式：所有数据嵌套在project_name下
            project_name = list(data.keys())[0]  # 获取第一个键作为project_name
            project_data = data[project_name]
        
        # 创建实例
        schema = cls(document_id=project_data["document_id"], project_name=project_name)
        
        # 恢复processing_status
        status_data = project_data["processing_status"]
        schema.processing_status = ProcessingStatus(
            current_stage=status_data["current_stage"],
            completion_percentage=status_data["completion_percentage"],
            last_updated=datetime.fromisoformat(status_data["last_updated"]),
            stage_start_time=datetime.fromisoformat(status_data["stage_start_time"]) if status_data.get("stage_start_time") else None,
            stage_duration=status_data.get("stage_duration"),
            error_message=status_data.get("error_message")
        )
        
        # 恢复document_summary
        if project_data["document_summary"]:
            ds_data = project_data["document_summary"]
            schema.document_summary = DocumentSummary(
                content_id=ds_data["content_id"],
                document_id=ds_data["document_id"],
                full_raw_text=ds_data.get("full_raw_text"),
                ai_summary=ds_data.get("ai_summary"),
                source_file_path=ds_data.get("source_file_path", ""),
                file_name=ds_data.get("file_name", ""),
                file_size=ds_data.get("file_size", 0),
                page_texts=ds_data.get("page_texts"),
                cleaned_page_texts=ds_data.get("cleaned_page_texts"),
                toc=ds_data.get("toc"),
                metadata=ds_data.get("metadata"),
                total_pages=ds_data.get("total_pages", 0),
                total_word_count=ds_data.get("total_word_count"),
                chapter_count=ds_data.get("chapter_count"),
                image_count=ds_data.get("image_count", 0),
                table_count=ds_data.get("table_count", 0),
                processing_time=ds_data.get("processing_time", 0.0),
                created_at=ds_data.get("created_at")
            )
        
        # 恢复image_chunks
        for img_data in project_data.get("image_chunks", []):
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
                search_summary=img_data.get("search_summary"),
                detailed_description=img_data.get("detailed_description"),
                engineering_details=img_data.get("engineering_details"),
                created_at=img_data.get("created_at")
            )
            schema.image_chunks.append(image_chunk)
        
        # 恢复table_chunks
        for table_data in project_data.get("table_chunks", []):
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
                search_summary=table_data.get("search_summary"),
                detailed_description=table_data.get("detailed_description"),
                engineering_details=table_data.get("engineering_details"),
                created_at=table_data.get("created_at")
            )
            schema.table_chunks.append(table_chunk)
        
        # 恢复text_chunks
        for text_data in project_data.get("text_chunks", []):
            text_chunk = TextChunk(
                content_id=text_data["content_id"],
                document_id=text_data["document_id"],
                content=text_data["content"],
                chapter_id=text_data.get("chapter_id", ""),
                page_number=text_data.get("page_number"),
                chunk_index=text_data.get("chunk_index", 0),
                word_count=text_data.get("word_count", 0),
                created_at=text_data.get("created_at")
            )
            schema.text_chunks.append(text_chunk)
        
        # 恢复chapter_summaries
        for chapter_data in project_data.get("chapter_summaries", []):
            chapter_chunk = ChapterSummary(
                content_id=chapter_data["content_id"],
                document_id=chapter_data["document_id"],
                raw_content=chapter_data.get("raw_content"),
                ai_summary=chapter_data.get("ai_summary"),
                chapter_id=chapter_data.get("chapter_id", ""),
                chapter_title=chapter_data.get("chapter_title", ""),
                page_range=chapter_data.get("page_range"),
                word_count=chapter_data.get("word_count", 0),
                created_at=chapter_data.get("created_at")
            )
            schema.chapter_summaries.append(chapter_chunk)
        
        # 恢复derived_questions
        for question_data in project_data.get("derived_questions", []):
            question_chunk = DerivedQuestion(
                content_id=question_data["content_id"],
                document_id=question_data["document_id"],
                content=question_data["content"],
                question_type=question_data.get("question_type", ""),
                source_context=question_data.get("source_context"),
                confidence_score=question_data.get("confidence_score"),
                created_at=question_data.get("created_at")
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
            if img.search_summary or img.detailed_description or img.engineering_details:
                completed_fields += 1
        
        # 检查table_chunks的AI描述
        for table in self.table_chunks:
            total_fields += 1
            if table.search_summary or table.detailed_description or table.engineering_details:
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
            ai_descriptions_complete = all(bool(img.search_summary) or bool(img.detailed_description) or bool(img.engineering_details) for img in self.image_chunks)
            ai_descriptions_complete &= all(bool(table.search_summary) or bool(table.detailed_description) or bool(table.engineering_details) for table in self.table_chunks)
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