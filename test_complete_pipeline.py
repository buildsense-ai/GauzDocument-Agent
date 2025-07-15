#!/usr/bin/env python3
"""
测试完整的PDF处理pipeline（包含metadata处理）
验证从PDF到完整metadata的端到端流程
"""

import sys
import os
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

def test_complete_pipeline():
    """测试完整的PDF处理流程"""
    
    print("🚀 测试完整的PDF处理流程（包含Metadata）...")
    
    # 测试文件
    test_pdf = "testfiles/医灵古庙设计方案.pdf"
    
    if not os.path.exists(test_pdf):
        print(f"❌ 测试文件不存在: {test_pdf}")
        return
    
    try:
        # 导入PDF解析工具
        from pdf_processing.pdf_parser_tool import PDFParserTool
        
        # 创建工具实例
        tool = PDFParserTool()
        
        print(f"📄 开始处理: {test_pdf}")
        
        # 使用page_split模式，包含所有处理步骤
        result_json = tool.execute(
            action="parse_page_split",
            pdf_path=test_pdf,
            enable_ai_enhancement=True,
            docling_parallel_processing=False,  # Mac上禁用
            ai_parallel_processing=True
        )
        
        # 解析结果
        result = json.loads(result_json)
        
        if result["status"] == "success":
            output_dir = result["output_directory"]
            print(f"✅ 处理成功！输出目录: {output_dir}")
            
            # 检查生成的文件
            expected_files = [
                "page_split_processing_result.json",
                "toc_extraction_result.json", 
                "chunks_result.json",
                "metadata/basic_metadata.json",
                "metadata/document_summary.json",
                "metadata/chapter_summaries.json",
                "metadata/derived_questions.json"
            ]
            
            print("\n📋 检查生成的文件:")
            for file_path in expected_files:
                full_path = os.path.join(output_dir, file_path)
                if os.path.exists(full_path):
                    print(f"  ✅ {file_path}")
                    
                    # 显示文件大小
                    size = os.path.getsize(full_path)
                    print(f"     大小: {size:,} 字节")
                    
                    # 如果是JSON文件，显示部分内容
                    if file_path.endswith('.json'):
                        with open(full_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, dict):
                                print(f"     键: {list(data.keys())}")
                            elif isinstance(data, list):
                                print(f"     数组长度: {len(data)}")
                else:
                    print(f"  ❌ {file_path} - 文件不存在")
            
            # 显示处理统计
            print(f"\n📊 处理统计:")
            print(f"  处理时间: {result.get('processing_time', 0):.2f} 秒")
            print(f"  页面数量: {result.get('pages_count', 0)}")
            print(f"  TOC章节: {result.get('toc_count', 0)}")
            print(f"  分块数量: {result.get('chunks_count', 0)}")
            
            # 检查metadata目录
            metadata_dir = os.path.join(output_dir, "metadata")
            if os.path.exists(metadata_dir):
                print(f"\n🗂️ Metadata目录内容:")
                for file in os.listdir(metadata_dir):
                    file_path = os.path.join(metadata_dir, file)
                    size = os.path.getsize(file_path)
                    print(f"  📄 {file} ({size:,} 字节)")
            
        else:
            print(f"❌ 处理失败: {result.get('message', '未知错误')}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_complete_pipeline() 