#!/usr/bin/env python3
"""
简单的PDF处理测试脚本
包含基础处理和文档结构分析两个测试
"""
import sys
import os
import time
from datetime import datetime
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.pdf_processing.pdf_parser_tool import PDFParserTool
from src.pdf_processing.document_structure_analyzer import DocumentStructureAnalyzer
from src.pdf_processing.config import get_config, PDFProcessingConfig
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_basic_processing(test_file):
    """测试基础处理（包含媒体提取）"""
    logger.info("🚀 开始基础处理测试")
    logger.info("-" * 30)
    
    try:
        # 获取配置
        config = get_config()
        
        # 创建工具
        tool = PDFParserTool(config)
        
        # 执行基础处理
        start_time = time.time()
        result = tool.execute("parse_basic", pdf_path=test_file)
        end_time = time.time()
        
        if "error" in result:
            logger.error(f"❌ 处理失败: {result}")
            return False
        
        logger.info(f"✅ 基础处理完成")
        logger.info(f"⏱️ 处理时间: {end_time - start_time:.2f}秒")
        
        # 分析结果
        if "result" in result:
            result_data = result["result"]
            if "basic_processing_result" in result_data:
                basic_result = result_data["basic_processing_result"]
                if "pages" in basic_result:
                    pages = basic_result["pages"]
                    logger.info(f"📄 处理页数: {len(pages)}页")
                    
                    # 统计图片和表格
                    total_images = sum(len(page.get("images", [])) for page in pages)
                    total_tables = sum(len(page.get("tables", [])) for page in pages)
                    logger.info(f"🖼️ 图片数量: {total_images}")
                    logger.info(f"📊 表格数量: {total_tables}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 基础处理异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_document_structure_analysis(test_file):
    """测试文档结构分析（纯文本处理）"""
    logger.info("🔍 开始文档结构分析测试")
    logger.info("-" * 30)
    
    try:
        # 创建配置和分析器
        config = PDFProcessingConfig()
        analyzer = DocumentStructureAnalyzer(config)
        
        # 输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"parser_output/{timestamp}_integrated_test"
        os.makedirs(output_dir, exist_ok=True)
        
        # 执行分析
        start_time = time.time()
        document_structure, minimal_chunks = analyzer.analyze_and_chunk(
            pdf_path=test_file,
            output_dir=output_dir
        )
        end_time = time.time()
        
        logger.info(f"✅ 文档结构分析完成")
        logger.info(f"⏱️ 处理时间: {end_time - start_time:.2f}秒")
        logger.info(f"📖 文档结构: {len(document_structure.toc)} 个章节")
        logger.info(f"📄 分块数量: {len(minimal_chunks)} 个")
        logger.info(f"🚀 平均每分块: {(end_time - start_time) / len(minimal_chunks) * 1000:.2f}ms")
        
        # 输出章节信息
        for i, chapter in enumerate(document_structure.toc[:3]):  # 只显示前3个章节
            logger.info(f"  章节 {i+1}: {chapter.title[:50]}...")
        
        # 输出分块样例
        for i, chunk in enumerate(minimal_chunks[:3]):  # 只显示前3个分块
            logger.info(f"  分块 {i+1}: {chunk.content[:50]}...")
        
        # 输出文件信息
        logger.info(f"📁 输出目录: {output_dir}")
        for file in os.listdir(output_dir):
            file_path = os.path.join(output_dir, file)
            size = os.path.getsize(file_path)
            logger.info(f"  - {file}: {size} bytes")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 文档结构分析异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    logger.info("🎯 PDF处理集成测试")
    logger.info("=" * 50)
    
    # 测试文件路径
    test_file = "testfiles/医灵古庙设计方案.pdf"
    
    if not os.path.exists(test_file):
        logger.error(f"❌ 测试文件不存在: {test_file}")
        logger.info("=" * 50)
        logger.error("❌ 测试失败")
        return False
    
    logger.info(f"📋 测试文件: {test_file}")
    logger.info("=" * 50)
    
    # 测试结果
    results = []
    
    # 测试1: 基础处理（包含媒体提取）
    logger.info("🧪 测试1: 基础处理 (包含媒体提取)")
    result1 = test_basic_processing(test_file)
    results.append(("基础处理", result1))
    
    logger.info("=" * 50)
    
    # 测试2: 文档结构分析（纯文本处理）
    logger.info("🧪 测试2: 文档结构分析 (纯文本处理)")
    result2 = test_document_structure_analysis(test_file)
    results.append(("文档结构分析", result2))
    
    logger.info("=" * 50)
    
    # 汇总结果
    logger.info("📊 测试结果汇总:")
    all_passed = True
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"  {test_name}: {status}")
        if not result:
            all_passed = False
    
    logger.info("=" * 50)
    if all_passed:
        logger.info("🎉 所有测试通过！")
        logger.info("💡 架构说明:")
        logger.info("  - 基础处理: 包含页面级媒体提取（图片、表格）")
        logger.info("  - 文档结构分析: 专注于文本分块和章节结构")
        logger.info("  - 两者可以并行处理，各司其职")
    else:
        logger.error("❌ 部分测试失败")
    
    return all_passed

if __name__ == "__main__":
    main() 