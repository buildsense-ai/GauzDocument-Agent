# 文件名: test.py
# -*- coding: utf-8 -*-

"""
test.py

一个用于本地测试Markdown到Docx转换功能的独立脚本。
"""

# 导入我们自己编写的转换函数
from converter  import convert_md_to_docx_with_images
import os


def main():
    """
    主测试函数。
    """
    # --- 1. 请在这里配置您的输入文件路径 ---
    # 注释：使用 r'...' 格式（原始字符串）来处理Windows路径，可以有效避免反斜杠带来的问题。
    # 请将这里的路径替换为您自己电脑上test.md文件的真实路径。
    input_md_path = r'E:\gaosi\mcp_demo\long_generator\tasks\task_5609aa66-e120-490f-93d7-5d7dd5d3cba4.md'

    # --- 2. 检查输入文件是否存在 ---
    if not os.path.exists(input_md_path):
        print(f"!! [错误] 输入文件不存在，请检查路径是否正确: {input_md_path}")
        return

    # --- 3. 自动生成输出文件的路径 ---
    # 注释：我们将在原始文件名后面加上 "_converted" 并替换后缀为 .docx，
    #       这样可以避免覆盖任何现有文件。
    file_directory = os.path.dirname(input_md_path)
    file_basename = os.path.splitext(os.path.basename(input_md_path))[0]
    output_docx_path = os.path.join(file_directory, f"{file_basename}_converted.docx")

    print("--- 开始测试Markdown到Docx的转换 ---")
    print(f"  输入文件: {input_md_path}")
    print(f"  输出文件: {output_docx_path}")
    print("-" * 40)

    # --- 4. 调用核心转换函数 ---
    result_path = convert_md_to_docx_with_images(
        md_filepath=input_md_path,
        output_docx_path=output_docx_path
    )

    # --- 5. 打印最终结果 ---
    if result_path:
        print("-" * 40)
        print(f"✅ 测试成功！")
        print(f"转换后的Docx文件已保存在: {result_path}")
        print("您现在可以打开这个文件来检查转换效果了。")
    else:
        print("-" * 40)
        print(f"❌ 测试失败。")
        print("请检查上面的日志输出以获取详细的错误信息。")
        print("常见原因：")
        print("  1. 您的系统中没有安装Pandoc本体。")
        print("  2. 必要的Python库（pypandoc, requests, Pillow）没有安装。")
        print("  3. Markdown文件中的图片URL无法访问。")


if __name__ == '__main__':
    main()
