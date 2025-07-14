#!/usr/bin/env python3
"""
调试版批量处理测试
专门检查批量处理的执行路径和性能
"""

import sys
import os
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_batch_processing_path():
    """测试批量处理路径"""
    print("🔍 调试批量处理执行路径")
    print("=" * 50)
    
    try:
        from src.pdf_processing.pdf_document_parser import PDFDocumentParser
        from src.pdf_processing.media_extractor import MediaExtractor
        from src.pdf_processing.ai_content_reorganizer import AIContentReorganizer
        from src.pdf_processing.config import PDFProcessingConfig
        
        # 测试文件路径
        test_pdf_path = "testfiles/AlphaEvolve.pdf"
        
        if not os.path.exists(test_pdf_path):
            print(f"❌ 测试文件不存在: {test_pdf_path}")
            return
        
        print(f"📄 测试文件: {test_pdf_path}")
        
        # 创建配置
        config = PDFProcessingConfig()
        print(f"🔧 配置信息:")
        print(f"  - 默认LLM: {config.ai_content.default_llm_model}")
        print(f"  - 最大工作线程: {config.ai_content.max_workers}")
        print(f"  - 启用并行处理: {config.ai_content.enable_parallel_processing}")
        
        # 步骤1：解析PDF
        print("\n📄 步骤1：解析PDF文档...")
        parser = PDFDocumentParser(config)
        raw_result, page_texts = parser.parse_pdf(test_pdf_path)
        print(f"✅ 解析完成，共 {len(page_texts)} 页")
        
        # 步骤2：提取媒体
        print("\n🖼️ 步骤2：提取媒体...")
        media_extractor = MediaExtractor(config)
        
        # 创建临时输出目录
        output_dir = Path("temp_batch_test")
        output_dir.mkdir(exist_ok=True)
        
        pages = media_extractor.extract_media_from_pages(
            raw_result=raw_result,
            page_texts=page_texts,
            output_dir=str(output_dir)
        )
        
        print(f"✅ 媒体提取完成，共 {len(pages)} 页")
        
        # 显示前几页信息
        print("\n📋 前5页信息:")
        for i, page in enumerate(pages[:5]):
            print(f"  页面 {page.page_number}:")
            print(f"    - 原始文本: {len(page.raw_text)} 字符")
            print(f"    - 图片: {len(page.images)} 个")
            print(f"    - 表格: {len(page.tables)} 个")
        
        # 步骤3：AI内容重组（重点测试）
        print("\n🧠 步骤3：AI内容重组（批量处理测试）...")
        ai_reorganizer = AIContentReorganizer(config)
        
        print("🔍 检查AI客户端状态:")
        print(f"  - 可用的AI客户端: {list(ai_reorganizer.ai_clients.keys())}")
        
        # 强制启用并行处理来测试批量处理
        print("\n🚀 开始批量处理测试...")
        start_time = time.time()
        
        # 测试批量处理
        processed_pages = ai_reorganizer.process_pages(
            pages, 
            parallel_processing=True
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print(f"\n✅ 批量处理完成！")
        print(f"⏱️ 处理时间: {processing_time:.2f} 秒")
        print(f"📊 处理页数: {len(processed_pages)}")
        print(f"⚡ 平均每页: {processing_time/len(processed_pages):.2f} 秒")
        
        # 检查处理效果
        cleaned_pages = sum(1 for page in processed_pages if page.cleaned_text)
        print(f"🧹 已清洗文本的页数: {cleaned_pages}")
        
        # 显示处理后的前几页
        print("\n📋 处理后前3页:")
        for i, page in enumerate(processed_pages[:3]):
            print(f"  页面 {page.page_number}:")
            print(f"    - 原始文本: {len(page.raw_text)} 字符")
            print(f"    - 清洗文本: {len(page.cleaned_text) if page.cleaned_text else 0} 字符")
            print(f"    - 文本清洗: {'✅' if page.cleaned_text else '❌'}")
            
            # 显示图片描述情况
            for img in page.images:
                desc_status = "✅" if img.ai_description else "❌"
                print(f"    - 图片描述: {desc_status}")
                
            # 显示表格描述情况
            for table in page.tables:
                desc_status = "✅" if table.ai_description else "❌"
                print(f"    - 表格描述: {desc_status}")
        
        # 清理临时目录
        import shutil
        shutil.rmtree(output_dir)
        
        print(f"\n🎉 批量处理测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_batch_processing_path() 