#!/usr/bin/env python3
"""
简化版批量处理测试
专门测试AlphaEvolve.pdf的44页批量处理
"""

import sys
import os
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_batch_processing():
    """测试批量处理功能"""
    print("🚀 开始44页PDF批量处理测试...")
    
    # 测试文件路径
    test_pdf_path = "testfiles/AlphaEvolve.pdf"
    
    # 检查文件是否存在
    if not os.path.exists(test_pdf_path):
        print(f"❌ 测试文件不存在: {test_pdf_path}")
        return False
    
    print(f"📄 测试文件: {test_pdf_path}")
    
    try:
        from src.pdf_processing.pdf_parser_tool import PDFParserTool
        
        # 创建PDF解析工具
        parser = PDFParserTool()
        
        print("✅ PDF解析工具初始化成功")
        print("🚀 开始解析...")
        
        start_time = time.time()
        
        # 执行基础解析，启用AI增强
        result = parser.execute(
            action="parse_basic",
            pdf_path=test_pdf_path,
            enable_ai_enhancement=True
        )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n✅ 处理完成！总耗时: {total_time:.2f} 秒")
        
        # 简单分析结果
        import json
        result_data = json.loads(result)
        
        if result_data["status"] == "success":
            pages = result_data["result"]["pages"]
            print(f"📊 成功处理 {len(pages)} 页")
            print(f"⚡ 平均每页处理时间: {total_time/len(pages):.2f} 秒")
            
            # 检查批量处理效果
            cleaned_pages = sum(1 for page in pages if page.get("cleaned_text"))
            print(f"🧹 已清洗文本的页数: {cleaned_pages}")
            
            return True
        else:
            print(f"❌ 处理失败: {result_data.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_batch_processing()
    
    if success:
        print("\n🎉 批量处理测试成功！")
    else:
        print("\n❌ 批量处理测试失败！") 