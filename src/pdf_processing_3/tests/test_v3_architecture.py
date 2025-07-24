"""
PDF Processing V3 架构测试

测试V3版本的基础功能：
- Schema对象创建和序列化
- 本地存储管理器
- 项目隔离功能
- 项目ID生成
"""

import asyncio
import json
from pathlib import Path
import tempfile
import shutil

from ..models.final_schema_v3 import (
    DocumentSummaryV3, 
    TextChunkV3, 
    ImageChunkV3, 
    FinalMetadataSchemaV3,
    generate_project_id,
    generate_content_id,
    generate_document_id
)
from ..storage.local_storage_manager import LocalStorageManager


def test_project_id_generation():
    """测试项目ID生成的最佳实践格式"""
    print("=== 测试项目ID生成 ===")
    
    # 生成多个项目ID示例
    project_ids = []
    for i in range(5):
        project_id = generate_project_id()
        project_ids.append(project_id)
        print(f"项目ID {i+1}: {project_id}")
    
    # 验证格式
    for pid in project_ids:
        parts = pid.split('_')
        assert len(parts) == 3, f"项目ID格式错误: {pid}"
        assert parts[0] == "proj", f"前缀错误: {pid}"
        assert len(parts[1]) == 8, f"日期格式错误: {pid}"
        assert len(parts[2]) == 4, f"随机后缀长度错误: {pid}"
    
    print("✅ 项目ID生成测试通过")
    print()


def test_schema_v3_creation():
    """测试V3 Schema对象创建和基本功能"""
    print("=== 测试V3 Schema创建 ===")
    
    # 生成测试数据
    project_id = generate_project_id("test")
    print(f"测试项目ID: {project_id}")
    
    # 创建DocumentSummary
    doc_summary = DocumentSummaryV3(
        rtr_project_id=project_id,
        rtr_source_path="testfiles/医灵古庙设计方案.pdf",
        rtr_file_name="医灵古庙设计方案.pdf",
        ana_total_pages=15,
        ana_file_size=2048000
    )
    
    print(f"DocumentSummary创建成功:")
    print(f"  - content_id: {doc_summary.content_id}")
    print(f"  - document_id: {doc_summary.rtr_document_id}")
    print(f"  - project_id: {doc_summary.rtr_project_id}")
    print(f"  - schema_version: {doc_summary.sys_schema_version}")
    
    # 创建TextChunk
    text_chunk = TextChunkV3(
        rtr_document_id=doc_summary.rtr_document_id,
        rtr_project_id=project_id,
        emb_content="这是一段测试文本内容，用于验证V3 Schema的功能。",
        rtr_mineru_chunk_id="chunk_001",
        rtr_sequence_index=0,
        ana_word_count=25
    )
    
    print(f"TextChunk创建成功:")
    print(f"  - content_id: {text_chunk.content_id}")
    print(f"  - mineru_chunk_id: {text_chunk.rtr_mineru_chunk_id}")
    print(f"  - 内容长度: {len(text_chunk.emb_content)}字符")
    
    # 创建ImageChunk
    image_chunk = ImageChunkV3(
        rtr_document_id=doc_summary.rtr_document_id,
        rtr_project_id=project_id,
        rtr_media_path="media/images/image_001.png",
        rtr_caption="测试图片",
        rtr_mineru_chunk_id="img_001",
        rtr_sequence_index=1,
        ana_width=800,
        ana_height=600
    )
    
    print(f"ImageChunk创建成功:")
    print(f"  - content_id: {image_chunk.content_id}")
    print(f"  - media_path: {image_chunk.rtr_media_path}")
    print(f"  - 尺寸: {image_chunk.ana_width}x{image_chunk.ana_height}")
    
    # 创建完整Schema
    schema = FinalMetadataSchemaV3(
        document_id=doc_summary.rtr_document_id,
        project_id=project_id,
        document_summary=doc_summary,
        text_chunks=[text_chunk],
        image_chunks=[image_chunk]
    )
    
    print(f"FinalMetadataSchemaV3创建成功:")
    print(f"  - document_id: {schema.document_id}")
    print(f"  - project_id: {schema.project_id}")
    print(f"  - schema_version: {schema.schema_version}")
    
    # 测试统计功能
    counts = schema.get_all_chunks_count()
    print(f"  - 块统计: {counts}")
    
    # 测试项目一致性验证
    is_consistent = schema.validate_project_consistency()
    print(f"  - 项目一致性: {'✅ 通过' if is_consistent else '❌ 失败'}")
    
    # 测试序列化
    schema_dict = schema.to_dict()
    print(f"  - 序列化成功，数据大小: {len(json.dumps(schema_dict))}字节")
    
    print("✅ V3 Schema创建测试通过")
    print()
    
    return schema


async def test_local_storage_manager():
    """测试本地存储管理器"""
    print("=== 测试本地存储管理器 ===")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="test_v3_storage_")
    print(f"临时存储目录: {temp_dir}")
    
    try:
        # 初始化存储管理器
        storage = LocalStorageManager(base_path=temp_dir)
        print("✅ 存储管理器初始化成功")
        
        # 创建测试Schema
        project_id = generate_project_id("storage_test")
        doc_summary = DocumentSummaryV3(
            rtr_project_id=project_id,
            rtr_source_path="test.pdf",
            rtr_file_name="test.pdf"
        )
        
        schema = FinalMetadataSchemaV3(
            document_id=doc_summary.rtr_document_id,
            project_id=project_id,
            document_summary=doc_summary
        )
        
        # 测试保存metadata
        saved_path = await storage.save_final_metadata(schema)
        print(f"✅ Metadata保存成功: {saved_path}")
        
        # 测试保存Mineru原始输出
        raw_output = {
            "task_id": "test_task_123",
            "document_info": {
                "total_pages": 10,
                "file_size": 1024000
            },
            "chunks": [
                {"type": "text", "content": "测试文本"},
                {"type": "image", "path": "test.png"}
            ]
        }
        
        raw_path = await storage.save_mineru_raw_output(
            raw_output, project_id, schema.document_id
        )
        print(f"✅ Mineru原始输出保存成功: {raw_path}")
        
        # 测试保存媒体文件
        test_image_data = b"fake_image_data_for_testing"
        media_path = await storage.save_media_file(
            test_image_data, "test_image.png", project_id, schema.document_id, "images"
        )
        print(f"✅ 媒体文件保存成功: {media_path}")
        
        # 测试列出项目和文档
        projects = storage.list_projects()
        print(f"✅ 项目列表: {projects}")
        
        documents = storage.list_documents(project_id)
        print(f"✅ 文档列表: {documents}")
        
        # 测试存储统计
        stats = storage.get_storage_stats()
        print(f"✅ 存储统计:")
        print(f"  - 总项目数: {stats['total_projects']}")
        print(f"  - 总文档数: {stats['total_documents']}")
        print(f"  - 总大小: {stats['total_size_mb']}MB")
        
        # 验证文件确实存在
        doc_path = storage.get_document_path(project_id, schema.document_id)
        metadata_file = doc_path / "v3_final_metadata.json"
        raw_output_file = doc_path / "mineru_raw_output.json"
        image_file = doc_path / "media" / "images" / "test_image.png"
        
        assert metadata_file.exists(), "Metadata文件未找到"
        assert raw_output_file.exists(), "原始输出文件未找到"
        assert image_file.exists(), "图片文件未找到"
        
        print("✅ 所有文件验证通过")
        print("✅ 本地存储管理器测试通过")
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)
        print(f"🧹 临时目录清理完成: {temp_dir}")
    
    print()


def test_project_isolation():
    """测试项目隔离功能"""
    print("=== 测试项目隔离功能 ===")
    
    # 创建两个不同项目的Schema
    project_a = generate_project_id("project_a")
    project_b = generate_project_id("project_b")
    
    print(f"项目A ID: {project_a}")
    print(f"项目B ID: {project_b}")
    
    # 项目A的Schema
    doc_a = DocumentSummaryV3(
        rtr_project_id=project_a,
        rtr_file_name="project_a_doc.pdf"
    )
    
    schema_a = FinalMetadataSchemaV3(
        document_id=doc_a.rtr_document_id,
        project_id=project_a,
        document_summary=doc_a
    )
    
    # 项目B的Schema
    doc_b = DocumentSummaryV3(
        rtr_project_id=project_b,
        rtr_file_name="project_b_doc.pdf"
    )
    
    schema_b = FinalMetadataSchemaV3(
        document_id=doc_b.rtr_document_id,
        project_id=project_b,
        document_summary=doc_b
    )
    
    # 验证项目隔离
    assert schema_a.project_id != schema_b.project_id, "项目ID应该不同"
    assert schema_a.document_id != schema_b.document_id, "文档ID应该不同"
    assert schema_a.validate_project_consistency(), "项目A一致性验证失败"
    assert schema_b.validate_project_consistency(), "项目B一致性验证失败"
    
    print("✅ 项目隔离验证通过")
    print(f"  - 项目A文档ID: {schema_a.document_id}")
    print(f"  - 项目B文档ID: {schema_b.document_id}")
    print("✅ 项目隔离功能测试通过")
    print()


async def main():
    """运行所有测试"""
    print("🚀 PDF Processing V3 架构测试开始")
    print("=" * 50)
    print()
    
    # 运行所有测试
    test_project_id_generation()
    schema = test_schema_v3_creation()
    await test_local_storage_manager()
    test_project_isolation()
    
    print("=" * 50)
    print("🎉 所有V3架构测试通过！")
    print()
    print("📋 项目ID格式最佳实践:")
    print("   格式: proj_YYYYMMDD_random4")
    print("   示例: proj_20250125_a8f3")
    print("   优点: 时间可读性 + 唯一性 + 简洁性")
    print()
    print("📁 本地存储目录结构:")
    print("   project_data/{project_id}/{document_id}/")
    print("   ├── v3_final_metadata.json")
    print("   ├── mineru_raw_output.json")
    print("   ├── process_data.json")
    print("   └── media/images|tables/")
    print()
    print("✅ V3架构已准备就绪，可以开始集成Mineru API！")


if __name__ == "__main__":
    asyncio.run(main()) 