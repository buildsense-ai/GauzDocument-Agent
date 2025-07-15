#!/usr/bin/env python3
"""
完整工作流测试脚本
测试: page_split → AI增强 → TOC提取 → AI分块 的完整流程
"""

import os
import json
import time
from pathlib import Path

# 导入PDF解析工具
from src.pdf_processing.pdf_parser_tool import PDFParserTool

def test_complete_workflow():
    """测试完整的工作流程"""
    
    # 测试文件路径
    test_pdf = "testfiles/医灵古庙设计方案.pdf"
    
    if not os.path.exists(test_pdf):
        print(f"❌ 测试文件不存在: {test_pdf}")
        return
    
    print("🚀 开始完整工作流测试...")
    print("=" * 60)
    
    # 创建PDF解析工具
    tool = PDFParserTool()
    
    # 执行完整流程
    start_time = time.time()
    
    result_json = tool.execute(
        action="parse_page_split",
        pdf_path=test_pdf,
        enable_ai_enhancement=True,
        docling_parallel_processing=False,  # Mac上禁用docling并行处理避免PyTorch错误
        ai_parallel_processing=True  # 启用AI并行处理，提升性能
    )
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print("=" * 60)
    print(f"⏱️  总耗时: {total_time:.2f} 秒")
    
    # 解析结果
    try:
        result = json.loads(result_json)
        
        if result["status"] == "success":
            print("✅ 完整流程测试成功!")
            print(f"📁 输出目录: {result['output_directory']}")
            print(f"📄 处理页数: {result['pages_count']}")
            print(f"📖 TOC章节数: {result['toc_count']}")
            print(f"🔪 分块数量: {result['chunks_count']}")
            print(f"⏱️  处理时间: {result['processing_time']:.2f} 秒")
            
            # 检查输出文件
            output_dir = result['output_directory']
            check_output_files(output_dir)
            
        else:
            print("❌ 完整流程测试失败!")
            print(f"错误信息: {result.get('message', '未知错误')}")
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}")
        print("原始响应:")
        print(result_json)

def check_output_files(output_dir):
    """检查输出文件"""
    print("\n📁 检查输出文件:")
    print("-" * 40)
    
    expected_files = [
        "page_split_processing_result.json",
        "toc_extraction_result.json", 
        "chunks_result.json"
    ]
    
    for filename in expected_files:
        filepath = os.path.join(output_dir, filename)
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            print(f"✅ {filename} ({file_size:,} bytes)")
            
            # 如果是JSON文件，检查内容
            if filename.endswith('.json'):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if filename == "page_split_processing_result.json":
                        print(f"   📄 页面数: {len(data.get('pages', []))}")
                        print(f"   🖼️  图片数: {sum(len(page.get('images', [])) for page in data.get('pages', []))}")
                        print(f"   📊 表格数: {sum(len(page.get('tables', [])) for page in data.get('pages', []))}")
                    
                    elif filename == "toc_extraction_result.json":
                        toc_items = data.get('toc', [])
                        print(f"   📖 TOC项目数: {len(toc_items)}")
                        if toc_items:
                            level_counts = {}
                            for item in toc_items:
                                level = item.get('level', 0)
                                level_counts[level] = level_counts.get(level, 0) + 1
                            print(f"   📊 各级别数量: {level_counts}")
                    
                    elif filename == "chunks_result.json":
                        print(f"   📖 章节数: {data.get('total_chapters', 0)}")
                        print(f"   🔪 分块数: {data.get('total_chunks', 0)}")
                        
                except Exception as e:
                    print(f"   ⚠️  文件读取失败: {e}")
        else:
            print(f"❌ {filename} (缺失)")
    
    # 检查页面目录
    print("\n📁 检查页面目录:")
    print("-" * 40)
    
    page_dirs = [d for d in os.listdir(output_dir) if d.startswith('page_') and os.path.isdir(os.path.join(output_dir, d))]
    page_dirs.sort(key=lambda x: int(x.split('_')[1]))
    
    total_images = 0
    total_tables = 0
    
    for page_dir in page_dirs[:5]:  # 只显示前5个页面
        page_path = os.path.join(output_dir, page_dir)
        images = [f for f in os.listdir(page_path) if f.endswith('.png') and 'picture' in f]
        tables = [f for f in os.listdir(page_path) if f.endswith('.png') and 'table' in f]
        
        total_images += len(images)
        total_tables += len(tables)
        
        print(f"✅ {page_dir}: {len(images)} 图片, {len(tables)} 表格")
    
    if len(page_dirs) > 5:
        print(f"   ... 还有 {len(page_dirs) - 5} 个页面")
    
    print(f"📊 总计: {total_images} 图片, {total_tables} 表格")

if __name__ == "__main__":
    test_complete_workflow() 