#!/usr/bin/env python3
"""
测试增强版处理效果
验证跨页面内容连接、图片表格精确定位、章节关联等功能
"""

import json
import os
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.append(str(Path(__file__).parent / "src"))

from src.pdf_processing.enhanced_ai_content_reorganizer import EnhancedAIContentReorganizer
from src.pdf_processing.data_models import PageData, ImageWithContext, TableWithContext

def test_enhanced_processing():
    """测试增强版处理"""
    print("🧪 开始测试增强版处理...")
    
    # 测试数据路径
    test_data_dir = "parser_output/20250714_232720_vvmpc0"
    basic_result_file = os.path.join(test_data_dir, "basic_processing_result.json")
    
    if not os.path.exists(basic_result_file):
        print(f"❌ 测试数据不存在: {basic_result_file}")
        return
    
    # 读取基础处理结果
    print("📖 读取基础处理结果...")
    with open(basic_result_file, 'r', encoding='utf-8') as f:
        basic_result = json.load(f)
    
    # 重建PageData对象
    pages = []
    for page_data in basic_result["pages"]:
        # 重建图片对象
        images = []
        for img_data in page_data["images"]:
            image = ImageWithContext(
                image_path=img_data["image_path"],
                page_number=img_data["page_number"],
                page_context=img_data["page_context"],
                ai_description=img_data.get("ai_description", "图片描述"),
                caption=img_data.get("caption"),
                metadata=img_data.get("metadata", {})
            )
            images.append(image)
        
        # 重建表格对象
        tables = []
        for table_data in page_data["tables"]:
            table = TableWithContext(
                table_path=table_data["table_path"],
                page_number=table_data["page_number"],
                page_context=table_data["page_context"],
                ai_description=table_data.get("ai_description", "表格描述"),
                caption=table_data.get("caption"),
                metadata=table_data.get("metadata", {})
            )
            tables.append(table)
        
        # 重建页面对象
        page = PageData(
            page_number=page_data["page_number"],
            raw_text=page_data["raw_text"],
            cleaned_text=page_data.get("cleaned_text", ""),
            images=images,
            tables=tables
        )
        pages.append(page)
    
    print(f"✅ 成功加载 {len(pages)} 个页面")
    
    # 创建增强版处理器
    print("🔧 创建增强版处理器...")
    enhanced_processor = EnhancedAIContentReorganizer()
    
    # 执行增强版处理
    print("🚀 执行增强版处理...")
    try:
        enhanced_pages, enhanced_media = enhanced_processor.process_pages_enhanced(
            pages, 
            parallel_processing=True
        )
        
        print(f"✅ 增强版处理完成!")
        print(f"📄 处理页面数: {len(enhanced_pages)}")
        print(f"🎯 增强媒体数: {len(enhanced_media)}")
        
        # 分析增强效果
        print("\n📊 增强效果分析:")
        
        # 1. 媒体分析
        image_count = len([m for m in enhanced_media if m.position_info.media_type == "image"])
        table_count = len([m for m in enhanced_media if m.position_info.media_type == "table"])
        print(f"🖼️ 图片数量: {image_count}")
        print(f"📋 表格数量: {table_count}")
        
        # 2. 显示增强媒体信息
        print("\n🎯 增强媒体信息:")
        for i, media in enumerate(enhanced_media[:5]):  # 只显示前5个
            print(f"  {i+1}. {media.position_info.media_id}")
            print(f"     类型: {media.position_info.media_type}")
            print(f"     占位符: {media.position_info.unique_placeholder}")
            print(f"     章节提示: {media.position_info.chapter_hint}")
            print(f"     上下文得分: {media.context_score:.2f}")
            print(f"     描述: {media.position_info.ai_description[:50]}...")
            print()
        
        # 3. 保存增强结果
        print("💾 保存增强结果...")
        output_dir = "enhanced_processing_test_output"
        os.makedirs(output_dir, exist_ok=True)
        
        output_files = enhanced_processor.save_enhanced_processing_result(
            enhanced_pages, 
            enhanced_media, 
            output_dir
        )
        
        print("✅ 结果已保存到:")
        for name, path in output_files.items():
            print(f"  {name}: {path}")
        
        # 4. 显示增强文本样本
        print("\n📝 增强文本样本:")
        enhanced_full_text = enhanced_processor.generate_enhanced_full_text(enhanced_pages, enhanced_media)
        print(f"总长度: {len(enhanced_full_text)} 字符")
        print("前500字符:")
        print(enhanced_full_text[:500])
        print("...")
        
    except Exception as e:
        print(f"❌ 增强版处理失败: {e}")
        import traceback
        traceback.print_exc()

def compare_processing_results():
    """比较原始和增强处理结果"""
    print("\n🔍 比较原始和增强处理结果...")
    
    # 原始完整文本
    original_full_text_path = "parser_output/20250714_232720_vvmpc0/full_text.txt"
    if os.path.exists(original_full_text_path):
        with open(original_full_text_path, 'r', encoding='utf-8') as f:
            original_text = f.read()
        print(f"📄 原始文本长度: {len(original_text)} 字符")
        print(f"📄 原始文本段落数: {len(original_text.split('\\n\\n'))}")
    
    # 增强版完整文本
    enhanced_full_text_path = "enhanced_processing_test_output/enhanced_full_text.txt"
    if os.path.exists(enhanced_full_text_path):
        with open(enhanced_full_text_path, 'r', encoding='utf-8') as f:
            enhanced_text = f.read()
        print(f"🎯 增强文本长度: {len(enhanced_text)} 字符")
        print(f"🎯 增强文本段落数: {len(enhanced_text.split('\\n\\n'))}")
        
        # 分析unique占位符
        import re
        unique_placeholders = re.findall(r'{{([^}]+)}}', enhanced_text)
        print(f"🎯 unique占位符数量: {len(unique_placeholders)}")
        
        if unique_placeholders:
            print("示例占位符:")
            for placeholder in unique_placeholders[:5]:
                print(f"  {placeholder}")
    
    # 增强媒体信息
    enhanced_media_path = "enhanced_processing_test_output/enhanced_media_info.json"
    if os.path.exists(enhanced_media_path):
        with open(enhanced_media_path, 'r', encoding='utf-8') as f:
            media_info = json.load(f)
        print(f"🎯 增强媒体项数: {media_info['total_media']}")
        
        # 分析章节关联
        chapter_hints = {}
        for item in media_info['media_items']:
            hint = item.get('chapter_hint', 'unknown')
            if hint not in chapter_hints:
                chapter_hints[hint] = 0
            chapter_hints[hint] += 1
        
        print("章节关联分析:")
        for hint, count in chapter_hints.items():
            print(f"  {hint}: {count} 个媒体项")

if __name__ == "__main__":
    test_enhanced_processing()
    compare_processing_results() 