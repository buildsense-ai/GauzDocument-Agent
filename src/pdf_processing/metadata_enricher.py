#!/usr/bin/env python3
"""
元数据增强器
支持"小块检索，大块喂养"模式的元数据增强
重点：章节归属信息和检索优化的元数据
"""

import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from .config import PDFProcessingConfig
from .document_structure_analyzer import DocumentStructure, MinimalChunk, ChapterInfo
from .data_models import ProcessingResult, PageData, ImageWithContext, TableWithContext
try:
    from ..deepseek_client import DeepSeekClient
    from ..openrouter_client import OpenRouterClient
    from ..qwen_client import QwenClient
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    sys.path.append('..')
    from deepseek_client import DeepSeekClient
    from openrouter_client import OpenRouterClient
    from qwen_client import QwenClient

logger = logging.getLogger(__name__)

@dataclass
class EnrichedChunk:
    """增强的最小分块信息 - 为检索优化"""
    # 基础分块信息
    chunk_id: int
    content: str
    chunk_type: str  # paragraph, list_item, image_desc, table_desc
    
    # 章节归属信息（核心）
    belongs_to_chapter: str  # "1", "2.1", "3.2.1"
    chapter_title: str
    chapter_level: int
    chapter_summary: str  # 所属章节的概要
    
    # 相关媒体信息
    related_images: List[Dict[str, Any]] = None
    related_tables: List[Dict[str, Any]] = None
    
    # 检索优化
    summary: Optional[str] = None  # 块摘要（可选）
    hypothetical_questions: List[str] = None  # 假设问题
    
    def __post_init__(self):
        if self.related_images is None:
            self.related_images = []
        if self.related_tables is None:
            self.related_tables = []
        if self.hypothetical_questions is None:
            self.hypothetical_questions = []

@dataclass
class ChapterSummary:
    """章节摘要 - 用于"大块喂养" """
    chapter_id: str  # "1", "2.1", "3.2.1"
    chapter_title: str
    level: int
    content_summary: str  # 章节概要
    total_chunks: int  # 包含的分块数
    chunk_ids: List[int]  # 包含的分块ID列表
    related_media_count: int  # 相关媒体数量

@dataclass
class IndexStructure:
    """检索优化的索引结构"""
    # 小块检索索引
    minimal_chunks: List[EnrichedChunk]  # 最小颗粒度分块，用于精确检索
    
    # 大块喂养索引
    chapter_summaries: List[ChapterSummary]  # 章节摘要，用于上下文提供
    
    # 问题索引
    hypothetical_questions: List[Dict[str, Any]]  # 假设问题索引，提升召回率
    
class MetadataEnricher:
    """
    元数据增强器
    支持"小块检索，大块喂养"模式：
    1. 为最小分块添加章节归属信息
    2. 生成章节摘要用于上下文提供
    3. 关联图片/表格到相应分块
    """
    
    def __init__(self, config: PDFProcessingConfig = None):
        self.config = config or PDFProcessingConfig()
        
        # 初始化LLM客户端（用于摘要和问题生成）
        self.llm_client = self._init_llm_client()
        
        logger.info("✅ 元数据增强器初始化完成")
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        try:
            if self.config.ai_content.default_llm_model.startswith('qwen'):
                return QwenClient(
                    model=self.config.ai_content.default_llm_model,
                    max_tokens=self.config.ai_content.max_context_length // 10,
                    max_retries=self.config.ai_content.max_retries,
                    enable_batch_mode=True
                )
            elif self.config.ai_content.default_llm_model.startswith('deepseek'):
                return DeepSeekClient()
            elif self.config.ai_content.default_llm_model.startswith('google/gemini'):
                return OpenRouterClient()
            else:
                logger.warning(f"不支持的LLM模型: {self.config.ai_content.default_llm_model}")
                return None
        except Exception as e:
            logger.error(f"LLM客户端初始化失败: {e}")
            return None
    
    def enrich_metadata(self, 
                       document_structure: DocumentStructure,
                       minimal_chunks: List[MinimalChunk],
                       processing_result: ProcessingResult) -> IndexStructure:
        """
        增强元数据并生成检索优化的索引结构
        
        Args:
            document_structure: 文档结构
            minimal_chunks: 最小分块列表
            processing_result: PDF处理结果
            
        Returns:
            IndexStructure: 检索优化的索引结构
        """
        logger.info(f"🔍 开始元数据增强，处理 {len(minimal_chunks)} 个最小分块")
        
        # 第一步：基础元数据增强
        enriched_chunks = self._enrich_basic_metadata(minimal_chunks, document_structure)
        
        # 第二步：关联图片和表格
        enriched_chunks = self._associate_media_with_chunks(enriched_chunks, processing_result, document_structure)
        
        # 第三步：生成假设问题（可选）
        if self.llm_client:
            enriched_chunks = self._generate_hypothetical_questions(enriched_chunks)
        
        # 第四步：生成章节摘要
        chapter_summaries = self._build_chapter_summaries(enriched_chunks, document_structure)
        
        # 第五步：构建问题索引
        hypothetical_questions = self._build_question_index(enriched_chunks)
        
        # 构建最终索引结构
        index_structure = IndexStructure(
            minimal_chunks=enriched_chunks,
            chapter_summaries=chapter_summaries,
            hypothetical_questions=hypothetical_questions
        )
        
        logger.info(f"✅ 元数据增强完成，生成 {len(enriched_chunks)} 个增强分块，{len(chapter_summaries)} 个章节摘要")
        
        return index_structure
    
    def _enrich_basic_metadata(self, 
                              minimal_chunks: List[MinimalChunk], 
                              document_structure: DocumentStructure) -> List[EnrichedChunk]:
        """增强基础元数据"""
        enriched_chunks = []
        
        # 创建章节ID到章节信息的映射
        chapter_map = {chapter.chapter_id: chapter for chapter in document_structure.toc}
        
        for chunk in minimal_chunks:
            chapter_info = chapter_map.get(chunk.belongs_to_chapter)
            chapter_summary = chapter_info.content_summary if chapter_info else ""
            
            enriched_chunk = EnrichedChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                chunk_type=chunk.chunk_type,
                belongs_to_chapter=chunk.belongs_to_chapter,
                chapter_title=chunk.chapter_title,
                chapter_level=chunk.chapter_level,
                chapter_summary=chapter_summary
            )
            
            enriched_chunks.append(enriched_chunk)
        
        return enriched_chunks
    
    def _associate_media_with_chunks(self, 
                                   enriched_chunks: List[EnrichedChunk],
                                   processing_result: ProcessingResult,
                                   document_structure: DocumentStructure) -> List[EnrichedChunk]:
        """关联图片和表格到相应的分块（通过章节归属）"""
        logger.info("🖼️ 关联图片和表格到分块")
        
        # 收集所有媒体并按内容匹配到章节
        all_images = processing_result.get_all_images()
        all_tables = processing_result.get_all_tables()
        
        # 为每个分块关联相关媒体
        for chunk in enriched_chunks:
            # 简化的关联策略：如果图片/表格的页面上下文包含分块内容的关键词，就关联
            chunk_keywords = self._extract_keywords(chunk.content)
            
            # 关联图片
            for image in all_images:
                if self._is_media_related_to_chunk(image.page_context, chunk_keywords, chunk.content):
                    image_info = {
                        "image_path": image.image_path,
                        "page_number": image.page_number,
                        "ai_description": image.ai_description
                    }
                    chunk.related_images.append(image_info)
            
            # 关联表格
            for table in all_tables:
                if self._is_media_related_to_chunk(table.page_context, chunk_keywords, chunk.content):
                    table_info = {
                        "table_path": table.table_path,
                        "page_number": table.page_number,
                        "ai_description": table.ai_description
                    }
                    chunk.related_tables.append(table_info)
        
        return enriched_chunks
    
    def _extract_keywords(self, content: str) -> List[str]:
        """从内容中提取关键词"""
        # 简单的关键词提取：去除常见词汇，保留长度>2的词
        common_words = {'的', '是', '在', '了', '和', '与', '或', '但', '因为', '所以', '这', '那', '这个', '那个'}
        words = content.replace('，', ' ').replace('。', ' ').replace('、', ' ').split()
        keywords = [word.strip() for word in words if len(word) > 2 and word not in common_words]
        return keywords[:10]  # 只取前10个关键词
    
    def _is_media_related_to_chunk(self, media_context: str, chunk_keywords: List[str], chunk_content: str) -> bool:
        """判断媒体是否与分块相关"""
        # 如果媒体上下文包含分块的关键词，或者有内容重叠，则认为相关
        if len(chunk_keywords) == 0:
            return False
        
        match_count = sum(1 for keyword in chunk_keywords if keyword in media_context)
        return match_count >= min(2, len(chunk_keywords) // 2)  # 至少匹配一半关键词
    
    def _generate_hypothetical_questions(self, enriched_chunks: List[EnrichedChunk]) -> List[EnrichedChunk]:
        """生成假设问题（可选，用于提升召回率）"""
        logger.info("🧠 生成假设问题")
        
        for chunk in enriched_chunks:
            # 只为较长的段落生成问题
            if chunk.chunk_type == "paragraph" and len(chunk.content) > 100:
                try:
                    questions_prompt = f"""
基于以下文本内容，生成2-3个假设问题，这些问题应该能够被该文本回答：

{chunk.content}

问题要求：
1. 使用自然的提问方式
2. 适合作为搜索查询
3. 每个问题一行，不需要编号

输出格式：
问题1
问题2
问题3
"""
                    
                    questions_response = self.llm_client.call_api(questions_prompt)
                    chunk.hypothetical_questions = [q.strip() for q in questions_response.split('\n') if q.strip()]
                    
                except Exception as e:
                    logger.error(f"生成假设问题失败: {e}")
                    chunk.hypothetical_questions = []
        
        return enriched_chunks
    
    def _build_chapter_summaries(self, 
                               enriched_chunks: List[EnrichedChunk],
                               document_structure: DocumentStructure) -> List[ChapterSummary]:
        """构建章节摘要（用于"大块喂养"）"""
        logger.info("🏗️ 构建章节摘要")
        
        chapter_summaries = []
        
        # 按章节分组分块
        chapters_dict = {}
        for chunk in enriched_chunks:
            chapter_id = chunk.belongs_to_chapter
            if chapter_id not in chapters_dict:
                chapters_dict[chapter_id] = []
            chapters_dict[chapter_id].append(chunk)
        
        # 为每个章节生成摘要
        for chapter_info in document_structure.toc:
            chapter_id = chapter_info.chapter_id
            chunks_in_chapter = chapters_dict.get(chapter_id, [])
            
            if chunks_in_chapter:
                # 统计相关媒体数量
                total_images = sum(len(chunk.related_images) for chunk in chunks_in_chapter)
                total_tables = sum(len(chunk.related_tables) for chunk in chunks_in_chapter)
                
                chapter_summary = ChapterSummary(
                    chapter_id=chapter_id,
                    chapter_title=chapter_info.title,
                    level=chapter_info.level,
                    content_summary=chapter_info.content_summary,
                    total_chunks=len(chunks_in_chapter),
                    chunk_ids=[chunk.chunk_id for chunk in chunks_in_chapter],
                    related_media_count=total_images + total_tables
                )
                
                chapter_summaries.append(chapter_summary)
        
        return chapter_summaries
    
    def _build_question_index(self, enriched_chunks: List[EnrichedChunk]) -> List[Dict[str, Any]]:
        """构建假设问题索引"""
        question_index = []
        
        for chunk in enriched_chunks:
            for question in chunk.hypothetical_questions:
                question_entry = {
                    'question': question,
                    'chunk_id': chunk.chunk_id,
                    'belongs_to_chapter': chunk.belongs_to_chapter,
                    'chapter_title': chunk.chapter_title
                }
                question_index.append(question_entry)
        
        return question_index
    
    def save_index_structure(self, index_structure: IndexStructure, output_path: str):
        """保存索引结构到文件"""
        try:
            # 转换为可序列化的格式
            serializable_data = {
                'minimal_chunks': [asdict(chunk) for chunk in index_structure.minimal_chunks],
                'chapter_summaries': [asdict(summary) for summary in index_structure.chapter_summaries],
                'hypothetical_questions': index_structure.hypothetical_questions
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📄 索引结构已保存到: {output_path}")
            
        except Exception as e:
            logger.error(f"保存索引结构失败: {e}")
    
    def load_index_structure(self, input_path: str) -> IndexStructure:
        """从文件加载索引结构"""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 重建对象
            minimal_chunks = []
            for chunk_data in data['minimal_chunks']:
                chunk = EnrichedChunk(**chunk_data)
                minimal_chunks.append(chunk)
            
            chapter_summaries = []
            for summary_data in data['chapter_summaries']:
                summary = ChapterSummary(**summary_data)
                chapter_summaries.append(summary)
            
            index_structure = IndexStructure(
                minimal_chunks=minimal_chunks,
                chapter_summaries=chapter_summaries,
                hypothetical_questions=data['hypothetical_questions']
            )
            
            logger.info(f"📄 索引结构已从文件加载: {input_path}")
            return index_structure
            
        except Exception as e:
            logger.error(f"加载索引结构失败: {e}")
            raise 