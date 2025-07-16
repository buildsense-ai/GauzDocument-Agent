#!/usr/bin/env python3
"""
Stage2智能处理器完整测试脚本
测试四个核心步骤：
- Step 2.1: 页面文本修复
- Step 2.2: 全局结构识别（TOC提取）
- Step 2.3: 内容提取与切分（章节切分）
- Step 2.4: 多模态描述生成
"""

import os
import sys
import json
import time
from pathlib import Path

# 添加项目根目录到path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.pdf_processing_2.stage2_intelligent_processor import Stage2IntelligentProcessor, process_stage2_from_file
from src.pdf_processing_2.final_schema import FinalMetadataSchema


def test_stage2_complete():
    """测试Stage2的完整处理流程"""
    print("🎯 测试Stage2完整处理功能...")
    
    # 测试路径
    metadata_path = "parser_output_v2/test_stage1_20250716_110158/final_metadata.json"
    
    if not os.path.exists(metadata_path):
        print(f"❌ 找不到测试文件: {metadata_path}")
        return False
    
    print(f"📄 使用测试文件: {metadata_path}")
    
    try:
        # 执行Stage2处理
        print("\n🚀 开始执行Stage2完整处理...")
        start_time = time.time()
        
        final_schema, output_path = process_stage2_from_file(metadata_path)
        
        processing_time = time.time() - start_time
        
        # 验证处理结果
        print(f"\n📊 Stage2处理结果验证:")
        print(f"✅ 处理时间: {processing_time:.2f}秒")
        print(f"✅ 输出文件: {output_path}")
        
        # 验证文档摘要和页面修复
        if final_schema.document_summary:
            print(f"✅ 文档总页数: {final_schema.document_summary.total_pages}")
            
            # 检查页面文本修复
            original_pages = len(final_schema.document_summary.page_texts) if final_schema.document_summary.page_texts else 0
            cleaned_pages = len(final_schema.document_summary.cleaned_page_texts) if final_schema.document_summary.cleaned_page_texts else 0
            print(f"✅ 原始页面文本: {original_pages}页")
            print(f"✅ 修复页面文本: {cleaned_pages}页")
            
            # 检查TOC提取结果
            if final_schema.document_summary.metadata and final_schema.document_summary.metadata.get('toc'):
                toc_items = final_schema.document_summary.metadata['toc']
                print(f"✅ TOC提取成功: {len(toc_items)}个章节")
                
                # 显示TOC结构
                print(f"📖 TOC结构预览:")
                for item in toc_items[:3]:  # 只显示前3个
                    indent = "  " * (item.get('level', 1) - 1)
                    print(f"  {indent}{item.get('level', 1)}. {item.get('title', '未知标题')}")
                if len(toc_items) > 3:
                    print(f"  ...（共{len(toc_items)}个章节）")
            else:
                print(f"⚠️ TOC提取结果: 未找到章节结构")
        else:
            print("⚠️ 文档摘要为空")
        
        # 验证文本分块结果
        print(f"✅ 文本分块数: {len(final_schema.text_chunks)}")
        if final_schema.text_chunks:
            # 显示分块预览
            print(f"📝 分块预览:")
            for i, chunk in enumerate(final_schema.text_chunks[:2]):  # 只显示前2个
                content_preview = chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content
                print(f"  块{i+1}: {chunk.chapter_id} ({chunk.word_count}字符)")
                print(f"       {content_preview}")
            if len(final_schema.text_chunks) > 2:
                print(f"  ...（共{len(final_schema.text_chunks)}个分块）")
        
        # 验证多模态描述
        print(f"✅ 图片数: {len(final_schema.image_chunks)}")
        print(f"✅ 表格数: {len(final_schema.table_chunks)}")
        
        # 检查结构化描述生成情况
        structured_images = sum(1 for img in final_schema.image_chunks if img.search_summary)
        structured_tables = sum(1 for table in final_schema.table_chunks if table.search_summary)
        
        print(f"✅ 结构化图片描述: {structured_images}/{len(final_schema.image_chunks)}")
        print(f"✅ 结构化表格描述: {structured_tables}/{len(final_schema.table_chunks)}")
        
        # 验证处理状态
        if final_schema.processing_status:
            print(f"✅ 处理阶段: {final_schema.processing_status.current_stage}")
            print(f"✅ 完成度: {final_schema.processing_status.completion_percentage}%")
        
        # 验证文件完整性
        print(f"\n🔍 文件完整性验证:")
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✅ final_metadata.json: {file_size:,} bytes")
            
            # 尝试重新加载验证
            try:
                reloaded_schema = FinalMetadataSchema.load(output_path)
                print(f"✅ JSON重新加载成功")
                print(f"   - {len(reloaded_schema.image_chunks)}个图片")
                print(f"   - {len(reloaded_schema.table_chunks)}个表格")
                print(f"   - {len(reloaded_schema.text_chunks)}个文本分块")
            except Exception as e:
                print(f"❌ JSON重新加载失败: {e}")
                return False
        else:
            print(f"❌ 输出文件不存在: {output_path}")
            return False
        
        print(f"\n✅ Stage2完整测试通过!")
        return True
        
    except Exception as e:
        print(f"❌ Stage2处理失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_step_by_step():
    """分步测试各个Stage2步骤"""
    print("\n🔍 分步测试Stage2各个步骤...")
    
    metadata_path = "parser_output_v2/test_stage1_20250716_110158/final_metadata.json"
    
    if not os.path.exists(metadata_path):
        print(f"❌ 找不到测试文件: {metadata_path}")
        return False
    
    try:
        # 加载数据
        final_schema = FinalMetadataSchema.load(metadata_path)
        processor = Stage2IntelligentProcessor()
        
        print(f"📖 原始数据状态:")
        print(f"   - 页面文本: {len(final_schema.document_summary.page_texts)}页" if final_schema.document_summary and final_schema.document_summary.page_texts else "   - 页面文本: 无")
        print(f"   - 图片: {len(final_schema.image_chunks)}个")
        print(f"   - 表格: {len(final_schema.table_chunks)}个")
        
        # Step 2.1 测试
        print(f"\n🔧 测试Step 2.1: 页面文本修复...")
        processor._process_step_2_1_text_repair(final_schema)
        cleaned_count = len(final_schema.document_summary.cleaned_page_texts) if final_schema.document_summary and final_schema.document_summary.cleaned_page_texts else 0
        print(f"   ✅ 修复页面数: {cleaned_count}")
        
        # Step 2.2 测试
        print(f"\n🗺️ 测试Step 2.2: 全局结构识别...")
        processor._process_step_2_2_toc_extraction(final_schema)
        toc_count = len(final_schema.document_summary.metadata.get('toc', [])) if final_schema.document_summary and final_schema.document_summary.metadata else 0
        print(f"   ✅ 识别章节数: {toc_count}")
        
        # Step 2.3 测试
        print(f"\n✂️ 测试Step 2.3: 内容提取与切分...")
        original_chunks = len(final_schema.text_chunks)
        processor._process_step_2_3_content_chunking(final_schema)
        new_chunks = len(final_schema.text_chunks) - original_chunks
        print(f"   ✅ 新增分块数: {new_chunks}")
        
        # Step 2.4 测试
        print(f"\n🖼️ 测试Step 2.4: 多模态描述生成...")
        processor._process_step_2_4_multimodal(final_schema)
        structured_images = sum(1 for img in final_schema.image_chunks if img.search_summary)
        print(f"   ✅ 结构化图片描述: {structured_images}/{len(final_schema.image_chunks)}")
        
        print(f"\n✅ 分步测试完成!")
        return True
        
    except Exception as e:
        print(f"❌ 分步测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数：运行完整测试套件"""
    print("🚀 PDF Processing V2 - Stage2智能处理器测试")
    print("=" * 60)
    print("📋 测试内容:")
    print("   - Step 2.1: 页面文本修复 (修正OCR错误)")
    print("   - Step 2.2: 全局结构识别 (TOC提取)")
    print("   - Step 2.3: 内容提取与切分 (章节分块)")
    print("   - Step 2.4: 多模态描述生成 (图片表格描述)")
    print()
    
    # 运行完整测试
    success = test_stage2_complete()
    
    if success:
        print("\n" + "="*50)
        print("✅ 所有测试通过！")
        print("💡 Stage2智能处理器功能正常")
        print("📋 下一步: 可以开始Stage3的设计和实现")
        print("🎯 Stage3内容: 高级内容分块优化（可选）")
    else:
        print("\n" + "="*50)
        print("❌ 测试失败！")
        print("💡 建议: 检查错误信息，修复问题后重新测试")
    
        # 运行分步测试帮助诊断问题
        print("\n🔍 运行分步测试进行诊断...")
        test_step_by_step()


if __name__ == "__main__":
    main() 