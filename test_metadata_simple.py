#!/usr/bin/env python3
"""
简化的metadata测试脚本
直接验证修复后的字段提取功能
"""

import json
import os

def test_field_extraction():
    """测试字段提取功能"""
    
    print("🔧 测试图片/表格metadata字段提取...")
    
    # 测试数据文件
    page_split_file = "parser_output/20250715_131307_page_split/page_split_processing_result.json"
    
    if not os.path.exists(page_split_file):
        print(f"❌ 测试文件不存在: {page_split_file}")
        return
    
    # 读取原始数据
    with open(page_split_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"✅ 数据加载成功")
    print(f"📄 总页数: {len(data.get('pages', []))}")
    
    # 统计图片和表格
    total_images = 0
    total_tables = 0
    
    for page_num, page_data in enumerate(data.get("pages", []), 1):
        images = page_data.get("images", [])
        tables = page_data.get("tables", [])
        
        total_images += len(images)
        total_tables += len(tables)
        
        # 测试第一个图片的字段提取
        if images and total_images == 1:
            first_image = images[0]
            print(f"\n🖼️ 第一个图片字段验证:")
            print(f"   image_path: {first_image.get('image_path', 'MISSING')}")
            print(f"   page_number: {first_image.get('page_number', 'MISSING')}")
            print(f"   ai_description: {first_image.get('ai_description', 'MISSING')}")
            
            metadata = first_image.get("metadata", {})
            print(f"   metadata.width: {metadata.get('width', 'MISSING')}")
            print(f"   metadata.height: {metadata.get('height', 'MISSING')}")
            print(f"   metadata.size: {metadata.get('size', 'MISSING')}")
            print(f"   metadata.aspect_ratio: {metadata.get('aspect_ratio', 'MISSING')}")
        
        # 测试第一个表格的字段提取
        if tables and total_tables == 1:
            first_table = tables[0]
            print(f"\n📊 第一个表格字段验证:")
            print(f"   table_path: {first_table.get('table_path', 'MISSING')}")
            print(f"   page_number: {first_table.get('page_number', 'MISSING')}")
            print(f"   ai_description: {first_table.get('ai_description', 'MISSING')}")
            
            metadata = first_table.get("metadata", {})
            print(f"   metadata.width: {metadata.get('width', 'MISSING')}")
            print(f"   metadata.height: {metadata.get('height', 'MISSING')}")
            print(f"   metadata.size: {metadata.get('size', 'MISSING')}")
            print(f"   metadata.aspect_ratio: {metadata.get('aspect_ratio', 'MISSING')}")
    
    print(f"\n📊 统计结果:")
    print(f"   总图片数: {total_images}")
    print(f"   总表格数: {total_tables}")

def test_stitch_text_with_ids():
    """测试包含ID的文本缝合功能"""
    
    print("\n🧵 测试文本缝合功能...")
    
    page_split_file = "parser_output/20250715_131307_page_split/page_split_processing_result.json"
    
    if not os.path.exists(page_split_file):
        print(f"❌ 测试文件不存在: {page_split_file}")
        return
    
    with open(page_split_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    pages = data.get('pages', [])
    full_text_parts = []
    
    # 全局计数器，用于生成唯一ID
    global_image_counter = 0
    global_table_counter = 0
    
    for page in pages:
        cleaned_text = page.get('cleaned_text', '') or ''
        images = page.get('images', [])
        tables = page.get('tables', [])
        
        # 添加页面文本
        if cleaned_text and cleaned_text.strip():
            full_text_parts.append(cleaned_text.strip())
        
        # 添加图片描述（包含唯一标识符）
        for image in images:
            global_image_counter += 1
            description = image.get('ai_description', '图片描述') or '图片描述'
            image_path = image.get('image_path', '')
            # 格式：[图片|ID:xxx|PATH:xxx: 描述]
            full_text_parts.append(f"[图片|ID:{global_image_counter}|PATH:{image_path}: {description}]")
        
        # 添加表格描述（包含唯一标识符）
        for table in tables:
            global_table_counter += 1
            description = table.get('ai_description', '表格描述') or '表格描述'
            table_path = table.get('table_path', '')
            # 格式：[表格|ID:xxx|PATH:xxx: 描述]
            full_text_parts.append(f"[表格|ID:{global_table_counter}|PATH:{table_path}: {description}]")
    
    # 用双换行连接，保持段落分隔
    full_text = "\n\n".join(full_text_parts)
    
    print(f"✅ 文本缝合完成，总长度: {len(full_text)} 字符")
    print(f"🖼️ 包含图片: {global_image_counter} 个")
    print(f"📊 包含表格: {global_table_counter} 个")
    
    # 验证新格式的引用
    import re
    image_refs = re.findall(r'\[图片\|ID:(\d+)\|PATH:([^:]+):', full_text)
    table_refs = re.findall(r'\[表格\|ID:(\d+)\|PATH:([^:]+):', full_text)
    
    print(f"🔍 发现图片引用: {len(image_refs)} 个")
    print(f"🔍 发现表格引用: {len(table_refs)} 个")
    
    if image_refs:
        print(f"   示例图片引用: ID={image_refs[0][0]}, PATH={os.path.basename(image_refs[0][1])}")
    if table_refs:
        print(f"   示例表格引用: ID={table_refs[0][0]}, PATH={os.path.basename(table_refs[0][1])}")
    
    # 保存测试结果
    output_file = "parser_output/full_text_with_ids.txt"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(full_text)
    
    print(f"💾 带ID的完整文本已保存到: {output_file}")

if __name__ == "__main__":
    test_field_extraction()
    test_stitch_text_with_ids()
    print("\n✅ 简化测试完成!") 