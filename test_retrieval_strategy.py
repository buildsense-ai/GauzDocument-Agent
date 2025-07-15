#!/usr/bin/env python3
"""
测试检索策略
验证"小块检索，大块喂养"功能
"""

import json
import os
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.append(str(Path(__file__).parent / "src"))

from src.pdf_processing.text_chunker import TextChunker
from src.pdf_processing.retrieval_strategy import RetrievalStrategy, RetrievalQuery

def test_retrieval_strategy():
    """测试检索策略"""
    print("🧪 开始测试检索策略...")
    
    # 1. 加载分块结果
    chunking_output_dir = "chunking_test_output"
    chapters_file = os.path.join(chunking_output_dir, "first_level_chapters.json")
    chunks_file = os.path.join(chunking_output_dir, "minimal_chunks.json")
    
    if not os.path.exists(chapters_file) or not os.path.exists(chunks_file):
        print("❌ 请先运行 test_text_chunker.py 生成分块结果")
        return
    
    # 从JSON文件重建分块结果
    print("📖 加载分块结果...")
    chunking_result = load_chunking_result(chapters_file, chunks_file)
    
    # 2. 创建检索策略
    strategy = RetrievalStrategy(chunking_result)
    
    # 3. 测试不同的查询
    test_queries = [
        "文物保护",
        "医灵古庙",
        "建筑设计",
        "安全监测",
        "项目概况",
        "基础措施",
        "影响分析",
        "技术可行性"
    ]
    
    for query_text in test_queries:
        print(f"\n{'='*60}")
        print(f"🔍 测试查询: '{query_text}'")
        print('='*60)
        
        # 创建查询
        query = RetrievalQuery(query_text=query_text, top_k=3)
        
        # 执行检索
        result = strategy.search(query)
        
        # 显示结果
        formatted_result = strategy.format_retrieval_result(result)
        print(formatted_result)
        
        # 保存结果
        output_file = f"retrieval_test_output_{query_text.replace(' ', '_')}.json"
        strategy.save_retrieval_result(result, output_file)
    
    # 4. 测试高级查询
    print(f"\n{'='*60}")
    print("🧪 测试高级查询功能")
    print('='*60)
    
    # 只检索标题块
    query = RetrievalQuery(
        query_text="建筑",
        top_k=2,
        chunk_types=["title"]
    )
    result = strategy.search(query)
    print("🎯 只检索标题块:")
    print(strategy.format_retrieval_result(result))
    
    # 只检索特定章节
    query = RetrievalQuery(
        query_text="安全",
        top_k=3,
        chapter_filter=["8", "16", "17"]  # 文保单位、影响分析、预防措施
    )
    result = strategy.search(query)
    print("\n🎯 只检索特定章节:")
    print(strategy.format_retrieval_result(result))
    
    print("\n🎉 检索策略测试完成!")

def load_chunking_result(chapters_file, chunks_file):
    """从JSON文件加载分块结果"""
    # 这里需要重新构建ChunkingResult对象
    # 由于导入问题，我们直接使用字典形式进行测试
    with open(chapters_file, 'r', encoding='utf-8') as f:
        chapters_data = json.load(f)
    
    with open(chunks_file, 'r', encoding='utf-8') as f:
        chunks_data = json.load(f)
    
    # 重新构建对象
    from src.pdf_processing.text_chunker import ChapterContent, MinimalChunk, ChunkingResult
    
    # 重建章节对象
    chapters = []
    for ch_data in chapters_data['chapters']:
        chapter = ChapterContent(
            chapter_id=ch_data['chapter_id'],
            title=ch_data['title'],
            content=ch_data['content'],
            start_pos=ch_data['start_pos'],
            end_pos=ch_data['end_pos'],
            word_count=ch_data['word_count'],
            has_images=ch_data['has_images'],
            has_tables=ch_data['has_tables']
        )
        chapters.append(chapter)
    
    # 重建块对象
    chunks = []
    for chunk_data in chunks_data['chunks']:
        chunk = MinimalChunk(
            chunk_id=chunk_data['chunk_id'],
            content=chunk_data['content'],
            chunk_type=chunk_data['chunk_type'],
            belongs_to_chapter=chunk_data['belongs_to_chapter'],
            chapter_title=chunk_data['chapter_title'],
            start_pos=chunk_data['start_pos'],
            end_pos=chunk_data['end_pos'],
            word_count=chunk_data['word_count']
        )
        chunks.append(chunk)
    
    # 重建分块结果
    result = ChunkingResult(
        first_level_chapters=chapters,
        minimal_chunks=chunks,
        total_chapters=len(chapters),
        total_chunks=len(chunks),
        processing_metadata=chunks_data['processing_metadata']
    )
    
    return result

if __name__ == "__main__":
    test_retrieval_strategy() 