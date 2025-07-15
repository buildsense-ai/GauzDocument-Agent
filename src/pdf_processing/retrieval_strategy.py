#!/usr/bin/env python3
"""
检索策略实现
支持"小块检索，大块喂养"模式
实现最小块检索和完整章节返回
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import re

from .text_chunker import ChunkingResult, MinimalChunk, ChapterContent

@dataclass
class RetrievalQuery:
    """检索查询"""
    query_text: str
    top_k: int = 5
    chunk_types: Optional[List[str]] = None  # 限制检索的块类型
    chapter_filter: Optional[List[str]] = None  # 限制检索的章节
    
@dataclass
class ChunkMatch:
    """块匹配结果"""
    chunk: MinimalChunk
    score: float
    match_type: str  # exact, partial, semantic
    matched_text: str
    
@dataclass
class RetrievalResult:
    """检索结果"""
    query: RetrievalQuery
    chunk_matches: List[ChunkMatch]
    relevant_chapters: List[ChapterContent]
    chapter_scores: Dict[str, float]  # 章节ID -> 聚合得分
    total_matches: int


class RetrievalStrategy:
    """检索策略实现"""
    
    def __init__(self, chunking_result: ChunkingResult):
        self.chunking_result = chunking_result
        self.chunks_by_chapter = self._group_chunks_by_chapter()
        self.chapters_by_id = {ch.chapter_id: ch for ch in chunking_result.first_level_chapters}
        
    def _group_chunks_by_chapter(self) -> Dict[str, List[MinimalChunk]]:
        """按章节分组块"""
        groups = defaultdict(list)
        for chunk in self.chunking_result.minimal_chunks:
            groups[chunk.belongs_to_chapter].append(chunk)
        return dict(groups)
    
    def search(self, query: RetrievalQuery) -> RetrievalResult:
        """
        执行检索
        
        Args:
            query: 检索查询
            
        Returns:
            RetrievalResult: 检索结果
        """
        print(f"🔍 开始检索: '{query.query_text}'")
        
        # 1. 在最小块中检索
        chunk_matches = self._search_in_chunks(query)
        print(f"✅ 找到 {len(chunk_matches)} 个匹配的块")
        
        # 2. 计算章节得分
        chapter_scores = self._calculate_chapter_scores(chunk_matches)
        print(f"📊 涉及 {len(chapter_scores)} 个章节")
        
        # 3. 获取相关章节
        relevant_chapters = self._get_relevant_chapters(chapter_scores, query.top_k)
        print(f"📖 返回 {len(relevant_chapters)} 个完整章节")
        
        # 4. 构建结果
        result = RetrievalResult(
            query=query,
            chunk_matches=chunk_matches,
            relevant_chapters=relevant_chapters,
            chapter_scores=chapter_scores,
            total_matches=len(chunk_matches)
        )
        
        return result
    
    def _search_in_chunks(self, query: RetrievalQuery) -> List[ChunkMatch]:
        """在最小块中检索"""
        matches = []
        query_text = query.query_text.lower()
        
        for chunk in self.chunking_result.minimal_chunks:
            # 应用块类型过滤
            if query.chunk_types and chunk.chunk_type not in query.chunk_types:
                continue
                
            # 应用章节过滤
            if query.chapter_filter and chunk.belongs_to_chapter not in query.chapter_filter:
                continue
            
            # 检查匹配
            chunk_text = chunk.content.lower()
            match_score = 0
            match_type = "none"
            matched_text = ""
            
            # 1. 精确匹配
            if query_text in chunk_text:
                match_score = 1.0
                match_type = "exact"
                matched_text = query_text
            
            # 2. 部分匹配（查询词的子集）
            elif self._has_partial_match(query_text, chunk_text):
                match_score = 0.7
                match_type = "partial"
                matched_text = self._get_partial_match(query_text, chunk_text)
            
            # 3. 语义匹配（关键词重叠）
            elif self._has_semantic_match(query_text, chunk_text):
                match_score = 0.4
                match_type = "semantic"
                matched_text = self._get_semantic_match(query_text, chunk_text)
            
            # 根据块类型调整得分
            if match_score > 0:
                match_score = self._adjust_score_by_chunk_type(match_score, chunk.chunk_type)
                
                match = ChunkMatch(
                    chunk=chunk,
                    score=match_score,
                    match_type=match_type,
                    matched_text=matched_text
                )
                matches.append(match)
        
        # 按得分排序
        matches.sort(key=lambda x: x.score, reverse=True)
        
        return matches[:query.top_k * 3]  # 返回更多块用于章节聚合
    
    def _has_partial_match(self, query_text: str, chunk_text: str) -> bool:
        """检查是否有部分匹配"""
        query_words = query_text.split()
        if len(query_words) <= 1:
            return False
            
        # 至少匹配一半的词
        matched_words = sum(1 for word in query_words if word in chunk_text)
        return matched_words >= len(query_words) // 2
    
    def _get_partial_match(self, query_text: str, chunk_text: str) -> str:
        """获取部分匹配的文本"""
        query_words = query_text.split()
        matched_words = [word for word in query_words if word in chunk_text]
        return " ".join(matched_words)
    
    def _has_semantic_match(self, query_text: str, chunk_text: str) -> bool:
        """检查是否有语义匹配"""
        # 简单的关键词匹配
        query_words = set(query_text.split())
        chunk_words = set(chunk_text.split())
        
        # 计算交集
        intersection = query_words.intersection(chunk_words)
        return len(intersection) > 0
    
    def _get_semantic_match(self, query_text: str, chunk_text: str) -> str:
        """获取语义匹配的文本"""
        query_words = set(query_text.split())
        chunk_words = set(chunk_text.split())
        intersection = query_words.intersection(chunk_words)
        return " ".join(intersection)
    
    def _adjust_score_by_chunk_type(self, score: float, chunk_type: str) -> float:
        """根据块类型调整得分"""
        # 不同类型的块有不同的检索价值
        type_weights = {
            "title": 1.2,      # 标题块权重高
            "paragraph": 1.0,  # 段落块标准权重
            "list_item": 0.9,  # 列表项略低
            "image_desc": 0.7, # 图片描述较低
            "table_desc": 0.8  # 表格描述中等
        }
        
        weight = type_weights.get(chunk_type, 1.0)
        return score * weight
    
    def _calculate_chapter_scores(self, chunk_matches: List[ChunkMatch]) -> Dict[str, float]:
        """计算章节聚合得分"""
        chapter_scores = defaultdict(float)
        
        for match in chunk_matches:
            chapter_id = match.chunk.belongs_to_chapter
            
            # 聚合得分，考虑多个块的贡献
            chapter_scores[chapter_id] += match.score
            
            # 如果同一章节有多个匹配，给予bonus
            existing_matches = sum(1 for m in chunk_matches 
                                 if m.chunk.belongs_to_chapter == chapter_id)
            if existing_matches > 1:
                chapter_scores[chapter_id] += 0.1 * (existing_matches - 1)
        
        return dict(chapter_scores)
    
    def _get_relevant_chapters(self, chapter_scores: Dict[str, float], top_k: int) -> List[ChapterContent]:
        """获取相关章节"""
        # 按得分排序
        sorted_chapters = sorted(chapter_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 获取top_k章节
        relevant_chapters = []
        for chapter_id, score in sorted_chapters[:top_k]:
            if chapter_id in self.chapters_by_id:
                relevant_chapters.append(self.chapters_by_id[chapter_id])
        
        return relevant_chapters
    
    def format_retrieval_result(self, result: RetrievalResult) -> str:
        """格式化检索结果为可读文本"""
        output = []
        
        # 查询信息
        output.append(f"🔍 查询: {result.query.query_text}")
        output.append(f"📊 找到 {result.total_matches} 个匹配块，涉及 {len(result.relevant_chapters)} 个章节\n")
        
        # 章节结果
        for i, chapter in enumerate(result.relevant_chapters):
            chapter_score = result.chapter_scores.get(chapter.chapter_id, 0)
            output.append(f"📖 章节 {i+1}: {chapter.title} (得分: {chapter_score:.2f})")
            output.append(f"   章节ID: {chapter.chapter_id}")
            output.append(f"   字数: {chapter.word_count}")
            output.append(f"   内容预览: {chapter.content[:200]}...")
            output.append("")
        
        # 匹配块详情
        output.append("🔍 匹配块详情:")
        for i, match in enumerate(result.chunk_matches[:10]):  # 只显示前10个
            output.append(f"   {i+1}. {match.chunk.chunk_id} ({match.chunk.chunk_type})")
            output.append(f"      得分: {match.score:.2f} ({match.match_type})")
            output.append(f"      匹配文本: {match.matched_text}")
            output.append(f"      所属章节: {match.chunk.chapter_title}")
            output.append(f"      内容: {match.chunk.content[:100]}...")
            output.append("")
        
        return "\n".join(output)
    
    def save_retrieval_result(self, result: RetrievalResult, output_path: str):
        """保存检索结果"""
        # 转换为可序列化的格式
        result_dict = {
            "query": {
                "query_text": result.query.query_text,
                "top_k": result.query.top_k,
                "chunk_types": result.query.chunk_types,
                "chapter_filter": result.query.chapter_filter
            },
            "chunk_matches": [
                {
                    "chunk": {
                        "chunk_id": match.chunk.chunk_id,
                        "content": match.chunk.content,
                        "chunk_type": match.chunk.chunk_type,
                        "belongs_to_chapter": match.chunk.belongs_to_chapter,
                        "chapter_title": match.chunk.chapter_title,
                        "word_count": match.chunk.word_count
                    },
                    "score": match.score,
                    "match_type": match.match_type,
                    "matched_text": match.matched_text
                }
                for match in result.chunk_matches
            ],
            "relevant_chapters": [
                {
                    "chapter_id": chapter.chapter_id,
                    "title": chapter.title,
                    "content": chapter.content,
                    "word_count": chapter.word_count,
                    "has_images": chapter.has_images,
                    "has_tables": chapter.has_tables
                }
                for chapter in result.relevant_chapters
            ],
            "chapter_scores": result.chapter_scores,
            "total_matches": result.total_matches
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        
        print(f"💾 检索结果已保存到: {output_path}") 