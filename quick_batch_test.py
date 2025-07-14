#!/usr/bin/env python3
"""
快速批量处理测试
实时监控44页PDF的批量处理进度
"""

import sys
import os
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """主函数"""
    print("🎯 AlphaEvolve.pdf 44页批量处理测试")
    print("=" * 50)
    
    # 测试文件路径
    test_pdf_path = "testfiles/AlphaEvolve.pdf"
    
    # 检查文件是否存在
    if not os.path.exists(test_pdf_path):
        print(f"❌ 测试文件不存在: {test_pdf_path}")
        return
    
    print(f"📄 测试文件: {test_pdf_path}")
    
    try:
        from src.pdf_processing.pdf_parser_tool import PDFParserTool
        from src.pdf_processing.config import PDFProcessingConfig
        
        # 查看配置
        config = PDFProcessingConfig()
        print(f"🔧 配置信息:")
        print(f"  - 默认LLM: {config.ai_content.default_llm_model}")
        print(f"  - 最大工作线程: {config.ai_content.max_workers}")
        print(f"  - 启用并行处理: {config.ai_content.enable_parallel_processing}")
        
        # 创建PDF解析工具
        print("\n🚀 初始化PDF解析工具...")
        parser = PDFParserTool()
        
        print("✅ PDF解析工具初始化成功")
        print("🚀 开始解析...")
        
        start_time = time.time()
        
        # 执行基础解析
        result = parser.execute(
            action="parse_basic",
            pdf_path=test_pdf_path,
            enable_ai_enhancement=True
        )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n✅ 处理完成！")
        print(f"⏱️ 总耗时: {total_time:.2f} 秒")
        
        # 解析结果
        import json
        result_data = json.loads(result)
        
        if result_data["status"] == "success":
            pages = result_data["result"]["pages"]
            images = result_data["result"]["images"]
            tables = result_data["result"]["tables"]
            
            print(f"\n📊 处理结果:")
            print(f"  - 总页数: {len(pages)}")
            print(f"  - 图片数: {len(images)}")
            print(f"  - 表格数: {len(tables)}")
            print(f"  - 平均每页处理时间: {total_time/len(pages):.2f} 秒")
            
            # 检查批量处理效果
            cleaned_pages = sum(1 for page in pages if page.get("cleaned_text"))
            print(f"  - 已清洗文本的页数: {cleaned_pages}")
            
            # 显示前几页的处理情况
            print(f"\n📋 前5页处理情况:")
            for i, page in enumerate(pages[:5]):
                print(f"  页面 {page.get('page_number', i+1)}:")
                print(f"    - 原始文本: {len(page.get('raw_text', ''))} 字符")
                print(f"    - 清洗文本: {len(page.get('cleaned_text', ''))} 字符")
                print(f"    - 图片: {len(page.get('images', []))} 个")
                print(f"    - 表格: {len(page.get('tables', []))} 个")
            
            print(f"\n🎉 批量处理测试成功！")
            
        else:
            print(f"❌ 处理失败: {result_data.get('message', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 