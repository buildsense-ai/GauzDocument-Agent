#!/usr/bin/env python3
"""
章节摘要生成器
为每个章节生成详细的摘要信息
"""

import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from .metadata_schema import ChapterSummaryMetadata, create_content_id
from .text_chunker import ChunkingResult, ChapterContent
from src.qwen_client import QwenClient


class ChapterSummaryGenerator:
    """章节摘要生成器"""
    
    def __init__(self, model: str = "qwen-plus"):
        """
        初始化章节摘要生成器
        
        Args:
            model: 使用的AI模型
        """
        self.client = QwenClient(model=model, temperature=0.3)
        self.model = model
        
    def generate_chapter_summaries(self, 
                                 document_id: str,
                                 chunking_result: ChunkingResult,
                                 toc_data: Dict[str, Any],
                                 image_metadata: Optional[List[Dict[str, Any]]] = None,
                                 table_metadata: Optional[List[Dict[str, Any]]] = None,
                                 parallel_processing: bool = True) -> List[tuple[ChapterSummaryMetadata, str]]:
        """
        生成所有章节的摘要
        
        Args:
            document_id: 文档ID
            chunking_result: 分块结果
            toc_data: TOC数据
            image_metadata: 图片元数据
            table_metadata: 表格元数据
            parallel_processing: 是否并行处理
            
        Returns:
            List[tuple[ChapterSummaryMetadata, str]]: 章节摘要元数据和内容的列表
        """
        if not chunking_result.first_level_chapters:
            return []
            
        # 准备章节映射
        chapter_mapping = self._create_chapter_mapping(toc_data)
        
        # 统计每个章节的图片和表格数量
        chapter_media_stats = self._count_chapter_media(
            chunking_result.first_level_chapters,
            image_metadata or [],
            table_metadata or []
        )
        
        if parallel_processing:
            return self._generate_summaries_parallel(
                document_id, chunking_result.first_level_chapters,
                chapter_mapping, chapter_media_stats
            )
        else:
            return self._generate_summaries_sequential(
                document_id, chunking_result.first_level_chapters,
                chapter_mapping, chapter_media_stats
            )
    
    def _generate_summaries_parallel(self, 
                                   document_id: str,
                                   chapters: List[ChapterContent],
                                   chapter_mapping: Dict[str, Any],
                                   chapter_media_stats: Dict[str, Dict[str, int]]) -> List[tuple[ChapterSummaryMetadata, str]]:
        """并行生成章节摘要"""
        
        results = []
        
        # 使用线程池进行并行处理
        with ThreadPoolExecutor(max_workers=5) as executor:
            # 提交任务
            future_to_chapter = {
                executor.submit(
                    self._generate_single_chapter_summary,
                    document_id, chapter, chapter_mapping, chapter_media_stats
                ): chapter for chapter in chapters
            }
            
            # 收集结果
            for future in as_completed(future_to_chapter):
                chapter = future_to_chapter[future]
                try:
                    result = future.result()
                    results.append(result)
                    print(f"✅ 章节摘要生成完成: {chapter.title}")
                except Exception as e:
                    print(f"❌ 章节摘要生成失败: {chapter.title}, 错误: {e}")
                    # 创建基础摘要
                    basic_summary = self._create_basic_chapter_summary(
                        document_id, chapter, chapter_mapping, chapter_media_stats
                    )
                    results.append(basic_summary)
        
        # 按章节顺序排序
        results.sort(key=lambda x: x[0].chapter_order)
        
        return results
    
    def _generate_summaries_sequential(self,
                                     document_id: str,
                                     chapters: List[ChapterContent],
                                     chapter_mapping: Dict[str, Any],
                                     chapter_media_stats: Dict[str, Dict[str, int]]) -> List[tuple[ChapterSummaryMetadata, str]]:
        """顺序生成章节摘要"""
        
        results = []
        
        for chapter in chapters:
            try:
                result = self._generate_single_chapter_summary(
                    document_id, chapter, chapter_mapping, chapter_media_stats
                )
                results.append(result)
                print(f"✅ 章节摘要生成完成: {chapter.title}")
            except Exception as e:
                print(f"❌ 章节摘要生成失败: {chapter.title}, 错误: {e}")
                # 创建基础摘要
                basic_summary = self._create_basic_chapter_summary(
                    document_id, chapter, chapter_mapping, chapter_media_stats
                )
                results.append(basic_summary)
        
        return results
    
    def _generate_single_chapter_summary(self,
                                       document_id: str,
                                       chapter: ChapterContent,
                                       chapter_mapping: Dict[str, Any],
                                       chapter_media_stats: Dict[str, Dict[str, int]]) -> tuple[ChapterSummaryMetadata, str]:
        """生成单个章节的摘要"""
        
        start_time = time.time()
        
        # 获取章节信息
        chapter_info = chapter_mapping.get(chapter.chapter_id, {})
        media_stats = chapter_media_stats.get(chapter.chapter_id, {"image_count": 0, "table_count": 0})
        
        # 统计章节信息
        paragraph_count = self._count_paragraphs(chapter.content)
        text_chunk_count = self._count_text_chunks_in_chapter(chapter.chapter_id, chapter_mapping)
        
        # 生成摘要内容
        summary_content = self._generate_chapter_summary_content(chapter, chapter_info, media_stats)
        
        # 创建元数据
        processing_time = time.time() - start_time
        content_id = create_content_id(document_id, "chapter_summary", int(chapter.chapter_id))
        
        chapter_summary = ChapterSummaryMetadata(
            content_id=content_id,
            document_id=document_id,
            chapter_id=chapter.chapter_id,
            toc_id=chapter.chapter_id,  # 假设toc_id和chapter_id相同
            chapter_order=int(chapter.chapter_id) if chapter.chapter_id.isdigit() else 0,
            word_count=chapter.word_count,
            paragraph_count=paragraph_count,
            text_chunk_count=text_chunk_count,
            image_count=media_stats["image_count"],
            table_count=media_stats["table_count"],
            created_at=datetime.now()
        )
        
        return chapter_summary, summary_content
    
    def _create_basic_chapter_summary(self,
                                    document_id: str,
                                    chapter: ChapterContent,
                                    chapter_mapping: Dict[str, Any],
                                    chapter_media_stats: Dict[str, Dict[str, int]]) -> tuple[ChapterSummaryMetadata, str]:
        """创建基础章节摘要（当AI生成失败时使用）"""
        
        chapter_info = chapter_mapping.get(chapter.chapter_id, {})
        media_stats = chapter_media_stats.get(chapter.chapter_id, {"image_count": 0, "table_count": 0})
        
        # 统计信息
        paragraph_count = self._count_paragraphs(chapter.content)
        text_chunk_count = self._count_text_chunks_in_chapter(chapter.chapter_id, chapter_mapping)
        
        # 基础摘要内容
        summary_content = f"""
{chapter.title}

本章节包含{chapter.word_count}字的内容，共{paragraph_count}个段落。
章节内容涵盖了{chapter.title}相关的主要信息和技术要点。
{"" if media_stats["image_count"] == 0 else f"包含{media_stats['image_count']}张图片"}
{"" if media_stats["table_count"] == 0 else f"包含{media_stats['table_count']}个表格"}
"""
        
        # 创建元数据
        content_id = create_content_id(document_id, "chapter_summary", int(chapter.chapter_id))
        
        chapter_summary = ChapterSummaryMetadata(
            content_id=content_id,
            document_id=document_id,
            chapter_id=chapter.chapter_id,
            toc_id=chapter.chapter_id,
            chapter_order=int(chapter.chapter_id) if chapter.chapter_id.isdigit() else 0,
            word_count=chapter.word_count,
            paragraph_count=paragraph_count,
            text_chunk_count=text_chunk_count,
            image_count=media_stats["image_count"],
            table_count=media_stats["table_count"],
            created_at=datetime.now()
        )
        
        return chapter_summary, summary_content.strip()
    
    def _generate_chapter_summary_content(self,
                                        chapter: ChapterContent,
                                        chapter_info: Dict[str, Any],
                                        media_stats: Dict[str, int]) -> str:
        """生成章节摘要内容"""
        
        # 构建提示词
        prompt = self._build_chapter_summary_prompt(chapter, chapter_info, media_stats)
        
        try:
            # 调用AI生成摘要
            summary_content = self.client.generate_response(prompt)
            
            # 后处理摘要内容
            summary_content = self._post_process_summary(summary_content)
            
            return summary_content
            
        except Exception as e:
            print(f"⚠️ 生成章节摘要时发生错误: {e}")
            # 返回基础摘要
            return self._generate_basic_chapter_content(chapter, media_stats)
    
    def _build_chapter_summary_prompt(self,
                                    chapter: ChapterContent,
                                    chapter_info: Dict[str, Any],
                                    media_stats: Dict[str, int]) -> str:
        """构建章节摘要生成提示词"""
        
        # 截取章节内容（避免过长）
        content_preview = chapter.content[:1000] + "..." if len(chapter.content) > 1000 else chapter.content
        
        media_info = []
        if media_stats["image_count"] > 0:
            media_info.append(f"{media_stats['image_count']}张图片")
        if media_stats["table_count"] > 0:
            media_info.append(f"{media_stats['table_count']}个表格")
        
        media_text = f"，包含{' and '.join(media_info)}" if media_info else ""
        
        prompt = f"""
请为以下章节生成一个详细的摘要：

## 章节信息
- 章节标题: {chapter.title}
- 字数: {chapter.word_count}字
- 媒体内容: {media_text}

## 章节内容
{content_preview}

## 要求
请生成一个150-200字的章节摘要，包含以下内容：
1. 章节的主要主题和目标
2. 核心内容要点（3-5个关键点）
3. 重要的技术细节或方法
4. 章节在整个文档中的作用

请用专业、简洁的语言，确保摘要准确反映章节的核心内容。
"""
        
        return prompt
    
    def _post_process_summary(self, summary_content: str) -> str:
        """后处理摘要内容"""
        # 移除多余的空行
        lines = [line.strip() for line in summary_content.split('\n') if line.strip()]
        return '\n'.join(lines)
    
    def _generate_basic_chapter_content(self, chapter: ChapterContent, media_stats: Dict[str, int]) -> str:
        """生成基础章节内容"""
        media_info = []
        if media_stats["image_count"] > 0:
            media_info.append(f"{media_stats['image_count']}张图片")
        if media_stats["table_count"] > 0:
            media_info.append(f"{media_stats['table_count']}个表格")
        
        media_text = f"，包含{' and '.join(media_info)}" if media_info else ""
        
        return f"""
{chapter.title}

本章节包含{chapter.word_count}字的详细内容{media_text}。
章节内容涵盖了{chapter.title}相关的主要信息和技术要点，
为项目的实施提供了重要的指导和参考。
"""
    
    def _create_chapter_mapping(self, toc_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建章节映射"""
        chapter_mapping = {}
        
        for item in toc_data.get("toc_items", []):
            if item.get("level") == 1:  # 只处理第一级章节
                chapter_mapping[item["id"]] = {
                    "title": item["title"],
                    "order": int(item["id"]) if item["id"].isdigit() else 0
                }
        
        return chapter_mapping
    
    def _count_chapter_media(self,
                           chapters: List[ChapterContent],
                           image_metadata: List[Dict[str, Any]],
                           table_metadata: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        """统计每个章节的图片和表格数量"""
        
        chapter_media_stats = {}
        
        for chapter in chapters:
            chapter_id = chapter.chapter_id
            
            # 统计图片数量
            image_count = sum(1 for img in image_metadata if img.get("chapter_id") == chapter_id)
            
            # 统计表格数量
            table_count = sum(1 for tbl in table_metadata if tbl.get("chapter_id") == chapter_id)
            
            chapter_media_stats[chapter_id] = {
                "image_count": image_count,
                "table_count": table_count
            }
        
        return chapter_media_stats
    
    def _count_paragraphs(self, content: str) -> int:
        """统计段落数量"""
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        return len(paragraphs)
    
    def _count_text_chunks_in_chapter(self, chapter_id: str, chapter_mapping: Dict[str, Any]) -> int:
        """统计章节中的文本块数量"""
        # 这里暂时返回估算值，实际应该从chunking_result中获取
        return 10  # 默认值
    
    def save_chapter_summaries(self, 
                             chapter_summaries: List[tuple[ChapterSummaryMetadata, str]], 
                             output_dir: str):
        """
        保存章节摘要
        
        Args:
            chapter_summaries: 章节摘要列表
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存所有章节摘要元数据
        all_metadata = []
        all_content = {}
        
        for chapter_summary, summary_content in chapter_summaries:
            # 转换为可序列化格式
            metadata_dict = {
                "content_id": chapter_summary.content_id,
                "document_id": chapter_summary.document_id,
                "chapter_id": chapter_summary.chapter_id,
                "toc_id": chapter_summary.toc_id,
                "chapter_order": chapter_summary.chapter_order,
                "word_count": chapter_summary.word_count,
                "paragraph_count": chapter_summary.paragraph_count,
                "text_chunk_count": chapter_summary.text_chunk_count,
                "image_count": chapter_summary.image_count,
                "table_count": chapter_summary.table_count,
                "created_at": chapter_summary.created_at.isoformat()
            }
            
            all_metadata.append(metadata_dict)
            all_content[chapter_summary.chapter_id] = summary_content
        
        # 保存元数据
        metadata_file = os.path.join(output_dir, "chapter_summaries_metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, ensure_ascii=False, indent=2)
        
        # 保存摘要内容
        content_file = os.path.join(output_dir, "chapter_summaries_content.json")
        with open(content_file, 'w', encoding='utf-8') as f:
            json.dump(all_content, f, ensure_ascii=False, indent=2)
        
        print(f"📚 章节摘要已保存:")
        print(f"   - 元数据: {metadata_file}")
        print(f"   - 内容: {content_file}")
        print(f"   - 章节数量: {len(chapter_summaries)}") 