import json
import os

from generator import LongDocumentGenerator as Generator

def main():
    """Main function to run the generator test."""
    # 使用用户提供的大纲
    mock_outline = {
        "title": "关于广州中山纪念堂的文物影响评估报告",
        "description": "本报告旨在对广州中山纪念堂进行文物影响评估。",
        "chapters": [
            {"chapterId": "ch_01", "title": "项目概况", "key_points": ["编制背景", "评估内容和范围", "项目编制依据", "评估目的", "评估原则和思想"]},
            {"chapterId": "ch_02", "title": "建设项目涉及文物情况", "key_points": ["文物概况", "历史沿革", "价值评估", "现状情况"]},
            {"chapterId": "ch_03", "title": "项目建设必要性", "key_points": []},
            {"chapterId": "ch_04", "title": "项目建设概况", "key_points": []},
            {"chapterId": "ch_05", "title": "支撑法律，法规及文件等", "key_points": []},
            {"chapterId": "ch_06", "title": "项目对文物影响评估", "key_points": ["对文物本体安全影响评估", "对文物保护范围内影响评估", "对文物建筑历史景观风貌影响评估", "对文物施工期影响评估"]},
            {"chapterId": "ch_07", "title": "项目监测方案", "key_points": []},
            {"chapterId": "ch_08", "title": "应急方案", "key_points": []},
            {"chapterId": "ch_09", "title": "结论及建议", "key_points": ["评估结论", "要求与建议"]}
        ]
    }

    # 实例化 Generator
    # 注意：请确保您的环境中已经配置了必要的 API 密钥等环境变量
    generator = Generator(task_id="test_task")

    print("开始生成文档...")
    # 调用生成方法
    final_md_content = generator.generate_by_outline(mock_outline)

    # 打印生成的 Markdown 内容
    print("\n--- 生成的文档内容 ---\n")
    print(final_md_content)

    # 可以选择将结果保存到文件
    output_filename = "test_generated_report.md"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(final_md_content)
    print(f"\n文档已保存至 {os.path.abspath(output_filename)}")

if __name__ == "__main__":
    main()