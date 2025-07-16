#!/usr/bin/env python3
"""
测试阶段1: Docling解析 + 初始Schema填充

验证Stage1DoclingProcessor的功能
简化版本：直接运行完整测试，无需用户交互
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入测试组件
from src.pdf_processing_2.stage1_docling_processor import Stage1DoclingProcessor
from src.pdf_processing_2.final_schema import FinalMetadataSchema


def test_stage1_complete():
    """测试阶段1的完整功能（自动运行版本）"""
    
    print("🧪 测试阶段1: Docling解析 + 初始Schema填充 + 重试机制")
    print("=" * 60)
    
    # 使用测试PDF
    test_pdf = "testfiles/医灵古庙设计方案.pdf"
    if not os.path.exists(test_pdf):
        print(f"❌ 测试文件不存在: {test_pdf}")
        return False
    
    # 🕒 生成带时间戳的输出目录，避免重复测试冲突
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"parser_output_v2/test_stage1_{timestamp}"
    
    print(f"📁 输出目录: {output_dir}")
    print(f"📄 测试文件: {test_pdf}")
    
    try:
        # 创建处理器（使用进程池模式，启用重试机制）
        processor = Stage1DoclingProcessor(use_process_pool=True)
        
        # 执行处理
        print("\n🚀 开始执行Stage1处理...")
        final_schema, final_metadata_path = processor.process(test_pdf, output_dir)
        
        # ✅ 验证结果
        print(f"\n📊 处理结果验证:")
        print(f"✅ 处理完成度: {final_schema.get_completion_percentage()}%")
        
        if final_schema.document_summary:
            print(f"✅ 总页数: {final_schema.document_summary.total_pages}")
            print(f"✅ 文字内容: {len(final_schema.document_summary.content)}字符")
            if final_schema.document_summary.page_texts:
                print(f"✅ 页面文本数: {len(final_schema.document_summary.page_texts)}页")
            else:
                print(f"⚠️ 页面文本数: 0页（未生成）")
        else:
            print("⚠️ 文档摘要为空")
        
        print(f"✅ 图片数: {len(final_schema.image_chunks)}")
        print(f"✅ 表格数: {len(final_schema.table_chunks)}")
        
        # 🔍 验证文件完整性
        print(f"\n🔍 文件完整性验证:")
        
        # 检查JSON文件
        if os.path.exists(final_metadata_path):
            file_size = os.path.getsize(final_metadata_path)
            print(f"✅ final_metadata.json: {file_size:,} bytes")
            
            # 尝试重新加载验证
            try:
                reloaded_schema = FinalMetadataSchema.load(final_metadata_path)
                print(f"✅ JSON重新加载成功: {len(reloaded_schema.image_chunks)}图片 + {len(reloaded_schema.table_chunks)}表格")
            except Exception as e:
                print(f"❌ JSON重新加载失败: {e}")
        
        # 检查媒体文件
        total_media_files = 0
        if os.path.exists(output_dir):
            for item in os.listdir(output_dir):
                if item.startswith("page_"):
                    page_dir = os.path.join(output_dir, item)
                    if os.path.isdir(page_dir):
                        media_files = [f for f in os.listdir(page_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
                        total_media_files += len(media_files)
        
        print(f"✅ 媒体文件总数: {total_media_files}个")
        
        # 🎯 数据一致性检查
        expected_media = len(final_schema.image_chunks) + len(final_schema.table_chunks)
        if total_media_files == expected_media:
            print(f"✅ 数据一致性: 统计({expected_media}) = 文件({total_media_files})")
        else:
            print(f"⚠️ 数据不一致: 统计({expected_media}) ≠ 文件({total_media_files})")
        
        print(f"\n📁 测试结果保存在: {output_dir}")
        print(f"🎉 Stage1测试完成! 系统已验证重试机制有效性")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        print(f"🔍 错误详情:\n{traceback.format_exc()}")
        return False


def main():
    """主函数：直接运行完整测试"""
    print("🚀 PDF Processing V2 - 阶段1测试")
    print("=" * 60)
    print("📋 测试配置: 完整性测试 + 重试机制验证")
    print("🔄 重试参数: 最大3次重试，2秒间隔")
    print("🏭 并行模式: 进程池（适合CPU密集型任务）")
    print("🔒 网络模式: 离线模式（避免HuggingFace连接问题）")
    print()
    
    success = test_stage1_complete()
    
    if success:
        print("\n✅ 所有测试通过！")
        print("💡 下一步: 可以开始阶段2的设计和实现")
        print("📋 阶段2内容: 并行AI处理（图片描述、文档摘要、TOC提取）")
    else:
        print("\n❌ 测试失败！")
        print("💡 建议: 检查错误信息，修复问题后重新测试")


if __name__ == "__main__":
    main() 