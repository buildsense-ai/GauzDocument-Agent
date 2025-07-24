"""
PDF Processing V3 Module

基于Mineru外部服务的PDF处理系统V3版本
- 新的V3 Schema定义
- 项目隔离支持
- 本地JSON存储
- Mineru API集成
"""

__version__ = "3.0.0"
__author__ = "GauzDocument Team"

from .models.final_schema_v3 import *
from .clients.mineru_client import MineruClient
from .storage.local_storage_manager import LocalStorageManager

__all__ = [
    # Schema Models
    'DocumentSummaryV3',
    'TextChunkV3', 
    'ImageChunkV3',
    'TableChunkV3',
    'ChapterSummaryV3',
    'DerivedQuestionV3',
    'FinalMetadataSchemaV3',
    
    # Clients
    'MineruClient',
    
    # Storage
    'LocalStorageManager',
] 