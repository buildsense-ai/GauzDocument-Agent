#!/usr/bin/env python3
"""
TOC转Markdown生成器 V2
将TOC提取V2结果转换为美观的Markdown目录
"""

import json
import os
from typing import Dict, List, Any

def generate_markdown_toc_v2(toc_json_path: str, output_path: str = None) -> str:
    """
    生成V2版本的Markdown格式的TOC
    
    Args:
        toc_json_path: TOC JSON文件路径
        output_path: 输出Markdown文件路径（可选）
        
    Returns:
        str: Markdown格式的TOC内容
    """
    # 读取TOC JSON
    with open(toc_json_path, 'r', encoding='utf-8') as f:
        toc_data = json.load(f)
    
    toc_items = toc_data.get('toc', [])
    total_chapters = toc_data.get('total_chapters', len(toc_items))
    
    # 构建Markdown内容
    markdown_lines = []
    
    # 添加标题
    markdown_lines.extend([
        "# 📚 医灵古庙设计方案 - 目录 (V2版本)",
        "",
        f"> **文档概览**：共 {total_chapters} 个章节，改进版TOC提取结果",
        "",
        "## 🎯 V2版本改进点",
        "- ✅ 去除页码噪音，文本更纯净",
        "- ✅ 简化章节ID为数字格式",
        "- ✅ 正确设置parent_id层级关系",
        "- ✅ 优化开头文本匹配片段",
        "",
        "---",
        ""
    ])
    
    # 添加目录
    markdown_lines.append("## 📖 目录结构")
    markdown_lines.append("")
    
    # 统计层级
    level_count = {}
    for item in toc_items:
        level = item.get('level', 1)
        level_count[level] = level_count.get(level, 0) + 1
    
    # 显示层级统计
    level_stats = []
    for level in sorted(level_count.keys()):
        count = level_count[level]
        level_icon = "📖" if level == 1 else "📄" if level == 2 else "📝"
        level_stats.append(f"{level_icon} {level}级: {count}个")
    
    markdown_lines.extend([
        f"> **层级统计**: {' | '.join(level_stats)}",
        ""
    ])
    
    # 生成目录列表
    for item in toc_items:
        title = item.get('title', '')
        level = item.get('level', 1)
        start_text = item.get('start_text', '')
        item_id = item.get('id', '')
        parent_id = item.get('parent_id')
        
        # 根据层级设置缩进和图标
        indent = "  " * (level - 1)
        icon = "📖" if level == 1 else "📄" if level == 2 else "📝"
        
        # 父级信息
        parent_info = f" ← `{parent_id}`" if parent_id else ""
        
        # 开头文本预览（限制长度）
        preview = start_text[:40] + "..." if len(start_text) > 40 else start_text
        
        # 生成目录行
        markdown_lines.append(f"{indent}{icon} **{title}** `[{item_id}]`{parent_info}")
        markdown_lines.append(f"{indent}   *{preview}*")
        markdown_lines.append("")
    
    # 添加详细匹配信息
    markdown_lines.extend([
        "---",
        "",
        "## 🔍 匹配信息详情",
        "",
        "以下是用于文本切割的精确匹配信息：",
        ""
    ])
    
    for item in toc_items:
        title = item.get('title', '')
        level = item.get('level', 1)
        start_text = item.get('start_text', '')
        item_id = item.get('id', '')
        parent_id = item.get('parent_id')
        
        # 根据层级设置标题格式
        level_marker = "#" * (level + 2)  # 从 ### 开始
        
        markdown_lines.extend([
            f"{level_marker} {title} `[ID: {item_id}]`",
            "",
            f"**父级ID**: `{parent_id if parent_id else 'null'}`",
            "",
            f"**匹配文本**:",
            f"```",
            start_text,
            f"```",
            ""
        ])
    
    # 合并所有行
    markdown_content = "\n".join(markdown_lines)
    
    # 保存到文件
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"✅ V2版本Markdown目录已保存到: {output_path}")
    
    return markdown_content

def main():
    """主函数"""
    # 输入和输出路径
    input_file = "parser_output/20250714_145102_zpdlfg/toc_extraction_result_v2.json"
    output_dir = os.path.dirname(input_file)
    
    if not os.path.exists(input_file):
        print(f"❌ 输入文件不存在: {input_file}")
        return
    
    # 生成不同版本的markdown
    versions = {
        "toc_v2_beautiful.md": "美观版V2目录",
        "toc_v2_detailed.md": "详细版V2目录"
    }
    
    for filename, description in versions.items():
        output_path = os.path.join(output_dir, filename)
        print(f"📝 正在生成{description}...")
        
        # 生成markdown
        markdown_content = generate_markdown_toc_v2(input_file, output_path)
        
        # 显示统计
        lines = markdown_content.split('\n')
        chars = len(markdown_content)
        print(f"   📊 {len(lines)} 行，{chars} 字符")
    
    print("\n🎉 所有V2版本目录生成完成!")

if __name__ == "__main__":
    main() 