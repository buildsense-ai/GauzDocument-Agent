"""
PDF Processing Configuration

管理PDF处理相关的配置参数
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DoclingConfig:
    """Docling解析器配置"""
    images_scale: float = 5.0
    generate_page_images: bool = True
    generate_picture_images: bool = True
    ocr_enabled: bool = True
    artifacts_path: Optional[str] = None


@dataclass
class MediaExtractorConfig:
    """媒体提取器配置"""
    parallel_processing: bool = True
    max_workers: int = 32  # 提升并发数，提高媒体处理效率
    supported_image_formats: List[str] = field(default_factory=lambda: ["PNG", "JPEG", "JPG"])
    supported_table_formats: List[str] = field(default_factory=lambda: ["PNG"])


@dataclass
class AIContentConfig:
    """AI内容处理配置"""
    default_llm_model: str = "qwen-turbo-latest"  # 默认使用Qwen，rate limit更高
    default_vlm_model: str = "google/gemini-2.5-flash"
    max_context_length: int = 50000
    enable_parallel_processing: bool = True
    max_workers: int = 32  # 提升并发数，充分利用Qwen API能力
    max_retries: int = 3
    # 文本清洗开关
    enable_text_cleaning: bool = True
    # 图片描述生成开关
    enable_image_description: bool = True
    # 表格描述生成开关
    enable_table_description: bool = True


@dataclass
class OutputConfig:
    """输出配置"""
    base_output_dir: str = "parser_output"
    create_timestamped_dirs: bool = True
    # 自定义输出目录路径（如果设置，则忽略base_output_dir和create_timestamped_dirs）
    custom_output_path: Optional[str] = None
    save_json_files: bool = True
    save_summary: bool = True
    preserve_original_filenames: bool = False


@dataclass
class PDFProcessingConfig:
    """PDF处理总体配置"""
    docling: DoclingConfig = field(default_factory=DoclingConfig)
    media_extractor: MediaExtractorConfig = field(default_factory=MediaExtractorConfig)
    ai_content: AIContentConfig = field(default_factory=AIContentConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    
    # 支持的AI模型列表 - 简化为只包含实际使用的模型
    supported_models: List[str] = field(default_factory=lambda: [
        # Qwen模型（用于文本处理，高rate limit）
        "qwen-turbo-latest", "qwen-plus-latest", "qwen-max-latest",
        # DeepSeek模型（用于文本处理）
        "deepseek-chat", "deepseek-reasoner",
        # Gemini模型（用于多模态处理）
        "google/gemini-2.5-flash", "google/gemini-pro",
        # 保留OpenAI接口兼容性（如果必要）
        "openai/gpt-4o", "openai/gpt-4o-mini"
    ])
    
    @classmethod
    def from_env(cls) -> 'PDFProcessingConfig':
        """从环境变量创建配置"""
        config = cls()
        
        # 从环境变量读取配置
        if os.getenv('PDF_IMAGES_SCALE'):
            config.docling.images_scale = float(os.getenv('PDF_IMAGES_SCALE'))
        
        if os.getenv('PDF_PARALLEL_PROCESSING'):
            config.media_extractor.parallel_processing = os.getenv('PDF_PARALLEL_PROCESSING').lower() == 'true'
        
        if os.getenv('PDF_MAX_WORKERS'):
            config.media_extractor.max_workers = int(os.getenv('PDF_MAX_WORKERS'))
        
        if os.getenv('PDF_DEFAULT_LLM_MODEL'):
            config.ai_content.default_llm_model = os.getenv('PDF_DEFAULT_LLM_MODEL')
        
        if os.getenv('PDF_DEFAULT_VLM_MODEL'):
            config.ai_content.default_vlm_model = os.getenv('PDF_DEFAULT_VLM_MODEL')
        
        if os.getenv('PDF_MAX_WORKERS'):
            config.ai_content.max_workers = int(os.getenv('PDF_MAX_WORKERS'))
        
        if os.getenv('PDF_ENABLE_TEXT_CLEANING'):
            config.ai_content.enable_text_cleaning = os.getenv('PDF_ENABLE_TEXT_CLEANING').lower() == 'true'
        
        if os.getenv('PDF_ENABLE_IMAGE_DESCRIPTION'):
            config.ai_content.enable_image_description = os.getenv('PDF_ENABLE_IMAGE_DESCRIPTION').lower() == 'true'
        
        if os.getenv('PDF_ENABLE_TABLE_DESCRIPTION'):
            config.ai_content.enable_table_description = os.getenv('PDF_ENABLE_TABLE_DESCRIPTION').lower() == 'true'
        
        if os.getenv('PDF_OUTPUT_DIR'):
            config.output.base_output_dir = os.getenv('PDF_OUTPUT_DIR')
        
        if os.getenv('PDF_CUSTOM_OUTPUT_PATH'):
            config.output.custom_output_path = os.getenv('PDF_CUSTOM_OUTPUT_PATH')
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'docling': {
                'images_scale': self.docling.images_scale,
                'generate_page_images': self.docling.generate_page_images,
                'generate_picture_images': self.docling.generate_picture_images,
                'ocr_enabled': self.docling.ocr_enabled,
                'artifacts_path': self.docling.artifacts_path
            },
            'media_extractor': {
                'parallel_processing': self.media_extractor.parallel_processing,
                'max_workers': self.media_extractor.max_workers,
                'supported_image_formats': self.media_extractor.supported_image_formats,
                'supported_table_formats': self.media_extractor.supported_table_formats
            },
            'ai_content': {
                'default_llm_model': self.ai_content.default_llm_model,
                'default_vlm_model': self.ai_content.default_vlm_model,
                'max_context_length': self.ai_content.max_context_length,
                'enable_parallel_processing': self.ai_content.enable_parallel_processing,
                'max_workers': self.ai_content.max_workers,
                'max_retries': self.ai_content.max_retries,
                'enable_text_cleaning': self.ai_content.enable_text_cleaning,
                'enable_image_description': self.ai_content.enable_image_description,
                'enable_table_description': self.ai_content.enable_table_description
            },
            'output': {
                'base_output_dir': self.output.base_output_dir,
                'create_timestamped_dirs': self.output.create_timestamped_dirs,
                'custom_output_path': self.output.custom_output_path,
                'save_json_files': self.output.save_json_files,
                'save_summary': self.output.save_summary,
                'preserve_original_filenames': self.output.preserve_original_filenames
            },
            'supported_models': self.supported_models
        }


# 默认配置实例
DEFAULT_CONFIG = PDFProcessingConfig()


def get_config() -> PDFProcessingConfig:
    """获取配置实例"""
    return PDFProcessingConfig.from_env()


def validate_config(config: PDFProcessingConfig) -> List[str]:
    """验证配置并返回错误信息"""
    errors = []
    
    # 验证Docling配置
    if config.docling.images_scale <= 0:
        errors.append("images_scale must be greater than 0")
    
    # 验证媒体提取器配置
    if config.media_extractor.max_workers <= 0:
        errors.append("max_workers must be greater than 0")
    
    # 验证AI内容配置
    # 检查默认LLM模型是否为支持的模型
    supported_llm_models = ["qwen-turbo-latest", "qwen-plus-latest", "qwen-max-latest", "deepseek-chat", "deepseek-reasoner"]
    if config.ai_content.default_llm_model not in supported_llm_models:
        errors.append(f"default_llm_model '{config.ai_content.default_llm_model}' must be one of {supported_llm_models}")
    
    # 检查默认VLM模型是否为支持的Gemini模型
    supported_vlm_models = ["google/gemini-2.5-flash", "google/gemini-pro"]
    if config.ai_content.default_vlm_model not in supported_vlm_models:
        errors.append(f"default_vlm_model '{config.ai_content.default_vlm_model}' must be one of {supported_vlm_models}")
    
    if config.ai_content.max_context_length <= 0:
        errors.append("max_context_length must be greater than 0")
    
    # 验证输出配置
    if not config.output.base_output_dir:
        errors.append("base_output_dir cannot be empty")
    
    return errors


def create_output_directory(config: PDFProcessingConfig, 
                          pdf_filename: Optional[str] = None) -> str:
    """
    创建输出目录
    
    Args:
        config: PDF处理配置
        pdf_filename: PDF文件名（可选）
        
    Returns:
        str: 输出目录路径
    """
    # 如果设置了自定义输出路径，直接使用
    if config.output.custom_output_path:
        output_dir = Path(config.output.custom_output_path)
    else:
        base_dir = Path(config.output.base_output_dir)
        
        if config.output.create_timestamped_dirs:
            from datetime import datetime
            import random
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_id = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
            
            if pdf_filename and config.output.preserve_original_filenames:
                pdf_name = Path(pdf_filename).stem
                dir_name = f"{timestamp}_{pdf_name}_{random_id}"
            else:
                dir_name = f"{timestamp}_{random_id}"
            
            output_dir = base_dir / dir_name
        else:
            output_dir = base_dir
    
    output_dir.mkdir(parents=True, exist_ok=True)
    return str(output_dir) 