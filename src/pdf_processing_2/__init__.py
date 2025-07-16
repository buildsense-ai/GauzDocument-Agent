"""
PDF Processing V2 - 重构版本

基于渐进式填充Final Schema的新架构
支持阶段性处理、中断恢复、并行优化
"""

# 重构版本标识
VERSION = "2.0.0"
REFACTOR_TARGET = "progressive_schema_filling"

# 阶段定义
PROCESSING_STAGES = {
    "stage1": "docling_parse_and_initial_schema",
    "stage2": "parallel_ai_processing", 
    "stage3": "content_chunking",
    "stage4": "chapter_summaries",
    "stage5": "question_generation"
}

# 导出重构后的主要组件
try:
    from .final_schema import FinalMetadataSchema
    from .stage1_docling_processor import Stage1DoclingProcessor
    
    __all__ = [
        "FinalMetadataSchema",
        "Stage1DoclingProcessor", 
        "VERSION",
        "PROCESSING_STAGES"
    ]
except ImportError as e:
    print(f"⚠️ 导入PDF Processing V2组件失败: {e}")
    __all__ = [
        "VERSION",
        "PROCESSING_STAGES"
    ] 