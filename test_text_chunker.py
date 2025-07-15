#!/usr/bin/env python3
"""
测试文本分块器
验证第一级章节切割和最小块分割功能
"""

import json
import os
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.append(str(Path(__file__).parent / "src"))

# 直接导入TextChunker
from src.pdf_processing.text_chunker import TextChunker

def test_text_chunker():
    """测试文本分块器"""
    print("🧪 开始测试文本分块器...")
    
    # 输入文件路径
    test_data_dir = "parser_output/20250714_232720_vvmpc0"
    full_text_file = os.path.join(test_data_dir, "full_text.txt")
    toc_result_file = os.path.join(test_data_dir, "toc_extraction_result.json")
    
    # 检查输入文件是否存在
    if not os.path.exists(full_text_file):
        print(f"❌ 找不到文件: {full_text_file}")
        return
        
    if not os.path.exists(toc_result_file):
        print(f"❌ 找不到文件: {toc_result_file}")
        return
    
    # 读取输入数据
    print("📖 读取输入数据...")
    with open(full_text_file, 'r', encoding='utf-8') as f:
        full_text = f.read()
    
    with open(toc_result_file, 'r', encoding='utf-8') as f:
        toc_result = json.load(f)
    
    print(f"✅ 成功读取数据:")
    print(f"   - 全文长度: {len(full_text)} 字符")
    print(f"   - TOC章节数: {len(toc_result['toc'])} 个")
    
    # 创建分块器
    chunker = TextChunker()
    
    # 执行分块
    print("\n🔪 开始执行分块...")
    result = chunker.chunk_text_with_toc(full_text, toc_result)
    
    # 显示结果统计
    print(f"\n📊 分块结果统计:")
    print(f"   - 第一级章节数: {result.total_chapters}")
    print(f"   - 最小块总数: {result.total_chunks}")
    
    # 显示第一级章节详情
    print(f"\n📖 第一级章节详情:")
    for i, chapter in enumerate(result.first_level_chapters):
        print(f"   {i+1}. {chapter.title} (ID: {chapter.chapter_id})")
        print(f"      - 字数: {chapter.word_count}")
        print(f"      - 包含图片: {'是' if chapter.has_images else '否'}")
        print(f"      - 包含表格: {'是' if chapter.has_tables else '否'}")
        print(f"      - 内容预览: {chapter.content[:100].strip()}...")
        print()
    
    # 显示最小块分类统计
    chunk_types = {}
    for chunk in result.minimal_chunks:
        chunk_type = chunk.chunk_type
        if chunk_type not in chunk_types:
            chunk_types[chunk_type] = 0
        chunk_types[chunk_type] += 1
    
    print(f"📝 最小块分类统计:")
    for chunk_type, count in chunk_types.items():
        print(f"   - {chunk_type}: {count} 个")
    
    # 显示部分最小块示例
    print(f"\n🔍 最小块示例:")
    for i, chunk in enumerate(result.minimal_chunks[:5]):  # 只显示前5个
        print(f"   {i+1}. {chunk.chunk_id} ({chunk.chunk_type})")
        print(f"      所属章节: {chunk.chapter_title}")
        print(f"      字数: {chunk.word_count}")
        print(f"      内容: {chunk.content[:80].strip()}...")
        print()
    
    # 保存结果
    output_dir = "chunking_test_output"
    print(f"💾 保存分块结果到: {output_dir}")
    chunker.save_chunking_result(result, output_dir)
    
    # 验证保存的文件
    chapters_file = os.path.join(output_dir, "first_level_chapters.json")
    chunks_file = os.path.join(output_dir, "minimal_chunks.json")
    
    if os.path.exists(chapters_file):
        print(f"✅ 章节文件已保存: {chapters_file}")
    else:
        print(f"❌ 章节文件保存失败: {chapters_file}")
    
    if os.path.exists(chunks_file):
        print(f"✅ 块文件已保存: {chunks_file}")
    else:
        print(f"❌ 块文件保存失败: {chunks_file}")
    
    print("\n🎉 测试完成!")
    
    return result

def analyze_chunking_quality(result):
    """分析分块质量"""
    print("\n📈 分块质量分析:")
    
    # 章节长度分析
    chapter_lengths = [chapter.word_count for chapter in result.first_level_chapters]
    avg_chapter_length = sum(chapter_lengths) / len(chapter_lengths)
    max_chapter_length = max(chapter_lengths)
    min_chapter_length = min(chapter_lengths)
    
    print(f"   章节长度统计:")
    print(f"   - 平均长度: {avg_chapter_length:.0f} 字符")
    print(f"   - 最大长度: {max_chapter_length} 字符")
    print(f"   - 最小长度: {min_chapter_length} 字符")
    
    # 最小块长度分析
    chunk_lengths = [chunk.word_count for chunk in result.minimal_chunks]
    avg_chunk_length = sum(chunk_lengths) / len(chunk_lengths)
    max_chunk_length = max(chunk_lengths)
    min_chunk_length = min(chunk_lengths)
    
    print(f"   最小块长度统计:")
    print(f"   - 平均长度: {avg_chunk_length:.0f} 字符")
    print(f"   - 最大长度: {max_chunk_length} 字符")
    print(f"   - 最小长度: {min_chunk_length} 字符")
    
    # 检索友好度分析
    suitable_chunks = [chunk for chunk in result.minimal_chunks 
                      if 100 <= chunk.word_count <= 500]
    
    print(f"   检索友好度:")
    print(f"   - 适合检索的块数: {len(suitable_chunks)}/{len(result.minimal_chunks)}")
    print(f"   - 比例: {len(suitable_chunks)/len(result.minimal_chunks)*100:.1f}%")

if __name__ == "__main__":
    result = test_text_chunker()
    if result:
        analyze_chunking_quality(result) 