#!/usr/bin/env python3
"""
TOC转Markdown生成器
将TOC提取结果转换为美观的Markdown目录
"""

import json
import os
from typing import Dict, List, Any

def generate_markdown_toc(toc_json_path: str, output_path: str = None) -> str:
    """
    生成Markdown格式的TOC
    
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
        "# 📚 医灵古庙设计方案 - 目录",
        "",
        f"> **文档概览**：共 {total_chapters} 个章节，31 页内容",
        "",
        "---",
        ""
    ])
    
    # 生成目录项
    for i, item in enumerate(toc_items, 1):
        title = item.get('title', '')
        level = item.get('level', 1)
        page_number = item.get('page_number', '')
        start_text = item.get('start_text', '')
        
        # 根据层级生成缩进
        indent = "  " * (level - 1)
        
        # 生成编号
        if level == 1:
            number = f"{i:02d}."
        else:
            number = f"{i:02d}."
        
        # 生成层级图标
        if level == 1:
            icon = "📖"
        elif level == 2:
            icon = "📄"
        else:
            icon = "📝"
        
        # 构建目录行
        if page_number:
            toc_line = f"{indent}{icon} **{title}** ............................ *第 {page_number} 页*"
        else:
            toc_line = f"{indent}{icon} **{title}**"
        
        markdown_lines.append(toc_line)
        
        # 添加开头文本预览（仅一级标题）
        if level == 1 and start_text:
            preview_text = start_text[:80] + "..." if len(start_text) > 80 else start_text
            markdown_lines.append(f"{indent}   > *{preview_text}*")
        
        markdown_lines.append("")
    
    # 添加页脚
    markdown_lines.extend([
        "---",
        "",
        "## 📋 文档结构统计",
        "",
        f"- **总页数**: 31 页",
        f"- **总章节**: {total_chapters} 个",
        f"- **一级章节**: {len([item for item in toc_items if item.get('level') == 1])} 个",
        f"- **二级章节**: {len([item for item in toc_items if item.get('level') == 2])} 个",
        f"- **三级章节**: {len([item for item in toc_items if item.get('level') == 3])} 个",
        "",
        "---",
        "",
        f"*📅 生成时间: {toc_data.get('extraction_time', 'N/A')}*",
        "",
        "**🔄 处理说明**：",
        "- 本目录通过 AI 自动提取生成",
        "- 每个章节包含用于精确匹配的开头文本",
        "- 支持多级章节结构和页码定位",
        ""
    ])
    
    markdown_content = "\n".join(markdown_lines)
    
    # 保存到文件
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"✅ Markdown目录已保存到: {output_path}")
    
    return markdown_content

def generate_simple_toc(toc_json_path: str) -> str:
    """
    生成简洁版的TOC
    
    Args:
        toc_json_path: TOC JSON文件路径
        
    Returns:
        str: 简洁版TOC内容
    """
    with open(toc_json_path, 'r', encoding='utf-8') as f:
        toc_data = json.load(f)
    
    toc_items = toc_data.get('toc', [])
    
    lines = ["# 目录\n"]
    
    for item in toc_items:
        title = item.get('title', '')
        level = item.get('level', 1)
        page_number = item.get('page_number', '')
        
        # 生成缩进
        indent = "  " * (level - 1)
        
        # 生成目录项
        if page_number:
            lines.append(f"{indent}- {title} (第 {page_number} 页)")
        else:
            lines.append(f"{indent}- {title}")
    
    return "\n".join(lines)

def generate_detailed_toc(toc_json_path: str) -> str:
    """
    生成详细版的TOC（包含开头文本）
    
    Args:
        toc_json_path: TOC JSON文件路径
        
    Returns:
        str: 详细版TOC内容
    """
    with open(toc_json_path, 'r', encoding='utf-8') as f:
        toc_data = json.load(f)
    
    toc_items = toc_data.get('toc', [])
    
    lines = [
        "# 📖 详细目录\n",
        "---\n"
    ]
    
    for i, item in enumerate(toc_items, 1):
        title = item.get('title', '')
        level = item.get('level', 1)
        page_number = item.get('page_number', '')
        start_text = item.get('start_text', '')
        
        # 添加章节标题
        if level == 1:
            lines.append(f"## {i:02d}. {title}")
        elif level == 2:
            lines.append(f"### {title}")
        else:
            lines.append(f"#### {title}")
        
        # 添加页码信息
        if page_number:
            lines.append(f"**📍 页码**: {page_number}")
        
        # 添加开头文本
        if start_text:
            lines.append(f"**🔍 开头文本**: {start_text}")
        
        lines.append("")
    
    return "\n".join(lines)

def main():
    """主函数"""
    toc_json_path = "parser_output/20250714_145102_zpdlfg/toc_extraction_result.json"
    
    if not os.path.exists(toc_json_path):
        print(f"❌ 文件不存在: {toc_json_path}")
        return
    
    # 生成不同风格的目录
    base_dir = "parser_output/20250714_145102_zpdlfg"
    
    # 1. 美观版目录
    print("🎨 生成美观版目录...")
    markdown_toc = generate_markdown_toc(
        toc_json_path, 
        os.path.join(base_dir, "toc_beautiful.md")
    )
    
    # 2. 简洁版目录
    print("📝 生成简洁版目录...")
    simple_toc = generate_simple_toc(toc_json_path)
    with open(os.path.join(base_dir, "toc_simple.md"), 'w', encoding='utf-8') as f:
        f.write(simple_toc)
    print(f"✅ 简洁版目录已保存到: {os.path.join(base_dir, 'toc_simple.md')}")
    
    # 3. 详细版目录
    print("📋 生成详细版目录...")
    detailed_toc = generate_detailed_toc(toc_json_path)
    with open(os.path.join(base_dir, "toc_detailed.md"), 'w', encoding='utf-8') as f:
        f.write(detailed_toc)
    print(f"✅ 详细版目录已保存到: {os.path.join(base_dir, 'toc_detailed.md')}")
    
    # 4. 在控制台输出简洁版
    print("\n" + "="*50)
    print("📋 简洁版目录预览:")
    print("="*50)
    print(simple_toc)
    print("="*50)
    
    print(f"\n🎉 所有目录格式已生成完成！")
    print(f"📂 文件位置: {base_dir}")

if __name__ == "__main__":
    main() 