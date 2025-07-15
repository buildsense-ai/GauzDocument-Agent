#!/usr/bin/env python3
"""
测试修复后的metadata提取功能
验证图片和表格的正确字段提取以及章节分配
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from pdf_processing.metadata_extractor import MetadataExtractor
from pdf_processing.text_chunker import TextChunker
from pdf_processing.toc_extractor import TOCExtractor
import json

def test_fixed_metadata_extraction():
    """测试修复后的metadata提取"""
    
    print("🔧 测试修复后的图片/表格metadata提取...")
    
    # 使用现有的测试数据
    page_split_file = "parser_output/20250715_131307_page_split/page_split_processing_result.json"
    
    if not os.path.exists(page_split_file):
        print(f"❌ 测试文件不存在: {page_split_file}")
        return
    
    # 初始化提取器
    extractor = MetadataExtractor(project_name="医灵古庙设计方案")
    
    # 1. 测试page_split结果的metadata提取
    print("\n📄 提取基础metadata...")
    basic_metadata = extractor.extract_from_page_split_result(page_split_file)
    
    print(f"✅ 文档信息: {basic_metadata['document_info']['file_name']}")
    print(f"📊 图片数量: {len(basic_metadata['image_metadata'])}")
    print(f"📋 表格数量: {len(basic_metadata['table_metadata'])}")
    
    # 验证图片metadata
    if basic_metadata['image_metadata']:
        first_image = basic_metadata['image_metadata'][0]
        print(f"\n🖼️ 第一个图片metadata验证:")
        print(f"   图片路径: {first_image.image_path}")
        print(f"   尺寸: {first_image.width}x{first_image.height}")
        print(f"   文件大小: {first_image.size}")
        print(f"   宽高比: {first_image.aspect_ratio:.2f}")
        print(f"   AI描述: {first_image.ai_description}")
        print(f"   章节ID: {first_image.chapter_id}")
    
    # 验证表格metadata
    if basic_metadata['table_metadata']:
        first_table = basic_metadata['table_metadata'][0]
        print(f"\n📊 第一个表格metadata验证:")
        print(f"   表格路径: {first_table.table_path}")
        print(f"   尺寸: {first_table.width}x{first_table.height}")
        print(f"   文件大小: {first_table.size}")
        print(f"   宽高比: {first_table.aspect_ratio:.2f}")
        print(f"   AI描述: {first_table.ai_description}")
        print(f"   章节ID: {first_table.chapter_id}")
    
    # 2. 测试章节分配功能
    print("\n🧵 测试full_text生成和章节分配...")
    
    # 生成full_text（包含唯一标识符）
    toc_extractor = TOCExtractor()
    full_text = toc_extractor.stitch_full_text(page_split_file)
    
    print(f"📝 Full text长度: {len(full_text)} 字符")
    
    # 检查是否包含新的格式化引用
    import re
    image_refs = re.findall(r'\[图片\|ID:(\d+)\|PATH:([^:]+):', full_text)
    table_refs = re.findall(r'\[表格\|ID:(\d+)\|PATH:([^:]+):', full_text)
    
    print(f"🔍 发现图片引用: {len(image_refs)} 个")
    print(f"🔍 发现表格引用: {len(table_refs)} 个")
    
    if image_refs:
        print(f"   示例图片引用: ID={image_refs[0][0]}, PATH={image_refs[0][1]}")
    if table_refs:
        print(f"   示例表格引用: ID={table_refs[0][0]}, PATH={table_refs[0][1]}")
    
    # 3. 生成TOC结果用于测试
    print("\n📑 生成TOC结果用于测试...")
    toc_items, reasoning = toc_extractor.extract_toc_with_reasoning(full_text)
    toc_result = {"toc_items": toc_items, "reasoning": reasoning}
    
    # 4. 测试文本分块
    print("\n✂️ 测试文本分块...")
    text_chunker = TextChunker()
    chunking_result = text_chunker.chunk_text_with_toc(full_text, toc_result)
    
    print(f"📚 章节数量: {len(chunking_result.first_level_chapters)}")
    print(f"📦 分块数量: {len(chunking_result.minimal_chunks)}")
    
    # 5. 测试精确章节分配
    print("\n🎯 测试精确章节分配...")
    chunk_metadata = extractor.extract_from_chunking_result(
        chunking_result,
        basic_metadata['image_metadata'],
        basic_metadata['table_metadata']
    )
    
    # 验证章节分配结果
    assigned_images = [img for img in basic_metadata['image_metadata'] if img.chapter_id]
    assigned_tables = [tbl for tbl in basic_metadata['table_metadata'] if tbl.chapter_id]
    
    print(f"✅ 已分配章节的图片: {len(assigned_images)} / {len(basic_metadata['image_metadata'])}")
    print(f"✅ 已分配章节的表格: {len(assigned_tables)} / {len(basic_metadata['table_metadata'])}")
    
    # 显示分配结果示例
    for i, img in enumerate(assigned_images[:3]):  # 显示前3个
        print(f"   图片 {i+1}: 章节 {img.chapter_id} - {os.path.basename(img.image_path)}")
    
    for i, tbl in enumerate(assigned_tables[:3]):  # 显示前3个
        print(f"   表格 {i+1}: 章节 {tbl.chapter_id} - {os.path.basename(tbl.table_path)}")
    
    # 6. 保存测试结果
    print("\n💾 保存测试结果...")
    output_dir = "parser_output/metadata_test_fixed"
    os.makedirs(output_dir, exist_ok=True)
    
    extractor.save_extracted_metadata(
        output_dir,
        image_metadata=basic_metadata['image_metadata'],
        table_metadata=basic_metadata['table_metadata'],
        text_chunks=chunk_metadata['text_chunks']
    )
    
    print(f"✅ 测试完成，结果保存到: {output_dir}")

if __name__ == "__main__":
    test_fixed_metadata_extraction() 