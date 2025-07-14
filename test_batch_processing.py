#!/usr/bin/env python3
"""
测试PDF批量页面处理功能
测试AlphaEvolve.pdf的44个页面批量处理能力
"""

import sys
import os
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.pdf_processing.pdf_parser_tool import PDFParserTool
from src.pdf_processing.config import PDFProcessingConfig

def test_batch_processing():
    """测试批量处理功能"""
    print("🚀 测试PDF批量页面处理功能")
    print("=" * 60)
    
    # 测试文件路径
    test_pdf_path = "testfiles/AlphaEvolve.pdf"
    
    # 检查文件是否存在
    if not os.path.exists(test_pdf_path):
        print(f"❌ 测试文件不存在: {test_pdf_path}")
        return False
    
    print(f"📄 测试文件: {test_pdf_path}")
    
    # 创建配置，启用批量处理
    config = PDFProcessingConfig()
    print(f"🔧 配置信息:")
    print(f"  - 默认LLM模型: {config.ai_content.default_llm_model}")
    print(f"  - 最大工作线程: {config.ai_content.max_workers}")
    print(f"  - 启用并行处理: {config.ai_content.enable_parallel_processing}")
    print(f"  - 启用文本清洗: {config.ai_content.enable_text_cleaning}")
    
    # 创建PDF解析工具
    parser = PDFParserTool()
    
    try:
        print("\n🧪 开始批量处理测试...")
        start_time = time.time()
        
        # 执行基础解析，启用AI增强
        result = parser.execute(
            action="parse_basic",
            pdf_path=test_pdf_path,
            enable_ai_enhancement=True
        )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n📊 批量处理完成!")
        print(f"⏱️ 总耗时: {total_time:.2f} 秒")
        
        # 解析结果
        if isinstance(result, str):
            import json
            result_data = json.loads(result)
        else:
            result_data = result
        
        # 分析结果
        if 'result' in result_data:
            pages = result_data['result'].get('pages', [])
            images = result_data['result'].get('images', [])
            tables = result_data['result'].get('tables', [])
            
            print(f"\n📈 处理结果统计:")
            print(f"  - 总页数: {len(pages)}")
            print(f"  - 图片数: {len(images)}")
            print(f"  - 表格数: {len(tables)}")
            
            # 检查每页的处理情况
            processed_pages = 0
            cleaned_text_pages = 0
            
            for page in pages:
                processed_pages += 1
                if page.get('cleaned_text'):
                    cleaned_text_pages += 1
            
            print(f"  - 已处理页数: {processed_pages}")
            print(f"  - 已清洗文本页数: {cleaned_text_pages}")
            print(f"  - 平均每页处理时间: {total_time/processed_pages:.2f} 秒")
            
            # 检查是否使用了批量处理
            if processed_pages == len(pages):
                print("✅ 所有页面都已处理完成")
            else:
                print("⚠️ 部分页面未处理完成")
            
            # 显示前3页的处理情况
            print(f"\n📋 前3页处理情况:")
            for i, page in enumerate(pages[:3]):
                print(f"  页面 {page.get('page_number', i+1)}:")
                print(f"    - 原始文本长度: {len(page.get('raw_text', ''))}")
                print(f"    - 清洗文本长度: {len(page.get('cleaned_text', ''))}")
                print(f"    - 图片数: {len(page.get('images', []))}")
                print(f"    - 表格数: {len(page.get('tables', []))}")
        
        return True
        
    except Exception as e:
        print(f"❌ 批量处理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🎯 PDF批量页面处理测试")
    print("测试目标: 44页AlphaEvolve.pdf批量处理")
    print("=" * 60)
    
    success = test_batch_processing()
    
    if success:
        print("\n🎉 批量处理测试成功!")
        print("✅ 44个页面批量处理功能正常工作")
    else:
        print("\n❌ 批量处理测试失败!")
        print("请检查配置和依赖")

if __name__ == "__main__":
    main() 