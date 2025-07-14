"""
PDF Processing 元数据表结构定义
支持所有类型的embedding内容的统一元数据结构
"""

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from enum import Enum
import json

class ContentType(Enum):
    """内容类型枚举"""
    DOCUMENT_SUMMARY = "document_summary"      # 文档摘要
    CHAPTER_SUMMARY = "chapter_summary"        # 章节摘要
    TEXT_CHUNK = "text_chunk"                  # 文本块
    IMAGE_CHUNK = "image_chunk"                # 图片块
    TABLE_CHUNK = "table_chunk"                # 表格块
    DERIVED_QUESTION = "derived_question"      # 衍生问题

class ContentLevel(Enum):
    """内容层级枚举"""
    DOCUMENT = "document"                      # 文档级
    CHAPTER = "chapter"                        # 章节级  
    CHUNK = "chunk"                           # 块级
    QUESTION = "question"                     # 问题级

@dataclass
class UnifiedMetadata:
    """
    统一的元数据结构
    适用于所有类型的embedding内容
    """
    # === 基础标识字段 ===
    content_id: str                           # 内容唯一标识
    document_id: str                          # 文档ID
    content_type: ContentType                 # 内容类型
    content_level: ContentLevel               # 内容层级
    
    # === 层级关系字段 ===
    chapter_id: Optional[str] = None          # 章节ID（如 "1", "2.1", "3.2.1"）
    chapter_title: Optional[str] = None       # 章节标题
    chapter_level: Optional[int] = None       # 章节数字层级（1, 2, 3...）
    parent_chunk_id: Optional[str] = None     # 父级chunk ID（用于关联）
    
    # === 内容描述字段 ===
    content: str                              # 实际内容/描述
    content_summary: Optional[str] = None     # 内容摘要
    document_title: Optional[str] = None      # 文档标题
    document_summary: Optional[str] = None    # 文档摘要
    
    # === 位置和尺寸字段 ===
    page_number: Optional[int] = None         # 页码
    position_in_page: Optional[int] = None    # 页面内位置序号
    position_in_chapter: Optional[int] = None # 章节内位置序号
    
    # === 媒体文件字段 ===
    file_path: Optional[str] = None           # 文件路径（图片/表格）
    file_size: Optional[int] = None           # 文件大小（字节）
    file_format: Optional[str] = None         # 文件格式（png, jpg等）
    image_dimensions: Optional[str] = None    # 图片尺寸（如 "800x600"）
    
    # === 质量和置信度字段 ===
    extraction_confidence: Optional[float] = None  # 提取置信度 (0-1)
    ai_description_confidence: Optional[float] = None  # AI描述置信度 (0-1)
    content_quality_score: Optional[float] = None     # 内容质量分数 (0-1)
    
    # === 关联关系字段 ===
    related_images: Optional[List[str]] = None      # 相关图片ID列表
    related_tables: Optional[List[str]] = None      # 相关表格ID列表
    related_chunks: Optional[List[str]] = None      # 相关文本块ID列表
    derived_questions: Optional[List[str]] = None   # 衍生问题ID列表
    
    # === 检索优化字段 ===
    keywords: Optional[List[str]] = None            # 关键词列表
    tags: Optional[List[str]] = None                # 标签列表
    language: Optional[str] = None                  # 语言标识
    
    # === 处理信息字段 ===
    created_at: Optional[str] = None                # 创建时间
    updated_at: Optional[str] = None                # 更新时间
    processing_version: Optional[str] = None        # 处理版本
    
    # === 扩展字段 ===
    extra_metadata: Optional[Dict[str, Any]] = None  # 额外元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {}
        for field_name, field_value in self.__dict__.items():
            if field_value is not None:
                if isinstance(field_value, (ContentType, ContentLevel)):
                    result[field_name] = field_value.value
                elif isinstance(field_value, list) and field_value:
                    result[field_name] = field_value
                elif not isinstance(field_value, list):
                    result[field_name] = field_value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedMetadata':
        """从字典创建实例"""
        # 处理枚举字段
        if 'content_type' in data:
            data['content_type'] = ContentType(data['content_type'])
        if 'content_level' in data:
            data['content_level'] = ContentLevel(data['content_level'])
        
        return cls(**data)

# === 具体类型的元数据构建函数 ===

def create_document_summary_metadata(
    document_id: str,
    document_title: str,
    content: str,
    content_summary: str,
    total_pages: int,
    **kwargs
) -> UnifiedMetadata:
    """创建文档摘要元数据"""
    return UnifiedMetadata(
        content_id=f"doc_summary_{document_id}",
        document_id=document_id,
        content_type=ContentType.DOCUMENT_SUMMARY,
        content_level=ContentLevel.DOCUMENT,
        content=content,
        content_summary=content_summary,
        document_title=document_title,
        document_summary=content_summary,
        extra_metadata={"total_pages": total_pages, **kwargs}
    )

def create_chapter_summary_metadata(
    document_id: str,
    chapter_id: str,
    chapter_title: str,
    chapter_level: int,
    content: str,
    content_summary: str,
    document_title: str,
    document_summary: str,
    **kwargs
) -> UnifiedMetadata:
    """创建章节摘要元数据"""
    return UnifiedMetadata(
        content_id=f"chapter_summary_{document_id}_{chapter_id}",
        document_id=document_id,
        content_type=ContentType.CHAPTER_SUMMARY,
        content_level=ContentLevel.CHAPTER,
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        chapter_level=chapter_level,
        content=content,
        content_summary=content_summary,
        document_title=document_title,
        document_summary=document_summary,
        **kwargs
    )

def create_text_chunk_metadata(
    document_id: str,
    chunk_id: str,
    chapter_id: str,
    chapter_title: str,
    chapter_level: int,
    content: str,
    page_number: int,
    position_in_chapter: int,
    document_title: str,
    document_summary: str,
    **kwargs
) -> UnifiedMetadata:
    """创建文本块元数据"""
    return UnifiedMetadata(
        content_id=f"text_chunk_{document_id}_{chunk_id}",
        document_id=document_id,
        content_type=ContentType.TEXT_CHUNK,
        content_level=ContentLevel.CHUNK,
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        chapter_level=chapter_level,
        content=content,
        page_number=page_number,
        position_in_chapter=position_in_chapter,
        document_title=document_title,
        document_summary=document_summary,
        **kwargs
    )

def create_image_chunk_metadata(
    document_id: str,
    image_id: str,
    chapter_id: str,
    chapter_title: str,
    chapter_level: int,
    ai_description: str,
    file_path: str,
    page_number: int,
    position_in_chapter: int,
    document_title: str,
    document_summary: str,
    file_size: Optional[int] = None,
    file_format: Optional[str] = None,
    image_dimensions: Optional[str] = None,
    ai_description_confidence: Optional[float] = None,
    **kwargs
) -> UnifiedMetadata:
    """创建图片块元数据"""
    return UnifiedMetadata(
        content_id=f"image_chunk_{document_id}_{image_id}",
        document_id=document_id,
        content_type=ContentType.IMAGE_CHUNK,
        content_level=ContentLevel.CHUNK,
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        chapter_level=chapter_level,
        content=ai_description,
        file_path=file_path,
        page_number=page_number,
        position_in_chapter=position_in_chapter,
        document_title=document_title,
        document_summary=document_summary,
        file_size=file_size,
        file_format=file_format,
        image_dimensions=image_dimensions,
        ai_description_confidence=ai_description_confidence,
        **kwargs
    )

def create_table_chunk_metadata(
    document_id: str,
    table_id: str,
    chapter_id: str,
    chapter_title: str,
    chapter_level: int,
    ai_description: str,
    file_path: str,
    page_number: int,
    position_in_chapter: int,
    document_title: str,
    document_summary: str,
    file_size: Optional[int] = None,
    file_format: Optional[str] = None,
    table_dimensions: Optional[str] = None,
    ai_description_confidence: Optional[float] = None,
    **kwargs
) -> UnifiedMetadata:
    """创建表格块元数据"""
    return UnifiedMetadata(
        content_id=f"table_chunk_{document_id}_{table_id}",
        document_id=document_id,
        content_type=ContentType.TABLE_CHUNK,
        content_level=ContentLevel.CHUNK,
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        chapter_level=chapter_level,
        content=ai_description,
        file_path=file_path,
        page_number=page_number,
        position_in_chapter=position_in_chapter,
        document_title=document_title,
        document_summary=document_summary,
        file_size=file_size,
        file_format=file_format,
        extra_metadata={"table_dimensions": table_dimensions, **kwargs},
        ai_description_confidence=ai_description_confidence,
        **kwargs
    )

def create_derived_question_metadata(
    document_id: str,
    question_id: str,
    chapter_id: str,
    chapter_title: str,
    chapter_level: int,
    question_content: str,
    document_title: str,
    document_summary: str,
    **kwargs
) -> UnifiedMetadata:
    """创建衍生问题元数据"""
    return UnifiedMetadata(
        content_id=f"derived_question_{document_id}_{question_id}",
        document_id=document_id,
        content_type=ContentType.DERIVED_QUESTION,
        content_level=ContentLevel.QUESTION,
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        chapter_level=chapter_level,
        content=question_content,
        document_title=document_title,
        document_summary=document_summary,
        **kwargs
    )

# === 元数据验证函数 ===

def validate_metadata(metadata: UnifiedMetadata) -> bool:
    """验证元数据完整性"""
    # 必需字段检查
    required_fields = ['content_id', 'document_id', 'content_type', 'content_level', 'content']
    for field in required_fields:
        if getattr(metadata, field) is None:
            return False
    
    # 类型特定验证
    if metadata.content_type in [ContentType.IMAGE_CHUNK, ContentType.TABLE_CHUNK]:
        if not metadata.file_path:
            return False
    
    if metadata.content_level == ContentLevel.CHUNK:
        if not metadata.chapter_id:
            return False
    
    return True

# === 元数据索引优化 ===

def get_search_fields(metadata: UnifiedMetadata) -> Dict[str, Any]:
    """获取用于搜索的字段"""
    search_fields = {
        'content_type': metadata.content_type.value,
        'content_level': metadata.content_level.value,
        'document_id': metadata.document_id,
    }
    
    # 添加章节信息
    if metadata.chapter_id:
        search_fields['chapter_id'] = metadata.chapter_id
        search_fields['chapter_level'] = metadata.chapter_level
    
    # 添加页面信息
    if metadata.page_number:
        search_fields['page_number'] = metadata.page_number
    
    # 添加文件信息
    if metadata.file_path:
        search_fields['has_file'] = True
        search_fields['file_format'] = metadata.file_format
    
    return search_fields

# === 使用示例 ===

def create_sample_metadata():
    """创建示例元数据"""
    
    # 文档摘要
    doc_summary = create_document_summary_metadata(
        document_id="alphaevolve_2024",
        document_title="AlphaEvolve: A coding agent for scientific discovery",
        content="AlphaEvolve是一个用于科学和算法发现的编程智能体...",
        content_summary="AlphaEvolve系统介绍",
        total_pages=44
    )
    
    # 章节摘要
    chapter_summary = create_chapter_summary_metadata(
        document_id="alphaevolve_2024",
        chapter_id="2.1",
        chapter_title="Task specification",
        chapter_level=2,
        content="任务规范部分详细描述了...",
        content_summary="任务规范章节",
        document_title="AlphaEvolve: A coding agent for scientific discovery",
        document_summary="AlphaEvolve系统介绍"
    )
    
    # 文本块
    text_chunk = create_text_chunk_metadata(
        document_id="alphaevolve_2024",
        chunk_id="chunk_001",
        chapter_id="2.1",
        chapter_title="Task specification",
        chapter_level=2,
        content="AlphaEvolve通过生成代码来解决科学问题...",
        page_number=5,
        position_in_chapter=1,
        document_title="AlphaEvolve: A coding agent for scientific discovery",
        document_summary="AlphaEvolve系统介绍"
    )
    
    # 图片块
    image_chunk = create_image_chunk_metadata(
        document_id="alphaevolve_2024",
        image_id="img_001",
        chapter_id="2.1",
        chapter_title="Task specification",
        chapter_level=2,
        ai_description="系统架构图显示了AlphaEvolve的主要组件",
        file_path="parser_output/alphaevolve_2024/picture-1.png",
        page_number=5,
        position_in_chapter=2,
        document_title="AlphaEvolve: A coding agent for scientific discovery",
        document_summary="AlphaEvolve系统介绍",
        file_size=1024000,
        file_format="png",
        image_dimensions="800x600",
        ai_description_confidence=0.95
    )
    
    # 表格块
    table_chunk = create_table_chunk_metadata(
        document_id="alphaevolve_2024",
        table_id="table_001",
        chapter_id="3.1",
        chapter_title="Results",
        chapter_level=2,
        ai_description="实验结果表格显示了不同算法的性能对比",
        file_path="parser_output/alphaevolve_2024/table-1.png",
        page_number=15,
        position_in_chapter=1,
        document_title="AlphaEvolve: A coding agent for scientific discovery",
        document_summary="AlphaEvolve系统介绍",
        file_size=2048000,
        file_format="png",
        table_dimensions="5x10",
        ai_description_confidence=0.88
    )
    
    # 衍生问题
    derived_question = create_derived_question_metadata(
        document_id="alphaevolve_2024",
        question_id="q_001",
        chapter_id="2.1",
        chapter_title="Task specification",
        chapter_level=2,
        question_content="AlphaEvolve如何处理复杂的科学计算任务？",
        document_title="AlphaEvolve: A coding agent for scientific discovery",
        document_summary="AlphaEvolve系统介绍"
    )
    
    return [doc_summary, chapter_summary, text_chunk, image_chunk, table_chunk, derived_question] 