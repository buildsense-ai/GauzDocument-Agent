#!/usr/bin/env python3
"""
测试阶段1: Docling解析 + 初始Schema填充

验证Stage1DoclingProcessor的功能
"""

import os
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入测试组件
from src.pdf_processing_2.stage1_docling_processor import Stage1DoclingProcessor
from src.pdf_processing_2.final_schema import FinalMetadataSchema


def test_stage1_complete():
    """测试阶段1的完整功能"""
    
    print("🧪 测试阶段1: Docling解析 + 初始Schema填充（完整性测试）")
    
    # 使用测试PDF
    test_pdf = "testfiles/测试文件.pdf"
    if not os.path.exists(test_pdf):
        print(f"❌ 测试文件不存在: {test_pdf}")
        return False
    
    # 设置输出目录
    output_dir = "parser_output_v2/test_stage1_complete"
    
    try:
        # 创建处理器（使用保守的并行设置）
        processor = Stage1DoclingProcessor(use_process_pool=True)
        
        # 执行处理
        print(f"📄 处理PDF: {test_pdf}")
        final_schema, final_metadata_path = processor.process(test_pdf, output_dir)
        
        # 详细验证结果
        print("\n📊 验证结果:")
        print(f"✅ Final metadata保存至: {final_metadata_path}")
        print(f"✅ Document ID: {final_schema.document_id}")
        print(f"✅ 处理状态: {final_schema.processing_status.current_stage}")
        print(f"✅ 完成度: {final_schema.get_completion_percentage()}%")
        
        # 验证document_summary
        if final_schema.document_summary:
            content_length = len(final_schema.document_summary.content)
            print(f"✅ 文档摘要: {content_length} 字符")
            print(f"✅ 总页数: {final_schema.document_summary.total_pages}")
            print(f"✅ 文件大小: {final_schema.document_summary.file_size} bytes")
            print(f"✅ 图片数量统计: {final_schema.document_summary.image_count}")
            print(f"✅ 表格数量统计: {final_schema.document_summary.table_count}")
            print(f"✅ 处理时间: {final_schema.document_summary.processing_time:.2f} 秒")
        else:
            print("❌ 文档摘要缺失")
            return False
        
        # 验证image_chunks
        image_count = len(final_schema.image_chunks)
        print(f"✅ 图片chunks: {image_count}个")
        if image_count > 0:
            for i, img in enumerate(final_schema.image_chunks[:3]):  # 显示前3个作为示例
                print(f"   🖼️ 图片{i+1}: 页面{img.page_number}, {img.width}x{img.height}, {img.caption}")
        
        # 验证table_chunks  
        table_count = len(final_schema.table_chunks)
        print(f"✅ 表格chunks: {table_count}个")
        if table_count > 0:
            for i, table in enumerate(final_schema.table_chunks[:3]):  # 显示前3个作为示例
                print(f"   📋 表格{i+1}: 页面{table.page_number}, {table.width}x{table.height}, {table.caption}")
        
        # 验证文件结构
        print(f"\n📁 验证输出文件结构:")
        if os.path.exists(final_metadata_path):
            file_size = os.path.getsize(final_metadata_path)
            print(f"✅ final_metadata.json: {file_size} bytes")
            
            # 验证JSON文件可以重新加载
            try:
                reloaded_schema = FinalMetadataSchema.load(final_metadata_path)
                print(f"✅ JSON重新加载成功: {reloaded_schema.document_id}")
                print(f"✅ 重新加载后图片数: {len(reloaded_schema.image_chunks)}")
                print(f"✅ 重新加载后表格数: {len(reloaded_schema.table_chunks)}")
            except Exception as e:
                print(f"❌ JSON重新加载失败: {e}")
                return False
        else:
            print(f"❌ final_metadata.json 文件不存在")
            return False
        
        # 检查页面输出目录
        page_dirs = [d for d in os.listdir(output_dir) if d.startswith('page_')]
        print(f"✅ 页面输出目录: {len(page_dirs)} 个")
        
        # 验证媒体文件
        total_images = 0
        total_tables = 0
        for page_dir in page_dirs:
            page_path = os.path.join(output_dir, page_dir)
            if os.path.isdir(page_path):
                files = os.listdir(page_path)
                images = [f for f in files if f.startswith('picture-')]
                tables = [f for f in files if f.startswith('table-')]
                total_images += len(images)
                total_tables += len(tables)
        
        print(f"✅ 实际媒体文件: {total_images}个图片, {total_tables}个表格")
        
        # 验证数据一致性
        if (final_schema.document_summary.image_count == image_count == total_images and
            final_schema.document_summary.table_count == table_count == total_tables):
            print("✅ 数据一致性检查通过")
        else:
            print(f"⚠️ 数据不一致: 统计({final_schema.document_summary.image_count}img, {final_schema.document_summary.table_count}table) vs 实际chunks({image_count}img, {table_count}table) vs 文件({total_images}img, {total_tables}table)")
        
        print(f"\n🎉 阶段1测试完成！处理了{final_schema.document_summary.total_pages}页PDF，生成{image_count}个图片和{table_count}个表格的metadata。")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行Stage1完整性测试"""
    
    print("🚀 PDF Processing V2 - 阶段1完整性测试")
    print("=" * 60)
    
    # 完整性测试
    test_result = test_stage1_complete()
    
    print("\n" + "=" * 60)
    print("📊 测试结果:")
    if test_result:
        print("🎉 阶段1完整性测试通过！")
        print("✨ Stage1处理器工作正常，可以继续开发Stage2")
    else:
        print("❌ 阶段1测试失败，需要修复问题")
    
    return test_result


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 