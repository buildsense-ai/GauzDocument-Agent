# 文件名: md_to_docx_converter.py
# -*- coding: utf-8 -*-

"""
md_to_docx_converter.py

使用Pandoc将Markdown文件转换为.docx文件，并能自动处理其中的网络图片和标题样式。
"""

import os
import re
import requests
import uuid
import pypandoc
from typing import Optional

# [已更新] 导入python-docx库中所有需要的模块
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn


def convert_md_to_docx_with_images(md_filepath: str, output_docx_path: str) -> Optional[str]:
    """
    将Markdown文件转换为.docx，自动下载并嵌入其中的网络图片，并按要求设置所有标题的样式。

    Args:
        md_filepath (str): 输入的Markdown文件路径。
        output_docx_path (str): 输出的.docx文件路径。

    Returns:
        Optional[str]: 如果成功，返回输出的.docx文件路径；否则返回None。
    """
    print(f"--- 开始将 {os.path.basename(md_filepath)} 转换为 .docx ---")

    temp_image_dir = os.path.join(os.path.dirname(md_filepath), f"temp_images_{uuid.uuid4()}")
    os.makedirs(temp_image_dir, exist_ok=True)

    try:
        with open(md_filepath, 'r', encoding='utf-8') as f:
            md_content = f.read()

        image_urls = re.findall(r'!\[.*?\]\((.*?)\)', md_content)
        modified_md_content = md_content

        for url in image_urls:
            if url.startswith(('http://', 'https://')):
                try:
                    print(f"--> 正在下载图片: {url}")
                    response = requests.get(url, timeout=20)
                    response.raise_for_status()

                    # 尝试从URL获取文件扩展名，如果失败则默认为.png
                    try:
                        ext = os.path.splitext(url.split('?')[0])[-1][1:]
                        if not ext: ext = 'png'
                    except:
                        ext = 'png'

                    image_filename = f"{uuid.uuid4()}.{ext}"
                    local_image_path = os.path.join(temp_image_dir, image_filename)

                    with open(local_image_path, 'wb') as f:
                        f.write(response.content)

                    modified_md_content = modified_md_content.replace(url, local_image_path)
                    print(f"--> 图片已下载至: {local_image_path}")

                except requests.exceptions.RequestException as e:
                    print(f"!! [警告] 下载图片失败: {url}, 错误: {e}")
                    pass

        print("--- 正在调用Pandoc进行基础转换... ---")
        pypandoc.convert_text(
            modified_md_content,
            'docx',
            format='md',
            outputfile=output_docx_path
        )

        # --- [已更新] 后处理步骤：打开并精细化修改Docx文档样式 ---
        print("--- 正在进行Docx后处理（调整标题样式）... ---")
        doc = Document(output_docx_path)

        # 遍历文档中的所有段落
        for paragraph in doc.paragraphs:
            # Pandoc会将Markdown的'#' '##'等转换为'Heading 1', 'Heading 2'等样式
            # 我们检查段落的样式名称是否以'Heading'开头
            if paragraph.style.name.startswith('Heading'):
                # 1. 设置对齐方式为居中
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

                # 2. 遍历段落中的所有部分(run)，统一设置字体样式
                # 注释：必须遍历run来设置，因为一个段落中可能包含多种格式。
                #       我们在这里强制将所有格式统一。
                for run in paragraph.runs:
                    # 设置字体为宋体
                    run.font.name = '宋体'
                    # 关键：还需要设置东亚字体，以确保在中英文混合时正确显示
                    r = run._element
                    r.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

                    # 设置字号为小四 (12pt)
                    run.font.size = Pt(12)

                    # 设置为粗体
                    run.font.bold = True

                    # 设置颜色为黑色 (R, G, B)
                    run.font.color.rgb = RGBColor(0, 0, 0)

                print(f"  -> 已重设样式并居中标题: '{paragraph.text[:30]}...'")

        # 保存对样式的修改
        doc.save(output_docx_path)
        # --- [更新结束] ---

        print(f"--- .docx 文档已成功生成并完成样式调整: {output_docx_path} ---")
        return output_docx_path

    except Exception as e:
        print(f"!! [错误] Markdown转Docx过程中发生错误: {e}")
        return None
    finally:
        if os.path.exists(temp_image_dir):
            for file in os.listdir(temp_image_dir):
                os.remove(os.path.join(temp_image_dir, file))
            os.rmdir(temp_image_dir)
            print("--- 已清理临时图片文件。 ---")

