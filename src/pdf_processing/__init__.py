"""
PDF Processing Package

提供PDF解析、图片表格提取、AI内容重组的模块化组件
"""

from .config import PDFProcessingConfig, DoclingConfig, MediaExtractorConfig, AIContentConfig, OutputConfig, create_output_directory, validate_config
from .data_models import PageData, ImageWithContext, TableWithContext, ProcessingResult, AdvancedProcessingResult
from .media_extractor import MediaExtractor
from .pdf_document_parser import PDFDocumentParser
from .ai_content_reorganizer import AIContentReorganizer
from .document_structure_analyzer import DocumentStructureAnalyzer, DocumentStructure, MinimalChunk, ChapterInfo
from .metadata_enricher import MetadataEnricher, EnrichedChunk, ChapterSummary, IndexStructure
from .pdf_parser_tool import PDFParserTool

# 便捷函数
def get_config():
    """获取默认配置"""
    return PDFProcessingConfig.from_env()

def create_document_parser(config=None):
    """创建PDF文档解析器"""
    return PDFDocumentParser(config)

def create_media_extractor(parallel_processing=True, max_workers=4):
    """创建媒体提取器"""
    return MediaExtractor(parallel_processing, max_workers)

def create_ai_content_reorganizer(config=None):
    """创建AI内容重组器"""
    return AIContentReorganizer(config)

def create_structure_analyzer(config=None):
    """创建文档结构分析器"""
    return DocumentStructureAnalyzer(config)

def create_metadata_enricher(config=None):
    """创建元数据增强器"""
    return MetadataEnricher(config)

def create_pdf_parser_tool(config=None):
    """创建PDF解析工具"""
    return PDFParserTool(config)

__all__ = [
    # 配置类
    'PDFProcessingConfig',
    'DoclingConfig', 
    'MediaExtractorConfig',
    'AIContentConfig',
    'OutputConfig',
    
    # 数据模型
    'PageData',
    'ImageWithContext',
    'TableWithContext', 
    'ProcessingResult',
    'AdvancedProcessingResult',
    
    # 基础处理组件
    'MediaExtractor',
    'PDFDocumentParser',
    'AIContentReorganizer',
    
    # 高级处理组件
    'DocumentStructureAnalyzer',
    'DocumentStructure',
    'MinimalChunk',
    'ChapterInfo',
    'MetadataEnricher',
    'EnrichedChunk',
    'ChapterSummary',
    'IndexStructure',
    
    # 统一工具接口
    'PDFParserTool',
    
    # 便捷函数
    'get_config',
    'create_document_parser',
    'create_media_extractor',
    'create_ai_content_reorganizer',
    'create_structure_analyzer',
    'create_metadata_enricher',
    'create_pdf_parser_tool',
    'create_output_directory',
    'validate_config'
] 