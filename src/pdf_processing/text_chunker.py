#!/usr/bin/env python3
"""
文本分块器 - 基于TOC的智能文本分块
支持第一级章节切割和最小块分割
实现"小块检索，大块喂养"模式
使用AI智能分块器替代正则表达式段落切割
"""

import json
import re
import os
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# 导入AI分块器
from .ai_chunker import AIChunker, MinimalChunk as AIMinimalChunk

@dataclass
class ChapterContent:
    """第一级章节内容"""
    chapter_id: str
    title: str
    content: str
    start_pos: int
    end_pos: int
    word_count: int
    has_images: bool
    has_tables: bool
    
@dataclass
class MinimalChunk:
    """最小颗粒度分块"""
    chunk_id: str
    content: str
    chunk_type: str  # title, paragraph, list_item, image_desc, table_desc
    belongs_to_chapter: str
    chapter_title: str
    start_pos: int
    end_pos: int
    word_count: int
    
@dataclass
class ChunkingResult:
    """分块结果"""
    first_level_chapters: List[ChapterContent]
    minimal_chunks: List[MinimalChunk]
    total_chapters: int
    total_chunks: int
    processing_metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式，便于JSON序列化
        
        Returns:
            Dict[str, Any]: 包含所有分块信息的字典
        """
        return {
            "first_level_chapters": [
                {
                    "chapter_id": chapter.chapter_id,
                    "title": chapter.title,
                    "content": chapter.content,
                    "start_pos": chapter.start_pos,
                    "end_pos": chapter.end_pos,
                    "word_count": chapter.word_count,
                    "has_images": chapter.has_images,
                    "has_tables": chapter.has_tables
                }
                for chapter in self.first_level_chapters
            ],
            "minimal_chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "chunk_type": chunk.chunk_type,
                    "belongs_to_chapter": chunk.belongs_to_chapter,
                    "chapter_title": chunk.chapter_title,
                    "start_pos": chunk.start_pos,
                    "end_pos": chunk.end_pos,
                    "word_count": chunk.word_count
                }
                for chunk in self.minimal_chunks
            ],
            "total_chapters": self.total_chapters,
            "total_chunks": self.total_chunks,
            "processing_metadata": self.processing_metadata
        }


class TextChunker:
    """文本分块器"""
    
    def __init__(self, use_ai_chunker: bool = True, ai_model: str = "qwen-turbo"):
        """
        初始化文本分块器
        
        Args:
            use_ai_chunker: 是否使用AI分块器
            ai_model: AI分块器使用的模型
        """
        self.use_ai_chunker = use_ai_chunker
        self.ai_chunker = AIChunker(model=ai_model) if use_ai_chunker else None
        
        self.processing_metadata = {
            "chunking_method": "toc_based_with_ai" if use_ai_chunker else "toc_based",
            "support_retrieval": True,
            "chunk_strategy": "minimal_chunks_with_full_chapters",
            "ai_model": ai_model if use_ai_chunker else None
        }
    
    def chunk_text_with_toc(self, full_text: str, toc_result: Dict[str, Any]) -> ChunkingResult:
        """
        基于TOC结果进行文本分块
        
        Args:
            full_text: 完整文本
            toc_result: TOC提取结果
            
        Returns:
            ChunkingResult: 分块结果
        """
        print("🔪 开始基于TOC的文本分块...")
        
        # 获取第一级章节
        first_level_toc = [item for item in toc_result['toc'] if item['level'] == 1]
        print(f"📖 找到 {len(first_level_toc)} 个第一级章节")
        
        # 1. 切割第一级章节
        first_level_chapters = self._cut_first_level_chapters(full_text, first_level_toc)
        print(f"✅ 第一级章节切割完成: {len(first_level_chapters)} 个章节")
        
        # 2. 生成最小块
        minimal_chunks = self._generate_minimal_chunks(first_level_chapters)
        print(f"✅ 最小块生成完成: {len(minimal_chunks)} 个块")
        
        # 3. 构建结果
        result = ChunkingResult(
            first_level_chapters=first_level_chapters,
            minimal_chunks=minimal_chunks,
            total_chapters=len(first_level_chapters),
            total_chunks=len(minimal_chunks),
            processing_metadata=self.processing_metadata
        )
        
        return result
    
    def _cut_first_level_chapters(self, full_text: str, first_level_toc: List[Dict]) -> List[ChapterContent]:
        """
        切割第一级章节
        
        Args:
            full_text: 完整文本
            first_level_toc: 第一级TOC项目
            
        Returns:
            List[ChapterContent]: 章节内容列表
        """
        chapters = []
        
        for i, toc_item in enumerate(first_level_toc):
            chapter_id = toc_item['id']
            title = toc_item['title']
            start_text = toc_item['start_text']
            
            # 使用start_text查找章节开始位置
            start_pos = self._find_chapter_start(full_text, start_text)
            
            if start_pos == -1:
                print(f"⚠️ 无法找到章节 '{title}' 的开始位置")
                continue
                
            # 确定章节结束位置
            if i + 1 < len(first_level_toc):
                next_start_text = first_level_toc[i + 1]['start_text']
                end_pos = self._find_chapter_start(full_text, next_start_text)
                if end_pos == -1:
                    end_pos = len(full_text)
            else:
                end_pos = len(full_text)
            
            # 提取章节内容
            content = full_text[start_pos:end_pos].strip()
            
            # 检查是否包含图片和表格
            has_images = "[图片:" in content
            has_tables = "[表格:" in content or "表" in content
            
            chapter = ChapterContent(
                chapter_id=chapter_id,
                title=title,
                content=content,
                start_pos=start_pos,
                end_pos=end_pos,
                word_count=len(content),
                has_images=has_images,
                has_tables=has_tables
            )
            
            chapters.append(chapter)
            
        return chapters
    
    def _find_chapter_start(self, full_text: str, start_text: str) -> int:
        """
        查找章节开始位置
        
        Args:
            full_text: 完整文本
            start_text: 开始文本片段
            
        Returns:
            int: 位置索引，-1表示未找到
        """
        # 预处理start_text，去除换行和多余空格
        cleaned_start_text = re.sub(r'\s+', ' ', start_text).strip()
        
        # 1. 精确匹配
        pos = full_text.find(cleaned_start_text)
        if pos != -1:
            return pos
            
        # 2. 尝试模糊匹配 - 分词匹配
        words = cleaned_start_text.split()
        if len(words) > 3:
            # 尝试前3个词
            partial_text = ' '.join(words[:3])
            pos = full_text.find(partial_text)
            if pos != -1:
                return pos
        
        # 3. 尝试更宽松的匹配 - 去掉标点符号
        import string
        cleaned_text = cleaned_start_text.translate(str.maketrans('', '', string.punctuation))
        pos = full_text.find(cleaned_text)
        if pos != -1:
            return pos
            
        # 4. 尝试关键词匹配
        # 如果start_text包含关键词，尝试单独匹配关键词
        keywords = ['总结', '方案', '监测', '项目', '工程', '分析', '措施', '建议']
        for keyword in keywords:
            if keyword in cleaned_start_text and keyword in full_text:
                # 找到关键词后，尝试找到包含更多上下文的位置
                keyword_positions = []
                start_pos = 0
                while True:
                    pos = full_text.find(keyword, start_pos)
                    if pos == -1:
                        break
                    keyword_positions.append(pos)
                    start_pos = pos + 1
                
                # 对每个关键词位置，检查上下文是否匹配
                for pos in keyword_positions:
                    # 取关键词前后20个字符作为上下文
                    context_start = max(0, pos - 20)
                    context_end = min(len(full_text), pos + len(keyword) + 20)
                    context = full_text[context_start:context_end]
                    
                    # 检查上下文是否包含start_text中的其他词
                    word_matches = sum(1 for word in words if word in context)
                    if word_matches >= min(2, len(words) // 2):  # 至少匹配一半的词
                        return pos
        
        # 5. 最后的回退：使用正则表达式进行宽松匹配
        try:
            # 只匹配前10个字符，允许一些变化
            pattern = re.escape(cleaned_start_text[:10])
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                return match.start()
        except:
            pass
            
        return -1
    
    def _generate_minimal_chunks(self, chapters: List[ChapterContent]) -> List[MinimalChunk]:
        """
        生成最小颗粒度分块
        
        Args:
            chapters: 章节内容列表
            
        Returns:
            List[MinimalChunk]: 最小块列表
        """
        if self.use_ai_chunker and self.ai_chunker:
            # 使用AI分块器进行异步分块
            return self._generate_chunks_with_ai(chapters)
        else:
            # 使用传统的正则分块
            return self._generate_chunks_with_regex(chapters)
    
    def _generate_chunks_with_ai(self, chapters: List[ChapterContent]) -> List[MinimalChunk]:
        """使用AI分块器生成分块"""
        print("🤖 使用AI分块器进行智能分块...")
        
        if not self.ai_chunker:
            print("❌ AI分块器未初始化，回退到正则分块")
            return self._generate_chunks_with_regex(chapters)
        
        # 准备章节数据
        chapter_data = []
        for chapter in chapters:
            chapter_data.append({
                'chapter_id': chapter.chapter_id,
                'title': chapter.title,
                'content': chapter.content
            })
        
        # 使用AI分块器进行批量异步处理
        try:
            ai_chunks = asyncio.run(self.ai_chunker.chunk_chapters_batch(chapter_data))
            print(f"✅ AI分块完成，共生成 {len(ai_chunks)} 个分块")
            
            # 转换为本地MinimalChunk格式
            chunks = []
            for ai_chunk in ai_chunks:
                chunk = MinimalChunk(
                    chunk_id=ai_chunk.chunk_id,
                    content=ai_chunk.content,
                    chunk_type=ai_chunk.chunk_type,
                    belongs_to_chapter=ai_chunk.belongs_to_chapter,
                    chapter_title=ai_chunk.chapter_title,
                    start_pos=ai_chunk.start_pos,
                    end_pos=ai_chunk.end_pos,
                    word_count=ai_chunk.word_count
                )
                chunks.append(chunk)
            
            return chunks
        except Exception as e:
            print(f"❌ AI分块失败，回退到正则分块: {e}")
            return self._generate_chunks_with_regex(chapters)
    
    def _generate_chunks_with_regex(self, chapters: List[ChapterContent]) -> List[MinimalChunk]:
        """使用正则表达式生成分块（回退方案）"""
        print("📝 使用正则表达式进行传统分块...")
        
        minimal_chunks = []
        chunk_counter = 0
        
        for chapter in chapters:
            # 为每个章节生成最小块
            chapter_chunks = self._chunk_single_chapter(chapter, chunk_counter)
            minimal_chunks.extend(chapter_chunks)
            chunk_counter += len(chapter_chunks)
            
        return minimal_chunks
    
    def _chunk_single_chapter(self, chapter: ChapterContent, start_chunk_id: int) -> List[MinimalChunk]:
        """
        对单个章节进行最小块分割
        
        Args:
            chapter: 章节内容
            start_chunk_id: 起始块ID
            
        Returns:
            List[MinimalChunk]: 章节内的最小块列表
        """
        chunks = []
        content = chapter.content
        chunk_id = start_chunk_id
        
        # 1. 标题块 - 章节标题 + 开头1-2段
        title_chunk = self._create_title_chunk(chapter, chunk_id)
        if title_chunk:
            chunks.append(title_chunk)
            chunk_id += 1
        
        # 2. 段落块 - 将内容分成段落
        paragraphs = self._split_into_paragraphs(content)
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
                
            # 判断段落类型
            chunk_type = self._determine_chunk_type(paragraph)
            
            # 创建最小块
            chunk = MinimalChunk(
                chunk_id=f"{chapter.chapter_id}_{chunk_id}",
                content=paragraph.strip(),
                chunk_type=chunk_type,
                belongs_to_chapter=chapter.chapter_id,
                chapter_title=chapter.title,
                start_pos=0,  # 相对于章节的位置
                end_pos=len(paragraph),
                word_count=len(paragraph.strip())
            )
            
            chunks.append(chunk)
            chunk_id += 1
            
        return chunks
    
    def _create_title_chunk(self, chapter: ChapterContent, chunk_id: int) -> Optional[MinimalChunk]:
        """
        创建标题块
        
        Args:
            chapter: 章节内容
            chunk_id: 块ID
            
        Returns:
            Optional[MinimalChunk]: 标题块
        """
        # 获取章节开头的内容（标题 + 前1-2段）
        lines = chapter.content.split('\n')
        title_content_lines = []
        
        # 添加标题
        title_content_lines.append(chapter.title)
        
        # 添加前几行内容
        for line in lines[:3]:  # 取前3行
            if line.strip() and not line.startswith('[图片:') and not line.startswith('[表格:'):
                title_content_lines.append(line.strip())
        
        title_content = '\n'.join(title_content_lines)
        
        if len(title_content) < 50:  # 如果太短，返回None
            return None
            
        return MinimalChunk(
            chunk_id=f"{chapter.chapter_id}_{chunk_id}",
            content=title_content,
            chunk_type="title",
            belongs_to_chapter=chapter.chapter_id,
            chapter_title=chapter.title,
            start_pos=0,
            end_pos=len(title_content),
            word_count=len(title_content)
        )
    
    def _split_into_paragraphs(self, content: str) -> List[str]:
        """
        将内容分割为段落
        
        Args:
            content: 内容文本
            
        Returns:
            List[str]: 段落列表
        """
        # 按双换行分割段落
        paragraphs = content.split('\n\n')
        
        # 进一步处理，确保每个段落都有合适的长度
        processed_paragraphs = []
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            # 如果段落太长，进一步分割
            if len(paragraph) > 1000:
                # 按句号分割
                sentences = paragraph.split('。')
                current_chunk = ""
                
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) > 500:
                        if current_chunk:
                            processed_paragraphs.append(current_chunk + '。')
                        current_chunk = sentence
                    else:
                        current_chunk += sentence + '。'
                
                if current_chunk:
                    processed_paragraphs.append(current_chunk)
            else:
                processed_paragraphs.append(paragraph)
        
        return processed_paragraphs
    
    def _determine_chunk_type(self, paragraph: str) -> str:
        """
        确定段落类型
        
        Args:
            paragraph: 段落内容
            
        Returns:
            str: 段落类型
        """
        paragraph = paragraph.strip()
        
        # 图片描述
        if paragraph.startswith('[图片:') or 'Error: An unexpected error occurred while fetching the image description' in paragraph:
            return "image_desc"
            
        # 表格描述
        if paragraph.startswith('[表格:') or '表' in paragraph[:50]:
            return "table_desc"
            
        # 列表项
        if paragraph.startswith('- ') or paragraph.startswith('• ') or re.match(r'^\d+\.', paragraph):
            return "list_item"
            
        # 普通段落
        return "paragraph"
    
    def save_chunking_result(self, result: ChunkingResult, output_dir: str):
        """
        保存分块结果
        
        Args:
            result: 分块结果
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存第一级章节
        chapters_data = {
            "chapters": [
                {
                    "chapter_id": chapter.chapter_id,
                    "title": chapter.title,
                    "content": chapter.content,
                    "start_pos": chapter.start_pos,
                    "end_pos": chapter.end_pos,
                    "word_count": chapter.word_count,
                    "has_images": chapter.has_images,
                    "has_tables": chapter.has_tables
                }
                for chapter in result.first_level_chapters
            ],
            "total_chapters": result.total_chapters,
            "processing_metadata": result.processing_metadata
        }
        
        chapters_file = os.path.join(output_dir, "first_level_chapters.json")
        with open(chapters_file, 'w', encoding='utf-8') as f:
            json.dump(chapters_data, f, ensure_ascii=False, indent=2)
        
        # 保存最小块
        chunks_data = {
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "chunk_type": chunk.chunk_type,
                    "belongs_to_chapter": chunk.belongs_to_chapter,
                    "chapter_title": chunk.chapter_title,
                    "start_pos": chunk.start_pos,
                    "end_pos": chunk.end_pos,
                    "word_count": chunk.word_count
                }
                for chunk in result.minimal_chunks
            ],
            "total_chunks": result.total_chunks,
            "processing_metadata": result.processing_metadata
        }
        
        chunks_file = os.path.join(output_dir, "minimal_chunks.json")
        with open(chunks_file, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)
        
        print(f"📁 分块结果已保存到: {output_dir}")
        print(f"   - 第一级章节: {chapters_file}")
        print(f"   - 最小块: {chunks_file}") 