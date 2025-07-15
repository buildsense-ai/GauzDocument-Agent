#!/usr/bin/env python3
"""
测试Metadata Pipeline
验证所有新的metadata组件能否正常工作
"""

import os
import json
import time
from pathlib import Path

# 导入新的组件
from src.pdf_processing.metadata_extractor import MetadataExtractor
from src.pdf_processing.document_summary_generator import DocumentSummaryGenerator
from src.pdf_processing.chapter_summary_generator import ChapterSummaryGenerator
from src.pdf_processing.question_generator import QuestionGenerator
from src.pdf_processing.toc_extractor import TOCExtractor
from src.pdf_processing.text_chunker import TextChunker


def test_metadata_pipeline():
    """测试完整的metadata pipeline"""
    
    print("🚀 开始测试Metadata Pipeline...")
    print("=" * 60)
    
    # 使用最新的输出结果
    page_split_file = "parser_output/20250715_131307_page_split/page_split_processing_result.json"
    toc_file = "parser_output/20250715_131307_page_split/toc_test_result.json"
    chunks_file = "parser_output/20250715_131307_page_split/chunks_test_result.json"
    
    # 验证输入文件存在
    required_files = [page_split_file, toc_file, chunks_file]
    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"❌ 输入文件不存在: {file_path}")
            return
    
    # 创建输出目录
    output_dir = Path("parser_output/metadata_test")
    output_dir.mkdir(exist_ok=True)
    
    # 1. 测试MetadataExtractor
    print("\n📊 测试MetadataExtractor...")
    test_metadata_extractor(page_split_file, toc_file, chunks_file, output_dir)
    
    # 2. 测试DocumentSummaryGenerator
    print("\n📄 测试DocumentSummaryGenerator...")
    test_document_summary_generator(page_split_file, toc_file, chunks_file, output_dir)
    
    # 3. 测试ChapterSummaryGenerator
    print("\n📚 测试ChapterSummaryGenerator...")
    test_chapter_summary_generator(page_split_file, toc_file, chunks_file, output_dir)
    
    # 4. 测试QuestionGenerator
    print("\n❓ 测试QuestionGenerator...")
    test_question_generator(page_split_file, toc_file, chunks_file, output_dir)
    
    print("\n✅ 所有测试完成！")
    print(f"📁 结果保存在: {output_dir}")


def test_metadata_extractor(page_split_file, toc_file, chunks_file, output_dir):
    """测试MetadataExtractor"""
    
    try:
        # 初始化extractor
        extractor = MetadataExtractor(project_name="医灵古庙项目")
        
        # 从page_split结果提取基础信息
        base_info = extractor.extract_from_page_split_result(page_split_file)
        document_id = base_info["document_info"]["document_id"]
        
        print(f"📋 文档ID: {document_id}")
        print(f"📄 总页数: {base_info['document_info']['total_pages']}")
        print(f"🖼️ 图片数: {len(base_info['image_metadata'])}")
        print(f"📊 表格数: {len(base_info['table_metadata'])}")
        
        # 从TOC结果提取信息
        doc_toc, chapter_mapping = extractor.extract_from_toc_result(toc_file, document_id)
        
        print(f"📖 章节数: {doc_toc.chapter_count}")
        print(f"📋 总目录项: {doc_toc.total_sections}")
        
        # 从chunks结果提取信息
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        
        # 模拟ChunkingResult（简化版）
        from src.pdf_processing.text_chunker import ChunkingResult, ChapterContent, MinimalChunk
        
        chapters = []
        chunks = []
        
        for chapter_data in chunks_data.get("first_level_chapters", []):
            chapter = ChapterContent(
                chapter_id=chapter_data["chapter_id"],
                title=chapter_data["title"],
                content=chapter_data["content"],
                start_pos=chapter_data["start_pos"],
                end_pos=chapter_data["end_pos"],
                word_count=chapter_data["word_count"],
                has_images=chapter_data.get("has_images", False),
                has_tables=chapter_data.get("has_tables", False)
            )
            chapters.append(chapter)
        
        for chunk_data in chunks_data.get("minimal_chunks", []):
            chunk = MinimalChunk(
                chunk_id=chunk_data["chunk_id"],
                content=chunk_data["content"],
                chunk_type=chunk_data["chunk_type"],
                belongs_to_chapter=chunk_data["belongs_to_chapter"],
                chapter_title=chunk_data["chapter_title"],
                start_pos=chunk_data["start_pos"],
                end_pos=chunk_data["end_pos"],
                word_count=chunk_data["word_count"]
            )
            chunks.append(chunk)
        
        chunking_result = ChunkingResult(
            first_level_chapters=chapters,
            minimal_chunks=chunks,
            total_chapters=len(chapters),
            total_chunks=len(chunks),
            processing_metadata={}
        )
        
        # 建立章节映射
        extractor.map_chapters_to_content(
            base_info['image_metadata'],
            base_info['table_metadata'],
            chapter_mapping,
            base_info['page_split_data']
        )
        
        # 提取文本chunk元数据
        text_chunks = extractor.extract_from_chunking_result(chunking_result, document_id, chapter_mapping)
        
        print(f"🔤 文本chunks: {len(text_chunks)}")
        
        # 保存提取结果
        extractor.save_extracted_metadata(
            str(output_dir / "extractor"),
            document_info=base_info["document_info"],
            doc_toc=doc_toc,
            chapter_mapping=chapter_mapping,
            image_metadata=base_info['image_metadata'],
            table_metadata=base_info['table_metadata'],
            text_chunks=text_chunks
        )
        
        print("✅ MetadataExtractor测试完成")
        
        # 返回数据给后续测试使用
        return {
            "document_id": document_id,
            "document_info": base_info["document_info"],
            "chunking_result": chunking_result,
            "chapter_mapping": chapter_mapping,
            "image_metadata": base_info['image_metadata'],
            "table_metadata": base_info['table_metadata']
        }
        
    except Exception as e:
        print(f"❌ MetadataExtractor测试失败: {e}")
        return None


def test_document_summary_generator(page_split_file, toc_file, chunks_file, output_dir):
    """测试DocumentSummaryGenerator"""
    
    try:
        # 复用extractor的结果
        extractor = MetadataExtractor(project_name="医灵古庙项目")
        base_info = extractor.extract_from_page_split_result(page_split_file)
        doc_toc, chapter_mapping = extractor.extract_from_toc_result(toc_file, base_info["document_info"]["document_id"])
        
        # 模拟chunking_result
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        
        from src.pdf_processing.text_chunker import ChunkingResult, ChapterContent, MinimalChunk
        
        chapters = []
        chunks = []
        
        for chapter_data in chunks_data.get("first_level_chapters", []):
            chapter = ChapterContent(
                chapter_id=chapter_data["chapter_id"],
                title=chapter_data["title"],
                content=chapter_data["content"],
                start_pos=chapter_data["start_pos"],
                end_pos=chapter_data["end_pos"],
                word_count=chapter_data["word_count"],
                has_images=chapter_data.get("has_images", False),
                has_tables=chapter_data.get("has_tables", False)
            )
            chapters.append(chapter)
        
        for chunk_data in chunks_data.get("minimal_chunks", []):
            chunk = MinimalChunk(
                chunk_id=chunk_data["chunk_id"],
                content=chunk_data["content"],
                chunk_type=chunk_data["chunk_type"],
                belongs_to_chapter=chunk_data["belongs_to_chapter"],
                chapter_title=chunk_data["chapter_title"],
                start_pos=chunk_data["start_pos"],
                end_pos=chunk_data["end_pos"],
                word_count=chunk_data["word_count"]
            )
            chunks.append(chunk)
        
        chunking_result = ChunkingResult(
            first_level_chapters=chapters,
            minimal_chunks=chunks,
            total_chapters=len(chapters),
            total_chunks=len(chunks),
            processing_metadata={}
        )
        
        # 初始化生成器
        generator = DocumentSummaryGenerator(model="qwen-plus")
        
        # 生成文档摘要
        doc_summary, summary_content = generator.generate_document_summary(
            base_info["document_info"],
            chunking_result,
            {"toc_items": json.loads(doc_toc.toc_json)},
            len(base_info['image_metadata']),
            len(base_info['table_metadata'])
        )
        
        print(f"📄 文档摘要已生成")
        print(f"📊 处理时间: {doc_summary.processing_time:.2f}秒")
        print(f"📝 摘要预览: {summary_content[:100]}...")
        
        # 保存摘要
        generator.save_document_summary(doc_summary, summary_content, str(output_dir / "document_summary"))
        
        print("✅ DocumentSummaryGenerator测试完成")
        
    except Exception as e:
        print(f"❌ DocumentSummaryGenerator测试失败: {e}")


def test_chapter_summary_generator(page_split_file, toc_file, chunks_file, output_dir):
    """测试ChapterSummaryGenerator"""
    
    try:
        # 复用extractor的结果
        extractor = MetadataExtractor(project_name="医灵古庙项目")
        base_info = extractor.extract_from_page_split_result(page_split_file)
        doc_toc, chapter_mapping = extractor.extract_from_toc_result(toc_file, base_info["document_info"]["document_id"])
        
        # 模拟chunking_result
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        
        from src.pdf_processing.text_chunker import ChunkingResult, ChapterContent, MinimalChunk
        
        chapters = []
        chunks = []
        
        for chapter_data in chunks_data.get("first_level_chapters", []):
            chapter = ChapterContent(
                chapter_id=chapter_data["chapter_id"],
                title=chapter_data["title"],
                content=chapter_data["content"],
                start_pos=chapter_data["start_pos"],
                end_pos=chapter_data["end_pos"],
                word_count=chapter_data["word_count"],
                has_images=chapter_data.get("has_images", False),
                has_tables=chapter_data.get("has_tables", False)
            )
            chapters.append(chapter)
        
        for chunk_data in chunks_data.get("minimal_chunks", []):
            chunk = MinimalChunk(
                chunk_id=chunk_data["chunk_id"],
                content=chunk_data["content"],
                chunk_type=chunk_data["chunk_type"],
                belongs_to_chapter=chunk_data["belongs_to_chapter"],
                chapter_title=chunk_data["chapter_title"],
                start_pos=chunk_data["start_pos"],
                end_pos=chunk_data["end_pos"],
                word_count=chunk_data["word_count"]
            )
            chunks.append(chunk)
        
        chunking_result = ChunkingResult(
            first_level_chapters=chapters,
            minimal_chunks=chunks,
            total_chapters=len(chapters),
            total_chunks=len(chunks),
            processing_metadata={}
        )
        
        # 初始化生成器
        generator = ChapterSummaryGenerator(model="qwen-plus")
        
        # 准备图片和表格元数据
        image_metadata = [{"chapter_id": str(i % 6 + 1)} for i in range(len(base_info['image_metadata']))]
        table_metadata = [{"chapter_id": str(i % 6 + 1)} for i in range(len(base_info['table_metadata']))]
        
        # 生成章节摘要
        chapter_summaries = generator.generate_chapter_summaries(
            base_info["document_info"]["document_id"],
            chunking_result,
            {"toc_items": json.loads(doc_toc.toc_json)},
            image_metadata,
            table_metadata,
            parallel_processing=True
        )
        
        print(f"📚 章节摘要已生成: {len(chapter_summaries)}个")
        
        # 保存摘要
        generator.save_chapter_summaries(chapter_summaries, str(output_dir / "chapter_summaries"))
        
        print("✅ ChapterSummaryGenerator测试完成")
        
    except Exception as e:
        print(f"❌ ChapterSummaryGenerator测试失败: {e}")


def test_question_generator(page_split_file, toc_file, chunks_file, output_dir):
    """测试QuestionGenerator"""
    
    try:
        # 复用extractor的结果
        extractor = MetadataExtractor(project_name="医灵古庙项目")
        base_info = extractor.extract_from_page_split_result(page_split_file)
        doc_toc, chapter_mapping = extractor.extract_from_toc_result(toc_file, base_info["document_info"]["document_id"])
        
        # 模拟chunking_result
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        
        from src.pdf_processing.text_chunker import ChunkingResult, ChapterContent, MinimalChunk
        
        chapters = []
        chunks = []
        
        for chapter_data in chunks_data.get("first_level_chapters", []):
            chapter = ChapterContent(
                chapter_id=chapter_data["chapter_id"],
                title=chapter_data["title"],
                content=chapter_data["content"],
                start_pos=chapter_data["start_pos"],
                end_pos=chapter_data["end_pos"],
                word_count=chapter_data["word_count"],
                has_images=chapter_data.get("has_images", False),
                has_tables=chapter_data.get("has_tables", False)
            )
            chapters.append(chapter)
        
        for chunk_data in chunks_data.get("minimal_chunks", []):
            chunk = MinimalChunk(
                chunk_id=chunk_data["chunk_id"],
                content=chunk_data["content"],
                chunk_type=chunk_data["chunk_type"],
                belongs_to_chapter=chunk_data["belongs_to_chapter"],
                chapter_title=chunk_data["chapter_title"],
                start_pos=chunk_data["start_pos"],
                end_pos=chunk_data["end_pos"],
                word_count=chunk_data["word_count"]
            )
            chunks.append(chunk)
        
        chunking_result = ChunkingResult(
            first_level_chapters=chapters,
            minimal_chunks=chunks,
            total_chapters=len(chapters),
            total_chunks=len(chunks),
            processing_metadata={}
        )
        
        # 初始化生成器
        generator = QuestionGenerator(model="qwen-turbo")
        
        # 生成问题（限制数量以节省时间）
        questions = generator.generate_questions_from_chunks(
            base_info["document_info"]["document_id"],
            chunking_result,
            chapter_mapping,
            questions_per_chunk=2,
            parallel_processing=True
        )
        
        print(f"❓ 派生问题已生成: {len(questions)}个")
        
        # 保存问题
        generator.save_derived_questions(questions, str(output_dir / "derived_questions"))
        
        print("✅ QuestionGenerator测试完成")
        
    except Exception as e:
        print(f"❌ QuestionGenerator测试失败: {e}")


if __name__ == "__main__":
    test_metadata_pipeline() 