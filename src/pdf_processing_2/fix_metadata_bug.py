#!/usr/bin/env python3
"""
Metadata Bug Fix Script

修复现有metadata文件中的几个问题：
1. 图片chunks中的detailed_description字段包含JSON字符串而非纯文本
2. 移除已废弃的字段（page_number, page_range）
3. 确保所有字段都正确格式化

Usage:
    python fix_metadata_bug.py <metadata_file_path>
"""

import json
import re
import argparse
from pathlib import Path
from typing import Dict, Any, Optional


def extract_json_from_markdown(text: str) -> Optional[Dict[str, Any]]:
    """从markdown格式的JSON字符串中提取实际的JSON对象"""
    if not text:
        return None
    
    try:
        # 直接尝试解析
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 查找 ```json ... ``` 或 ``` ... ``` 格式
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # 查找第一个 { 到最后一个 } 之间的内容
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        json_str = brace_match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    return None


def fix_image_chunk(image_chunk: Dict[str, Any]) -> bool:
    """修复单个图片chunk的描述字段"""
    fixed = False
    
    # 检查detailed_description字段是否包含JSON字符串
    detailed_desc = image_chunk.get('detailed_description')
    if detailed_desc and isinstance(detailed_desc, str):
        extracted_json = extract_json_from_markdown(detailed_desc)
        if extracted_json:
            # 提取各个字段
            search_summary = extracted_json.get('search_summary')
            detailed_description = extracted_json.get('detailed_description')
            engineering_details = extracted_json.get('engineering_details')
            
            # 更新字段
            if search_summary and search_summary != "AI生成的图片描述":
                image_chunk['search_summary'] = search_summary
                fixed = True
            
            if detailed_description:
                image_chunk['detailed_description'] = detailed_description
                fixed = True
            
            if engineering_details is not None:
                image_chunk['engineering_details'] = engineering_details
                fixed = True
            
            if fixed:
                print(f"✅ 修复图片 {image_chunk.get('content_id', 'unknown')}")
    
    return fixed


def remove_deprecated_fields(data: Dict[str, Any]) -> int:
    """移除已废弃的字段"""
    removed_count = 0
    
    # 移除text_chunks中的page_number字段
    text_chunks = data.get('text_chunks', [])
    for chunk in text_chunks:
        if 'page_number' in chunk:
            del chunk['page_number']
            removed_count += 1
    
    # 移除chapter_summaries中的page_range字段
    chapter_summaries = data.get('chapter_summaries', [])
    for chapter in chapter_summaries:
        if 'page_range' in chapter:
            del chapter['page_range']
            removed_count += 1
    
    return removed_count


def fix_metadata_file(file_path: str, output_path: Optional[str] = None) -> None:
    """修复metadata文件"""
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        raise FileNotFoundError(f"文件不存在: {file_path_obj}")
    
    print(f"📖 读取metadata文件: {file_path_obj}")
    
    # 读取原文件
    with open(file_path_obj, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 统计修复情况
    fixed_images = 0
    
    # 修复图片chunks
    image_chunks = data.get('image_chunks', [])
    for image_chunk in image_chunks:
        if fix_image_chunk(image_chunk):
            fixed_images += 1
    
    # 移除废弃字段
    removed_fields = remove_deprecated_fields(data)
    
    # 移除document_summary中的metadata字段（如果存在）
    doc_summary = data.get('document_summary', {})
    if 'metadata' in doc_summary:
        del doc_summary['metadata']
        removed_fields += 1
        print("✅ 移除document_summary.metadata字段")
    
    # 确定输出路径
    if output_path is None:
        output_path_obj = file_path_obj.parent / f"{file_path_obj.stem}_fixed{file_path_obj.suffix}"
    else:
        output_path_obj = Path(output_path)
    
    # 写入修复后的文件
    with open(output_path_obj, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 修复后的文件已保存到: {output_path_obj}")
    print(f"📊 修复统计:")
    print(f"  - 修复的图片: {fixed_images}")
    print(f"  - 移除的废弃字段: {removed_fields}")
    
    if fixed_images > 0 or removed_fields > 0:
        print("✅ 修复完成!")
    else:
        print("ℹ️  没有发现需要修复的问题")


def main():
    parser = argparse.ArgumentParser(description="修复PDF处理metadata文件中的bug")
    parser.add_argument("metadata_file", help="要修复的metadata文件路径")
    parser.add_argument("-o", "--output", help="输出文件路径（默认为原文件名加_fixed后缀）")
    
    args = parser.parse_args()
    
    try:
        fix_metadata_file(args.metadata_file, args.output)
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 