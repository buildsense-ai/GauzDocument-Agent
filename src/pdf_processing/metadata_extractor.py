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
                                   image_metadata: List[ImageChunkMetadata],
                                   table_metadata: List[TableChunkMetadata]) -> Dict[str, Any]:
        """
        从chunking结果中提取metadata并精确分配章节
        
        Args:
            chunking_result: 文本分块结果
            image_metadata: 图片元数据列表  
            table_metadata: 表格元数据列表
            
        Returns:
            Dict: 提取的元数据
        """
        # 精确分配图片和表格的章节ID
        self._assign_precise_chapter_ids_from_chunks(
            image_metadata, table_metadata, chunking_result
        )
        
        # 生成chunk级别的metadata
        text_chunk_metadata = self._extract_text_chunk_metadata(
            chunking_result, image_metadata[0].document_id if image_metadata else "unknown"
        )
        
        return {
            "text_chunks": text_chunk_metadata,
            "image_metadata": image_metadata,
            "table_metadata": table_metadata,
            "chunking_result": chunking_result
        }

    def _assign_precise_chapter_ids_from_chunks(self, 
                                              image_metadata: List[ImageChunkMetadata],
                                              table_metadata: List[TableChunkMetadata],
                                              chunking_result: ChunkingResult) -> None:
        """
        基于chunking结果精确分配图片和表格的章节ID
        
        这个方法通过解析full_text中的图片/表格引用来确定它们所属的章节
        """
        # 构建路径到metadata的映射
        image_path_to_metadata = {img.image_path: img for img in image_metadata}
        table_path_to_metadata = {tbl.table_path: tbl for tbl in table_metadata}
        
        # 遍历所有章节，查找图片和表格引用
        for chapter in chunking_result.first_level_chapters:
            chapter_content = chapter.content
            chapter_id = chapter.chapter_id
            
            # 查找图片引用：[图片|ID:xxx|PATH:xxx: 描述]
            import re
            image_pattern = r'\[图片\|ID:(\d+)\|PATH:([^:]+):'
            image_matches = re.findall(image_pattern, chapter_content)
            
            for img_id, img_path in image_matches:
                # 寻找匹配的图片metadata
                matching_image = None
                for img in image_metadata:
                    if img.image_path == img_path or img.image_path.endswith(img_path):
                        matching_image = img
                        break
                
                if matching_image:
                    matching_image.chapter_id = str(chapter_id)
                    print(f"📍 分配图片 {img_id} ({os.path.basename(img_path)}) 到章节 {chapter_id}")
            
            # 查找表格引用：[表格|ID:xxx|PATH:xxx: 描述]
            table_pattern = r'\[表格\|ID:(\d+)\|PATH:([^:]+):'
            table_matches = re.findall(table_pattern, chapter_content)
            
            for tbl_id, tbl_path in table_matches:
                # 寻找匹配的表格metadata
                matching_table = None
                for tbl in table_metadata:
                    if tbl.table_path == tbl_path or tbl.table_path.endswith(tbl_path):
                        matching_table = tbl
                        break
                
                if matching_table:
                    matching_table.chapter_id = str(chapter_id)
                    print(f"📍 分配表格 {tbl_id} ({os.path.basename(tbl_path)}) 到章节 {chapter_id}")
        
        # 为未分配章节的图片/表格分配默认章节
        unassigned_images = [img for img in image_metadata if not img.chapter_id]
        unassigned_tables = [tbl for tbl in table_metadata if not tbl.chapter_id]
        
        if unassigned_images:
            print(f"⚠️ {len(unassigned_images)} 个图片未找到章节归属，分配到默认章节")
            for img in unassigned_images:
                img.chapter_id = "1"  # 默认分配到第一章
        
        if unassigned_tables:
            print(f"⚠️ {len(unassigned_tables)} 个表格未找到章节归属，分配到默认章节")
            for tbl in unassigned_tables:
                tbl.chapter_id = "1"  # 默认分配到第一章

    def _extract_text_chunk_metadata(self, chunking_result: ChunkingResult, 
                                   document_id: str) -> List[TextChunkMetadata]:
        """从chunking结果提取文本chunk metadata"""
        text_chunk_metadata = []
        
        for chunk in chunking_result.minimal_chunks:
            # 使用chunk自身的章节归属信息
            chapter_id = chunk.belongs_to_chapter
            
            text_chunk = TextChunkMetadata(
                content_id=create_content_id(document_id, "text_chunk", len(text_chunk_metadata) + 1),
                document_id=document_id,
                chapter_id=str(chapter_id),
                chunk_type=chunk.chunk_type,
                word_count=chunk.word_count,
                position_in_chapter=chunk.start_pos,  # 使用start_pos作为位置
                paragraph_index=0,  # MinimalChunk没有这个字段，设为默认值
                is_first_paragraph=False,  # MinimalChunk没有这个字段，设为默认值
                is_last_paragraph=False,   # MinimalChunk没有这个字段，设为默认值
                preceding_chunk_id=None,  # 可以后续优化
                following_chunk_id=None,  # 可以后续优化
                created_at=datetime.now()
            )
            text_chunk_metadata.append(text_chunk)
        
        return text_chunk_metadata

    def _find_chunk_chapter(self, chunk, chapters) -> str:
        """找到chunk所属的章节"""
        # 通过chunk的内容在章节中的位置来确定归属
        chunk_content = chunk.content[:100]  # 取前100字符用于匹配
        
        for chapter in chapters:
            if chunk_content in chapter.content:
                return chapter.chapter_id
        
        return "1"  # 默认返回第一章
    
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
                # 修复字段名匹配问题
                metadata = image.get("metadata", {})
                image_chunk = ImageChunkMetadata(
                    content_id=create_content_id(document_id, "image_chunk", len(image_metadata) + 1),
                    document_id=document_id,
                    chapter_id=None,  # 需要根据页面位置确定章节
                    image_path=image.get("image_path", ""),  # 修复：使用正确字段名
                    page_number=image.get("page_number", page_num),  # 使用图片自带的页码
                    caption=image.get("caption", f"图片 {img_idx + 1}"),
                    width=metadata.get("width", 0),  # 修复：从metadata中获取
                    height=metadata.get("height", 0),  # 修复：从metadata中获取
                    size=metadata.get("size", 0),  # 修复：从metadata中获取
                    aspect_ratio=metadata.get("aspect_ratio", 0.0),  # 修复：从metadata中获取
                    ai_description=image.get("ai_description", ""),
                    page_context=image.get("page_context", page_data.get("cleaned_text", page_data.get("raw_text", ""))),
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
                # 修复字段名匹配问题
                metadata = table.get("metadata", {})
                table_chunk = TableChunkMetadata(
                    content_id=create_content_id(document_id, "table_chunk", len(table_metadata) + 1),
                    document_id=document_id,
                    chapter_id=None,  # 需要根据页面位置确定章节
                    table_path=table.get("table_path", ""),  # 修复：使用正确字段名
                    page_number=table.get("page_number", page_num),  # 使用表格自带的页码
                    caption=table.get("caption", f"表格 {tbl_idx + 1}"),
                    width=metadata.get("width", 0),  # 修复：从metadata中获取
                    height=metadata.get("height", 0),  # 修复：从metadata中获取
                    size=metadata.get("size", 0),  # 修复：从metadata中获取
                    aspect_ratio=metadata.get("aspect_ratio", 0.0),  # 修复：从metadata中获取
                    ai_description=table.get("ai_description", ""),
                    page_context=table.get("page_context", page_data.get("cleaned_text", page_data.get("raw_text", ""))),
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
        # 改进的章节分配策略
        chapter_page_ranges = self._build_chapter_page_ranges(chapter_mapping, page_split_data)
        
        # 为图片分配章节
        for image in image_metadata:
            chapter_id = self._find_chapter_for_page(image.page_number, chapter_page_ranges)
            image.chapter_id = chapter_id
            
        # 为表格分配章节
        for table in table_metadata:
            chapter_id = self._find_chapter_for_page(table.page_number, chapter_page_ranges)
            table.chapter_id = chapter_id

    def _build_chapter_page_ranges(self, chapter_mapping: Dict[str, Any], 
                                  page_split_data: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
        """
        构建章节页面范围映射
        
        Returns:
            Dict[chapter_id, {"start_page": int, "end_page": int}]
        """
        total_pages = len(page_split_data.get("pages", []))
        
        # 如果没有章节信息，返回单一章节覆盖所有页面
        if not chapter_mapping:
            return {"1": {"start_page": 1, "end_page": total_pages}}
        
        # 方法1：如果有TOC信息，尝试从中提取页面范围
        if isinstance(chapter_mapping, dict) and "chapters" in chapter_mapping:
            chapters = chapter_mapping["chapters"]
            chapter_ranges = {}
            
            # 假设章节按顺序排列，计算每个章节的页面范围
            chapter_list = sorted(chapters.items(), key=lambda x: int(x[0]))
            pages_per_chapter = total_pages // len(chapter_list) if chapter_list else total_pages
            
            for i, (chapter_id, chapter_info) in enumerate(chapter_list):
                start_page = i * pages_per_chapter + 1
                end_page = min((i + 1) * pages_per_chapter, total_pages)
                
                # 最后一章包含所有剩余页面
                if i == len(chapter_list) - 1:
                    end_page = total_pages
                    
                chapter_ranges[str(chapter_id)] = {
                    "start_page": start_page,
                    "end_page": end_page
                }
            
            return chapter_ranges
        
        # 方法2：基于页面内容智能分析（如果有文本内容）
        chapter_ranges = self._analyze_content_based_chapters(page_split_data)
        if chapter_ranges:
            return chapter_ranges
        
        # 方法3：回退到简单的均分策略
        chapter_count = len(chapter_mapping) if isinstance(chapter_mapping, dict) else 6  # 默认6章
        pages_per_chapter = max(1, total_pages // chapter_count)
        
        chapter_ranges = {}
        for i in range(chapter_count):
            chapter_id = str(i + 1)
            start_page = i * pages_per_chapter + 1
            end_page = min((i + 1) * pages_per_chapter, total_pages)
            
            # 最后一章包含所有剩余页面
            if i == chapter_count - 1:
                end_page = total_pages
                
            chapter_ranges[chapter_id] = {
                "start_page": start_page,
                "end_page": end_page
            }
        
        return chapter_ranges

    def _analyze_content_based_chapters(self, page_split_data: Dict[str, Any]) -> Optional[Dict[str, Dict[str, int]]]:
        """
        基于页面内容分析章节分布
        
        通过识别章节标题等关键词来确定章节边界
        """
        import re
        
        pages = page_split_data.get("pages", [])
        chapter_pages = []
        
        # 定义章节标题的正则模式
        chapter_patterns = [
            r'^第[一二三四五六七八九十\d]+章',  # 第X章
            r'^章节[一二三四五六七八九十\d]+',  # 章节X
            r'^[一二三四五六七八九十\d]+[、\.．]',  # 数字编号
            r'^\d+\.',  # 阿拉伯数字编号
            r'^[IVX]+\.',  # 罗马数字编号
        ]
        
        for page_idx, page_data in enumerate(pages):
            page_text = page_data.get("cleaned_text") or page_data.get("raw_text", "")
            lines = page_text.split('\n')
            
            for line in lines[:5]:  # 只检查前5行
                line = line.strip()
                if not line:
                    continue
                    
                # 检查是否匹配章节标题模式
                for pattern in chapter_patterns:
                    if re.match(pattern, line):
                        chapter_pages.append({
                            "page": page_idx + 1,
                            "title": line[:50],  # 保留前50个字符作为标题
                            "chapter_num": len(chapter_pages) + 1
                        })
                        break
                        
                if len(chapter_pages) > 0 and chapter_pages[-1]["page"] == page_idx + 1:
                    break  # 找到章节标题后停止检查当前页面
        
        # 如果找到了章节标题，构建页面范围
        if len(chapter_pages) >= 2:  # 至少要有2个章节才有意义
            chapter_ranges = {}
            total_pages = len(pages)
            
            for i, chapter_info in enumerate(chapter_pages):
                chapter_id = str(chapter_info["chapter_num"])
                start_page = chapter_info["page"]
                
                # 结束页面是下一个章节的前一页，或者是最后一页
                if i + 1 < len(chapter_pages):
                    end_page = chapter_pages[i + 1]["page"] - 1
                else:
                    end_page = total_pages
                
                chapter_ranges[chapter_id] = {
                    "start_page": start_page,
                    "end_page": end_page
                }
            
            return chapter_ranges
        
        return None

    def _find_chapter_for_page(self, page_number: int, 
                              chapter_ranges: Dict[str, Dict[str, int]]) -> Optional[str]:
        """
        根据页码查找对应的章节ID
        """
        for chapter_id, page_range in chapter_ranges.items():
            if page_range["start_page"] <= page_number <= page_range["end_page"]:
                return chapter_id
        
        # 如果没有找到匹配的章节，返回第一个章节
        if chapter_ranges:
            return list(chapter_ranges.keys())[0]
        
        return "1"  # 默认章节
    
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