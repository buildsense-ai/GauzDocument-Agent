#!/usr/bin/env python3
"""
从page_split结果开始的测试脚本
测试: TOC提取 + AI分块
"""

import os
import json
import time
from pathlib import Path

# 导入相关组件
from src.pdf_processing.toc_extractor import TOCExtractor
from src.pdf_processing.ai_chunker import AIChunker
from src.pdf_processing.text_chunker import TextChunker

def test_from_page_split_result():
    """从page_split结果开始测试后续流程"""
    
    # 使用最新的输出结果
    result_file = "parser_output/20250715_131307_page_split/page_split_processing_result.json"
    
    if not os.path.exists(result_file):
        print(f"❌ 结果文件不存在: {result_file}")
        return
    
    print("🚀 开始从page_split结果测试...")
    print("=" * 60)
    
    # 读取page_split结果
    with open(result_file, 'r', encoding='utf-8') as f:
        page_split_data = json.load(f)
    
    print(f"📄 加载完成: {len(page_split_data['pages'])} 页")
    
    # 1. 测试TOC提取
    print("\n📖 开始TOC提取测试...")
    toc_start = time.time()
    
    toc_extractor = TOCExtractor()
    
    # 先拼接完整文本
    full_text = toc_extractor.stitch_full_text(result_file)
    print(f"📝 完整文本长度: {len(full_text)} 字符")
    
    # 提取TOC
    toc_items, reasoning_content = toc_extractor.extract_toc_with_reasoning(full_text)
    
    toc_end = time.time()
    toc_time = toc_end - toc_start
    
    print(f"✅ TOC提取完成，耗时: {toc_time:.2f} 秒")
    if toc_items:
        print(f"📖 识别章节数: {len(toc_items)}")
        
        # 保存TOC结果
        output_dir = Path(result_file).parent
        toc_result_dict = {
            "toc": [item.__dict__ for item in toc_items],
            "reasoning_content": reasoning_content
        }
        
        toc_file = output_dir / "toc_test_result.json"
        with open(toc_file, 'w', encoding='utf-8') as f:
            json.dump(toc_result_dict, f, ensure_ascii=False, indent=2)
        print(f"💾 TOC结果已保存: {toc_file}")
    else:
        print("❌ TOC提取失败")
        return
    
    # 2. 测试AI分块
    print("\n🔪 开始AI分块测试...")
    chunk_start = time.time()
    
    # 基于TOC进行分块
    text_chunker = TextChunker()
    
    print(f"📝 完整文本长度: {len(full_text)} 字符")
    
    # 使用正确的方法调用
    try:
        chunks_result = text_chunker.chunk_text_with_toc(full_text, toc_result_dict)
        
        if chunks_result:
            print(f"📚 第一级章节数: {len(chunks_result.first_level_chapters)}")
            print(f"🔪 总分块数: {len(chunks_result.minimal_chunks)}")
            
            # 保存分块结果
            chunks_file = output_dir / "chunks_test_result.json"
            with open(chunks_file, 'w', encoding='utf-8') as f:
                json.dump(chunks_result.to_dict(), f, ensure_ascii=False, indent=2)
            print(f"💾 分块结果已保存: {chunks_file}")
            
            successful_chapters = len(chunks_result.first_level_chapters)
            failed_chapters = 0
            all_chunks = chunks_result.minimal_chunks
        else:
            print("❌ AI分块失败")
            successful_chapters = 0
            failed_chapters = 1
            all_chunks = []
        
    except Exception as e:
        print(f"❌ AI分块失败: {e}")
        successful_chapters = 0
        failed_chapters = 1
        all_chunks = []
    
    chunk_end = time.time()
    chunk_time = chunk_end - chunk_start
    
    print(f"\n✅ AI分块完成，耗时: {chunk_time:.2f} 秒")
    print(f"📊 成功章节: {successful_chapters}")
    print(f"❌ 失败章节: {failed_chapters}")
    print(f"🔪 总分块数: {len(all_chunks)}")
    
    # 总结
    total_time = toc_time + chunk_time
    print(f"\n📊 测试总结:")
    print(f"⏱️  TOC提取时间: {toc_time:.2f} 秒")
    print(f"⏱️  AI分块时间: {chunk_time:.2f} 秒")
    print(f"⏱️  总耗时: {total_time:.2f} 秒")

if __name__ == "__main__":
    test_from_page_split_result() 