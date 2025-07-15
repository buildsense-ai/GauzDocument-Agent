"""
PDF Processing 元数据表结构定义
支持所有类型的embedding内容的统一元数据结构
"""

from dataclasses import dataclass
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum

class DocumentScope(Enum):
    """文档范围枚举"""
    PROJECT = "project"      # 项目级材料
    GENERAL = "general"      # 通用材料（法规、行业最佳实践等）

class ContentType(Enum):
    """内容类型枚举"""
    DOCUMENT_SUMMARY = "document_summary"
    CHAPTER_SUMMARY = "chapter_summary"
    TEXT_CHUNK = "text_chunk"
    IMAGE_CHUNK = "image_chunk"
    TABLE_CHUNK = "table_chunk"
    DERIVED_QUESTION = "derived_question"

# === 通用元数据字段 ===
UNIVERSAL_METADATA_FIELDS = {
    "content_id": str,           # 唯一标识  
    "document_id": str,          # 文档ID
    "content_type": str,         # "document_summary"|"chapter_summary"|"text_chunk"|"image_chunk"|"table_chunk"|"derived_question"
    "content_level": str,        # "document"|"chapter"|"chunk"|"question"
    
    # === 层级关系（高频使用）===
    "chapter_id": str,           # "1"|"2"|"3" (仅一级章节)
    "document_title": str,       # 文档标题
    "chapter_title": str,        # 章节标题
    
    # === 项目分类 ===
    "document_scope": str,       # "project"|"general"
    "project_name": str,         # 项目名称（scope=project时）
    
    # === 处理信息 ===
    "created_at": datetime,      # 创建时间
}

# === 文档类型管理表 ===
@dataclass
class DocumentType:
    """文档类型管理"""
    type_id: str                       # 类型ID
    type_name: str                     # 类型名称
    category: str                      # 大类别（工程资料/法规文件/标准规范等）
    description: str                   # 描述
    typical_structure: List[str]       # 典型结构（章节模式）
    created_at: datetime              # 创建时间

# === TOC存储表（简化版：JSON存储）===
@dataclass
class DocumentTOC:
    """文档TOC存储"""
    document_id: str                    # 文档ID
    toc_json: str                       # TOC的JSON字符串
    chapter_count: int                  # 一级章节数量
    total_sections: int                 # 总章节数量
    created_at: datetime               # 创建时间

# === 具体内容类型元数据表 ===

@dataclass
class ImageChunkMetadata:
    """图片chunk元数据"""
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 所属文档ID
    chapter_id: Optional[str]          # 所属章节ID（可能在章节外）
    
    # === 文件信息 ===
    image_path: str                    # 图片路径
    page_number: int                   # 页码
    caption: str                       # 图片标题
    
    # === 尺寸信息 ===
    width: int                         # 宽度
    height: int                        # 高度
    size: int                          # 文件大小
    aspect_ratio: float                # 宽高比
    
    # === 内容信息 ===
    ai_description: str                # AI生成的描述
    page_context: str                  # 页面上下文（包含前后文本）
    
    # === 处理信息 ===
    created_at: datetime               # 创建时间

@dataclass
class TableChunkMetadata:
    """表格chunk元数据"""
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 所属文档ID
    chapter_id: Optional[str]          # 所属章节ID（可能在章节外）
    
    # === 文件信息 ===
    table_path: str                    # 表格图片路径
    page_number: int                   # 页码
    caption: str                       # 表格标题
    
    # === 尺寸信息 ===
    width: int                         # 宽度
    height: int                        # 高度
    size: int                          # 文件大小
    aspect_ratio: float                # 宽高比
    
    # === 内容信息 ===
    ai_description: str                # AI生成的描述
    page_context: str                  # 页面上下文（包含前后文本）
    
    # === 处理信息 ===
    created_at: datetime               # 创建时间

@dataclass
class TextChunkMetadata:
    """文本chunk元数据"""
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 所属文档ID
    chapter_id: str                    # 所属章节ID
    
    # === 内容信息 ===
    chunk_type: str                    # "title"|"paragraph"|"list_item"
    word_count: int                    # 字数
    
    # === 位置信息 ===
    position_in_chapter: int           # 在章节中的位置顺序
    
    # === 段落信息 ===
    paragraph_index: int               # 段落索引（如果是段落）
    is_first_paragraph: bool           # 是否是章节首段
    is_last_paragraph: bool            # 是否是章节末段
    
    # === 上下文信息 ===
    preceding_chunk_id: Optional[str]  # 前一个chunk的ID
    following_chunk_id: Optional[str]  # 后一个chunk的ID
    
    # === 处理信息 ===
    created_at: datetime               # 创建时间

@dataclass
class ChapterSummaryMetadata:
    """章节摘要元数据"""
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 所属文档ID
    chapter_id: str                    # 章节ID（同时作为顺序标识）
    toc_id: str                        # 关联的TOC条目ID
    
    # === 章节顺序 ===
    chapter_order: int                 # 章节顺序（1,2,3...）
    
    # === 内容统计 ===
    word_count: int                    # 字数
    paragraph_count: int               # 段落数
    text_chunk_count: int              # 文本块数量
    image_count: int                   # 图片数量
    table_count: int                   # 表格数量
    
    # === 处理信息 ===
    created_at: datetime               # 创建时间

@dataclass
class DocumentSummaryMetadata:
    """文档摘要元数据"""
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 文档ID
    document_type_id: str              # 文档类型ID（关联DocumentType表）
    
    # === 文档信息 ===
    source_file_path: str              # 源文件路径
    file_name: str                     # 文件名
    file_size: int                     # 文件大小
    
    # === 内容统计 ===
    total_pages: int                   # 总页数
    total_word_count: int              # 总字数
    chapter_count: int                 # 章节数
    image_count: int                   # 图片总数
    table_count: int                   # 表格总数
    
    # === 处理信息 ===
    processing_time: float             # 处理时间（秒）
    created_at: datetime               # 创建时间
    
    # === 关联信息 ===
    toc_root_id: str                   # 根TOC条目ID

@dataclass
class DerivedQuestionMetadata:
    """派生问题元数据"""
    # === 核心标识 ===
    content_id: str                    # 唯一标识
    document_id: str                   # 所属文档ID
    chapter_id: str                    # 所属章节ID
    
    # === 问题信息 ===
    question_category: str             # 问题分类（基于章节内容）
    
    # === 生成信息 ===
    generated_from_chunk_id: str       # 基于哪个chunk生成的问题
    
    # === 处理信息 ===
    created_at: datetime               # 创建时间

# === 辅助函数 ===
def get_metadata_class(content_type: str):
    """根据内容类型获取对应的元数据类"""
    mapping = {
        "document_summary": DocumentSummaryMetadata,
        "chapter_summary": ChapterSummaryMetadata,
        "text_chunk": TextChunkMetadata,
        "image_chunk": ImageChunkMetadata,
        "table_chunk": TableChunkMetadata,
        "derived_question": DerivedQuestionMetadata,
    }
    return mapping.get(content_type)

def create_content_id(document_id: str, content_type: str, sequence: int) -> str:
    """创建内容ID"""
    return f"{document_id}_{content_type}_{sequence:06d}"

def filter_by_project(metadata_list: List[Any], project_name: str) -> List[Any]:
    """按项目过滤元数据"""
    return [m for m in metadata_list if hasattr(m, 'project_name') and m.project_name == project_name] 