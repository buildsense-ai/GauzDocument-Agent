#!/usr/bin/env python3
"""
文档摘要生成器
基于文档的各个部分生成文档级别的摘要
"""

import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from .metadata_schema import DocumentSummaryMetadata, DocumentType, create_content_id
from .text_chunker import ChunkingResult
from src.qwen_client import QwenClient


class DocumentSummaryGenerator:
    """文档摘要生成器"""
    
    def __init__(self, model: str = "qwen-plus"):
        """
        初始化文档摘要生成器
        
        Args:
            model: 使用的AI模型
        """
        self.client = QwenClient(model=model, temperature=0.3)
        self.model = model
        
    def generate_document_summary(self, 
                                document_info: Dict[str, Any],
                                chunking_result: ChunkingResult,
                                toc_data: Dict[str, Any],
                                image_count: int = 0,
                                table_count: int = 0) -> tuple[DocumentSummaryMetadata, str]:
        """
        生成文档摘要
        
        Args:
            document_info: 文档基础信息
            chunking_result: 分块结果
            toc_data: TOC数据
            image_count: 图片数量
            table_count: 表格数量
            
        Returns:
            DocumentSummaryMetadata: 文档摘要元数据
        """
        start_time = time.time()
        
        # 1. 收集文档统计信息
        stats = self._collect_document_stats(document_info, chunking_result, toc_data, image_count, table_count)
        
        # 2. 推断文档类型
        document_type = self._infer_document_type(document_info, toc_data, stats)
        
        # 3. 生成摘要内容
        summary_content = self._generate_summary_content(document_info, chunking_result, toc_data, stats)
        
        # 4. 创建DocumentSummaryMetadata
        processing_time = time.time() - start_time
        content_id = create_content_id(document_info["document_id"], "document_summary", 1)
        
        document_summary = DocumentSummaryMetadata(
            content_id=content_id,
            document_id=document_info["document_id"],
            document_type_id=document_type.type_id,
            source_file_path=document_info["source_file_path"],
            file_name=document_info["file_name"],
            file_size=self._get_file_size(document_info["source_file_path"]),
            total_pages=stats["total_pages"],
            total_word_count=stats["total_word_count"],
            chapter_count=stats["chapter_count"],
            image_count=image_count,
            table_count=table_count,
            processing_time=processing_time,
            created_at=datetime.now(),
            toc_root_id="1"  # 假设根节点ID为1
        )
        
        return document_summary, summary_content
    
    def _collect_document_stats(self, document_info: Dict[str, Any], 
                               chunking_result: ChunkingResult,
                               toc_data: Dict[str, Any],
                               image_count: int,
                               table_count: int) -> Dict[str, Any]:
        """收集文档统计信息"""
        
        # 计算总字数
        total_word_count = sum(chunk.word_count for chunk in chunking_result.minimal_chunks)
        
        # 章节统计
        chapter_count = len(chunking_result.first_level_chapters)
        
        stats = {
            "total_pages": document_info["total_pages"],
            "total_word_count": total_word_count,
            "chapter_count": chapter_count,
            "image_count": image_count,
            "table_count": table_count,
            "chunk_count": len(chunking_result.minimal_chunks),
            "avg_words_per_chapter": total_word_count // chapter_count if chapter_count > 0 else 0,
            "avg_words_per_page": total_word_count // document_info["total_pages"] if document_info["total_pages"] > 0 else 0
        }
        
        return stats
    
    def _infer_document_type(self, document_info: Dict[str, Any], 
                            toc_data: Dict[str, Any], 
                            stats: Dict[str, Any]) -> DocumentType:
        """推断文档类型"""
        
        file_name = document_info["file_name"].lower()
        toc_items = toc_data.get("toc_items", [])
        
        # 基于文件名的简单推断
        if any(keyword in file_name for keyword in ["设计方案", "设计", "方案"]):
            return DocumentType(
                type_id="design_proposal",
                type_name="设计方案",
                category="工程资料",
                description="建筑工程设计方案文档",
                typical_structure=["项目概况", "设计依据", "方案设计", "技术措施"],
                created_at=datetime.now()
            )
        elif any(keyword in file_name for keyword in ["评估", "报告", "分析"]):
            return DocumentType(
                type_id="assessment_report",
                type_name="评估报告",
                category="工程资料",
                description="工程项目评估报告",
                typical_structure=["项目背景", "评估内容", "分析结果", "建议措施"],
                created_at=datetime.now()
            )
        elif any(keyword in file_name for keyword in ["规范", "标准", "规程"]):
            return DocumentType(
                type_id="standard_specification",
                type_name="标准规范",
                category="标准规范",
                description="行业标准规范文档",
                typical_structure=["总则", "术语", "基本要求", "技术要求"],
                created_at=datetime.now()
            )
        else:
            return DocumentType(
                type_id="general_document",
                type_name="通用文档",
                category="通用资料",
                description="通用技术文档",
                typical_structure=["概述", "内容", "结论"],
                created_at=datetime.now()
            )
    
    def _generate_summary_content(self, document_info: Dict[str, Any],
                                 chunking_result: ChunkingResult,
                                 toc_data: Dict[str, Any],
                                 stats: Dict[str, Any]) -> str:
        """生成摘要内容"""
        
        # 准备输入数据
        chapters_info = []
        for chapter in chunking_result.first_level_chapters:
            chapters_info.append({
                "title": chapter.title,
                "word_count": chapter.word_count,
                "content_preview": chapter.content[:200] + "..." if len(chapter.content) > 200 else chapter.content
            })
        
        # 构建提示词
        prompt = self._build_summary_prompt(document_info, chapters_info, stats)
        
        try:
            # 调用AI生成摘要
            summary_content = self.client.generate_response(prompt)
            
            # 后处理摘要内容
            summary_content = self._post_process_summary(summary_content)
            
            return summary_content
            
        except Exception as e:
            print(f"⚠️ 生成文档摘要时发生错误: {e}")
            # 返回基础摘要
            return self._generate_basic_summary(document_info, stats)
    
    def _build_summary_prompt(self, document_info: Dict[str, Any], 
                             chapters_info: List[Dict[str, Any]], 
                             stats: Dict[str, Any]) -> str:
        """构建摘要生成提示词"""
        
        chapters_text = "\n".join([
            f"- {chapter['title']} ({chapter['word_count']}字)\n  内容预览: {chapter['content_preview']}"
            for chapter in chapters_info
        ])
        
        prompt = f"""
请为以下文档生成一个综合性摘要：

## 文档基本信息
- 文档名称: {document_info['file_name']}
- 总页数: {stats['total_pages']}页
- 总字数: {stats['total_word_count']}字
- 章节数: {stats['chapter_count']}章
- 图片数: {stats['image_count']}张
- 表格数: {stats['table_count']}个

## 章节结构
{chapters_text}

## 要求
请生成一个200-300字的文档摘要，包含以下内容：
1. 文档的主要目的和性质
2. 核心内容概括
3. 主要章节的重点内容
4. 文档的价值和适用范围

请用专业、简洁的语言，确保摘要准确反映文档的核心内容。
"""
        
        return prompt
    
    def _post_process_summary(self, summary_content: str) -> str:
        """后处理摘要内容"""
        # 移除多余的空行
        lines = [line.strip() for line in summary_content.split('\n') if line.strip()]
        return '\n'.join(lines)
    
    def _generate_basic_summary(self, document_info: Dict[str, Any], stats: Dict[str, Any]) -> str:
        """生成基础摘要（当AI生成失败时使用）"""
        return f"""
{document_info['file_name']} 是一份包含{stats['total_pages']}页、{stats['chapter_count']}个章节的技术文档。
文档总字数约{stats['total_word_count']}字，包含{stats['image_count']}张图片和{stats['table_count']}个表格。
该文档按章节结构组织，涵盖了项目的各个方面，为相关工作提供了详细的技术指导和参考资料。
"""
    
    def _get_file_size(self, file_path: str) -> int:
        """获取文件大小"""
        try:
            return os.path.getsize(file_path)
        except:
            return 0
    
    def save_document_summary(self, summary_metadata: DocumentSummaryMetadata, 
                            summary_content: str, output_dir: str):
        """
        保存文档摘要
        
        Args:
            summary_metadata: 摘要元数据
            summary_content: 摘要内容
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存元数据
        metadata_file = os.path.join(output_dir, "document_summary_metadata.json")
        metadata_dict = {
            "content_id": summary_metadata.content_id,
            "document_id": summary_metadata.document_id,
            "document_type_id": summary_metadata.document_type_id,
            "source_file_path": summary_metadata.source_file_path,
            "file_name": summary_metadata.file_name,
            "file_size": summary_metadata.file_size,
            "total_pages": summary_metadata.total_pages,
            "total_word_count": summary_metadata.total_word_count,
            "chapter_count": summary_metadata.chapter_count,
            "image_count": summary_metadata.image_count,
            "table_count": summary_metadata.table_count,
            "processing_time": summary_metadata.processing_time,
            "created_at": summary_metadata.created_at.isoformat(),
            "toc_root_id": summary_metadata.toc_root_id
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
        
        # 保存摘要内容
        content_file = os.path.join(output_dir, "document_summary_content.txt")
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(summary_content)
        
        print(f"📄 文档摘要已保存:")
        print(f"   - 元数据: {metadata_file}")
        print(f"   - 内容: {content_file}")
        print(f"   - 处理时间: {summary_metadata.processing_time:.2f}秒") 