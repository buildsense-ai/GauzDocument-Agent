#!/usr/bin/env python3
"""
测试PDF解析工具的完整工作流程
测试parse_page_split模式的端到端处理
"""

import os
import sys
import json
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.pdf_processing.pdf_parser_tool import PDFParserTool
from src.pdf_processing.config import PDFProcessingConfig

def test_complete_workflow():
    """测试完整的PDF处理工作流程"""
    
    # 配置测试参数
    test_pdf_path = "testfiles/医灵古庙设计方案.pdf"
    
    # 检查测试文件是否存在
    if not os.path.exists(test_pdf_path):
        print(f"❌ 测试文件不存在: {test_pdf_path}")
        return False
    
    # 创建PDF解析工具
    config = PDFProcessingConfig()
    pdf_tool = PDFParserTool(config)
    
    print("🚀 开始测试完整PDF处理工作流程")
    print(f"📁 测试文件: {test_pdf_path}")
    print("="*60)
    
    start_time = time.time()
    
    try:
        # 执行完整的页面分割解析流程
        result_json = pdf_tool.execute(
            action="parse_page_split",
            pdf_path=test_pdf_path,
            enable_ai_enhancement=True,
            docling_parallel_processing=False,  # Mac上禁用docling并行
            ai_parallel_processing=True         # 启用AI并行处理
        )
        
        # 解析结果
        result = json.loads(result_json)
        
        if result["status"] == "success":
            output_dir = result["output_directory"]
            processing_time = result["processing_time"]
            
            print(f"✅ 处理成功!")
            print(f"📁 输出目录: {output_dir}")
            print(f"⏱️ 处理时间: {processing_time:.2f} 秒")
            print(f"📄 页面数量: {result['pages_count']}")
            print(f"📖 TOC章节数: {result['toc_count']}")
            print(f"🔪 分块数量: {result['chunks_count']}")
            
            # 验证输出文件
            print("\n📋 验证输出文件:")
            verify_output_files(output_dir)
            
            return True
            
        else:
            print(f"❌ 处理失败: {result['message']}")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        end_time = time.time()
        total_time = end_time - start_time
        print(f"\n⏱️ 总测试时间: {total_time:.2f} 秒")

def verify_output_files(output_dir: str) -> None:
    """验证输出文件是否生成"""
    
    expected_files = [
        "page_split_processing_result.json",
        "toc_extraction_result.json", 
        "chunks_result.json",
        "metadata/basic_metadata.json",
        "metadata/document_summary.json",
        "metadata/chapter_summaries.json",
        "metadata/derived_questions.json"
    ]
    
    all_files_exist = True
    
    for file_path in expected_files:
        full_path = os.path.join(output_dir, file_path)
        if os.path.exists(full_path):
            # 获取文件大小
            file_size = os.path.getsize(full_path)
            print(f"✅ {file_path} ({file_size:,} bytes)")
        else:
            print(f"❌ {file_path} (文件不存在)")
            all_files_exist = False
    
    # 检查页面目录
    page_dirs = [d for d in os.listdir(output_dir) if d.startswith("page_")]
    if page_dirs:
        print(f"📁 页面目录: {len(page_dirs)} 个 ({', '.join(sorted(page_dirs)[:5])}{'...' if len(page_dirs) > 5 else ''})")
        
        # 检查第一页的媒体文件
        page_1_dir = os.path.join(output_dir, "page_1")
        if os.path.exists(page_1_dir):
            media_files = [f for f in os.listdir(page_1_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
            if media_files:
                print(f"🖼️ 第1页媒体文件: {len(media_files)} 个")
    
    # 显示输出目录的总体统计
    print(f"\n📊 输出目录统计:")
    print(f"   - 目录: {output_dir}")
    print(f"   - 主要文件: {sum(1 for f in expected_files if os.path.exists(os.path.join(output_dir, f)))}/{len(expected_files)}")
    print(f"   - 页面目录: {len(page_dirs)} 个")
    
    if all_files_exist:
        print("🎉 所有预期文件都已生成!")
    else:
        print("⚠️ 某些文件缺失，请检查处理日志")

def display_sample_results(output_dir: str) -> None:
    """显示部分结果样本"""
    
    print("\n📋 结果样本:")
    
    # 显示TOC结果
    toc_file = os.path.join(output_dir, "toc_extraction_result.json")
    if os.path.exists(toc_file):
        try:
            with open(toc_file, 'r', encoding='utf-8') as f:
                toc_data = json.load(f)
            
            toc_items = toc_data.get("toc", [])
            print(f"📖 TOC章节 ({len(toc_items)} 个):")
            for i, item in enumerate(toc_items[:3]):  # 只显示前3个
                print(f"   {item.get('level', 1)}. {item.get('title', 'Unknown')}")
            if len(toc_items) > 3:
                print(f"   ... 还有 {len(toc_items) - 3} 个章节")
                
        except Exception as e:
            print(f"   ⚠️ 读取TOC文件失败: {e}")
    
    # 显示分块结果
    chunks_file = os.path.join(output_dir, "chunks_result.json")
    if os.path.exists(chunks_file):
        try:
            with open(chunks_file, 'r', encoding='utf-8') as f:
                chunks_data = json.load(f)
            
            chapters = chunks_data.get("first_level_chapters", [])
            chunks = chunks_data.get("minimal_chunks", [])
            
            print(f"🔪 分块结果:")
            print(f"   - 一级章节: {len(chapters)} 个")
            print(f"   - 最小分块: {len(chunks)} 个")
            
            if chapters:
                print(f"   首章标题: {chapters[0].get('title', 'Unknown')}")
                print(f"   首章字数: {chapters[0].get('word_count', 0):,} 字")
                
        except Exception as e:
            print(f"   ⚠️ 读取分块文件失败: {e}")
    
    # 显示元数据基本信息
    metadata_file = os.path.join(output_dir, "metadata/basic_metadata.json")
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            doc_info = metadata.get("document", {})
            images = metadata.get("images", [])
            tables = metadata.get("tables", [])
            
            print(f"📊 基础元数据:")
            print(f"   - 文档ID: {doc_info.get('document_id', 'Unknown')}")
            print(f"   - 页面数: {doc_info.get('total_pages', 0)}")
            print(f"   - 图片数: {len(images)}")
            print(f"   - 表格数: {len(tables)}")
                
        except Exception as e:
            print(f"   ⚠️ 读取元数据文件失败: {e}")

if __name__ == "__main__":
    print("🧪 PDF处理工具完整工作流程测试")
    print("="*60)
    
    # 运行测试
    success = test_complete_workflow()
    
    if success:
        print("\n🎉 测试完成！所有组件工作正常。")
        
        # 获取最新的输出目录
        parser_output_dir = "parser_output"
        if os.path.exists(parser_output_dir):
            subdirs = [d for d in os.listdir(parser_output_dir) if d.endswith("_page_split")]
            if subdirs:
                latest_dir = os.path.join(parser_output_dir, sorted(subdirs)[-1])
                display_sample_results(latest_dir)
        
        print(f"\n📁 详细结果请查看输出目录中的文件")
    else:
        print("\n❌ 测试失败，请检查错误信息和日志")
        sys.exit(1) 