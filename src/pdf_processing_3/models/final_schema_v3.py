"""
PDF Processing V3 Final Schema

基于新字段命名规范的V3版本Schema定义：
- emb_* : 向量化字段 
- rtr_* : 检索字段（包括项目隔离）
- ana_* : 统计分析字段
- prc_* : 过程数据字段（本地JSON存储）
- sys_* : 系统字段

支持项目隔离、Mineru原生坐标系统、本地存储
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


def generate_content_id() -> str:
    """生成唯一的content_id"""
    return f"content_{uuid.uuid4().hex[:12]}"


def generate_document_id() -> str:
    """生成唯一的document_id"""
    return f"doc_{uuid.uuid4().hex[:8]}"


def generate_project_id(prefix: str = "proj") -> str:
    """
    生成项目ID的最佳实践格式
    
    推荐格式: proj_YYYYMMDD_shortname_random
    示例: proj_20250125_medicorp_a8f3, proj_20250125_design_b2d9
    
    Args:
        prefix: 前缀，默认"proj"
    
    Returns:
        格式化的项目ID
    """
    date_str = datetime.now().strftime("%Y%m%d")
    random_suffix = uuid.uuid4().hex[:4]
    return f"{prefix}_{date_str}_{random_suffix}"


@dataclass
class DocumentSummaryV3:
    """
    文档摘要对象V3版本
    
    核心改进：
    - 添加项目隔离字段 rtr_project_id
    - 新字段命名规范
    - 本地JSON存储策略
    - Mineru任务追踪
    """
    
    # ===== 核心字段 =====
    content_id: str = field(default_factory=generate_content_id)
    rtr_document_id: str = field(default_factory=generate_document_id)
    rtr_project_id: str = ""                         # 项目隔离硬过滤
    rtr_content_type: str = "document_summary"        # 内容类型标识
    
    # ===== 向量化字段 =====
    emb_summary: Optional[str] = None                 # AI生成的文档摘要（向量化）
    
    # ===== 检索字段 =====
    rtr_source_path: str = ""                        # 原始文件路径
    rtr_file_name: str = ""                          # 文件名（用于UI展示）
    
    # ===== 过程数据字段（本地JSON存储）=====
    prc_full_raw_text: Optional[str] = None          # 完整原始文本
    prc_mineru_raw_output: Optional[Dict[str, Any]] = None  # Mineru完整原始输出
    prc_page_texts: Optional[Dict[str, str]] = None  # 分页文本（调试用）
    prc_cleaned_page_texts: Optional[Dict[str, str]] = None  # 清理后分页文本
    prc_toc: Optional[Dict[str, Any]] = None         # 目录信息
    
    # ===== 统计字段 =====
    ana_total_pages: int = 0                         # 总页数
    ana_word_count: Optional[int] = None             # 总字数
    ana_chapter_count: int = 0                       # 章节数
    ana_image_count: int = 0                         # 图片数量
    ana_table_count: int = 0                         # 表格数量
    ana_file_size: int = 0                           # 文件大小（字节）
    ana_processing_time: Optional[float] = None      # 处理时间（秒）
    
    # ===== 系统字段 =====
    sys_created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sys_schema_version: str = "3.0.0"
    sys_mineru_task_id: Optional[str] = None         # Mineru任务ID


@dataclass  
class TextChunkV3:
    """
    文本块对象V3版本
    
    核心改进：
    - 基于Mineru原生坐标系统
    - 移除页码依赖
    - 项目隔离支持
    """
    
    # ===== 核心字段 =====
    content_id: str = field(default_factory=generate_content_id)
    rtr_document_id: str = ""
    rtr_project_id: str = ""                         # 项目隔离
    rtr_content_type: str = "text_chunk"
    
    # ===== 向量化字段 =====
    emb_content: str = ""                            # 主要向量化内容
    
    # ===== 坐标字段（基于Mineru）=====
    rtr_mineru_chunk_id: Optional[str] = None        # Mineru原始chunk标识
    rtr_chapter_id: Optional[str] = None             # 章节关联ID
    rtr_sequence_index: Optional[int] = None         # 在文档/章节中的顺序
    
    # ===== 统计字段 =====
    ana_word_count: int = 0                          # 文本字数
    
    # ===== 系统字段 =====
    sys_created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ImageChunkV3:
    """
    图片块对象V3版本
    
    核心改进：
    - Mineru原生坐标和元数据
    - 项目隔离支持  
    - 本地媒体文件管理
    """
    
    # ===== 核心字段 =====
    content_id: str = field(default_factory=generate_content_id)
    rtr_document_id: str = ""
    rtr_project_id: str = ""                         # 项目隔离
    rtr_content_type: str = "image_chunk"
    
    # ===== 检索字段 =====
    rtr_media_path: str = ""                         # 图片存储路径
    rtr_caption: str = ""                            # 简短标题/说明
    
    # ===== 坐标字段（基于Mineru）=====
    rtr_mineru_chunk_id: Optional[str] = None        # Mineru原始坐标
    rtr_chapter_id: Optional[str] = None             # 章节关联
    rtr_sequence_index: Optional[int] = None         # 在文档中的顺序
    
    # ===== 过程数据字段 =====
    prc_mineru_metadata: Optional[Dict[str, Any]] = None  # Mineru原始元数据
    prc_page_context: Optional[str] = None          # 页面上下文（调试用）
    
    # ===== 向量化字段（AI生成）=====
    emb_search_summary: Optional[str] = None         # 搜索摘要（向量化）
    emb_detail_desc: Optional[str] = None           # 详细描述（向量化）
    emb_engineering_desc: Optional[str] = None      # 工程技术描述（向量化）
    
    # ===== 统计字段 =====
    ana_width: int = 0                               # 图片宽度
    ana_height: int = 0                              # 图片高度
    ana_file_size: int = 0                           # 文件大小
    ana_aspect_ratio: float = 0.0                   # 宽高比
    
    # ===== 系统字段 =====
    sys_created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TableChunkV3:
    """
    表格块对象V3版本
    
    与ImageChunkV3类似的设计，针对表格优化
    """
    
    # ===== 核心字段 =====
    content_id: str = field(default_factory=generate_content_id)
    rtr_document_id: str = ""
    rtr_project_id: str = ""                         # 项目隔离
    rtr_content_type: str = "table_chunk"
    
    # ===== 检索字段 =====
    rtr_media_path: str = ""                         # 表格图片路径
    rtr_caption: str = ""                            # 表格标题
    
    # ===== 坐标字段（基于Mineru）=====
    rtr_mineru_chunk_id: Optional[str] = None        # Mineru原始坐标
    rtr_chapter_id: Optional[str] = None             # 章节关联
    rtr_sequence_index: Optional[int] = None         # 在文档中的顺序
    
    # ===== 过程数据字段 =====
    prc_mineru_metadata: Optional[Dict[str, Any]] = None  # Mineru原始元数据
    prc_raw_table_data: Optional[List[List[str]]] = None  # 原始表格数据
    prc_page_context: Optional[str] = None          # 页面上下文
    
    # ===== 向量化字段（AI生成）=====
    emb_search_summary: Optional[str] = None         # 搜索摘要（向量化）
    emb_detail_desc: Optional[str] = None           # 详细描述（向量化）
    emb_data_summary: Optional[str] = None          # 数据摘要（向量化）
    
    # ===== 统计字段 =====
    ana_rows: int = 0                                # 行数
    ana_columns: int = 0                             # 列数
    ana_width: int = 0                               # 表格图片宽度
    ana_height: int = 0                              # 表格图片高度
    ana_file_size: int = 0                           # 文件大小
    
    # ===== 系统字段 =====
    sys_created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ChapterSummaryV3:
    """
    章节摘要对象V3版本
    
    核心改进：
    - 基于Mineru的章节识别
    - 项目隔离支持
    """
    
    # ===== 核心字段 =====
    content_id: str = field(default_factory=generate_content_id)
    rtr_document_id: str = ""
    rtr_project_id: str = ""                         # 项目隔离
    rtr_content_type: str = "chapter_summary"
    
    # ===== 检索字段 =====
    rtr_chapter_id: str = ""                         # 章节ID
    rtr_chapter_title: str = ""                      # 章节标题
    rtr_chapter_level: int = 1                       # 章节层级（1,2,3...）
    
    # ===== 过程数据字段 =====
    prc_raw_content: Optional[str] = None           # 章节原始内容
    prc_mineru_toc_info: Optional[Dict[str, Any]] = None  # Mineru目录信息
    
    # ===== 向量化字段 =====
    emb_ai_summary: Optional[str] = None             # AI生成的章节摘要
    
    # ===== 统计字段 =====
    ana_word_count: int = 0                          # 章节字数
    ana_text_chunks_count: int = 0                   # 包含的文本块数量
    ana_image_count: int = 0                         # 包含的图片数量
    ana_table_count: int = 0                         # 包含的表格数量
    
    # ===== 系统字段 =====
    sys_created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DerivedQuestionV3:
    """
    衍生问题对象V3版本
    
    暂未实现的功能，保留设计
    """
    
    # ===== 核心字段 =====
    content_id: str = field(default_factory=generate_content_id)
    rtr_document_id: str = ""
    rtr_project_id: str = ""                         # 项目隔离
    rtr_content_type: str = "derived_question"
    
    # ===== 向量化字段 =====
    emb_content: str = ""                            # 问题文本（向量化）
    
    # ===== 检索字段 =====
    rtr_question_type: str = ""                      # 问题类型
    rtr_confidence_score: float = 0.0               # 置信度分数
    
    # ===== 过程数据字段 =====
    prc_source_context: Optional[str] = None        # 来源上下文
    prc_generation_metadata: Optional[Dict[str, Any]] = None  # 生成元数据
    
    # ===== 系统字段 =====
    sys_created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class FinalMetadataSchemaV3:
    """
    最终元数据结构V3版本
    
    整合所有六大对象的容器
    """
    
    # ===== 文档标识 =====
    document_id: str = ""
    project_id: str = ""
    schema_version: str = "3.0.0"
    
    # ===== 六大对象 =====
    document_summary: Optional[DocumentSummaryV3] = None
    text_chunks: List[TextChunkV3] = field(default_factory=list)
    image_chunks: List[ImageChunkV3] = field(default_factory=list)
    table_chunks: List[TableChunkV3] = field(default_factory=list)
    chapter_summaries: List[ChapterSummaryV3] = field(default_factory=list)
    derived_questions: List[DerivedQuestionV3] = field(default_factory=list)
    
    # ===== 系统字段 =====
    sys_created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sys_last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于JSON序列化"""
        from dataclasses import asdict
        return asdict(self)
    
    def get_all_chunks_count(self) -> Dict[str, int]:
        """获取所有块的统计信息"""
        return {
            "text_chunks": len(self.text_chunks),
            "image_chunks": len(self.image_chunks), 
            "table_chunks": len(self.table_chunks),
            "chapter_summaries": len(self.chapter_summaries),
            "derived_questions": len(self.derived_questions),
        }
    
    def validate_project_consistency(self) -> bool:
        """验证所有对象的项目ID一致性"""
        if not self.project_id:
            return False
            
        # 检查所有对象的project_id是否一致
        all_objects = []
        if self.document_summary:
            all_objects.append(self.document_summary)
        all_objects.extend(self.text_chunks)
        all_objects.extend(self.image_chunks) 
        all_objects.extend(self.table_chunks)
        all_objects.extend(self.chapter_summaries)
        all_objects.extend(self.derived_questions)
        
        for obj in all_objects:
            if hasattr(obj, 'rtr_project_id') and obj.rtr_project_id != self.project_id:
                return False
                
        return True 