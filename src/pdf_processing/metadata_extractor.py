#!/usr/bin/env python3
"""
Metadata提取器
将现有的处理结果转换为标准化的metadata结构
"""

import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from .metadata_schema import (
    DocumentSummaryMetadata, ChapterSummaryMetadata, 
    TextChunkMetadata, ImageChunkMetadata, TableChunkMetadata,
    DocumentType, DocumentTOC, DocumentScope, ContentType,
    create_content_id, UNIVERSAL_METADATA_FIELDS
)
from .text_chunker import ChunkingResult


class MetadataExtractor:
    """从现有数据结构提取标准化metadata"""
    
    def __init__(self, project_name: str = "default_project"):
        """
        初始化metadata提取器
        
        Args:
            project_name: 项目名称
        """
        self.project_name = project_name
        self.document_scope = DocumentScope.PROJECT
        
    def extract_from_page_split_result(self, page_split_file: str) -> Dict[str, Any]:
        """
        从page_split结果提取基础metadata
        
        Args:
            page_split_file: page_split结果文件路径
            
        Returns:
            Dict包含提取的基础信息
        """
        if not os.path.exists(page_split_file):
            raise FileNotFoundError(f"Page split结果文件不存在: {page_split_file}")
            
        with open(page_split_file, 'r', encoding='utf-8') as f:
            page_split_data = json.load(f)
            
        # 提取文档基础信息
        document_info = {
            "document_id": self._generate_document_id(page_split_data.get("source_file", "unknown")),
            "source_file_path": page_split_data.get("source_file", ""),
            "file_name": Path(page_split_data.get("source_file", "")).name,
            "total_pages": len(page_split_data.get("pages", [])),
            "processing_time": page_split_data.get("processing_time", 0.0),
            "created_at": datetime.now()
        }
        
        # 提取图片metadata
        image_metadata = self._extract_image_metadata(page_split_data, document_info["document_id"])
        
        # 提取表格metadata
        table_metadata = self._extract_table_metadata(page_split_data, document_info["document_id"])
        
        return {
            "document_info": document_info,
            "image_metadata": image_metadata,
            "table_metadata": table_metadata,
            "page_split_data": page_split_data
        }
    
    def extract_from_toc_result(self, toc_file: str, document_id: str) -> Tuple[DocumentTOC, Dict[str, Any]]:
        """
        从TOC结果提取TOC metadata
        
        Args:
            toc_file: TOC结果文件路径
            document_id: 文档ID
            
        Returns:
            Tuple[DocumentTOC, Dict[str, Any]]: TOC元数据和章节映射
        """
        if not os.path.exists(toc_file):
            raise FileNotFoundError(f"TOC结果文件不存在: {toc_file}")
            
        with open(toc_file, 'r', encoding='utf-8') as f:
            toc_data = json.load(f)
            
        # 创建DocumentTOC
        toc_items = toc_data.get("toc_items", [])
        doc_toc = DocumentTOC(
            document_id=document_id,
            toc_json=json.dumps(toc_items, ensure_ascii=False),
            chapter_count=len([item for item in toc_items if item.get("level") == 1]),
            total_sections=len(toc_items),
            created_at=datetime.now()
        )
        
        # 创建章节映射（ID -> 标题）
        chapter_mapping = {}
        for item in toc_items:
            if item.get("level") == 1:  # 只处理第一级章节
                chapter_mapping[item["id"]] = {
                    "title": item["title"],
                    "order": int(item["id"]) if item["id"].isdigit() else 0
                }
        
        return doc_toc, chapter_mapping
    
    def extract_from_chunking_result(self, chunking_result: ChunkingResult, 
                                   document_id: str, chapter_mapping: Dict[str, Any]) -> List[TextChunkMetadata]:
        """
        从分块结果提取文本chunk metadata
        
        Args:
            chunking_result: 分块结果
            document_id: 文档ID
            chapter_mapping: 章节映射
            
        Returns:
            List[TextChunkMetadata]: 文本chunk元数据列表
        """
        text_chunks = []
        
        for chunk in chunking_result.minimal_chunks:
            # 获取章节信息
            chapter_info = chapter_mapping.get(chunk.belongs_to_chapter, {})
            
            # 创建TextChunkMetadata
            text_chunk = TextChunkMetadata(
                content_id=create_content_id(document_id, "text_chunk", len(text_chunks) + 1),
                document_id=document_id,
                chapter_id=chunk.belongs_to_chapter,
                chunk_type=chunk.chunk_type,
                word_count=chunk.word_count,
                position_in_chapter=chunk.start_pos,
                paragraph_index=0,  # 需要从ai_chunker中获取更详细信息
                is_first_paragraph=False,  # 需要从ai_chunker中获取更详细信息
                is_last_paragraph=False,   # 需要从ai_chunker中获取更详细信息
                preceding_chunk_id=None,   # 需要建立链接关系
                following_chunk_id=None,   # 需要建立链接关系
                created_at=datetime.now()
            )
            
            text_chunks.append(text_chunk)
            
        # 建立前后链接关系
        for i, chunk in enumerate(text_chunks):
            if i > 0:
                chunk.preceding_chunk_id = text_chunks[i-1].content_id
            if i < len(text_chunks) - 1:
                chunk.following_chunk_id = text_chunks[i+1].content_id
                
        return text_chunks
    
    def create_universal_metadata(self, content_id: str, document_id: str, 
                                content_type: str, content_level: str,
                                chapter_id: Optional[str] = None,
                                document_title: str = "",
                                chapter_title: str = "") -> Dict[str, Any]:
        """
        创建通用metadata字段
        
        Args:
            content_id: 内容ID
            document_id: 文档ID
            content_type: 内容类型
            content_level: 内容层级
            chapter_id: 章节ID
            document_title: 文档标题
            chapter_title: 章节标题
            
        Returns:
            Dict包含通用metadata字段
        """
        return {
            "content_id": content_id,
            "document_id": document_id,
            "content_type": content_type,
            "content_level": content_level,
            "chapter_id": chapter_id or "",
            "document_title": document_title,
            "chapter_title": chapter_title,
            "document_scope": self.document_scope.value,
            "project_name": self.project_name,
            "created_at": datetime.now()
        }
    
    def _extract_image_metadata(self, page_split_data: Dict[str, Any], document_id: str) -> List[ImageChunkMetadata]:
        """提取图片metadata"""
        image_metadata = []
        
        for page_num, page_data in enumerate(page_split_data.get("pages", []), 1):
            images = page_data.get("images", [])
            
            for img_idx, image in enumerate(images):
                image_chunk = ImageChunkMetadata(
                    content_id=create_content_id(document_id, "image_chunk", len(image_metadata) + 1),
                    document_id=document_id,
                    chapter_id=None,  # 需要根据页面位置确定章节
                    image_path=image.get("path", ""),
                    page_number=page_num,
                    caption=image.get("caption", f"图片 {img_idx + 1}"),
                    width=image.get("width", 0),
                    height=image.get("height", 0),
                    size=image.get("size", 0),
                    aspect_ratio=image.get("aspect_ratio", 0.0),
                    ai_description=image.get("ai_description", ""),
                    page_context=page_data.get("text", ""),
                    created_at=datetime.now()
                )
                image_metadata.append(image_chunk)
                
        return image_metadata
    
    def _extract_table_metadata(self, page_split_data: Dict[str, Any], document_id: str) -> List[TableChunkMetadata]:
        """提取表格metadata"""
        table_metadata = []
        
        for page_num, page_data in enumerate(page_split_data.get("pages", []), 1):
            tables = page_data.get("tables", [])
            
            for tbl_idx, table in enumerate(tables):
                table_chunk = TableChunkMetadata(
                    content_id=create_content_id(document_id, "table_chunk", len(table_metadata) + 1),
                    document_id=document_id,
                    chapter_id=None,  # 需要根据页面位置确定章节
                    table_path=table.get("path", ""),
                    page_number=page_num,
                    caption=table.get("caption", f"表格 {tbl_idx + 1}"),
                    width=table.get("width", 0),
                    height=table.get("height", 0),
                    size=table.get("size", 0),
                    aspect_ratio=table.get("aspect_ratio", 0.0),
                    ai_description=table.get("ai_description", ""),
                    page_context=page_data.get("text", ""),
                    created_at=datetime.now()
                )
                table_metadata.append(table_chunk)
                
        return table_metadata
    
    def _generate_document_id(self, source_file: str) -> str:
        """生成文档ID"""
        # 使用文件名的hash作为文档ID的一部分
        file_name = Path(source_file).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"doc_{file_name}_{timestamp}"
    
    def map_chapters_to_content(self, image_metadata: List[ImageChunkMetadata],
                               table_metadata: List[TableChunkMetadata],
                               chapter_mapping: Dict[str, Any],
                               page_split_data: Dict[str, Any]) -> None:
        """
        根据页面位置将图片和表格映射到章节
        
        Args:
            image_metadata: 图片元数据列表
            table_metadata: 表格元数据列表
            chapter_mapping: 章节映射
            page_split_data: 页面分割数据
        """
        # 这里需要实现一个简单的页面到章节的映射逻辑
        # 可以根据页面数量和章节数量进行估算
        total_pages = len(page_split_data.get("pages", []))
        chapter_count = len(chapter_mapping)
        
        if chapter_count > 0:
            pages_per_chapter = total_pages // chapter_count
            
            # 为图片分配章节
            for image in image_metadata:
                estimated_chapter = min((image.page_number - 1) // pages_per_chapter + 1, chapter_count)
                image.chapter_id = str(estimated_chapter)
                
            # 为表格分配章节
            for table in table_metadata:
                estimated_chapter = min((table.page_number - 1) // pages_per_chapter + 1, chapter_count)
                table.chapter_id = str(estimated_chapter)
    
    def save_extracted_metadata(self, output_dir: str, **metadata_collections):
        """
        保存提取的metadata
        
        Args:
            output_dir: 输出目录
            **metadata_collections: 各类metadata集合
        """
        os.makedirs(output_dir, exist_ok=True)
        
        for collection_name, collection_data in metadata_collections.items():
            if collection_data:
                output_file = os.path.join(output_dir, f"{collection_name}_metadata.json")
                
                # 转换为可序列化的格式
                if isinstance(collection_data, list):
                    serializable_data = [self._to_serializable(item) for item in collection_data]
                else:
                    serializable_data = self._to_serializable(collection_data)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(serializable_data, f, ensure_ascii=False, indent=2, default=str)
                    
                print(f"💾 {collection_name} metadata已保存: {output_file}")
    
    def _to_serializable(self, obj) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        if hasattr(obj, '__dict__'):
            result = {}
            for key, value in obj.__dict__.items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                else:
                    result[key] = value
            return result
        return obj 