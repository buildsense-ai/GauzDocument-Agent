#!/usr/bin/env python3
"""
问题生成器（可选组件）
基于文本chunk生成派生问题，提高检索多样性
"""

import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from .metadata_schema import DerivedQuestionMetadata, create_content_id
from .text_chunker import ChunkingResult, MinimalChunk
from src.qwen_client import QwenClient


class QuestionGenerator:
    """问题生成器"""
    
    def __init__(self, model: str = "qwen-turbo"):
        """
        初始化问题生成器
        
        Args:
            model: 使用的AI模型，默认使用轻量模型
        """
        self.client = QwenClient(model=model, temperature=0.7)  # 较高温度增加多样性
        self.model = model
        
    def generate_questions_from_chunks(self,
                                     document_id: str,
                                     chunking_result: ChunkingResult,
                                     chapter_mapping: Dict[str, Any],
                                     questions_per_chunk: int = 2,
                                     parallel_processing: bool = True) -> List[Tuple[DerivedQuestionMetadata, str]]:
        """
        从文本chunks生成派生问题
        
        Args:
            document_id: 文档ID
            chunking_result: 分块结果
            chapter_mapping: 章节映射
            questions_per_chunk: 每个chunk生成的问题数量
            parallel_processing: 是否并行处理
            
        Returns:
            List[Tuple[DerivedQuestionMetadata, str]]: 问题元数据和问题内容的列表
        """
        
        # 过滤出适合生成问题的chunks
        suitable_chunks = self._filter_suitable_chunks(chunking_result.minimal_chunks)
        
        print(f"📝 找到 {len(suitable_chunks)} 个适合生成问题的chunks")
        
        if not suitable_chunks:
            return []
        
        if parallel_processing:
            return self._generate_questions_parallel(
                document_id, suitable_chunks, chapter_mapping, questions_per_chunk
            )
        else:
            return self._generate_questions_sequential(
                document_id, suitable_chunks, chapter_mapping, questions_per_chunk
            )
    
    def _filter_suitable_chunks(self, chunks: List[MinimalChunk]) -> List[MinimalChunk]:
        """过滤出适合生成问题的chunks"""
        
        suitable_chunks = []
        
        for chunk in chunks:
            # 过滤条件：
            # 1. 文本长度适中（不太短也不太长）
            # 2. 是段落类型（不是标题或列表项）
            # 3. 包含足够的信息内容
            
            if (chunk.chunk_type == "paragraph" and 
                50 <= chunk.word_count <= 300 and
                self._has_substantial_content(chunk.content)):
                suitable_chunks.append(chunk)
        
        return suitable_chunks
    
    def _has_substantial_content(self, content: str) -> bool:
        """检查chunk是否包含足够的实质内容"""
        
        # 简单的内容质量检查
        if not content or len(content.strip()) < 100:
            return False
            
        # 检查是否包含技术术语或专业词汇
        technical_keywords = ["技术", "方法", "设计", "分析", "评估", "实施", "标准", "规范", "要求"]
        
        content_lower = content.lower()
        keyword_count = sum(1 for keyword in technical_keywords if keyword in content_lower)
        
        return keyword_count >= 1
    
    def _generate_questions_parallel(self,
                                   document_id: str,
                                   chunks: List[MinimalChunk],
                                   chapter_mapping: Dict[str, Any],
                                   questions_per_chunk: int) -> List[Tuple[DerivedQuestionMetadata, str]]:
        """并行生成问题"""
        
        all_questions = []
        
        # 使用线程池进行并行处理
        with ThreadPoolExecutor(max_workers=8) as executor:
            # 提交任务
            future_to_chunk = {
                executor.submit(
                    self._generate_questions_for_chunk,
                    document_id, chunk, chapter_mapping, questions_per_chunk
                ): chunk for chunk in chunks
            }
            
            # 收集结果
            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    questions = future.result()
                    all_questions.extend(questions)
                    print(f"✅ 为chunk生成问题完成: {len(questions)}个问题")
                except Exception as e:
                    print(f"❌ 为chunk生成问题失败: {e}")
        
        print(f"📊 总共生成 {len(all_questions)} 个问题")
        return all_questions
    
    def _generate_questions_sequential(self,
                                     document_id: str,
                                     chunks: List[MinimalChunk],
                                     chapter_mapping: Dict[str, Any],
                                     questions_per_chunk: int) -> List[Tuple[DerivedQuestionMetadata, str]]:
        """顺序生成问题"""
        
        all_questions = []
        
        for chunk in chunks:
            try:
                questions = self._generate_questions_for_chunk(
                    document_id, chunk, chapter_mapping, questions_per_chunk
                )
                all_questions.extend(questions)
                print(f"✅ 为chunk生成问题完成: {len(questions)}个问题")
            except Exception as e:
                print(f"❌ 为chunk生成问题失败: {e}")
        
        print(f"📊 总共生成 {len(all_questions)} 个问题")
        return all_questions
    
    def _generate_questions_for_chunk(self,
                                    document_id: str,
                                    chunk: MinimalChunk,
                                    chapter_mapping: Dict[str, Any],
                                    questions_per_chunk: int) -> List[Tuple[DerivedQuestionMetadata, str]]:
        """为单个chunk生成问题"""
        
        chapter_info = chapter_mapping.get(chunk.belongs_to_chapter, {})
        
        # 生成问题
        questions = self._generate_questions_content(chunk, chapter_info, questions_per_chunk)
        
        # 创建元数据
        result = []
        for i, question in enumerate(questions):
            content_id = create_content_id(document_id, "derived_question", 
                                         int(f"{chunk.belongs_to_chapter}{i+1:03d}"))
            
            # 推断问题分类
            category = self._infer_question_category(question, chapter_info)
            
            question_metadata = DerivedQuestionMetadata(
                content_id=content_id,
                document_id=document_id,
                chapter_id=chunk.belongs_to_chapter,
                question_category=category,
                generated_from_chunk_id=chunk.chunk_id,
                created_at=datetime.now()
            )
            
            result.append((question_metadata, question))
        
        return result
    
    def _generate_questions_content(self,
                                  chunk: MinimalChunk,
                                  chapter_info: Dict[str, Any],
                                  questions_per_chunk: int) -> List[str]:
        """生成问题内容"""
        
        # 构建提示词
        prompt = self._build_question_generation_prompt(chunk, chapter_info, questions_per_chunk)
        
        try:
            # 调用AI生成问题
            response = self.client.generate_response(prompt)
            
            # 解析生成的问题
            questions = self._parse_generated_questions(response)
            
            return questions[:questions_per_chunk]  # 限制问题数量
            
        except Exception as e:
            print(f"⚠️ 生成问题时发生错误: {e}")
            # 返回基础问题
            return self._generate_basic_questions(chunk, chapter_info)
    
    def _build_question_generation_prompt(self,
                                        chunk: MinimalChunk,
                                        chapter_info: Dict[str, Any],
                                        questions_per_chunk: int) -> str:
        """构建问题生成提示词"""
        
        chapter_title = chapter_info.get("title", "未知章节")
        
        prompt = f"""
基于以下文本内容，生成{questions_per_chunk}个相关的问题。这些问题应该能够帮助用户更好地理解和检索文档内容。

## 章节信息
- 章节标题: {chapter_title}
- 内容类型: {chunk.chunk_type}

## 文本内容
{chunk.content}

## 要求
1. 生成{questions_per_chunk}个不同类型的问题
2. 问题应该涵盖：
   - 核心概念问题（什么是...？）
   - 方法问题（如何...？）
   - 原因问题（为什么...？）
   - 应用问题（在什么情况下...？）
3. 问题应该具体、清晰、实用
4. 每个问题独占一行，以"Q: "开头

示例格式：
Q: 什么是...？
Q: 如何...？
"""
        
        return prompt
    
    def _parse_generated_questions(self, response: str) -> List[str]:
        """解析生成的问题"""
        
        questions = []
        
        for line in response.split('\n'):
            line = line.strip()
            if line.startswith('Q: '):
                question = line[3:].strip()  # 移除"Q: "前缀
                if question and question.endswith('？'):
                    questions.append(question)
        
        return questions
    
    def _generate_basic_questions(self, chunk: MinimalChunk, chapter_info: Dict[str, Any]) -> List[str]:
        """生成基础问题（当AI生成失败时使用）"""
        
        chapter_title = chapter_info.get("title", "相关内容")
        
        # 提取关键词
        keywords = self._extract_keywords(chunk.content)
        
        basic_questions = []
        
        if keywords:
            basic_questions.append(f"什么是{keywords[0]}？")
            if len(keywords) > 1:
                basic_questions.append(f"如何理解{keywords[1]}？")
        
        basic_questions.append(f"{chapter_title}包含哪些主要内容？")
        
        return basic_questions[:2]  # 最多返回2个基础问题
    
    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        
        # 简单的关键词提取（可以进一步优化）
        common_words = {"的", "是", "在", "和", "与", "或", "但", "而", "也", "都", "有", "为", "了", "等", "及"}
        
        words = content.replace("，", " ").replace("。", " ").replace("；", " ").split()
        
        keywords = []
        for word in words:
            if len(word) >= 2 and word not in common_words:
                keywords.append(word)
        
        return keywords[:5]  # 返回前5个关键词
    
    def _infer_question_category(self, question: str, chapter_info: Dict[str, Any]) -> str:
        """推断问题分类"""
        
        chapter_title = chapter_info.get("title", "").lower()
        question_lower = question.lower()
        
        # 基于问题内容和章节标题推断分类
        if "什么" in question_lower or "定义" in question_lower:
            return "概念定义"
        elif "如何" in question_lower or "怎样" in question_lower:
            return "方法流程"
        elif "为什么" in question_lower or "原因" in question_lower:
            return "原因分析"
        elif "设计" in chapter_title or "方案" in chapter_title:
            return "设计方案"
        elif "评估" in chapter_title or "分析" in chapter_title:
            return "评估分析"
        elif "标准" in chapter_title or "规范" in chapter_title:
            return "标准规范"
        else:
            return "通用内容"
    
    def save_derived_questions(self, 
                             questions: List[Tuple[DerivedQuestionMetadata, str]], 
                             output_dir: str):
        """
        保存派生问题
        
        Args:
            questions: 问题列表
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存问题元数据
        all_metadata = []
        all_content = {}
        
        for question_metadata, question_content in questions:
            # 转换为可序列化格式
            metadata_dict = {
                "content_id": question_metadata.content_id,
                "document_id": question_metadata.document_id,
                "chapter_id": question_metadata.chapter_id,
                "question_category": question_metadata.question_category,
                "generated_from_chunk_id": question_metadata.generated_from_chunk_id,
                "created_at": question_metadata.created_at.isoformat()
            }
            
            all_metadata.append(metadata_dict)
            all_content[question_metadata.content_id] = question_content
        
        # 保存元数据
        metadata_file = os.path.join(output_dir, "derived_questions_metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, ensure_ascii=False, indent=2)
        
        # 保存问题内容
        content_file = os.path.join(output_dir, "derived_questions_content.json")
        with open(content_file, 'w', encoding='utf-8') as f:
            json.dump(all_content, f, ensure_ascii=False, indent=2)
        
        # 按分类统计
        category_stats = {}
        for metadata, _ in questions:
            category = metadata.question_category
            category_stats[category] = category_stats.get(category, 0) + 1
        
        print(f"❓ 派生问题已保存:")
        print(f"   - 元数据: {metadata_file}")
        print(f"   - 内容: {content_file}")
        print(f"   - 总问题数: {len(questions)}")
        print(f"   - 分类统计: {category_stats}")
    
    def generate_questions_by_category(self, 
                                     document_id: str,
                                     chunking_result: ChunkingResult,
                                     chapter_mapping: Dict[str, Any],
                                     target_categories: List[str]) -> List[Tuple[DerivedQuestionMetadata, str]]:
        """
        按指定分类生成问题
        
        Args:
            document_id: 文档ID
            chunking_result: 分块结果
            chapter_mapping: 章节映射
            target_categories: 目标分类列表
            
        Returns:
            List[Tuple[DerivedQuestionMetadata, str]]: 问题列表
        """
        
        # 根据章节标题筛选相关chunks
        relevant_chunks = []
        
        for chunk in chunking_result.minimal_chunks:
            chapter_info = chapter_mapping.get(chunk.belongs_to_chapter, {})
            chapter_title = chapter_info.get("title", "").lower()
            
            # 检查章节是否属于目标分类
            if any(category in chapter_title for category in target_categories):
                relevant_chunks.append(chunk)
        
        print(f"📋 找到 {len(relevant_chunks)} 个与目标分类相关的chunks")
        
        if not relevant_chunks:
            return []
        
        # 生成问题
        return self._generate_questions_parallel(
            document_id, relevant_chunks, chapter_mapping, 3  # 每个chunk生成3个问题
        ) 